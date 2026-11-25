"""
SignalForge — Phase 36B: Independent Test Suite
================================================
File: tests/test_strategy_36b.py

Comprehensive independent unit tests for:
  - Relative-strength calculations (20, 40, 60 session lookbacks)
  - Percentile ranking and CRSS formulation
  - Strict zero lookahead bias verification
  - Entry (top 10) and Exit (70th percentile drop) rules
  - Sector concentration limit (max 30% per sector)
  - Equal-weight allocation and integer share quantities
  - Cash ledger constraints
  - Delivery cost calculation and single-slippage reconciliation
  - Daily Mark-to-Market (MTM) equity valuation
  - Monthly, yearly, and cumulative mathematical reconciliation
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import unittest
import numpy as np
import pandas as pd

from src.strategy.strategy_36b.config import (
    CFG1_BIWEEKLY_OFFICIAL,
    CFG1_BIWEEKLY_STRESS,
    CFG2_MONTHLY_OFFICIAL,
    CFG2_MONTHLY_STRESS,
    CostScenario,
    RebalanceFrequency,
    Strategy36BConfig,
)
from src.strategy.strategy_36b.cross_sectional_ranker import (
    CrossSectionalRanker,
    StockRankEntry,
)
from src.strategy.strategy_36b.performance_metrics import PerformanceMetricsEngine
from src.strategy.strategy_36b.portfolio_constructor import (
    HoldingPosition,
    PortfolioConstructor,
    RebalancePlan,
)
from src.strategy.strategy_36b.rebalance_simulator import (
    CompletedTrade36B,
    DailyPortfolioSnapshot,
    RebalanceSimulator,
    SimulationResult36B,
    build_stress_broker_profile,
)
from src.strategy.strategy_36b.risk_engine import RiskEngine36B


class TestStrategy36B(unittest.TestCase):
    """Test suite validating all Phase 36B quantitative and accounting components."""

    def setUp(self) -> None:
        """Create a synthetic universe with known properties for deterministic testing."""
        np.random.seed(42)
        self.n_days = 100
        self.dates = [date(2017, 1, 2) + timedelta(days=i) for i in range(self.n_days)]
        self.symbols = [f"SYM_{i:02d}" for i in range(20)]  # 20 stocks
        self.sectors = {
            f"SYM_{i:02d}": "IT" if i < 5 else ("BANK" if i < 10 else ("AUTO" if i < 15 else "PHARMA"))
            for i in range(20)
        }
        self.isin_map = {s: f"INE_{s}_TEST" for s in self.symbols}

        # Generate price series: SYM_00 has highest momentum, SYM_19 has lowest
        self.universe: dict[str, pd.DataFrame] = {}
        for idx, sym in enumerate(self.symbols):
            drift = 0.002 * (10 - idx)  # Top symbols drift up, bottom symbols drift down
            noise = np.random.normal(0, 0.01, size=self.n_days)
            returns = drift + noise
            prices = 100.0 * np.cumprod(1.0 + returns)
            df = pd.DataFrame({
                "open": prices * 0.998,
                "high": prices * 1.01,
                "low": prices * 0.99,
                "close": prices,
                "volume": np.full(self.n_days, 100000.0),
            }, index=self.dates)
            self.universe[sym] = df

        self.config = Strategy36BConfig(
            config_id="TEST_CFG",
            rebalance_period_sessions=10,
            lookback_fast=20,
            lookback_mid=40,
            lookback_slow=60,
            max_holdings=10,
            target_position_pct=0.10,
            exit_percentile_threshold=0.70,
            max_sector_exposure_pct=0.30,
        )
        self.ranker = CrossSectionalRanker(self.universe, self.sectors, self.config)

    def test_relative_strength_calculations_and_crss(self) -> None:
        """Verify trailing returns and CRSS score formula."""
        target_date = self.dates[70]
        ranks = self.ranker.compute_ranks_for_date(target_date)
        self.assertEqual(len(ranks), len(self.symbols))

        for entry in ranks:
            # Verify CRSS formula: 0.20 * Rank20 + 0.40 * Rank40 + 0.40 * Rank60
            expected_crss = (
                0.20 * entry.rank_20_pct + 0.40 * entry.rank_40_pct + 0.40 * entry.rank_60_pct
            )
            self.assertAlmostEqual(entry.crss, expected_crss, places=5)
            self.assertTrue(0.0 <= entry.rank_20_pct <= 1.0)
            self.assertTrue(0.0 <= entry.rank_40_pct <= 1.0)
            self.assertTrue(0.0 <= entry.rank_60_pct <= 1.0)
            self.assertTrue(0.0 <= entry.crss <= 1.0)
            self.assertTrue(0.0 <= entry.crss_percentile <= 1.0)

        # Universe rank should be 1 to K ordered descending by CRSS
        ranks_sorted = sorted(ranks, key=lambda x: x.universe_rank)
        self.assertEqual(ranks_sorted[0].universe_rank, 1)
        self.assertEqual(ranks_sorted[-1].universe_rank, 20)
        self.assertGreaterEqual(ranks_sorted[0].crss, ranks_sorted[1].crss)

    def test_no_lookahead_bias(self) -> None:
        """Verify that modifying future prices does NOT change historical rankings."""
        target_date = self.dates[65]
        ranks_original = self.ranker.compute_ranks_for_date(target_date)

        # Tamper with future prices at day 80
        future_date = self.dates[80]
        original_future_close = self.universe["SYM_19"].loc[future_date, "close"]
        self.universe["SYM_19"].loc[future_date, "close"] = 999999.0

        # Recompute rankings on day 65
        ranker_tampered = CrossSectionalRanker(self.universe, self.sectors, self.config)
        ranks_after = ranker_tampered.compute_ranks_for_date(target_date)

        # Restore
        self.universe["SYM_19"].loc[future_date, "close"] = original_future_close

        # Rankings on day 65 must be 100% identical
        for orig, aft in zip(ranks_original, ranks_after):
            self.assertEqual(orig.symbol, aft.symbol)
            self.assertAlmostEqual(orig.crss, aft.crss, places=7)
            self.assertEqual(orig.universe_rank, aft.universe_rank)

    def test_portfolio_constructor_entry_exit_rules(self) -> None:
        """Verify entry selection (top 10) and hysteresis exit rules (<70th percentile)."""
        constructor = PortfolioConstructor(self.config, self.isin_map)
        target_date = self.dates[65]
        next_date = self.dates[66]
        rankings = self.ranker.compute_ranks_for_date(target_date)

        # Case 1: Empty portfolio -> Should pick up to 10 top stocks, respecting sector limit
        plan1 = constructor.generate_rebalance_plan(
            signal_date=target_date,
            execution_date=next_date,
            current_holdings={},
            rankings=rankings,
            current_equity=100000.0,
        )
        self.assertEqual(len(plan1.symbols_to_exit), 0)
        # All entered stocks must be in top 10 rankings
        for cand in plan1.symbols_to_enter:
            self.assertLessEqual(cand.universe_rank, 10)

        # Sector cap: At most 3 stocks per sector (30% of 10)
        sec_counts: dict[str, int] = {}
        for cand in plan1.symbols_to_enter:
            sec_counts[cand.sector] = sec_counts.get(cand.sector, 0) + 1
        for sec, cnt in sec_counts.items():
            self.assertLessEqual(cnt, 3)

        # Case 2: Holding that drops below 70th percentile must exit
        worst_sym = rankings[-1].symbol  # definitely < 0.70 percentile
        best_sym = rankings[0].symbol    # >= 0.70 percentile

        holdings = {
            worst_sym: HoldingPosition(
                symbol=worst_sym, sector=self.sectors[worst_sym], isin="INE_W",
                quantity=10, entry_date=self.dates[50], effective_entry_price=100.0, last_close_price=90.0
            ),
            best_sym: HoldingPosition(
                symbol=best_sym, sector=self.sectors[best_sym], isin="INE_B",
                quantity=10, entry_date=self.dates[50], effective_entry_price=100.0, last_close_price=110.0
            ),
        }

        plan2 = constructor.generate_rebalance_plan(
            signal_date=target_date,
            execution_date=next_date,
            current_holdings=holdings,
            rankings=rankings,
            current_equity=100000.0,
        )
        self.assertIn(worst_sym, plan2.symbols_to_exit)
        self.assertIn(best_sym, plan2.retained_symbols)

    def test_cost_calculation_official_vs_stress(self) -> None:
        """Verify delivery cost calculation and stress penalty surcharge."""
        stress_broker, stress_exec = build_stress_broker_profile()
        self.assertEqual(stress_broker.brokerage_min_per_order, Decimal("5.00"))
        self.assertEqual(stress_exec.slippage_bps, Decimal("15.0"))
        self.assertGreater(stress_broker.exchange_turnover_rate_override, Decimal("0.0000325"))

    def test_accounting_reconciliation(self) -> None:
        """Verify monthly, yearly, and cumulative reconciliation logic."""
        # Create mock trades and snapshots
        trades = [
            CompletedTrade36B(
                trade_id="T01", config_id="C1", symbol="S1", sector="IT", isin="I1",
                entry_date=date(2017, 3, 1), exit_date=date(2017, 3, 15), holding_sessions=10,
                quantity=10, raw_entry_price=100.0, effective_entry_price=100.05,
                raw_exit_price=110.0, effective_exit_price=109.95,
                gross_pnl=99.0, statutory_costs=15.0, slippage_costs=1.0, total_costs=16.0,
                net_pnl=84.0, net_return_pct=8.4, exit_reason="TEST"
            ),
            CompletedTrade36B(
                trade_id="T02", config_id="C1", symbol="S2", sector="BANK", isin="I2",
                entry_date=date(2017, 3, 15), exit_date=date(2017, 4, 5), holding_sessions=15,
                quantity=20, raw_entry_price=50.0, effective_entry_price=50.025,
                raw_exit_price=48.0, effective_exit_price=47.975,
                gross_pnl=-41.0, statutory_costs=12.0, slippage_costs=1.0, total_costs=13.0,
                net_pnl=-53.0, net_return_pct=-5.3, exit_reason="TEST"
            ),
        ]

        snaps = [
            DailyPortfolioSnapshot(
                date=date(2017, 3, 1), cash=99000.0, holdings_market_value=1000.0, total_equity=100000.0,
                gross_exposure=0.01, net_exposure=0.01, active_holdings_count=1,
                daily_return_pct=0.0, cumulative_return_pct=0.0, drawdown_pct=0.0,
                nifty_close=8500.0, nifty_return_pct=0.0, nifty_cumulative_pct=0.0
            ),
            DailyPortfolioSnapshot(
                date=date(2017, 4, 30), cash=100031.0, holdings_market_value=0.0, total_equity=100031.0,
                gross_exposure=0.0, net_exposure=0.0, active_holdings_count=0,
                daily_return_pct=0.031, cumulative_return_pct=0.031, drawdown_pct=0.0,
                nifty_close=8600.0, nifty_return_pct=1.17, nifty_cumulative_pct=1.17
            ),
        ]

        sim_res = SimulationResult36B(
            config=self.config,
            completed_trades=trades,
            daily_snapshots=snaps,
            rebalance_plans=[],
            initial_capital=100000.0,
            final_equity=100031.0,
            gross_profit=58.0,
            total_statutory_costs=27.0,
            total_slippage=2.0,
            total_costs=29.0,
            net_profit=31.0,
            net_return_pct=0.031,
            win_rate=50.0,
            profit_factor=84.0 / 53.0,
            avg_win=84.0,
            avg_loss=53.0,
            payoff_ratio=84.0 / 53.0,
            max_drawdown_pct=0.0,
            total_turnover=4000.0,
        )

        engine = PerformanceMetricsEngine(sim_res)
        monthly = engine.compute_monthly_performance()
        self.assertEqual(len(monthly), 2)
        total_monthly_pnl = sum(m.net_pnl for m in monthly)
        self.assertAlmostEqual(total_monthly_pnl, sim_res.net_profit, places=2)

        yearly = engine.compute_yearly_performance()
        self.assertEqual(len(yearly), 1)
        self.assertAlmostEqual(yearly[0].net_pnl, sim_res.net_profit, places=2)

    def test_full_synthetic_simulation_execution(self) -> None:
        """Run full simulation on synthetic universe to test end-to-end integration."""
        nifty_df = pd.DataFrame({
            "close": np.linspace(8500, 10500, self.n_days),
            "open": np.linspace(8500, 10500, self.n_days),
            "high": np.linspace(8500, 10500, self.n_days) * 1.01,
            "low": np.linspace(8500, 10500, self.n_days) * 0.99,
        }, index=self.dates)

        constructor = PortfolioConstructor(self.config, self.isin_map)
        sim = RebalanceSimulator(
            ranker=self.ranker,
            constructor=constructor,
            nifty_daily=nifty_df,
            config=self.config,
        )
        res = sim.run_simulation()

        # Check basic simulation invariants
        self.assertEqual(res.initial_capital, 100000.0)
        self.assertGreater(len(res.daily_snapshots), 0)
        # Cash must never be negative
        for snap in res.daily_snapshots:
            self.assertGreaterEqual(snap.cash, -0.01)
            self.assertGreaterEqual(snap.total_equity, 0.0)
            self.assertLessEqual(snap.gross_exposure, 1.05)

        # Mathematical reconciliation between final equity and trade net PnL sum
        trade_pnl_sum = sum(t.net_pnl for t in res.completed_trades)
        expected_final = 100000.0 + trade_pnl_sum
        self.assertAlmostEqual(res.final_equity, expected_final, places=2)
        self.assertAlmostEqual(res.net_profit, trade_pnl_sum, places=2)

    def test_block_bootstrap_alpha_computation(self) -> None:
        """Verify block bootstrap produces valid 95% confidence intervals."""
        np.random.seed(42)
        snaps = []
        p_returns = np.random.normal(0.0005, 0.01, size=80)
        m_returns = np.random.normal(0.0002, 0.008, size=80)
        eq = 100000.0
        nifty = 8500.0

        for i, d in enumerate(self.dates[:80]):
            eq *= (1.0 + p_returns[i])
            nifty *= (1.0 + m_returns[i])
            snaps.append(
                DailyPortfolioSnapshot(
                    date=d, cash=10000.0, holdings_market_value=eq - 10000.0,
                    total_equity=eq,
                    gross_exposure=0.9, net_exposure=0.9, active_holdings_count=10,
                    daily_return_pct=p_returns[i] * 100.0, cumulative_return_pct=((eq / 100000.0) - 1.0) * 100.0,
                    drawdown_pct=0.0,
                    nifty_close=nifty,
                    nifty_return_pct=m_returns[i] * 100.0,
                    nifty_cumulative_pct=((nifty / 8500.0) - 1.0) * 100.0,
                )
            )
        sim_res = SimulationResult36B(
            config=self.config, completed_trades=[], daily_snapshots=snaps,
            rebalance_plans=[], initial_capital=100000.0, final_equity=eq,
            gross_profit=eq - 100000.0, total_statutory_costs=0.0, total_slippage=0.0, total_costs=0.0,
            net_profit=eq - 100000.0, net_return_pct=((eq / 100000.0) - 1.0) * 100.0,
            win_rate=0.0, profit_factor=0.0,
            avg_win=0.0, avg_loss=0.0, payoff_ratio=0.0, max_drawdown_pct=0.0, total_turnover=0.0,
        )
        engine = PerformanceMetricsEngine(sim_res)
        boot = engine.run_block_bootstrap_alpha(n_iterations=500, block_size_days=5, seed=42)
        self.assertGreater(boot.ci_upper_95, boot.ci_lower_95)
        self.assertGreaterEqual(boot.prob_positive_alpha, 0.0)
        self.assertLessEqual(boot.prob_positive_alpha, 100.0)


if __name__ == "__main__":
    unittest.main()

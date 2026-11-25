"""
SignalForge — Phase 36B: Portfolio Rebalance Simulator
======================================================
File: src/strategy/strategy_36b/rebalance_simulator.py

Simulates multi-asset cross-sectional relative strength rebalancing with integer share sizing,
strict cash delivery accounting, exact single-slippage statutory deduction, and full
daily Mark-to-Market (MTM) equity tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.backtest.indian_delivery_costs import (
    BrokerChargeProfile,
    DPBillingMode,
    ExecutionCostAssumptions,
    GROWW_DELIVERY_PROFILE,
)
from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.strategy_36b.config import (
    CostScenario,
    RebalanceFrequency,
    Strategy36BConfig,
)
from src.strategy.strategy_36b.cross_sectional_ranker import (
    CrossSectionalRanker,
    StockRankEntry,
)
from src.strategy.strategy_36b.portfolio_constructor import (
    HoldingPosition,
    PortfolioConstructor,
    RebalancePlan,
)


@dataclass
class CompletedTrade36B:
    """Represents a completed round-trip trade in Phase 36B."""
    trade_id: str
    config_id: str
    symbol: str
    sector: str
    isin: str
    entry_date: date
    exit_date: date
    holding_sessions: int
    quantity: int
    raw_entry_price: float
    effective_entry_price: float
    raw_exit_price: float
    effective_exit_price: float
    gross_pnl: float
    statutory_costs: float
    slippage_costs: float
    total_costs: float
    net_pnl: float
    net_return_pct: float
    exit_reason: str


@dataclass
class DailyPortfolioSnapshot:
    """Daily snapshot of portfolio equity, cash, and exposure."""
    date: date
    cash: float
    holdings_market_value: float
    total_equity: float
    gross_exposure: float
    net_exposure: float
    active_holdings_count: int
    daily_return_pct: float
    cumulative_return_pct: float
    drawdown_pct: float
    nifty_close: float
    nifty_return_pct: float
    nifty_cumulative_pct: float


@dataclass
class SimulationResult36B:
    """Comprehensive result of a Phase 36B backtest simulation."""
    config: Strategy36BConfig
    completed_trades: List[CompletedTrade36B]
    daily_snapshots: List[DailyPortfolioSnapshot]
    rebalance_plans: List[RebalancePlan]
    initial_capital: float
    final_equity: float
    gross_profit: float
    total_statutory_costs: float
    total_slippage: float
    total_costs: float
    net_profit: float
    net_return_pct: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    max_drawdown_pct: float
    total_turnover: float
    notes: List[str] = field(default_factory=list)


def build_stress_broker_profile() -> Tuple[BrokerChargeProfile, ExecutionCostAssumptions]:
    """
    Constructs a verified conservative stress profile where statutory rates
    are strictly >= official rates, and slippage is 15 bps (3x higher).
    """
    stress_broker = BrokerChargeProfile(
        broker_name="Groww",
        pricing_plan="Conservative Stress Schedule (₹406/cr)",
        delivery_brokerage_rate=Decimal("0.001"),
        brokerage_min_per_order=Decimal("5.00"),
        brokerage_max_per_order=Decimal("20.00"),
        dp_billing_mode=DPBillingMode.PER_EXECUTED_ORDER,
        # ₹406.25/cr = 1.25x penalty surcharge over statutory ₹325/cr rate
        exchange_turnover_rate_override=Decimal("406.25") / Decimal("10000000"),
        is_hypothetical_override=True,
        override_description="Stress test with +25% exchange rate surcharge",
    )
    stress_exec = ExecutionCostAssumptions(
        slippage_bps=Decimal("15.0"),
        spread_bps=Decimal("5.0"),
    )
    return stress_broker, stress_exec


class RebalanceSimulator:
    """
    Executes the multi-session portfolio simulation for Phase 36B.
    """

    def __init__(
        self,
        ranker: CrossSectionalRanker,
        constructor: PortfolioConstructor,
        nifty_daily: pd.DataFrame,
        config: Strategy36BConfig,
    ) -> None:
        self.ranker = ranker
        self.constructor = constructor
        self.nifty_daily = nifty_daily
        self.config = config

    def run_simulation(self) -> SimulationResult36B:
        """Runs the complete backtest simulation from 2017 to 2019."""
        trading_dates = self.ranker.trading_dates
        total_sessions = len(trading_dates)

        # Setup cost profiles
        use_stress = self.config.use_stress_costs
        slippage_factor = self.config.execution_slippage_bps / 10000.0

        stress_broker, stress_exec = (
            build_stress_broker_profile() if use_stress else (None, None)
        )

        cash = float(self.config.initial_capital)
        holdings: Dict[str, HoldingPosition] = {}
        completed_trades: List[CompletedTrade36B] = []
        snapshots: List[DailyPortfolioSnapshot] = []
        rebalance_plans: List[RebalancePlan] = []
        trade_counter = 0

        # Lookback requirement
        warmup_sessions = max(
            self.config.lookback_fast,
            self.config.lookback_mid,
            self.config.lookback_slow,
        )

        # Rebalance cadence tracking
        sessions_since_rebalance = 0
        pending_plan: Optional[RebalancePlan] = None
        peak_equity = float(self.config.initial_capital)

        # Align Nifty series
        nifty_closes = self.nifty_daily["close"].reindex(trading_dates).ffill().bfill()
        nifty_start_val = float(nifty_closes.iloc[0])

        for day_idx, current_date in enumerate(trading_dates):
            # 1. Execute Pending Rebalance Plan (if generated on previous session's close)
            if pending_plan is not None and pending_plan.execution_date == current_date:
                # A. Execute Exits first to release cash
                for sym in pending_plan.symbols_to_exit:
                    if sym in holdings:
                        pos = holdings.pop(sym)
                        raw_exit = self.ranker.get_open_price(sym, current_date)
                        eff_exit = raw_exit * (1.0 - slippage_factor)

                        # Calculate statutory & execution costs
                        cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                            symbol=pos.symbol,
                            isin=pos.isin,
                            entry_date=pos.entry_date,
                            exit_date=current_date,
                            entry_price=pos.effective_entry_price,
                            exit_price=eff_exit,
                            quantity=pos.quantity,
                            broker_profile=stress_broker,
                            execution_assumptions=stress_exec,
                            use_stress_profile=use_stress,
                            order_id_prefix="P36B",
                        )

                        gross_pnl = round(float(cost_sum.gross_pnl), 2)
                        statutory_costs = round(
                            cost_sum.total_friction_costs - cost_sum.total_execution_friction, 2
                        )
                        slippage_costs = round(float(cost_sum.total_execution_friction), 2)
                        total_costs = round(float(cost_sum.total_friction_costs), 2)
                        net_pnl = round(gross_pnl - statutory_costs, 2)
                        net_ret_pct = (
                            (net_pnl / (pos.quantity * pos.effective_entry_price)) * 100.0
                            if (pos.quantity * pos.effective_entry_price) > 0 else 0.0
                        )

                        # Credit cash back to ledger
                        cash += (pos.quantity * pos.effective_entry_price) + net_pnl

                        # Holding duration in trading sessions
                        entry_idx = trading_dates.index(pos.entry_date)
                        holding_sessions = day_idx - entry_idx

                        trade_counter += 1
                        completed_trades.append(
                            CompletedTrade36B(
                                trade_id=f"T36B_{self.config.config_id}_{trade_counter:04d}",
                                config_id=self.config.config_id,
                                symbol=pos.symbol,
                                sector=pos.sector,
                                isin=pos.isin,
                                entry_date=pos.entry_date,
                                exit_date=current_date,
                                holding_sessions=holding_sessions,
                                quantity=pos.quantity,
                                raw_entry_price=pos.effective_entry_price / (1.0 + slippage_factor),
                                effective_entry_price=pos.effective_entry_price,
                                raw_exit_price=raw_exit,
                                effective_exit_price=eff_exit,
                                gross_pnl=gross_pnl,
                                statutory_costs=statutory_costs,
                                slippage_costs=slippage_costs,
                                total_costs=total_costs,
                                net_pnl=net_pnl,
                                net_return_pct=net_ret_pct,
                                exit_reason="REBALANCE_RANK_DROP",
                            )
                        )

                # B. Execute Entries
                num_entries = len(pending_plan.symbols_to_enter)
                if num_entries > 0 and cash > 100.0:
                    # Current portfolio equity estimate
                    curr_holdings_val = sum(
                        h.quantity * self.ranker.get_open_price(h.symbol, current_date)
                        for h in holdings.values()
                    )
                    est_equity = cash + curr_holdings_val
                    target_alloc = est_equity * self.config.target_position_pct

                    # Divide available cash equally among new entries (capped at target_alloc)
                    cash_per_entry = min(target_alloc, cash / num_entries)

                    for entry_rank in pending_plan.symbols_to_enter:
                        sym = entry_rank.symbol
                        raw_entry = self.ranker.get_open_price(sym, current_date)
                        eff_entry = raw_entry * (1.0 + slippage_factor)

                        # Integer shares
                        qty = int(cash_per_entry // eff_entry)
                        pos_cost = qty * eff_entry

                        if qty > 0 and pos_cost <= cash:
                            cash -= pos_cost
                            isin = self.constructor.isin_map.get(sym, f"INE_{sym}_CANONICAL")
                            holdings[sym] = HoldingPosition(
                                symbol=sym,
                                sector=entry_rank.sector,
                                isin=isin,
                                quantity=qty,
                                entry_date=current_date,
                                effective_entry_price=eff_entry,
                                last_close_price=raw_entry,
                            )

                rebalance_plans.append(pending_plan)
                pending_plan = None
                sessions_since_rebalance = 0

            # 2. Daily Mark-to-Market (MTM) Portfolio Valuation
            holdings_mtm = 0.0
            for sym, pos in list(holdings.items()):
                close_px = self.ranker.get_close_price(sym, current_date)
                pos.last_close_price = close_px
                holdings_mtm += pos.quantity * close_px

            total_equity = cash + holdings_mtm
            gross_exposure = (holdings_mtm / total_equity) if total_equity > 0 else 0.0
            net_exposure = gross_exposure  # Long-only: Net == Gross

            # Update Peak and Drawdown
            if total_equity > peak_equity:
                peak_equity = total_equity
            drawdown_pct = ((peak_equity - total_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0

            # Returns calculation
            prev_equity = snapshots[-1].total_equity if snapshots else float(self.config.initial_capital)
            daily_ret_pct = ((total_equity / prev_equity) - 1.0) * 100.0
            cum_ret_pct = ((total_equity / self.config.initial_capital) - 1.0) * 100.0

            # Nifty returns
            nifty_curr = float(nifty_closes.loc[current_date])
            prev_nifty = float(nifty_closes.iloc[day_idx - 1]) if day_idx > 0 else nifty_curr
            nifty_ret_pct = ((nifty_curr / prev_nifty) - 1.0) * 100.0
            nifty_cum_pct = ((nifty_curr / nifty_start_val) - 1.0) * 100.0

            snapshots.append(
                DailyPortfolioSnapshot(
                    date=current_date,
                    cash=round(cash, 2),
                    holdings_market_value=round(holdings_mtm, 2),
                    total_equity=round(total_equity, 2),
                    gross_exposure=round(gross_exposure, 4),
                    net_exposure=round(net_exposure, 4),
                    active_holdings_count=len(holdings),
                    daily_return_pct=round(daily_ret_pct, 4),
                    cumulative_return_pct=round(cum_ret_pct, 4),
                    drawdown_pct=round(drawdown_pct, 4),
                    nifty_close=round(nifty_curr, 2),
                    nifty_return_pct=round(nifty_ret_pct, 4),
                    nifty_cumulative_pct=round(nifty_cum_pct, 4),
                )
            )

            # 3. Check for Terminal Session Liquidation (end of 2019-12-31)
            if day_idx == total_sessions - 1:
                # Terminal liquidation of all open holdings at final close
                for sym in list(holdings.keys()):
                    pos = holdings.pop(sym)
                    raw_exit = pos.last_close_price
                    eff_exit = raw_exit * (1.0 - slippage_factor)

                    cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                        symbol=pos.symbol,
                        isin=pos.isin,
                        entry_date=pos.entry_date,
                        exit_date=current_date,
                        entry_price=pos.effective_entry_price,
                        exit_price=eff_exit,
                        quantity=pos.quantity,
                        broker_profile=stress_broker,
                        execution_assumptions=stress_exec,
                        use_stress_profile=use_stress,
                        order_id_prefix="P36B",
                    )

                    gross_pnl = round(float(cost_sum.gross_pnl), 2)
                    statutory_costs = round(
                        cost_sum.total_friction_costs - cost_sum.total_execution_friction, 2
                    )
                    slippage_costs = round(float(cost_sum.total_execution_friction), 2)
                    total_costs = round(float(cost_sum.total_friction_costs), 2)
                    net_pnl = round(gross_pnl - statutory_costs, 2)
                    net_ret_pct = (
                        (net_pnl / (pos.quantity * pos.effective_entry_price)) * 100.0
                        if (pos.quantity * pos.effective_entry_price) > 0 else 0.0
                    )

                    cash += (pos.quantity * pos.effective_entry_price) + net_pnl
                    entry_idx = trading_dates.index(pos.entry_date)
                    holding_sessions = day_idx - entry_idx

                    trade_counter += 1
                    completed_trades.append(
                        CompletedTrade36B(
                            trade_id=f"T36B_{self.config.config_id}_{trade_counter:04d}",
                            config_id=self.config.config_id,
                            symbol=pos.symbol,
                            sector=pos.sector,
                            isin=pos.isin,
                            entry_date=pos.entry_date,
                            exit_date=current_date,
                            holding_sessions=holding_sessions,
                            quantity=pos.quantity,
                            raw_entry_price=pos.effective_entry_price / (1.0 + slippage_factor),
                            effective_entry_price=pos.effective_entry_price,
                            raw_exit_price=raw_exit,
                            effective_exit_price=eff_exit,
                            gross_pnl=gross_pnl,
                            statutory_costs=statutory_costs,
                            slippage_costs=slippage_costs,
                            total_costs=total_costs,
                            net_pnl=net_pnl,
                            net_return_pct=net_ret_pct,
                            exit_reason="TERMINAL_LIQUIDATION",
                        )
                    )
                # Update final snapshot
                snapshots[-1].cash = round(cash, 2)
                snapshots[-1].holdings_market_value = 0.0
                snapshots[-1].total_equity = round(cash, 2)
                snapshots[-1].gross_exposure = 0.0
                snapshots[-1].net_exposure = 0.0
                snapshots[-1].active_holdings_count = 0
                break

            # 4. Check for Next Rebalance Signal
            if day_idx >= warmup_sessions:
                sessions_since_rebalance += 1
                if sessions_since_rebalance >= self.config.rebalance_period_sessions:
                    # Signal date is current_date; execution date is next trading session
                    next_date = trading_dates[day_idx + 1]
                    rankings = self.ranker.compute_ranks_for_date(current_date)
                    plan = self.constructor.generate_rebalance_plan(
                        signal_date=current_date,
                        execution_date=next_date,
                        current_holdings=holdings,
                        rankings=rankings,
                        current_equity=total_equity,
                    )
                    pending_plan = plan

        # Calculate final summary statistics
        final_equity = round(cash, 2)
        net_profit = round(final_equity - self.config.initial_capital, 2)
        net_return_pct = round((net_profit / self.config.initial_capital) * 100.0, 2)

        gross_profit = round(sum(t.gross_pnl for t in completed_trades), 2)
        total_statutory = round(sum(t.statutory_costs for t in completed_trades), 2)
        total_slippage = round(sum(t.slippage_costs for t in completed_trades), 2)
        total_costs = round(sum(t.total_costs for t in completed_trades), 2)

        wins = [t for t in completed_trades if t.net_pnl > 0]
        losses = [t for t in completed_trades if t.net_pnl < 0]

        win_rate = (len(wins) / len(completed_trades) * 100.0) if completed_trades else 0.0
        sum_win = sum(t.net_pnl for t in wins)
        sum_loss = abs(sum(t.net_pnl for t in losses))
        profit_factor = (sum_win / sum_loss) if sum_loss > 0 else (999.0 if sum_win > 0 else 0.0)

        avg_win = (sum_win / len(wins)) if wins else 0.0
        avg_loss = (sum_loss / len(losses)) if losses else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        max_dd = max(s.drawdown_pct for s in snapshots) if snapshots else 0.0
        total_turnover = sum(
            (t.quantity * t.effective_entry_price) + (t.quantity * t.effective_exit_price)
            for t in completed_trades
        )

        return SimulationResult36B(
            config=self.config,
            completed_trades=completed_trades,
            daily_snapshots=snapshots,
            rebalance_plans=rebalance_plans,
            initial_capital=float(self.config.initial_capital),
            final_equity=final_equity,
            gross_profit=gross_profit,
            total_statutory_costs=total_statutory,
            total_slippage=total_slippage,
            total_costs=total_costs,
            net_profit=net_profit,
            net_return_pct=net_return_pct,
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            payoff_ratio=round(payoff_ratio, 2),
            max_drawdown_pct=round(max_dd, 2),
            total_turnover=round(total_turnover, 2),
        )

"""
SignalForge — Phase 36C: Portfolio Rebalance Simulator & Risk Engine
====================================================================
File: src/strategy/strategy_36c/rebalance_simulator.py

Simulates multi-asset cross-sectional relative strength rebalancing with:
  - Nifty 50 macro regime filter (CFG-1, CFG-3)
  - 3 x ATR(14) trailing stops with gap-through-stop and intraday modeling (CFG-2, CFG-3)
  - Dynamic cash and ranking-based exits (CFG-4)
  - Full single-slippage delivery cost accounting with zero discrepancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
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
from src.strategy.strategy_36c.config import (
    CostScenario,
    Strategy36CConfig,
)
from src.strategy.strategy_36c.cross_sectional_ranker import (
    CrossSectionalRanker,
    StockRankEntry,
)
from src.strategy.strategy_36c.portfolio_constructor import (
    HoldingPosition,
    PortfolioConstructor,
    RebalancePlan,
)


@dataclass
class CompletedTrade36C:
    """Represents a completed round-trip trade in Phase 36C."""
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
    is_bull_regime: bool


@dataclass
class SimulationResult36C:
    """Comprehensive result of a Phase 36C backtest simulation."""
    config: Strategy36CConfig
    completed_trades: List[CompletedTrade36C]
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
    Executes the multi-session portfolio simulation for Phase 36C.
    """

    def __init__(
        self,
        ranker: CrossSectionalRanker,
        constructor: PortfolioConstructor,
        nifty_daily: pd.DataFrame,
        atr_dict: Dict[str, pd.Series],
        config: Strategy36CConfig,
    ) -> None:
        self.ranker = ranker
        self.constructor = constructor
        self.nifty_daily = nifty_daily
        self.atr_dict = atr_dict
        self.config = config

    def run_simulation(self) -> SimulationResult36C:
        """Runs the complete backtest simulation across 2017 to 2019."""
        trading_dates = self.ranker.trading_dates
        total_sessions = len(trading_dates)

        use_stress = self.config.use_stress_costs
        slippage_factor = self.config.execution_slippage_bps / 10000.0

        stress_broker, stress_exec = (
            build_stress_broker_profile() if use_stress else (None, None)
        )

        cash = float(self.config.initial_capital)
        holdings: Dict[str, HoldingPosition] = {}
        completed_trades: List[CompletedTrade36C] = []
        snapshots: List[DailyPortfolioSnapshot] = []
        rebalance_plans: List[RebalancePlan] = []
        trade_counter = 0

        warmup_sessions = max(
            self.config.lookback_fast,
            self.config.lookback_mid,
            self.config.lookback_slow,
        )

        sessions_since_rebalance = 0
        pending_plan: Optional[RebalancePlan] = None
        peak_equity = float(self.config.initial_capital)

        nifty_closes = self.nifty_daily["close"].reindex(trading_dates).ffill().bfill()
        nifty_start_val = float(nifty_closes.iloc[0])
        nifty_regimes = self.nifty_daily["is_bull_regime"].reindex(trading_dates).fillna(False)

        for day_idx, current_date in enumerate(trading_dates):
            current_is_bull = bool(nifty_regimes.loc[current_date])

            # 1. Execute Pending Rebalance Plan at Open
            if pending_plan is not None and pending_plan.execution_date == current_date:
                # A. Execute Exits first
                for sym in pending_plan.symbols_to_exit:
                    if sym in holdings:
                        pos = holdings.pop(sym)
                        raw_exit = self.ranker.get_open_price(sym, current_date)
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
                            order_id_prefix="P36C",
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
                            CompletedTrade36C(
                                trade_id=f"T36C_{self.config.config_id}_{trade_counter:04d}",
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
                                exit_reason="REBALANCE_EXIT",
                            )
                        )

                # B. Execute Entries (only if allowed by regime)
                can_enter = True
                if self.config.use_regime_filter:
                    # In CFG-1 and CFG-3, regime on signal date must be Bull to enter
                    sig_date = pending_plan.signal_date
                    can_enter = bool(nifty_regimes.loc[sig_date])

                num_entries = len(pending_plan.symbols_to_enter) if can_enter else 0
                if num_entries > 0 and cash > 100.0:
                    curr_holdings_val = sum(
                        h.quantity * self.ranker.get_open_price(h.symbol, current_date)
                        for h in holdings.values()
                    )
                    est_equity = cash + curr_holdings_val
                    target_alloc = est_equity * self.config.target_position_pct
                    cash_per_entry = min(target_alloc, cash / num_entries)

                    for entry_rank in pending_plan.symbols_to_enter:
                        sym = entry_rank.symbol
                        raw_entry = self.ranker.get_open_price(sym, current_date)
                        eff_entry = raw_entry * (1.0 + slippage_factor)

                        qty = int(cash_per_entry // eff_entry)
                        pos_cost = qty * eff_entry

                        if qty > 0 and pos_cost <= cash:
                            cash -= pos_cost
                            isin = self.constructor.isin_map.get(sym, f"INE_{sym}_CANONICAL")

                            # Initial ATR stop level
                            initial_stop = 0.0
                            if self.config.use_atr_stop and sym in self.atr_dict:
                                sig_date = pending_plan.signal_date
                                if sig_date in self.atr_dict[sym].index:
                                    atr_val = float(self.atr_dict[sym].loc[sig_date])
                                    initial_stop = raw_entry - (self.config.atr_stop_multiplier * atr_val)

                            holdings[sym] = HoldingPosition(
                                symbol=sym,
                                sector=entry_rank.sector,
                                isin=isin,
                                quantity=qty,
                                entry_date=current_date,
                                effective_entry_price=eff_entry,
                                last_close_price=raw_entry,
                                highest_close_since_entry=raw_entry,
                                current_atr_stop=initial_stop,
                            )

                rebalance_plans.append(pending_plan)
                pending_plan = None
                sessions_since_rebalance = 0

            # 2. Check ATR Trailing Stops on Active Holdings during day_idx
            if self.config.use_atr_stop and holdings:
                for sym in list(holdings.keys()):
                    pos = holdings[sym]
                    if pos.entry_date == current_date:
                        # Entered today at open; skip stop check on the exact entry day
                        continue

                    # Current stop level calculated from previous day close
                    stop_level = pos.current_atr_stop
                    if stop_level <= 0.0:
                        continue

                    open_px = self.ranker.get_open_price(sym, current_date)
                    low_px = self.ranker.get_low_price(sym, current_date)

                    stop_triggered = False
                    raw_exit = 0.0
                    exit_reason = ""

                    # A. Gap-through-stop at open
                    if open_px <= stop_level:
                        stop_triggered = True
                        raw_exit = open_px  # Conservative fill at open
                        exit_reason = "STOP_GAP_OPEN"
                    # B. Intraday stop trigger
                    elif low_px <= stop_level:
                        stop_triggered = True
                        raw_exit = stop_level  # Filled at stop price
                        exit_reason = "STOP_INTRADAY"

                    if stop_triggered:
                        holdings.pop(sym)
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
                            order_id_prefix="P36C",
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
                            CompletedTrade36C(
                                trade_id=f"T36C_{self.config.config_id}_{trade_counter:04d}",
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
                                exit_reason=exit_reason,
                            )
                        )

            # 3. Daily Mark-to-Market Valuation & ATR Stop Updates
            holdings_mtm = 0.0
            for sym, pos in list(holdings.items()):
                close_px = self.ranker.get_close_price(sym, current_date)
                pos.last_close_price = close_px
                holdings_mtm += pos.quantity * close_px

                # Update highest close and ratchet ATR stop upward
                if close_px > pos.highest_close_since_entry:
                    pos.highest_close_since_entry = close_px

                if self.config.use_atr_stop and sym in self.atr_dict:
                    if current_date in self.atr_dict[sym].index:
                        atr_val = float(self.atr_dict[sym].loc[current_date])
                        new_stop = close_px - (self.config.atr_stop_multiplier * atr_val)
                        if new_stop > pos.current_atr_stop:
                            pos.current_atr_stop = new_stop

            total_equity = cash + holdings_mtm
            gross_exposure = (holdings_mtm / total_equity) if total_equity > 0 else 0.0
            net_exposure = gross_exposure

            if total_equity > peak_equity:
                peak_equity = total_equity
            drawdown_pct = ((peak_equity - total_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0

            prev_equity = snapshots[-1].total_equity if snapshots else float(self.config.initial_capital)
            daily_ret_pct = ((total_equity / prev_equity) - 1.0) * 100.0
            cum_ret_pct = ((total_equity / self.config.initial_capital) - 1.0) * 100.0

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
                    is_bull_regime=current_is_bull,
                )
            )

            # 4. Terminal Session Liquidation (2019-12-31)
            if day_idx == total_sessions - 1:
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
                        order_id_prefix="P36C",
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
                        CompletedTrade36C(
                            trade_id=f"T36C_{self.config.config_id}_{trade_counter:04d}",
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
                snapshots[-1].cash = round(cash, 2)
                snapshots[-1].holdings_market_value = 0.0
                snapshots[-1].total_equity = round(cash, 2)
                snapshots[-1].gross_exposure = 0.0
                snapshots[-1].net_exposure = 0.0
                snapshots[-1].active_holdings_count = 0
                break

            # 5. Check Next Rebalance Plan Generation at Close
            if day_idx >= warmup_sessions:
                sessions_since_rebalance += 1

                # Check if regime changed
                prev_is_bull = bool(nifty_regimes.loc[trading_dates[day_idx - 1]]) if day_idx > 0 else current_is_bull
                regime_switched_to_bear = self.config.use_regime_filter and prev_is_bull and not current_is_bull
                regime_switched_to_bull = self.config.use_regime_filter and not prev_is_bull and current_is_bull

                trigger_rebalance = False
                if regime_switched_to_bear:
                    # Immediate liquidation to cash on next open
                    trigger_rebalance = True
                elif regime_switched_to_bull:
                    # Immediate deployment into equities on next open
                    trigger_rebalance = True
                elif sessions_since_rebalance >= self.config.rebalance_period_sessions:
                    # Scheduled bi-weekly rebalance
                    trigger_rebalance = True

                if trigger_rebalance:
                    next_date = trading_dates[day_idx + 1]
                    rankings = self.ranker.compute_ranks_for_date(current_date)
                    plan = self.constructor.generate_rebalance_plan(
                        signal_date=current_date,
                        execution_date=next_date,
                        current_holdings=holdings,
                        rankings=rankings,
                        is_bull_regime=current_is_bull,
                    )
                    pending_plan = plan

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

        return SimulationResult36C(
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

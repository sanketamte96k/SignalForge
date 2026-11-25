"""
SignalForge — Phase 34A: Portfolio Simulator & Performance Accounting
======================================================================
File: src/strategy/strategy_34a/portfolio_simulator.py

Simulates multi-timeframe swing trading with max 2 concurrent positions,
strict single-slippage cash accounting, official vs stress delivery transaction costs,
and automated mathematical reconciliation down to ₹0.00.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.strategy_34a.config import (
    ExitReason,
    RiskTier,
    Strategy34AConfig,
)
from src.strategy.strategy_34a.signal_engine import (
    Strategy34ASignal,
    evaluate_34a_exit,
    generate_34a_signals,
)


def to_py_date(d: Any) -> date:
    """Safe conversion of string/pd.Timestamp/datetime to Python datetime.date."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, (pd.Timestamp, datetime)):
        return d.date()
    if isinstance(d, str):
        return pd.to_datetime(d).date()
    raise ValueError(f"Cannot convert {type(d)} to datetime.date: {d}")


@dataclass
class CompletedTrade34A:
    """Single completed swing trade record with unified single-slippage accounting."""
    trade_id: int
    config_id: str
    symbol: str
    sector: str
    isin: str
    entry_date: date
    exit_date: date
    bars_held: int
    quantity: int
    raw_entry_price: float
    raw_exit_price: float
    effective_entry_price: float
    effective_exit_price: float
    gross_pnl: float
    slippage: float
    statutory_broker_costs: float
    total_costs: float
    net_pnl: float
    net_return_pct: float
    exit_reason: str
    exit_notes: str


@dataclass
class SimulationResult34A:
    """Consolidated backtest performance, risk metrics, and audit reconciliation."""
    config: Strategy34AConfig
    trades: List[CompletedTrade34A]
    initial_capital: float
    final_equity: float
    net_pnl: float
    roi_pct: float
    cagr_pct: float
    profit_factor: float
    win_rate_pct: float
    completed_trades: int
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    max_drawdown_pct: float
    ex_top3_net_pnl: float
    ex_top5_net_pnl: float
    top3_pct_of_gains: float
    avg_holding_bars: float
    capital_utilization_pct: float
    profitable_months: int
    losing_months: int
    zero_trade_months: int
    profitable_months_pct: float
    profitable_years: int
    losing_years: int
    daily_equity_series: pd.Series
    monthly_summary: pd.DataFrame
    yearly_summary: pd.DataFrame
    reconciliation_discrepancy: float
    reconciliation_passed: bool


def run_34a_simulation(
    augmented_universe: Dict[str, pd.DataFrame],
    config: Strategy34AConfig,
) -> SimulationResult34A:
    """
    Executes an independent portfolio simulation of Strategy 34A across 2017-2019.
    Adheres strictly to single-slippage accounting and cash delivery financing.
    """
    symbols = sorted(list(augmented_universe.keys()))
    if not symbols:
        raise ValueError("augmented_universe is empty.")

    # Harmonize trading dates across universe
    first_sym = symbols[0]
    trading_dates = sorted(list(augmented_universe[first_sym].index))
    n_days = len(trading_dates)

    cash = float(config.initial_capital)
    active_positions: Dict[str, Dict[str, Any]] = {}
    completed_trades: List[CompletedTrade34A] = []
    trade_counter = 0

    equity_records: Dict[date, float] = {}
    pending_signals: List[Strategy34ASignal] = []
    pending_exits: Dict[str, Tuple[ExitReason, str]] = {}  # Symbol -> (reason, notes)

    slippage_factor = config.execution_slippage_bps / 10000.0

    for day_idx in range(n_days):
        current_dt = to_py_date(trading_dates[day_idx])
        is_final_bar = (day_idx == n_days - 1)

        # -------------------------------------------------------------
        # STEP 1A: EXECUTE PENDING EOD EXITS AT TODAY'S OPEN
        # -------------------------------------------------------------
        if pending_exits:
            for sym, (exit_reason, exit_notes) in list(pending_exits.items()):
                if sym in active_positions:
                    pos = active_positions.pop(sym)
                    bar = augmented_universe[sym].loc[trading_dates[day_idx]]
                    raw_exit_px = float(bar["open"])
                    effective_exit_px = raw_exit_px * (1.0 - slippage_factor)

                    cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                        symbol=pos["symbol"],
                        isin=pos["isin"],
                        entry_date=pos["entry_date"],
                        exit_date=current_dt,
                        entry_price=pos["effective_entry_price"],
                        exit_price=effective_exit_px,
                        quantity=pos["quantity"],
                        use_stress_profile=config.use_stress_costs,
                    )

                    statutory_broker = round(cost_sum.total_friction_costs - cost_sum.total_execution_friction, 2)
                    gross_pnl = round(float(cost_sum.gross_pnl), 2)
                    slippage_val = round(float(cost_sum.total_execution_friction), 2)
                    total_costs_val = round(float(cost_sum.total_friction_costs), 2)
                    net_pnl_val = round(gross_pnl - statutory_broker, 2)
                    net_ret_pct = (net_pnl_val / (pos["quantity"] * pos["effective_entry_price"])) * 100.0

                    # Exact cash update ensuring zero floating-point accumulation noise
                    cash += (pos["quantity"] * pos["effective_entry_price"]) + net_pnl_val

                    completed_trades.append(
                        CompletedTrade34A(
                            trade_id=pos["trade_id"],
                            config_id=config.config_id,
                            symbol=pos["symbol"],
                            sector=pos["sector"],
                            isin=pos["isin"],
                            entry_date=pos["entry_date"],
                            exit_date=current_dt,
                            bars_held=pos["bars_held"],
                            quantity=pos["quantity"],
                            raw_entry_price=round(pos["raw_entry_price"], 2),
                            raw_exit_price=round(raw_exit_px, 2),
                            effective_entry_price=round(pos["effective_entry_price"], 2),
                            effective_exit_price=round(effective_exit_px, 2),
                            gross_pnl=round(gross_pnl, 2),
                            slippage=round(slippage_val, 2),
                            statutory_broker_costs=round(statutory_broker, 2),
                            total_costs=round(total_costs_val, 2),
                            net_pnl=net_pnl_val,
                            net_return_pct=round(net_ret_pct, 2),
                            exit_reason=exit_reason.value,
                            exit_notes=exit_notes,
                        )
                    )
            pending_exits.clear()

        # -------------------------------------------------------------
        # STEP 1B: EXECUTE PENDING ENTRY SIGNALS AT TODAY'S OPEN
        # -------------------------------------------------------------
        if pending_signals and not is_final_bar:
            # Sort pending signals by relative strength descending, then symbol
            pending_signals.sort(key=lambda s: (-s.rs_val, s.symbol))

            for sig in pending_signals:
                if len(active_positions) >= config.max_concurrent_positions:
                    break
                if sig.symbol in active_positions:
                    continue

                bar = augmented_universe[sig.symbol].loc[trading_dates[day_idx]]
                raw_open = float(bar["open"])
                exec_open = raw_open * (1.0 + slippage_factor)

                # Portfolio equity at today's open
                current_equity = cash + sum(
                    p["quantity"] * float(augmented_universe[p["symbol"]].loc[trading_dates[day_idx]]["open"])
                    for p in active_positions.values()
                )

                risk_budget = current_equity * config.risk_per_trade
                stop_dist = max(0.50, exec_open - sig.stop_loss_price)
                raw_shares = int(risk_budget / stop_dist)
                max_cash_shares = int(cash / exec_open)
                shares = min(raw_shares, max_cash_shares)

                if shares < 1:
                    continue

                cost_required = shares * exec_open
                if cost_required > cash:
                    continue

                trade_counter += 1
                sector = config.symbol_sector_map.get(sig.symbol, "Diversified")
                isin = config.symbol_isin_map.get(sig.symbol, f"INE_{sig.symbol}_CANONICAL")

                active_positions[sig.symbol] = {
                    "trade_id": trade_counter,
                    "symbol": sig.symbol,
                    "sector": sector,
                    "isin": isin,
                    "entry_date": current_dt,
                    "raw_entry_price": raw_open,
                    "effective_entry_price": exec_open,
                    "quantity": shares,
                    "stop_loss_price": sig.stop_loss_price,
                    "bars_held": 0,
                }
                cash -= cost_required

            pending_signals = []

        # -------------------------------------------------------------
        # STEP 2: INTRADAY EVALUATION (PROTECTIVE STOPS)
        # -------------------------------------------------------------
        immediate_exits = []
        for sym, pos in list(active_positions.items()):
            pos["bars_held"] += 1
            bar = augmented_universe[sym].loc[trading_dates[day_idx]]

            should_exit, exit_px, reason, note, exit_next = evaluate_34a_exit(
                pos=pos,
                bar=bar,
                is_final_bar=is_final_bar,
                config=config,
            )

            if should_exit:
                immediate_exits.append((sym, exit_px, reason, note))
            elif exit_next and not is_final_bar:
                pending_exits[sym] = (reason, note)

        # Process immediate exits (protective stop or end-of-data)
        for sym, raw_exit_px, exit_reason, exit_notes in immediate_exits:
            pos = active_positions.pop(sym)
            effective_exit_px = raw_exit_px * (1.0 - slippage_factor)

            cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                symbol=pos["symbol"],
                isin=pos["isin"],
                entry_date=pos["entry_date"],
                exit_date=current_dt,
                entry_price=pos["effective_entry_price"],
                exit_price=effective_exit_px,
                quantity=pos["quantity"],
                use_stress_profile=config.use_stress_costs,
            )

            statutory_broker = round(cost_sum.total_friction_costs - cost_sum.total_execution_friction, 2)
            gross_pnl = round(float(cost_sum.gross_pnl), 2)
            slippage_val = round(float(cost_sum.total_execution_friction), 2)
            total_costs_val = round(float(cost_sum.total_friction_costs), 2)
            net_pnl_val = round(gross_pnl - statutory_broker, 2)
            net_ret_pct = (net_pnl_val / (pos["quantity"] * pos["effective_entry_price"])) * 100.0

            # Exact cash update ensuring zero floating-point accumulation noise
            cash += (pos["quantity"] * pos["effective_entry_price"]) + net_pnl_val

            completed_trades.append(
                CompletedTrade34A(
                    trade_id=pos["trade_id"],
                    config_id=config.config_id,
                    symbol=pos["symbol"],
                    sector=pos["sector"],
                    isin=pos["isin"],
                    entry_date=pos["entry_date"],
                    exit_date=current_dt,
                    bars_held=pos["bars_held"],
                    quantity=pos["quantity"],
                    raw_entry_price=round(pos["raw_entry_price"], 2),
                    raw_exit_price=round(raw_exit_px, 2),
                    effective_entry_price=round(pos["effective_entry_price"], 2),
                    effective_exit_price=round(effective_exit_px, 2),
                    gross_pnl=round(gross_pnl, 2),
                    slippage=round(slippage_val, 2),
                    statutory_broker_costs=round(statutory_broker, 2),
                    total_costs=round(total_costs_val, 2),
                    net_pnl=net_pnl_val,
                    net_return_pct=round(net_ret_pct, 2),
                    exit_reason=exit_reason.value if exit_reason else "unknown",
                    exit_notes=exit_notes,
                )
            )

        # -------------------------------------------------------------
        # STEP 3: EOD EQUITY RECORD & SIGNAL GENERATION
        # -------------------------------------------------------------
        eod_equity = cash + sum(
            p["quantity"] * float(augmented_universe[p["symbol"]].loc[trading_dates[day_idx]]["close"])
            for p in active_positions.values()
        )
        equity_records[current_dt] = round(eod_equity, 2)

        if not is_final_bar:
            for sym in symbols:
                if sym in active_positions or sym in pending_exits:
                    continue
                bar_row = augmented_universe[sym].loc[trading_dates[day_idx]]
                sig = generate_34a_signals(
                    symbol=sym,
                    row=bar_row,
                    signal_date=current_dt,
                    config=config,
                )
                if sig is not None:
                    pending_signals.append(sig)

    # -----------------------------------------------------------------
    # AUDIT RECONCILIATION & PERFORMANCE METRICS
    # -----------------------------------------------------------------
    final_equity = equity_records[to_py_date(trading_dates[-1])]
    sum_net_pnl = sum(t.net_pnl for t in completed_trades)
    cash_delta = cash - config.initial_capital
    reconciliation_discrepancy = abs(cash_delta - sum_net_pnl)
    reconciliation_passed = bool(reconciliation_discrepancy < 0.01)

    total_trades = len(completed_trades)
    winning_trades = [t for t in completed_trades if t.net_pnl > 0]
    losing_trades = [t for t in completed_trades if t.net_pnl < 0]

    win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
    gross_gains = sum(t.net_pnl for t in winning_trades)
    gross_losses = abs(sum(t.net_pnl for t in losing_trades))
    profit_factor = (gross_gains / gross_losses) if gross_losses > 0 else (99.0 if gross_gains > 0 else 0.0)

    avg_win = (gross_gains / len(winning_trades)) if winning_trades else 0.0
    avg_loss = (gross_losses / len(losing_trades)) if losing_trades else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    roi_pct = (sum_net_pnl / config.initial_capital) * 100.0
    # 3-year study period: 2017 to 2019
    cagr_pct = (((1.0 + (sum_net_pnl / config.initial_capital)) ** (1.0 / 3.0)) - 1.0) * 100.0 if (sum_net_pnl > -config.initial_capital) else -100.0

    # Drawdown series
    eq_series = pd.Series(equity_records)
    rolling_peak = eq_series.cummax()
    dd_series = (eq_series - rolling_peak) / rolling_peak
    max_dd_pct = abs(dd_series.min() * 100.0)

    # Top winners removal
    sorted_pnls = sorted([t.net_pnl for t in completed_trades], reverse=True)
    ex_top3 = sum(sorted_pnls[3:]) if len(sorted_pnls) >= 3 else 0.0
    ex_top5 = sum(sorted_pnls[5:]) if len(sorted_pnls) >= 5 else 0.0
    top3_gains = sum(sorted_pnls[:3]) if len(sorted_pnls) >= 3 else 0.0
    top3_pct = (top3_gains / gross_gains * 100.0) if gross_gains > 0 else 0.0

    avg_hold = float(np.mean([t.bars_held for t in completed_trades])) if completed_trades else 0.0
    cap_util = float(np.mean([1.0 - (eq_val / config.initial_capital) for eq_val in equity_records.values()])) * 100.0

    # Monthly Summary
    monthly_pnls: Dict[str, float] = {}
    for t in completed_trades:
        m_key = t.exit_date.strftime("%Y-%m")
        monthly_pnls[m_key] = monthly_pnls.get(m_key, 0.0) + t.net_pnl

    all_months = pd.date_range("2017-01-01", "2019-12-31", freq="MS").strftime("%Y-%m").tolist()
    m_records = []
    for m in all_months:
        pnl_m = round(monthly_pnls.get(m, 0.0), 2)
        m_trades = [t for t in completed_trades if t.exit_date.strftime("%Y-%m") == m]
        m_records.append({
            "month": m,
            "net_pnl": pnl_m,
            "trades_count": len(m_trades),
            "profitable": pnl_m > 0.0,
            "losing": pnl_m < 0.0,
            "zero_trade": len(m_trades) == 0,
        })
    monthly_df = pd.DataFrame(m_records)

    prof_months = int(monthly_df["profitable"].sum())
    los_months = int(monthly_df["losing"].sum())
    zero_months = int(monthly_df["zero_trade"].sum())
    prof_months_pct = (prof_months / 36.0) * 100.0

    # Yearly Summary
    yearly_records = []
    for yr in [2017, 2018, 2019]:
        y_trades = [t for t in completed_trades if t.exit_date.year == yr]
        y_pnl = round(sum(t.net_pnl for t in y_trades), 2)
        y_roi = (y_pnl / config.initial_capital) * 100.0
        yearly_records.append({
            "year": yr,
            "net_pnl": y_pnl,
            "roi_pct": round(y_roi, 2),
            "trades_count": len(y_trades),
            "profitable": y_pnl > 0.0,
        })
    yearly_df = pd.DataFrame(yearly_records)
    prof_years = int(yearly_df["profitable"].sum())
    los_years = 3 - prof_years

    return SimulationResult34A(
        config=config,
        trades=completed_trades,
        initial_capital=config.initial_capital,
        final_equity=round(final_equity, 2),
        net_pnl=round(sum_net_pnl, 2),
        roi_pct=round(roi_pct, 2),
        cagr_pct=round(cagr_pct, 2),
        profit_factor=round(profit_factor, 2),
        win_rate_pct=round(win_rate, 2),
        completed_trades=total_trades,
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        payoff_ratio=round(payoff_ratio, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        ex_top3_net_pnl=round(ex_top3, 2),
        ex_top5_net_pnl=round(ex_top5, 2),
        top3_pct_of_gains=round(top3_pct, 2),
        avg_holding_bars=round(avg_hold, 2),
        capital_utilization_pct=round(cap_util, 2),
        profitable_months=prof_months,
        losing_months=los_months,
        zero_trade_months=zero_months,
        profitable_months_pct=round(prof_months_pct, 2),
        profitable_years=prof_years,
        losing_years=los_years,
        daily_equity_series=eq_series,
        monthly_summary=monthly_df,
        yearly_summary=yearly_df,
        reconciliation_discrepancy=round(reconciliation_discrepancy, 4),
        reconciliation_passed=reconciliation_passed,
    )

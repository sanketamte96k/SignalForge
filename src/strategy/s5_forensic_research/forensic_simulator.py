"""
SignalForge — Phase 33B: S5 Forensic Simulation Engine
======================================================
File: src/strategy/s5_forensic_research/forensic_simulator.py

Simulates S5 baseline and pre-registered forensic variations with full
single-slipped and double-slipped reconciliation tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.s5_forensic_research.config import (
    FORENSIC_HYPOTHESIS_CONFIGS,
    S5ForensicConfig,
    S5HypothesisID,
)
from src.strategy.strategy_research_lab.config import ExitReason, RiskTier, StrategyLabConfig
from src.strategy.strategy_research_lab.indicators import attach_all_indicators
from src.strategy.strategy_research_lab.portfolio_simulator import CompletedTrade, to_py_date


@dataclass
class S5ForensicTrade:
    """Detailed trade record with both single and double slippage P&L."""
    trade_id: int
    hypothesis_id: str
    symbol: str
    sector: str
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
    net_pnl_single_slipped: float  # Gross - statutory_broker
    net_pnl_double_slipped: float  # Gross - total_costs (with slippage subtracted twice)
    exit_reason: str
    exit_notes: str


@dataclass
class S5ForensicResult:
    """Forensic backtest output for S5 variations."""
    hypothesis_id: str
    cost_schedule: str
    initial_capital: float
    trades: List[S5ForensicTrade]
    # Single-slipped metrics (Cash equity)
    final_equity_single: float
    net_pnl_single: float
    roi_single: float
    cagr_single: float
    pf_single: float
    payoff_single: float
    max_dd_single: float
    ex_top3_net_pnl_single: float
    top3_contribution_pct_single: float
    # Double-slipped metrics (Phase 33A Ledger equivalent)
    net_pnl_double: float
    roi_double: float
    cagr_double: float
    pf_double: float
    payoff_double: float
    ex_top3_net_pnl_double: float
    top3_contribution_pct_double: float
    # Operational metrics
    completed_trades: int
    win_rate_single: float
    win_rate_double: float
    daily_equity_series: pd.Series
    monthly_summary: pd.DataFrame
    yearly_summary: pd.DataFrame
    profitable_months_single: int
    losing_months_single: int
    zero_trade_months: int
    profitable_months_pct_single: float
    profitable_years_single: int
    losing_years_single: int


def run_s5_forensic_simulation(
    hypothesis_id: S5HypothesisID,
    augmented_universe: Dict[str, pd.DataFrame],
    risk_tier: RiskTier = RiskTier.E2,
    use_stress_costs: bool = True,
    config: Optional[StrategyLabConfig] = None,
    cfg: Optional[S5ForensicConfig] = None,
) -> S5ForensicResult:
    """
    Executes an auditable forensic simulation of an S5 hypothesis across 2017-2019.
    """
    if config is None:
        config = StrategyLabConfig()
    if cfg is None:
        cfg = FORENSIC_HYPOTHESIS_CONFIGS[hypothesis_id]

    symbols = sorted(list(augmented_universe.keys()))
    trading_dates = sorted(list(augmented_universe[symbols[0]].index))
    n_days = len(trading_dates)

    cash = config.initial_capital
    active_positions: Dict[str, Dict[str, Any]] = {}
    completed_trades: List[S5ForensicTrade] = []
    trade_counter = 0

    equity_records: Dict[date, float] = {}
    pending_signals: List[Dict[str, Any]] = []

    for day_idx in range(n_days):
        current_dt = to_py_date(trading_dates[day_idx])
        is_final_bar = (day_idx == n_days - 1)

        # -------------------------------------------------------------
        # STEP 1: EXECUTE PENDING SIGNALS AT TODAY'S OPEN
        # -------------------------------------------------------------
        if pending_signals and not is_final_bar:
            for sig in pending_signals:
                if len(active_positions) >= config.max_concurrent_positions:
                    break
                if sig["symbol"] in active_positions:
                    continue

                bar = augmented_universe[sig["symbol"]].loc[trading_dates[day_idx]]
                raw_open = float(bar["open"])
                slippage_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exec_open = raw_open * (1.0 + slippage_factor)

                current_equity = cash + sum(
                    p["quantity"] * float(augmented_universe[p["symbol"]].loc[trading_dates[day_idx]]["open"])
                    for p in active_positions.values()
                )

                risk_budget = current_equity * risk_tier.risk_fraction
                stop_dist = max(0.50, exec_open - sig["stop_loss_price"])
                raw_shares = int(risk_budget / stop_dist)
                max_cash_shares = int(cash / exec_open)
                shares = min(raw_shares, max_cash_shares)

                if shares < 1:
                    continue

                cost_required = shares * exec_open
                if cost_required > cash:
                    continue

                trade_counter += 1
                sector = config.symbol_sector_map.get(sig["symbol"], "Diversified")
                isin = config.symbol_isin_map.get(sig["symbol"], f"INE_{sig['symbol']}_CANONICAL")

                profit_target = None
                if cfg.profit_target_atr_mult is not None:
                    profit_target = exec_open + (cfg.profit_target_atr_mult * sig["atr14"])

                active_positions[sig["symbol"]] = {
                    "trade_id": trade_counter,
                    "symbol": sig["symbol"],
                    "sector": sector,
                    "isin": isin,
                    "entry_date": current_dt,
                    "entry_price": exec_open,
                    "raw_entry_open": raw_open,
                    "quantity": shares,
                    "stop_loss_price": sig["stop_loss_price"],
                    "profit_target_price": profit_target,
                    "trailing_exit_level": sig["trailing_exit_level"],
                    "max_hold_bars": cfg.max_hold_bars,
                    "bars_held": 0,
                }
                cash -= cost_required

            pending_signals = []

        # -------------------------------------------------------------
        # STEP 2: EVALUATE EXITS ON CURRENT BAR
        # -------------------------------------------------------------
        symbols_to_exit = []
        for sym, pos in list(active_positions.items()):
            pos["bars_held"] += 1
            bar = augmented_universe[sym].loc[trading_dates[day_idx]]
            open_px = float(bar["open"])
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])

            # 1. Final bar
            if is_final_bar:
                symbols_to_exit.append((sym, close, ExitReason.END_OF_DATA_LIQUIDATION, "Final bar close"))
                continue

            # 2. Stop loss
            if low <= pos["stop_loss_price"]:
                exec_px = min(open_px, pos["stop_loss_price"])
                symbols_to_exit.append((sym, exec_px, ExitReason.PROTECTIVE_STOP, f"Stop at {exec_px:.2f}"))
                continue

            # 3. Profit target (if H2 enabled)
            if pos["profit_target_price"] is not None and high >= pos["profit_target_price"]:
                exec_px = max(open_px, pos["profit_target_price"])
                symbols_to_exit.append((sym, exec_px, ExitReason.PROFIT_TARGET, f"Target at {exec_px:.2f}"))
                continue

            # 4. Trailing stop
            current_trail = float(bar.get("donchian_low_10", np.nan))
            active_trail = current_trail if not pd.isna(current_trail) else pos["trailing_exit_level"]
            if active_trail is not None and low < active_trail:
                exec_px = min(open_px, active_trail)
                symbols_to_exit.append((sym, exec_px, ExitReason.TRAILING_STOP, f"Trailing low at {exec_px:.2f}"))
                continue

            # 5. Time stop
            if pos["bars_held"] >= pos["max_hold_bars"]:
                symbols_to_exit.append((sym, close, ExitReason.TIME_STOP, f"Max holding ({pos['bars_held']} bars)"))
                continue

        # Execute Exits
        for sym, raw_exit_px, exit_reason, exit_notes in symbols_to_exit:
            pos = active_positions.pop(sym)
            friction_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
            effective_exit_px = raw_exit_px * (1.0 - friction_factor)

            e_date = pos["entry_date"]
            x_date = current_dt

            cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                symbol=pos["symbol"],
                isin=pos["isin"],
                entry_date=e_date,
                exit_date=x_date,
                entry_price=pos["entry_price"],
                exit_price=effective_exit_px,
                quantity=pos["quantity"],
                use_stress_profile=use_stress_costs,
            )

            statutory_broker = cost_sum.total_friction_costs - cost_sum.total_execution_friction
            # Single-slipped cash update
            cash += (pos["quantity"] * effective_exit_px) - statutory_broker

            gross_pnl = float(cost_sum.gross_pnl)
            slip = float(cost_sum.total_execution_friction)
            tot_costs = float(cost_sum.total_friction_costs)
            net_single = round(gross_pnl - statutory_broker, 2)
            net_double = round(gross_pnl - tot_costs, 2)

            completed_trades.append(
                S5ForensicTrade(
                    trade_id=pos["trade_id"],
                    hypothesis_id=hypothesis_id.value,
                    symbol=pos["symbol"],
                    sector=pos["sector"],
                    entry_date=e_date,
                    exit_date=x_date,
                    bars_held=pos["bars_held"],
                    quantity=pos["quantity"],
                    raw_entry_price=round(pos["raw_entry_open"], 2),
                    raw_exit_price=round(raw_exit_px, 2),
                    effective_entry_price=round(pos["entry_price"], 2),
                    effective_exit_price=round(effective_exit_px, 2),
                    gross_pnl=round(gross_pnl, 2),
                    slippage=round(slip, 2),
                    statutory_broker_costs=round(statutory_broker, 2),
                    total_costs=round(tot_costs, 2),
                    net_pnl_single_slipped=net_single,
                    net_pnl_double_slipped=net_double,
                    exit_reason=exit_reason.value,
                    exit_notes=exit_notes,
                )
            )

        # -------------------------------------------------------------
        # STEP 3: EOD EQUITY SNAPSHOT & SIGNAL GENERATION
        # -------------------------------------------------------------
        eod_equity = cash + sum(
            p["quantity"] * float(augmented_universe[p["symbol"]].loc[trading_dates[day_idx]]["close"])
            for p in active_positions.values()
        )
        equity_records[current_dt] = eod_equity

        if day_idx < n_days - 1:
            next_dt = to_py_date(trading_dates[day_idx + 1])
            new_sigs = []
            for sym in symbols:
                df = augmented_universe[sym]
                if day_idx >= len(df):
                    continue
                row = df.iloc[day_idx]
                if pd.isna(row["close"]) or pd.isna(row["atr_14"]) or float(row["atr_14"]) <= 0:
                    continue

                close = float(row["close"])
                volume = float(row["volume"])
                atr14 = float(row["atr_14"])
                bb_width_pct = float(row.get("bb_width_pct_120", np.nan))
                dh_20 = float(row["donchian_high_20"])
                dl_10 = float(row["donchian_low_10"])
                vol_sma20 = float(row["volume_sma_20"])

                if pd.isna(bb_width_pct) or pd.isna(dh_20) or pd.isna(vol_sma20):
                    continue

                cond_squeeze = bb_width_pct <= cfg.bb_width_pct_thresh
                cond_breakout = close > dh_20
                cond_volume = volume > (cfg.volume_mult * vol_sma20)

                if cond_squeeze and cond_breakout and cond_volume:
                    stop_loss = close - (cfg.stop_atr_mult * atr14)
                    priority = 1.0 - bb_width_pct
                    new_sigs.append({
                        "symbol": sym,
                        "signal_date": current_dt,
                        "execution_date": next_dt,
                        "signal_close": close,
                        "atr14": atr14,
                        "stop_loss_price": stop_loss,
                        "trailing_exit_level": dl_10,
                        "priority": priority,
                    })

            new_sigs.sort(key=lambda s: s["priority"], reverse=True)
            pending_signals = new_sigs

    daily_eq_series = pd.Series(equity_records)
    final_eq_single = float(daily_eq_series.iloc[-1])
    net_pnl_single = round(final_eq_single - config.initial_capital, 2)
    roi_single = round((net_pnl_single / config.initial_capital) * 100.0, 2)
    cagr_single = round(((final_eq_single / config.initial_capital) ** (1.0 / 3.0) - 1.0) * 100.0, 2)

    peak_eq = daily_eq_series.cummax()
    dd_series = (daily_eq_series - peak_eq) / peak_eq * 100.0
    max_dd_single = round(abs(float(dd_series.min())), 2)

    n_trades = len(completed_trades)
    # Single-slipped calculations
    wins_s = [t for t in completed_trades if t.net_pnl_single_slipped > 0]
    losses_s = [t for t in completed_trades if t.net_pnl_single_slipped <= 0]
    win_rate_s = round(len(wins_s) / n_trades * 100.0, 2) if n_trades > 0 else 0.0

    pos_s = sum(t.net_pnl_single_slipped for t in wins_s)
    neg_s = abs(sum(t.net_pnl_single_slipped for t in losses_s))
    pf_single = round(pos_s / neg_s, 2) if neg_s > 0 else (99.0 if pos_s > 0 else 0.0)

    avg_win_s = (pos_s / len(wins_s)) if wins_s else 0.0
    avg_loss_s = (neg_s / len(losses_s)) if losses_s else 0.0
    payoff_single = round(avg_win_s / avg_loss_s, 2) if avg_loss_s > 0 else 0.0

    # Double-slipped calculations
    net_pnl_double = round(sum(t.net_pnl_double_slipped for t in completed_trades), 2)
    roi_double = round((net_pnl_double / config.initial_capital) * 100.0, 2)
    cagr_double = round((((config.initial_capital + net_pnl_double) / config.initial_capital) ** (1.0 / 3.0) - 1.0) * 100.0, 2)

    wins_d = [t for t in completed_trades if t.net_pnl_double_slipped > 0]
    losses_d = [t for t in completed_trades if t.net_pnl_double_slipped <= 0]
    win_rate_d = round(len(wins_d) / n_trades * 100.0, 2) if n_trades > 0 else 0.0

    pos_d = sum(t.net_pnl_double_slipped for t in wins_d)
    neg_d = abs(sum(t.net_pnl_double_slipped for t in losses_d))
    pf_double = round(pos_d / neg_d, 2) if neg_d > 0 else (99.0 if pos_d > 0 else 0.0)

    avg_win_d = (pos_d / len(wins_d)) if wins_d else 0.0
    avg_loss_d = (neg_d / len(losses_d)) if losses_d else 0.0
    payoff_double = round(avg_win_d / avg_loss_d, 2) if avg_loss_d > 0 else 0.0

    # Top-3 trade dependency
    sorted_s = sorted([t.net_pnl_single_slipped for t in completed_trades], reverse=True)
    top3_s_sum = sum(sorted_s[:3]) if len(sorted_s) >= 3 else sum(sorted_s)
    ex_top3_s = net_pnl_single - top3_s_sum
    top3_contrib_s = (top3_s_sum / net_pnl_single * 100.0) if net_pnl_single > 0 else 0.0

    sorted_d = sorted([t.net_pnl_double_slipped for t in completed_trades], reverse=True)
    top3_d_sum = sum(sorted_d[:3]) if len(sorted_d) >= 3 else sum(sorted_d)
    ex_top3_d = net_pnl_double - top3_d_sum
    top3_contrib_d = (top3_d_sum / net_pnl_double * 100.0) if net_pnl_double > 0 else 0.0

    # Monthly and yearly tables
    if completed_trades:
        df_t = pd.DataFrame([t.__dict__ for t in completed_trades])
        df_t["exit_date"] = pd.to_datetime(df_t["exit_date"])
        df_t["year"] = df_t["exit_date"].dt.year
        df_t["month"] = df_t["exit_date"].dt.to_period("M").astype(str)

        # Yearly aggregation
        yearly_recs = []
        for y in sorted(df_t["year"].unique()):
            sub_y = df_t[df_t["year"] == y]
            n_y = len(sub_y)
            n_w_s = int((sub_y["net_pnl_single_slipped"] > 0).sum())
            gp = float(sub_y["gross_pnl"].sum())
            costs = float(sub_y["total_costs"].sum())
            net_s = float(sub_y["net_pnl_single_slipped"].sum())
            net_d = float(sub_y["net_pnl_double_slipped"].sum())
            yearly_recs.append({
                "year": y,
                "trades": n_y,
                "win_rate_single": round(n_w_s / n_y * 100.0, 2),
                "gross_pnl": round(gp, 2),
                "total_costs": round(costs, 2),
                "net_pnl_single": round(net_s, 2),
                "net_pnl_double": round(net_d, 2),
            })
        df_yearly = pd.DataFrame(yearly_recs)

        # Monthly aggregation
        all_cal_months = [f"{y}-{m:02d}" for y in [2017, 2018, 2019] for m in range(1, 13)]
        monthly_recs = []
        prof_m = 0
        loss_m = 0
        zero_m = 0
        for ym in all_cal_months:
            sub_m = df_t[df_t["month"] == ym]
            if len(sub_m) == 0:
                zero_m += 1
                monthly_recs.append({
                    "month": ym,
                    "trades": 0,
                    "net_pnl_single": 0.0,
                    "net_pnl_double": 0.0,
                    "status": "ZERO_TRADES",
                })
            else:
                net_s = float(sub_m["net_pnl_single_slipped"].sum())
                net_d = float(sub_m["net_pnl_double_slipped"].sum())
                if net_s > 0:
                    prof_m += 1
                    status = "PROFITABLE"
                else:
                    loss_m += 1
                    status = "LOSING"
                monthly_recs.append({
                    "month": ym,
                    "trades": len(sub_m),
                    "net_pnl_single": round(net_s, 2),
                    "net_pnl_double": round(net_d, 2),
                    "status": status,
                })
        df_monthly = pd.DataFrame(monthly_recs)

        prof_m_pct = round(prof_m / (prof_m + loss_m) * 100.0, 2) if (prof_m + loss_m) > 0 else 0.0
        prof_y = int((df_yearly["net_pnl_single"] > 0).sum())
        loss_y = int((df_yearly["net_pnl_single"] <= 0).sum())
    else:
        df_yearly = pd.DataFrame()
        df_monthly = pd.DataFrame()
        prof_m = 0
        loss_m = 0
        zero_m = 36
        prof_m_pct = 0.0
        prof_y = 0
        loss_y = 3

    cost_str = "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)"

    return S5ForensicResult(
        hypothesis_id=hypothesis_id.value,
        cost_schedule=cost_str,
        initial_capital=config.initial_capital,
        trades=completed_trades,
        final_equity_single=final_eq_single,
        net_pnl_single=net_pnl_single,
        roi_single=roi_single,
        cagr_single=cagr_single,
        pf_single=pf_single,
        payoff_single=payoff_single,
        max_dd_single=max_dd_single,
        ex_top3_net_pnl_single=round(ex_top3_s, 2),
        top3_contribution_pct_single=round(top3_contrib_s, 2),
        net_pnl_double=net_pnl_double,
        roi_double=roi_double,
        cagr_double=cagr_double,
        pf_double=pf_double,
        payoff_double=payoff_double,
        ex_top3_net_pnl_double=round(ex_top3_d, 2),
        top3_contribution_pct_double=round(top3_contrib_d, 2),
        completed_trades=n_trades,
        win_rate_single=win_rate_s,
        win_rate_double=win_rate_d,
        daily_equity_series=daily_eq_series,
        monthly_summary=df_monthly,
        yearly_summary=df_yearly,
        profitable_months_single=prof_m,
        losing_months_single=loss_m,
        zero_trade_months=zero_m,
        profitable_months_pct_single=prof_m_pct,
        profitable_years_single=prof_y,
        losing_years_single=loss_y,
    )

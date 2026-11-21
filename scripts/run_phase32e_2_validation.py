"""
SignalForge — Phase 32E.2: DTP-V2 Controlled Performance Validation Runner
===========================================================================
File: scripts/run_phase32e_2_validation.py

Executes controlled, reproducible validation of DTP-V2 against DTP-V1
across the approved 21-stock Primary NSE Cash-Equity Universe (2017-2019, 739 sessions)
under both Official (₹307/cr) and Stress (₹317/cr) delivery cost schedules.
Strictly read-only with respect to frozen strategy code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    load_and_resample_21_universe,
    calculate_signal_priority,
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
)

# Strategy V1 imports
from src.strategy.dtp_v1.config import (
    DTPExitReason as DTPExitReasonV1,
    DTPRegimeState as DTPRegimeStateV1,
    DTPV1Config,
    OrderAction as OrderActionV1,
)
from src.strategy.dtp_v1.cost_integration import (
    calculate_dtp_roundtrip_costs as calculate_dtp_roundtrip_costs_v1,
)
from src.strategy.dtp_v1.indicators import calculate_dtp_indicators as calculate_dtp_indicators_v1
from src.strategy.dtp_v1.market_filter import evaluate_breadth_regime as evaluate_breadth_regime_v1
from src.strategy.dtp_v1.portfolio_rules import DTPPortfolioTracker as DTPPortfolioTrackerV1
from src.strategy.dtp_v1.risk_manager import calculate_dtp_position_size as calculate_dtp_position_size_v1
from src.strategy.dtp_v1.signal_engine import (
    DTPEODSignal as DTPEODSignalV1,
    DTPPositionState as DTPPositionStateV1,
    evaluate_exit_conditions as evaluate_exit_conditions_v1,
    evaluate_next_open_execution as evaluate_next_open_execution_v1,
    generate_eod_signal as generate_eod_signal_v1,
)

# Strategy V2 imports
from src.strategy.dtp_v2.config import (
    DTPExitReason as DTPExitReasonV2,
    DTPRegimeState as DTPRegimeStateV2,
    DTPV2Config,
    OrderAction as OrderActionV2,
)
from src.strategy.dtp_v2.cost_integration import (
    calculate_dtp_roundtrip_costs as calculate_dtp_roundtrip_costs_v2,
)
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators as calculate_dtp_indicators_v2
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime as evaluate_breadth_regime_v2
from src.strategy.dtp_v2.portfolio_rules import DTPPortfolioTracker as DTPPortfolioTrackerV2
from src.strategy.dtp_v2.risk_manager import calculate_dtp_position_size as calculate_dtp_position_size_v2
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal as DTPEODSignalV2,
    DTPPositionState as DTPPositionStateV2,
    evaluate_exit_conditions as evaluate_exit_conditions_v2,
    evaluate_next_open_execution as evaluate_next_open_execution_v2,
    generate_eod_signal as generate_eod_signal_v2,
)

OUT_DIR = PROJECT_ROOT / "reports" / "phase32e_2"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_strategy_simulation(
    version: str,  # "DTP-V1" or "DTP-V2"
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """
    Executes a single causal backtest run across 739 sessions.
    Supports either DTP-V1 or DTP-V2 with exact module bindings.
    """
    scenario_id = f"{version}_{'STRESS_317' if use_stress_costs else 'OFFICIAL_307'}"
    cost_schedule = "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)"

    if version == "DTP-V1":
        config = DTPV1Config(
            risk_fraction_per_trade=0.01,
            max_concurrent_positions=3,
            symbol_sector_map=EXPANDED_SECTOR_MAP,
            symbol_isin_map=EXPANDED_ISIN_MAP,
        )
        portfolio = DTPPortfolioTrackerV1(initial_capital=initial_capital, config=config)
        eval_next_open = evaluate_next_open_execution_v1
        calc_pos_size = calculate_dtp_position_size_v1
        eval_exits = evaluate_exit_conditions_v1
        eval_regime = evaluate_breadth_regime_v1
        gen_signal = generate_eod_signal_v1
        calc_costs = calculate_dtp_roundtrip_costs_v1
        PosStateClass = DTPPositionStateV1
        order_action_enter = OrderActionV1.ENTER_LONG
    else:
        config = DTPV2Config(
            risk_fraction_per_trade=0.01,
            max_concurrent_positions=3,
            symbol_sector_map=EXPANDED_SECTOR_MAP,
            symbol_isin_map=EXPANDED_ISIN_MAP,
        )
        portfolio = DTPPortfolioTrackerV2(initial_capital=initial_capital, config=config)
        eval_next_open = evaluate_next_open_execution_v2
        calc_pos_size = calculate_dtp_position_size_v2
        eval_exits = evaluate_exit_conditions_v2
        eval_regime = evaluate_breadth_regime_v2
        gen_signal = generate_eod_signal_v2
        calc_costs = calculate_dtp_roundtrip_costs_v2
        PosStateClass = DTPPositionStateV2
        order_action_enter = OrderActionV2.ENTER_LONG

    positions_state: Dict[str, Any] = {}
    pending_signals: Dict[str, Tuple[Any, Tuple[float, float, str]]] = {}
    executed_trades: List[Dict[str, Any]] = []
    rejected_signals: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []

    trade_counter = 0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution for Pending Signals
        if pending_signals:
            # Deterministic priority sorting (lowest risk distance, highest RS, symbol tie-breaker)
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])

            for sym, (sig, prio_tuple) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])

                action, fill_price, action_msg = eval_next_open(
                    signal=sig,
                    next_open_price=today_open,
                    config=config,
                )

                if action != order_action_enter:
                    rejected_signals.append({
                        "scenario_id": scenario_id,
                        "date": current_dt,
                        "symbol": sym,
                        "reason": f"Execution rejected: {action_msg}",
                    })
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = config.symbol_sector_map.get(sym, "General")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)

                shares, size_msg = calc_pos_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    config=config,
                )

                if shares <= 0:
                    rejected_signals.append({
                        "scenario_id": scenario_id,
                        "date": current_dt,
                        "symbol": sym,
                        "reason": f"Sizing rejected: {size_msg}",
                    })
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    sector=sector,
                    current_prices=curr_prices,
                )

                if not can_open:
                    rejected_signals.append({
                        "scenario_id": scenario_id,
                        "date": current_dt,
                        "symbol": sym,
                        "reason": f"Portfolio gate rejected: {gate_msg}",
                    })
                    continue

                # Open Position
                trade_counter += 1
                order_id = f"{version}_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
                active_pos = portfolio.open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    shares=shares,
                    stop_price=sig.initial_stop_price,
                    r_distance=sig.r_distance,
                    entry_date=current_dt,
                    order_id=order_id,
                    sector=sector,
                )

                positions_state[sym] = PosStateClass(
                    symbol=sym,
                    entry_date=current_dt,
                    entry_price=fill_price,
                    quantity=shares,
                    initial_stop_price=sig.initial_stop_price,
                    current_stop_price=sig.initial_stop_price,
                    r_distance=sig.r_distance,
                    highest_high=fill_price,
                    highest_close=fill_price,
                )

            pending_signals.clear()

        # Step B: Intraday Session Exits Evaluation
        full_exits: List[Tuple[str, str, float, str]] = []

        for sym, pos in list(portfolio.positions.items()):
            pos_state = positions_state[sym]
            bar = augmented_universe[sym].loc[current_ts]

            # Last day forced liquidation
            if day_idx == len(trading_dates) - 1:
                friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exit_px = float(bar["close"]) * (1.0 - friction_rate)
                full_exits.append((sym, "MANUAL_CLOSE", exit_px, "End of validation period liquidation"))
                continue

            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            open_px = float(bar["open"])
            atr = float(bar.get("atr", 1.0))
            ema50 = float(bar.get("ema_slow", close))
            rsi = float(bar.get("rsi", 50.0))
            bb_upper = float(bar.get("bb_upper", close * 1.10))

            reason_obj, exit_px, exit_msg = eval_exits(
                pos=pos_state,
                current_high=high,
                current_low=low,
                current_close=close,
                current_open=open_px,
                current_atr=atr,
                current_ema50=ema50,
                current_rsi=rsi,
                current_bb_upper=bb_upper,
                config=config,
            )

            if reason_obj is not None:
                full_exits.append((sym, reason_obj.value if hasattr(reason_obj, "value") else str(reason_obj), exit_px, exit_msg))

        # Process Exits
        for sym, reason_str, exit_px, exit_msg in full_exits:
            active_pos = portfolio.positions[sym]
            isin = config.symbol_isin_map.get(sym, "DEFAULT_ISIN")

            breakdown, cost_summary = calc_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix=f"{version}",
            )

            net_proceeds = cost_summary.sell_turnover - cost_summary.total_friction_costs
            portfolio.close_position(sym, exit_px, net_proceeds)
            pos_state = positions_state.pop(sym, None)

            initial_risk_amount = active_pos.quantity * active_pos.r_distance
            realized_r = cost_summary.net_pnl / initial_risk_amount if initial_risk_amount > 0 else 0.0

            taxes_and_statutory = (
                cost_summary.total_stt +
                cost_summary.exchange_charge +
                cost_summary.ipft_charge +
                cost_summary.sebi_turnover_fee +
                cost_summary.total_stamp_duty +
                cost_summary.total_gst
            )

            executed_trades.append({
                "scenario_id": scenario_id,
                "strategy_version": version,
                "cost_schedule": cost_schedule,
                "trade_id": active_pos.order_id,
                "order_id": active_pos.order_id,
                "symbol": sym,
                "sector": active_pos.sector,
                "entry_date": active_pos.entry_date.isoformat(),
                "entry_price": round(active_pos.entry_price, 4),
                "exit_date": current_dt.isoformat(),
                "exit_price": round(exit_px, 4),
                "quantity": active_pos.quantity,
                "gross_pnl": round(cost_summary.gross_pnl, 2),
                "brokerage": round(cost_summary.total_brokerage, 2),
                "taxes_and_statutory": round(taxes_and_statutory, 2),
                "depository_charges": round(cost_summary.total_dp_charge, 2),
                "execution_friction": round(cost_summary.total_execution_friction, 2),
                "total_costs": round(cost_summary.total_friction_costs, 2),
                "net_pnl": round(cost_summary.net_pnl, 2),
                "holding_days": pos_state.holding_days if pos_state else (current_dt - active_pos.entry_date).days,
                "exit_reason": reason_str,
                "exit_message": exit_msg,
                "realized_r": round(realized_r, 4),
                "risk_amount": round(initial_risk_amount, 2),
                "entry_turnover": round(cost_summary.buy_turnover, 2),
                "exit_turnover": round(cost_summary.sell_turnover, 2),
                "total_turnover": round(cost_summary.total_turnover, 2),
                "stt": round(cost_summary.total_stt, 2),
                "exchange_fee": round(cost_summary.exchange_charge, 2),
                "ipft_fee": round(cost_summary.ipft_charge, 2),
                "sebi_fee": round(cost_summary.sebi_turnover_fee, 2),
                "stamp_duty": round(cost_summary.total_stamp_duty, 2),
                "gst": round(cost_summary.total_gst, 2),
            })

        # Step C: Session Close (15:30 IST) - Daily Mark to Market & Signal Generation
        closing_prices = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        session_equity = portfolio.get_portfolio_equity(closing_prices)
        invested_capital = portfolio.total_invested_capital()
        open_pos_value = sum(pos.market_value(closing_prices[s]) for s, pos in portfolio.positions.items())

        daily_records.append({
            "scenario_id": scenario_id,
            "strategy_version": version,
            "cost_schedule": cost_schedule,
            "date": current_dt.isoformat(),
            "cash": round(portfolio.cash, 2),
            "invested_capital": round(invested_capital, 2),
            "open_position_value": round(open_pos_value, 2),
            "total_equity": round(session_equity, 2),
            "open_positions": portfolio.position_count,
            "exposure_pct": round((open_pos_value / session_equity) * 100.0, 4) if session_equity > 0 else 0.0,
        })

        # Breadth regime check
        regime_state, _ = eval_regime(augmented_universe, config=config, bar_idx=day_idx)

        # Generate signals for tomorrow (stop before final day)
        if day_idx < len(trading_dates) - 2:
            for sym in APPROVED_21_SYMBOLS:
                if sym in portfolio.positions:
                    continue  # No duplicate positions

                sig = gen_signal(
                    symbol=sym,
                    df=augmented_universe[sym],
                    market_regime=regime_state,
                    config=config,
                    bar_idx=day_idx,
                    signal_date=current_dt,
                )

                if sig is not None:
                    bar = augmented_universe[sym].iloc[day_idx]
                    prio = calculate_signal_priority(sig, bar)
                    pending_signals[sym] = (sig, prio)

    # Compile DataFrames
    df_trades = pd.DataFrame(executed_trades)
    df_daily = pd.DataFrame(daily_records)
    df_rejected = pd.DataFrame(rejected_signals)

    df_daily["peak_equity"] = df_daily["total_equity"].cummax()
    df_daily["drawdown_pct"] = ((df_daily["total_equity"] - df_daily["peak_equity"]) / df_daily["peak_equity"]) * 100.0

    ending_equity = float(df_daily["total_equity"].iloc[-1])
    net_pnl = ending_equity - initial_capital
    net_return_pct = (net_pnl / initial_capital) * 100.0
    years = len(trading_dates) / 252.0
    cagr = (((ending_equity / initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if ending_equity > 0 else -100.0
    max_dd_pct = abs(float(df_daily["drawdown_pct"].min()))
    max_dd_inr = float((df_daily["peak_equity"] - df_daily["total_equity"]).max())

    total_trades_count = len(df_trades)
    if total_trades_count > 0:
        win_trades = df_trades[df_trades["net_pnl"] > 0]
        loss_trades = df_trades[df_trades["net_pnl"] <= 0]
        win_rate = (len(win_trades) / total_trades_count) * 100.0
        gross_wins = float(win_trades["net_pnl"].sum())
        gross_losses = float(abs(loss_trades["net_pnl"].sum()))
        net_pf = gross_wins / gross_losses if gross_losses > 0 else 999.0

        raw_gross_wins = float(df_trades[df_trades["gross_pnl"] > 0]["gross_pnl"].sum())
        raw_gross_losses = float(abs(df_trades[df_trades["gross_pnl"] <= 0]["gross_pnl"].sum()))
        gross_pf = raw_gross_wins / raw_gross_losses if raw_gross_losses > 0 else 999.0

        avg_win_inr = float(win_trades["net_pnl"].mean()) if len(win_trades) > 0 else 0.0
        avg_loss_inr = float(abs(loss_trades["net_pnl"].mean())) if len(loss_trades) > 0 else 0.0
        payoff_ratio = avg_win_inr / avg_loss_inr if avg_loss_inr > 0 else 999.0
        net_expectancy = float(df_trades["net_pnl"].mean())

        total_gross_pnl = float(df_trades["gross_pnl"].sum())
        total_costs = float(df_trades["total_costs"].sum())
        cost_to_gross_pct = (total_costs / total_gross_pnl) * 100.0 if total_gross_pnl > 0 else 999.0
        avg_holding_days = float(df_trades["holding_days"].mean())
        avg_cap_utilization = float(df_daily["exposure_pct"].mean())
    else:
        win_rate = 0.0
        gross_pf = 0.0
        net_pf = 0.0
        avg_win_inr = 0.0
        avg_loss_inr = 0.0
        payoff_ratio = 0.0
        net_expectancy = 0.0
        total_gross_pnl = 0.0
        total_costs = 0.0
        cost_to_gross_pct = 0.0
        avg_holding_days = 0.0
        avg_cap_utilization = 0.0

    summary_metrics = {
        "scenario_id": scenario_id,
        "strategy_version": version,
        "cost_schedule": cost_schedule,
        "initial_capital": initial_capital,
        "ending_equity": round(ending_equity, 2),
        "net_pnl": round(net_pnl, 2),
        "gross_pnl": round(total_gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "cost_to_gross_pct": round(cost_to_gross_pct, 2),
        "total_trades": total_trades_count,
        "winning_trades": len(win_trades) if total_trades_count > 0 else 0,
        "losing_trades": len(loss_trades) if total_trades_count > 0 else 0,
        "win_rate_pct": round(win_rate, 2),
        "gross_pf": round(gross_pf, 2),
        "net_pf": round(net_pf, 2),
        "avg_win_inr": round(avg_win_inr, 2),
        "avg_loss_inr": round(avg_loss_inr, 2),
        "payoff_ratio": round(payoff_ratio, 2),
        "net_expectancy": round(net_expectancy, 2),
        "max_drawdown_inr": round(max_dd_inr, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "cagr_pct": round(cagr, 2),
        "avg_holding_days": round(avg_holding_days, 1),
        "capital_utilization_pct": round(avg_cap_utilization, 2),
        "completed_trades": total_trades_count,
    }

    return {
        "summary": summary_metrics,
        "df_trades": df_trades,
        "df_daily": df_daily,
        "df_rejected": df_rejected,
    }


def main():
    print("=" * 80)
    print("SignalForge — Phase 32E.2: Controlled Performance Validation")
    print("=" * 80)

    print("\nLoading and synchronizing 21-stock daily universe...")
    universe_daily = load_and_resample_21_universe()
    sample_sym = APPROVED_21_SYMBOLS[0]
    trading_dates = list(universe_daily[sample_sym].index)
    print(f"Loaded {len(APPROVED_21_SYMBOLS)} symbols across {len(trading_dates)} synchronized sessions.")
    print(f"Session date range: {trading_dates[0].date()} to {trading_dates[-1].date()}")

    # Pre-compute indicators for both strategies
    print("\nPre-computing causal indicators across universe...")
    augmented_v1: Dict[str, pd.DataFrame] = {}
    augmented_v2: Dict[str, pd.DataFrame] = {}
    cfg_v1 = DTPV1Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)
    cfg_v2 = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

    for sym in APPROVED_21_SYMBOLS:
        df_sym = universe_daily[sym]
        augmented_v1[sym] = calculate_dtp_indicators_v1(df_sym, config=cfg_v1)
        augmented_v2[sym] = calculate_dtp_indicators_v2(df_sym, config=cfg_v2)

    scenarios_to_run = [
        ("DTP-V1", augmented_v1, False),  # DTP-V1 Official
        ("DTP-V1", augmented_v1, True),   # DTP-V1 Stress
        ("DTP-V2", augmented_v2, False),  # DTP-V2 Official
        ("DTP-V2", augmented_v2, True),   # DTP-V2 Stress
    ]

    all_summaries: List[Dict[str, Any]] = []
    all_trades: List[pd.DataFrame] = []
    all_daily: List[pd.DataFrame] = []

    for ver, aug_dict, use_stress in scenarios_to_run:
        sched_name = "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)"
        print(f"\nExecuting backtest: {ver} under {sched_name}...")
        res = run_strategy_simulation(
            version=ver,
            augmented_universe=aug_dict,
            trading_dates=trading_dates,
            use_stress_costs=use_stress,
            initial_capital=100000.0,
        )
        s = res["summary"]
        all_summaries.append(s)
        all_trades.append(res["df_trades"])
        all_daily.append(res["df_daily"])

        print(f"  Trades: {s['total_trades']}, WinRate: {s['win_rate_pct']}%, Net PnL: ₹{s['net_pnl']:,.2f}, NetPF: {s['net_pf']}, Payoff: {s['payoff_ratio']}, MaxDD: {s['max_drawdown_pct']}%, CAGR: {s['cagr_pct']}%")

    # Combine master tables
    df_summary = pd.DataFrame(all_summaries)
    df_all_trades = pd.concat(all_trades, ignore_index=True)
    df_all_daily = pd.concat(all_daily, ignore_index=True)

    # 1. Save phase32e_2_scenario_summary.csv
    summary_csv_path = OUT_DIR / "phase32e_2_scenario_summary.csv"
    df_summary.to_csv(summary_csv_path, index=False)
    print(f"\nSaved {summary_csv_path}")

    # 2. Save phase32e_2_trade_ledger.csv
    ledger_csv_path = OUT_DIR / "phase32e_2_trade_ledger.csv"
    df_all_trades.to_csv(ledger_csv_path, index=False)
    print(f"Saved {ledger_csv_path}")

    # 3. Save phase32e_2_daily_equity.csv
    daily_csv_path = OUT_DIR / "phase32e_2_daily_equity.csv"
    df_all_daily.to_csv(daily_csv_path, index=False)
    print(f"Saved {daily_csv_path}")

    # 4. Save phase32e_2_cost_reconciliation.csv
    cost_rows = []
    for s in all_summaries:
        scen_id = s["scenario_id"]
        scen_trades = df_all_trades[df_all_trades["scenario_id"] == scen_id]

        turnover = float(scen_trades["total_turnover"].sum())
        brokerage = float(scen_trades["brokerage"].sum())
        stt = float(scen_trades["stt"].sum())
        exchange_fee = float(scen_trades["exchange_fee"].sum())
        ipft_fee = float(scen_trades["ipft_fee"].sum())
        sebi_fee = float(scen_trades["sebi_fee"].sum())
        stamp_duty = float(scen_trades["stamp_duty"].sum())
        gst = float(scen_trades["gst"].sum())
        dp_charges = float(scen_trades["depository_charges"].sum())
        slippage_spread = float(scen_trades["execution_friction"].sum())
        total_costs = float(scen_trades["total_costs"].sum())
        calculated_sum = brokerage + stt + exchange_fee + ipft_fee + sebi_fee + stamp_duty + gst + dp_charges + slippage_spread
        reconciliation_delta = round(total_costs - calculated_sum, 4)

        items = [
            ("total_turnover", turnover),
            ("brokerage", brokerage),
            ("stt", stt),
            ("exchange_fee", exchange_fee),
            ("ipft_fee", ipft_fee),
            ("sebi_fee", sebi_fee),
            ("stamp_duty", stamp_duty),
            ("gst", gst),
            ("depository_charges", dp_charges),
            ("execution_friction_slippage_spread", slippage_spread),
            ("total_friction_costs", total_costs),
            ("component_sum", calculated_sum),
            ("reconciliation_delta", reconciliation_delta),
        ]
        for metric_name, val in items:
            cost_rows.append({
                "scenario_id": scen_id,
                "strategy_version": s["strategy_version"],
                "cost_schedule": s["cost_schedule"],
                "metric": metric_name,
                "value": round(val, 2) if "delta" not in metric_name else val,
            })

    df_cost_rec = pd.DataFrame(cost_rows)
    cost_rec_path = OUT_DIR / "phase32e_2_cost_reconciliation.csv"
    df_cost_rec.to_csv(cost_rec_path, index=False)
    print(f"Saved {cost_rec_path}")

    # 5. Save phase32e_2_stock_attribution.csv
    stock_rows = []
    for s in all_summaries:
        scen_id = s["scenario_id"]
        scen_trades = df_all_trades[df_all_trades["scenario_id"] == scen_id]

        for sym in APPROVED_21_SYMBOLS:
            sym_trades = scen_trades[scen_trades["symbol"] == sym]
            n_t = len(sym_trades)
            if n_t > 0:
                wins = len(sym_trades[sym_trades["net_pnl"] > 0])
                losses = len(sym_trades[sym_trades["net_pnl"] <= 0])
                wr = (wins / n_t) * 100.0
                gross = float(sym_trades["gross_pnl"].sum())
                costs = float(sym_trades["total_costs"].sum())
                net = float(sym_trades["net_pnl"].sum())
                gwins = float(sym_trades[sym_trades["net_pnl"] > 0]["net_pnl"].sum())
                glosses = float(abs(sym_trades[sym_trades["net_pnl"] <= 0]["net_pnl"].sum()))
                npf = round(gwins / glosses, 2) if glosses > 0 else 999.0
                avg_hold = round(float(sym_trades["holding_days"].mean()), 1)
            else:
                wins = losses = 0
                wr = 0.0
                gross = costs = net = 0.0
                npf = 0.0
                avg_hold = 0.0

            stock_rows.append({
                "scenario_id": scen_id,
                "strategy_version": s["strategy_version"],
                "cost_schedule": s["cost_schedule"],
                "symbol": sym,
                "trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 2),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "net_profit_factor": npf,
                "avg_holding_days": avg_hold,
            })

    df_stock_attr = pd.DataFrame(stock_rows)
    stock_attr_path = OUT_DIR / "phase32e_2_stock_attribution.csv"
    df_stock_attr.to_csv(stock_attr_path, index=False)
    print(f"Saved {stock_attr_path}")

    # 6. Save phase32e_2_sector_attribution.csv
    sector_rows = []
    unique_sectors = sorted(list(set(EXPANDED_SECTOR_MAP.values())))
    for s in all_summaries:
        scen_id = s["scenario_id"]
        scen_trades = df_all_trades[df_all_trades["scenario_id"] == scen_id]
        total_pnl = float(scen_trades["net_pnl"].sum())

        for sec in unique_sectors:
            sec_trades = scen_trades[scen_trades["sector"] == sec]
            n_t = len(sec_trades)
            if n_t > 0:
                wins = len(sec_trades[sec_trades["net_pnl"] > 0])
                losses = len(sec_trades[sec_trades["net_pnl"] <= 0])
                wr = (wins / n_t) * 100.0
                gross = float(sec_trades["gross_pnl"].sum())
                costs = float(sec_trades["total_costs"].sum())
                net = float(sec_trades["net_pnl"].sum())
                gwins = float(sec_trades[sec_trades["net_pnl"] > 0]["net_pnl"].sum())
                glosses = float(abs(sec_trades[sec_trades["net_pnl"] <= 0]["net_pnl"].sum()))
                npf = round(gwins / glosses, 2) if glosses > 0 else 999.0
                alloc_pct = (n_t / len(scen_trades)) * 100.0 if len(scen_trades) > 0 else 0.0
            else:
                wins = losses = 0
                wr = 0.0
                gross = costs = net = 0.0
                npf = 0.0
                alloc_pct = 0.0

            sector_rows.append({
                "scenario_id": scen_id,
                "strategy_version": s["strategy_version"],
                "cost_schedule": s["cost_schedule"],
                "sector": sec,
                "trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 2),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "net_profit_factor": npf,
                "trade_allocation_pct": round(alloc_pct, 2),
            })

    df_sec_attr = pd.DataFrame(sector_rows)
    sec_attr_path = OUT_DIR / "phase32e_2_sector_attribution.csv"
    df_sec_attr.to_csv(sec_attr_path, index=False)
    print(f"Saved {sec_attr_path}")

    # 7. Save phase32e_2_exit_attribution.csv
    exit_rows = []
    for s in all_summaries:
        scen_id = s["scenario_id"]
        scen_trades = df_all_trades[df_all_trades["scenario_id"] == scen_id]
        total_trades = len(scen_trades)

        for reason in scen_trades["exit_reason"].unique():
            r_trades = scen_trades[scen_trades["exit_reason"] == reason]
            n_t = len(r_trades)
            pct = (n_t / total_trades) * 100.0 if total_trades > 0 else 0.0
            gross = float(r_trades["gross_pnl"].sum())
            costs = float(r_trades["total_costs"].sum())
            net = float(r_trades["net_pnl"].sum())
            avg_r = float(r_trades["realized_r"].mean())
            avg_hold = float(r_trades["holding_days"].mean())

            exit_rows.append({
                "scenario_id": scen_id,
                "strategy_version": s["strategy_version"],
                "cost_schedule": s["cost_schedule"],
                "exit_reason": reason,
                "trades": n_t,
                "pct_of_trades": round(pct, 2),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "avg_realized_r": round(avg_r, 4),
                "avg_holding_days": round(avg_hold, 1),
            })

    df_exit_attr = pd.DataFrame(exit_rows)
    exit_attr_path = OUT_DIR / "phase32e_2_exit_attribution.csv"
    df_exit_attr.to_csv(exit_attr_path, index=False)
    print(f"Saved {exit_attr_path}")

    # 8. Save phase32e_2_acceptance_gates.csv
    gate_defs = [
        ("GATE_1_NET_PF", "Net Profit Factor >= 1.30", 1.30, lambda s: s["net_pf"] >= 1.30, lambda s: f"{s['net_pf']:.2f}"),
        ("GATE_2_WIN_RATE", "Win Rate >= 45%", 45.0, lambda s: s["win_rate_pct"] >= 45.0, lambda s: f"{s['win_rate_pct']:.2f}%"),
        ("GATE_3_MAX_DD", "Maximum Drawdown <= 18%", 18.0, lambda s: s["max_drawdown_pct"] <= 18.0, lambda s: f"{s['max_drawdown_pct']:.2f}%"),
        ("GATE_4_TRADES", "Completed Trades >= 30", 30, lambda s: s["completed_trades"] >= 30, lambda s: f"{s['completed_trades']}"),
        ("GATE_5_CAGR", "CAGR >= 12%", 12.0, lambda s: s["cagr_pct"] >= 12.0, lambda s: f"{s['cagr_pct']:.2f}%"),
        ("GATE_6_PAYOFF", "Payoff Ratio >= 1.80", 1.80, lambda s: s["payoff_ratio"] >= 1.80, lambda s: f"{s['payoff_ratio']:.2f}"),
    ]

    gate_rows = []
    for s in all_summaries:
        for gid, gdesc, thresh, eval_fn, act_fn in gate_defs:
            status = "PASS" if eval_fn(s) else "FAIL"
            gate_rows.append({
                "scenario_id": s["scenario_id"],
                "strategy_version": s["strategy_version"],
                "cost_schedule": s["cost_schedule"],
                "gate_id": gid,
                "gate_description": gdesc,
                "threshold": thresh,
                "actual_value": act_fn(s),
                "status": status,
            })

    df_gates = pd.DataFrame(gate_rows)
    gates_path = OUT_DIR / "phase32e_2_acceptance_gates.csv"
    df_gates.to_csv(gates_path, index=False)
    print(f"Saved {gates_path}")

    print("\nPhase 32E.2 Controlled Validation complete.")

if __name__ == "__main__":
    main()

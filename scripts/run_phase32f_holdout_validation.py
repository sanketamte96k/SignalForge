"""
SignalForge — Phase 32F: 2020 Out-of-Sample Holdout Validation Runner
=====================================================================
File: scripts/run_phase32f_holdout_validation.py

Executes the pre-registered DTP-V2 holdout validation across the
quarantined 2020 NSE cash-equity dataset (2020-01-01 to 2020-12-31).
Uses the frozen DTP-V2 implementation and forensic cost engine.
Strictly adheres to ₹0 budget, immutable parameters, and governance rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
    calculate_signal_priority,
)
from src.strategy.dtp_v2.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV2Config,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v2.portfolio_rules import DTPPortfolioTracker
from src.strategy.dtp_v2.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)

OUT_DIR = PROJECT_ROOT / "reports" / "phase32f"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_and_resample_2020_holdout() -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """
    Loads 1-minute historical data for the 21 approved symbols,
    including 2019 warm-up period (from 2019-01-01) through 2020-12-31,
    and resamples to synchronized daily OHLCV bars.
    Never accesses ADANIPORTS.
    """
    stocks_dir = PROJECT_ROOT / "data" / "historical" / "stocks"
    universe_daily: Dict[str, pd.DataFrame] = {}
    quality_audit: Dict[str, Any] = {}

    for sym in APPROVED_21_SYMBOLS:
        csv_path = stocks_dir / f"{sym}_1m.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing required historical file: {csv_path}")

        df = pd.read_csv(csv_path)
        # Parse timestamp column
        ts_col = "timestamp" if "timestamp" in df.columns else df.columns[0]
        df[ts_col] = pd.to_datetime(df[ts_col])
        df = df.set_index(ts_col).sort_index()

        # Filter from 2019-01-01 (warmup) to 2020-12-31 (holdout end)
        df_filtered = df[(df.index >= "2019-01-01") & (df.index <= "2020-12-31 23:59:59")].copy()

        # Resample to daily OHLCV
        daily_open = df_filtered["open"].resample("1D").first()
        daily_high = df_filtered["high"].resample("1D").max()
        daily_low = df_filtered["low"].resample("1D").min()
        daily_close = df_filtered["close"].resample("1D").last()
        daily_vol = df_filtered["volume"].resample("1D").sum()

        daily_df = pd.DataFrame({
            "open": daily_open,
            "high": daily_high,
            "low": daily_low,
            "close": daily_close,
            "volume": daily_vol,
        }).dropna(subset=["close"])

        universe_daily[sym] = daily_df

        # Record 2020 data quality
        df_2020 = daily_df[daily_df.index >= "2020-01-01"]
        quality_audit[sym] = {
            "total_bars_loaded": len(df_filtered),
            "daily_bars_total": len(daily_df),
            "daily_bars_2020": len(df_2020),
            "start_date_2020": df_2020.index[0].date().isoformat() if len(df_2020) > 0 else "N/A",
            "end_date_2020": df_2020.index[-1].date().isoformat() if len(df_2020) > 0 else "N/A",
            "missing_nan_count": int(df_2020.isna().sum().sum()),
        }

    # Verify session synchronization across universe in 2020
    sample_sym = APPROVED_21_SYMBOLS[0]
    expected_2020_dates = set(universe_daily[sample_sym][universe_daily[sample_sym].index >= "2020-01-01"].index)
    for sym in APPROVED_21_SYMBOLS:
        sym_2020_dates = set(universe_daily[sym][universe_daily[sym].index >= "2020-01-01"].index)
        diff = expected_2020_dates.symmetric_difference(sym_2020_dates)
        if diff:
            print(f"Warning: Synchronization discrepancy for {sym}: {len(diff)} mismatched sessions.")

    return universe_daily, quality_audit


def execute_holdout_backtest(
    universe_daily: Dict[str, pd.DataFrame],
    risk_fraction: float = 0.0125,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
    scenario_id: str = "HOLDOUT_2020_S3_125",
) -> Dict[str, Any]:
    """
    Executes an immutable, strictly causal validation backtest across the 2020 holdout partition.
    Includes causal indicators pre-computed with 2019 warm-up.
    Trading strictly commences on the first trading session of 2020.
    """
    config = DTPV2Config(
        risk_fraction_per_trade=risk_fraction,
        max_concurrent_positions=3,
        max_position_allocation_pct=0.333,
        max_sector_exposure_pct=0.40,
        profit_target_r_mult=3.0,
        trailing_atr_mult=2.0,
        trailing_r_mult=1.5,
        max_holding_sessions=10,
        execution_slippage_bps=5.0,
        execution_spread_bps=5.0,
        symbol_sector_map=EXPANDED_SECTOR_MAP,
        symbol_isin_map=EXPANDED_ISIN_MAP,
    )

    # Pre-compute indicators with 2019 warm-up
    augmented_universe: Dict[str, pd.DataFrame] = {}
    for sym in APPROVED_21_SYMBOLS:
        augmented_universe[sym] = calculate_dtp_indicators(universe_daily[sym], config=config)

    # Identify all trading dates in 2020
    all_dates = list(universe_daily[APPROVED_21_SYMBOLS[0]].index)
    holdout_indices = [idx for idx, ts in enumerate(all_dates) if ts.year == 2020]
    first_2020_idx = holdout_indices[0]
    total_2020_sessions = len(holdout_indices)

    portfolio = DTPPortfolioTracker(initial_capital=initial_capital, config=config)
    positions_state: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str]]] = {}
    executed_trades: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []
    trade_counter = 0

    emergency_termination = False
    termination_reason = ""

    # Day-by-day causal simulation across 2020
    for day_offset, day_idx in enumerate(holdout_indices):
        current_ts = all_dates[day_idx]
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution for Pending Signals
        if pending_signals and not emergency_termination:
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])

            for sym, (sig, prio_tuple) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])

                action, fill_price, action_msg = evaluate_next_open_execution(
                    signal=sig,
                    next_open_price=today_open,
                    config=config,
                )

                if action != OrderAction.ENTER_LONG:
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = config.symbol_sector_map.get(sym, "General")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)

                shares, size_msg = calculate_dtp_position_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    config=config,
                )

                if shares <= 0:
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    sector=sector,
                    current_prices=curr_prices,
                )

                if not can_open:
                    continue

                # Open Position
                trade_counter += 1
                order_id = f"DTP_V2_2020_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
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

                positions_state[sym] = DTPPositionState(
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

            # Last day of 2020 forced liquidation
            if day_offset == total_2020_sessions - 1 or emergency_termination:
                friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exit_px = float(bar["close"]) * (1.0 - friction_rate)
                full_exits.append((sym, "MANUAL_CLOSE", exit_px, "End of 2020 validation period liquidation"))
                continue

            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            open_px = float(bar["open"])
            atr = float(bar.get("atr", 1.0))
            ema50 = float(bar.get("ema_slow", close))
            rsi = float(bar.get("rsi", 50.0))
            bb_upper = float(bar.get("bb_upper", close * 1.10))

            reason_obj, exit_px, exit_msg = evaluate_exit_conditions(
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

            breakdown, cost_summary = calculate_dtp_roundtrip_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix="DTP_V2_2020",
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
                "strategy_version": "DTP-V2",
                "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
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
                "total_turnover": round(cost_summary.total_turnover, 2),
            })

        # Step C: Session Close (15:30 IST) Mark-to-Market & Signals
        closing_prices = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        session_equity = portfolio.get_portfolio_equity(closing_prices)
        invested_capital = portfolio.total_invested_capital()
        open_pos_value = sum(pos.market_value(closing_prices[s]) for s, pos in portfolio.positions.items())

        # Check peak drawdown limit
        peak_so_far = max([r["total_equity"] for r in daily_records] + [initial_capital])
        current_dd_pct = ((peak_so_far - session_equity) / peak_so_far) * 100.0 if peak_so_far > 0 else 0.0

        daily_records.append({
            "scenario_id": scenario_id,
            "date": current_dt.isoformat(),
            "cash": round(portfolio.cash, 2),
            "invested_capital": round(invested_capital, 2),
            "open_position_value": round(open_pos_value, 2),
            "total_equity": round(session_equity, 2),
            "open_positions": portfolio.position_count,
            "exposure_pct": round((open_pos_value / session_equity) * 100.0, 4) if session_equity > 0 else 0.0,
            "drawdown_pct": round(current_dd_pct, 4),
        })

        if current_dd_pct > 18.0 and not emergency_termination:
            emergency_termination = True
            termination_reason = f"Emergency termination: Maximum drawdown breached 18% threshold ({current_dd_pct:.2f}%) on {current_dt}"
            print(f"TERMINATION: {termination_reason}")

        # Regime & Signal Generation for Tomorrow
        regime_state, _ = evaluate_breadth_regime(augmented_universe, config=config, bar_idx=day_idx)

        if day_offset < total_2020_sessions - 2 and not emergency_termination:
            for sym in APPROVED_21_SYMBOLS:
                if sym in portfolio.positions:
                    continue

                sig = generate_eod_signal(
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

    df_trades = pd.DataFrame(executed_trades)
    df_daily = pd.DataFrame(daily_records)

    # Compute aggregate performance
    ending_equity = float(df_daily["total_equity"].iloc[-1])
    net_pnl = ending_equity - initial_capital
    cagr = (((ending_equity / initial_capital) ** (1.0 / (total_2020_sessions / 252.0))) - 1.0) * 100.0 if ending_equity > 0 else -100.0
    max_dd = float(df_daily["drawdown_pct"].max())

    n_t = len(df_trades)
    if n_t > 0:
        win_trades = df_trades[df_trades["net_pnl"] > 0]
        loss_trades = df_trades[df_trades["net_pnl"] <= 0]
        wr = (len(win_trades) / n_t) * 100.0
        gw = float(win_trades["net_pnl"].sum())
        gl = float(abs(loss_trades["net_pnl"].sum()))
        npf = gw / gl if gl > 0 else 999.0
        aw = float(win_trades["net_pnl"].mean()) if len(win_trades) > 0 else 0.0
        al = float(abs(loss_trades["net_pnl"].mean())) if len(loss_trades) > 0 else 0.0
        payoff = aw / al if al > 0 else 999.0
        cap_util = float(df_daily["exposure_pct"].mean())
        gross_pnl = float(df_trades["gross_pnl"].sum())
        costs = float(df_trades["total_costs"].sum())
    else:
        wr = 0.0
        npf = 0.0
        payoff = 0.0
        cap_util = 0.0
        gross_pnl = 0.0
        costs = 0.0

    summary = {
        "scenario_id": scenario_id,
        "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
        "risk_fraction_pct": round(risk_fraction * 100.0, 2),
        "initial_capital": initial_capital,
        "ending_equity": round(ending_equity, 2),
        "net_pnl": round(net_pnl, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(costs, 2),
        "total_trades": n_t,
        "win_rate_pct": round(wr, 2),
        "net_pf": round(npf, 2),
        "payoff_ratio": round(payoff, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "cagr_pct": round(cagr, 2),
        "capital_utilization_pct": round(cap_util, 2),
        "emergency_termination": emergency_termination,
        "termination_reason": termination_reason,
    }

    return {
        "summary": summary,
        "df_trades": df_trades,
        "df_daily": df_daily,
    }


def main():
    print("=" * 80)
    print("SignalForge — Phase 32F: 2020 Out-of-Sample Holdout Validation")
    print("=" * 80)

    print("\n1. Loading 2020 holdout partition with 2019 causal warm-up...")
    universe_daily, quality_audit = load_and_resample_2020_holdout()
    sample_sym = APPROVED_21_SYMBOLS[0]
    total_sessions_2020 = len(universe_daily[sample_sym][universe_daily[sample_sym].index >= "2020-01-01"])
    print(f"Loaded 21 symbols across {total_sessions_2020} trading sessions in 2020.")

    # Execute Baseline Pre-Registered Sizing (1.25% Risk)
    print("\n2. Executing Pre-Registered Holdout Validation (1.25% Risk)...")
    res_s3_off = execute_holdout_backtest(universe_daily, risk_fraction=0.0125, use_stress_costs=False, scenario_id="HOLDOUT_2020_S3_125_OFFICIAL")
    res_s3_str = execute_holdout_backtest(universe_daily, risk_fraction=0.0125, use_stress_costs=True, scenario_id="HOLDOUT_2020_S3_125_STRESS")

    # Execute Secondary Benchmark Sizing (1.00% Risk)
    print("\n3. Executing Secondary Benchmark Validation (1.00% Risk)...")
    res_base_off = execute_holdout_backtest(universe_daily, risk_fraction=0.010, use_stress_costs=False, scenario_id="HOLDOUT_2020_BASE_100_OFFICIAL")
    res_base_str = execute_holdout_backtest(universe_daily, risk_fraction=0.010, use_stress_costs=True, scenario_id="HOLDOUT_2020_BASE_100_STRESS")

    # Execute Aggressive Sensitivity (1.50% Risk)
    print("\n4. Executing Aggressive Sensitivity (1.50% Risk)...")
    res_s4_off = execute_holdout_backtest(universe_daily, risk_fraction=0.015, use_stress_costs=False, scenario_id="HOLDOUT_2020_S4_150_OFFICIAL")
    res_s4_str = execute_holdout_backtest(universe_daily, risk_fraction=0.015, use_stress_costs=True, scenario_id="HOLDOUT_2020_S4_150_STRESS")

    all_runs = [res_s3_off, res_s3_str, res_base_off, res_base_str, res_s4_off, res_s4_str]

    # Save Metrics CSVs
    official_summaries = [r["summary"] for r in [res_s3_off, res_base_off, res_s4_off]]
    stress_summaries = [r["summary"] for r in [res_s3_str, res_base_str, res_s4_str]]

    df_off_metrics = pd.DataFrame(official_summaries)
    df_str_metrics = pd.DataFrame(stress_summaries)

    df_off_metrics.to_csv(OUT_DIR / "phase32f_official_metrics.csv", index=False)
    df_str_metrics.to_csv(OUT_DIR / "phase32f_stress_metrics.csv", index=False)
    print("Saved official and stress metrics CSVs.")

    # Save Trade Ledgers
    df_all_trades = pd.concat([r["df_trades"] for r in all_runs], ignore_index=True)
    df_all_trades.to_csv(OUT_DIR / "phase32f_trade_ledger.csv", index=False)
    print("Saved holdout trade ledger CSV.")

    # Save Stock Attribution (for primary 1.25% Official run)
    primary_trades = res_s3_off["df_trades"]
    stock_rows = []
    for sym in APPROVED_21_SYMBOLS:
        st = primary_trades[primary_trades["symbol"] == sym]
        n_t = len(st)
        if n_t > 0:
            wins = len(st[st["net_pnl"] > 0])
            losses = len(st[st["net_pnl"] <= 0])
            wr = (wins / n_t) * 100.0
            gross = float(st["gross_pnl"].sum())
            costs = float(st["total_costs"].sum())
            net = float(st["net_pnl"].sum())
            gw = float(st[st["net_pnl"] > 0]["net_pnl"].sum())
            gl = float(abs(st[st["net_pnl"] <= 0]["net_pnl"].sum()))
            pf = gw / gl if gl > 0 else 999.0
        else:
            wins = losses = 0
            wr = gross = costs = net = pf = 0.0

        stock_rows.append({
            "symbol": sym,
            "sector": EXPANDED_SECTOR_MAP.get(sym, "General"),
            "trades": n_t,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 2),
            "gross_pnl": round(gross, 2),
            "total_costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "net_pf": round(pf, 2),
        })

    df_stock_attr = pd.DataFrame(stock_rows)
    df_stock_attr.to_csv(OUT_DIR / "phase32f_stock_attribution.csv", index=False)
    print("Saved stock attribution CSV.")

    # Save Sector Attribution
    unique_sectors = sorted(list(set(EXPANDED_SECTOR_MAP.values())))
    sector_rows = []
    for sec in unique_sectors:
        st = primary_trades[primary_trades["sector"] == sec]
        n_t = len(st)
        if n_t > 0:
            wins = len(st[st["net_pnl"] > 0])
            losses = len(st[st["net_pnl"] <= 0])
            wr = (wins / n_t) * 100.0
            gross = float(st["gross_pnl"].sum())
            costs = float(st["total_costs"].sum())
            net = float(st["net_pnl"].sum())
            gw = float(st[st["net_pnl"] > 0]["net_pnl"].sum())
            gl = float(abs(st[st["net_pnl"] <= 0]["net_pnl"].sum()))
            pf = gw / gl if gl > 0 else 999.0
        else:
            wins = losses = 0
            wr = gross = costs = net = pf = 0.0

        sector_rows.append({
            "sector": sec,
            "trades": n_t,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 2),
            "gross_pnl": round(gross, 2),
            "total_costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "net_pf": round(pf, 2),
        })

    df_sec_attr = pd.DataFrame(sector_rows)
    df_sec_attr.to_csv(OUT_DIR / "phase32f_sector_attribution.csv", index=False)
    print("Saved sector attribution CSV.")

    # Save Regime Attribution
    # Categorize primary trades by entry regime
    trading_dates = list(universe_daily[APPROVED_21_SYMBOLS[0]].index)
    date_to_idx = {ts.date(): idx for idx, ts in enumerate(trading_dates)}
    regime_cache = {}
    cfg = DTPV2Config()
    for d, idx in date_to_idx.items():
        state, _ = evaluate_breadth_regime(universe_daily, config=cfg, bar_idx=idx)
        regime_cache[d.isoformat()] = state.value

    primary_trades = primary_trades.copy()
    primary_trades["entry_regime"] = primary_trades["entry_date"].map(regime_cache).fillna("NEUTRAL")

    regime_rows = []
    for reg in ["BULLISH", "NEUTRAL", "BEARISH"]:
        rt = primary_trades[primary_trades["entry_regime"] == reg]
        n_t = len(rt)
        if n_t > 0:
            wins = len(rt[rt["net_pnl"] > 0])
            losses = len(rt[rt["net_pnl"] <= 0])
            wr = (wins / n_t) * 100.0
            gross = float(rt["gross_pnl"].sum())
            costs = float(rt["total_costs"].sum())
            net = float(rt["net_pnl"].sum())
            gw = float(rt[rt["net_pnl"] > 0]["net_pnl"].sum())
            gl = float(abs(rt[rt["net_pnl"] <= 0]["net_pnl"].sum()))
            pf = gw / gl if gl > 0 else 999.0
            aw = float(rt[rt["net_pnl"] > 0]["net_pnl"].mean()) if wins > 0 else 0.0
            al = float(abs(rt[rt["net_pnl"] <= 0]["net_pnl"].mean())) if losses > 0 else 0.0
            po = aw / al if al > 0 else 999.0
        else:
            wins = losses = 0
            wr = gross = costs = net = pf = po = 0.0

        regime_rows.append({
            "market_regime": reg,
            "trades": n_t,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 2),
            "gross_pnl": round(gross, 2),
            "total_costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "net_pf": round(pf, 2),
            "payoff_ratio": round(po, 2),
        })

    df_reg_attr = pd.DataFrame(regime_rows)
    df_reg_attr.to_csv(OUT_DIR / "phase32f_regime_attribution.csv", index=False)
    print("Saved regime attribution CSV.")

    # Save Acceptance Gates CSV
    # Audit both 6 Original Acceptance Gates AND 6 Pre-Registered Holdout Gates
    gate_rows = []
    s3_off = res_s3_off["summary"]
    s3_str = res_s3_str["summary"]

    gates_def = [
        # Original 6 Acceptance Gates
        ("ORIG_GATE_1_NET_PF", "Net Profit Factor >= 1.30 (Both Sched)", 1.30,
         f"Off: {s3_off['net_pf']}, Str: {s3_str['net_pf']}",
         "PASS" if (s3_off["net_pf"] >= 1.30 and s3_str["net_pf"] >= 1.30) else "FAIL"),
        ("ORIG_GATE_2_WIN_RATE", "Win Rate >= 45.0%", 45.0,
         f"{s3_off['win_rate_pct']}%",
         "PASS" if s3_off["win_rate_pct"] >= 45.0 else "FAIL"),
        ("ORIG_GATE_3_MAX_DD", "Maximum Drawdown <= 18.0%", 18.0,
         f"Off: {s3_off['max_drawdown_pct']}%, Str: {s3_str['max_drawdown_pct']}%",
         "PASS" if (s3_off["max_drawdown_pct"] <= 18.0 and s3_str["max_drawdown_pct"] <= 18.0) else "FAIL"),
        ("ORIG_GATE_4_TRADES", "Completed Trades >= 30", 30,
         f"{s3_off['total_trades']}",
         "PASS" if s3_off["total_trades"] >= 30 else "FAIL"),
        ("ORIG_GATE_5_CAGR", "CAGR >= 12.0%", 12.0,
         f"Off: {s3_off['cagr_pct']}%, Str: {s3_str['cagr_pct']}%",
         "PASS" if (s3_off["cagr_pct"] >= 12.0 and s3_str["cagr_pct"] >= 12.0) else "FAIL"),
        ("ORIG_GATE_6_PAYOFF", "Payoff Ratio >= 1.80", 1.80,
         f"Off: {s3_off['payoff_ratio']}, Str: {s3_str['payoff_ratio']}",
         "PASS" if (s3_off["payoff_ratio"] >= 1.80 and s3_str["payoff_ratio"] >= 1.80) else "FAIL"),

        # Pre-Registered 2020 Holdout Gates
        ("HOLD_GATE_1_NET_PF", "Holdout Net Profit Factor >= 1.25 (Both Sched)", 1.25,
         f"Off: {s3_off['net_pf']}, Str: {s3_str['net_pf']}",
         "PASS" if (s3_off["net_pf"] >= 1.25 and s3_str["net_pf"] >= 1.25) else "FAIL"),
        ("HOLD_GATE_2_WIN_RATE", "Holdout Win Rate >= 40.0%", 40.0,
         f"{s3_off['win_rate_pct']}%",
         "PASS" if s3_off["win_rate_pct"] >= 40.0 else "FAIL"),
        ("HOLD_GATE_3_MAX_DD", "Holdout Maximum Drawdown <= 18.0%", 18.0,
         f"Off: {s3_off['max_drawdown_pct']}%, Str: {s3_str['max_drawdown_pct']}%",
         "PASS" if (s3_off["max_drawdown_pct"] <= 18.0 and s3_str["max_drawdown_pct"] <= 18.0) else "FAIL"),
        ("HOLD_GATE_4_TRADES", "Holdout Completed Trades >= 10", 10,
         f"{s3_off['total_trades']}",
         "PASS" if s3_off["total_trades"] >= 10 else "FAIL"),
        ("HOLD_GATE_5_NET_PNL", "Holdout Net PnL > 0 (Both Sched)", 0.0,
         f"Off: ₹{s3_off['net_pnl']}, Str: ₹{s3_str['net_pnl']}",
         "PASS" if (s3_off["net_pnl"] > 0 and s3_str["net_pnl"] > 0) else "FAIL"),
        ("HOLD_GATE_6_PAYOFF", "Holdout Payoff Ratio >= 1.50", 1.50,
         f"Off: {s3_off['payoff_ratio']}, Str: {s3_str['payoff_ratio']}",
         "PASS" if (s3_off["payoff_ratio"] >= 1.50 and s3_str["payoff_ratio"] >= 1.50) else "FAIL"),
    ]

    for gid, gdesc, thresh, act, status in gates_def:
        gate_rows.append({
            "gate_id": gid,
            "gate_description": gdesc,
            "threshold": thresh,
            "actual_value": act,
            "status": status,
        })

    df_gates = pd.DataFrame(gate_rows)
    df_gates.to_csv(OUT_DIR / "phase32f_acceptance_gates.csv", index=False)
    print("Saved acceptance gates CSV.")

    print("\nPhase 32F Holdout Execution Complete.")

if __name__ == "__main__":
    main()

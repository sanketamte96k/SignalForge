"""
SignalForge — Phase 24G.14: Independent Strategy Alpha & Cost Model Investigation
================================================================================
Comprehensive investigation into:
  1. Transaction cost discrepancy (3,948 vs 962 trades in combined evaluation)
  2. Independent transaction cost audit (statutory formulas, historical tax regimes, edge scenarios)
  3. Gross alpha decomposition (direction, time-of-day, exit reason, signal indicator conditions)
  4. Trading frequency and turnover dynamics (reversals, holding duration, rapid re-entries)
  5. Partition diagnostic summary across Training (2017-2018), Validation (2019), and Holdout (2020)
"""

from __future__ import annotations

import datetime
from datetime import time as dtime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.risk_engine_v2 import (
    CostBreakdown,
    CostModelType,
    ExitReason,
    PositionSide,
    RejectionReason,
    RiskEngineConfigV2,
    RiskEngineV2,
    V2Trade,
    calculate_transaction_costs,
    calculate_position_size,
    calculate_clamped_stop_distance,
)
from src.strategy.backtest_strategy import (
    Position,
    StrategyConfig,
    calculate_timeframe_indicators,
    _make_cursors,
    _generate_filtered_signal,
    signal_result_to_position,
)

OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G14_alpha_cost_investigation"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.14 PREFLIGHT VERIFICATION")
    print("=" * 80)

    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    cfg_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    print(f"Strategy Snapshot Hash: {cfg_hash}")
    assert cfg_hash == EXPECTED_CONFIG_HASH, f"Config hash mismatch: expected {EXPECTED_CONFIG_HASH}, got {cfg_hash}"

    data_bytes = DATA_PATH.read_bytes()
    data_hash = hashlib.sha256(data_bytes).hexdigest()
    print(f"ADANIPORTS SHA-256:     {data_hash}")
    assert data_hash == EXPECTED_DATA_HASH, f"Data hash mismatch: expected {EXPECTED_DATA_HASH}, got {data_hash}"

    assert REGISTRY_PATH.exists(), "Universe registry missing"
    assert PAPER_LEDGER_PATH.exists(), "Paper ledger missing"
    print("Preflight verification passed successfully.\n")


def audit_cost_model_scenarios(df_trades_combined: pd.DataFrame) -> pd.DataFrame:
    """
    Independent audit of realistic Indian transaction friction calculations
    across representative scenarios from raw trade records.
    """
    print("Executing Independent Transaction Cost Audit...")

    scenarios = []

    # 1. Large Turnover Long Trade
    t_large_long = df_trades_combined[(df_trades_combined["side"] == "LONG") & (df_trades_combined["quantity"] > 1000)].iloc[0]
    scenarios.append(("1. Large Turnover LONG Trade", t_large_long))

    # 2. Large Turnover Short Trade
    t_large_short = df_trades_combined[(df_trades_combined["side"] == "SHORT") & (df_trades_combined["quantity"] > 1000)].iloc[0]
    scenarios.append(("2. Large Turnover SHORT Trade", t_large_short))

    # 3. Small Turnover Long Trade
    small_candidates = df_trades_combined[(df_trades_combined["side"] == "LONG") & (df_trades_combined["quantity"] <= 3)]
    t_small_long = small_candidates.iloc[0] if len(small_candidates) > 0 else df_trades_combined.iloc[-1]
    scenarios.append(("3. Small Turnover LONG Trade", t_small_long))

    # 4. Small Turnover Short Trade
    small_short_cand = df_trades_combined[(df_trades_combined["side"] == "SHORT") & (df_trades_combined["quantity"] <= 3)]
    t_small_short = small_short_cand.iloc[0] if len(small_short_cand) > 0 else df_trades_combined.iloc[-2]
    scenarios.append(("4. Small Turnover SHORT Trade", t_small_short))

    # 5. Same-Day Entry and Exit
    sameday_cand = df_trades_combined[df_trades_combined["bars_held"] > 0]
    t_sameday = sameday_cand.iloc[0]
    scenarios.append(("5. Same-Day Intraday Entry & Exit", t_sameday))

    # 6. Gap-Through-Stop Exit
    gap_cand = df_trades_combined[
        ((df_trades_combined["side"] == "LONG") & (df_trades_combined["exit_price"] < df_trades_combined["initial_stop"])) |
        ((df_trades_combined["side"] == "SHORT") & (df_trades_combined["exit_price"] > df_trades_combined["initial_stop"]))
    ]
    t_gap = gap_cand.iloc[0]
    scenarios.append(("6. Gap-Through-Stop Adverse Exit", t_gap))

    # 7. EOD Mandatory Liquidation
    eod_cand = df_trades_combined[df_trades_combined["exit_reason"] == "EOD"]
    t_eod = eod_cand.iloc[0]
    scenarios.append(("7. 15:29:00 Mandatory EOD Liquidation", t_eod))

    # 8. Final-Dataset Boundary Liquidation (last trade in dataset)
    t_final = df_trades_combined.iloc[-1]
    scenarios.append(("8. Partition Boundary Final Liquidation", t_final))

    # 9. Synthetic Morning Window Entry (09:20:00 to verify 5 bps morning slippage rate)
    synth_morning = pd.Series({
        "trade_id": 99901,
        "side": "LONG",
        "entry_time": "2020-01-02 09:20:00",
        "exit_time": "2020-01-02 09:40:00",
        "entry_price": 380.0,
        "exit_price": 382.0,
        "quantity": 1000,
        "initial_stop": 378.0,
        "final_stop": 378.0,
        "bars_held": 20,
        "exit_reason": "TAKE_PROFIT",
    })
    scenarios.append(("9. Morning Window Entry (09:15–09:30 5 bps Slippage)", synth_morning))

    audit_rows = []

    for name, row in scenarios:
        side = PositionSide(row["side"])
        entry_p = float(row["entry_price"])
        exit_p = float(row["exit_price"])
        qty = int(row["quantity"])
        entry_t = pd.Timestamp(row["entry_time"])
        exit_t = pd.Timestamp(row["exit_time"])

        # Engine's calculation
        engine_cb = calculate_transaction_costs(
            side=side,
            entry_price=entry_p,
            exit_price=exit_p,
            quantity=qty,
            entry_time=entry_t,
            exit_time=exit_t,
            cost_model=CostModelType.REALISTIC_INTRADAY,
            slippage_per_share=0.0,
        )

        # Independent manual calculation
        entry_turnover = entry_p * qty
        exit_turnover = exit_p * qty
        total_turnover = entry_turnover + exit_turnover

        # 1. Brokerage: min(20, 0.05% turnover) per leg
        calc_entry_brok = min(20.0, entry_turnover * 0.0005)
        calc_exit_brok = min(20.0, exit_turnover * 0.0005)
        calc_brok = calc_entry_brok + calc_exit_brok

        # 2. STT: 0.025% on sell leg only
        sell_turnover = exit_turnover if side == PositionSide.LONG else entry_turnover
        calc_stt = sell_turnover * 0.00025

        # 3. NSE turnover charges: 0.00297% total turnover
        calc_nse = total_turnover * 0.0000297

        # 4. SEBI turnover charges: 0.0001% total turnover
        calc_sebi = total_turnover * 0.000001

        # 5. Stamp duty: 0.003% on buy leg only
        buy_turnover = entry_turnover if side == PositionSide.LONG else exit_turnover
        calc_stamp = buy_turnover * 0.00003

        # 6. GST: 18% on (brokerage + NSE + SEBI)
        calc_gst = 0.18 * (calc_brok + calc_nse + calc_sebi)

        # 7. Slippage: 5 bps entry in morning (09:15-09:30), else 2 bps; 2 bps exit. Min 1 tick (Rs 0.05).
        is_morning = entry_t.time() <= dtime(9, 30)
        entry_slip_rate = 0.0005 if is_morning else 0.0002
        calc_entry_slip = max(entry_turnover * entry_slip_rate, 0.05 * qty)
        calc_exit_slip = max(exit_turnover * 0.0002, 0.05 * qty)
        calc_slip = calc_entry_slip + calc_exit_slip

        calc_statutory = calc_stt + calc_nse + calc_sebi + calc_stamp + calc_gst
        calc_total_cost = calc_brok + calc_statutory + calc_slip

        # Gross P&L
        calc_gross_pnl = (exit_p - entry_p) * qty if side == PositionSide.LONG else (entry_p - exit_p) * qty
        calc_net_pnl = calc_gross_pnl - calc_total_cost

        diff = abs(engine_cb.total_costs - calc_total_cost)
        status = "PASSED" if diff < 1e-4 else "FAILED"

        audit_rows.append({
            "scenario": name,
            "trade_id": int(row["trade_id"]),
            "side": side.value,
            "entry_time": str(entry_t),
            "exit_time": str(exit_t),
            "entry_price": entry_p,
            "exit_price": exit_p,
            "quantity": qty,
            "entry_turnover": round(entry_turnover, 2),
            "exit_turnover": round(exit_turnover, 2),
            "total_turnover": round(total_turnover, 2),
            "engine_brokerage": engine_cb.brokerage,
            "audit_brokerage": round(calc_brok, 4),
            "engine_stt": engine_cb.stt,
            "audit_stt": round(calc_stt, 4),
            "engine_exchange_charges": engine_cb.exchange_charges,
            "audit_exchange_charges": round(calc_nse, 4),
            "engine_sebi_charges": engine_cb.sebi_charges,
            "audit_sebi_charges": round(calc_sebi, 4),
            "engine_stamp_duty": engine_cb.stamp_duty,
            "audit_stamp_duty": round(calc_stamp, 4),
            "engine_gst": engine_cb.gst,
            "audit_gst": round(calc_gst, 4),
            "engine_slippage": engine_cb.slippage,
            "audit_slippage": round(calc_slip, 4),
            "engine_total_costs": engine_cb.total_costs,
            "audit_total_costs": round(calc_total_cost, 4),
            "audit_gross_pnl": round(calc_gross_pnl, 2),
            "audit_net_pnl": round(calc_net_pnl, 2),
            "cost_difference": round(diff, 6),
            "audit_status": status,
        })

    df_audit = pd.DataFrame(audit_rows)
    return df_audit


def decompose_gross_alpha(
    df_raw: pd.DataFrame,
    df_trades: pd.DataFrame,
    timeframe_data: dict[str, pd.DataFrame],
    cfg_strat: StrategyConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Decompose gross P&L (before transaction costs) across:
      1. Direction (LONG vs SHORT)
      2. Time of day
      3. Exit category
      4. Indicator signal conditions (EMA alignment, RSI, RVOL, ATR)
    """
    print("Computing Multi-Timeframe Signal Context for Gross Alpha Decomposition...")

    cursors = _make_cursors(timeframe_data, cfg_strat.use_rvol)

    # Pre-extract signal context at all timestamps
    ts_context: dict[pd.Timestamp, dict] = {}
    for ts in df_raw.index:
        s30 = cursors["30m"].update(ts)
        s15 = cursors["15m"].update(ts)
        s10 = cursors["10m"].update(ts)
        s5 = cursors["5m"].update(ts)
        if s30 is not None and s15 is not None and s10 is not None and s5 is not None:
            res = _generate_filtered_signal(states=(s30, s15, s10, s5), config=cfg_strat)
            ts_context[ts] = {
                "score": res.score,
                "confidence": res.confidence,
                "alignment": res.timeframe_alignment,
                "rsi_5m": s5.rsi,
                "rvol_5m": s5.rvol,
                "atr_5m": s5.atr,
                "ema20_5m": s5.ema20,
                "ema50_5m": s5.ema50,
                "ema_trend_5m": "BULL" if s5.ema20 > s5.ema50 else "BEAR",
            }

    # Enrich trade records with signal attributes
    enriched = []
    for _, r in df_trades.iterrows():
        entry_t = pd.Timestamp(r["entry_time"])
        # Signal timestamp is 1 minute before entry fill (or exact minute)
        sig_t = entry_t - timedelta(minutes=1)
        ctx = ts_context.get(sig_t, ts_context.get(entry_t, {}))

        d = r.to_dict()
        d["entry_time_dt"] = entry_t
        d["entry_hour"] = entry_t.hour
        d["entry_minute"] = entry_t.minute
        d["signal_score"] = ctx.get("score", np.nan)
        d["signal_confidence"] = ctx.get("confidence", np.nan)
        d["timeframe_alignment"] = ctx.get("alignment", np.nan)
        d["rsi_5m"] = ctx.get("rsi_5m", np.nan)
        d["rvol_5m"] = ctx.get("rvol_5m", np.nan)
        d["atr_5m"] = ctx.get("atr_5m", np.nan)
        d["ema_trend_5m"] = ctx.get("ema_trend_5m", "UNKNOWN")

        # Time of day segment
        t_time = entry_t.time()
        if t_time < dtime(10, 0):
            tod = "09:15–10:00 (Opening Session)"
        elif t_time < dtime(11, 0):
            tod = "10:00–11:00 (Morning Trend)"
        elif t_time < dtime(12, 0):
            tod = "11:00–12:00 (Pre-Midday)"
        elif t_time < dtime(13, 0):
            tod = "12:00–13:00 (Midday Consolidation)"
        elif t_time < dtime(14, 0):
            tod = "13:00–14:00 (Early Afternoon)"
        else:
            tod = "14:00–15:29 (Closing Session)"
        d["time_of_day_bucket"] = tod

        # Exit category cleanup
        exit_r = r["exit_reason"]
        is_gap = False
        if r["side"] == "LONG" and r["exit_price"] < r["initial_stop"]:
            is_gap = True
        elif r["side"] == "SHORT" and r["exit_price"] > r["initial_stop"]:
            is_gap = True
        d["exit_category"] = "GAP_THROUGH_STOP" if is_gap else exit_r

        # RSI conditions
        rsi = ctx.get("rsi_5m", np.nan)
        if pd.isna(rsi):
            rsi_b = "UNKNOWN"
        elif rsi >= 65:
            rsi_b = "RSI >= 65 (Strong Momentum)"
        elif rsi >= 60:
            rsi_b = "RSI 60–65 (Long Filter Baseline)"
        elif rsi <= 35:
            rsi_b = "RSI <= 35 (Oversold / Strong Short)"
        elif rsi <= 40:
            rsi_b = "RSI 35–40 (Short Momentum)"
        else:
            rsi_b = "RSI 40–60 (Neutral Range)"
        d["rsi_bucket"] = rsi_b

        # RVOL conditions
        rvol = ctx.get("rvol_5m", np.nan)
        if pd.isna(rvol):
            rvol_b = "UNKNOWN"
        elif rvol >= 2.5:
            rvol_b = "RVOL >= 2.5 (Surge Volume)"
        elif rvol >= 1.5:
            rvol_b = "RVOL 1.5–2.5 (Qualifying Volume)"
        else:
            rvol_b = "RVOL < 1.5 (Sub-threshold)"
        d["rvol_bucket"] = rvol_b

        # Timeframe alignment
        align = ctx.get("alignment", np.nan)
        if pd.isna(align):
            align_b = "UNKNOWN"
        elif align == 4:
            align_b = "4/4 Timeframes Aligned (Unanimous)"
        elif align == 3:
            align_b = "3/4 Timeframes Aligned (Majority)"
        else:
            align_b = f"{int(align)}/4 Timeframes Aligned"
        d["alignment_bucket"] = align_b

        enriched.append(d)

    df_enr = pd.DataFrame(enriched)

    # Segmentation helper
    def analyze_segment(df_sub: pd.DataFrame, seg_type: str, seg_name: str) -> dict:
        n = len(df_sub)
        if n == 0:
            return {
                "segment_type": seg_type,
                "segment_name": seg_name,
                "trade_count": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "gross_pnl": 0.0,
                "avg_gross_pnl_per_trade": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown_amount": 0.0,
            }

        wins = df_sub[df_sub["gross_pnl"] > 0]
        losses = df_sub[df_sub["gross_pnl"] < 0]
        win_rate = len(wins) / n * 100.0
        gross_pnl = df_sub["gross_pnl"].sum()
        avg_pnl = gross_pnl / n
        gp = wins["gross_pnl"].sum()
        gl = abs(losses["gross_pnl"].sum())
        pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
        avg_w = gp / len(wins) if len(wins) > 0 else 0.0
        avg_l = gl / len(losses) if len(losses) > 0 else 0.0

        # Running max drawdown of gross pnl
        cum_pnl = df_sub["gross_pnl"].cumsum()
        peak = cum_pnl.cummax()
        dd = (peak - cum_pnl).max()

        return {
            "segment_type": seg_type,
            "segment_name": seg_name,
            "trade_count": n,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "gross_pnl": round(gross_pnl, 2),
            "avg_gross_pnl_per_trade": round(avg_pnl, 2),
            "gross_profit": round(gp, 2),
            "gross_loss": round(gl, 2),
            "profit_factor": round(pf, 4) if np.isfinite(pf) else None,
            "avg_win": round(avg_w, 2),
            "avg_loss": round(avg_l, 2),
            "max_drawdown_amount": round(dd, 2) if not pd.isna(dd) else 0.0,
        }

    decomp_rows = []

    # 1. Total Strategy
    decomp_rows.append(analyze_segment(df_enr, "1. Overall Strategy", "All Trades (Gross Alpha Baseline)"))

    # 2. Direction
    for side in ("LONG", "SHORT"):
        sub = df_enr[df_enr["side"] == side]
        decomp_rows.append(analyze_segment(sub, "2. Direction", f"{side} Trades"))

    # 3. Time of Day
    for tod in sorted(df_enr["time_of_day_bucket"].unique()):
        sub = df_enr[df_enr["time_of_day_bucket"] == tod]
        decomp_rows.append(analyze_segment(sub, "3. Time of Day", tod))

    # 4. Exit Category
    for ec in sorted(df_enr["exit_category"].unique()):
        sub = df_enr[df_enr["exit_category"] == ec]
        decomp_rows.append(analyze_segment(sub, "4. Exit Category", f"Exit: {ec}"))

    # 5. Timeframe Alignment
    for al in sorted(df_enr["alignment_bucket"].unique()):
        sub = df_enr[df_enr["alignment_bucket"] == al]
        decomp_rows.append(analyze_segment(sub, "5. Timeframe Alignment", al))

    # 6. RSI Conditions
    for rsi_b in sorted(df_enr["rsi_bucket"].unique()):
        sub = df_enr[df_enr["rsi_bucket"] == rsi_b]
        decomp_rows.append(analyze_segment(sub, "6. 5m RSI Conditions", rsi_b))

    # 7. RVOL Conditions
    for rv_b in sorted(df_enr["rvol_bucket"].unique()):
        sub = df_enr[df_enr["rvol_bucket"] == rv_b]
        decomp_rows.append(analyze_segment(sub, "7. 5m RVOL Conditions", rv_b))

    df_decomp = pd.DataFrame(decomp_rows)
    return df_decomp, df_enr


def analyze_trading_frequency_and_turnover(
    df_raw: pd.DataFrame,
    partitions_data: dict[str, dict],
) -> pd.DataFrame:
    """
    Compute trading frequency, holding durations, notional turnover,
    and rapid re-entry / reversal dynamics across partitions and models.
    """
    print("Computing Trading Frequency and Turnover Dynamics...")

    rows = []

    for p_id, p_info in partitions_data.items():
        p_name = p_info["name"]
        p_slice = p_info["slice"]
        trading_days = len(set(p_slice.index.date))

        # 1. V1 Baseline
        df_v1 = pd.read_csv(p_info["v1_csv"])
        v1_n = len(df_v1)
        v1_entry_dt = pd.to_datetime(df_v1["entry_time"])
        v1_exit_dt = pd.to_datetime(df_v1["exit_time"])
        v1_holding_m = (v1_exit_dt - v1_entry_dt).dt.total_seconds() / 60.0
        v1_trades_by_day = v1_entry_dt.dt.date.value_counts()
        v1_buy_turn = (df_v1["entry_price"] * df_v1["quantity"]).sum()
        v1_sell_turn = (df_v1["exit_price"] * df_v1["quantity"]).sum()

        rows.append({
            "partition": p_name,
            "engine": "V1 Baseline",
            "cost_model": "1 bps flat",
            "trading_days": trading_days,
            "total_trades": v1_n,
            "avg_trades_per_day": round(v1_n / trading_days, 2),
            "max_trades_single_day": int(v1_trades_by_day.max()) if len(v1_trades_by_day) > 0 else 0,
            "avg_holding_duration_bars": round(v1_holding_m.mean(), 1),
            "median_holding_duration_bars": round(v1_holding_m.median(), 1),
            "avg_position_size_shares": round(df_v1["quantity"].mean(), 1),
            "avg_turnover_per_trade": round((v1_buy_turn + v1_sell_turn) / v1_n, 2) if v1_n > 0 else 0.0,
            "total_buy_turnover": round(v1_buy_turn, 2),
            "total_sell_turnover": round(v1_sell_turn, 2),
            "total_traded_notional": round(v1_buy_turn + v1_sell_turn, 2),
            "daily_breaker_activations": 0,
            "cooldown_activations": 0,
            "insufficient_capital_rejections": 0,
            "total_rejections": p_info.get("v1_rejections", 0),
            "rapid_reentry_count_under_15m": 0,
            "reversal_trade_count": 0,
        })

        # 2. V2 Baseline (1 bps)
        df_v2_b = pd.read_csv(p_info["v2_base_csv"])
        v2_b_n = len(df_v2_b)
        v2_b_entry_dt = pd.to_datetime(df_v2_b["entry_time"])
        v2_b_exit_dt = pd.to_datetime(df_v2_b["exit_time"])
        v2_b_holding_bars = df_v2_b["bars_held"]
        v2_b_trades_by_day = v2_b_entry_dt.dt.date.value_counts()
        v2_b_buy_turn = (df_v2_b["entry_price"] * df_v2_b["quantity"]).sum()
        v2_b_sell_turn = (df_v2_b["exit_price"] * df_v2_b["quantity"]).sum()

        # Rapid re-entry: time between previous exit and current entry < 15 minutes
        time_since_last_exit = (v2_b_entry_dt - v2_b_exit_dt.shift(1)).dt.total_seconds() / 60.0
        rapid_b = int(((time_since_last_exit >= 0) & (time_since_last_exit <= 15)).sum())

        rows.append({
            "partition": p_name,
            "engine": "V2 Risk Engine",
            "cost_model": "1 bps baseline",
            "trading_days": trading_days,
            "total_trades": v2_b_n,
            "avg_trades_per_day": round(v2_b_n / trading_days, 2),
            "max_trades_single_day": int(v2_b_trades_by_day.max()) if len(v2_b_trades_by_day) > 0 else 0,
            "avg_holding_duration_bars": round(v2_b_holding_bars.mean(), 1),
            "median_holding_duration_bars": round(v2_b_holding_bars.median(), 1),
            "avg_position_size_shares": round(df_v2_b["quantity"].mean(), 1),
            "avg_turnover_per_trade": round((v2_b_buy_turn + v2_b_sell_turn) / v2_b_n, 2) if v2_b_n > 0 else 0.0,
            "total_buy_turnover": round(v2_b_buy_turn, 2),
            "total_sell_turnover": round(v2_b_sell_turn, 2),
            "total_traded_notional": round(v2_b_buy_turn + v2_b_sell_turn, 2),
            "daily_breaker_activations": p_info["v2_base_metrics"]["daily_loss_limit_activations"],
            "cooldown_activations": p_info["v2_base_metrics"]["cooldown_activations"],
            "insufficient_capital_rejections": p_info["v2_base_metrics"].get("rejection_breakdown", {}).get("INSUFFICIENT_CAPITAL", 0),
            "total_rejections": p_info["v2_base_metrics"]["total_rejected_orders"],
            "rapid_reentry_count_under_15m": rapid_b,
            "reversal_trade_count": int((df_v2_b["exit_reason"] == "REVERSAL").sum()),
        })

        # 3. V2 Realistic Intraday Statutory Model
        df_v2_r = pd.read_csv(p_info["v2_real_csv"])
        v2_r_n = len(df_v2_r)
        v2_r_entry_dt = pd.to_datetime(df_v2_r["entry_time"])
        v2_r_exit_dt = pd.to_datetime(df_v2_r["exit_time"])
        v2_r_holding_bars = df_v2_r["bars_held"]
        v2_r_trades_by_day = v2_r_entry_dt.dt.date.value_counts()
        v2_r_buy_turn = (df_v2_r["entry_price"] * df_v2_r["quantity"]).sum()
        v2_r_sell_turn = (df_v2_r["exit_price"] * df_v2_r["quantity"]).sum()

        time_since_last_exit_r = (v2_r_entry_dt - v2_r_exit_dt.shift(1)).dt.total_seconds() / 60.0
        rapid_r = int(((time_since_last_exit_r >= 0) & (time_since_last_exit_r <= 15)).sum())

        rows.append({
            "partition": p_name,
            "engine": "V2 Risk Engine",
            "cost_model": "realistic_intraday statutory",
            "trading_days": trading_days,
            "total_trades": v2_r_n,
            "avg_trades_per_day": round(v2_r_n / trading_days, 2),
            "max_trades_single_day": int(v2_r_trades_by_day.max()) if len(v2_r_trades_by_day) > 0 else 0,
            "avg_holding_duration_bars": round(v2_r_holding_bars.mean(), 1),
            "median_holding_duration_bars": round(v2_r_holding_bars.median(), 1),
            "avg_position_size_shares": round(df_v2_r["quantity"].mean(), 1),
            "avg_turnover_per_trade": round((v2_r_buy_turn + v2_r_sell_turn) / v2_r_n, 2) if v2_r_n > 0 else 0.0,
            "total_buy_turnover": round(v2_r_buy_turn, 2),
            "total_sell_turnover": round(v2_r_sell_turn, 2),
            "total_traded_notional": round(v2_r_buy_turn + v2_r_sell_turn, 2),
            "daily_breaker_activations": p_info["v2_real_metrics"]["daily_loss_limit_activations"],
            "cooldown_activations": p_info["v2_real_metrics"]["cooldown_activations"],
            "insufficient_capital_rejections": p_info["v2_real_metrics"].get("rejection_breakdown", {}).get("INSUFFICIENT_CAPITAL", 0),
            "total_rejections": p_info["v2_real_metrics"]["total_rejected_orders"],
            "rapid_reentry_count_under_15m": rapid_r,
            "reversal_trade_count": int((df_v2_r["exit_reason"] == "REVERSAL").sum()),
        })

    return pd.DataFrame(rows)


def build_partition_diagnostic_summary(partitions_data: dict[str, dict]) -> pd.DataFrame:
    """
    Construct partition diagnostic summary table comparing V1 Baseline,
    V2 Baseline, and V2 Realistic across Training, Validation, and Holdout.
    """
    rows = []
    for p_id, p_info in partitions_data.items():
        p_name = p_info["name"]

        # V1
        v1_m = p_info["v1_metrics"]
        rows.append({
            "partition": p_name,
            "engine": "V1 Baseline",
            "cost_model": "1 bps flat",
            "total_trades": v1_m["total_trades"],
            "win_rate_pct": v1_m["win_rate_pct"],
            "gross_pnl": v1_m["gross_pnl"],
            "total_costs": v1_m["total_transaction_costs"],
            "net_pnl": v1_m["net_pnl"],
            "profit_factor": v1_m["profit_factor"],
            "max_drawdown_amount": v1_m["max_drawdown_amount"],
            "expectancy_per_trade": v1_m["expectancy_per_trade"],
            "stop_exits": v1_m["stop_loss_exits"],
            "target_exits": v1_m["target_exits"],
            "eod_exits": v1_m["eod_exits"],
            "breaker_activations": v1_m["daily_loss_limit_activations"],
            "insufficient_capital_rejections": 0,
        })

        # V2 Base
        v2_bm = p_info["v2_base_metrics"]
        rows.append({
            "partition": p_name,
            "engine": "V2 Risk Engine",
            "cost_model": "1 bps baseline",
            "total_trades": v2_bm["total_trades"],
            "win_rate_pct": v2_bm["win_rate_pct"],
            "gross_pnl": v2_bm["gross_pnl"],
            "total_costs": v2_bm["total_transaction_costs"],
            "net_pnl": v2_bm["net_pnl"],
            "profit_factor": v2_bm["profit_factor"],
            "max_drawdown_amount": v2_bm["max_drawdown_amount"],
            "expectancy_per_trade": v2_bm["expectancy_per_trade"],
            "stop_exits": v2_bm["stop_loss_exits"],
            "target_exits": v2_bm["target_exits"],
            "eod_exits": v2_bm["eod_exits"],
            "breaker_activations": v2_bm["daily_loss_limit_activations"],
            "insufficient_capital_rejections": v2_bm.get("rejection_breakdown", {}).get("INSUFFICIENT_CAPITAL", 0),
        })

        # V2 Real
        v2_rm = p_info["v2_real_metrics"]
        rows.append({
            "partition": p_name,
            "engine": "V2 Risk Engine",
            "cost_model": "realistic_intraday",
            "total_trades": v2_rm["total_trades"],
            "win_rate_pct": v2_rm["win_rate_pct"],
            "gross_pnl": v2_rm["gross_pnl"],
            "total_costs": v2_rm["total_transaction_costs"],
            "net_pnl": v2_rm["net_pnl"],
            "profit_factor": v2_rm["profit_factor"],
            "max_drawdown_amount": v2_rm["max_drawdown_amount"],
            "expectancy_per_trade": v2_rm["expectancy_per_trade"],
            "stop_exits": v2_rm["stop_loss_exits"],
            "target_exits": v2_rm["target_exits"],
            "eod_exits": v2_rm["eod_exits"],
            "breaker_activations": v2_rm["daily_loss_limit_activations"],
            "insufficient_capital_rejections": v2_rm.get("rejection_breakdown", {}).get("INSUFFICIENT_CAPITAL", 0),
        })

    return pd.DataFrame(rows)


def main():
    verify_preflight()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ADANIPORTS historical dataset...")
    df_raw = pd.read_csv(DATA_PATH, parse_dates=["timestamp"]).set_index("timestamp").sort_index()

    cfg_strat = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        minimum_long_rsi=60.0,
        use_rvol=True,
    )

    print("Calculating multi-timeframe indicators across full historical data...")
    t0 = time.time()
    timeframe_data = calculate_timeframe_indicators(df_raw, cfg_strat)
    print(f"Timeframe indicators ready in {time.time() - t0:.2f}s.")

    # Load Phase 24G.13 evaluation results and metrics
    eval_dir = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G13_v2_controlled_evaluation"
    with open(eval_dir / "phase24G13_metrics.json", "r", encoding="utf-8") as f:
        metrics_json = json.load(f)["metrics"]

    metrics_map = {}
    for m in metrics_json:
        key = (m["engine"], m["cost_model"], m["partition"])
        metrics_map[key] = m

    partitions_data = {
        "training_2017_2018": {
            "name": "Training (2017–2018)",
            "slice": df_raw["2017-01-02 09:15:00":"2018-12-31 15:29:00"],
            "v1_csv": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_training_2017_2018.csv",
            "v1_metrics": metrics_map[("V1", "historical_baseline (1 bps)", "Training (2017–2018)")],
            "v2_base_csv": eval_dir / "trades_v2_baseline_training_2017_2018.csv",
            "v2_base_metrics": metrics_map[("V2", "historical_baseline (1 bps)", "Training (2017–2018)")],
            "v2_real_csv": eval_dir / "trades_v2_realistic_training_2017_2018.csv",
            "v2_real_metrics": metrics_map[("V2", "realistic_intraday (Indian statutory)", "Training (2017–2018)")],
        },
        "validation_2019": {
            "name": "Validation (2019)",
            "slice": df_raw["2019-01-01 09:15:00":"2019-12-31 15:29:00"],
            "v1_csv": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_validation_2019.csv",
            "v1_metrics": metrics_map[("V1", "historical_baseline (1 bps)", "Validation (2019)")],
            "v2_base_csv": eval_dir / "trades_v2_baseline_validation_2019.csv",
            "v2_base_metrics": metrics_map[("V2", "historical_baseline (1 bps)", "Validation (2019)")],
            "v2_real_csv": eval_dir / "trades_v2_realistic_validation_2019.csv",
            "v2_real_metrics": metrics_map[("V2", "realistic_intraday (Indian statutory)", "Validation (2019)")],
        },
        "holdout_2020": {
            "name": "Holdout Test (2020)",
            "slice": df_raw["2020-01-01 09:15:00":"2020-12-31 15:29:00"],
            "v1_csv": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_holdout_2020.csv",
            "v1_metrics": metrics_map[("V1", "historical_baseline (1 bps)", "Holdout Test (2020)")],
            "v2_base_csv": eval_dir / "trades_v2_baseline_holdout_2020.csv",
            "v2_base_metrics": metrics_map[("V2", "historical_baseline (1 bps)", "Holdout Test (2020)")],
            "v2_real_csv": eval_dir / "trades_v2_realistic_holdout_2020.csv",
            "v2_real_metrics": metrics_map[("V2", "realistic_intraday (Indian statutory)", "Holdout Test (2020)")],
        },
        "combined_2017_2020": {
            "name": "Combined Period (2017–2020)",
            "slice": df_raw["2017-01-02 09:15:00":"2020-12-31 15:29:00"],
            "v1_csv": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_combined_2017_2020.csv",
            "v1_metrics": metrics_map[("V1", "historical_baseline (1 bps)", "Combined Period (2017–2020 Descriptive Summary)")],
            "v2_base_csv": eval_dir / "trades_v2_baseline_combined_2017_2020.csv",
            "v2_base_metrics": metrics_map[("V2", "historical_baseline (1 bps)", "Combined Period (2017–2020 Descriptive Summary)")],
            "v2_real_csv": eval_dir / "trades_v2_realistic_combined_2017_2020.csv",
            "v2_real_metrics": metrics_map[("V2", "realistic_intraday (Indian statutory)", "Combined Period (2017–2020 Descriptive Summary)")],
        },
    }

    # 1. Independent Cost Model Audit
    df_trades_combined = pd.read_csv(eval_dir / "trades_v2_baseline_combined_2017_2020.csv")
    df_audit = audit_cost_model_scenarios(df_trades_combined)
    audit_csv_path = OUT_DIR / "cost_model_independent_audit.csv"
    df_audit.to_csv(audit_csv_path, index=False)
    print(f"Saved {audit_csv_path.name} (SHA-256: {hashlib.sha256(audit_csv_path.read_bytes()).hexdigest()[:16]}...)")

    # 2. Gross Alpha Decomposition
    df_decomp, df_enr = decompose_gross_alpha(df_raw, df_trades_combined, timeframe_data, cfg_strat)
    decomp_csv_path = OUT_DIR / "gross_alpha_decomposition.csv"
    df_decomp.to_csv(decomp_csv_path, index=False)
    print(f"Saved {decomp_csv_path.name} (SHA-256: {hashlib.sha256(decomp_csv_path.read_bytes()).hexdigest()[:16]}...)")

    # 3. Trading Frequency & Turnover Dynamics
    df_freq = analyze_trading_frequency_and_turnover(df_raw, partitions_data)
    freq_csv_path = OUT_DIR / "trade_frequency_turnover_analysis.csv"
    df_freq.to_csv(freq_csv_path, index=False)
    print(f"Saved {freq_csv_path.name} (SHA-256: {hashlib.sha256(freq_csv_path.read_bytes()).hexdigest()[:16]}...)")

    # 4. Partition Diagnostic Summary
    df_part = build_partition_diagnostic_summary(partitions_data)
    part_csv_path = OUT_DIR / "partition_diagnostic_summary.csv"
    df_part.to_csv(part_csv_path, index=False)
    print(f"Saved {part_csv_path.name} (SHA-256: {hashlib.sha256(part_csv_path.read_bytes()).hexdigest()[:16]}...)")

    # Save summary hashes
    summary_hashes = {
        "cost_model_independent_audit.csv": hashlib.sha256(audit_csv_path.read_bytes()).hexdigest(),
        "gross_alpha_decomposition.csv": hashlib.sha256(decomp_csv_path.read_bytes()).hexdigest(),
        "trade_frequency_turnover_analysis.csv": hashlib.sha256(freq_csv_path.read_bytes()).hexdigest(),
        "partition_diagnostic_summary.csv": hashlib.sha256(part_csv_path.read_bytes()).hexdigest(),
    }
    with open(OUT_DIR / "reproducibility_hashes.json", "w", encoding="utf-8") as f:
        json.dump(summary_hashes, f, indent=2)

    print("\n" + "=" * 80)
    print("PHASE 24G.14 INVESTIGATION CALCULATIONS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

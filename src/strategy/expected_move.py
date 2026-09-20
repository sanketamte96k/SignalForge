"""
SignalForge — Phase 7: Expected Move & Forward Excursion Engine
===============================================================
File: src/strategy/expected_move.py

Calculates risk geometry (Entry, Stop, Target, Risk, Reward, R:R)
and computes historical forward excursion profiles (MFE/MAE) for research.

IMPORTANT:
Forward MFE, MAE, and horizon returns are computed STRICTLY for research
and evaluation. They are NEVER used to generate signals at timestamp T.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd


@dataclass
class StructuralSetupCandidate:
    symbol: str
    datetime: pd.Timestamp
    bar_index: int
    setup_type: str        # BREAKOUT_RETEST, TREND_PULLBACK, RANGE_REVERSAL, FAILED_BREAKOUT, MOMENTUM_EXPANSION
    direction: str         # LONG or SHORT
    entry_price: float
    stop_price: float
    target_price: float
    risk_distance: float
    reward_distance: float
    reward_risk_ratio: float
    atr: float
    context: Dict[str, Any] = field(default_factory=dict)

    # Research-only forward evaluation metrics (isolated from decision logic)
    forward_mfe: Dict[str, float] = field(default_factory=dict)
    forward_mae: Dict[str, float] = field(default_factory=dict)
    forward_returns: Dict[str, float] = field(default_factory=dict)
    exit_datetime: Optional[pd.Timestamp] = None
    exit_price: float = 0.0
    exit_reason: str = "PENDING"  # TARGET, STOP, EOD
    gross_pnl: float = 0.0
    costs: float = 0.0
    net_pnl: float = 0.0
    holding_minutes: int = 0


def detect_structural_setups(df_struct: pd.DataFrame, symbol: str) -> List[StructuralSetupCandidate]:
    """
    Detects the 5 independent candidate structural events:
    A. BREAKOUT + RETEST
    B. TREND PULLBACK
    C. RANGE REVERSAL
    D. FAILED BREAKOUT REVERSAL
    E. MOMENTUM EXPANSION AFTER COMPRESSION
    """
    candidates: List[StructuralSetupCandidate] = []
    n = len(df_struct)
    if n < 50:
        return candidates

    close = df_struct["Close"].to_numpy()
    high = df_struct["High"].to_numpy()
    low = df_struct["Low"].to_numpy()
    open_p = df_struct["Open"].to_numpy()
    atr = df_struct["atr14_1m"].to_numpy()
    dts = df_struct.index

    st_type = df_struct["structure_type"].to_numpy()
    st_dir = df_struct["structure_direction"].to_numpy()
    st_strength = df_struct["structure_strength"].to_numpy()
    st_age = df_struct["structure_age"].to_numpy()
    comp = df_struct["range_compression"].to_numpy()

    t_dir_1m = df_struct["trend_dir_1m"].to_numpy()
    t_dir_5m = df_struct["trend_dir_5m"].to_numpy()
    t_dir_15m = df_struct["trend_dir_15m"].to_numpy()
    t_dir_30m = df_struct["trend_dir_30m"].to_numpy()

    dist_sup = df_struct["dist_to_support_atr"].to_numpy()
    dist_res = df_struct["dist_to_resistance_atr"].to_numpy()
    dist_mid = df_struct["dist_to_midpoint_atr"].to_numpy()
    r_high = df_struct["range_high"].to_numpy()
    r_low = df_struct["range_low"].to_numpy()

    ema21 = df_struct["ema21_1m"].to_numpy()
    ema50 = df_struct["ema50_1m"].to_numpy()

    for i in range(25, n - 65):  # Leave room for causal lookahead isolation
        c = close[i]
        h = high[i]
        l = low[i]
        o = open_p[i]
        a = max(atr[i], 0.1)

        # Context dict at bar i
        ctx = {
            "trend_dir_1m": int(t_dir_1m[i]),
            "trend_dir_5m": int(t_dir_5m[i]),
            "trend_dir_15m": int(t_dir_15m[i]),
            "trend_dir_30m": int(t_dir_30m[i]),
            "dist_to_support_atr": float(dist_sup[i]),
            "dist_to_resistance_atr": float(dist_res[i]),
            "dist_to_midpoint_atr": float(dist_mid[i]),
            "range_compression": float(comp[i]),
            "structure_type": str(st_type[i]),
            "structure_strength": float(st_strength[i]),
            "structure_age": int(st_age[i]),
            "candle_body_ratio": float(abs(c - o) / max(h - l, 1e-4)),
            "atr_ratio": float(df_struct["atr_ratio_1m"].iloc[i]),
        }

        # A. BREAKOUT + RETEST
        if st_type[i] == "BREAKOUT_RETEST_BULLISH":
            risk = 1.2 * a
            reward = 1.8 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="BREAKOUT_RETEST", direction="LONG",
                entry_price=round(float(c), 2),
                stop_price=round(float(c - risk), 2),
                target_price=round(float(c + reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))
        elif st_type[i] == "BREAKOUT_RETEST_BEARISH":
            risk = 1.2 * a
            reward = 1.8 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="BREAKOUT_RETEST", direction="SHORT",
                entry_price=round(float(c), 2),
                stop_price=round(float(c + risk), 2),
                target_price=round(float(c - reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))

        # B. TREND PULLBACK
        # 1m and 5m in strong trend; price retraces to EMA21 and prints continuation
        elif t_dir_1m[i] == 1 and t_dir_5m[i] == 1:
            if abs(l - ema21[i]) <= 0.3 * a and c > o and c > ema21[i]:
                risk = 1.25 * a
                reward = 1.875 * risk
                candidates.append(StructuralSetupCandidate(
                    symbol=symbol, datetime=dts[i], bar_index=i,
                    setup_type="TREND_PULLBACK", direction="LONG",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(c - risk), 2),
                    target_price=round(float(c + reward), 2),
                    risk_distance=round(float(risk), 2),
                    reward_distance=round(float(reward), 2),
                    reward_risk_ratio=round(float(reward / risk), 2),
                    atr=round(float(a), 2), context=ctx
                ))
        elif t_dir_1m[i] == -1 and t_dir_5m[i] == -1:
            if abs(h - ema21[i]) <= 0.3 * a and c < o and c < ema21[i]:
                risk = 1.25 * a
                reward = 1.875 * risk
                candidates.append(StructuralSetupCandidate(
                    symbol=symbol, datetime=dts[i], bar_index=i,
                    setup_type="TREND_PULLBACK", direction="SHORT",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(c + risk), 2),
                    target_price=round(float(c - reward), 2),
                    risk_distance=round(float(risk), 2),
                    reward_distance=round(float(reward), 2),
                    reward_risk_ratio=round(float(reward / risk), 2),
                    atr=round(float(a), 2), context=ctx
                ))

        # C. RANGE REVERSAL
        elif st_type[i] == "RANGE_REVERSAL_BULLISH":
            risk = 1.0 * a
            reward = 1.5 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="RANGE_REVERSAL", direction="LONG",
                entry_price=round(float(c), 2),
                stop_price=round(float(c - risk), 2),
                target_price=round(float(c + reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))
        elif st_type[i] == "RANGE_REVERSAL_BEARISH":
            risk = 1.0 * a
            reward = 1.5 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="RANGE_REVERSAL", direction="SHORT",
                entry_price=round(float(c), 2),
                stop_price=round(float(c + risk), 2),
                target_price=round(float(c - reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))

        # D. FAILED BREAKOUT REVERSAL (Liquidity Sweep)
        elif st_type[i] == "FAILED_BREAKOUT_BULLISH":
            risk = 1.2 * a
            reward = 1.8 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="FAILED_BREAKOUT", direction="LONG",
                entry_price=round(float(c), 2),
                stop_price=round(float(c - risk), 2),
                target_price=round(float(c + reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))
        elif st_type[i] == "FAILED_BREAKOUT_BEARISH":
            risk = 1.2 * a
            reward = 1.8 * risk
            candidates.append(StructuralSetupCandidate(
                symbol=symbol, datetime=dts[i], bar_index=i,
                setup_type="FAILED_BREAKOUT", direction="SHORT",
                entry_price=round(float(c), 2),
                stop_price=round(float(c + risk), 2),
                target_price=round(float(c - reward), 2),
                risk_distance=round(float(risk), 2),
                reward_distance=round(float(reward), 2),
                reward_risk_ratio=round(float(reward / risk), 2),
                atr=round(float(a), 2), context=ctx
            ))

        # E. MOMENTUM EXPANSION AFTER COMPRESSION
        elif comp[i] < 1.05 and (h - l) >= 1.2 * a and abs(c - o) >= 0.65 * (h - l):
            if c > o and c > r_high[i]:
                risk = 1.2 * a
                reward = 1.8 * risk
                candidates.append(StructuralSetupCandidate(
                    symbol=symbol, datetime=dts[i], bar_index=i,
                    setup_type="MOMENTUM_EXPANSION", direction="LONG",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(c - risk), 2),
                    target_price=round(float(c + reward), 2),
                    risk_distance=round(float(risk), 2),
                    reward_distance=round(float(reward), 2),
                    reward_risk_ratio=round(float(reward / risk), 2),
                    atr=round(float(a), 2), context=ctx
                ))
            elif c < o and c < r_low[i]:
                risk = 1.2 * a
                reward = 1.8 * risk
                candidates.append(StructuralSetupCandidate(
                    symbol=symbol, datetime=dts[i], bar_index=i,
                    setup_type="MOMENTUM_EXPANSION", direction="SHORT",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(c + risk), 2),
                    target_price=round(float(c - reward), 2),
                    risk_distance=round(float(risk), 2),
                    reward_distance=round(float(reward), 2),
                    reward_risk_ratio=round(float(reward / risk), 2),
                    atr=round(float(a), 2), context=ctx
                ))

    return candidates


def compute_forward_excursions(
    candidates: List[StructuralSetupCandidate],
    df: pd.DataFrame,
    cost_multiplier: float = 1.0,
    fixed_capital_risk: float = 1000.0
) -> None:
    """
    Computes forward MFE and MAE across 5m, 10m, 15m, 30m, and 60m windows.
    Also executes forward trade simulation with target, stop, or 15:15 EOD exit.
    
    STRICT RESEARCH PURPOSE: Modifies candidate attributes for analysis only.
    """
    n = len(df)
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    close = df["Close"].to_numpy()
    dts = df.index
    horizons = [5, 10, 15, 30, 60]

    for cand in candidates:
        idx = cand.bar_index
        entry = cand.entry_price
        direction = cand.direction
        atr = cand.atr
        stop = cand.stop_price
        target = cand.target_price

        # 1. Forward MFE / MAE / Returns
        for h in horizons:
            end_h = min(idx + 1 + h, n)
            if end_h <= idx + 1:
                continue

            sub_h = high[idx + 1 : end_h]
            sub_l = low[idx + 1 : end_h]
            end_c = close[min(idx + h, n - 1)]

            if direction == "LONG":
                mfe_val = float(np.max(sub_h) - entry)
                mae_val = float(entry - np.min(sub_l))
                ret_val = float((end_c - entry) / entry) * 100.0
            else:  # SHORT
                mfe_val = float(entry - np.min(sub_l))
                mae_val = float(np.max(sub_h) - entry)
                ret_val = float((entry - end_c) / entry) * 100.0

            cand.forward_mfe[f"{h}m"] = round(mfe_val / atr, 2)
            cand.forward_mae[f"{h}m"] = round(mae_val / atr, 2)
            cand.forward_returns[f"{h}m"] = round(ret_val, 3)

        # 2. Forward Trade Simulation (until Target, Stop, or EOD 15:15)
        # Sizing: risk fixed_capital_risk
        risk_per_share = max(cand.risk_distance, 0.5)
        qty = max(int(fixed_capital_risk / risk_per_share), 1)

        exit_dt = dts[-1]
        exit_p = close[-1]
        exit_reason = "EOD"
        hold_mins = 0

        curr_day = dts[idx].date()

        for j in range(idx + 1, n):
            bar_dt = dts[j]
            # Enforce Intraday EOD cut-off at 15:15 or session change
            if bar_dt.date() != curr_day or bar_dt.time() >= pd.Timestamp("15:15:00").time():
                exit_dt = bar_dt
                exit_p = close[j]
                exit_reason = "EOD"
                hold_mins = j - idx
                break

            bar_h = high[j]
            bar_l = low[j]

            if direction == "LONG":
                if bar_l <= stop:
                    exit_dt = bar_dt
                    exit_p = stop
                    exit_reason = "STOP"
                    hold_mins = j - idx
                    break
                elif bar_h >= target:
                    exit_dt = bar_dt
                    exit_p = target
                    exit_reason = "TARGET"
                    hold_mins = j - idx
                    break
            else:  # SHORT
                if bar_h >= stop:
                    exit_dt = bar_dt
                    exit_p = stop
                    exit_reason = "STOP"
                    hold_mins = j - idx
                    break
                elif bar_l <= target:
                    exit_dt = bar_dt
                    exit_p = target
                    exit_reason = "TARGET"
                    hold_mins = j - idx
                    break

        if direction == "LONG":
            gross = (exit_p - entry) * qty
        else:
            gross = (entry - exit_p) * qty

        turnover = (entry + exit_p) * qty
        # Brokerage: Rs. 20 flat + 0.05% turnover
        base_costs = 20.0 + (turnover * 0.0005)
        tot_costs = base_costs * cost_multiplier
        net = gross - tot_costs

        cand.exit_datetime = exit_dt
        cand.exit_price = round(float(exit_p), 2)
        cand.exit_reason = exit_reason
        cand.gross_pnl = round(float(gross), 2)
        cand.costs = round(float(tot_costs), 2)
        cand.net_pnl = round(float(net), 2)
        cand.holding_minutes = hold_mins

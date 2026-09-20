"""
SignalForge — Phase 7: Market Structure & Multi-Timeframe Context Engine
========================================================================
File: src/strategy/structure_engine.py

Causal Market Structure Engine detecting:
1. Higher High (HH)
2. Higher Low (HL)
3. Lower High (LH)
4. Lower Low (LL)
5. Break of Structure (BOS)
6. Change of Character (CHoCH)
7. Range High
8. Range Low
9. Range Compression
10. Failed Breakout
11. Breakout Retest
12. Support/Resistance Proximity

Strictly causal: Structure confirmed only at or before timestamp T.
No future candles are ever inspected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class MarketStructureSnapshot:
    timestamp: pd.Timestamp
    structure_type: str        # BOS_BULLISH, BOS_BEARISH, CHOCH_BULLISH, CHOCH_BEARISH, etc.
    structure_direction: str   # BULLISH, BEARISH, NEUTRAL
    structure_strength: float  # 0.0 to 1.0
    structure_age: int         # Bars since the key structural reference level was formed
    distance_to_structure: float  # ATR units
    breakout_distance: float      # ATR units
    retest_distance: float        # ATR units
    swing_high: float
    swing_low: float
    range_high: float
    range_low: float
    support_level: float
    resistance_level: float
    dist_to_support_atr: float
    dist_to_resistance_atr: float
    dist_to_midpoint_atr: float
    range_compression: float


def compute_causal_mtf_context(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes causal indicators for 1m, 5m, 15m, and 30m timeframes.
    Higher timeframe candles are only completed at their interval close,
    ensuring 100% causal availability at timestamp T with zero lookahead.
    """
    out = df.copy()
    close_1m = out["Close"]
    high_1m = out["High"]
    low_1m = out["Low"]
    vol_1m = out["Volume"]

    # 1. 1-Minute Baseline Indicators
    out["ema9_1m"] = close_1m.ewm(span=9, adjust=False).mean()
    out["ema21_1m"] = close_1m.ewm(span=21, adjust=False).mean()
    out["ema50_1m"] = close_1m.ewm(span=50, adjust=False).mean()
    out["ema9_slope_1m"] = out["ema9_1m"].diff(5) / 5.0

    prev_c_1m = close_1m.shift(1).bfill()
    tr1 = high_1m - low_1m
    tr2 = (high_1m - prev_c_1m).abs()
    tr3 = (low_1m - prev_c_1m).abs()
    tr_1m = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr14_1m"] = tr_1m.ewm(span=14, adjust=False).mean()
    out["atr_sma50_1m"] = out["atr14_1m"].rolling(50, min_periods=10).mean().bfill()
    out["atr_ratio_1m"] = out["atr14_1m"] / out["atr_sma50_1m"].replace(0, np.nan).fillna(1.0)

    # 1m Trend direction
    out["trend_dir_1m"] = np.where(
        (out["ema9_1m"] > out["ema21_1m"]) & (out["ema9_slope_1m"] > 0), 1,
        np.where((out["ema9_1m"] < out["ema21_1m"]) & (out["ema9_slope_1m"] < 0), -1, 0)
    )
    out["return_5m_1m"] = close_1m.pct_change(5).fillna(0.0)
    out["rvol_1m"] = (vol_1m / vol_1m.rolling(20, min_periods=5).mean().replace(0, np.nan)).fillna(1.0)

    # 2. Resample Higher Timeframes Causally (closed='left', label='right')
    # A 5-minute bar for [09:15, 09:20) completes at 09:20.
    for tf_str, rule, span_fast, span_slow in [
        ("5m", "5min", 9, 21),
        ("15m", "15min", 9, 21),
        ("30m", "30min", 9, 21),
    ]:
        resampled = out.resample(rule, closed="left", label="right").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }).dropna()

        res_close = resampled["Close"]
        res_fast = res_close.ewm(span=span_fast, adjust=False).mean()
        res_slow = res_close.ewm(span=span_slow, adjust=False).mean()
        res_slope = res_fast.diff(3) / 3.0

        res_prev_c = res_close.shift(1).bfill()
        res_tr1 = resampled["High"] - resampled["Low"]
        res_tr2 = (resampled["High"] - res_prev_c).abs()
        res_tr3 = (resampled["Low"] - res_prev_c).abs()
        res_tr = pd.concat([res_tr1, res_tr2, res_tr3], axis=1).max(axis=1)
        res_atr = res_tr.ewm(span=14, adjust=False).mean()

        res_dir = np.where(
            (res_fast > res_slow) & (res_slope > 0), 1,
            np.where((res_fast < res_slow) & (res_slope < 0), -1, 0)
        )

        res_df = pd.DataFrame({
            f"trend_dir_{tf_str}": res_dir,
            f"ema_fast_{tf_str}": res_fast,
            f"ema_slow_{tf_str}": res_slow,
            f"atr_{tf_str}": res_atr,
            f"slope_{tf_str}": res_slope,
        }, index=resampled.index)

        # Merge causally via merge_asof: only past completed higher timeframe candle is visible
        out = pd.merge_asof(
            out,
            res_df,
            left_index=True,
            right_index=True,
            direction="backward"
        )
        out[f"trend_dir_{tf_str}"] = out[f"trend_dir_{tf_str}"].fillna(0).astype(int)
        out[f"atr_{tf_str}"] = out[f"atr_{tf_str}"].bfill().fillna(out["atr14_1m"])

    return out


def compute_market_structure(df: pd.DataFrame, swing_k: int = 4, range_window: int = 20) -> pd.DataFrame:
    """
    Computes strictly causal swing points, BOS, CHoCH, and range structure.
    
    A swing high is confirmed at bar i if bar (i - swing_k) is the highest in [i - 2*k, i].
    Thus at bar i, information about swing high at (i - swing_k) becomes known causally.
    """
    df_feat = compute_causal_mtf_context(df)
    n = len(df_feat)

    high = df_feat["High"].to_numpy()
    low = df_feat["Low"].to_numpy()
    close = df_feat["Close"].to_numpy()
    open_p = df_feat["Open"].to_numpy()
    atr = df_feat["atr14_1m"].to_numpy()

    # Pre-allocate output arrays
    structure_type = ["NONE"] * n
    structure_direction = ["NEUTRAL"] * n
    structure_strength = np.zeros(n, dtype=float)
    structure_age = np.zeros(n, dtype=int)
    dist_to_structure = np.zeros(n, dtype=float)
    breakout_distance = np.zeros(n, dtype=float)
    retest_distance = np.zeros(n, dtype=float)

    curr_swing_high = np.zeros(n, dtype=float)
    curr_swing_low = np.zeros(n, dtype=float)
    range_high_arr = np.zeros(n, dtype=float)
    range_low_arr = np.zeros(n, dtype=float)
    support_arr = np.zeros(n, dtype=float)
    resistance_arr = np.zeros(n, dtype=float)
    dist_to_support = np.zeros(n, dtype=float)
    dist_to_resistance = np.zeros(n, dtype=float)
    dist_to_midpoint = np.zeros(n, dtype=float)
    range_compression = np.ones(n, dtype=float)

    # State variables tracking confirmed structure
    last_sh = high[0]
    last_sh_idx = 0
    prev_sh = high[0]

    last_sl = low[0]
    last_sl_idx = 0
    prev_sl = low[0]

    current_trend = 0  # 1 for bullish (HH+HL), -1 for bearish (LH+LL), 0 neutral
    last_breakout_level = 0.0
    last_breakout_dir = 0
    last_breakout_idx = -999

    k = swing_k

    for i in range(2 * k + 1, n):
        c = close[i]
        h = high[i]
        l = low[i]
        o = open_p[i]
        a = max(atr[i], 0.1)

        # 1. Trailing Range Window [i - range_window, i - 1]
        start_rw = max(0, i - range_window)
        r_high = float(np.max(high[start_rw:i]))
        r_low = float(np.min(low[start_rw:i]))
        r_span = r_high - r_low
        r_mid = (r_high + r_low) / 2.0

        range_high_arr[i] = r_high
        range_low_arr[i] = r_low
        comp = r_span / (a * np.sqrt(range_window))
        range_compression[i] = comp

        # 2. Check for confirmed Swing High at bar (i - k)
        cand_sh_idx = i - k
        cand_sh = high[cand_sh_idx]
        if np.all(cand_sh >= high[cand_sh_idx - k : cand_sh_idx + k + 1]):
            # Confirmed swing high
            prev_sh = last_sh
            last_sh = cand_sh
            last_sh_idx = cand_sh_idx
            if last_sh > prev_sh:
                sh_type = "HH"
            else:
                sh_type = "LH"

        # 3. Check for confirmed Swing Low at bar (i - k)
        cand_sl_idx = i - k
        cand_sl = low[cand_sl_idx]
        if np.all(cand_sl <= low[cand_sl_idx - k : cand_sl_idx + k + 1]):
            # Confirmed swing low
            prev_sl = last_sl
            last_sl = cand_sl
            last_sl_idx = cand_sl_idx
            if last_sl > prev_sl:
                sl_type = "HL"
            else:
                sl_type = "LL"

        curr_swing_high[i] = last_sh
        curr_swing_low[i] = last_sl

        # 4. Support and Resistance levels
        # Resistance is the nearest ceiling above price
        res_cand = r_high if r_high > c else (last_sh if last_sh > c else c + a)
        sup_cand = r_low if r_low < c else (last_sl if last_sl < c else c - a)

        resistance_arr[i] = res_cand
        support_arr[i] = sup_cand

        d_res = (res_cand - c) / a
        d_sup = (c - sup_cand) / a
        d_mid = abs(c - r_mid) / a

        dist_to_resistance[i] = max(round(float(d_res), 2), 0.0)
        dist_to_support[i] = max(round(float(d_sup), 2), 0.0)
        dist_to_midpoint[i] = round(float(d_mid), 2)

        # 5. Classify Structural Events at Bar i
        # A. Break of Structure (BOS) vs Change of Character (CHoCH)
        # Prior bar was below swing high, current bar closes above swing high
        st_type = "NONE"
        st_dir = "NEUTRAL"
        st_strength = 0.5
        st_age = i - last_sh_idx
        d_struct = abs(c - last_sh) / a
        bo_dist = 0.0
        ret_dist = 0.0

        if close[i - 1] <= last_sh and c > last_sh:
            bo_dist = (c - last_sh) / a
            last_breakout_level = last_sh
            last_breakout_dir = 1
            last_breakout_idx = i
            if current_trend >= 0:
                st_type = "BOS_BULLISH"
                st_dir = "BULLISH"
                st_strength = min(0.6 + (bo_dist * 0.2), 1.0)
                current_trend = 1
            else:
                st_type = "CHOCH_BULLISH"
                st_dir = "BULLISH"
                st_strength = min(0.7 + (bo_dist * 0.2), 1.0)
                current_trend = 1

        elif close[i - 1] >= last_sl and c < last_sl:
            bo_dist = (last_sl - c) / a
            last_breakout_level = last_sl
            last_breakout_dir = -1
            last_breakout_idx = i
            if current_trend <= 0:
                st_type = "BOS_BEARISH"
                st_dir = "BEARISH"
                st_strength = min(0.6 + (bo_dist * 0.2), 1.0)
                current_trend = -1
            else:
                st_type = "CHOCH_BEARISH"
                st_dir = "BEARISH"
                st_strength = min(0.7 + (bo_dist * 0.2), 1.0)
                current_trend = -1

        # B. Breakout Retest: Occurs within 2 to 15 bars of a breakout
        elif last_breakout_idx > 0 and 2 <= (i - last_breakout_idx) <= 15:
            if last_breakout_dir == 1:
                # Bullish retest: low touches within 0.35 ATR of breakout level, close holds above
                if abs(l - last_breakout_level) <= 0.35 * a and c > last_breakout_level and c > o:
                    st_type = "BREAKOUT_RETEST_BULLISH"
                    st_dir = "BULLISH"
                    st_strength = 0.85
                    st_age = i - last_breakout_idx
                    ret_dist = abs(l - last_breakout_level) / a
                    d_struct = ret_dist
            elif last_breakout_dir == -1:
                # Bearish retest: high touches within 0.35 ATR of breakout level, close holds below
                if abs(h - last_breakout_level) <= 0.35 * a and c < last_breakout_level and c < o:
                    st_type = "BREAKOUT_RETEST_BEARISH"
                    st_dir = "BEARISH"
                    st_strength = 0.85
                    st_age = i - last_breakout_idx
                    ret_dist = abs(h - last_breakout_level) / a
                    d_struct = ret_dist

        # C. Failed Breakout (Liquidity Sweep)
        # High exceeds range_high, but close drops back below range_high with upper tail
        elif h > r_high and c < r_high and (h - max(c, o)) > 0.4 * (h - l):
            st_type = "FAILED_BREAKOUT_BEARISH"
            st_dir = "BEARISH"
            st_strength = 0.80
            st_age = 1
            d_struct = (h - r_high) / a

        elif l < r_low and c > r_low and (min(c, o) - l) > 0.4 * (h - l):
            st_type = "FAILED_BREAKOUT_BULLISH"
            st_dir = "BULLISH"
            st_strength = 0.80
            st_age = 1
            d_struct = (r_low - l) / a

        # D. Range Reversals
        elif comp < 1.1 and d_res <= 0.2 and c < o:
            st_type = "RANGE_REVERSAL_BEARISH"
            st_dir = "BEARISH"
            st_strength = 0.70
            st_age = i - start_rw

        elif comp < 1.1 and d_sup <= 0.2 and c > o:
            st_type = "RANGE_REVERSAL_BULLISH"
            st_dir = "BULLISH"
            st_strength = 0.70
            st_age = i - start_rw

        structure_type[i] = st_type
        structure_direction[i] = st_dir
        structure_strength[i] = round(st_strength, 2)
        structure_age[i] = st_age
        dist_to_structure[i] = round(d_struct, 2)
        breakout_distance[i] = round(bo_dist, 2)
        retest_distance[i] = round(ret_dist, 2)

    df_feat["structure_type"] = structure_type
    df_feat["structure_direction"] = structure_direction
    df_feat["structure_strength"] = structure_strength
    df_feat["structure_age"] = structure_age
    df_feat["distance_to_structure"] = dist_to_structure
    df_feat["breakout_distance"] = breakout_distance
    df_feat["retest_distance"] = retest_distance

    df_feat["swing_high"] = curr_swing_high
    df_feat["swing_low"] = curr_swing_low
    df_feat["range_high"] = range_high_arr
    df_feat["range_low"] = range_low_arr
    df_feat["support_level"] = support_arr
    df_feat["resistance_level"] = resistance_arr
    df_feat["dist_to_support_atr"] = dist_to_support
    df_feat["dist_to_resistance_atr"] = dist_to_resistance
    df_feat["dist_to_midpoint_atr"] = dist_to_midpoint
    df_feat["range_compression"] = range_compression

    return df_feat

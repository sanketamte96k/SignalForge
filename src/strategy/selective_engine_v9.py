"""
SignalForge — Phase 9: Selective Signal Engine
==============================================
File: src/strategy/selective_engine_v9.py

Causal regime classification and 8-pillar setup quality scoring engine (0-100).
Evaluates trading opportunities strictly at timestamp T without lookahead:
 - Regime: TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY, TRANSITION
 - Quality Pillars:
    1. Trend quality        (0–20)
    2. Momentum quality     (0–15)
    3. Pullback quality     (0–15)
    4. Market location     (0–15)
    5. Volatility quality   (0–10)
    6. Price action         (0–10)
    7. Time-of-day          (0–5)
    8. Risk/reward quality  (0–10)
    Total = 100
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd


REGIMES = [
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "TRANSITION",
]


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of the 8 quality pillars."""
    trend_quality: float = 0.0       # 0-20
    momentum_quality: float = 0.0    # 0-15
    pullback_quality: float = 0.0    # 0-15
    market_location: float = 0.0     # 0-15
    volatility_quality: float = 0.0  # 0-10
    price_action: float = 0.0        # 0-10
    time_of_day: float = 0.0         # 0-5
    risk_reward: float = 0.0         # 0-10
    total_score: float = 0.0         # 0-100
    regime: str = "TRANSITION"
    reasons: List[str] = field(default_factory=list)


def precompute_causal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes strictly causal indicators across the entire timeline in vectorized fashion.
    Every indicator at row i depends strictly on rows <= i (zero future lookahead).
    """
    out = pd.DataFrame(index=df.index)
    close = df["Close"] if "Close" in df.columns else df["close"]
    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    open_p = df["Open"] if "Open" in df.columns else df["open"]

    out["close"] = close
    out["high"] = high
    out["low"] = low
    out["open"] = open_p

    # 1. Causal EMAs
    out["ema9"] = close.ewm(span=9, adjust=False).mean()
    out["ema21"] = close.ewm(span=21, adjust=False).mean()
    out["ema50"] = close.ewm(span=50, adjust=False).mean()
    out["ema21_slope"] = ((out["ema21"] - out["ema21"].shift(5)) / (5.0 * out["ema21"])).fillna(0.0)

    # 2. Causal True Range and ATR(14)
    prev_close = close.shift(1).bfill()
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["tr"] = tr
    out["atr14"] = tr.ewm(span=14, adjust=False).mean()
    out["atr_baseline"] = out["atr14"].rolling(50, min_periods=10).mean().bfill()
    out["atr_ratio"] = (out["atr14"] / out["atr_baseline"]).replace(0, np.nan).fillna(1.0)

    # 3. Causal Wilder's ADX(14)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    alpha = 1.0 / 14.0
    smooth_plus = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    smooth_minus = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    atr_smooth = tr.ewm(alpha=alpha, adjust=False).mean().replace(0, np.nan)
    plus_di = (smooth_plus / atr_smooth) * 100.0
    minus_di = (smooth_minus / atr_smooth) * 100.0
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / di_sum) * 100.0
    out["adx14"] = dx.ewm(alpha=alpha, adjust=False).mean().bfill().fillna(20.0)

    # 4. Rolling ranges (shifted by 1 so current candle's own extreme is not counted as prior support/resistance)
    out["hh_20"] = high.shift(1).rolling(20, min_periods=5).max().bfill()
    out["ll_20"] = low.shift(1).rolling(20, min_periods=5).min().bfill()
    span_20 = (out["hh_20"] - out["ll_20"]).replace(0, np.nan)
    out["span_20"] = span_20
    out["range_pos"] = ((close - out["ll_20"]) / span_20).clip(0.0, 1.0).fillna(0.5)
    out["range_comp"] = (span_20 / (out["atr14"] * np.sqrt(20))).fillna(1.0)

    out["hh_10"] = high.shift(1).rolling(10, min_periods=3).max().bfill()
    out["ll_10"] = low.shift(1).rolling(10, min_periods=3).min().bfill()

    # 5. Multi-horizon returns & RSI
    out["ret_5m"] = close.pct_change(5).fillna(0.0)
    out["ret_15m"] = close.pct_change(15).fillna(0.0)

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    out["rsi14"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # 6. Candle conviction
    c_range = (high - low).replace(0, np.nan)
    out["c_range"] = c_range
    out["body"] = (close - open_p).abs()
    out["body_ratio"] = (out["body"] / c_range).fillna(0.5)

    return out


def evaluate_trade_opportunity(
    feat_row: pd.Series | Dict[str, Any],
    direction: str,
    time_val: Any
) -> ScoreBreakdown:
    """
    Evaluates causal regime and computes 8-pillar quality score (0-100) from precomputed features.
    """
    is_long = (direction.upper() == "LONG")
    c = float(feat_row["close"])
    h = float(feat_row["high"])
    l = float(feat_row["low"])
    o = float(feat_row["open"])

    e9 = float(feat_row["ema9"])
    e21 = float(feat_row["ema21"])
    e50 = float(feat_row["ema50"])
    e21_slope = float(feat_row["ema21_slope"])

    atr = max(0.01, float(feat_row["atr14"]))
    atr_ratio = float(feat_row["atr_ratio"])
    adx14 = float(feat_row["adx14"])
    range_comp = float(feat_row["range_comp"])

    hh_20 = float(feat_row["hh_20"])
    ll_20 = float(feat_row["ll_20"])
    hh_10 = float(feat_row["hh_10"])
    ll_10 = float(feat_row["ll_10"])
    range_pos = float(feat_row["range_pos"])

    ret_5m = float(feat_row["ret_5m"])
    ret_15m = float(feat_row["ret_15m"])
    rsi14 = float(feat_row["rsi14"])

    body_ratio = float(feat_row["body_ratio"])
    c_range = float(feat_row["c_range"]) if not np.isnan(feat_row["c_range"]) else (h - l)

    # -------------------------------------------------------------------------
    # REGIME CLASSIFICATION
    # -------------------------------------------------------------------------
    if atr_ratio >= 1.40:
        regime = "HIGH_VOLATILITY"
    elif atr_ratio <= 0.65:
        regime = "LOW_VOLATILITY"
    elif adx14 >= 25.0 and e9 > e21 > e50 and e21_slope > 0.0002:
        regime = "TREND_UP"
    elif adx14 >= 25.0 and e9 < e21 < e50 and e21_slope < -0.0002:
        regime = "TREND_DOWN"
    elif adx14 < 20.0 or range_comp < 0.85:
        regime = "RANGE"
    else:
        regime = "TRANSITION"

    # -------------------------------------------------------------------------
    # 1. TREND QUALITY (0–20)
    # -------------------------------------------------------------------------
    tq = 0.0
    if is_long:
        if c > e21: tq += 6.0
        if e9 > e21: tq += 5.0
        if e21 > e50: tq += 5.0
        if e21_slope > 0.0001: tq += 4.0
    else:
        if c < e21: tq += 6.0
        if e9 < e21: tq += 5.0
        if e21 < e50: tq += 5.0
        if e21_slope < -0.0001: tq += 4.0

    # -------------------------------------------------------------------------
    # 2. MOMENTUM QUALITY (0–15)
    # -------------------------------------------------------------------------
    mq = 0.0
    if is_long:
        if ret_5m > 0.0005: mq += 5.0
        if ret_15m > 0.0010: mq += 4.0
        if 48.0 <= rsi14 <= 68.0:
            mq += 6.0
        elif rsi14 > 68.0:
            mq += 2.0
    else:
        if ret_5m < -0.0005: mq += 5.0
        if ret_15m < -0.0010: mq += 4.0
        if 32.0 <= rsi14 <= 52.0:
            mq += 6.0
        elif rsi14 < 32.0:
            mq += 2.0

    # -------------------------------------------------------------------------
    # 3. PULLBACK QUALITY (0–15)
    # -------------------------------------------------------------------------
    pq = 0.0
    if is_long:
        pb_depth = (hh_10 - l) / atr if atr > 0 else 1.0
        if 0.5 <= pb_depth <= 2.2:
            pq += 9.0
        elif pb_depth < 0.5:
            pq += 5.0
        if c >= e9:
            pq += 6.0
    else:
        pb_depth = (h - ll_10) / atr if atr > 0 else 1.0
        if 0.5 <= pb_depth <= 2.2:
            pq += 9.0
        elif pb_depth < 0.5:
            pq += 5.0
        if c <= e9:
            pq += 6.0

    # -------------------------------------------------------------------------
    # 4. MARKET LOCATION (0–15)
    # -------------------------------------------------------------------------
    ml = 0.0
    if is_long:
        if range_pos >= 0.80:
            ml += 12.0
        elif 0.25 <= range_pos <= 0.60:
            ml += 10.0
        else:
            ml += 4.0
        if (hh_20 - c) > 1.2 * atr or c >= hh_20:
            ml += 3.0
    else:
        if range_pos <= 0.20:
            ml += 12.0
        elif 0.40 <= range_pos <= 0.75:
            ml += 10.0
        else:
            ml += 4.0
        if (c - ll_20) > 1.2 * atr or c <= ll_20:
            ml += 3.0

    # -------------------------------------------------------------------------
    # 5. VOLATILITY QUALITY (0–10)
    # -------------------------------------------------------------------------
    if 0.85 <= atr_ratio <= 1.25:
        vq = 10.0
    elif 0.70 <= atr_ratio < 0.85 or 1.25 < atr_ratio <= 1.45:
        vq = 7.0
    elif atr_ratio > 1.80:
        vq = 2.0
    elif atr_ratio < 0.60:
        vq = 3.0
    else:
        vq = 5.0

    # -------------------------------------------------------------------------
    # 6. PRICE ACTION / CANDLE CONVICTION (0–10)
    # -------------------------------------------------------------------------
    pa = 0.0
    if is_long:
        if c > o: pa += 3.0
        if body_ratio >= 0.50: pa += 3.0
        if c_range > 0 and (c - l) / c_range >= 0.65: pa += 4.0
    else:
        if c < o: pa += 3.0
        if body_ratio >= 0.50: pa += 3.0
        if c_range > 0 and (h - c) / c_range >= 0.65: pa += 4.0

    # -------------------------------------------------------------------------
    # 7. TIME-OF-DAY QUALITY (0–5)
    # -------------------------------------------------------------------------
    if hasattr(time_val, "time"):
        t_val = time_val.time()
    elif isinstance(time_val, str):
        t_val = pd.to_datetime(time_val).time()
    else:
        t_val = time_val

    if (pd.Timestamp("10:00:00").time() <= t_val <= pd.Timestamp("11:30:00").time()) or \
       (pd.Timestamp("13:30:00").time() <= t_val <= pd.Timestamp("14:45:00").time()):
        tod = 5.0
    elif (pd.Timestamp("09:30:00").time() <= t_val < pd.Timestamp("10:00:00").time()) or \
         (pd.Timestamp("11:30:00").time() < t_val < pd.Timestamp("13:30:00").time()):
        tod = 3.0
    elif t_val > pd.Timestamp("15:00:00").time():
        tod = 1.0
    else:
        tod = 2.0

    # -------------------------------------------------------------------------
    # 8. RISK/REWARD QUALITY (0–10)
    # -------------------------------------------------------------------------
    inval_dist = 1.5 * atr
    if is_long:
        pot_target = max(hh_20 - c, 2.0 * inval_dist)
    else:
        pot_target = max(c - ll_20, 2.0 * inval_dist)

    rrr = pot_target / inval_dist if inval_dist > 0 else 1.0
    if rrr >= 2.0:
        rr = 10.0
    elif rrr >= 1.5:
        rr = 8.0
    elif rrr >= 1.2:
        rr = 6.0
    else:
        rr = 3.0

    total = min(100.0, max(0.0, tq + mq + pq + ml + vq + pa + tod + rr))

    return ScoreBreakdown(
        trend_quality=round(tq, 1),
        momentum_quality=round(mq, 1),
        pullback_quality=round(pq, 1),
        market_location=round(ml, 1),
        volatility_quality=round(vq, 1),
        price_action=round(pa, 1),
        time_of_day=round(tod, 1),
        risk_reward=round(rr, 1),
        total_score=round(total, 1),
        regime=regime,
        reasons=[]
    )

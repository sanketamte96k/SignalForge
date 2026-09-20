"""
SignalForge Intelligence Engine — Trend Engine
==============================================
Causal trend identification, strength measurement (0-100), and structured
reasoning using EMA alignment, slope, and price position.
"""

from __future__ import annotations

from typing import List, Tuple
import numpy as np
import pandas as pd

from src.intelligence.models import TrendAnalysis, TrendState, TradeBias


def calculate_trend_analysis(df: pd.DataFrame) -> TrendAnalysis:
    """
    Computes causal trend metrics and returns structured TrendAnalysis.
    Evaluates strictly at the last available bar (index -1) without future data.
    """
    if len(df) < 5:
        # Graceful fallback for insufficient bars
        last_price = float(df["Close"].iloc[-1]) if len(df) > 0 and "Close" in df.columns else 0.0
        return TrendAnalysis(
            direction=TradeBias.NEUTRAL,
            state=TrendState.NEUTRAL,
            strength=0.0,
            ema9=last_price,
            ema21=last_price,
            ema50=last_price,
            price_to_ema21_pct=0.0,
            ema21_slope=0.0,
            reasons=["Insufficient historical data for trend calculation (<5 bars)"]
        )

    # Normalize columns if needed
    close = df["Close"] if "Close" in df.columns else df["close"]
    
    # Causal EMAs
    ema9_series = close.ewm(span=9, adjust=False).mean()
    ema21_series = close.ewm(span=21, adjust=False).mean()
    ema50_series = close.ewm(span=50, adjust=False).mean()
    
    price = float(close.iloc[-1])
    e9 = float(ema9_series.iloc[-1])
    e21 = float(ema21_series.iloc[-1])
    e50 = float(ema50_series.iloc[-1])
    
    # EMA21 slope over last 5 bars
    lookback_slope = min(5, len(ema21_series) - 1)
    if lookback_slope > 0:
        e21_prev = float(ema21_series.iloc[-1 - lookback_slope])
        ema21_slope = (e21 - e21_prev) / (lookback_slope * e21) * 100.0  # % per bar
    else:
        ema21_slope = 0.0

    price_to_ema21_pct = ((price - e21) / e21) * 100.0
    
    # Recent return (over 10 bars or available length)
    lookback_ret = min(10, len(close) - 1)
    recent_return_pct = ((price - float(close.iloc[-1 - lookback_ret])) / float(close.iloc[-1 - lookback_ret])) * 100.0

    reasons: List[str] = []
    bullish_points = 0.0
    bearish_points = 0.0
    max_points = 100.0

    # 1. Price vs EMA21 (25 pts)
    if price > e21:
        pts = min(25.0, 15.0 + max(0.0, price_to_ema21_pct * 10.0))
        bullish_points += pts
        reasons.append(f"Price is above EMA21 by {price_to_ema21_pct:+.2f}%")
    else:
        pts = min(25.0, 15.0 + max(0.0, -price_to_ema21_pct * 10.0))
        bearish_points += pts
        reasons.append(f"Price is below EMA21 by {price_to_ema21_pct:+.2f}%")

    # 2. EMA Stack Alignment: 9 vs 21 (25 pts)
    if e9 > e21:
        spread_pct = ((e9 - e21) / e21) * 100.0
        bullish_points += min(25.0, 15.0 + spread_pct * 20.0)
        reasons.append("Fast EMA9 is stacked above medium EMA21")
    else:
        spread_pct = ((e21 - e9) / e21) * 100.0
        bearish_points += min(25.0, 15.0 + spread_pct * 20.0)
        reasons.append("Fast EMA9 is stacked below medium EMA21")

    # 3. EMA 21 vs 50 Alignment (20 pts)
    if len(close) >= 20:
        if e21 > e50:
            bullish_points += 20.0
            reasons.append("Medium EMA21 is above baseline EMA50")
        else:
            bearish_points += 20.0
            reasons.append("Medium EMA21 is below baseline EMA50")

    # 4. EMA21 Slope Direction & Conviction (15 pts)
    if ema21_slope > 0.01:
        bullish_points += min(15.0, 8.0 + ema21_slope * 100.0)
        reasons.append(f"EMA21 trajectory is positive ({ema21_slope:+.3f}%/bar)")
    elif ema21_slope < -0.01:
        bearish_points += min(15.0, 8.0 + abs(ema21_slope) * 100.0)
        reasons.append(f"EMA21 trajectory is negative ({ema21_slope:+.3f}%/bar)")
    else:
        reasons.append("EMA21 slope is flat")

    # 5. Recent Price Return Agreement (15 pts)
    if recent_return_pct > 0.1:
        bullish_points += min(15.0, 5.0 + recent_return_pct * 10.0)
        reasons.append(f"Recent {lookback_ret}-bar directional return is positive ({recent_return_pct:+.2f}%)")
    elif recent_return_pct < -0.1:
        bearish_points += min(15.0, 5.0 + abs(recent_return_pct) * 10.0)
        reasons.append(f"Recent {lookback_ret}-bar directional return is negative ({recent_return_pct:+.2f}%)")

    # Determine State and Direction
    net_score = bullish_points - bearish_points
    strength = min(100.0, max(0.0, abs(net_score)))

    if net_score >= 50.0:
        state = TrendState.STRONG_BULLISH
        direction = TradeBias.LONG_BIAS
    elif net_score >= 15.0:
        state = TrendState.BULLISH
        direction = TradeBias.LONG_BIAS
    elif net_score <= -50.0:
        state = TrendState.STRONG_BEARISH
        direction = TradeBias.SHORT_BIAS
    elif net_score <= -15.0:
        state = TrendState.BEARISH
        direction = TradeBias.SHORT_BIAS
    else:
        state = TrendState.NEUTRAL
        direction = TradeBias.NEUTRAL
        strength = max(0.0, 100.0 - abs(net_score) * 2.0)  # Neutral certainty

    return TrendAnalysis(
        direction=direction,
        state=state,
        strength=round(float(strength), 2),
        ema9=round(float(e9), 2),
        ema21=round(float(e21), 2),
        ema50=round(float(e50), 2),
        price_to_ema21_pct=round(float(price_to_ema21_pct), 3),
        ema21_slope=round(float(ema21_slope), 4),
        reasons=reasons
    )

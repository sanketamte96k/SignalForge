"""
SignalForge Intelligence Engine — Momentum Engine
=================================================
Causal momentum evaluation synthesizing multi-horizon returns, Wilder's RSI,
rate of change (ROC), and directional persistence into an explainable score.
"""

from __future__ import annotations

from typing import List
import numpy as np
import pandas as pd

from src.intelligence.models import MomentumAnalysis, TradeBias
from src.intelligence.config import IntelligenceThresholds


def calculate_momentum_analysis(
    df: pd.DataFrame,
    thresholds: IntelligenceThresholds | None = None
) -> MomentumAnalysis:
    """
    Computes causal momentum metrics strictly using historical data up to index -1.
    """
    if thresholds is None:
        thresholds = IntelligenceThresholds()

    if len(df) < 5:
        return MomentumAnalysis(
            direction=TradeBias.NEUTRAL,
            strength=0.0,
            rsi14=50.0,
            return_5m_pct=0.0,
            return_15m_pct=0.0,
            return_30m_pct=0.0,
            roc=0.0,
            reasons=["Insufficient historical data (<5 bars) for momentum analysis"]
        )

    close = df["Close"] if "Close" in df.columns else df["close"]
    price = float(close.iloc[-1])

    # 1. Multi-horizon returns
    ret_5m = ((price - float(close.iloc[-min(5, len(close) - 1)])) / float(close.iloc[-min(5, len(close) - 1)])) * 100.0
    ret_15m = ((price - float(close.iloc[-min(15, len(close) - 1)])) / float(close.iloc[-min(15, len(close) - 1)])) * 100.0
    ret_30m = ((price - float(close.iloc[-min(30, len(close) - 1)])) / float(close.iloc[-min(30, len(close) - 1)])) * 100.0

    # Rate of change (10 bars)
    lookback_roc = min(10, len(close) - 1)
    roc = ((price - float(close.iloc[-1 - lookback_roc])) / float(close.iloc[-1 - lookback_roc])) * 100.0

    # 2. Causal Wilder's RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    alpha = 1.0 / 14.0
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs = avg_gain.iloc[-1] / (avg_loss.iloc[-1] + 1e-9)
    rsi14 = 100.0 - (100.0 / (1.0 + rs))
    rsi14 = min(100.0, max(0.0, float(rsi14)))

    # 3. Directional Persistence (how many of last 5 bars closed in same direction)
    lookback_p = min(5, len(close) - 1)
    if lookback_p > 0:
        recent_diffs = delta.iloc[-lookback_p:]
        pos_bars = (recent_diffs > 0).sum()
        neg_bars = (recent_diffs < 0).sum()
    else:
        pos_bars = 0
        neg_bars = 0

    reasons: List[str] = []
    bullish_pts = 0.0
    bearish_pts = 0.0

    # Return alignment (40 pts)
    if ret_5m > 0.05 and ret_15m > 0.08:
        bullish_pts += 30.0
        reasons.append(f"Short & medium-term returns aligned positive (+{ret_5m:.2f}%, +{ret_15m:.2f}%)")
    elif ret_5m < -0.05 and ret_15m < -0.08:
        bearish_pts += 30.0
        reasons.append(f"Short & medium-term returns aligned negative ({ret_5m:.2f}%, {ret_15m:.2f}%)")
    else:
        reasons.append(f"Mixed returns across horizons (5m: {ret_5m:+.2f}%, 15m: {ret_15m:+.2f}%)")

    if ret_30m > 0.15:
        bullish_pts += 10.0
    elif ret_30m < -0.15:
        bearish_pts += 10.0

    # RSI Context (30 pts)
    if rsi14 >= thresholds.rsi_neutral_high and rsi14 <= thresholds.rsi_overbought:
        bullish_pts += 30.0
        reasons.append(f"RSI(14) is in healthy bullish expansion zone ({rsi14:.1f})")
    elif rsi14 > thresholds.rsi_overbought:
        bullish_pts += 15.0
        reasons.append(f"RSI(14) is overbought ({rsi14:.1f}) — strong momentum but elevated pullback risk")
    elif rsi14 <= thresholds.rsi_neutral_low and rsi14 >= thresholds.rsi_oversold:
        bearish_pts += 30.0
        reasons.append(f"RSI(14) is in healthy bearish momentum zone ({rsi14:.1f})")
    elif rsi14 < thresholds.rsi_oversold:
        bearish_pts += 15.0
        reasons.append(f"RSI(14) is oversold ({rsi14:.1f}) — strong downward thrust but exhaustion risk")
    else:
        reasons.append(f"RSI(14) is neutral ({rsi14:.1f})")

    # Rate of Change (15 pts)
    if roc > 0.1:
        bullish_pts += 15.0
        reasons.append(f"Positive velocity: 10-bar ROC is +{roc:.2f}%")
    elif roc < -0.1:
        bearish_pts += 15.0
        reasons.append(f"Negative velocity: 10-bar ROC is {roc:.2f}%")

    # Directional Persistence (15 pts)
    if pos_bars >= 4:
        bullish_pts += 15.0
        reasons.append(f"High bullish persistence ({pos_bars}/5 consecutive green closes)")
    elif neg_bars >= 4:
        bearish_pts += 15.0
        reasons.append(f"High bearish persistence ({neg_bars}/5 consecutive red closes)")

    net_score = bullish_pts - bearish_pts
    strength = min(100.0, max(0.0, abs(net_score)))

    if net_score >= 25.0:
        direction = TradeBias.LONG_BIAS
    elif net_score <= -25.0:
        direction = TradeBias.SHORT_BIAS
    else:
        direction = TradeBias.NEUTRAL
        strength = max(0.0, 50.0 - abs(net_score))

    return MomentumAnalysis(
        direction=direction,
        strength=round(float(strength), 1),
        rsi14=round(float(rsi14), 1),
        return_5m_pct=round(float(ret_5m), 3),
        return_15m_pct=round(float(ret_15m), 3),
        return_30m_pct=round(float(ret_30m), 3),
        roc=round(float(roc), 3),
        reasons=reasons
    )

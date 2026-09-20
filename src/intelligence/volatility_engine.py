"""
SignalForge Intelligence Engine — Volatility Engine
===================================================
Causal volatility classification, regime detection, expansion/contraction dynamics,
and volatility quality scoring (0-100).
"""

from __future__ import annotations

from typing import List
import numpy as np
import pandas as pd

from src.intelligence.models import VolatilityAnalysis, VolatilityState, VolatilityDynamics
from src.intelligence.config import IntelligenceThresholds


def calculate_volatility_analysis(
    df: pd.DataFrame,
    thresholds: IntelligenceThresholds | None = None
) -> VolatilityAnalysis:
    """
    Computes causal volatility metrics and returns structured VolatilityAnalysis.
    Evaluates strictly at the last available bar without future lookahead.
    """
    if thresholds is None:
        thresholds = IntelligenceThresholds()

    if len(df) < 5:
        return VolatilityAnalysis(
            state=VolatilityState.NORMAL,
            dynamics=VolatilityDynamics.STABLE,
            atr=1.0,
            atr_relative_ratio=1.0,
            realized_volatility_pctile=50.0,
            range_compression=1.0,
            volatility_quality_score=50.0,
            reasons=["Insufficient historical bars (<5) for volatility profiling"]
        )

    # Column mapping
    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    close = df["Close"] if "Close" in df.columns else df["close"]

    # 1. Causal True Range and ATR(14)
    prev_close = close.shift(1).bfill()
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr14_series = tr.ewm(span=14, adjust=False).mean()
    atr = float(atr14_series.iloc[-1])

    # 2. Baseline ATR (rolling 50 SMA)
    sma_win = min(50, len(atr14_series))
    atr_baseline = float(atr14_series.iloc[-sma_win:].mean())
    atr_rel = atr / atr_baseline if atr_baseline > 0 else 1.0

    # 3. Realized Volatility Percentile (rolling 100 bars)
    pctile_win = min(100, len(atr14_series))
    recent_atrs = atr14_series.iloc[-pctile_win:]
    min_atr = float(recent_atrs.min())
    max_atr = float(recent_atrs.max())
    denom = max_atr - min_atr
    if denom > 1e-6:
        rv_pctile = ((atr - min_atr) / denom) * 100.0
    else:
        rv_pctile = 50.0
    rv_pctile = min(100.0, max(0.0, rv_pctile))

    # 4. Range Compression (20-bar rolling range vs 20*ATR)
    range_win = min(20, len(df))
    hh_20 = float(high.iloc[-range_win:].max())
    ll_20 = float(low.iloc[-range_win:].min())
    rolling_range = hh_20 - ll_20
    expected_range = atr * np.sqrt(range_win)
    range_comp = rolling_range / expected_range if expected_range > 0 else 1.0

    # 5. Volatility Dynamics (ATR slope over last 5 bars)
    dyn_win = min(5, len(atr14_series) - 1)
    if dyn_win > 0:
        atr_change = (atr - float(atr14_series.iloc[-1 - dyn_win])) / atr_baseline
        if atr_change > 0.15:
            dynamics = VolatilityDynamics.EXPANDING
        elif atr_change < -0.15:
            dynamics = VolatilityDynamics.CONTRACTING
        else:
            dynamics = VolatilityDynamics.STABLE
    else:
        dynamics = VolatilityDynamics.STABLE

    # 6. Volatility State Classification
    reasons: List[str] = []
    if atr_rel >= thresholds.vol_extreme_ratio or rv_pctile >= 95.0:
        state = VolatilityState.EXTREME
        reasons.append(f"Extreme volatility detected (ATR is {atr_rel:.2f}x baseline; {rv_pctile:.0f}th percentile)")
    elif atr_rel >= thresholds.vol_high_ratio or rv_pctile >= 75.0:
        state = VolatilityState.HIGH
        reasons.append(f"Elevated volatility (ATR is {atr_rel:.2f}x baseline; {rv_pctile:.0f}th percentile)")
    elif atr_rel <= thresholds.vol_very_low_ratio or rv_pctile <= 10.0:
        state = VolatilityState.VERY_LOW
        reasons.append(f"Compressed/Very low volatility (ATR is {atr_rel:.2f}x baseline; {rv_pctile:.0f}th percentile)")
    elif atr_rel <= thresholds.vol_low_ratio or rv_pctile <= 25.0:
        state = VolatilityState.LOW
        reasons.append(f"Subdued volatility (ATR is {atr_rel:.2f}x baseline)")
    else:
        state = VolatilityState.NORMAL
        reasons.append(f"Normal balanced volatility regime (ATR {atr:.2f}, {atr_rel:.2f}x baseline)")

    reasons.append(f"Volatility trajectory is {dynamics.value.lower()}")

    # 7. Volatility Quality Score (0-100)
    # Balanced/normal volatility has highest quality (~80-95).
    # Extreme volatility is hazardous (~20-40). Dead compressed volatility lacks follow-through (~30-50).
    if state == VolatilityState.NORMAL:
        quality_score = 90.0 if dynamics == VolatilityDynamics.STABLE else 80.0
    elif state == VolatilityState.LOW:
        quality_score = 70.0
    elif state == VolatilityState.HIGH:
        quality_score = 60.0
    elif state == VolatilityState.VERY_LOW:
        quality_score = 40.0
    else:  # EXTREME
        quality_score = 20.0

    return VolatilityAnalysis(
        state=state,
        dynamics=dynamics,
        atr=round(float(atr), 2),
        atr_relative_ratio=round(float(atr_rel), 2),
        realized_volatility_pctile=round(float(rv_pctile), 1),
        range_compression=round(float(range_comp), 2),
        volatility_quality_score=round(float(quality_score), 1),
        reasons=reasons
    )

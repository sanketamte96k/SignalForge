"""
SignalForge — Phase 6: Setup Quality Scoring Engine
====================================================
File: src/strategy/setup_score.py

Evaluates every setup candidate on a 0–100 transparent scale
across 5 equal-weight pillars (0–20 points each):
1. Trend Alignment (0–20): Alignment with higher timeframe / EMA slope / ADX.
2. Structure Quality (0–20): Cleanliness of breakout / range compression / boundaries.
3. Momentum Quality (0–20): Return acceleration and candle conviction.
4. Volatility Condition (0–20): ATR regime appropriateness (expansion vs stagnation).
5. Entry Location Quality (0–20): Distance from key levels and risk geometry.

Every sub-pillar score is preserved in the dataset for rigorous empirical analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
import pandas as pd


@dataclass
class QualityBreakdown:
    total_score: float
    trend_score: float
    structure_score: float
    momentum_score: float
    volatility_score: float
    entry_location_score: float
    confidence_tier: str  # HIGH (>=75), MEDIUM (50-74), LOW (<50)


def calculate_setup_quality(
    setup_name: str,
    direction: str,
    row: pd.Series,
    features: Dict[str, Any]
) -> QualityBreakdown:
    """
    Computes transparent equal-weight quality score from 0 to 100.
    """
    # 1. Trend Alignment (0–20)
    trend_score = 10.0  # Base
    ema_slope = float(row.get("ema9_slope", 0.0))
    adx = float(row.get("adx14", 20.0))
    ema_spread = float(row.get("ema_spread", 0.0))

    if direction == "LONG":
        if ema_slope > 0:
            trend_score += 5.0
        if ema_spread > 0:
            trend_score += 2.5
        if adx >= 22.0:
            trend_score += 2.5
    else:  # SHORT
        if ema_slope < 0:
            trend_score += 5.0
        if ema_spread < 0:
            trend_score += 2.5
        if adx >= 22.0:
            trend_score += 2.5
    trend_score = float(np.clip(trend_score, 0.0, 20.0))

    # 2. Structure Quality (0–20)
    structure_score = 10.0
    compression = float(features.get("compression", features.get("compression_prior", 1.0)))
    if compression < 0.9:
        structure_score += 8.0
    elif compression < 1.1:
        structure_score += 4.0
    elif compression > 1.4:
        structure_score -= 4.0

    if setup_name in ["BREAKOUT", "MOMENTUM_EXPANSION"]:
        if features.get("breakout_distance_atr", 0.0) < 1.0:
            structure_score += 2.0
    elif setup_name == "RANGE_REVERSAL":
        structure_score += 4.0 if adx < 22.0 else 0.0
    structure_score = float(np.clip(structure_score, 0.0, 20.0))

    # 3. Momentum Quality (0–20)
    momentum_score = 10.0
    candle_body_ratio = float(row.get("candle_body_ratio", 0.5))
    if candle_body_ratio >= 0.65:
        momentum_score += 6.0
    elif candle_body_ratio >= 0.50:
        momentum_score += 3.0

    plus_di = float(row.get("plus_di", 20.0))
    minus_di = float(row.get("minus_di", 20.0))
    if direction == "LONG" and plus_di > minus_di:
        momentum_score += 4.0
    elif direction == "SHORT" and minus_di > plus_di:
        momentum_score += 4.0
    momentum_score = float(np.clip(momentum_score, 0.0, 20.0))

    # 4. Volatility Condition (0–20)
    volatility_score = 10.0
    atr_ratio = float(row.get("atr_ratio", 1.0))
    atr_pctile = float(row.get("atr_pctile", 50.0))

    if setup_name in ["BREAKOUT", "MOMENTUM_EXPANSION"]:
        if atr_ratio >= 1.10:
            volatility_score += 7.0
        elif atr_ratio >= 0.95:
            volatility_score += 3.0
        if 40.0 <= atr_pctile <= 85.0:
            volatility_score += 3.0
    else:  # PULLBACK or RANGE_REVERSAL
        if 30.0 <= atr_pctile <= 70.0:
            volatility_score += 6.0
        if atr_ratio <= 1.15:
            volatility_score += 4.0
    volatility_score = float(np.clip(volatility_score, 0.0, 20.0))

    # 5. Entry Location Quality (0–20)
    entry_score = 10.0
    range_pos = float(row.get("range_position", 0.5))
    if direction == "LONG":
        if setup_name == "RANGE_REVERSAL" and range_pos <= 0.3:
            entry_score += 8.0
        elif setup_name in ["BREAKOUT", "PULLBACK"] and range_pos >= 0.6:
            entry_score += 6.0
    else:  # SHORT
        if setup_name == "RANGE_REVERSAL" and range_pos >= 0.7:
            entry_score += 8.0
        elif setup_name in ["BREAKOUT", "PULLBACK"] and range_pos <= 0.4:
            entry_score += 6.0
    entry_score = float(np.clip(entry_score, 0.0, 20.0))

    total = round(trend_score + structure_score + momentum_score + volatility_score + entry_score, 1)
    tier = "HIGH" if total >= 75.0 else ("MEDIUM" if total >= 50.0 else "LOW")

    return QualityBreakdown(
        total_score=total,
        trend_score=round(trend_score, 1),
        structure_score=round(structure_score, 1),
        momentum_score=round(momentum_score, 1),
        volatility_score=round(volatility_score, 1),
        entry_location_score=round(entry_score, 1),
        confidence_tier=tier
    )

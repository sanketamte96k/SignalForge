"""
SignalForge Intelligence Engine — Risk Context Engine
=====================================================
Contextual risk measurement using ATR multiples, structural invalidation distance,
and volatility stress to classify risk levels (LOW, MEDIUM, HIGH, EXTREME).
"""

from __future__ import annotations

from typing import List
from src.intelligence.models import (
    RiskContext,
    RiskLevel,
    TradeBias,
    VolatilityAnalysis,
    StructureAnalysis,
    VolatilityState,
)


def calculate_risk_context(
    price: float,
    direction: TradeBias,
    volatility: VolatilityAnalysis,
    structure: StructureAnalysis
) -> RiskContext:
    """
    Evaluates contextual risk and invalidation geometry based on structural
    levels and current volatility.
    """
    atr = max(0.01, volatility.atr)
    warnings: List[str] = []

    # 1. Distance to nearest structural invalidation level
    if direction == TradeBias.LONG_BIAS:
        # Long invalidation: swing low
        structural_dist = max(0.0, price - structure.recent_swing_low)
    elif direction == TradeBias.SHORT_BIAS:
        # Short invalidation: swing high
        structural_dist = max(0.0, structure.recent_swing_high - price)
    else:
        # Neutral: average distance to range boundary
        structural_dist = min(price - structure.recent_swing_low, structure.recent_swing_high - price)
        structural_dist = max(0.0, structural_dist)

    # 2. Suggested risk distance (structure-guided with 1.25x ATR minimum)
    min_risk_dist = 1.25 * atr
    if structural_dist > 0.1 * atr:
        suggested_dist = max(min_risk_dist, structural_dist)
    else:
        suggested_dist = min_risk_dist

    atr_mult = suggested_dist / atr
    vol_adjusted_risk = suggested_dist * (volatility.atr_relative_ratio)

    # 3. Estimated Reward/Risk Context
    # In trending / breakout conditions, reward projects forward to either structural ceiling or a standard 1.5R/2ATR continuation target
    if direction == TradeBias.LONG_BIAS:
        dist_to_ceiling = max(0.0, structure.recent_swing_high - price)
        potential_reward = max(dist_to_ceiling, 1.5 * suggested_dist, 2.0 * atr)
    elif direction == TradeBias.SHORT_BIAS:
        dist_to_floor = max(0.0, price - structure.recent_swing_low)
        potential_reward = max(dist_to_floor, 1.5 * suggested_dist, 2.0 * atr)
    else:
        potential_reward = suggested_dist

    rrr = potential_reward / suggested_dist if suggested_dist > 0 else 1.0

    # 4. Risk Level Classification
    # Extreme conditions: ATR ratio > 2.0x, or risk distance > 4.0 ATR, or price in erratic breakout
    if volatility.state == VolatilityState.EXTREME or atr_mult > 4.5:
        risk_level = RiskLevel.EXTREME
        risk_score = 15.0
        warnings.append(f"Extreme risk: Volatility multiple {volatility.atr_relative_ratio:.2f}x or structural invalidation too wide ({atr_mult:.1f} ATR)")
    elif volatility.state == VolatilityState.HIGH or atr_mult > 3.0 or rrr < 0.8:
        risk_level = RiskLevel.HIGH
        risk_score = 45.0
        warnings.append(f"Elevated risk: High volatility or unfavorable reward/risk context ({rrr:.2f}:1)")
    elif atr_mult < 1.8 and rrr >= 1.4:
        risk_level = RiskLevel.LOW
        risk_score = 85.0
    else:
        risk_level = RiskLevel.MEDIUM
        risk_score = 70.0

    if rrr < 1.0:
        warnings.append(f"Caution: Estimated structural reward/risk ({rrr:.2f}:1) is asymmetric against trade")

    return RiskContext(
        risk_level=risk_level,
        suggested_risk_distance=round(float(suggested_dist), 2),
        risk_distance_atr_multiple=round(float(atr_mult), 2),
        distance_to_structure=round(float(structural_dist), 2),
        volatility_adjusted_risk=round(float(vol_adjusted_risk), 2),
        estimated_reward_risk_ratio=round(float(rrr), 2),
        risk_quality_score=round(float(risk_score), 1),
        warnings=warnings
    )

"""
SignalForge Intelligence Engine — Confidence Engine
===================================================
Calculates agreement-of-evidence consensus across Trend, Momentum, Structure,
Volatility, and Session without ever implying a win probability.
"""

from __future__ import annotations

from typing import List
from src.intelligence.models import (
    ConfidenceAnalysis,
    TradeBias,
    TrendAnalysis,
    MomentumAnalysis,
    StructureAnalysis,
    VolatilityAnalysis,
    SessionContext,
    StructureState,
    VolatilityState,
    SessionState,
)


def calculate_confidence_analysis(
    overall_direction: TradeBias,
    trend: TrendAnalysis,
    momentum: MomentumAnalysis,
    structure: StructureAnalysis,
    volatility: VolatilityAnalysis,
    session: SessionContext
) -> ConfidenceAnalysis:
    """
    Measures degree of causal agreement and absence of contradictory evidence.
    """
    conflicting_factors: List[str] = []
    reasons: List[str] = []

    if overall_direction == TradeBias.NEUTRAL:
        return ConfidenceAnalysis(
            score=35.0,
            agreement_ratio=0.33,
            conflicting_factors=["Directional evidence is neutral / undecided"],
            reasons=["No clear directional consensus across indicators"]
        )

    # 1. Check directional alignment across primary engines (Trend, Momentum, Structure)
    agreed_count = 0
    total_components = 3

    # Trend check
    if trend.direction == overall_direction:
        agreed_count += 1
        reasons.append("Trend alignment agrees with overall bias")
    elif trend.direction != TradeBias.NEUTRAL:
        conflicting_factors.append(f"Trend ({trend.direction.value}) opposes overall bias ({overall_direction.value})")

    # Momentum check
    if momentum.direction == overall_direction:
        agreed_count += 1
        reasons.append("Momentum alignment agrees with overall bias")
    elif momentum.direction != TradeBias.NEUTRAL:
        conflicting_factors.append(f"Momentum ({momentum.direction.value}) opposes overall bias")

    # Structure check
    if overall_direction == TradeBias.LONG_BIAS:
        if structure.state in (StructureState.BULLISH_STRUCTURE, StructureState.BREAKOUT_UP):
            agreed_count += 1
            reasons.append("Market structure confirms bullish progression / breakout")
        elif structure.state in (StructureState.BEARISH_STRUCTURE, StructureState.BREAKOUT_DOWN):
            conflicting_factors.append("Market structure is bearish despite bullish bias")
    else:  # SHORT_BIAS
        if structure.state in (StructureState.BEARISH_STRUCTURE, StructureState.BREAKOUT_DOWN):
            agreed_count += 1
            reasons.append("Market structure confirms bearish progression / breakdown")
        elif structure.state in (StructureState.BULLISH_STRUCTURE, StructureState.BREAKOUT_UP):
            conflicting_factors.append("Market structure is bullish despite bearish bias")

    agreement_ratio = agreed_count / total_components

    # 2. Base Confidence calculation
    base_score = agreement_ratio * 70.0

    # 3. Adjustments for environmental context
    # Volatility health
    if volatility.state == VolatilityState.NORMAL:
        base_score += 15.0
        reasons.append("Volatility environment is balanced and orderly")
    elif volatility.state in (VolatilityState.HIGH, VolatilityState.LOW):
        base_score += 8.0
    elif volatility.state == VolatilityState.EXTREME:
        base_score -= 25.0
        conflicting_factors.append("Extreme volatility undermines signal fidelity")
    elif volatility.state == VolatilityState.VERY_LOW:
        base_score -= 10.0
        conflicting_factors.append("Severe volatility compression limits directional follow-through")

    # Session quality
    if session.state in (SessionState.EARLY_SESSION, SessionState.AFTERNOON):
        base_score += 15.0
        reasons.append("Session timing is in high-liquidity active execution window")
    elif session.state == SessionState.MIDDAY:
        base_score += 5.0
    elif session.state == SessionState.CLOSING:
        base_score -= 20.0
        conflicting_factors.append("Late session trading window compromises holding timeframe")

    # Penalty for conflicting factors
    if len(conflicting_factors) > 0:
        penalty = len(conflicting_factors) * 15.0
        base_score = max(10.0, base_score - penalty)

    final_score = min(100.0, max(0.0, base_score))

    return ConfidenceAnalysis(
        score=round(float(final_score), 1),
        agreement_ratio=round(float(agreement_ratio), 2),
        conflicting_factors=conflicting_factors,
        reasons=reasons
    )

"""
SignalForge Intelligence Engine — Opportunity & Tradeability Engine
===================================================================
Synthesizes weighted component scores into Opportunity Score (0-100), evaluates
directional bias consensus, computes Tradeability Score (0-100), and strictly
enforces NO_TRADE gates.
"""

from __future__ import annotations

from typing import List, Tuple, Dict
from src.intelligence.models import (
    OpportunityScore,
    TradeBias,
    TradeabilityDecision,
    NoTradeReason,
    TrendAnalysis,
    MomentumAnalysis,
    StructureAnalysis,
    VolatilityAnalysis,
    SessionContext,
    RiskContext,
    ConfidenceAnalysis,
    StructureState,
    VolatilityState,
    SessionState,
    RiskLevel,
)
from src.intelligence.config import IntelligenceConfig


def determine_directional_bias(
    trend: TrendAnalysis,
    momentum: MomentumAnalysis,
    structure: StructureAnalysis
) -> Tuple[TradeBias, List[str]]:
    """
    Synthesizes overall directional bias based on agreement between Trend,
    Momentum, and Market Structure. If evidence conflicts, defaults to NEUTRAL.
    """
    long_votes = 0
    short_votes = 0
    reasons: List[str] = []

    # 1. Trend vote
    if trend.direction == TradeBias.LONG_BIAS:
        long_votes += 1
    elif trend.direction == TradeBias.SHORT_BIAS:
        short_votes += 1

    # 2. Momentum vote
    if momentum.direction == TradeBias.LONG_BIAS:
        long_votes += 1
    elif momentum.direction == TradeBias.SHORT_BIAS:
        short_votes += 1

    # 3. Structure vote
    if structure.state in (StructureState.BULLISH_STRUCTURE, StructureState.BREAKOUT_UP):
        long_votes += 1
    elif structure.state in (StructureState.BEARISH_STRUCTURE, StructureState.BREAKOUT_DOWN):
        short_votes += 1

    if long_votes >= 2 and short_votes == 0:
        bias = TradeBias.LONG_BIAS
        reasons.append(f"Consensus bullish bias ({long_votes}/3 primary engines agree)")
    elif short_votes >= 2 and long_votes == 0:
        bias = TradeBias.SHORT_BIAS
        reasons.append(f"Consensus bearish bias ({short_votes}/3 primary engines agree)")
    else:
        bias = TradeBias.NEUTRAL
        reasons.append(f"Conflicting or indecisive directional votes (Long: {long_votes}, Short: {short_votes})")

    return bias, reasons


def calculate_opportunity_score(
    trend: TrendAnalysis,
    structure: StructureAnalysis,
    momentum: MomentumAnalysis,
    volatility: VolatilityAnalysis,
    risk: RiskContext,
    session: SessionContext,
    config: IntelligenceConfig
) -> OpportunityScore:
    """
    Synthesizes weighted component quality scores into unified Opportunity Score.
    """
    w = config.weights
    tot_weight = (
        w.trend + w.structure + w.momentum +
        w.volatility + w.risk_reward + w.session
    )

    norm_w = {
        "trend": w.trend / tot_weight,
        "structure": w.structure / tot_weight,
        "momentum": w.momentum / tot_weight,
        "volatility": w.volatility / tot_weight,
        "risk_reward": w.risk_reward / tot_weight,
        "session": w.session / tot_weight,
    }

    comp_scores = {
        "trend": trend.strength,
        "structure": structure.quality_score,
        "momentum": momentum.strength,
        "volatility": volatility.volatility_quality_score,
        "risk_reward": risk.risk_quality_score,
        "session": session.session_quality_score,
    }

    opp_score = sum(norm_w[k] * comp_scores[k] for k in norm_w)
    opp_score = min(100.0, max(0.0, opp_score))

    return OpportunityScore(
        score=round(float(opp_score), 1),
        weights={k: round(v, 3) for k, v in norm_w.items()},
        component_scores={k: round(v, 1) for k, v in comp_scores.items()}
    )


def evaluate_tradeability(
    direction: TradeBias,
    opp_score: float,
    confidence: ConfidenceAnalysis,
    risk: RiskContext,
    volatility: VolatilityAnalysis,
    session: SessionContext,
    structure: StructureAnalysis,
    config: IntelligenceConfig
) -> Tuple[float, TradeabilityDecision, List[NoTradeReason], List[str]]:
    """
    Computes tradeability score (0-100) and explicitly checks for NO_TRADE / CAUTION conditions.
    SignalForge prioritizes capital preservation by preferring NO_TRADE over questionable setups.
    """
    no_trade_reasons: List[NoTradeReason] = []
    explanation_reasons: List[str] = []

    # 1. Base tradeability derives from opportunity and confidence
    tradeability_base = (opp_score * 0.55) + (confidence.score * 0.45)

    # 2. Strict Hard Gates for NO_TRADE
    # Gate A: Session End Proximity
    if session.minutes_to_close <= config.thresholds.no_trade_session_minutes_remaining:
        no_trade_reasons.append(NoTradeReason.LATE_SESSION)
        explanation_reasons.append(f"Late session cutoff ({session.minutes_to_close}m to close)")
        tradeability_base = min(tradeability_base, 25.0)

    # Gate B: Extreme Risk / Volatility
    if risk.risk_level == RiskLevel.EXTREME or volatility.state == VolatilityState.EXTREME:
        no_trade_reasons.append(NoTradeReason.EXTREME_VOLATILITY)
        explanation_reasons.append("Extreme market volatility / erratic expansion")
        tradeability_base = min(tradeability_base, 20.0)

    # Gate C: Directional Conflict / Indecision
    if direction == TradeBias.NEUTRAL:
        no_trade_reasons.append(NoTradeReason.CONFLICTING_SIGNALS)
        explanation_reasons.append("Directional bias is neutral with conflicting sub-engine votes")
        tradeability_base = min(tradeability_base, 35.0)

    # Gate D: Trapped in Noise / Low Edge Range
    if structure.state == StructureState.RANGE_STRUCTURE and structure.range_position >= 0.4 and structure.range_position <= 0.6:
        if opp_score < 60.0:
            no_trade_reasons.append(NoTradeReason.RANGE_NO_EDGE)
            explanation_reasons.append("Price trapped in range center without structural momentum")
            tradeability_base = min(tradeability_base, 38.0)

    # Gate E: Low Confidence
    if confidence.score < config.thresholds.min_confidence_tradeable:
        no_trade_reasons.append(NoTradeReason.LOW_CONFIDENCE)
        explanation_reasons.append(f"Confidence score ({confidence.score:.1f}) is below minimum tradeable threshold ({config.thresholds.min_confidence_tradeable})")

    # Gate F: Poor Risk-Reward
    if risk.estimated_reward_risk_ratio < 0.8:
        no_trade_reasons.append(NoTradeReason.POOR_RISK_REWARD)
        explanation_reasons.append(f"Unfavorable structural reward/risk geometry ({risk.estimated_reward_risk_ratio:.2f}:1)")

    tradeability_score = min(100.0, max(0.0, tradeability_base))

    # 3. Decision mapping
    if len(no_trade_reasons) > 0 or tradeability_score < config.thresholds.caution_min_score:
        decision = TradeabilityDecision.NO_TRADE
    elif tradeability_score >= config.thresholds.tradeable_min_score and confidence.score >= config.thresholds.min_confidence_tradeable:
        decision = TradeabilityDecision.TRADEABLE
    else:
        decision = TradeabilityDecision.CAUTION

    return round(float(tradeability_score), 1), decision, no_trade_reasons, explanation_reasons

"""
SignalForge Intelligence Engine — Explanation Engine
====================================================
Transforms numerical metrics, classifications, and agreement consensus into
human-interpretable facts, evidence bullets, risk warnings, and NO_TRADE justifications.
"""

from __future__ import annotations

from typing import List
from src.intelligence.models import (
    ExplanationReport,
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
)


def generate_explanation_report(
    symbol: str,
    price: float,
    direction: TradeBias,
    opp_score: float,
    tradeability_score: float,
    confidence: ConfidenceAnalysis,
    decision: TradeabilityDecision,
    no_trade_reasons: List[NoTradeReason],
    decision_reasons: List[str],
    trend: TrendAnalysis,
    momentum: MomentumAnalysis,
    structure: StructureAnalysis,
    volatility: VolatilityAnalysis,
    risk: RiskContext,
    session: SessionContext
) -> ExplanationReport:
    """
    Constructs an evidence-backed structured explanation report for a symbol's market state.
    """
    evidence: List[str] = []
    warnings: List[str] = []

    # 1. Gather positive structural evidence
    if direction == TradeBias.LONG_BIAS:
        if trend.direction == TradeBias.LONG_BIAS:
            evidence.append(f"Trend: Strong bullish alignment (EMA9 > EMA21 > EMA50; strength {trend.strength:.0f})")
        if momentum.direction == TradeBias.LONG_BIAS:
            evidence.append(f"Momentum: Positive directional velocity (RSI {momentum.rsi14:.1f}, 5m {momentum.return_5m_pct:+.2f}%)")
        if structure.state.value in ("BULLISH_STRUCTURE", "BREAKOUT_UP"):
            evidence.append(f"Structure: {structure.state.value.replace('_', ' ').title()} (Range pos: {structure.range_position*100:.0f}%)")
    elif direction == TradeBias.SHORT_BIAS:
        if trend.direction == TradeBias.SHORT_BIAS:
            evidence.append(f"Trend: Strong bearish alignment (EMA9 < EMA21 < EMA50; strength {trend.strength:.0f})")
        if momentum.direction == TradeBias.SHORT_BIAS:
            evidence.append(f"Momentum: Downward thrust confirmed (RSI {momentum.rsi14:.1f}, 5m {momentum.return_5m_pct:+.2f}%)")
        if structure.state.value in ("BEARISH_STRUCTURE", "BREAKOUT_DOWN"):
            evidence.append(f"Structure: {structure.state.value.replace('_', ' ').title()} (Range pos: {structure.range_position*100:.0f}%)")

    if volatility.state.value == "NORMAL":
        evidence.append(f"Volatility: Balanced and orderly ATR regime ({volatility.atr:.2f}, {volatility.dynamics.value})")

    if session.session_quality_score >= 75.0:
        evidence.append(f"Session: Favorable active trading window ({session.state.value.replace('_', ' ').title()})")

    # 2. Gather active risks and warnings
    for w in risk.warnings:
        warnings.append(f"Risk: {w}")

    for c in confidence.conflicting_factors:
        warnings.append(f"Divergence: {c}")

    if session.minutes_to_close <= 30:
        warnings.append(f"Session: Nearing market close ({session.minutes_to_close} mins remaining)")

    if structure.range_position >= 0.85 and direction == TradeBias.LONG_BIAS:
        warnings.append("Resistance: Price pressing immediate range ceiling (exhaustion risk)")
    elif structure.range_position <= 0.15 and direction == TradeBias.SHORT_BIAS:
        warnings.append("Support: Price pressing immediate range floor (bounce risk)")

    # 3. Format NO_TRADE justifications
    formatted_no_trade = [f"{r.value}: {desc}" for r, desc in zip(no_trade_reasons, decision_reasons)]

    # 4. Generate summary headline
    if decision == TradeabilityDecision.TRADEABLE:
        summary = (
            f"{symbol} at Rs. {price:,.2f} presents a {direction.value.replace('_', ' ')} opportunity "
            f"(Score: {opp_score:.0f}/100, Confidence: {confidence.score:.0f}/100) with orderly risk context."
        )
    elif decision == TradeabilityDecision.CAUTION:
        summary = (
            f"{symbol} at Rs. {price:,.2f} displays marginal {direction.value.replace('_', ' ')} conditions "
            f"(Score: {opp_score:.0f}/100, Tradeability: {tradeability_score:.0f}/100); exercise caution due to mixed signals."
        )
    else:
        reason_str = decision_reasons[0] if decision_reasons else "sub-threshold quality"
        summary = (
            f"{symbol} at Rs. {price:,.2f} is marked NO_TRADE ({direction.value.replace('_', ' ')} bias, "
            f"Tradeability: {tradeability_score:.0f}/100) due to {reason_str}."
        )

    return ExplanationReport(
        summary=summary,
        evidence=evidence,
        warnings=warnings,
        no_trade_reasons=formatted_no_trade
    )

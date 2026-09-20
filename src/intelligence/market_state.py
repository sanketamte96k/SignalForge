"""
SignalForge Intelligence Engine — Unified Market State Coordinator
==================================================================
Orchestrates all sub-engines (Trend, Volatility, Momentum, Structure, Session,
Risk, Confidence, Opportunity, and Explanation) to produce complete per-symbol
intelligence and market-wide overviews.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import pandas as pd

from src.intelligence.models import (
    SymbolIntelligence,
    MarketOverview,
    MarketCondition,
    TradeBias,
    TradeabilityDecision,
    VolatilityState,
    StructureState,
    VolatilityDynamics,
)
from src.intelligence.config import IntelligenceConfig
from src.intelligence.trend_engine import calculate_trend_analysis
from src.intelligence.volatility_engine import calculate_volatility_analysis
from src.intelligence.momentum_engine import calculate_momentum_analysis
from src.intelligence.structure_engine import calculate_structure_analysis
from src.intelligence.session_engine import calculate_session_context
from src.intelligence.risk_context import calculate_risk_context
from src.intelligence.confidence_engine import calculate_confidence_analysis
from src.intelligence.opportunity_engine import (
    determine_directional_bias,
    calculate_opportunity_score,
    evaluate_tradeability,
)
from src.intelligence.explanation_engine import generate_explanation_report


def determine_market_condition(
    structure: StructureState,
    vol_dynamics: VolatilityDynamics,
    trend_strength: float
) -> MarketCondition:
    """
    Synthesizes overall market condition regime.
    """
    if structure in (StructureState.BREAKOUT_UP, StructureState.BREAKOUT_DOWN):
        return MarketCondition.BREAKOUT
    if vol_dynamics == VolatilityDynamics.EXPANDING:
        return MarketCondition.VOLATILITY_EXPANSION
    if vol_dynamics == VolatilityDynamics.CONTRACTING:
        return MarketCondition.VOLATILITY_CONTRACTION
    if trend_strength >= 60.0:
        return MarketCondition.TRENDING
    if structure == StructureState.RANGE_STRUCTURE or trend_strength < 35.0:
        return MarketCondition.RANGING
    return MarketCondition.UNCERTAIN


def evaluate_symbol_intelligence(
    symbol: str,
    df: pd.DataFrame,
    config: IntelligenceConfig | None = None
) -> SymbolIntelligence:
    """
    Evaluates complete intelligence state for a single symbol using past-only OHLCV.
    """
    if config is None:
        config = IntelligenceConfig()

    if len(df) == 0:
        raise ValueError(f"Cannot evaluate empty DataFrame for symbol {symbol}")

    # Extract current bar time and price
    timestamp_val = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[-1].get("timestamp", str(pd.Timestamp.now()))
    close_series = df["Close"] if "Close" in df.columns else df["close"]
    current_price = float(close_series.iloc[-1])

    # 1. Run component engines
    trend = calculate_trend_analysis(df)
    volatility = calculate_volatility_analysis(df, thresholds=config.thresholds)
    momentum = calculate_momentum_analysis(df, thresholds=config.thresholds)
    structure = calculate_structure_analysis(df)
    session = calculate_session_context(timestamp_val, thresholds=config.thresholds)

    # 2. Determine consensus directional bias
    direction, dir_reasons = determine_directional_bias(trend, momentum, structure)

    # 3. Contextual risk & confidence
    risk = calculate_risk_context(current_price, direction, volatility, structure)
    confidence = calculate_confidence_analysis(
        direction, trend, momentum, structure, volatility, session
    )

    # 4. Opportunity & Tradeability scoring
    opp = calculate_opportunity_score(
        trend, structure, momentum, volatility, risk, session, config
    )

    tradeability_score, decision, no_trade_reasons, decision_reasons = evaluate_tradeability(
        direction, opp.score, confidence, risk, volatility, session, structure, config
    )

    # 5. Market condition classification
    market_condition = determine_market_condition(
        structure.state, volatility.dynamics, trend.strength
    )

    # 6. Structured explanation report
    explanation = generate_explanation_report(
        symbol=symbol,
        price=current_price,
        direction=direction,
        opp_score=opp.score,
        tradeability_score=tradeability_score,
        confidence=confidence,
        decision=decision,
        no_trade_reasons=no_trade_reasons,
        decision_reasons=decision_reasons,
        trend=trend,
        momentum=momentum,
        structure=structure,
        volatility=volatility,
        risk=risk,
        session=session
    )

    return SymbolIntelligence(
        symbol=symbol,
        timestamp=str(timestamp_val),
        price=round(current_price, 2),
        direction=direction,
        opportunity_score=opp.score,
        tradeability_score=tradeability_score,
        confidence_score=confidence.score,
        risk_level=risk.risk_level,
        decision=decision,
        market_condition=market_condition,
        trend=trend,
        volatility=volatility,
        momentum=momentum,
        structure=structure,
        session=session,
        risk=risk,
        confidence=confidence,
        explanation=explanation
    )


def rank_symbol_opportunities(
    intelligences: List[SymbolIntelligence]
) -> List[SymbolIntelligence]:
    """
    Ranks opportunities prioritizing Tradeable setups with high Opportunity and Confidence scores.
    """
    decision_priority = {
        TradeabilityDecision.TRADEABLE: 2,
        TradeabilityDecision.CAUTION: 1,
        TradeabilityDecision.NO_TRADE: 0,
    }

    return sorted(
        intelligences,
        key=lambda item: (
            decision_priority.get(item.decision, 0),
            item.opportunity_score,
            item.confidence_score,
            item.tradeability_score
        ),
        reverse=True
    )


def evaluate_market_overview(
    symbols_data: Dict[str, pd.DataFrame],
    config: IntelligenceConfig | None = None
) -> MarketOverview:
    """
    Scans a universe of symbols and produces a consolidated MarketOverview report.
    """
    if config is None:
        config = IntelligenceConfig()

    results: List[SymbolIntelligence] = []
    for sym, df_sym in symbols_data.items():
        if len(df_sym) >= 5:
            try:
                intel = evaluate_symbol_intelligence(sym, df_sym, config)
                results.append(intel)
            except Exception:
                continue

    if len(results) == 0:
        return MarketOverview(
            timestamp=str(pd.Timestamp.now()),
            market_condition=MarketCondition.UNCERTAIN,
            market_volatility=VolatilityState.NORMAL,
            number_of_symbols=0,
            bullish_count=0,
            bearish_count=0,
            neutral_count=0,
            tradeable_count=0,
            caution_count=0,
            no_trade_count=0,
            top_opportunities=[]
        )

    ranked = rank_symbol_opportunities(results)
    latest_ts = ranked[0].timestamp if ranked else str(pd.Timestamp.now())

    bullish_cnt = sum(1 for r in results if r.direction == TradeBias.LONG_BIAS)
    bearish_cnt = sum(1 for r in results if r.direction == TradeBias.SHORT_BIAS)
    neutral_cnt = sum(1 for r in results if r.direction == TradeBias.NEUTRAL)

    tradeable_cnt = sum(1 for r in results if r.decision == TradeabilityDecision.TRADEABLE)
    caution_cnt = sum(1 for r in results if r.decision == TradeabilityDecision.CAUTION)
    no_trade_cnt = sum(1 for r in results if r.decision == TradeabilityDecision.NO_TRADE)

    # Predominant market condition
    cond_counts: Dict[MarketCondition, int] = {}
    for r in results:
        cond_counts[r.market_condition] = cond_counts.get(r.market_condition, 0) + 1
    predom_cond = max(cond_counts.items(), key=lambda x: x[1])[0]

    # Predominant volatility state
    vol_counts: Dict[VolatilityState, int] = {}
    for r in results:
        vol_counts[r.volatility.state] = vol_counts.get(r.volatility.state, 0) + 1
    predom_vol = max(vol_counts.items(), key=lambda x: x[1])[0]

    return MarketOverview(
        timestamp=latest_ts,
        market_condition=predom_cond,
        market_volatility=predom_vol,
        number_of_symbols=len(results),
        bullish_count=bullish_cnt,
        bearish_count=bearish_cnt,
        neutral_count=neutral_cnt,
        tradeable_count=tradeable_cnt,
        caution_count=caution_cnt,
        no_trade_count=no_trade_cnt,
        top_opportunities=ranked[:10]
    )

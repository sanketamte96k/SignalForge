"""
SignalForge Intelligence Engine — Data Models
=============================================
Unified typed models, enums, and metric structures for market intelligence,
regimes, confidence, opportunity scoring, and contextual risk.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TrendState(str, Enum):
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


class VolatilityState(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class VolatilityDynamics(str, Enum):
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    STABLE = "STABLE"


class MarketCondition(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    VOLATILITY_CONTRACTION = "VOLATILITY_CONTRACTION"
    UNCERTAIN = "UNCERTAIN"


class TradeBias(str, Enum):
    LONG_BIAS = "LONG_BIAS"
    SHORT_BIAS = "SHORT_BIAS"
    NEUTRAL = "NEUTRAL"


class StructureState(str, Enum):
    BULLISH_STRUCTURE = "BULLISH_STRUCTURE"
    BEARISH_STRUCTURE = "BEARISH_STRUCTURE"
    RANGE_STRUCTURE = "RANGE_STRUCTURE"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    UNCLEAR = "UNCLEAR"


class SessionState(str, Enum):
    OPENING = "OPENING"
    EARLY_SESSION = "EARLY_SESSION"
    MIDDAY = "MIDDAY"
    AFTERNOON = "AFTERNOON"
    CLOSING = "CLOSING"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class TradeabilityDecision(str, Enum):
    TRADEABLE = "TRADEABLE"
    CAUTION = "CAUTION"
    NO_TRADE = "NO_TRADE"


class NoTradeReason(str, Enum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICTING_SIGNALS = "CONFLICTING_SIGNALS"
    WEAK_TREND = "WEAK_TREND"
    RANGE_NO_EDGE = "RANGE_NO_EDGE"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    POOR_RISK_REWARD = "POOR_RISK_REWARD"
    LATE_SESSION = "LATE_SESSION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_QUALITY_WARNING = "DATA_QUALITY_WARNING"


# -----------------------------------------------------------------------------
# Component Analyses
# -----------------------------------------------------------------------------

class TrendAnalysis(BaseModel):
    direction: TradeBias
    state: TrendState
    strength: float = Field(ge=0.0, le=100.0)
    ema9: float
    ema21: float
    ema50: float
    price_to_ema21_pct: float
    ema21_slope: float
    reasons: List[str] = Field(default_factory=list)


class VolatilityAnalysis(BaseModel):
    state: VolatilityState
    dynamics: VolatilityDynamics
    atr: float
    atr_relative_ratio: float
    realized_volatility_pctile: float = Field(ge=0.0, le=100.0)
    range_compression: float
    volatility_quality_score: float = Field(ge=0.0, le=100.0)
    reasons: List[str] = Field(default_factory=list)


class MomentumAnalysis(BaseModel):
    direction: TradeBias
    strength: float = Field(ge=0.0, le=100.0)
    rsi14: float
    return_5m_pct: float
    return_15m_pct: float
    return_30m_pct: float
    roc: float
    reasons: List[str] = Field(default_factory=list)


class StructureAnalysis(BaseModel):
    state: StructureState
    quality_score: float = Field(ge=0.0, le=100.0)
    recent_swing_high: float
    recent_swing_low: float
    distance_to_high_pct: float
    distance_to_low_pct: float
    range_position: float = Field(ge=0.0, le=1.0)
    breakout_state: str
    reasons: List[str] = Field(default_factory=list)


class SessionContext(BaseModel):
    state: SessionState
    timestamp: str
    minutes_from_open: int
    minutes_to_close: int
    session_quality_score: float = Field(ge=0.0, le=100.0)
    reasons: List[str] = Field(default_factory=list)


class RiskContext(BaseModel):
    risk_level: RiskLevel
    suggested_risk_distance: float
    risk_distance_atr_multiple: float
    distance_to_structure: float
    volatility_adjusted_risk: float
    estimated_reward_risk_ratio: float
    risk_quality_score: float = Field(ge=0.0, le=100.0)
    warnings: List[str] = Field(default_factory=list)


class ConfidenceAnalysis(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    agreement_ratio: float = Field(ge=0.0, le=1.0)
    conflicting_factors: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class OpportunityScore(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    weights: Dict[str, float]
    component_scores: Dict[str, float]


class ExplanationReport(BaseModel):
    summary: str
    evidence: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    no_trade_reasons: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Unified Per-Symbol Intelligence Object
# -----------------------------------------------------------------------------

class SymbolIntelligence(BaseModel):
    symbol: str
    timestamp: str
    price: float
    direction: TradeBias
    opportunity_score: float = Field(ge=0.0, le=100.0)
    tradeability_score: float = Field(ge=0.0, le=100.0)
    confidence_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel
    decision: TradeabilityDecision
    market_condition: MarketCondition
    trend: TrendAnalysis
    volatility: VolatilityAnalysis
    momentum: MomentumAnalysis
    structure: StructureAnalysis
    session: SessionContext
    risk: RiskContext
    confidence: ConfidenceAnalysis
    explanation: ExplanationReport


# -----------------------------------------------------------------------------
# Market-Wide Overview
# -----------------------------------------------------------------------------

class MarketOverview(BaseModel):
    timestamp: str
    market_condition: MarketCondition
    market_volatility: VolatilityState
    number_of_symbols: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    tradeable_count: int
    caution_count: int
    no_trade_count: int
    top_opportunities: List[SymbolIntelligence] = Field(default_factory=list)

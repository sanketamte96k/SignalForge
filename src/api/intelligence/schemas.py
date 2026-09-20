"""
SignalForge API — Intelligence Schemas
======================================
Pydantic schemas for the Market Intelligence REST API endpoints.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from src.intelligence.models import (
    TradeBias,
    TradeabilityDecision,
    RiskLevel,
    MarketCondition,
    VolatilityState,
    TrendState,
    StructureState,
    SessionState,
    SymbolIntelligence,
    MarketOverview,
    ExplanationReport,
)


class IntelligenceSummaryItem(BaseModel):
    symbol: str
    price: float
    direction: TradeBias
    opportunity_score: float
    tradeability_score: float
    confidence_score: float
    risk_level: RiskLevel
    decision: TradeabilityDecision
    market_condition: MarketCondition
    trend_state: TrendState
    volatility_state: VolatilityState
    summary: str


class IntelligenceOverviewResponse(BaseModel):
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
    top_opportunities: List[SymbolIntelligence]


class IntelligenceScannerListResponse(BaseModel):
    timestamp: str
    count: int
    items: List[SymbolIntelligence]


class ExplanationResponse(BaseModel):
    symbol: str
    price: float
    direction: TradeBias
    decision: TradeabilityDecision
    summary: str
    evidence: List[str]
    warnings: List[str]
    no_trade_reasons: List[str]


class IntelligenceHistoryPoint(BaseModel):
    timestamp: str
    price: float
    opportunity_score: float
    tradeability_score: float
    confidence_score: float
    decision: TradeabilityDecision
    direction: TradeBias


class IntelligenceHistoryResponse(BaseModel):
    symbol: str
    count: int
    history: List[IntelligenceHistoryPoint]

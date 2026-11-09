"""
SignalForge API — Intelligence Routes
=====================================
FastAPI route handlers for Market Intelligence, Opportunity Scanning,
Decision Explanation, and History endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.core.security import validate_symbol
from src.data.stock_provider import StockDataProvider
from src.intelligence.models import (
    SymbolIntelligence,
    MarketOverview,
    TradeBias,
    TradeabilityDecision,
)
from src.intelligence.market_state import (
    evaluate_symbol_intelligence,
    evaluate_market_overview,
    rank_symbol_opportunities,
)
from src.intelligence.config import IntelligenceConfig
from src.api.intelligence.schemas import (
    IntelligenceOverviewResponse,
    IntelligenceScannerListResponse,
    ExplanationResponse,
    IntelligenceHistoryResponse,
    IntelligenceHistoryPoint,
)

router = APIRouter(
    prefix="/api/intelligence",
    tags=["Intelligence"],
)

_stock_provider = StockDataProvider()
DEFAULT_SYMBOLS = ["RELIANCE", "INFY", "ICICIBANK", "ADANIENT", "ADANIPORTS"]
_config = IntelligenceConfig()


def _load_symbol_dataframe(symbol: str, max_bars: int = 300) -> pd.DataFrame:
    """
    Loads latest OHLCV market data for a given equity symbol from canonical historical storage.
    Validates symbol format and safe-path invariants.
    """
    norm_symbol = symbol.strip().upper()
    if not norm_symbol:
        raise HTTPException(
            status_code=400,
            detail="Symbol cannot be empty.",
        )

    if norm_symbol in {"NIFTY 50", "NIFTY", "^NSEI"}:
        raise HTTPException(
            status_code=400,
            detail="NIFTY 50 is an index. Market Intelligence operates on equity symbols.",
        )

    try:
        validate_symbol(norm_symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}': {exc}",
        ) from exc

    path = _stock_provider.local_path(norm_symbol)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No market data available for symbol '{norm_symbol}'",
        )

    try:
        df = _stock_provider.load(norm_symbol)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to load market data for '{norm_symbol}': {exc}",
        ) from exc

    if df.empty:
        raise HTTPException(
            status_code=503,
            detail=f"Market data for '{norm_symbol}' is empty.",
        )

    if len(df) > max_bars:
        return df.tail(max_bars).copy()
    return df.copy()


@router.get("/overview", response_model=IntelligenceOverviewResponse)
def get_market_overview() -> IntelligenceOverviewResponse:
    """
    Scans the primary universe and returns a consolidated market-wide intelligence overview.
    """
    universe_data: Dict[str, pd.DataFrame] = {}
    for sym in DEFAULT_SYMBOLS:
        try:
            df_sym = _load_symbol_dataframe(sym, max_bars=150)
            universe_data[sym] = df_sym
        except Exception:
            continue

    overview = evaluate_market_overview(universe_data, _config)
    return IntelligenceOverviewResponse(
        timestamp=overview.timestamp,
        market_condition=overview.market_condition,
        market_volatility=overview.market_volatility,
        number_of_symbols=overview.number_of_symbols,
        bullish_count=overview.bullish_count,
        bearish_count=overview.bearish_count,
        neutral_count=overview.neutral_count,
        tradeable_count=overview.tradeable_count,
        caution_count=overview.caution_count,
        no_trade_count=overview.no_trade_count,
        top_opportunities=overview.top_opportunities,
    )


@router.get("", response_model=IntelligenceScannerListResponse)
def list_scanned_opportunities(
    decision: Optional[TradeabilityDecision] = None,
    bias: Optional[TradeBias] = None,
    min_opportunity: float = Query(0.0, ge=0.0, le=100.0)
) -> IntelligenceScannerListResponse:
    """
    Returns all scanned universe symbols ranked by opportunity and tradeability.
    """
    min_opp_val = (
        float(min_opportunity.default)
        if hasattr(min_opportunity, "default") and isinstance(min_opportunity.default, (int, float))
        else float(min_opportunity)
    )

    results: List[SymbolIntelligence] = []
    latest_ts = str(pd.Timestamp.now())

    for sym in DEFAULT_SYMBOLS:
        try:
            df_sym = _load_symbol_dataframe(sym, max_bars=150)
            intel = evaluate_symbol_intelligence(sym, df_sym, _config)
            latest_ts = intel.timestamp

            # Apply query filters
            if decision and intel.decision != decision:
                continue
            if bias and intel.direction != bias:
                continue
            if intel.opportunity_score < min_opp_val:
                continue

            results.append(intel)
        except Exception:
            continue

    ranked = rank_symbol_opportunities(results)
    return IntelligenceScannerListResponse(
        timestamp=latest_ts,
        count=len(ranked),
        items=ranked
    )


@router.get("/{symbol}", response_model=SymbolIntelligence)
def get_symbol_intelligence(symbol: str) -> SymbolIntelligence:
    """
    Returns comprehensive causal intelligence, scores, and risk context for a specific symbol.
    """
    df = _load_symbol_dataframe(symbol, max_bars=200)
    return evaluate_symbol_intelligence(symbol.upper(), df, _config)


@router.get("/{symbol}/explanation", response_model=ExplanationResponse)
def get_symbol_explanation(symbol: str) -> ExplanationResponse:
    """
    Returns structured human-readable explanation, evidence facts, and warnings for a symbol.
    """
    intel = get_symbol_intelligence(symbol)
    return ExplanationResponse(
        symbol=intel.symbol,
        price=intel.price,
        direction=intel.direction,
        decision=intel.decision,
        summary=intel.explanation.summary,
        evidence=intel.explanation.evidence,
        warnings=intel.explanation.warnings,
        no_trade_reasons=intel.explanation.no_trade_reasons,
    )


@router.get("/{symbol}/history", response_model=IntelligenceHistoryResponse)
def get_symbol_intelligence_history(
    symbol: str,
    bars: int = Query(60, ge=10, le=200),
    step: int = Query(5, ge=1, le=15)
) -> IntelligenceHistoryResponse:
    """
    Returns a causal historical progression of intelligence evaluations over recent bars.
    Evaluates strictly with historical slices up to each evaluation timestamp (zero lookahead).
    """
    bars_val = (
        int(bars.default)
        if hasattr(bars, "default") and isinstance(bars.default, int)
        else int(bars)
    )
    step_val = (
        int(step.default)
        if hasattr(step, "default") and isinstance(step.default, int)
        else int(step)
    )

    df = _load_symbol_dataframe(symbol, max_bars=bars_val + 50)
    history_points: List[IntelligenceHistoryPoint] = []

    # Slide window backwards
    total_len = len(df)
    indices = range(max(50, total_len - bars_val), total_len, step_val)

    for idx in indices:
        slice_df = df.iloc[:idx].copy()
        if len(slice_df) < 20:
            continue
        intel = evaluate_symbol_intelligence(symbol.upper(), slice_df, _config)
        history_points.append(IntelligenceHistoryPoint(
            timestamp=intel.timestamp,
            price=intel.price,
            opportunity_score=intel.opportunity_score,
            tradeability_score=intel.tradeability_score,
            confidence_score=intel.confidence_score,
            decision=intel.decision,
            direction=intel.direction
        ))

    return IntelligenceHistoryResponse(
        symbol=symbol.upper(),
        count=len(history_points),
        history=history_points
    )

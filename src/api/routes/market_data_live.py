"""
SignalForge — Phase 30: Live Market Data Ingestion & Telemetry Routes
=====================================================================
File: src/api/routes/market_data_live.py

Endpoints:
- GET  /api/market-data/live/status
- GET  /api/market-data/live/telemetry
- GET  /api/market-data/live/symbols/{symbol}/health
- POST /api/market-data/live/ingest/quote
- POST /api/market-data/live/ingest/candle
- POST /api/market-data/live/disconnect
- POST /api/market-data/live/reset
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path, status

from src.api.models import (
    LiveCandleIngestRequest,
    LiveMarketDataStatusResponse,
    LiveQuoteIngestRequest,
    SymbolLiveHealthResponse,
)
from src.market_data.live_adapter import (
    DataQualityState,
    FeedType,
    LiveMarketCandle,
    LiveMarketQuote,
    ProviderNeutralMarketDataAdapter,
)

router = APIRouter(prefix="/api/market-data/live", tags=["live-market-data"])

_live_adapter: ProviderNeutralMarketDataAdapter | None = None


def get_live_adapter() -> ProviderNeutralMarketDataAdapter:
    """Return the active provider-neutral market data adapter singleton."""
    global _live_adapter
    if _live_adapter is None:
        _live_adapter = ProviderNeutralMarketDataAdapter(
            source_id="provider_neutral_adapter",
            default_feed_type=FeedType.SYNTHETIC,
            stale_threshold_seconds=60.0,
            delayed_threshold_seconds=300.0,
            recovery_required_bars=3,
        )
    return _live_adapter


def reset_live_adapter() -> ProviderNeutralMarketDataAdapter:
    """Reset the adapter singleton for clean isolation in tests."""
    global _live_adapter
    _live_adapter = ProviderNeutralMarketDataAdapter(
        source_id="provider_neutral_adapter",
        default_feed_type=FeedType.SYNTHETIC,
        stale_threshold_seconds=60.0,
        delayed_threshold_seconds=300.0,
        recovery_required_bars=3,
    )
    return _live_adapter


@router.get(
    "/status",
    response_model=LiveMarketDataStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_live_market_data_status() -> LiveMarketDataStatusResponse:
    """Return system-level live market data telemetry and provider health status."""
    adapter = get_live_adapter()
    adapter.evaluate_staleness()
    summary = adapter.get_telemetry_summary()
    return LiveMarketDataStatusResponse(**summary)


@router.get(
    "/telemetry",
    status_code=status.HTTP_200_OK,
)
def get_live_market_data_telemetry() -> Dict[str, Any]:
    """Return full detailed latency and data-quality telemetry report."""
    adapter = get_live_adapter()
    adapter.evaluate_staleness()
    return adapter.get_telemetry_summary()


@router.get(
    "/symbols/{symbol}/health",
    response_model=SymbolLiveHealthResponse,
    status_code=status.HTTP_200_OK,
)
def get_symbol_live_health(
    symbol: str = Path(..., description="NSE Stock Symbol"),
) -> SymbolLiveHealthResponse:
    """Return health, latency, and quality telemetry for an individual symbol stream."""
    adapter = get_live_adapter()
    adapter.evaluate_staleness()
    clean_sym = symbol.strip().upper()
    summary = adapter.get_telemetry_summary()
    sym_data = summary["symbols"].get(clean_sym)
    if not sym_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_sym}' not registered in live market data stream.",
        )
    return SymbolLiveHealthResponse(**sym_data)


@router.post(
    "/ingest/quote",
    status_code=status.HTTP_200_OK,
)
def ingest_live_quote(payload: LiveQuoteIngestRequest) -> Dict[str, Any]:
    """Ingest a live quote update into the provider-neutral adapter."""
    adapter = get_live_adapter()
    now = datetime.now(timezone.utc)
    event_ts = payload.event_timestamp or now

    feed_type_enum = FeedType.SYNTHETIC
    try:
        feed_type_enum = FeedType(payload.feed_type.upper())
    except Exception:
        pass

    try:
        quote = LiveMarketQuote(
            symbol=payload.symbol,
            exchange=payload.exchange,
            ltp=payload.ltp,
            volume=payload.volume,
            bid=payload.bid,
            ask=payload.ask,
            bid_qty=payload.bid_qty,
            ask_qty=payload.ask_qty,
            event_timestamp=event_ts,
            receive_timestamp=now,
            quality_state=DataQualityState.CONNECTED,
            source_id=payload.source_id,
            feed_type=feed_type_enum,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    success, reason, latency = adapter.ingest_quote(quote)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason or "Quote validation failed",
        )

    return {
        "status": "INGESTED",
        "symbol": payload.symbol.upper(),
        "reason": reason,
        "latency": latency.to_dict() if latency else None,
    }


@router.post(
    "/ingest/candle",
    status_code=status.HTTP_200_OK,
)
def ingest_live_candle(payload: LiveCandleIngestRequest) -> Dict[str, Any]:
    """Ingest an OHLCV candle update into the provider-neutral adapter."""
    adapter = get_live_adapter()
    now = datetime.now(timezone.utc)
    event_ts = payload.event_timestamp or now
    candle_ts = payload.candle_timestamp or event_ts

    feed_type_enum = FeedType.SYNTHETIC
    try:
        feed_type_enum = FeedType(payload.feed_type.upper())
    except Exception:
        pass

    try:
        candle = LiveMarketCandle(
            symbol=payload.symbol,
            exchange=payload.exchange,
            timeframe=payload.timeframe,
            open=payload.open,
            high=payload.high,
            low=payload.low,
            close=payload.close,
            volume=payload.volume,
            candle_timestamp=candle_ts,
            is_closed=payload.is_closed,
            event_timestamp=event_ts,
            receive_timestamp=now,
            quality_state=DataQualityState.CONNECTED,
            source_id=payload.source_id,
            feed_type=feed_type_enum,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    success, reason, latency = adapter.ingest_candle(candle)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason or "Candle validation failed",
        )

    return {
        "status": "INGESTED",
        "symbol": payload.symbol.upper(),
        "is_closed": payload.is_closed,
        "reason": reason,
        "latency": latency.to_dict() if latency else None,
    }


@router.post(
    "/disconnect",
    status_code=status.HTTP_200_OK,
)
def trigger_outage_disconnect() -> Dict[str, Any]:
    """Simulate a feed outage / network disconnect for validation testing."""
    adapter = get_live_adapter()
    adapter.force_disconnect(reason="Manual test trigger")
    return {
        "status": "DISCONNECTED",
        "global_state": adapter.global_state.value,
        "simulation_only": True,
    }


@router.post(
    "/reset",
    status_code=status.HTTP_200_OK,
)
def reset_adapter_state() -> Dict[str, Any]:
    """Reset live adapter state for testing."""
    adapter = reset_live_adapter()
    return {
        "status": "RESET",
        "global_state": adapter.global_state.value,
        "simulation_only": True,
    }

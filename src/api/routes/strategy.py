"""Strategy state API routes."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.models import StrategySignalResponse
from src.api.routes.nifty import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    _build_strategy_signal,
    _load_nifty_data,
)
from src.data.downloader import load_market_data
from src.data.stock_provider import StockDataProvider


router = APIRouter(
    prefix="/api/strategy",
    tags=["strategy"],
)

_stock_provider = StockDataProvider()


@router.get(
    "/signal",
    response_model=StrategySignalResponse,
)
def get_strategy_signal(
    symbol: str = Query("NIFTY 50"),
    timeframe: str = Query("15m"),
) -> StrategySignalResponse:
    """Return the current strategy state for a symbol and timeframe."""
    normalized_symbol = symbol.strip().upper()

    if not normalized_symbol:
        raise HTTPException(
            status_code=400,
            detail="Symbol cannot be empty.",
        )

    if timeframe not in SUPPORTED_STRATEGY_TIMEFRAMES:
        supported = ", ".join(SUPPORTED_STRATEGY_TIMEFRAMES)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported strategy timeframe: '{timeframe}'. "
                f"Supported: {supported}."
            ),
        )

    if normalized_symbol in {"NIFTY 50", "NIFTY", "^NSEI"}:
        data = _load_nifty_data()
        return _build_strategy_signal(data, "NIFTY 50", timeframe)

    path = _stock_provider.local_path(normalized_symbol)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Historical data not available for symbol '{normalized_symbol}'.",
        )

    try:
        data = load_market_data(path)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to load data for {normalized_symbol}: {exc}",
        ) from exc

    if data.empty:
        raise HTTPException(
            status_code=503,
            detail=f"Market data for {normalized_symbol} is empty.",
        )

    return _build_strategy_signal(data, normalized_symbol, timeframe)

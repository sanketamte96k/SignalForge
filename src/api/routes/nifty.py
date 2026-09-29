"""NIFTY 50 API routes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
import math
from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    BaseIndicatorsResponse,
    NiftyAnalysisResponse,
    NiftyChartCandle,
    NiftyChartResponse,
    NiftyLatestResponse,
    NiftySignalResponse,
    SignalAnalysisDetail,
    StrategyConfirmation,
    StrategyIndicators,
    StrategySignalResponse,
    TimeframeDetail,
)
from src.data.downloader import load_market_data
from src.data.resampler import resample_ohlcv
from src.indicators.indicators import calculate_rsi
from src.signals.signal_engine import SignalResult
from src.strategy.causal_timeframe_indicators import TimeframeIndicatorState
from src.strategy.context import CausalStrategyContext
from src.strategy.signal_rules import (
    Direction,
    momentum_support,
    trend_direction,
    volume_support,
)


router = APIRouter(
    prefix="/api/nifty",
    tags=["nifty"],
)


DATA_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

STRATEGY_WARMUP_CANDLES = 2000
SUPPORTED_CHART_TIMEFRAMES = {"1m", "5m", "10m", "15m", "30m"}
SUPPORTED_STRATEGY_TIMEFRAMES = ("5m", "10m", "15m", "30m")
MAX_CHART_CANDLES = 500


@dataclass(frozen=True)
class NiftyEngineState:
    """Consolidated state from causal engine processing."""

    candle: pd.Series
    position: str | None
    signal: str
    signal_result: SignalResult | None
    timeframe_states: dict[str, TimeframeIndicatorState]


@lru_cache(maxsize=1)
def _load_nifty_data() -> pd.DataFrame:
    """Load and cache the validated NIFTY 50 historical dataset."""
    try:
        data = load_market_data(DATA_PATH)

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to load NIFTY 50 market data: {exc}",
        ) from exc

    if data.empty:
        raise HTTPException(
            status_code=503,
            detail="NIFTY 50 market data is empty.",
        )

    return data


def _process_recent_history(
    data: pd.DataFrame,
) -> NiftyEngineState:
    """Process a bounded recent history window causally."""
    if data.empty:
        raise HTTPException(
            status_code=503,
            detail="NIFTY 50 market data is empty.",
        )

    recent_data = data.tail(
        STRATEGY_WARMUP_CANDLES
    ).copy()

    context = CausalStrategyContext()

    latest_candle: pd.Series | None = None
    latest_position = None

    for timestamp, candle in recent_data.iterrows():
        candle = candle.copy()
        candle.name = timestamp

        result = context.process_candle(candle)

        latest_candle = candle
        latest_position = result.position

    if latest_candle is None:
        raise HTTPException(
            status_code=503,
            detail="Unable to process NIFTY 50 market data.",
        )

    position_value = (
        latest_position.value
        if latest_position is not None
        else None
    )

    signal = _position_to_signal(position_value)

    return NiftyEngineState(
        candle=latest_candle,
        position=position_value,
        signal=signal,
        signal_result=context.last_signal_result,
        timeframe_states=context.latest_timeframe_states,
    )


def _position_to_signal(
    position: str | None,
) -> str:
    """Convert a strategy position to the public API signal."""
    if position == "LONG":
        return "BUY"

    if position == "SHORT":
        return "SELL"

    return "NO_TRADE"


def _build_chart_data(
    data: pd.DataFrame,
    timeframe: str,
    limit: int,
) -> NiftyChartResponse:
    """Build real chart candles and a backend-calculated RSI(14) series."""
    if timeframe == "1m":
        chart_data = data.copy()
    else:
        try:
            chart_data = resample_ohlcv(data, timeframe)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    if chart_data.empty:
        raise HTTPException(
            status_code=503,
            detail=f"No complete NIFTY 50 candles available for {timeframe}.",
        )

    # Calculate RSI on the selected timeframe's close series before taking
    # the display tail. This preserves the full warm-up history instead of
    # resetting RSI at the left edge of the chart.
    rsi_series = calculate_rsi(
        chart_data["close"],
        period=14,
    )

    display_data = chart_data.tail(limit).copy()
    display_rsi = rsi_series.loc[display_data.index]

    candles: list[NiftyChartCandle] = []
    for timestamp, row in display_data.iterrows():
        rsi_value = display_rsi.loc[timestamp]
        candles.append(
            NiftyChartCandle(
                timestamp=pd.Timestamp(timestamp).to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                rsi14=(
                    round(float(rsi_value), 4)
                    if pd.notna(rsi_value)
                    else None
                ),
            )
        )

    return NiftyChartResponse(
        symbol="NIFTY 50",
        timeframe=timeframe,
        candles=candles,
    )


@router.get(
    "/latest",
    response_model=NiftyLatestResponse,
)
def get_latest_nifty() -> NiftyLatestResponse:
    """Return the latest available NIFTY 50 candle."""
    data = _load_nifty_data()

    candle = data.iloc[-1]
    timestamp = data.index[-1]

    return NiftyLatestResponse(
        symbol="NIFTY 50",
        timestamp=timestamp.to_pydatetime(),
        open=float(candle["open"]),
        high=float(candle["high"]),
        low=float(candle["low"]),
        close=float(candle["close"]),
        volume=float(candle["volume"]),
    )


def _sanitize_float(val: float | int | None) -> float | None:
    """Sanitize float values, guarding against NaN and Infinity."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def _build_strategy_signal(
    data: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> NiftySignalResponse:
    """Build authoritative strategy signal response without lookahead."""
    if timeframe not in SUPPORTED_STRATEGY_TIMEFRAMES:
        supported = ", ".join(SUPPORTED_STRATEGY_TIMEFRAMES)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported strategy timeframe: '{timeframe}'. "
                f"Supported: {supported}."
            ),
        )

    state = _process_recent_history(data)
    timestamp = pd.Timestamp(state.candle.name)
    current_price = _sanitize_float(state.candle["close"])
    if current_price is None:
        current_price = 0.0

    tf_state = state.timeframe_states.get(timeframe)
    if tf_state is not None:
        ind = tf_state.indicators
        ema_fast = _sanitize_float(ind.ema_fast)
        ema_slow = _sanitize_float(ind.ema_slow)
        rsi_val = _sanitize_float(ind.rsi)
        atr_val = _sanitize_float(ind.atr)
        volume_val = (
            _sanitize_float(ind.rvol)
            if (ind.rvol is not None and ind.rvol > 0)
            else (_sanitize_float(state.candle["volume"]) if state.candle["volume"] > 0 else None)
        )
    else:
        ind = None
        ema_fast = ema_slow = rsi_val = atr_val = volume_val = None

    indicators = StrategyIndicators(
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi=rsi_val,
        atr=atr_val,
        volume=volume_val,
        vwap=None,
    )

    sig_res = state.signal_result
    signal = state.signal

    # EMA confirmation
    if tf_state is not None and ind is not None and ind.ema_fast is not None and ind.ema_slow is not None:
        if signal == "BUY":
            ema_confirmed = tf_state.close > ind.ema_fast > ind.ema_slow
        elif signal == "SELL":
            ema_confirmed = tf_state.close < ind.ema_fast < ind.ema_slow
        else:
            ema_confirmed = False
    else:
        ema_confirmed = None

    # RSI confirmation
    if rsi_val is not None:
        if signal == "BUY":
            rsi_confirmed = momentum_support(Direction.LONG, rsi_val)
        elif signal == "SELL":
            rsi_confirmed = momentum_support(Direction.SHORT, rsi_val)
        else:
            rsi_confirmed = False
    else:
        rsi_confirmed = None

    # Volume confirmation: only if RVOL is usable and available
    if tf_state is not None and ind is not None and ind.rvol is not None and ind.rvol > 0:
        volume_confirmed = volume_support(ind.rvol, minimum_rvol=1.5)
    else:
        volume_confirmed = None

    # Multi-timeframe confirmation
    if sig_res is not None:
        mtf_confirmed = (sig_res.timeframe_alignment == 4 and signal != "NO_TRADE")
    else:
        mtf_confirmed = False

    confirmation = StrategyConfirmation(
        ema=ema_confirmed,
        rsi_momentum=rsi_confirmed,
        volume=volume_confirmed,
        multi_timeframe=mtf_confirmed,
    )

    if sig_res is not None:
        signal_reason = sig_res.reason
        confidence = _sanitize_float(sig_res.confidence)
    else:
        signal_reason = "Warm-up incomplete or indicators unavailable."
        confidence = 0.0

    # Risk geometry & execution brackets
    if signal in ("BUY", "SELL") and atr_val is not None and atr_val > 0:
        risk_distance = max(round(atr_val * 1.5, 2), 0.5)
        entry_price = current_price
        if signal == "BUY":
            stop_loss = round(entry_price - risk_distance, 2)
            target_1 = round(entry_price + (risk_distance * 1.5), 2)
            target_2 = round(entry_price + (risk_distance * 2.0), 2)
        else:
            stop_loss = round(entry_price + risk_distance, 2)
            target_1 = round(entry_price - (risk_distance * 1.5), 2)
            target_2 = round(entry_price - (risk_distance * 2.0), 2)
    else:
        entry_price = None
        stop_loss = None
        target_1 = None
        target_2 = None

    return NiftySignalResponse(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp.to_pydatetime(),
        signal=signal,
        signal_reason=signal_reason,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        confidence=confidence,
        indicators=indicators,
        confirmation=confirmation,
        status="HISTORICAL",
        position=state.position,
        price=current_price,
        strategy="SignalForge",
    )


@router.get(
    "/signal",
    response_model=NiftySignalResponse,
)
def get_nifty_signal(
    timeframe: str = Query("15m"),
) -> NiftySignalResponse:
    """Return the latest SignalForge NIFTY 50 strategy signal."""
    data = _load_nifty_data()
    return _build_strategy_signal(data, "NIFTY 50", timeframe)


@router.get(
    "/analysis",
    response_model=NiftyAnalysisResponse,
)
def get_nifty_analysis() -> NiftyAnalysisResponse:
    """Return the complete latest SignalForge NIFTY 50 analysis."""
    data = _load_nifty_data()

    state = _process_recent_history(data)

    timestamp = pd.Timestamp(state.candle.name)

    sig_res = state.signal_result
    if sig_res is not None:
        analysis_detail = SignalAnalysisDetail(
            score=sig_res.score,
            confidence=sig_res.confidence,
            reason=sig_res.reason,
            timeframe_alignment=sig_res.timeframe_alignment,
        )
    else:
        analysis_detail = SignalAnalysisDetail(
            score=0,
            confidence=0.0,
            reason="Warm-up incomplete or indicators unavailable.",
            timeframe_alignment=0,
        )

    timeframes_dict: dict[str, TimeframeDetail] = {}
    supported_timeframes = ("5m", "10m", "15m", "30m")

    for tf in supported_timeframes:
        if tf in state.timeframe_states:
            tf_state = state.timeframe_states[tf]
            ind = tf_state.indicators
            is_ready = (
                ind.ema_fast is not None
                and ind.ema_slow is not None
                and ind.rsi is not None
                and ind.atr is not None
            )
            trend_val = (
                trend_direction(
                    tf_state.close,
                    ind.ema_fast,
                    ind.ema_slow,
                ).value
                if is_ready
                else None
            )

            timeframes_dict[tf] = TimeframeDetail(
                timeframe=tf,
                timestamp=tf_state.timestamp.to_pydatetime(),
                close=round(float(tf_state.close), 2),
                ema20=(
                    round(float(ind.ema_fast), 2)
                    if ind.ema_fast is not None
                    else None
                ),
                ema50=(
                    round(float(ind.ema_slow), 2)
                    if ind.ema_slow is not None
                    else None
                ),
                rsi14=(
                    round(float(ind.rsi), 2)
                    if ind.rsi is not None
                    else None
                ),
                atr14=(
                    round(float(ind.atr), 2)
                    if ind.atr is not None
                    else None
                ),
                rvol20=(
                    round(float(ind.rvol), 2)
                    if ind.rvol is not None
                    else None
                ),
                trend=trend_val,
                ready=is_ready,
            )
        else:
            timeframes_dict[tf] = TimeframeDetail(
                timeframe=tf,
                timestamp=None,
                close=None,
                ema20=None,
                ema50=None,
                rsi14=None,
                atr14=None,
                rvol20=None,
                trend=None,
                ready=False,
            )

    return NiftyAnalysisResponse(
        symbol="NIFTY 50",
        timestamp=timestamp.to_pydatetime(),
        price=float(state.candle["close"]),
        signal=state.signal,
        position=state.position,
        strategy="SignalForge",
        analysis=analysis_detail,
        indicators=BaseIndicatorsResponse(),
        timeframes=timeframes_dict,
    )


@router.get(
    "/chart",
    response_model=NiftyChartResponse,
)
def get_nifty_chart(
    timeframe: str = Query("5m"),
    limit: int = Query(200, ge=1, le=MAX_CHART_CANDLES),
) -> NiftyChartResponse:
    """Return real NIFTY 50 OHLCV candles plus backend RSI(14)."""
    if timeframe not in SUPPORTED_CHART_TIMEFRAMES:
        supported = ", ".join(sorted(SUPPORTED_CHART_TIMEFRAMES))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported chart timeframe: {timeframe}. "
                f"Supported: {supported}."
            ),
        )

    data = _load_nifty_data()
    return _build_chart_data(data, timeframe, limit)

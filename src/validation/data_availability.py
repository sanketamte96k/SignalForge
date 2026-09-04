from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.data.resampler import SUPPORTED_TIMEFRAMES, resample_ohlcv
from src.data.session import prepare_market_session
from src.market_data.adapter import (
    MarketDataValidationError,
    validate_market_data,
)


DEFAULT_REQUIRED_TIMEFRAMES = tuple(SUPPORTED_TIMEFRAMES.keys())


@dataclass(frozen=True)
class DataAvailabilityResult:
    """Result of the historical-data availability check."""

    available: bool
    candle_count: int
    session_count: int
    first_timestamp: pd.Timestamp | None
    last_timestamp: pd.Timestamp | None
    timeframe_candle_counts: dict[str, int]
    required_timeframes: tuple[str, ...]
    minimum_candles: int
    minimum_sessions: int
    reasons: tuple[str, ...]

    @property
    def has_data(self) -> bool:
        """Return whether at least one usable candle exists."""
        return self.candle_count > 0


class DataAvailabilityChecker:
    """
    Check whether historical OHLCV data is sufficient to begin
    SignalForge stock validation.

    This stage only checks data availability. It does not determine
    whether the trading strategy is profitable or whether an
    instrument should become signal-eligible.
    """

    def __init__(
        self,
        minimum_candles: int = 1,
        minimum_sessions: int = 1,
        required_timeframes: tuple[str, ...] = DEFAULT_REQUIRED_TIMEFRAMES,
    ) -> None:
        if (
            not isinstance(minimum_candles, int)
            or isinstance(minimum_candles, bool)
        ):
            raise TypeError(
                "minimum_candles must be an integer."
            )

        if minimum_candles < 1:
            raise ValueError(
                "minimum_candles must be at least 1."
            )

        if (
            not isinstance(minimum_sessions, int)
            or isinstance(minimum_sessions, bool)
        ):
            raise TypeError(
                "minimum_sessions must be an integer."
            )

        if minimum_sessions < 1:
            raise ValueError(
                "minimum_sessions must be at least 1."
            )

        if not isinstance(required_timeframes, tuple):
            raise TypeError(
                "required_timeframes must be a tuple."
            )

        if not required_timeframes:
            raise ValueError(
                "required_timeframes must not be empty."
            )

        invalid_timeframes = [
            timeframe
            for timeframe in required_timeframes
            if timeframe not in SUPPORTED_TIMEFRAMES
        ]

        if invalid_timeframes:
            raise ValueError(
                "Unsupported required timeframes: "
                f"{invalid_timeframes}. "
                f"Supported: {list(SUPPORTED_TIMEFRAMES)}"
            )

        if len(set(required_timeframes)) != len(
            required_timeframes
        ):
            raise ValueError(
                "required_timeframes must not contain duplicates."
            )

        self.minimum_candles = minimum_candles
        self.minimum_sessions = minimum_sessions
        self.required_timeframes = required_timeframes

    def check(
        self,
        data: pd.DataFrame,
    ) -> DataAvailabilityResult:
        """
        Check historical OHLCV data availability.

        The input is first passed through the existing market-data
        validation layer, then restricted to the regular market
        session before availability is measured.
        """

        reasons: list[str] = []

        try:
            validated = validate_market_data(data)
        except (
            TypeError,
            MarketDataValidationError,
        ) as exc:
            return DataAvailabilityResult(
                available=False,
                candle_count=0,
                session_count=0,
                first_timestamp=None,
                last_timestamp=None,
                timeframe_candle_counts={
                    timeframe: 0
                    for timeframe in self.required_timeframes
                },
                required_timeframes=self.required_timeframes,
                minimum_candles=self.minimum_candles,
                minimum_sessions=self.minimum_sessions,
                reasons=(str(exc),),
            )

        session_data = prepare_market_session(
            validated
        )

        candle_count = len(session_data)

        if candle_count == 0:
            reasons.append(
                "No usable candles exist inside the market session."
            )

        if candle_count < self.minimum_candles:
            reasons.append(
                "Insufficient 1-minute candle history: "
                f"{candle_count} available, "
                f"{self.minimum_candles} required."
            )

        session_count = self._count_sessions(
            session_data
        )

        if session_count < self.minimum_sessions:
            reasons.append(
                "Insufficient trading-session history: "
                f"{session_count} available, "
                f"{self.minimum_sessions} required."
            )

        timeframe_candle_counts: dict[str, int] = {}

        for timeframe in self.required_timeframes:
            if session_data.empty:
                count = 0
            else:
                count = len(
                    resample_ohlcv(
                        session_data,
                        timeframe,
                    )
                )

            timeframe_candle_counts[timeframe] = count

            if count == 0:
                reasons.append(
                    f"No complete {timeframe} candles are available."
                )

        first_timestamp = (
            session_data.index[0]
            if not session_data.empty
            else None
        )

        last_timestamp = (
            session_data.index[-1]
            if not session_data.empty
            else None
        )

        return DataAvailabilityResult(
            available=not reasons,
            candle_count=candle_count,
            session_count=session_count,
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            timeframe_candle_counts=timeframe_candle_counts,
            required_timeframes=self.required_timeframes,
            minimum_candles=self.minimum_candles,
            minimum_sessions=self.minimum_sessions,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _count_sessions(
        data: pd.DataFrame,
    ) -> int:
        """Count unique calendar dates represented by usable candles."""

        if data.empty:
            return 0

        dates: set[date] = {
            timestamp.date()
            for timestamp in data.index
        }

        return len(dates)

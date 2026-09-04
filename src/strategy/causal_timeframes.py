"""Causal timeframe construction for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


SUPPORTED_TIMEFRAMES = {
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
}

REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True)
class CompletedCandle:
    """A completed higher-timeframe candle."""

    timeframe: str
    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float


class CausalTimeframeBuilder:
    """
    Build higher-timeframe candles causally from incoming 1-minute candles.

    Only candles that are fully completed are emitted.

    Source candles must arrive chronologically.

    Duplicate timestamps are ignored.

    Out-of-order timestamps are rejected.

    A higher-timeframe candle is emitted only when all expected
    consecutive 1-minute timestamps for its bucket have been received.

    Trading-session boundaries are treated as normal boundaries and
    do not require overnight minute continuity.
    """

    def __init__(
        self,
        timeframe: str | None = None,
    ) -> None:
        if timeframe is not None:
            if timeframe not in SUPPORTED_TIMEFRAMES:
                raise ValueError(
                    f"Unsupported timeframe: {timeframe}"
                )

            self._timeframes = {
                timeframe: SUPPORTED_TIMEFRAMES[timeframe]
            }
        else:
            self._timeframes = dict(SUPPORTED_TIMEFRAMES)

        self._buffers: dict[str, list[pd.Series]] = {
            tf: []
            for tf in self._timeframes
        }

        self._current_bucket: dict[
            str,
            pd.Timestamp | None,
        ] = {
            tf: None
            for tf in self._timeframes
        }

        self._last_timestamp: pd.Timestamp | None = None

    @property
    def buffers(self) -> dict[str, list[pd.Series]]:
        """Return a defensive copy of the current buffers."""

        return {
            timeframe: list(candles)
            for timeframe, candles in self._buffers.items()
        }

    def reset(self) -> None:
        """Reset all timeframe construction state."""

        self._buffers = {
            tf: []
            for tf in self._timeframes
        }

        self._current_bucket = {
            tf: None
            for tf in self._timeframes
        }

        self._last_timestamp = None

    def process_candle(
        self,
        candle: pd.Series,
    ) -> dict[str, CompletedCandle]:
        """
        Process exactly one new 1-minute candle.

        Returns only timeframe candles that became complete because
        of this source candle.

        Duplicate timestamps are ignored.

        Raises:
            ValueError:
                If the source timestamp arrives out of order.
        """

        self._validate_candle(candle)

        if candle.name is None and "timestamp" in candle.index:
            candle = candle.copy()
            candle.name = pd.Timestamp(
                candle["timestamp"]
            )

        timestamp = pd.Timestamp(candle.name)

        if self._last_timestamp is not None:
            if timestamp < self._last_timestamp:
                raise ValueError(
                    "candle timestamp must be strictly increasing; "
                    "out-of-order timestamp received."
                )

            if timestamp == self._last_timestamp:
                return {}

        completed: dict[str, CompletedCandle] = {}

        for timeframe, minutes in self._timeframes.items():
            bucket = self._bucket_start(
                timestamp,
                minutes,
            )

            current_bucket = self._current_bucket[timeframe]

            if current_bucket is None:
                self._current_bucket[timeframe] = bucket

            elif bucket != current_bucket:
                # The previous bucket did not receive all of its
                # expected source candles, so it is incomplete and
                # must never be emitted.
                self._buffers[timeframe] = []
                self._current_bucket[timeframe] = bucket

            self._buffers[timeframe].append(
                candle.copy()
            )

            if self._is_complete(
                timeframe=timeframe,
                candles=self._buffers[timeframe],
            ):
                completed_candle = self._build_completed_candle(
                    timeframe=timeframe,
                    candles=self._buffers[timeframe],
                )

                completed[timeframe] = completed_candle

                self._buffers[timeframe] = []

                self._current_bucket[timeframe] = None

        self._last_timestamp = timestamp

        return completed

    @staticmethod
    def _is_complete(
        timeframe: str,
        candles: list[pd.Series],
    ) -> bool:
        """
        Return True only when the buffer contains exactly the expected
        consecutive source timestamps for its timeframe.
        """

        expected_minutes = SUPPORTED_TIMEFRAMES[timeframe]

        if len(candles) != expected_minutes:
            return False

        timestamps = [
            pd.Timestamp(candle.name)
            for candle in candles
        ]

        expected = pd.date_range(
            start=timestamps[0],
            periods=expected_minutes,
            freq="min",
        )

        return timestamps == list(expected)

    @staticmethod
    def _bucket_start(
        timestamp: pd.Timestamp,
        minutes: int,
    ) -> pd.Timestamp:
        """
        Calculate the SignalForge intraday bucket start.

        Trading sessions begin at 09:15, so buckets are aligned to
        09:15 rather than midnight.
        """

        normalized = timestamp.normalize()

        minutes_since_session_start = (
            timestamp.hour * 60
            + timestamp.minute
            - (9 * 60 + 15)
        )

        bucket_number = (
            minutes_since_session_start // minutes
        )

        bucket_minutes = (
            9 * 60
            + 15
            + bucket_number * minutes
        )

        return normalized + pd.Timedelta(
            minutes=bucket_minutes,
        )

    @staticmethod
    def _build_completed_candle(
        timeframe: str,
        candles: list[pd.Series],
    ) -> CompletedCandle:
        """Aggregate source candles into one completed candle."""

        if not candles:
            raise ValueError(
                "Cannot build a completed candle from empty data."
            )

        timestamps = [
            pd.Timestamp(candle.name)
            for candle in candles
        ]

        return CompletedCandle(
            timeframe=timeframe,
            timestamp=timestamps[0],
            open=float(candles[0]["open"]),
            high=max(
                float(candle["high"])
                for candle in candles
            ),
            low=min(
                float(candle["low"])
                for candle in candles
            ),
            close=float(candles[-1]["close"]),
            volume=sum(
                float(candle["volume"])
                for candle in candles
            ),
        )

    @staticmethod
    def _validate_candle(
        candle: pd.Series,
    ) -> None:
        """Validate one incoming OHLCV candle."""

        if not isinstance(candle, pd.Series):
            raise TypeError(
                "candle must be a pandas Series."
            )

        if candle.name is None:
            if "timestamp" in candle.index:
                timestamp = pd.Timestamp(
                    candle["timestamp"]
                )
            else:
                raise ValueError(
                    "candle must have a timestamp index."
                )
        else:
            timestamp = pd.Timestamp(candle.name)

        if pd.isna(timestamp):
            raise ValueError(
                "candle timestamp cannot be missing."
            )

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in candle.index
        ]

        if missing:
            raise ValueError(
                f"candle is missing required columns: {missing}"
            )

        for column in REQUIRED_COLUMNS:
            value = candle[column]

            if pd.isna(value):
                raise ValueError(
                    f"candle {column} cannot be missing."
                )

        if float(candle["high"]) < float(candle["low"]):
            raise ValueError(
                "candle high cannot be lower than low."
            )

        if float(candle["volume"]) < 0:
            raise ValueError(
                "candle volume cannot be negative."
            )
"""Causal multi-timeframe indicator coordination for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategy.causal_indicators import (
    CausalIndicatorState,
    IndicatorSnapshot,
)
from src.strategy.causal_timeframes import (
    CausalTimeframeBuilder,
    CompletedCandle,
)


@dataclass(frozen=True)
class TimeframeIndicatorState:
    """Latest causally available indicator state for one timeframe."""

    timeframe: str
    timestamp: pd.Timestamp
    close: float
    indicators: IndicatorSnapshot


class CausalTimeframeIndicatorCoordinator:
    """Coordinate causal timeframe construction and indicators.

    A higher-timeframe candle becomes available only after its
    complete interval has elapsed.

    Example:

        09:15-09:20 5m candle
        -> completed when the 09:19 source candle arrives
        -> becomes available at 09:20

    No future source candle is inspected.
    """

    SUPPORTED_TIMEFRAMES = (
        "5m",
        "10m",
        "15m",
        "30m",
    )

    def __init__(
        self,
        *,
        ema_fast_period: int = 20,
        ema_slow_period: int = 50,
        rsi_period: int = 14,
        atr_period: int = 14,
        rvol_period: int = 20,
    ) -> None:
        self._builder = CausalTimeframeBuilder()

        self._indicator_states = {
            timeframe: CausalIndicatorState(
                ema_fast_period=ema_fast_period,
                ema_slow_period=ema_slow_period,
                rsi_period=rsi_period,
                atr_period=atr_period,
                rvol_period=rvol_period,
            )
            for timeframe in self.SUPPORTED_TIMEFRAMES
        }

        # Completed timeframe candles waiting until their information
        # is causally available to the strategy.
        self._pending: list[
            tuple[pd.Timestamp, CompletedCandle]
        ] = []

        # Latest indicator state actually available to the strategy.
        #
        # A timeframe can exist here even when one or more indicators
        # are still warming up. The consumer is responsible for
        # checking indicator readiness before generating a signal.
        self._latest_available: dict[
            str,
            TimeframeIndicatorState,
        ] = {}

    def process_candle(
        self,
        candle: pd.Series,
    ) -> dict[str, TimeframeIndicatorState]:
        """Process exactly one incoming 1-minute candle."""

        timestamp = self._validate_timestamp(candle)

        if candle.name is None:
            candle = candle.copy()
            candle.name = timestamp

        newly_available: dict[
            str,
            TimeframeIndicatorState,
        ] = {}

        # ---------------------------------------------------------
        # 1. Promote completed timeframe candles whose intervals
        #    have now fully elapsed.
        # ---------------------------------------------------------
        remaining_pending: list[
            tuple[pd.Timestamp, CompletedCandle]
        ] = []

        for available_at, completed in self._pending:
            if available_at <= timestamp:
                state = self._update_indicator_state(
                    completed
                )

                if state is not None:
                    self._latest_available[
                        completed.timeframe
                    ] = state

                    newly_available[
                        completed.timeframe
                    ] = state
            else:
                remaining_pending.append(
                    (available_at, completed)
                )

        self._pending = remaining_pending

        # ---------------------------------------------------------
        # 2. Process the current 1-minute candle.
        #
        # A newly completed higher-timeframe candle is deliberately
        # NOT made available until its interval has elapsed.
        # ---------------------------------------------------------
        completed_candles = (
            self._builder.process_candle(candle)
        )

        for timeframe, completed in completed_candles.items():
            available_at = (
                completed.timestamp
                + pd.Timedelta(
                    minutes=self._timeframe_minutes(
                        timeframe
                    )
                )
            )

            self._pending.append(
                (
                    available_at,
                    completed,
                )
            )

        return newly_available

    def get_latest_states(
        self,
    ) -> dict[str, TimeframeIndicatorState]:
        """Return the latest causally available state for each timeframe."""

        return dict(self._latest_available)

    def reset(self) -> None:
        """Reset all builders, indicators and pending state."""

        self._builder.reset()

        for indicator_state in self._indicator_states.values():
            indicator_state.reset()

        self._pending.clear()
        self._latest_available.clear()

    def _update_indicator_state(
        self,
        completed: CompletedCandle,
    ) -> TimeframeIndicatorState | None:
        """Update indicators using one completed timeframe candle."""

        indicator_state = self._indicator_states[
            completed.timeframe
        ]

        snapshot = indicator_state.update(
            high=completed.high,
            low=completed.low,
            close=completed.close,
            volume=completed.volume,
        )

        return TimeframeIndicatorState(
            timeframe=completed.timeframe,
            timestamp=completed.timestamp,
            close=completed.close,
            indicators=snapshot,
        )

    @staticmethod
    def _validate_timestamp(
        candle: pd.Series,
    ) -> pd.Timestamp:
        """Validate and return the source candle timestamp."""

        if not isinstance(candle, pd.Series):
            raise TypeError(
                "candle must be a pandas Series"
            )

        if "timestamp" in candle.index:
            timestamp = pd.Timestamp(
                candle["timestamp"]
            )
        elif candle.name is not None:
            timestamp = pd.Timestamp(
                candle.name
            )
        else:
            raise ValueError(
                "candle must contain a timestamp"
            )

        if pd.isna(timestamp):
            raise ValueError(
                "timestamp must not be NaT"
            )

        return timestamp

    @staticmethod
    def _timeframe_minutes(
        timeframe: str,
    ) -> int:
        """Return timeframe duration in minutes."""

        mapping = {
            "5m": 5,
            "10m": 10,
            "15m": 15,
            "30m": 30,
        }

        try:
            return mapping[timeframe]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            ) from exc
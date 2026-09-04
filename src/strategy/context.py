"""Causal strategy context for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.simulator import Position
from src.signals.signal_engine import (
    Signal,
    SignalResult,
    TimeframeState,
    generate_signal,
)
from src.strategy.backtest_strategy import StrategyConfig
from src.strategy.causal_timeframe_indicators import (
    CausalTimeframeIndicatorCoordinator,
    TimeframeIndicatorState,
)


@dataclass(frozen=True)
class StrategyContextResult:
    """
    Result returned after processing one market candle.

    Attributes:
        timestamp:
            Timestamp of the processed candle.

        position:
            Strategy position for the current candle.
            None means no trade / no action.
    """

    timestamp: pd.Timestamp
    position: Position | None


class CausalStrategyContext:
    """
    Stateful causal SignalForge strategy context.

    Every indicator value is calculated only from candles that have
    already been supplied to process_candle().

    The context never automatically consumes a complete dataset.

    Historical warm-up, when required, must be explicitly supplied
    by the caller one candle at a time.

    The frozen SignalForge strategy rules are preserved:
        - 30m / 15m / 10m / 5m timeframe alignment
        - RSI confirmation
        - ATR confirmation
        - optional RVOL confirmation
        - locked LONG RSI threshold
    """

    def __init__(
        self,
        warmup_data: pd.DataFrame | None = None,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        """
        Initialize the causal strategy context.

        `warmup_data` is retained for backward compatibility with
        the previous context API.

        It is validated and stored, but NEVER automatically processed.

        This is intentional: automatic processing would make it
        impossible for the caller to define an explicit causal
        warm-up boundary.
        """

        if warmup_data is not None:
            if not isinstance(
                warmup_data,
                pd.DataFrame,
            ):
                raise TypeError(
                    "warmup_data must be a pandas DataFrame."
                )

            if warmup_data.empty:
                raise ValueError(
                    "warmup_data cannot be empty."
                )

            self._validate_warmup_data(
                warmup_data
            )

            self._warmup_data = warmup_data.copy()
        else:
            self._warmup_data = None

        if strategy_config is None:
            strategy_config = StrategyConfig()

        if not isinstance(
            strategy_config,
            StrategyConfig,
        ):
            raise TypeError(
                "strategy_config must be a StrategyConfig."
            )

        self._strategy_config = strategy_config

        self._coordinator = (
            CausalTimeframeIndicatorCoordinator(
                ema_fast_period=(
                    strategy_config.ema_fast_period
                ),
                ema_slow_period=(
                    strategy_config.ema_slow_period
                ),
                rsi_period=(
                    strategy_config.rsi_period
                ),
                atr_period=(
                    strategy_config.atr_period
                ),
                rvol_period=(
                    strategy_config.rvol_period
                ),
            )
        )

        self._previous_candle: pd.Series | None = None

        self._last_timestamp: pd.Timestamp | None = None

        self._processed_count = 0

        self._use_rvol = strategy_config.use_rvol

        # Preserve the existing SignalForge behavior:
        # if the supplied warm-up dataset has no usable volume,
        # RVOL is disabled.
        if (
            warmup_data is not None
            and not (
                warmup_data["volume"] > 0
            ).any()
        ):
            self._use_rvol = False

    @property
    def last_timestamp(
        self,
    ) -> pd.Timestamp | None:
        """Return the timestamp of the latest processed candle."""

        return self._last_timestamp

    @property
    def processed_count(self) -> int:
        """Return the number of candles processed."""

        return self._processed_count

    @property
    def previous_candle(
        self,
    ) -> pd.Series | None:
        """Return a defensive copy of the previous candle."""

        if self._previous_candle is None:
            return None

        return self._previous_candle.copy()

    @property
    def warmup_data(
        self,
    ) -> pd.DataFrame | None:
        """
        Return a defensive copy of the optional warm-up dataset.

        The property exists for backward compatibility and
        introspection. The data is never automatically processed.
        """

        if self._warmup_data is None:
            return None

        return self._warmup_data.copy()

    def process_candle(
        self,
        candle: pd.Series,
    ) -> StrategyContextResult:
        """
        Process exactly one newly available market candle.

        Candles must arrive strictly chronologically.

        The current candle is the only new source information
        introduced by this call.
        """

        if not isinstance(
            candle,
            pd.Series,
        ):
            raise TypeError(
                "candle must be a pandas Series."
            )

        timestamp = candle.name

        if timestamp is None:
            if "timestamp" in candle.index:
                timestamp = candle["timestamp"]
            else:
                raise ValueError(
                    "candle must have a timestamp "
                    "in Series.name."
                )

        timestamp = pd.Timestamp(timestamp)

        if pd.isna(timestamp):
            raise ValueError(
                "candle timestamp must not be NaT."
            )

        if (
            self._last_timestamp is not None
            and timestamp <= self._last_timestamp
        ):
            raise ValueError(
                "candle timestamp must be strictly "
                "greater than the previously processed "
                "timestamp."
            )

        if candle.name != timestamp:
            candle = candle.copy()
            candle.name = timestamp

        # ---------------------------------------------------------
        # Process exactly this candle through the causal timeframe
        # and indicator machinery.
        # ---------------------------------------------------------
        self._coordinator.process_candle(
            candle
        )

        # ---------------------------------------------------------
        # The first candle establishes previous-candle state and
        # cannot produce a strategy signal.
        # ---------------------------------------------------------
        if self._previous_candle is None:
            self._previous_candle = candle.copy()

            self._last_timestamp = timestamp

            self._processed_count += 1

            return StrategyContextResult(
                timestamp=timestamp,
                position=None,
            )

        # ---------------------------------------------------------
        # Retrieve only timeframe information that has become
        # causally available by this timestamp.
        # ---------------------------------------------------------
        latest_states = (
            self._coordinator.get_latest_states()
        )

        required_timeframes = (
            "30m",
            "15m",
            "10m",
            "5m",
        )

        if any(
            timeframe not in latest_states
            for timeframe in required_timeframes
        ):
            position = None

        else:
            timeframe_states = {
                timeframe: self._convert_state(
                    latest_states[timeframe]
                )
                for timeframe in required_timeframes
            }

            # Indicator warm-up may still be incomplete.
            if any(
                state is None
                for state in timeframe_states.values()
            ):
                position = None

            else:
                signal_result = (
                    self._generate_filtered_signal(
                        states=(
                            timeframe_states["30m"],
                            timeframe_states["15m"],
                            timeframe_states["10m"],
                            timeframe_states["5m"],
                        )
                    )
                )

                position = (
                    self._signal_result_to_position(
                        signal_result
                    )
                )

        # ---------------------------------------------------------
        # Update state only after the signal has been calculated.
        # ---------------------------------------------------------
        self._previous_candle = candle.copy()

        self._last_timestamp = timestamp

        self._processed_count += 1

        return StrategyContextResult(
            timestamp=timestamp,
            position=position,
        )

    def reset(self) -> None:
        """
        Reset sequential processing state.

        Stored warm-up data remains available for compatibility,
        but is not automatically replayed.
        """

        self._coordinator.reset()

        self._previous_candle = None

        self._last_timestamp = None

        self._processed_count = 0

    def _generate_filtered_signal(
        self,
        states: tuple[
            TimeframeState,
            TimeframeState,
            TimeframeState,
            TimeframeState,
        ],
    ) -> SignalResult:
        """Apply the authoritative frozen SignalForge rules."""

        result = generate_signal(
            timeframe_30m=states[0],
            timeframe_15m=states[1],
            timeframe_10m=states[2],
            timeframe_5m=states[3],
            minimum_rvol=(
                self._strategy_config.minimum_rvol
            ),
            minimum_atr=(
                self._strategy_config.minimum_atr
            ),
            use_rvol=self._use_rvol,
        )

        # Preserve the locked LONG RSI >= 60 filter.
        if result.signal != Signal.BUY:
            return result

        if all(
            state.rsi
            >= self._strategy_config.minimum_long_rsi
            for state in states
        ):
            return result

        return SignalResult(
            signal=Signal.NO_TRADE,
            score=0,
            confidence=0.0,
            timeframe_alignment=(
                result.timeframe_alignment
            ),
            reason=(
                "LONG rejected: RSI below locked "
                "threshold "
                f"{self._strategy_config.minimum_long_rsi:.1f} "
                "on at least one timeframe."
            ),
        )

    @staticmethod
    def _signal_result_to_position(
        result: SignalResult,
    ) -> Position | None:
        """Convert Signal Engine output into Position."""

        if result.signal == Signal.BUY:
            return Position.LONG

        if result.signal == Signal.SELL:
            return Position.SHORT

        return None

    @staticmethod
    def _convert_state(
        state: TimeframeIndicatorState,
    ) -> TimeframeState | None:
        """Convert causal indicator state to Signal Engine state."""

        indicators = state.indicators

        if (
            indicators.ema_fast is None
            or indicators.ema_slow is None
            or indicators.rsi is None
            or indicators.atr is None
        ):
            return None

        return TimeframeState(
            close=float(
                state.close
            ),
            ema20=float(
                indicators.ema_fast
            ),
            ema50=float(
                indicators.ema_slow
            ),
            rsi=float(
                indicators.rsi
            ),
            rvol=(
                float(indicators.rvol)
                if indicators.rvol is not None
                else 0.0
            ),
            atr=float(
                indicators.atr
            ),
        )

    @staticmethod
    def _validate_warmup_data(
        data: pd.DataFrame,
    ) -> None:
        """Validate historical warm-up data."""

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = sorted(
            required_columns.difference(
                data.columns
            )
        )

        if missing:
            raise ValueError(
                "warmup_data is missing required "
                f"columns: {missing}"
            )

        if not isinstance(
            data.index,
            pd.DatetimeIndex,
        ):
            raise TypeError(
                "warmup_data index must be a DatetimeIndex."
            )

        if data.index.has_duplicates:
            raise ValueError(
                "warmup_data index cannot contain duplicates."
            )

        if not data.index.is_monotonic_increasing:
            raise ValueError(
                "warmup_data index must be sorted."
            )
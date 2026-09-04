from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.resampler import SUPPORTED_TIMEFRAMES
from src.strategy.causal_timeframe_indicators import (
    CausalTimeframeIndicatorCoordinator,
)


DEFAULT_REQUIRED_TIMEFRAMES = tuple(
    SUPPORTED_TIMEFRAMES.keys()
)


@dataclass(frozen=True)
class IndicatorCompatibilityResult:
    """Result of indicator compatibility analysis."""

    passed: bool
    total_source_candles: int
    processed_source_candles: int
    required_timeframes: tuple[str, ...]
    timeframe_candle_counts: dict[str, int]
    timeframe_ready_counts: dict[str, int]
    timeframe_indicator_ready: dict[str, bool]
    ema20_ready: bool
    ema50_ready: bool
    rsi14_ready: bool
    atr14_ready: bool
    rvol20_ready: bool
    issues: tuple[str, ...]

    @property
    def compatible_timeframes(self) -> tuple[str, ...]:
        """Return timeframes with all mandatory indicators ready."""

        return tuple(
            timeframe
            for timeframe in self.required_timeframes
            if self.timeframe_indicator_ready.get(
                timeframe,
                False,
            )
        )

    @property
    def compatibility_score(self) -> float:
        """Return percentage of required timeframes that are compatible."""

        if not self.required_timeframes:
            return 0.0

        compatible = len(
            self.compatible_timeframes
        )

        return round(
            compatible
            / len(self.required_timeframes)
            * 100.0,
            2,
        )


class IndicatorCompatibilityChecker:
    """
    Validate that historical data can support the SignalForge
    indicator engine.

    The checker uses the existing causal multi-timeframe indicator
    implementation. It does not duplicate indicator formulas and
    does not mutate the supplied DataFrame.

    Mandatory indicators:
        - EMA20
        - EMA50
        - RSI14
        - ATR14

    RVOL20 is treated as an optional data-dependent indicator because
    SignalForge already disables RVOL when usable volume is absent.
    """

    def __init__(
        self,
        *,
        required_timeframes: tuple[str, ...] = (
            DEFAULT_REQUIRED_TIMEFRAMES
        ),
        minimum_ready_observations: int = 1,
    ) -> None:
        if not required_timeframes:
            raise ValueError(
                "required_timeframes must not be empty."
            )

        unknown = sorted(
            set(required_timeframes)
            - set(
                CausalTimeframeIndicatorCoordinator.SUPPORTED_TIMEFRAMES
            )
        )

        if unknown:
            raise ValueError(
                "Unsupported timeframes: "
                f"{unknown}"
            )

        if (
            not isinstance(
                minimum_ready_observations,
                int,
            )
            or isinstance(
                minimum_ready_observations,
                bool,
            )
        ):
            raise TypeError(
                "minimum_ready_observations must be an integer."
            )

        if minimum_ready_observations <= 0:
            raise ValueError(
                "minimum_ready_observations must be greater than zero."
            )

        self._required_timeframes = tuple(
            required_timeframes
        )

        self._minimum_ready_observations = (
            minimum_ready_observations
        )

    def check(
        self,
        data: pd.DataFrame,
    ) -> IndicatorCompatibilityResult:
        """Check indicator compatibility using causal processing."""

        if not isinstance(
            data,
            pd.DataFrame,
        ):
            return self._failed_result(
                "Market data must be a pandas DataFrame."
            )

        if not isinstance(
            data.index,
            pd.DatetimeIndex,
        ):
            return self._failed_result(
                "Market data index must be a DatetimeIndex."
            )

        if data.empty:
            return self._failed_result(
                "Market data cannot be empty."
            )

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
            return self._failed_result(
                "Missing required columns: "
                f"{missing}"
            )

        issues: list[str] = []

        working = data.loc[
            :,
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        ].copy()

        working = working.sort_index()

        coordinator = (
            CausalTimeframeIndicatorCoordinator()
        )

        timeframe_candle_counts = {
            timeframe: 0
            for timeframe in self._required_timeframes
        }

        timeframe_ready_counts = {
            timeframe: 0
            for timeframe in self._required_timeframes
        }

        timeframe_indicator_ready = {
            timeframe: False
            for timeframe in self._required_timeframes
        }

        ema20_ready = False
        ema50_ready = False
        rsi14_ready = False
        atr14_ready = False
        rvol20_ready = False

        processed_source_candles = 0

        for timestamp, row in working.iterrows():
            candle = row.copy()
            candle.name = timestamp

            coordinator.process_candle(
                candle
            )

            processed_source_candles += 1

            states = coordinator.get_latest_states()

            for timeframe in self._required_timeframes:
                state = states.get(timeframe)

                if state is None:
                    continue

                timeframe_candle_counts[
                    timeframe
                ] += 1

                indicators = state.indicators

                if indicators.ema_fast is not None:
                    ema20_ready = True

                if indicators.ema_slow is not None:
                    ema50_ready = True

                if indicators.rsi is not None:
                    rsi14_ready = True

                if indicators.atr is not None:
                    atr14_ready = True

                if indicators.rvol is not None:
                    rvol20_ready = True

                mandatory_ready = (
                    indicators.ema_fast is not None
                    and indicators.ema_slow is not None
                    and indicators.rsi is not None
                    and indicators.atr is not None
                )

                if mandatory_ready:
                    timeframe_ready_counts[
                        timeframe
                    ] += 1

        for timeframe in self._required_timeframes:
            ready_count = timeframe_ready_counts[
                timeframe
            ]

            timeframe_indicator_ready[
                timeframe
            ] = (
                ready_count
                >= self._minimum_ready_observations
            )

            if timeframe_candle_counts[
                timeframe
            ] == 0:
                issues.append(
                    f"No completed {timeframe} candles "
                    "were available for indicator calculation."
                )
            elif not timeframe_indicator_ready[
                timeframe
            ]:
                issues.append(
                    f"{timeframe} does not have enough "
                    "indicator-ready observations."
                )

        if not ema20_ready:
            issues.append(
                "EMA20 did not become ready on any required timeframe."
            )

        if not ema50_ready:
            issues.append(
                "EMA50 did not become ready on any required timeframe."
            )

        if not rsi14_ready:
            issues.append(
                "RSI14 did not become ready on any required timeframe."
            )

        if not atr14_ready:
            issues.append(
                "ATR14 did not become ready on any required timeframe."
            )

        volume_has_positive_value = bool(
            (
                pd.to_numeric(
                    working["volume"],
                    errors="coerce",
                )
                > 0
            ).any()
        )

        if volume_has_positive_value and not rvol20_ready:
            issues.append(
                "RVOL20 did not become ready despite usable volume."
            )

        passed = (
            not issues
            and all(
                timeframe_indicator_ready.values()
            )
        )

        return IndicatorCompatibilityResult(
            passed=passed,
            total_source_candles=len(data),
            processed_source_candles=processed_source_candles,
            required_timeframes=self._required_timeframes,
            timeframe_candle_counts=timeframe_candle_counts,
            timeframe_ready_counts=timeframe_ready_counts,
            timeframe_indicator_ready=timeframe_indicator_ready,
            ema20_ready=ema20_ready,
            ema50_ready=ema50_ready,
            rsi14_ready=rsi14_ready,
            atr14_ready=atr14_ready,
            rvol20_ready=rvol20_ready,
            issues=tuple(issues),
        )

    @staticmethod
    def _failed_result(
        issue: str,
    ) -> IndicatorCompatibilityResult:
        """Build a failed result for invalid input."""

        return IndicatorCompatibilityResult(
            passed=False,
            total_source_candles=0,
            processed_source_candles=0,
            required_timeframes=(),
            timeframe_candle_counts={},
            timeframe_ready_counts={},
            timeframe_indicator_ready={},
            ema20_ready=False,
            ema50_ready=False,
            rsi14_ready=False,
            atr14_ready=False,
            rvol20_ready=False,
            issues=(issue,),
        )

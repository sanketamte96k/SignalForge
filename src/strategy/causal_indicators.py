"""Causal stateful indicators for SignalForge."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Current causal indicator values."""

    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    atr: float | None
    rvol: float | None


class CausalIndicatorState:
    """
    Incrementally calculate EMA, RSI, ATR and RVOL.

    Each update consumes exactly one completed OHLCV candle.

    The calculations mirror the existing SignalForge pandas
    implementations while maintaining only historical state required
    for future updates.
    """

    def __init__(
        self,
        ema_fast_period: int,
        ema_slow_period: int,
        rsi_period: int,
        atr_period: int,
        rvol_period: int,
    ) -> None:
        self._validate_period(
            ema_fast_period,
            "ema_fast_period",
        )
        self._validate_period(
            ema_slow_period,
            "ema_slow_period",
        )
        self._validate_period(
            rsi_period,
            "rsi_period",
        )
        self._validate_period(
            atr_period,
            "atr_period",
        )
        self._validate_period(
            rvol_period,
            "rvol_period",
        )

        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.rvol_period = rvol_period

        self._reset_state()

    def _reset_state(self) -> None:
        """Reset all indicator state."""

        self._count = 0

        self._previous_close: float | None = None

        # EMA state.
        self._ema_fast: float | None = None
        self._ema_slow: float | None = None
        self._close_warmup: list[float] = []

        # RSI EWM state.
        self._average_gain: float | None = None
        self._average_loss: float | None = None
        self._gain_loss_count = 0

        # ATR EWM state.
        self._atr: float | None = None
        self._true_range_count = 0

        # RVOL rolling window.
        self._volume_window: deque[float] = deque(
            maxlen=self.rvol_period,
        )

    def reset(self) -> None:
        """Reset the indicator state."""

        self._reset_state()

    def update(
        self,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> IndicatorSnapshot:
        """
        Process exactly one completed candle.

        Returns the indicator values available after this candle.
        """

        self._validate_value(high, "high")
        self._validate_value(low, "low")
        self._validate_value(close, "close")
        self._validate_value(volume, "volume")

        if high < low:
            raise ValueError(
                "high cannot be lower than low."
            )

        if volume < 0:
            raise ValueError(
                "volume cannot be negative."
            )

        self._count += 1

        self._close_warmup.append(close)

        self._update_ema(
            close,
            self.ema_fast_period,
            "fast",
        )

        self._update_ema(
            close,
            self.ema_slow_period,
            "slow",
        )

        self._update_rsi(close)

        self._update_atr(
            high,
            low,
            close,
        )

        self._volume_window.append(volume)

        self._previous_close = close

        return self.snapshot()

    def snapshot(self) -> IndicatorSnapshot:
        """Return current indicator values without updating state."""

        return IndicatorSnapshot(
            ema_fast=self._ema_fast,
            ema_slow=self._ema_slow,
            rsi=self._calculate_rsi_value(),
            atr=self._calculate_atr_value(),
            rvol=self._calculate_rvol_value(),
        )

    def _update_ema(
        self,
        close: float,
        period: int,
        which: str,
    ) -> None:
        """Update EMA using pandas ewm(adjust=False) semantics."""

        if which == "fast":
            current = self._ema_fast
        else:
            current = self._ema_slow

        if current is None:
            if self._count < period:
                return

            alpha = 2.0 / (period + 1.0)

            value = self._close_warmup[0]

            for price in self._close_warmup[1:]:
                value = (
                    alpha * price
                    + (1.0 - alpha) * value
                )

            if which == "fast":
                self._ema_fast = value
            else:
                self._ema_slow = value

            return

        alpha = 2.0 / (period + 1.0)

        updated = (
            alpha * close
            + (1.0 - alpha) * current
        )

        if which == "fast":
            self._ema_fast = updated
        else:
            self._ema_slow = updated

    def _update_rsi(
        self,
        close: float,
    ) -> None:
        """
        Update RSI using pandas EWM adjust=False semantics.

        The existing batch implementation starts its EWM from the
        first available gain/loss observation and uses min_periods
        only to control when the RSI becomes visible.
        """

        if self._previous_close is None:
            return

        delta = close - self._previous_close

        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        self._gain_loss_count += 1

        alpha = 1.0 / self.rsi_period

        if self._average_gain is None:
            self._average_gain = gain
            self._average_loss = loss
        else:
            self._average_gain = (
                alpha * gain
                + (1.0 - alpha) * self._average_gain
            )

            self._average_loss = (
                alpha * loss
                + (1.0 - alpha) * self._average_loss
            )

    def _calculate_rsi_value(self) -> float | None:
        """Calculate the current RSI value."""

        if self._gain_loss_count < self.rsi_period:
            return None

        if (
            self._average_gain is None
            or self._average_loss is None
        ):
            return None

        if self._average_loss == 0:
            if self._average_gain == 0:
                return 50.0

            return 100.0

        relative_strength = (
            self._average_gain
            / self._average_loss
        )

        return 100.0 - (
            100.0 / (1.0 + relative_strength)
        )

    def _update_atr(
        self,
        high: float,
        low: float,
        close: float,
    ) -> None:
        """
        Update ATR using pandas EWM adjust=False semantics.

        The first true-range observation seeds the recursive EWM.
        The value becomes visible after `atr_period` observations.
        """

        if self._previous_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - self._previous_close),
                abs(low - self._previous_close),
            )

        self._true_range_count += 1

        alpha = 1.0 / self.atr_period

        if self._atr is None:
            self._atr = true_range
        else:
            self._atr = (
                alpha * true_range
                + (1.0 - alpha) * self._atr
            )

    def _calculate_atr_value(self) -> float | None:
        """Return ATR when its warm-up period is complete."""

        if self._true_range_count < self.atr_period:
            return None

        return self._atr

    def _calculate_rvol_value(self) -> float | None:
        """Calculate the current rolling relative volume."""

        if len(self._volume_window) < self.rvol_period:
            return None

        average_volume = (
            sum(self._volume_window)
            / self.rvol_period
        )

        if average_volume == 0:
            return None

        return (
            self._volume_window[-1]
            / average_volume
        )

    @staticmethod
    def _validate_period(
        period: int,
        name: str,
    ) -> None:
        """Validate an indicator period."""

        if not isinstance(period, int) or isinstance(
            period,
            bool,
        ):
            raise TypeError(
                f"{name} must be an integer."
            )

        if period <= 0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

    @staticmethod
    def _validate_value(
        value: float,
        name: str,
    ) -> None:
        """Validate one numeric indicator input."""

        if not isinstance(value, (int, float)):
            raise TypeError(
                f"{name} must be numeric."
            )

        if isinstance(value, bool):
            raise TypeError(
                f"{name} must be numeric."
            )
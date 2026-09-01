"""Multi-timeframe signal engine for SignalForge."""

from dataclasses import dataclass
from enum import Enum

from src.strategy.signal_rules import (
    Direction,
    momentum_support,
    trend_direction,
    volatility_is_acceptable,
    volume_support,
)


class Signal(str, Enum):
    """Final SignalForge signal."""

    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class TimeframeState:
    """
    Indicator state for one timeframe.

    Each timeframe contains the latest values
    required by the SignalForge decision engine.
    """

    close: float
    ema20: float
    ema50: float
    rsi: float
    rvol: float
    atr: float


@dataclass(frozen=True)
class SignalResult:
    """Complete result produced by the signal engine."""

    signal: Signal
    score: int
    confidence: float
    timeframe_alignment: int
    reason: str


def _direction_to_signal(
    direction: Direction,
) -> Signal:
    """Convert strategy direction into final signal."""

    if direction == Direction.LONG:
        return Signal.BUY

    if direction == Direction.SHORT:
        return Signal.SELL

    return Signal.NO_TRADE


def _validate_state(
    state: TimeframeState,
    name: str,
) -> None:
    """Validate one timeframe state."""

    values = (
        state.close,
        state.ema20,
        state.ema50,
        state.rsi,
        state.rvol,
        state.atr,
    )

    for value in values:
        if not isinstance(value, (int, float)):
            raise TypeError(
                f"{name} contains a non-numeric value."
            )

    if state.rvol < 0:
        raise ValueError(
            f"{name} RVOL cannot be negative."
        )

    if state.atr < 0:
        raise ValueError(
            f"{name} ATR cannot be negative."
        )

    if not 0 <= state.rsi <= 100:
        raise ValueError(
            f"{name} RSI must be between 0 and 100."
        )


def _validate_threshold(
    value: float,
    name: str,
) -> None:
    """Validate a non-negative numeric threshold."""

    if not isinstance(
        value,
        (int, float),
    ) or isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{name} must be numeric."
        )

    if value < 0:
        raise ValueError(
            f"{name} cannot be negative."
        )


def generate_signal(
    timeframe_30m: TimeframeState,
    timeframe_15m: TimeframeState,
    timeframe_10m: TimeframeState,
    timeframe_5m: TimeframeState,
    minimum_rvol: float = 1.5,
    minimum_atr: float = 0.0,
    use_rvol: bool = True,
) -> SignalResult:
    """
    Generate a deterministic multi-timeframe signal.

    Timeframe hierarchy:

        30m -> market context
        15m -> primary trend
        10m -> confirmation
        5m  -> entry timing

    All four timeframes must agree directionally.

    RSI and ATR provide confirmation.

    RVOL provides additional confirmation only when
    use_rvol=True.

    When RVOL is unavailable for the underlying market,
    use_rvol=False prevents unavailable volume from
    incorrectly reducing the signal score.

    If timeframes disagree, NO_TRADE is returned.
    """

    states = {
        "30m": timeframe_30m,
        "15m": timeframe_15m,
        "10m": timeframe_10m,
        "5m": timeframe_5m,
    }

    # --------------------------------------------------------
    # Validate inputs
    # --------------------------------------------------------

    for name, state in states.items():

        if not isinstance(
            state,
            TimeframeState,
        ):
            raise TypeError(
                f"{name} must be a TimeframeState."
            )

        _validate_state(
            state,
            name,
        )

    _validate_threshold(
        minimum_rvol,
        "minimum_rvol",
    )

    _validate_threshold(
        minimum_atr,
        "minimum_atr",
    )

    if not isinstance(
        use_rvol,
        bool,
    ):
        raise TypeError(
            "use_rvol must be a boolean."
        )

    # --------------------------------------------------------
    # Determine trend direction for each timeframe
    # --------------------------------------------------------

    directions = {
        name: trend_direction(
            state.close,
            state.ema20,
            state.ema50,
        )
        for name, state in states.items()
    }

    # --------------------------------------------------------
    # Every timeframe must have a valid trend
    # --------------------------------------------------------

    if any(
        direction == Direction.NO_TRADE
        for direction in directions.values()
    ):
        return SignalResult(
            signal=Signal.NO_TRADE,
            score=0,
            confidence=0.0,
            timeframe_alignment=0,
            reason=(
                "Incomplete or neutral "
                "timeframe trend alignment."
            ),
        )

    # --------------------------------------------------------
    # Check directional agreement
    # --------------------------------------------------------

    direction_values = list(
        directions.values()
    )

    first_direction = direction_values[0]

    if any(
        direction != first_direction
        for direction in direction_values
    ):
        return SignalResult(
            signal=Signal.NO_TRADE,
            score=0,
            confidence=0.0,
            timeframe_alignment=0,
            reason="Timeframe disagreement.",
        )

    # --------------------------------------------------------
    # All timeframes agree
    # --------------------------------------------------------

    signal = _direction_to_signal(
        first_direction
    )

    # Four points for four aligned timeframes.
    score = 4

    confirmations = 0
    confirmation_maximum = 0

    # --------------------------------------------------------
    # Indicator confirmations
    # --------------------------------------------------------

    for state in states.values():

        # RSI confirmation
        confirmation_maximum += 1

        if momentum_support(
            first_direction,
            state.rsi,
        ):
            confirmations += 1

        # RVOL confirmation
        #
        # Only count RVOL when the underlying market
        # actually provides usable volume.
        if use_rvol:
            confirmation_maximum += 1

            if volume_support(
                state.rvol,
                minimum_rvol,
            ):
                confirmations += 1

        # ATR confirmation
        confirmation_maximum += 1

        if volatility_is_acceptable(
            state.atr,
            minimum_atr,
        ):
            confirmations += 1

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    score = (
        score + confirmations
    )

    # --------------------------------------------------------
    # Confidence
    #
    # Four timeframe alignment points plus the
    # available indicator confirmation points.
    #
    # With RVOL enabled:
    #     4 + 12 = 16 maximum
    #
    # With RVOL disabled:
    #     4 + 8 = 12 maximum
    #
    # This prevents unavailable RVOL from penalizing
    # NIFTY index signals.
    # --------------------------------------------------------

    maximum_score = (
        4 + confirmation_maximum
    )

    confidence = round(
        (score / maximum_score) * 100,
        2,
    )

    # --------------------------------------------------------
    # Human-readable reason
    # --------------------------------------------------------

    if use_rvol:
        reason = (
            f"{confirmations}/12 "
            "indicator confirmations."
        )

    else:
        reason = (
            f"{confirmations}/8 "
            "indicator confirmations. "
            "RVOL unavailable."
        )

    return SignalResult(
        signal=signal,
        score=score,
        confidence=confidence,
        timeframe_alignment=4,
        reason=reason,
    )
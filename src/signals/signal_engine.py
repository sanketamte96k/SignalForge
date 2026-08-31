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


def generate_signal(
    timeframe_30m: TimeframeState,
    timeframe_15m: TimeframeState,
    timeframe_10m: TimeframeState,
    timeframe_5m: TimeframeState,
    minimum_rvol: float = 1.5,
    minimum_atr: float = 0.0,
) -> SignalResult:
    """
    Generate a deterministic multi-timeframe signal.

    Timeframe hierarchy:

        30m -> market context
        15m -> primary trend
        10m -> confirmation
        5m  -> entry timing

    All four timeframes must agree directionally.

    RSI, RVOL and ATR provide additional confirmation.

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

        if not isinstance(state, TimeframeState):
            raise TypeError(
                f"{name} must be a TimeframeState."
            )

        _validate_state(
            state,
            name,
        )

    if minimum_rvol < 0:
        raise ValueError(
            "minimum_rvol cannot be negative."
        )

    if minimum_atr < 0:
        raise ValueError(
            "minimum_atr cannot be negative."
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

    # --------------------------------------------------------
    # Indicator confirmations
    # --------------------------------------------------------

    for state in states.values():

        # RSI confirmation
        if momentum_support(
            first_direction,
            state.rsi,
        ):
            confirmations += 1

        # RVOL confirmation
        if volume_support(
            state.rvol,
            minimum_rvol,
        ):
            confirmations += 1

        # ATR confirmation
        if volatility_is_acceptable(
            state.atr,
            minimum_atr,
        ):
            confirmations += 1

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    score += confirmations

    # Maximum:
    #
    # 4 timeframe points
    # +
    # 12 indicator confirmation points
    #
    # = 16
    maximum_score = 16

    confidence = round(
        (score / maximum_score) * 100,
        2,
    )

    # --------------------------------------------------------
    # Human-readable reason
    # --------------------------------------------------------

    if confirmations == 0:

        reason = (
            "No indicator confirmation."
        )

    else:

        reason = (
            f"{confirmations}/12 "
            "indicator confirmations."
        )

    return SignalResult(
        signal=signal,
        score=score,
        confidence=confidence,
        timeframe_alignment=4,
        reason=reason,
    )
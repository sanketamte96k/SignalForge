"""Pure trading decision rules for SignalForge."""

from enum import Enum


class Direction(str, Enum):
    """Possible trading directions."""

    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


def trend_direction(
    close: float,
    ema20: float,
    ema50: float,
) -> Direction:
    """Determine trend direction from price and EMA alignment."""

    if close > ema20 > ema50:
        return Direction.LONG

    if close < ema20 < ema50:
        return Direction.SHORT

    return Direction.NO_TRADE


def momentum_support(
    direction: Direction,
    rsi: float,
) -> bool:
    """Check whether RSI supports the proposed direction."""

    if direction == Direction.LONG:
        return rsi > 50

    if direction == Direction.SHORT:
        return rsi < 50

    return False


def volume_support(
    rvol: float,
    minimum_rvol: float = 1.5,
) -> bool:
    """Check whether relative volume provides confirmation."""

    if minimum_rvol < 0:
        raise ValueError("minimum_rvol cannot be negative.")

    return rvol >= minimum_rvol


def volatility_is_acceptable(
    atr: float,
    minimum_atr: float,
) -> bool:
    """Check whether current volatility is sufficient."""

    if minimum_atr < 0:
        raise ValueError("minimum_atr cannot be negative.")

    return atr >= minimum_atr
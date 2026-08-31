"""Technical indicators used by SignalForge."""

import pandas as pd


def calculate_ema(
    close: pd.Series,
    period: int,
) -> pd.Series:
    """
    Calculate the Exponential Moving Average (EMA).

    Parameters
    ----------
    close:
        Series containing closing prices.

    period:
        EMA lookback period. Must be a positive integer.

    Returns
    -------
    pd.Series
        EMA values with the same index as the input.
    """

    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series.")

    if close.empty:
        raise ValueError("close series cannot be empty.")

    if not isinstance(period, int) or isinstance(period, bool):
        raise TypeError("period must be an integer.")

    if period <= 0:
        raise ValueError("period must be greater than zero.")

    if close.isna().any():
        raise ValueError("close series cannot contain missing values.")

    return close.ewm(
        span=period,
        adjust=False,
        min_periods=period,
    ).mean()


def calculate_rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate the Relative Strength Index (RSI).

    Uses Wilder's smoothing method.

    Parameters
    ----------
    close:
        Series containing closing prices.

    period:
        RSI lookback period. Must be a positive integer.

    Returns
    -------
    pd.Series
        RSI values between 0 and 100.
    """

    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series.")

    if close.empty:
        raise ValueError("close series cannot be empty.")

    if not isinstance(period, int) or isinstance(period, bool):
        raise TypeError("period must be an integer.")

    if period <= 0:
        raise ValueError("period must be greater than zero.")

    if close.isna().any():
        raise ValueError("close series cannot contain missing values.")

    delta = close.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    relative_strength = average_gain / average_loss

    rsi = 100 - (
        100 / (1 + relative_strength)
    )

    # No losses means maximum RSI.
    rsi = rsi.where(
        average_loss != 0,
        100.0,
    )

    # No gains and no losses means a constant market.
    # In that case RSI is neutral at 50.
    rsi = rsi.where(
        ~(
            (average_gain == 0)
            & (average_loss == 0)
        ),
        50.0,
    )

    return rsi
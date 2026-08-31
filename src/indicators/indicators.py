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

    rsi = rsi.where(
        average_loss != 0,
        100.0,
    )

    rsi = rsi.where(
        ~(
            (average_gain == 0)
            & (average_loss == 0)
        ),
        50.0,
    )

    return rsi


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate the Average True Range (ATR).

    Uses Wilder's smoothing method.

    Parameters
    ----------
    high:
        Series containing high prices.

    low:
        Series containing low prices.

    close:
        Series containing closing prices.

    period:
        ATR lookback period. Must be a positive integer.

    Returns
    -------
    pd.Series
        ATR values with the same index as the input.
    """

    if not isinstance(high, pd.Series):
        raise TypeError("high must be a pandas Series.")

    if not isinstance(low, pd.Series):
        raise TypeError("low must be a pandas Series.")

    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series.")

    if high.empty or low.empty or close.empty:
        raise ValueError("price series cannot be empty.")

    if not isinstance(period, int) or isinstance(period, bool):
        raise TypeError("period must be an integer.")

    if period <= 0:
        raise ValueError("period must be greater than zero.")

    if not high.index.equals(low.index):
        raise ValueError("high and low must have the same index.")

    if not high.index.equals(close.index):
        raise ValueError("high and close must have the same index.")

    if high.isna().any():
        raise ValueError("high series cannot contain missing values.")

    if low.isna().any():
        raise ValueError("low series cannot contain missing values.")

    if close.isna().any():
        raise ValueError("close series cannot contain missing values.")

    if (high < low).any():
        raise ValueError(
            "high values cannot be lower than low values."
        )

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return atr
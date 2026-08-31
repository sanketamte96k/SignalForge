"""Utilities for converting 1-minute OHLCV data into higher timeframes."""

import pandas as pd


REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


SUPPORTED_TIMEFRAMES = {
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
}


def validate_ohlcv(data: pd.DataFrame) -> None:
    """Validate the basic structure of an OHLCV DataFrame."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError(
            "DataFrame index must be a pandas DatetimeIndex."
        )

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if data.empty:
        raise ValueError("OHLCV data cannot be empty.")


def resample_ohlcv(
    data: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    """
    Resample OHLCV data into a supported timeframe.

    Parameters
    ----------
    data:
        OHLCV DataFrame indexed by timestamps.

    timeframe:
        One of: 5m, 10m, 15m, 30m.

    Returns
    -------
    pd.DataFrame
        Resampled OHLCV data containing only complete candles.
    """

    validate_ohlcv(data)

    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}. "
            f"Supported: {list(SUPPORTED_TIMEFRAMES)}"
        )

    data = data.sort_index().copy()

    rule = SUPPORTED_TIMEFRAMES[timeframe]

    resampled = data.resample(
        rule,
        origin="start_day",
        offset="15min",
        label="left",
        closed="left",
    )

    result = resampled.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    # A valid higher-timeframe candle must contain
    # the expected number of source 1-minute candles.
    expected_rows = int(rule.removesuffix("min"))

    row_counts = resampled["close"].count()

    complete_candles = row_counts == expected_rows

    result = result.loc[complete_candles]

    # Remove any candle containing missing OHLC values.
    result = result.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
        ]
    )

    return result


def build_all_timeframes(
    data: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build all SignalForge intraday timeframes."""

    return {
        timeframe: resample_ohlcv(data, timeframe)
        for timeframe in SUPPORTED_TIMEFRAMES
    }
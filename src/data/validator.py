"""Validation utilities for SignalForge market data."""

import pandas as pd


REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


def validate_market_data(data: pd.DataFrame) -> None:
    """
    Validate the structure and basic integrity of OHLCV market data.

    The DataFrame must:
    - use a DatetimeIndex
    - contain open, high, low, close and volume
    - have no duplicate timestamps
    - be sorted chronologically
    - contain valid OHLC relationships
    - contain non-negative volume
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Market data cannot be empty.")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError(
            "Market data index must be a pandas DatetimeIndex."
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

    if data.index.has_duplicates:
        raise ValueError(
            "Market data contains duplicate timestamps."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Market data timestamps must be sorted "
            "in ascending order."
        )

    numeric_columns = list(REQUIRED_COLUMNS)

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise TypeError(
                f"Column '{column}' must contain numeric values."
            )

    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError(
            "Market data contains missing OHLCV values."
        )

    invalid_high = (
        (data["high"] < data["open"])
        | (data["high"] < data["close"])
    )

    if invalid_high.any():
        raise ValueError(
            "Market data contains invalid high values."
        )

    invalid_low = (
        (data["low"] > data["open"])
        | (data["low"] > data["close"])
    )

    if invalid_low.any():
        raise ValueError(
            "Market data contains invalid low values."
        )

    if (data["volume"] < 0).any():
        raise ValueError(
            "Market data contains negative volume."
        )
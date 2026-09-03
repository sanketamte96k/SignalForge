from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class MarketDataAdapter(ABC):
    """
    Abstract interface for market-data providers.

    Implementations must return validated chronological
    OHLCV candle data.
    """

    @abstractmethod
    def get_latest_candle(self) -> pd.Series:
        """Return the latest available candle."""
        raise NotImplementedError

    @abstractmethod
    def get_recent_candles(
        self,
        limit: int,
    ) -> pd.DataFrame:
        """Return the most recent candles."""
        raise NotImplementedError


class MarketDataValidationError(ValueError):
    """Raised when market data fails validation."""


def validate_market_data(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validate and normalize market-data candles.

    Returns a defensive copy sorted chronologically with
    duplicate timestamps removed.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "Market data must be a pandas DataFrame."
        )

    if data.empty:
        raise MarketDataValidationError(
            "Market data cannot be empty."
        )

    if not isinstance(data.index, pd.DatetimeIndex):
        raise MarketDataValidationError(
            "Market data index must be a DatetimeIndex."
        )

    missing_columns = (
        set(REQUIRED_COLUMNS)
        - set(data.columns)
    )

    if missing_columns:
        raise MarketDataValidationError(
            "Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    validated = data.loc[
        :,
        list(REQUIRED_COLUMNS),
    ].copy()

    validated = validated.sort_index()

    validated = validated[
        ~validated.index.duplicated(
            keep="last"
        )
    ]

    for column in REQUIRED_COLUMNS:
        validated[column] = pd.to_numeric(
            validated[column],
            errors="coerce",
        )

    if validated[list(REQUIRED_COLUMNS)].isna().any().any():
        raise MarketDataValidationError(
            "Market data contains missing or "
            "non-numeric OHLCV values."
        )

    if not validated.index.is_monotonic_increasing:
        raise MarketDataValidationError(
            "Market data must be chronologically ordered."
        )

    if (validated["high"] < validated["low"]).any():
        raise MarketDataValidationError(
            "Candle high cannot be below candle low."
        )

    if (
        (validated["open"] > validated["high"])
        | (validated["open"] < validated["low"])
    ).any():
        raise MarketDataValidationError(
            "Candle open must be between high and low."
        )

    if (
        (validated["close"] > validated["high"])
        | (validated["close"] < validated["low"])
    ).any():
        raise MarketDataValidationError(
            "Candle close must be between high and low."
        )

    if (validated["volume"] < 0).any():
        raise MarketDataValidationError(
            "Volume cannot be negative."
        )

    return validated
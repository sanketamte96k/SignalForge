"""Provider-agnostic market data domain models, contracts, and interfaces for SignalForge.

This module defines the provider-independent market data abstraction layer:
- MarketDataRequest: Standardized parameters for historical market data requests.
- MarketDataResult: Standardized container for returned and normalized market data.
- MarketDataProvider: Abstract interface that all data providers must implement.
- Canonical OHLCV contract and validation rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any

import pandas as pd


CANONICAL_OHLCV_COLUMNS = (
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
)

SUPPORTED_INTERVAL_PATTERN = re.compile(r"^\d+(m|h|d|wk|mo)$", re.IGNORECASE)

_COLUMN_RENAME_MAP = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


def normalize_ohlcv_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names to canonical Title Case OHLCV.

    Maps case-insensitively (e.g. 'open' -> 'Open', 'VOLUME' -> 'Volume').
    Returns a copy with renamed columns.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    rename_dict: dict[Any, str] = {}
    for col in data.columns:
        col_str = str(col).strip().lower()
        if col_str in _COLUMN_RENAME_MAP:
            rename_dict[col] = _COLUMN_RENAME_MAP[col_str]

    return data.rename(columns=rename_dict)


def validate_normalized_ohlcv(data: pd.DataFrame) -> None:
    """Validate DataFrame against canonical SignalForge OHLCV contract.

    Contract rules:
    - Must be a pandas DataFrame.
    - Cannot be empty.
    - Index must be a pd.DatetimeIndex.
    - Index must not contain NaT (malformed timestamps).
    - Index must not contain duplicate timestamps.
    - Index must be sorted in ascending order (monotonic increasing).
    - Must contain canonical columns: Open, High, Low, Close, Volume.
    - All canonical columns must be numeric.
    - No NaN values permitted in canonical OHLCV columns.
    - High must be >= Open and >= Close.
    - Low must be <= Open and <= Close.
    - High must be >= Low.
    - Volume must be >= 0 (no negative volume).

    Raises TypeError or ValueError on violation.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Market data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Market data cannot be empty.")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("Market data index must be a pandas DatetimeIndex.")

    if data.index.isna().any():
        raise ValueError("Market data index contains NaT (malformed timestamp).")

    if data.index.has_duplicates:
        raise ValueError("Market data contains duplicate timestamps.")

    if not data.index.is_monotonic_increasing:
        raise ValueError("Market data timestamps must be sorted in ascending order.")

    missing_cols = [col for col in CANONICAL_OHLCV_COLUMNS if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required canonical columns: {missing_cols}")

    for col in CANONICAL_OHLCV_COLUMNS:
        if not pd.api.types.is_numeric_dtype(data[col]):
            raise TypeError(f"Column '{col}' must contain numeric values.")

    if data[list(CANONICAL_OHLCV_COLUMNS)].isna().any().any():
        raise ValueError("Market data contains NaN OHLCV values.")

    invalid_high = (data["High"] < data["Open"]) | (data["High"] < data["Close"])
    if invalid_high.any():
        raise ValueError("Market data contains invalid High values (< Open or Close).")

    invalid_low = (data["Low"] > data["Open"]) | (data["Low"] > data["Close"])
    if invalid_low.any():
        raise ValueError("Market data contains invalid Low values (> Open or Close).")

    if (data["High"] < data["Low"]).any():
        raise ValueError("Market data contains invalid High < Low relationships.")

    if (data["Volume"] < 0).any():
        raise ValueError("Market data contains negative volume.")


@dataclass(frozen=True)
class MarketDataRequest:
    """Standardized request for historical market data.

    Parameters
    ----------
    symbol:
        Stock or asset ticker symbol (e.g. 'TCS', 'RELIANCE').
    exchange:
        Exchange identifier (e.g. 'NSE', 'BSE').
    interval:
        Bar interval (e.g. '1m', '5m', '15m', '1d').
    start:
        Start of the requested range (inclusive / best-effort).
    end:
        End of the requested range (inclusive / best-effort).
    adjusted:
        Whether to adjust prices for splits/dividends. Defaults to False.
    """

    symbol: str
    exchange: str = "NSE"
    interval: str = "1m"
    start: str | datetime | date | pd.Timestamp | None = None
    end: str | datetime | date | pd.Timestamp | None = None
    adjusted: bool = False

    def __post_init__(self) -> None:
        """Validate request invariants upon instantiation."""
        if not isinstance(self.symbol, str):
            raise TypeError("symbol must be a string.")
        norm_symbol = self.symbol.strip().upper()
        if not norm_symbol:
            raise ValueError("symbol must not be empty.")
        object.__setattr__(self, "symbol", norm_symbol)

        if not isinstance(self.exchange, str):
            raise TypeError("exchange must be a string.")
        norm_exchange = self.exchange.strip().upper()
        if not norm_exchange:
            raise ValueError("exchange must not be empty.")
        object.__setattr__(self, "exchange", norm_exchange)

        if not isinstance(self.interval, str):
            raise TypeError("interval must be a string.")
        norm_interval = self.interval.strip().lower()
        if not norm_interval:
            raise ValueError("interval must not be empty.")
        if not SUPPORTED_INTERVAL_PATTERN.match(norm_interval):
            raise ValueError(
                f"Invalid interval: '{self.interval}'. "
                "Expected formats like '1m', '5m', '15m', '1h', '1d'."
            )
        object.__setattr__(self, "interval", norm_interval)

        if not isinstance(self.adjusted, bool):
            raise TypeError("adjusted must be a boolean.")

        # Validate start/end order if both are provided
        if self.start is not None and self.end is not None:
            try:
                start_ts = pd.Timestamp(self.start)
                end_ts = pd.Timestamp(self.end)
            except Exception as e:
                raise ValueError(f"Failed to parse start or end date: {e}") from e

            if start_ts > end_ts:
                raise ValueError(
                    f"Start date ({self.start}) must be before or equal to "
                    f"end date ({self.end})."
                )


@dataclass
class MarketDataResult:
    """Standardized result envelope for market data queries.

    Parameters
    ----------
    symbol:
        Normalized ticker symbol.
    exchange:
        Normalized exchange identifier.
    interval:
        Normalized bar interval.
    data:
        pandas DataFrame conforming to canonical OHLCV contract.
    provider:
        Name of the provider that served this request.
    requested_start:
        Start boundary originally requested.
    requested_end:
        End boundary originally requested.
    metadata:
        Provider-specific provenance, checksum, or audit metadata.
    """

    symbol: str
    exchange: str
    interval: str
    data: pd.DataFrame
    provider: str
    requested_start: str | datetime | date | pd.Timestamp | None = None
    requested_end: str | datetime | date | pd.Timestamp | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate that the contained data satisfies the canonical OHLCV contract."""
        validate_normalized_ohlcv(self.data)


class MarketDataProvider(ABC):
    """Abstract interface for all SignalForge market data providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique canonical identifier for this provider."""
        raise NotImplementedError

    @abstractmethod
    def get_historical(self, request: MarketDataRequest) -> MarketDataResult:
        """Fetch historical market data matching the request.

        Implementations must return a MarketDataResult whose data conforms
        to the canonical OHLCV contract.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is available and ready to serve requests."""
        raise NotImplementedError

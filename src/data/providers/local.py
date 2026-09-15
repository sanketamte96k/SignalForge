"""Local historical market data provider for SignalForge.

This provider reads pre-existing datasets stored in local storage (CSV/Parquet).
It strictly adheres to the following constraints:
- ONLY reads local datasets; NEVER downloads from external sources.
- NEVER modifies production files or directories.
- NEVER synthesizes missing candles or interpolates data.
- NEVER bypasses validation; ensures canonical OHLCV normalization contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data.acquisition import DataDirectoryContract, compute_checksum
from src.data.market_data import (
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    normalize_ohlcv_columns,
    validate_normalized_ohlcv,
)


class LocalProvider(MarketDataProvider):
    """Provider reading historical OHLCV data from local filesystem storage."""

    def __init__(
        self,
        data_directory: str | Path | None = None,
    ) -> None:
        if data_directory is not None:
            self.data_directory = Path(data_directory)
        else:
            self.data_directory = DataDirectoryContract().stocks_dir

    @property
    def provider_name(self) -> str:
        """Canonical provider identifier."""
        return "local"

    def is_available(self) -> bool:
        """Return True if local storage directory exists."""
        return self.data_directory.exists() and self.data_directory.is_dir()

    def resolve_path(self, symbol: str, interval: str = "1m") -> Path:
        """Resolve expected local file path for a symbol and interval."""
        clean_symbol = symbol.strip().upper()
        # Check standard CSV naming pattern
        csv_path = self.data_directory / f"{clean_symbol}_{interval}.csv"
        if csv_path.exists():
            return csv_path

        # Check standard Parquet naming pattern
        parquet_path = self.data_directory / f"{clean_symbol}_{interval}.parquet"
        if parquet_path.exists():
            return parquet_path

        # Check if plain symbol file exists (e.g. SYMBOL.csv)
        plain_csv = self.data_directory / f"{clean_symbol}.csv"
        if plain_csv.exists():
            return plain_csv

        # Default to standard CSV path for clear error reporting
        return csv_path

    def get_historical(self, request: MarketDataRequest) -> MarketDataResult:
        """Load and normalize historical data from local storage.

        Parameters
        ----------
        request:
            The validated MarketDataRequest.

        Returns
        -------
        MarketDataResult
            Envelope containing canonical OHLCV data and metadata.
        """
        file_path = self.resolve_path(request.symbol, request.interval)
        if not file_path.exists():
            raise FileNotFoundError(
                f"Local market data not found for symbol '{request.symbol}' "
                f"(interval: {request.interval}) at path: {file_path}"
            )

        # Read file without altering it
        if file_path.suffix.lower() == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
        df.index.name = None

        # Normalize column names to canonical Title Case
        df = normalize_ohlcv_columns(df)

        # Apply date range filtering if requested
        if request.start is not None:
            start_ts = pd.Timestamp(request.start)
            if df.index.tz is not None and start_ts.tz is None:
                start_ts = start_ts.tz_localize(df.index.tz)
            elif df.index.tz is None and start_ts.tz is not None:
                start_ts = start_ts.tz_localize(None)
            df = df[df.index >= start_ts]

        if request.end is not None:
            end_ts = pd.Timestamp(request.end)
            if df.index.tz is not None and end_ts.tz is None:
                end_ts = end_ts.tz_localize(df.index.tz)
            elif df.index.tz is None and end_ts.tz is not None:
                end_ts = end_ts.tz_localize(None)
            df = df[df.index <= end_ts]

        # Invariant check: validate against canonical contract
        validate_normalized_ohlcv(df)

        # Audit provenance metadata
        checksum = compute_checksum(file_path)
        metadata: dict[str, Any] = {
            "source_file": str(file_path),
            "file_checksum": checksum,
            "row_count": len(df),
            "storage_format": file_path.suffix.lstrip(".").lower(),
        }

        return MarketDataResult(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            data=df,
            provider=self.provider_name,
            requested_start=request.start,
            requested_end=request.end,
            metadata=metadata,
        )

"""Stock-specific market data provider for SignalForge."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.downloader import (
    download_market_data,
    load_market_data,
    save_market_data,
)


class StockDataProvider:
    """
    Provide historical and recent OHLCV data for NSE stocks.

    This class is responsible only for stock symbol normalization and
    market-data acquisition/storage. Validation and signal generation
    remain separate concerns.
    """

    def __init__(
        self,
        *,
        data_directory: str | Path = "data/historical/stocks",
        exchange_suffix: str = ".NS",
    ) -> None:
        self.data_directory = Path(data_directory)
        self.exchange_suffix = self._normalize_suffix(
            exchange_suffix
        )

    def yahoo_ticker(self, symbol: str) -> str:
        """Convert a SignalForge stock symbol to its Yahoo ticker."""

        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol.endswith(self.exchange_suffix):
            return normalized_symbol

        return f"{normalized_symbol}{self.exchange_suffix}"

    def local_path(self, symbol: str) -> Path:
        """Return the standard local historical-data path."""

        normalized_symbol = self._normalize_symbol(symbol)
        target = self.data_directory / f"{normalized_symbol}_1m.csv"

        from src.core.security import validate_safe_path
        validate_safe_path(target, self.data_directory)

        return target

    def download(
        self,
        symbol: str,
        *,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1m",
    ) -> pd.DataFrame:
        """
        Download stock market data using the existing downloader.
        """

        ticker = self.yahoo_ticker(symbol)

        return download_market_data(
            ticker=ticker,
            start=start,
            end=end,
            interval=interval,
        )

    def save(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> Path:
        """Save stock market data to the standard local path."""

        path = self.local_path(symbol)

        return save_market_data(
            data=data,
            path=path,
        )

    def load(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """Load locally stored stock market data."""

        path = self.local_path(symbol)

        return load_market_data(path)

    def download_and_save(
        self,
        symbol: str,
        *,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1m",
    ) -> pd.DataFrame:
        """Download stock data and save the validated result."""

        data = self.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
        )

        self.save(
            symbol,
            data,
        )

        return data

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""

        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string.")

        from src.core.security import validate_symbol
        return validate_symbol(symbol)

    @staticmethod
    def _normalize_suffix(suffix: str) -> str:
        """Normalize the exchange suffix."""

        if not isinstance(suffix, str):
            raise TypeError(
                "exchange_suffix must be a string."
            )

        normalized = suffix.strip().upper()

        if not normalized:
            raise ValueError(
                "exchange_suffix must not be empty."
            )

        if not normalized.startswith("."):
            normalized = f".{normalized}"

        return normalized

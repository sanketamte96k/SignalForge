"""Historical stock CSV importer for SignalForge."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.validator import validate_market_data
from src.data.stock_provider import StockDataProvider


class StockDataImporter:
    """
    Import externally supplied historical stock data.

    Import is deliberately separate from downloading and validation.
    The imported dataset must pass SignalForge market-data validation
    before it is stored as the stock's local dataset.
    """

    def __init__(
        self,
        provider: StockDataProvider | None = None,
    ) -> None:
        self.provider = provider or StockDataProvider()

    def import_csv(
        self,
        symbol: str,
        source_path: str | Path,
    ) -> pd.DataFrame:
        """
        Import an OHLCV CSV and save it as the stock's local dataset.

        The source CSV must contain:
            timestamp/index + open + high + low + close + volume

        The timestamp may be stored either as the CSV index or in a
        column named timestamp, Datetime, datetime, or date.
        """

        normalized_symbol = self._normalize_symbol(symbol)
        input_path = Path(source_path)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Source CSV file not found: {input_path}"
            )

        if not input_path.is_file():
            raise ValueError(
                f"Source path is not a file: {input_path}"
            )

        try:
            data = self._read_csv(input_path)
        except Exception as exc:
            raise ValueError(
                f"Unable to read stock CSV: {exc}"
            ) from exc

        normalized_data = self._normalize_columns(data)

        validate_market_data(normalized_data)

        self.provider.save(
            normalized_symbol,
            normalized_data,
        )

        return normalized_data

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        """Read a CSV while supporting common timestamp layouts."""

        raw = pd.read_csv(path)

        if raw.empty:
            raise ValueError("Source CSV is empty.")

        timestamp_column = StockDataImporter._find_timestamp_column(
            raw.columns
        )

        if timestamp_column is not None:
            timestamps = pd.to_datetime(
                raw[timestamp_column],
                errors="raise",
            )

            data = raw.drop(columns=[timestamp_column]).copy()
            data.index = pd.DatetimeIndex(timestamps)
            return data

        if len(raw.columns) < 6:
            raise ValueError(
                "CSV must contain a timestamp and OHLCV columns."
            )

        first_column = raw.columns[0]

        try:
            timestamps = pd.to_datetime(
                raw[first_column],
                errors="raise",
            )
        except Exception as exc:
            raise ValueError(
                "CSV does not contain a recognizable timestamp column."
            ) from exc

        data = raw.drop(columns=[first_column]).copy()
        data.index = pd.DatetimeIndex(timestamps)

        return data

    @staticmethod
    def _find_timestamp_column(
        columns: pd.Index,
    ) -> str | None:
        """Find a conventional timestamp column name."""

        candidates = {
            "timestamp",
            "datetime",
            "date",
            "time",
        }

        for column in columns:
            if str(column).strip().lower() in candidates:
                return column

        return None

    @staticmethod
    def _normalize_columns(
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Normalize common OHLCV column naming conventions."""

        normalized = data.copy()

        rename_map: dict[object, str] = {}

        for column in normalized.columns:
            key = str(column).strip().lower()

            if key == "open":
                rename_map[column] = "open"
            elif key == "high":
                rename_map[column] = "high"
            elif key == "low":
                rename_map[column] = "low"
            elif key == "close":
                rename_map[column] = "close"
            elif key in {"volume", "vol"}:
                rename_map[column] = "volume"

        normalized = normalized.rename(columns=rename_map)

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = sorted(
            required_columns - set(normalized.columns)
        )

        if missing:
            raise ValueError(
                "CSV is missing required OHLCV columns: "
                f"{missing}"
            )

        return normalized[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ].copy()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""

        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string.")

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError("symbol must not be empty.")

        return normalized
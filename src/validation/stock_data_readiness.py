"""Historical stock-data readiness checks for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.stock_provider import StockDataProvider


REQUIRED_START = pd.Timestamp("2015-01-01")
REQUIRED_END = pd.Timestamp("2024-03-26 15:29:00")


@dataclass(frozen=True)
class StockDataReadinessResult:
    """Result of checking whether stock data is ready for validation."""

    symbol: str
    available: bool
    path: str
    total_rows: int
    first_timestamp: pd.Timestamp | None
    last_timestamp: pd.Timestamp | None
    required_start: pd.Timestamp
    required_end: pd.Timestamp
    covers_required_period: bool
    issues: tuple[str, ...]

    @property
    def ready(self) -> bool:
        """Return whether the dataset is ready for validation."""

        return (
            self.available
            and self.covers_required_period
            and not self.issues
        )

    @property
    def missing(self) -> bool:
        """Return whether the local dataset does not exist."""

        return not self.available


class StockDataReadinessChecker:
    """
    Check whether a stock has sufficient local history for validation.

    This class does not download data and does not change universe status.
    """

    def __init__(
        self,
        provider: StockDataProvider | None = None,
        *,
        required_start: pd.Timestamp = REQUIRED_START,
        required_end: pd.Timestamp = REQUIRED_END,
    ) -> None:
        self.provider = provider or StockDataProvider()
        self.required_start = pd.Timestamp(required_start)
        self.required_end = pd.Timestamp(required_end)

        if self.required_start > self.required_end:
            raise ValueError(
                "required_start must not be after required_end."
            )

    def check(self, symbol: str) -> StockDataReadinessResult:
        """Check local historical-data readiness for a stock."""

        normalized_symbol = self._normalize_symbol(symbol)
        path = self.provider.local_path(normalized_symbol)

        if not path.exists():
            return StockDataReadinessResult(
                symbol=normalized_symbol,
                available=False,
                path=str(path),
                total_rows=0,
                first_timestamp=None,
                last_timestamp=None,
                required_start=self.required_start,
                required_end=self.required_end,
                covers_required_period=False,
                issues=(
                    f"Historical data file not found: {path}",
                ),
            )

        try:
            data = self.provider.load(normalized_symbol)
        except Exception as exc:
            return StockDataReadinessResult(
                symbol=normalized_symbol,
                available=False,
                path=str(path),
                total_rows=0,
                first_timestamp=None,
                last_timestamp=None,
                required_start=self.required_start,
                required_end=self.required_end,
                covers_required_period=False,
                issues=(
                    f"Historical data could not be loaded: {exc}",
                ),
            )

        if data.empty:
            return StockDataReadinessResult(
                symbol=normalized_symbol,
                available=True,
                path=str(path),
                total_rows=0,
                first_timestamp=None,
                last_timestamp=None,
                required_start=self.required_start,
                required_end=self.required_end,
                covers_required_period=False,
                issues=(
                    "Historical data file is empty.",
                ),
            )

        first_timestamp = pd.Timestamp(data.index.min())
        last_timestamp = pd.Timestamp(data.index.max())

        issues: list[str] = []

        if first_timestamp > self.required_start:
            issues.append(
                "Historical data starts after the required "
                f"validation start: {first_timestamp}."
            )

        if last_timestamp < self.required_end:
            issues.append(
                "Historical data ends before the required "
                f"validation end: {last_timestamp}."
            )

        covers_required_period = (
            first_timestamp <= self.required_start
            and last_timestamp >= self.required_end
        )

        if not covers_required_period and not issues:
            issues.append(
                "Historical data does not cover the complete "
                "required validation period."
            )

        return StockDataReadinessResult(
            symbol=normalized_symbol,
            available=True,
            path=str(path),
            total_rows=len(data),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            required_start=self.required_start,
            required_end=self.required_end,
            covers_required_period=covers_required_period,
            issues=tuple(issues),
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""

        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string.")

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError("symbol must not be empty.")

        return normalized

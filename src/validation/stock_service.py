"""Stock validation orchestration service for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.stock_provider import StockDataProvider
from src.universe.manager import UniverseManager
from src.universe.validation import ValidationStatus
from src.validation.stock_data_readiness import StockDataReadinessChecker
from src.validation.stock_validator import (
    StockValidationResult,
    StockValidationRunner,
)


@dataclass(frozen=True)
class StockValidationService:
    """
    Coordinate stock-data readiness, validation, and universe status updates.

    The service does not alter the validation rules. It delegates all
    validation decisions to StockValidationRunner and only mirrors the
    resulting status into the supplied UniverseManager.

    Historical-data readiness is checked before local validation so that
    incomplete or missing datasets cannot enter the validation pipeline.
    """

    provider: StockDataProvider
    runner: StockValidationRunner
    universe: UniverseManager
    readiness_checker: StockDataReadinessChecker | None = None

    def __post_init__(self) -> None:
        """Create the default readiness checker when one is not supplied."""

        if self.readiness_checker is None:
            object.__setattr__(
                self,
                "readiness_checker",
                StockDataReadinessChecker(provider=self.provider),
            )

    def validate(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> StockValidationResult:
        """Validate a stock using an explicitly supplied dataset."""

        normalized_symbol = self._normalize_symbol(symbol)

        if not self.universe.contains(normalized_symbol):
            raise KeyError(
                f"Unknown stock symbol: {normalized_symbol}"
            )

        return self.runner.validate(
            normalized_symbol,
            data,
        )

    def check_data_readiness(self, symbol: str):
        """Check whether local historical data is ready for validation."""

        normalized_symbol = self._normalize_symbol(symbol)

        if not self.universe.contains(normalized_symbol):
            raise KeyError(
                f"Unknown stock symbol: {normalized_symbol}"
            )

        if self.readiness_checker is None:
            raise RuntimeError("Readiness checker is not configured.")

        return self.readiness_checker.check(normalized_symbol)

    def validate_from_local(
        self,
        symbol: str,
    ) -> StockValidationResult:
        """
        Load locally stored historical data and validate it.

        Readiness is checked before loading the dataset into the validation
        pipeline. No network request is made by this method.
        """

        normalized_symbol = self._normalize_symbol(symbol)

        readiness = self.check_data_readiness(normalized_symbol)

        if not readiness.ready:
            raise ValueError(
                "Stock historical data is not ready for validation: "
                + " ".join(readiness.issues)
            )

        data = self.provider.load(
            normalized_symbol,
        )

        return self.validate(
            normalized_symbol,
            data,
        )

    def validate_and_update_universe(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> StockValidationResult:
        """
        Validate a stock and mirror the resulting status in the universe.

        A stock becomes signal eligible only when the complete validation
        pipeline approves it.
        """

        result = self.validate(
            symbol,
            data,
        )

        self.universe.set_validation_status(
            result.symbol,
            result.status,
        )

        return result

    def validate_from_local_and_update_universe(
        self,
        symbol: str,
    ) -> StockValidationResult:
        """Load local data, validate it, and update its universe status."""

        normalized_symbol = self._normalize_symbol(symbol)

        readiness = self.check_data_readiness(normalized_symbol)

        if not readiness.ready:
            raise ValueError(
                "Stock historical data is not ready for validation: "
                + " ".join(readiness.issues)
            )

        data = self.provider.load(
            normalized_symbol,
        )

        return self.validate_and_update_universe(
            normalized_symbol,
            data,
        )

    def validation_status(
        self,
        symbol: str,
    ) -> ValidationStatus:
        """Return the current validation status in the universe."""

        normalized_symbol = self._normalize_symbol(symbol)

        if not self.universe.contains(normalized_symbol):
            raise KeyError(
                f"Unknown stock symbol: {normalized_symbol}"
            )

        return self.universe.get_validation_status(
            normalized_symbol,
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""

        if not isinstance(symbol, str):
            raise TypeError(
                "symbol must be a string."
            )

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol must not be empty."
            )

        return normalized

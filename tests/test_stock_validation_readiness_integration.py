"""Tests for stock-data readiness integration."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.stock_provider import StockDataProvider
from src.universe.manager import UniverseManager
from src.validation.approval import ApprovalResult
from src.validation.stock_data_readiness import StockDataReadinessChecker
from src.validation.stock_service import StockValidationService
from src.validation.stock_validator import StockValidationResult
from src.universe.validation import ValidationStatus


class FakeProvider:
    def __init__(self, data: pd.DataFrame | None = None) -> None:
        self.data = data
        self.loaded_symbols: list[str] = []

    def local_path(self, symbol: str) -> Path:
        return Path("data/historical/stocks") / f"{symbol}.NS.csv"

    def load(self, symbol: str) -> pd.DataFrame:
        self.loaded_symbols.append(symbol)

        if self.data is None:
            raise FileNotFoundError(symbol)

        return self.data.copy()


class FakeReadinessChecker:
    def __init__(self, ready: bool, issues: tuple[str, ...] = ()) -> None:
        self.ready = ready
        self.issues = issues
        self.checked_symbols: list[str] = []

    def check(self, symbol: str):
        self.checked_symbols.append(symbol)

        return type(
            "FakeReadinessResult",
            (),
            {
                "ready": self.ready,
                "issues": self.issues,
            },
        )()


class FakeRunner:
    def __init__(self, result: StockValidationResult) -> None:
        self.result = result
        self.called = False

    def validate(self, symbol: str, data: pd.DataFrame):
        self.called = True
        return self.result


def make_result(symbol: str) -> StockValidationResult:
    approval = ApprovalResult(
        status=ValidationStatus.VALIDATED,
        signal_eligible=True,
        approved=True,
        passed_gates=(
            "DATA_AVAILABILITY",
            "DATA_QUALITY",
            "INDICATOR_COMPATIBILITY",
            "HISTORICAL_BACKTEST",
            "CAUSALITY",
            "COST_SLIPPAGE",
            "REGIME_OOS",
        ),
        failed_gates=(),
        issues=(),
    )

    return StockValidationResult(
        symbol=symbol,
        data_availability=None,
        data_quality=None,
        indicator_compatibility=None,
        historical_backtest=None,
        causality=None,
        cost_slippage=None,
        regime_oos=None,
        approval=approval,
    )


def make_data() -> pd.DataFrame:
    index = pd.date_range(
        "2020-01-01 09:15",
        periods=3,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        index=index,
    )


def make_service(
    *,
    readiness: FakeReadinessChecker,
    provider: FakeProvider,
    runner: FakeRunner,
) -> StockValidationService:
    universe = UniverseManager()

    universe.add_instrument(
        symbol="TESTSTOCK",
        name="Test Stock",
    )

    return StockValidationService(
        provider=provider,
        runner=runner,
        universe=universe,
        readiness_checker=readiness,
    )


def test_local_validation_checks_readiness_before_loading_data() -> None:
    provider = FakeProvider(make_data())
    readiness = FakeReadinessChecker(
        ready=False,
        issues=("historical data is incomplete",),
    )
    runner = FakeRunner(make_result("TESTSTOCK"))

    service = make_service(
        readiness=readiness,
        provider=provider,
        runner=runner,
    )

    with pytest.raises(ValueError, match="historical data is incomplete"):
        service.validate_from_local("TESTSTOCK")

    assert readiness.checked_symbols == ["TESTSTOCK"]
    assert provider.loaded_symbols == []
    assert runner.called is False


def test_local_validation_runs_only_when_data_is_ready() -> None:
    provider = FakeProvider(make_data())
    readiness = FakeReadinessChecker(ready=True)
    runner = FakeRunner(make_result("TESTSTOCK"))

    service = make_service(
        readiness=readiness,
        provider=provider,
        runner=runner,
    )

    result = service.validate_from_local("TESTSTOCK")

    assert result.symbol == "TESTSTOCK"
    assert readiness.checked_symbols == ["TESTSTOCK"]
    assert provider.loaded_symbols == ["TESTSTOCK"]
    assert runner.called is True


def test_local_validation_update_checks_readiness_before_status_update() -> None:
    provider = FakeProvider(make_data())
    readiness = FakeReadinessChecker(
        ready=False,
        issues=("required historical period is missing",),
    )
    runner = FakeRunner(make_result("TESTSTOCK"))

    service = make_service(
        readiness=readiness,
        provider=provider,
        runner=runner,
    )

    with pytest.raises(
        ValueError,
        match="required historical period is missing",
    ):
        service.validate_from_local_and_update_universe("TESTSTOCK")

    assert service.validation_status("TESTSTOCK") is ValidationStatus.TESTING
    assert provider.loaded_symbols == []
    assert runner.called is False


def test_readiness_unknown_stock_is_rejected() -> None:
    provider = FakeProvider(make_data())
    readiness = FakeReadinessChecker(ready=True)
    runner = FakeRunner(make_result("UNKNOWN"))

    service = StockValidationService(
        provider=provider,
        runner=runner,
        universe=UniverseManager(),
        readiness_checker=readiness,
    )

    with pytest.raises(KeyError, match="Unknown stock symbol"):
        service.check_data_readiness("UNKNOWN")

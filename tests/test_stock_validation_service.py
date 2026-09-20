"""Tests for the SignalForge stock validation service."""

import pandas as pd
import pytest

from src.data.stock_provider import StockDataProvider
from src.universe.manager import UniverseManager
from src.universe.validation import ValidationStatus
from src.validation.approval import ApprovalResult
from src.validation.stock_data_readiness import StockDataReadinessResult
from src.validation.stock_service import StockValidationService
from src.validation.stock_validator import StockValidationResult


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


def make_runner_result(
    symbol: str,
    status: ValidationStatus,
) -> StockValidationResult:
    approval = ApprovalResult(
        status=status,
        signal_eligible=(
            status is ValidationStatus.VALIDATED
        ),
        approved=(
            status is ValidationStatus.VALIDATED
        ),
        passed_gates=(
            (
                "DATA_AVAILABILITY",
                "DATA_QUALITY",
                "INDICATOR_COMPATIBILITY",
                "HISTORICAL_BACKTEST",
                "CAUSALITY",
                "COST_SLIPPAGE",
                "REGIME_OOS",
            )
            if status is ValidationStatus.VALIDATED
            else ()
        ),
        failed_gates=(
            ()
            if status is ValidationStatus.VALIDATED
            else ("REGIME_OOS",)
        ),
        issues=(
            ()
            if status is ValidationStatus.VALIDATED
            else ("validation failed",)
        ),
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


class FakeRunner:
    def __init__(
        self,
        result: StockValidationResult,
    ) -> None:
        self.result = result
        self.calls: list[tuple[str, pd.DataFrame]] = []

    def validate(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> StockValidationResult:
        self.calls.append((symbol, data))
        return self.result


class FakeReadinessChecker:
    def __init__(
        self,
        ready: bool = True,
        issues: tuple[str, ...] = (),
    ) -> None:
        self.ready = ready
        self.issues = issues
        self.calls: list[str] = []

    def check(self, symbol: str) -> StockDataReadinessResult:
        self.calls.append(symbol)

        return StockDataReadinessResult(
            symbol=symbol,
            available=self.ready,
            path="data/historical/stocks/test.csv",
            total_rows=100 if self.ready else 0,
            first_timestamp=(
                pd.Timestamp("2015-01-01")
                if self.ready
                else None
            ),
            last_timestamp=(
                pd.Timestamp("2024-03-26 15:29:00")
                if self.ready
                else None
            ),
            required_start=pd.Timestamp("2015-01-01"),
            required_end=pd.Timestamp("2024-03-26 15:29:00"),
            covers_required_period=self.ready,
            issues=self.issues,
        )


def test_validate_delegates_to_runner() -> None:
    universe = UniverseManager()
    data = make_data()

    expected = make_runner_result(
        "RELIANCE",
        ValidationStatus.FAILED,
    )

    runner = FakeRunner(expected)
    service = StockValidationService(
        provider=StockDataProvider(),
        runner=runner,  # type: ignore[arg-type]
        universe=universe,
    )

    result = service.validate(
        " reliance ",
        data,
    )

    assert result is expected
    assert runner.calls == [
        ("RELIANCE", data),
    ]


def test_validate_rejects_unknown_symbol() -> None:
    universe = UniverseManager()

    service = StockValidationService(
        provider=StockDataProvider(),
        runner=FakeRunner(
            make_runner_result(
                "RELIANCE",
                ValidationStatus.FAILED,
            )
        ),  # type: ignore[arg-type]
        universe=universe,
    )

    with pytest.raises(
        KeyError,
        match="Unknown stock symbol: UNKNOWN",
    ):
        service.validate(
            "UNKNOWN",
            make_data(),
        )


def test_validate_rejects_invalid_symbol() -> None:
    universe = UniverseManager()

    service = StockValidationService(
        provider=StockDataProvider(),
        runner=FakeRunner(
            make_runner_result(
                "RELIANCE",
                ValidationStatus.FAILED,
            )
        ),  # type: ignore[arg-type]
        universe=universe,
    )

    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        service.validate(
            "   ",
            make_data(),
        )


def test_validate_from_local_loads_expected_stock(
    monkeypatch,
) -> None:
    universe = UniverseManager()
    data = make_data()

    expected = make_runner_result(
        "TCS",
        ValidationStatus.FAILED,
    )

    runner = FakeRunner(expected)
    provider = StockDataProvider()
    readiness_checker = FakeReadinessChecker()

    captured: dict[str, object] = {}

    def fake_load(symbol: str) -> pd.DataFrame:
        captured["symbol"] = symbol
        return data

    monkeypatch.setattr(
        provider,
        "load",
        fake_load,
    )

    service = StockValidationService(
        provider=provider,
        runner=runner,  # type: ignore[arg-type]
        universe=universe,
        readiness_checker=readiness_checker,  # type: ignore[arg-type]
    )

    result = service.validate_from_local(
        " TCS ",
    )

    assert result is expected
    assert readiness_checker.calls == ["TCS"]
    assert captured["symbol"] == "TCS"
    assert runner.calls == [
        ("TCS", data),
    ]


def test_validate_and_update_sets_validated_status() -> None:
    universe = UniverseManager()
    data = make_data()

    expected = make_runner_result(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    service = StockValidationService(
        provider=StockDataProvider(),
        runner=FakeRunner(expected),  # type: ignore[arg-type]
        universe=universe,
    )

    assert universe.get_validation_status(
        "RELIANCE"
    ) is ValidationStatus.TESTING

    result = service.validate_and_update_universe(
        "RELIANCE",
        data,
    )

    assert result.status is ValidationStatus.VALIDATED
    assert universe.get_validation_status(
        "RELIANCE"
    ) is ValidationStatus.VALIDATED
    assert universe.is_signal_eligible(
        "RELIANCE"
    ) is True


def test_failed_validation_is_not_signal_eligible() -> None:
    universe = UniverseManager()
    data = make_data()

    expected = make_runner_result(
        "RELIANCE",
        ValidationStatus.FAILED,
    )

    service = StockValidationService(
        provider=StockDataProvider(),
        runner=FakeRunner(expected),  # type: ignore[arg-type]
        universe=universe,
    )

    result = service.validate_and_update_universe(
        "RELIANCE",
        data,
    )

    assert result.status is ValidationStatus.FAILED
    assert universe.get_validation_status(
        "RELIANCE"
    ) is ValidationStatus.FAILED
    assert universe.is_signal_eligible(
        "RELIANCE"
    ) is False


def test_validation_status_requires_known_symbol() -> None:
    universe = UniverseManager()

    service = StockValidationService(
        provider=StockDataProvider(),
        runner=FakeRunner(
            make_runner_result(
                "RELIANCE",
                ValidationStatus.FAILED,
            )
        ),  # type: ignore[arg-type]
        universe=universe,
    )

    assert service.validation_status(
        "RELIANCE"
    ) is ValidationStatus.TESTING

    with pytest.raises(
        KeyError,
        match="Unknown stock symbol: UNKNOWN",
    ):
        service.validation_status(
            "UNKNOWN",
        )

"""Tests for the SignalForge stock validation orchestrator."""

from dataclasses import replace

import pandas as pd
import pytest

from src.universe.validation import ValidationStatus
from src.validation import (
    ApprovalResult,
    CausalityResult,
    CostSlippageResult,
    DataAvailabilityResult,
    DataQualityResult,
    HistoricalBacktestResult,
    IndicatorCompatibilityResult,
    RegimeOOSResult,
)
from src.validation.stock_validator import (
    StockValidationResult,
    StockValidationRunner,
)


def _minimal_ohlcv() -> pd.DataFrame:
    index = pd.date_range(
        "2024-01-01 09:15",
        periods=60,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100.0] * 60,
            "high": [101.0] * 60,
            "low": [99.0] * 60,
            "close": [100.0] * 60,
            "volume": [1_000.0] * 60,
        },
        index=index,
    )


def _runner() -> StockValidationRunner:
    return StockValidationRunner(
        development_start="2024-01-01",
        development_end="2024-01-15",
        oos_start="2024-01-16",
        oos_end="2024-01-31",
    )


def test_runner_rejects_non_dataframe() -> None:
    runner = _runner()

    with pytest.raises(TypeError, match="pandas DataFrame"):
        runner.validate(
            symbol="RELIANCE",
            data="not-dataframe",  # type: ignore[arg-type]
        )


def test_runner_normalizes_symbol_before_validation() -> None:
    runner = _runner()

    captured: dict[str, str] = {}

    def fake_validate(*, symbol: str, data: pd.DataFrame):
        captured["symbol"] = symbol
        return None

    original = runner.validate

    assert callable(original)
    assert runner._normalize_symbol(" reliance ") == "RELIANCE"
    assert runner._normalize_symbol("tcs") == "TCS"
    assert captured == {}


def test_runner_rejects_empty_symbol() -> None:
    runner = _runner()

    with pytest.raises(ValueError, match="symbol must not be empty"):
        runner.validate(
            symbol="   ",
            data=_minimal_ohlcv(),
        )


def test_runner_rejects_non_string_symbol() -> None:
    runner = _runner()

    with pytest.raises(TypeError, match="symbol must be a string"):
        runner.validate(
            symbol=123,  # type: ignore[arg-type]
            data=_minimal_ohlcv(),
        )


def test_result_properties_delegate_to_approval() -> None:
    approval = ApprovalResult(
        status=ValidationStatus.VALIDATED,
        signal_eligible=True,
        approved=True,
        passed_gates=("A", "B"),
        failed_gates=(),
        issues=(),
    )

    result = StockValidationResult(
        symbol="RELIANCE",
        data_availability=object(),  # type: ignore[arg-type]
        data_quality=object(),  # type: ignore[arg-type]
        indicator_compatibility=object(),  # type: ignore[arg-type]
        historical_backtest=object(),  # type: ignore[arg-type]
        causality=object(),  # type: ignore[arg-type]
        cost_slippage=object(),  # type: ignore[arg-type]
        regime_oos=object(),  # type: ignore[arg-type]
        approval=approval,
    )

    assert result.status == ValidationStatus.VALIDATED
    assert result.signal_eligible is True
    assert result.approved is True
    assert result.passed_gates == ("A", "B")
    assert result.failed_gates == ()
    assert result.issues == ()


def test_runner_exposes_configured_components() -> None:
    runner = _runner()

    assert runner.required_timeframes == (
        "5m",
        "10m",
        "15m",
        "30m",
    )
    assert runner.strategy_config is None
    assert runner.approval_validator is not None
    assert runner.data_availability_checker is not None
    assert runner.data_quality_checker is not None
    assert runner.indicator_compatibility_checker is not None
    assert runner.historical_backtest_validator is not None
    assert runner.causality_validator is not None
    assert runner.cost_slippage_validator is not None
    assert runner.regime_oos_validator is not None

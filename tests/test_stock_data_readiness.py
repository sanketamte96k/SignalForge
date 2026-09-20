"""Tests for stock historical-data readiness."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.stock_provider import StockDataProvider
from src.validation.stock_data_readiness import (
    REQUIRED_END,
    REQUIRED_START,
    StockDataReadinessChecker,
)


def _build_data(
    start: str,
    end: str,
) -> pd.DataFrame:
    index = pd.date_range(
        start=start,
        end=end,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
        },
        index=index,
    )


def test_missing_dataset_is_not_ready(tmp_path: Path) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    result = checker.check("RELIANCE")

    assert result.symbol == "RELIANCE"
    assert result.available is False
    assert result.ready is False
    assert result.missing is True
    assert result.total_rows == 0
    assert result.first_timestamp is None
    assert result.last_timestamp is None
    assert result.covers_required_period is False
    assert result.issues


def test_complete_dataset_is_ready(tmp_path: Path) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    data = _build_data(
        "2015-01-01",
        "2024-03-26 15:29:00",
    )

    provider.save(
        "RELIANCE",
        data,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    result = checker.check("RELIANCE")

    assert result.available is True
    assert result.ready is True
    assert result.missing is False
    assert result.total_rows == len(data)
    assert result.first_timestamp == pd.Timestamp(
        "2015-01-01"
    )
    assert result.last_timestamp == pd.Timestamp(
        "2024-03-26 15:29:00"
    )
    assert result.covers_required_period is True
    assert result.issues == ()


def test_dataset_starting_too_late_is_not_ready(
    tmp_path: Path,
) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    data = _build_data(
        "2018-01-01",
        "2024-03-26 15:29:00",
    )

    provider.save(
        "RELIANCE",
        data,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    result = checker.check("RELIANCE")

    assert result.available is True
    assert result.ready is False
    assert result.covers_required_period is False
    assert any(
        "starts after" in issue
        for issue in result.issues
    )


def test_dataset_ending_too_early_is_not_ready(
    tmp_path: Path,
) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    data = _build_data(
        "2015-01-01",
        "2023-12-29 15:29:00",
    )

    provider.save(
        "RELIANCE",
        data,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    result = checker.check("RELIANCE")

    assert result.available is True
    assert result.ready is False
    assert result.covers_required_period is False
    assert any(
        "ends before" in issue
        for issue in result.issues
    )


def test_symbol_is_normalized(tmp_path: Path) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    result = checker.check("  reliance  ")

    assert result.symbol == "RELIANCE"


def test_invalid_symbol_type_is_rejected(
    tmp_path: Path,
) -> None:
    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    checker = StockDataReadinessChecker(
        provider=provider,
    )

    with pytest.raises(TypeError):
        checker.check(123)  # type: ignore[arg-type]


def test_required_validation_window_is_frozen() -> None:
    assert REQUIRED_START == pd.Timestamp(
        "2015-01-01"
    )
    assert REQUIRED_END == pd.Timestamp(
        "2024-03-26 15:29:00"
    )

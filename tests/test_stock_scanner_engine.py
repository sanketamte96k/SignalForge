"""Tests for the SignalForge validated stock scanner engine."""

import pandas as pd
import pytest

from src.scanner.engine import StockScannerEngine
from src.universe.manager import UniverseManager
from src.universe.models import Instrument
from src.universe.validation import ValidationStatus


def make_data() -> pd.DataFrame:
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=20,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": range(100, 120),
            "high": range(101, 121),
            "low": range(99, 119),
            "close": [100.5 + i for i in range(20)],
            "volume": [1000 + (i * 10) for i in range(20)],
        },
        index=index,
    )


def make_manager() -> UniverseManager:
    instruments = (
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
        ),
        Instrument(
            symbol="TCS",
            name="Tata Consultancy Services Limited",
        ),
        Instrument(
            symbol="INFY",
            name="Infosys Limited",
        ),
    )

    return UniverseManager(
        instruments=instruments,
    )


def test_testing_stock_is_blocked() -> None:
    manager = make_manager()

    engine = StockScannerEngine(manager)

    result = engine.scan_symbol(
        "RELIANCE",
        make_data(),
    )

    assert result.signal == "NO_TRADE"
    assert result.position is None
    assert result.signal_eligible is False
    assert result.timestamp is None
    assert result.price is None
    assert result.signal_result is None
    assert "not VALIDATED" in result.reason


def test_failed_stock_is_blocked() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "TCS",
        ValidationStatus.FAILED,
    )

    engine = StockScannerEngine(manager)

    result = engine.scan_symbol(
        "TCS",
        make_data(),
    )

    assert result.signal == "NO_TRADE"
    assert result.position is None
    assert result.signal_eligible is False
    assert result.signal_result is None


def test_validated_stock_is_signal_eligible() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "INFY",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    result = engine.scan_symbol(
        "INFY",
        make_data(),
    )

    assert result.signal_eligible is True
    assert result.symbol == "INFY"
    assert result.name == "Infosys Limited"
    assert result.exchange == "NSE"


def test_validated_stock_without_data_returns_no_trade() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    result = engine.scan_symbol(
        "RELIANCE",
        None,
    )

    assert result.signal == "NO_TRADE"
    assert result.position is None
    assert result.signal_eligible is True
    assert result.timestamp is None
    assert result.price is None
    assert result.signal_result is None
    assert "unavailable" in result.reason


def test_validated_stock_with_empty_data_returns_no_trade() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    result = engine.scan_symbol(
        "RELIANCE",
        pd.DataFrame(),
    )

    assert result.signal == "NO_TRADE"
    assert result.position is None
    assert result.signal_eligible is True
    assert result.signal_result is None
    assert "empty" in result.reason


def test_non_dataframe_data_is_rejected() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    with pytest.raises(
        TypeError,
        match="stock market data must be a pandas DataFrame",
    ):
        engine.scan_symbol(
            "RELIANCE",
            "invalid",  # type: ignore[arg-type]
        )


def test_scan_preserves_universe_order() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "INFY",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    results = engine.scan(
        {
            "INFY": make_data(),
        }
    )

    assert [result.symbol for result in results] == [
        "RELIANCE",
        "TCS",
        "INFY",
    ]


def test_scan_blocks_missing_symbols_without_data() -> None:
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    engine = StockScannerEngine(manager)

    results = engine.scan({})

    result = results[0]

    assert result.symbol == "RELIANCE"
    assert result.signal_eligible is True
    assert result.signal == "NO_TRADE"
    assert result.price is None
    assert result.timestamp is None

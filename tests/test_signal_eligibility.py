import pytest

from src.universe.manager import UniverseManager
from src.universe.models import Instrument
from src.universe.validation import ValidationStatus


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


def test_testing_stock_is_not_signal_eligible():
    manager = make_manager()

    assert (
        manager.get_validation_status("RELIANCE")
        == ValidationStatus.TESTING
    )

    assert manager.is_signal_eligible("RELIANCE") is False


def test_failed_stock_is_not_signal_eligible():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.FAILED,
    )

    assert manager.is_signal_eligible("RELIANCE") is False


def test_validated_stock_is_signal_eligible():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.is_signal_eligible("RELIANCE") is True


def test_signal_eligibility_is_case_insensitive():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.is_signal_eligible(" reliance ") is True


def test_signal_eligible_symbols_returns_only_validated_stocks():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    manager.set_validation_status(
        "INFY",
        ValidationStatus.VALIDATED,
    )

    assert manager.signal_eligible_symbols() == (
        "RELIANCE",
        "INFY",
    )


def test_signal_eligible_symbols_preserves_universe_order():
    manager = make_manager()

    manager.set_validation_status(
        "INFY",
        ValidationStatus.VALIDATED,
    )

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.signal_eligible_symbols() == (
        "RELIANCE",
        "INFY",
    )


def test_signal_eligible_instruments_returns_only_validated():
    manager = make_manager()

    manager.set_validation_status(
        "TCS",
        ValidationStatus.VALIDATED,
    )

    eligible = manager.signal_eligible_instruments()

    assert len(eligible) == 1
    assert eligible[0].symbol == "TCS"
    assert (
        eligible[0].validation_status
        == ValidationStatus.VALIDATED
    )


def test_changing_validated_stock_back_to_testing_blocks_signals():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.is_signal_eligible("RELIANCE") is True

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.TESTING,
    )

    assert manager.is_signal_eligible("RELIANCE") is False
    assert manager.signal_eligible_symbols() == ()


def test_changing_validated_stock_to_failed_blocks_signals():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.FAILED,
    )

    assert manager.is_signal_eligible("RELIANCE") is False
    assert manager.signal_eligible_symbols() == ()


def test_unknown_stock_is_rejected_by_signal_eligibility():
    manager = make_manager()

    with pytest.raises(
        KeyError,
        match="instrument not found in universe: UNKNOWN",
    ):
        manager.is_signal_eligible("UNKNOWN")


def test_initial_universe_has_no_signal_eligible_stocks():
    manager = make_manager()

    assert manager.signal_eligible_symbols() == ()
    assert manager.signal_eligible_instruments() == ()

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

    return UniverseManager(instruments=instruments)


def test_instruments_default_to_testing():
    manager = make_manager()

    assert (
        manager.get_validation_status("RELIANCE")
        == ValidationStatus.TESTING
    )

    assert (
        manager.get_validation_status("TCS")
        == ValidationStatus.TESTING
    )


def test_get_validation_status_is_case_insensitive():
    manager = make_manager()

    assert (
        manager.get_validation_status(" reliance ")
        == ValidationStatus.TESTING
    )


def test_set_validation_status_to_validated():
    manager = make_manager()

    updated = manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert updated.validation_status == ValidationStatus.VALIDATED
    assert (
        manager.get_validation_status("RELIANCE")
        == ValidationStatus.VALIDATED
    )
    assert manager.is_validated("RELIANCE") is True


def test_set_validation_status_to_failed():
    manager = make_manager()

    updated = manager.set_validation_status(
        "TCS",
        ValidationStatus.FAILED,
    )

    assert updated.validation_status == ValidationStatus.FAILED
    assert (
        manager.get_validation_status("TCS")
        == ValidationStatus.FAILED
    )
    assert manager.is_validated("TCS") is False


def test_set_validation_status_accepts_string_value():
    manager = make_manager()

    updated = manager.set_validation_status(
        "INFY",
        "VALIDATED",
    )

    assert updated.validation_status == ValidationStatus.VALIDATED
    assert manager.is_validated("INFY") is True


def test_set_validation_status_can_return_to_testing():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.TESTING,
    )

    assert (
        manager.get_validation_status("RELIANCE")
        == ValidationStatus.TESTING
    )
    assert manager.is_validated("RELIANCE") is False


def test_invalid_status_is_rejected():
    manager = make_manager()

    with pytest.raises(
        ValueError,
        match="status must be a valid ValidationStatus",
    ):
        manager.set_validation_status(
            "RELIANCE",
            "INVALID",
        )


def test_unknown_symbol_is_rejected_when_reading_status():
    manager = make_manager()

    with pytest.raises(
        KeyError,
        match="instrument not found in universe: UNKNOWN",
    ):
        manager.get_validation_status("UNKNOWN")


def test_unknown_symbol_is_rejected_when_setting_status():
    manager = make_manager()

    with pytest.raises(
        KeyError,
        match="instrument not found in universe: UNKNOWN",
    ):
        manager.set_validation_status(
            "UNKNOWN",
            ValidationStatus.VALIDATED,
        )


def test_validation_status_change_preserves_instrument_metadata():
    manager = make_manager()

    before = manager.get_instrument("RELIANCE")

    after = manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert after.symbol == before.symbol
    assert after.name == before.name
    assert after.exchange == before.exchange
    assert after.instrument_type == before.instrument_type
    assert after.validation_status == ValidationStatus.VALIDATED


def test_validation_status_change_does_not_change_other_instruments():
    manager = make_manager()

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert (
        manager.get_validation_status("TCS")
        == ValidationStatus.TESTING
    )

    assert (
        manager.get_validation_status("INFY")
        == ValidationStatus.TESTING
    )


def test_is_validated_only_returns_true_for_validated_status():
    manager = make_manager()

    assert manager.is_validated("RELIANCE") is False

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.FAILED,
    )

    assert manager.is_validated("RELIANCE") is False

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.is_validated("RELIANCE") is True


def test_validation_status_change_preserves_sector_membership():
    manager = make_manager()

    manager.create_sector(
        "Technology",
        "Technology stocks",
    )

    manager.add_stock_to_sector(
        "Technology",
        "TCS",
    )

    manager.set_validation_status(
        "TCS",
        ValidationStatus.VALIDATED,
    )

    assert manager.sector_symbols("Technology") == ("TCS",)


def test_validation_status_change_preserves_watchlist_membership():
    manager = make_manager()

    manager.create_watchlist(
        "My Stocks",
        "Personal watchlist",
    )

    manager.add_stock_to_watchlist(
        "My Stocks",
        "RELIANCE",
    )

    manager.set_validation_status(
        "RELIANCE",
        ValidationStatus.VALIDATED,
    )

    assert manager.watchlist_symbols("My Stocks") == ("RELIANCE",)

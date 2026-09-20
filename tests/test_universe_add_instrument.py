from src.universe.manager import UniverseManager
from src.universe.validation import ValidationStatus


TEST_SYMBOL = "TESTSTOCK"
TEST_NAME = "Test Stock Industries"


def test_add_instrument_adds_new_stock_as_testing() -> None:
    manager = UniverseManager()

    before_count = len(manager)

    instrument = manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    assert len(manager) == before_count + 1
    assert instrument.symbol == TEST_SYMBOL
    assert instrument.name == TEST_NAME
    assert instrument.exchange == "NSE"
    assert instrument.instrument_type == "EQUITY"
    assert instrument.validation_status == ValidationStatus.TESTING


def test_added_instrument_is_not_signal_eligible() -> None:
    manager = UniverseManager()

    manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    assert manager.contains(TEST_SYMBOL)
    assert manager.get_validation_status(TEST_SYMBOL) == ValidationStatus.TESTING
    assert manager.is_validated(TEST_SYMBOL) is False
    assert manager.is_signal_eligible(TEST_SYMBOL) is False
    assert TEST_SYMBOL not in manager.signal_eligible_symbols()


def test_add_instrument_normalizes_symbol_and_name() -> None:
    manager = UniverseManager()

    instrument = manager.add_instrument(
        symbol="  teststock  ",
        name="  Test   Stock   Industries  ",
    )

    assert instrument.symbol == TEST_SYMBOL
    assert instrument.name == TEST_NAME


def test_add_instrument_is_searchable() -> None:
    manager = UniverseManager()

    manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    symbol_matches = manager.search_instruments("teststock")
    name_matches = manager.search_instruments("industries")

    assert any(
        instrument.symbol == TEST_SYMBOL
        for instrument in symbol_matches
    )
    assert any(
        instrument.symbol == TEST_SYMBOL
        for instrument in name_matches
    )


def test_duplicate_instrument_is_rejected() -> None:
    manager = UniverseManager()

    manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    try:
        manager.add_instrument(
            symbol=TEST_SYMBOL.lower(),
            name="Another Test Stock",
        )
    except ValueError as exc:
        assert str(exc) == (
            f"instrument already exists: {TEST_SYMBOL}"
        )
    else:
        raise AssertionError("Expected duplicate instrument to fail")


def test_added_instrument_can_be_validated_later() -> None:
    manager = UniverseManager()

    manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    updated = manager.set_validation_status(
        TEST_SYMBOL,
        ValidationStatus.VALIDATED,
    )

    assert updated.validation_status == ValidationStatus.VALIDATED
    assert manager.is_signal_eligible(TEST_SYMBOL) is True


def test_added_instrument_can_be_marked_failed() -> None:
    manager = UniverseManager()

    manager.add_instrument(
        symbol=TEST_SYMBOL,
        name=TEST_NAME,
    )

    updated = manager.set_validation_status(
        TEST_SYMBOL,
        ValidationStatus.FAILED,
    )

    assert updated.validation_status == ValidationStatus.FAILED
    assert manager.is_signal_eligible(TEST_SYMBOL) is False

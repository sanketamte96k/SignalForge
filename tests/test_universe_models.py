import pytest

from src.universe.models import Instrument
from src.universe.validation import ValidationStatus


def test_instrument_normalizes_fields():
    instrument = Instrument(
        symbol=" reliance ",
        name=" Reliance Industries Limited ",
        exchange=" nse ",
        instrument_type=" equity ",
    )

    assert instrument.symbol == "RELIANCE"
    assert instrument.name == "Reliance Industries Limited"
    assert instrument.exchange == "NSE"
    assert instrument.instrument_type == "EQUITY"


def test_instrument_defaults_to_testing_status():
    instrument = Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
    )

    assert instrument.validation_status == ValidationStatus.TESTING


def test_instrument_accepts_validated_status():
    instrument = Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        validation_status=ValidationStatus.VALIDATED,
    )

    assert instrument.validation_status == ValidationStatus.VALIDATED


def test_instrument_accepts_failed_status():
    instrument = Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        validation_status=ValidationStatus.FAILED,
    )

    assert instrument.validation_status == ValidationStatus.FAILED


def test_instrument_accepts_status_value():
    instrument = Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        validation_status="VALIDATED",
    )

    assert instrument.validation_status == ValidationStatus.VALIDATED


def test_instrument_rejects_invalid_status():
    with pytest.raises(
        ValueError,
        match="validation_status must be a valid ValidationStatus",
    ):
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
            validation_status="UNKNOWN",
        )


def test_instrument_rejects_empty_symbol():
    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        Instrument(
            symbol="   ",
            name="Reliance Industries Limited",
        )


def test_instrument_rejects_empty_name():
    with pytest.raises(
        ValueError,
        match="name must not be empty",
    ):
        Instrument(
            symbol="RELIANCE",
            name="   ",
        )


def test_instrument_rejects_empty_exchange():
    with pytest.raises(
        ValueError,
        match="exchange must not be empty",
    ):
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
            exchange="   ",
        )


def test_instrument_rejects_empty_instrument_type():
    with pytest.raises(
        ValueError,
        match="instrument_type must not be empty",
    ):
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
            instrument_type="   ",
        )

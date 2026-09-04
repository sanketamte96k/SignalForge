import pytest

from src.universe.sector import Sector


def test_sector_normalizes_name_and_description():
    sector = Sector(
        name="  Technology  ",
        description="  Technology stocks  ",
    )

    assert sector.name == "Technology"
    assert sector.description == "Technology stocks"


def test_sector_is_immutable():
    sector = Sector(name="Technology")

    with pytest.raises(AttributeError):
        sector.name = "Banking"


def test_sector_rejects_empty_name():
    with pytest.raises(
        ValueError,
        match="sector name must not be empty",
    ):
        Sector(name="   ")


def test_sector_normalizes_symbols():
    sector = Sector(
        name="Technology",
        symbols=(" tcs ", "infy"),
    )

    assert sector.symbols == ("TCS", "INFY")


def test_sector_rejects_empty_symbol():
    with pytest.raises(
        ValueError,
        match="sector symbol must not be empty",
    ):
        Sector(
            name="Technology",
            symbols=("TCS", "   "),
        )


def test_sector_rejects_duplicate_symbols():
    with pytest.raises(
        ValueError,
        match="sector contains duplicate symbol",
    ):
        Sector(
            name="Technology",
            symbols=("TCS", "tcs"),
        )


def test_sector_preserves_symbol_order():
    sector = Sector(
        name="Technology",
        symbols=("TCS", "INFY", "HCLTECH"),
    )

    assert sector.symbols == (
        "TCS",
        "INFY",
        "HCLTECH",
    )

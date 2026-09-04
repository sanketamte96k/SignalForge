import pytest

from src.universe.watchlist import Watchlist


def test_watchlist_normalizes_name_description_and_symbols():
    watchlist = Watchlist(
        name="  Momentum Stocks  ",
        description="  Stocks showing momentum  ",
        symbols=(" tcs ", "infy"),
    )

    assert watchlist.name == "Momentum Stocks"
    assert watchlist.description == "Stocks showing momentum"
    assert watchlist.symbols == ("TCS", "INFY")


def test_watchlist_is_immutable():
    watchlist = Watchlist(name="Momentum")

    with pytest.raises(AttributeError):
        watchlist.name = "Banking"


def test_watchlist_rejects_empty_name():
    with pytest.raises(
        ValueError,
        match="watchlist name must not be empty",
    ):
        Watchlist(name="   ")


def test_watchlist_rejects_empty_symbol():
    with pytest.raises(
        ValueError,
        match="watchlist symbol must not be empty",
    ):
        Watchlist(
            name="Momentum",
            symbols=("TCS", "   "),
        )


def test_watchlist_rejects_duplicate_symbols():
    with pytest.raises(
        ValueError,
        match="watchlist contains duplicate symbol",
    ):
        Watchlist(
            name="Momentum",
            symbols=("TCS", "tcs"),
        )


def test_watchlist_preserves_symbol_order():
    watchlist = Watchlist(
        name="Momentum",
        symbols=("TCS", "INFY", "HCLTECH"),
    )

    assert watchlist.symbols == (
        "TCS",
        "INFY",
        "HCLTECH",
    )

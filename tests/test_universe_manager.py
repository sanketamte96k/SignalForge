import pytest

from src.universe.manager import UniverseManager
from src.universe.models import Instrument
from src.universe.sector import Sector
from src.universe.watchlist import Watchlist


def test_manager_loads_nifty50_by_default():
    manager = UniverseManager()
    assert len(manager) == 50
    assert len(manager.symbols()) == 50


def test_manager_returns_instrument_case_insensitively():
    manager = UniverseManager()
    instrument = manager.get_instrument("reliance")
    assert instrument.symbol == "RELIANCE"
    assert instrument.name == "Reliance Industries Limited"


def test_manager_contains_symbol_case_insensitively():
    manager = UniverseManager()
    assert manager.contains("RELIANCE")
    assert manager.contains("reliance")
    assert not manager.contains("NOT_A_REAL_SYMBOL")


def test_manager_rejects_unknown_symbol():
    manager = UniverseManager()
    with pytest.raises(KeyError, match="instrument not found in universe"):
        manager.get_instrument("NOT_A_REAL_SYMBOL")


def test_manager_rejects_empty_symbol():
    manager = UniverseManager()
    with pytest.raises(ValueError, match="symbol must not be empty"):
        manager.get_instrument("   ")


def test_manager_rejects_empty_universe():
    with pytest.raises(
        ValueError,
        match="universe must contain at least one instrument",
    ):
        UniverseManager(instruments=())


def test_manager_rejects_duplicate_symbols():
    instruments = (
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
        ),
        Instrument(
            symbol="RELIANCE",
            name="Duplicate Reliance",
        ),
    )

    with pytest.raises(
        ValueError,
        match="universe contains duplicate symbols",
    ):
        UniverseManager(instruments=instruments)


def test_manager_preserves_instrument_order():
    instruments = (
        Instrument(
            symbol="TCS",
            name="Tata Consultancy Services Limited",
        ),
        Instrument(
            symbol="INFY",
            name="Infosys Limited",
        ),
        Instrument(
            symbol="RELIANCE",
            name="Reliance Industries Limited",
        ),
    )

    manager = UniverseManager(instruments=instruments)

    assert manager.symbols() == (
        "TCS",
        "INFY",
        "RELIANCE",
    )


def test_manager_returns_all_instruments():
    instruments = (
        Instrument(
            symbol="TCS",
            name="Tata Consultancy Services Limited",
        ),
        Instrument(
            symbol="INFY",
            name="Infosys Limited",
        ),
    )

    manager = UniverseManager(instruments=instruments)

    assert manager.all_instruments() == instruments


def test_manager_searches_by_exact_symbol():
    manager = UniverseManager()

    results = manager.search_instruments("TCS")

    assert tuple(instrument.symbol for instrument in results) == ("TCS",)


def test_manager_searches_by_partial_symbol():
    manager = UniverseManager()

    results = manager.search_instruments("TATA")

    symbols = tuple(instrument.symbol for instrument in results)

    assert "TATACONSUM" in symbols
    assert "TATASTEEL" in symbols
    assert "TCS" in symbols
    assert "TMPV" in symbols


def test_manager_searches_by_company_name():
    manager = UniverseManager()

    results = manager.search_instruments("Reliance Industries")

    assert tuple(instrument.symbol for instrument in results) == (
        "RELIANCE",
    )


def test_manager_search_is_case_insensitive():
    manager = UniverseManager()

    upper_results = manager.search_instruments("RELIANCE")
    lower_results = manager.search_instruments("reliance")

    assert upper_results == lower_results


def test_manager_search_ignores_outer_whitespace():
    manager = UniverseManager()

    results = manager.search_instruments("  TCS  ")

    assert tuple(instrument.symbol for instrument in results) == ("TCS",)


def test_manager_search_normalizes_repeated_spaces():
    manager = UniverseManager()

    results = manager.search_instruments("  Reliance   Industries  ")

    assert tuple(instrument.symbol for instrument in results) == (
        "RELIANCE",
    )


def test_manager_search_returns_results_in_universe_order():
    instruments = (
        Instrument(
            symbol="TCS",
            name="Tata Consultancy Services Limited",
        ),
        Instrument(
            symbol="TATACONSUM",
            name="Tata Consumer Products Limited",
        ),
        Instrument(
            symbol="INFY",
            name="Infosys Limited",
        ),
    )

    manager = UniverseManager(instruments=instruments)

    results = manager.search_instruments("tata")

    assert tuple(instrument.symbol for instrument in results) == (
        "TCS",
        "TATACONSUM",
    )


def test_manager_search_returns_empty_tuple_when_no_match():
    manager = UniverseManager()

    results = manager.search_instruments("THIS_WILL_NOT_MATCH")

    assert results == ()


def test_manager_rejects_empty_search_query():
    manager = UniverseManager()

    with pytest.raises(
        ValueError,
        match="search query must not be empty",
    ):
        manager.search_instruments("   ")


def test_manager_starts_with_no_custom_sectors():
    manager = UniverseManager()
    assert manager.all_sectors() == ()


def test_manager_creates_sector():
    manager = UniverseManager()

    sector = manager.create_sector(
        name="Technology",
        description="Technology stocks",
    )

    assert sector.name == "Technology"
    assert sector.description == "Technology stocks"
    assert sector.symbols == ()
    assert manager.all_sectors() == (sector,)


def test_manager_gets_sector_case_insensitively():
    manager = UniverseManager()

    created = manager.create_sector("Technology")

    assert manager.get_sector("technology") == created
    assert manager.get_sector(" TECHNOLOGY ") == created


def test_manager_contains_sector_case_insensitively():
    manager = UniverseManager()

    manager.create_sector("Technology")

    assert manager.contains_sector("technology")
    assert manager.contains_sector(" TECHNOLOGY ")
    assert not manager.contains_sector("Banking")


def test_manager_rejects_duplicate_sector_names():
    manager = UniverseManager()

    manager.create_sector("Technology")

    with pytest.raises(
        ValueError,
        match="sector already exists",
    ):
        manager.create_sector("technology")


def test_manager_rejects_empty_sector_name():
    manager = UniverseManager()

    with pytest.raises(
        ValueError,
        match="sector name must not be empty",
    ):
        manager.create_sector("   ")


def test_manager_rejects_unknown_sector():
    manager = UniverseManager()

    with pytest.raises(
        KeyError,
        match="sector not found",
    ):
        manager.get_sector("Technology")


def test_manager_rejects_empty_sector_lookup():
    manager = UniverseManager()

    with pytest.raises(
        ValueError,
        match="sector name must not be empty",
    ):
        manager.get_sector("   ")


def test_manager_accepts_initial_sectors():
    sectors = (
        Sector(name="Technology"),
        Sector(name="Banking"),
    )

    manager = UniverseManager(sectors=sectors)

    assert manager.all_sectors() == sectors


def test_manager_rejects_initial_sector_with_unknown_symbol():
    sectors = (
        Sector(
            name="Technology",
            symbols=("NOT_A_REAL_SYMBOL",),
        ),
    )

    with pytest.raises(
        ValueError,
        match="sector contains unknown instrument",
    ):
        UniverseManager(sectors=sectors)


def test_manager_adds_stock_to_sector():
    manager = UniverseManager()

    manager.create_sector("Technology")

    sector = manager.add_stock_to_sector(
        "Technology",
        "TCS",
    )

    assert sector.symbols == ("TCS",)
    assert manager.sector_symbols("Technology") == ("TCS",)


def test_manager_adds_stock_case_insensitively():
    manager = UniverseManager()

    manager.create_sector("Technology")

    sector = manager.add_stock_to_sector(
        " technology ",
        " tcs ",
    )

    assert sector.name == "Technology"
    assert sector.symbols == ("TCS",)


def test_manager_preserves_sector_stock_order():
    manager = UniverseManager()

    manager.create_sector("Technology")

    manager.add_stock_to_sector("Technology", "TCS")
    manager.add_stock_to_sector("Technology", "INFY")
    manager.add_stock_to_sector("Technology", "HCLTECH")

    assert manager.sector_symbols("Technology") == (
        "TCS",
        "INFY",
        "HCLTECH",
    )


def test_manager_rejects_unknown_stock():
    manager = UniverseManager()

    manager.create_sector("Technology")

    with pytest.raises(
        KeyError,
        match="instrument not found in universe",
    ):
        manager.add_stock_to_sector(
            "Technology",
            "NOT_A_REAL_SYMBOL",
        )


def test_manager_rejects_empty_stock_symbol():
    manager = UniverseManager()

    manager.create_sector("Technology")

    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        manager.add_stock_to_sector(
            "Technology",
            "   ",
        )


def test_manager_rejects_duplicate_stock_in_sector():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.add_stock_to_sector("Technology", "TCS")

    with pytest.raises(
        ValueError,
        match="stock already exists in sector",
    ):
        manager.add_stock_to_sector("Technology", "tcs")


def test_manager_allows_stock_in_multiple_sectors():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.create_sector("Large Cap")

    manager.add_stock_to_sector("Technology", "TCS")
    manager.add_stock_to_sector("Large Cap", "TCS")

    assert manager.sector_symbols("Technology") == ("TCS",)
    assert manager.sector_symbols("Large Cap") == ("TCS",)


def test_manager_does_not_modify_other_sectors():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.create_sector("Banking")

    manager.add_stock_to_sector("Technology", "TCS")

    assert manager.sector_symbols("Technology") == ("TCS",)
    assert manager.sector_symbols("Banking") == ()


def test_manager_sector_symbols_raises_for_unknown_sector():
    manager = UniverseManager()

    with pytest.raises(
        KeyError,
        match="sector not found",
    ):
        manager.sector_symbols("Technology")


def test_manager_removes_stock_from_sector():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.add_stock_to_sector("Technology", "TCS")
    manager.add_stock_to_sector("Technology", "INFY")

    sector = manager.remove_stock_from_sector(
        "Technology",
        "TCS",
    )

    assert sector.symbols == ("INFY",)
    assert manager.sector_symbols("Technology") == ("INFY",)


def test_manager_removes_stock_from_sector_case_insensitively():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.add_stock_to_sector("Technology", "TCS")

    sector = manager.remove_stock_from_sector(
        " technology ",
        " tcs ",
    )

    assert sector.symbols == ()


def test_manager_rejects_removing_missing_stock_from_sector():
    manager = UniverseManager()

    manager.create_sector("Technology")

    with pytest.raises(
        KeyError,
        match="stock not found in sector",
    ):
        manager.remove_stock_from_sector(
            "Technology",
            "TCS",
        )


def test_manager_does_not_modify_other_sector_when_removing():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.create_sector("Banking")

    manager.add_stock_to_sector("Technology", "TCS")
    manager.add_stock_to_sector("Banking", "TCS")

    manager.remove_stock_from_sector("Technology", "TCS")

    assert manager.sector_symbols("Technology") == ()
    assert manager.sector_symbols("Banking") == ("TCS",)


def test_manager_starts_with_no_watchlists():
    manager = UniverseManager()

    assert manager.all_watchlists() == ()


def test_manager_creates_watchlist():
    manager = UniverseManager()

    watchlist = manager.create_watchlist(
        name="Momentum",
        description="Momentum candidates",
    )

    assert watchlist.name == "Momentum"
    assert watchlist.description == "Momentum candidates"
    assert watchlist.symbols == ()
    assert manager.all_watchlists() == (watchlist,)


def test_manager_gets_watchlist_case_insensitively():
    manager = UniverseManager()

    created = manager.create_watchlist("Momentum")

    assert manager.get_watchlist("momentum") == created
    assert manager.get_watchlist(" MOMENTUM ") == created


def test_manager_contains_watchlist_case_insensitively():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    assert manager.contains_watchlist("momentum")
    assert manager.contains_watchlist(" MOMENTUM ")
    assert not manager.contains_watchlist("Banking")


def test_manager_rejects_duplicate_watchlist_names():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    with pytest.raises(
        ValueError,
        match="watchlist already exists",
    ):
        manager.create_watchlist("momentum")


def test_manager_rejects_empty_watchlist_name():
    manager = UniverseManager()

    with pytest.raises(
        ValueError,
        match="watchlist name must not be empty",
    ):
        manager.create_watchlist("   ")


def test_manager_rejects_unknown_watchlist():
    manager = UniverseManager()

    with pytest.raises(
        KeyError,
        match="watchlist not found",
    ):
        manager.get_watchlist("Momentum")


def test_manager_rejects_empty_watchlist_lookup():
    manager = UniverseManager()

    with pytest.raises(
        ValueError,
        match="watchlist name must not be empty",
    ):
        manager.get_watchlist("   ")


def test_manager_accepts_initial_watchlists():
    watchlists = (
        Watchlist(name="Momentum"),
        Watchlist(name="Favourites"),
    )

    manager = UniverseManager(watchlists=watchlists)

    assert manager.all_watchlists() == watchlists


def test_manager_rejects_initial_watchlist_with_unknown_symbol():
    watchlists = (
        Watchlist(
            name="Momentum",
            symbols=("NOT_A_REAL_SYMBOL",),
        ),
    )

    with pytest.raises(
        ValueError,
        match="watchlist contains unknown instrument",
    ):
        UniverseManager(watchlists=watchlists)


def test_manager_keeps_watchlists_independent_from_sectors():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.create_watchlist("Momentum")

    manager.add_stock_to_sector("Technology", "TCS")

    assert manager.sector_symbols("Technology") == ("TCS",)
    assert manager.get_watchlist("Momentum").symbols == ()


def test_manager_allows_same_stock_in_multiple_watchlists():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")
    manager.create_watchlist("Long Term")

    first = manager.get_watchlist("Momentum")
    second = manager.get_watchlist("Long Term")

    assert first.symbols == ()
    assert second.symbols == ()


def test_manager_adds_stock_to_watchlist():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    watchlist = manager.add_stock_to_watchlist(
        "Momentum",
        "TCS",
    )

    assert watchlist.symbols == ("TCS",)
    assert manager.watchlist_symbols("Momentum") == ("TCS",)


def test_manager_adds_stock_to_watchlist_case_insensitively():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    watchlist = manager.add_stock_to_watchlist(
        " momentum ",
        " tcs ",
    )

    assert watchlist.name == "Momentum"
    assert watchlist.symbols == ("TCS",)


def test_manager_preserves_watchlist_stock_order():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    manager.add_stock_to_watchlist("Momentum", "TCS")
    manager.add_stock_to_watchlist("Momentum", "INFY")
    manager.add_stock_to_watchlist("Momentum", "HCLTECH")

    assert manager.watchlist_symbols("Momentum") == (
        "TCS",
        "INFY",
        "HCLTECH",
    )


def test_manager_rejects_unknown_stock_for_watchlist():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    with pytest.raises(
        KeyError,
        match="instrument not found in universe",
    ):
        manager.add_stock_to_watchlist(
            "Momentum",
            "NOT_A_REAL_SYMBOL",
        )


def test_manager_rejects_duplicate_stock_in_watchlist():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")
    manager.add_stock_to_watchlist("Momentum", "TCS")

    with pytest.raises(
        ValueError,
        match="stock already exists in watchlist",
    ):
        manager.add_stock_to_watchlist("Momentum", "tcs")


def test_manager_removes_stock_from_watchlist():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")
    manager.add_stock_to_watchlist("Momentum", "TCS")
    manager.add_stock_to_watchlist("Momentum", "INFY")

    watchlist = manager.remove_stock_from_watchlist(
        "Momentum",
        "TCS",
    )

    assert watchlist.symbols == ("INFY",)
    assert manager.watchlist_symbols("Momentum") == ("INFY",)


def test_manager_removes_stock_from_watchlist_case_insensitively():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")
    manager.add_stock_to_watchlist("Momentum", "TCS")

    watchlist = manager.remove_stock_from_watchlist(
        " momentum ",
        " tcs ",
    )

    assert watchlist.symbols == ()


def test_manager_rejects_removing_missing_stock_from_watchlist():
    manager = UniverseManager()

    manager.create_watchlist("Momentum")

    with pytest.raises(
        KeyError,
        match="stock not found in watchlist",
    ):
        manager.remove_stock_from_watchlist(
            "Momentum",
            "TCS",
        )


def test_manager_does_not_modify_sector_when_watchlist_changes():
    manager = UniverseManager()

    manager.create_sector("Technology")
    manager.create_watchlist("Momentum")

    manager.add_stock_to_sector("Technology", "TCS")
    manager.add_stock_to_watchlist("Momentum", "TCS")

    manager.remove_stock_from_watchlist("Momentum", "TCS")

    assert manager.sector_symbols("Technology") == ("TCS",)
    assert manager.watchlist_symbols("Momentum") == ()

from src.universe.nifty50 import load_nifty50, nifty50_symbols


def test_nifty50_contains_exactly_50_constituents():
    instruments = load_nifty50()

    assert len(instruments) == 50


def test_nifty50_symbols_are_unique():
    symbols = nifty50_symbols()

    assert len(symbols) == len(set(symbols))


def test_nifty50_constituents_are_nse_equities():
    instruments = load_nifty50()

    assert all(instrument.exchange == "NSE" for instrument in instruments)
    assert all(
        instrument.instrument_type == "EQUITY"
        for instrument in instruments
    )


def test_nifty50_symbols_are_normalized():
    symbols = nifty50_symbols()

    assert all(symbol == symbol.upper() for symbol in symbols)
    assert all(symbol.strip() == symbol for symbol in symbols)


def test_nifty50_contains_expected_core_symbols():
    symbols = set(nifty50_symbols())

    expected = {
        "HDFCBANK",
        "ICICIBANK",
        "RELIANCE",
        "INFY",
        "TCS",
        "BHARTIARTL",
        "SBIN",
        "LT",
        "ITC",
        "TMPV",
    }

    assert expected.issubset(symbols)

"""Tests for the SignalForge stock data provider."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.stock_provider import StockDataProvider


def make_valid_data() -> pd.DataFrame:
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=index,
    )


def test_default_yahoo_ticker() -> None:
    provider = StockDataProvider()

    assert provider.yahoo_ticker("RELIANCE") == "RELIANCE.NS"


def test_yahoo_ticker_normalizes_symbol() -> None:
    provider = StockDataProvider()

    assert provider.yahoo_ticker(" reliance ") == "RELIANCE.NS"


def test_yahoo_ticker_does_not_duplicate_suffix() -> None:
    provider = StockDataProvider()

    assert provider.yahoo_ticker("RELIANCE.NS") == "RELIANCE.NS"


def test_custom_suffix_is_supported() -> None:
    provider = StockDataProvider(
        exchange_suffix="NS",
    )

    assert provider.yahoo_ticker("TCS") == "TCS.NS"


def test_local_path() -> None:
    provider = StockDataProvider(
        data_directory="data/test-stocks",
    )

    assert provider.local_path("TCS") == Path(
        "data/test-stocks/TCS_1m.csv"
    )


def test_empty_symbol_is_rejected() -> None:
    provider = StockDataProvider()

    with pytest.raises(ValueError, match="symbol must not be empty"):
        provider.yahoo_ticker("   ")


def test_non_string_symbol_is_rejected() -> None:
    provider = StockDataProvider()

    with pytest.raises(TypeError, match="symbol must be a string"):
        provider.yahoo_ticker(123)  # type: ignore[arg-type]


def test_empty_suffix_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="exchange_suffix must not be empty",
    ):
        StockDataProvider(exchange_suffix="   ")


def test_non_string_suffix_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="exchange_suffix must be a string",
    ):
        StockDataProvider(
            exchange_suffix=123,  # type: ignore[arg-type]
        )


def test_download_uses_existing_downloader(monkeypatch) -> None:
    expected = make_valid_data()
    captured: dict[str, object] = {}

    def fake_download(
        *,
        ticker,
        start,
        end,
        interval,
    ):
        captured["ticker"] = ticker
        captured["start"] = start
        captured["end"] = end
        captured["interval"] = interval
        return expected

    monkeypatch.setattr(
        "src.data.stock_provider.download_market_data",
        fake_download,
    )

    provider = StockDataProvider()

    result = provider.download(
        "RELIANCE",
        start="2026-09-01",
        end="2026-09-05",
        interval="1m",
    )

    assert captured == {
        "ticker": "RELIANCE.NS",
        "start": "2026-09-01",
        "end": "2026-09-05",
        "interval": "1m",
    }

    pd.testing.assert_frame_equal(
        result,
        expected,
    )


def test_save_uses_existing_downloader_save(
    monkeypatch,
    tmp_path,
) -> None:
    expected = make_valid_data()
    captured: dict[str, object] = {}

    def fake_save(*, data, path):
        captured["data"] = data
        captured["path"] = path
        return Path(path)

    monkeypatch.setattr(
        "src.data.stock_provider.save_market_data",
        fake_save,
    )

    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    result = provider.save(
        "INFY",
        expected,
    )

    assert result == tmp_path / "INFY_1m.csv"
    assert captured["data"] is expected
    assert captured["path"] == tmp_path / "INFY_1m.csv"


def test_load_uses_existing_downloader_load(
    monkeypatch,
    tmp_path,
) -> None:
    expected = make_valid_data()
    captured: dict[str, object] = {}

    def fake_load(path):
        captured["path"] = path
        return expected

    monkeypatch.setattr(
        "src.data.stock_provider.load_market_data",
        fake_load,
    )

    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    result = provider.load("SBIN")

    assert captured["path"] == tmp_path / "SBIN_1m.csv"

    pd.testing.assert_frame_equal(
        result,
        expected,
    )


def test_download_and_save(
    monkeypatch,
    tmp_path,
) -> None:
    expected = make_valid_data()
    saved: dict[str, object] = {}

    def fake_download(*args, **kwargs):
        saved["download_args"] = args
        saved["download_kwargs"] = kwargs
        return expected

    def fake_save(*, data, path):
        saved["data"] = data
        saved["path"] = path
        return Path(path)

    monkeypatch.setattr(
        "src.data.stock_provider.download_market_data",
        fake_download,
    )
    monkeypatch.setattr(
        "src.data.stock_provider.save_market_data",
        fake_save,
    )

    provider = StockDataProvider(
        data_directory=tmp_path,
    )

    result = provider.download_and_save(
        "HDFCBANK",
        start="2026-09-01",
        end="2026-09-05",
        interval="1m",
    )

    pd.testing.assert_frame_equal(
        result,
        expected,
    )

    assert saved["download_args"] == ()

    assert saved["download_kwargs"] == {
        "ticker": "HDFCBANK.NS",
        "start": "2026-09-01",
        "end": "2026-09-05",
        "interval": "1m",
    }

    assert saved["data"] is expected
    assert saved["path"] == tmp_path / "HDFCBANK_1m.csv"

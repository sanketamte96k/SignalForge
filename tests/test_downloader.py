import pandas as pd
import pytest

from src.data.downloader import (
    SUPPORTED_INTERVALS,
    _normalize_downloaded_data,
    _validate_parameters,
    download_market_data,
    load_market_data,
    save_market_data,
)


def make_valid_data():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [
                100,
                101,
                102,
                103,
                104,
            ],
            "high": [
                101,
                102,
                103,
                104,
                105,
            ],
            "low": [
                99,
                100,
                101,
                102,
                103,
            ],
            "close": [
                100.5,
                101.5,
                102.5,
                103.5,
                104.5,
            ],
            "volume": [
                1000,
                1100,
                1200,
                1300,
                1400,
            ],
        },
        index=index,
    )


def make_yahoo_data():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=3,
        freq="min",
    )

    return pd.DataFrame(
        {
            "Open": [100, 101, 102],
            "High": [101, 102, 103],
            "Low": [99, 100, 101],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1100, 1200],
        },
        index=index,
    )


def test_supported_intervals_contains_required_values():
    assert "1m" in SUPPORTED_INTERVALS
    assert "5m" in SUPPORTED_INTERVALS
    assert "15m" in SUPPORTED_INTERVALS
    assert "1d" in SUPPORTED_INTERVALS


def test_validate_parameters_accepts_valid_input():
    _validate_parameters(
        ticker="RELIANCE.NS",
        start="2026-01-01",
        end="2026-02-01",
        interval="1m",
    )


def test_empty_ticker_is_rejected():
    with pytest.raises(ValueError):
        _validate_parameters(
            ticker="",
            interval="1m",
        )


def test_whitespace_ticker_is_rejected():
    with pytest.raises(ValueError):
        _validate_parameters(
            ticker="   ",
            interval="1m",
        )


def test_non_string_ticker_is_rejected():
    with pytest.raises(TypeError):
        _validate_parameters(
            ticker=123,
            interval="1m",
        )


def test_invalid_interval_is_rejected():
    with pytest.raises(ValueError):
        _validate_parameters(
            ticker="RELIANCE.NS",
            interval="invalid",
        )


def test_non_string_start_is_rejected():
    with pytest.raises(TypeError):
        _validate_parameters(
            ticker="RELIANCE.NS",
            start=20260101,
            interval="1m",
        )


def test_non_string_end_is_rejected():
    with pytest.raises(TypeError):
        _validate_parameters(
            ticker="RELIANCE.NS",
            end=20260201,
            interval="1m",
        )


def test_normalize_downloaded_data_returns_dataframe():
    data = make_yahoo_data()

    result = _normalize_downloaded_data(
        data
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )


def test_normalize_downloaded_data_renames_columns():
    data = make_yahoo_data()

    result = _normalize_downloaded_data(
        data
    )

    assert list(result.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_normalize_downloaded_data_preserves_index():
    data = make_yahoo_data()

    result = _normalize_downloaded_data(
        data
    )

    assert result.index.equals(
        data.index
    )


def test_normalize_downloaded_data_sorts_index():
    data = make_yahoo_data()

    data = data.iloc[::-1]

    result = _normalize_downloaded_data(
        data
    )

    assert result.index.is_monotonic_increasing


def test_normalize_empty_data_is_rejected():
    data = pd.DataFrame()

    with pytest.raises(ValueError):
        _normalize_downloaded_data(data)


def test_normalize_missing_columns_is_rejected():
    data = make_yahoo_data().drop(
        columns=["Volume"]
    )

    with pytest.raises(ValueError):
        _normalize_downloaded_data(data)


def test_normalize_invalid_input_type():
    with pytest.raises(TypeError):
        _normalize_downloaded_data(
            "invalid"
        )


def test_save_market_data(tmp_path):
    data = make_valid_data()

    path = tmp_path / "market.csv"

    result = save_market_data(
        data,
        path,
    )

    assert result == path
    assert path.exists()


def test_load_market_data(tmp_path):
    data = make_valid_data()

    path = tmp_path / "market.csv"

    save_market_data(
        data,
        path,
    )

    result = load_market_data(
        path
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert list(result.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_loaded_data_matches_saved_data(
    tmp_path,
):
    data = make_valid_data()

    path = tmp_path / "market.csv"

    save_market_data(
        data,
        path,
    )

    result = load_market_data(
        path
    )

    pd.testing.assert_frame_equal(
        result,
        data,
        check_freq=False,
    )


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        load_market_data(
            "does_not_exist.csv"
        )


def test_save_invalid_data_type(tmp_path):
    with pytest.raises(TypeError):
        save_market_data(
            "invalid",
            tmp_path / "data.csv",
        )


def test_download_market_data_uses_yfinance(
    monkeypatch,
):
    expected = make_yahoo_data()

    def fake_download(**kwargs):
        assert kwargs["tickers"] == "RELIANCE.NS"
        assert kwargs["interval"] == "1m"
        assert kwargs["auto_adjust"] is False
        assert kwargs["progress"] is False

        return expected

    monkeypatch.setattr(
        "src.data.downloader.yf.download",
        fake_download,
    )

    result = download_market_data(
        ticker="RELIANCE.NS",
        start="2026-08-31",
        end="2026-09-01",
        interval="1m",
    )

    assert list(result.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_download_empty_response_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        "src.data.downloader.yf.download",
        lambda **kwargs: pd.DataFrame(),
    )

    with pytest.raises(ValueError):
        download_market_data(
            ticker="RELIANCE.NS",
            interval="1m",
        )


def test_download_failure_is_wrapped(
    monkeypatch,
):
    def fake_download(**kwargs):
        raise Exception("network failure")

    monkeypatch.setattr(
        "src.data.downloader.yf.download",
        fake_download,
    )

    with pytest.raises(RuntimeError):
        download_market_data(
            ticker="RELIANCE.NS",
            interval="1m",
        )


def test_download_invalid_ticker_before_api_call(
    monkeypatch,
):
    called = False

    def fake_download(**kwargs):
        nonlocal called
        called = True
        return make_yahoo_data()

    monkeypatch.setattr(
        "src.data.downloader.yf.download",
        fake_download,
    )

    with pytest.raises(ValueError):
        download_market_data(
            ticker="",
            interval="1m",
        )

    assert called is False
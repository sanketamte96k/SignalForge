import pandas as pd
import pytest

from src.data.validator import validate_market_data


def create_valid_data():
    """Create valid OHLCV data for testing."""

    timestamps = pd.date_range(
        start="2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103],
            "close": [101, 102, 103, 104, 105],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=timestamps,
    )


def test_valid_market_data():
    data = create_valid_data()

    validate_market_data(data)


def test_empty_data():
    data = pd.DataFrame()

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_missing_column():
    data = create_valid_data().drop(columns=["volume"])

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_duplicate_timestamp():
    data = create_valid_data()

    data.index = [
        data.index[0],
        data.index[1],
        data.index[1],
        data.index[3],
        data.index[4],
    ]

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_unsorted_timestamps():
    data = create_valid_data()

    data = data.iloc[::-1]

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_non_numeric_column():
    data = create_valid_data()

    data["close"] = "invalid"

    with pytest.raises(TypeError):
        validate_market_data(data)


def test_missing_values():
    data = create_valid_data()

    data.loc[data.index[2], "close"] = None

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_invalid_high():
    data = create_valid_data()

    data.loc[data.index[0], "high"] = 98

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_invalid_low():
    data = create_valid_data()

    data.loc[data.index[0], "low"] = 103

    with pytest.raises(ValueError):
        validate_market_data(data)


def test_negative_volume():
    data = create_valid_data()

    data.loc[data.index[0], "volume"] = -100

    with pytest.raises(ValueError):
        validate_market_data(data)
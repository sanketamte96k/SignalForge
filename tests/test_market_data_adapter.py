import pandas as pd
import pytest

from src.market_data.adapter import (
    MarketDataValidationError,
    validate_market_data,
)


def create_valid_data():
    index = pd.to_datetime(
        [
            "2023-01-02 09:17:00",
            "2023-01-02 09:15:00",
            "2023-01-02 09:16:00",
            "2023-01-02 09:16:00",
        ]
    )

    return pd.DataFrame(
        {
            "open": [102.0, 100.0, 101.0, 101.5],
            "high": [103.0, 101.0, 102.0, 102.0],
            "low": [101.0, 99.0, 100.0, 100.5],
            "close": [102.5, 100.5, 101.5, 101.8],
            "volume": [1000, 1200, 1100, 1150],
        },
        index=index,
    )


def test_validate_market_data_sorts_and_removes_duplicates():
    data = create_valid_data()

    result = validate_market_data(data)

    assert len(result) == 3
    assert result.index.is_monotonic_increasing
    assert not result.index.duplicated().any()

    assert list(result.index) == list(
        pd.to_datetime(
            [
                "2023-01-02 09:15:00",
                "2023-01-02 09:16:00",
                "2023-01-02 09:17:00",
            ]
        )
    )


def test_validate_market_data_keeps_required_columns():
    data = create_valid_data()

    data["extra"] = 123

    result = validate_market_data(data)

    assert list(result.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_validate_market_data_rejects_empty_data():
    data = pd.DataFrame(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
        index=pd.DatetimeIndex([]),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="cannot be empty",
    ):
        validate_market_data(data)


def test_validate_market_data_rejects_missing_columns():
    index = pd.date_range(
        "2023-01-02 09:15:00",
        periods=2,
        freq="min",
    )

    data = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
        },
        index=index,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="Missing required columns",
    ):
        validate_market_data(data)


def test_validate_market_data_rejects_high_below_low():
    index = pd.date_range(
        "2023-01-02 09:15:00",
        periods=1,
        freq="min",
    )

    data = pd.DataFrame(
        {
            "open": [99.5],
            "high": [98.0],
            "low": [99.0],
            "close": [99.2],
            "volume": [1000.0],
        },
        index=index,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="high cannot be below",
    ):
        validate_market_data(data)


def test_validate_market_data_rejects_negative_volume():
    index = pd.date_range(
        "2023-01-02 09:15:00",
        periods=1,
        freq="min",
    )

    data = pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [-1.0],
        },
        index=index,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="Volume cannot be negative",
    ):
        validate_market_data(data)


def test_validate_market_data_rejects_non_numeric_values():
    index = pd.date_range(
        "2023-01-02 09:15:00",
        periods=1,
        freq="min",
    )

    data = pd.DataFrame(
        {
            "open": ["bad"],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000.0],
        },
        index=index,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="missing or non-numeric",
    ):
        validate_market_data(data)


def test_validate_market_data_returns_copy():
    data = create_valid_data()

    result = validate_market_data(data)

    assert result is not data

    result.loc[
        result.index[0],
        "close",
    ] = 9999.0

    assert data.loc[
        result.index[0],
        "close",
    ] != 9999.0
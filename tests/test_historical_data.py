from pathlib import Path

import pandas as pd
import pytest

from scripts.verify_historical_data import (
    verify_dataset,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_exists():
    assert DATA_PATH.exists()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_is_not_empty():
    data = verify_dataset(
        DATA_PATH
    )

    assert not data.empty


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_has_expected_columns():
    data = verify_dataset(
        DATA_PATH
    )

    assert list(data.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_has_no_duplicates():
    data = verify_dataset(
        DATA_PATH
    )

    assert not data.index.has_duplicates


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_is_sorted():
    data = verify_dataset(
        DATA_PATH
    )

    assert data.index.is_monotonic_increasing


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_has_expected_row_count():
    data = verify_dataset(
        DATA_PATH
    )

    assert len(data) == 1875


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_has_expected_trading_days():
    data = verify_dataset(
        DATA_PATH
    )

    trading_days = data.index.normalize().unique()

    assert len(trading_days) == 5


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_each_trading_day_has_375_candles():
    data = verify_dataset(
        DATA_PATH
    )

    daily_counts = data.groupby(
        data.index.date
    ).size()

    assert (
        daily_counts == 375
    ).all()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_market_session_starts_at_915():
    data = verify_dataset(
        DATA_PATH
    )

    first_times = (
        data.groupby(data.index.date)
        .apply(
            lambda frame: frame.index[0].time(),
            include_groups=False,
        )
    )

    assert (
        first_times.astype(str) == "09:15:00"
    ).all()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_market_session_ends_at_1529():
    data = verify_dataset(
        DATA_PATH
    )

    last_times = (
        data.groupby(data.index.date)
        .apply(
            lambda frame: frame.index[-1].time(),
            include_groups=False,
        )
    )

    assert (
        last_times.astype(str) == "15:29:00"
    ).all()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_ohlcv_values_are_numeric():
    data = verify_dataset(
        DATA_PATH
    )

    assert all(
        pd.api.types.is_numeric_dtype(
            data[column]
        )
        for column in [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_historical_dataset_contains_no_missing_values():
    data = verify_dataset(
        DATA_PATH
    )

    assert not data.isna().any().any()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_high_is_not_below_low():
    data = verify_dataset(
        DATA_PATH
    )

    assert (
        data["high"] >= data["low"]
    ).all()


@pytest.mark.skipif(
    not DATA_PATH.exists(),
    reason="Real historical dataset is not available.",
)
def test_volume_is_non_negative():
    data = verify_dataset(
        DATA_PATH
    )

    assert (
        data["volume"] >= 0
    ).all()
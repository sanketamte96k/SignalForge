import pandas as pd
import pytest

from src.data.resampler import (
    build_all_timeframes,
    resample_ohlcv,
)


def create_test_data():
    """Create predictable 1-minute OHLCV data for testing."""

    timestamps = pd.date_range(
        start="2026-08-31 09:15",
        periods=30,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": range(100, 130),
            "high": range(101, 131),
            "low": range(99, 129),
            "close": range(100, 130),
            "volume": [1000] * 30,
        },
        index=timestamps,
    )


def test_5_minute_resampling():
    data = create_test_data()

    result = resample_ohlcv(data, "5m")

    assert len(result) == 6

    first = result.iloc[0]

    assert first["open"] == 100
    assert first["high"] == 105
    assert first["low"] == 99
    assert first["close"] == 104
    assert first["volume"] == 5000


def test_all_supported_timeframes():
    data = create_test_data()

    result = build_all_timeframes(data)

    assert set(result.keys()) == {
        "5m",
        "10m",
        "15m",
        "30m",
    }

    assert len(result["5m"]) == 6
    assert len(result["10m"]) == 3
    assert len(result["15m"]) == 2
    assert len(result["30m"]) == 1


def test_invalid_timeframe():
    data = create_test_data()

    with pytest.raises(ValueError):
        resample_ohlcv(data, "7m")


def test_missing_column():
    data = create_test_data().drop(columns=["volume"])

    with pytest.raises(ValueError):
        resample_ohlcv(data, "5m")


def test_invalid_index():
    data = create_test_data()
    data.index = range(len(data))

    with pytest.raises(TypeError):
        resample_ohlcv(data, "5m")


def test_incomplete_candle_is_removed():
    """An incomplete higher-timeframe candle must not be created."""

    data = create_test_data()

    # Remove the final minute.
    data = data.iloc[:-1]

    result = resample_ohlcv(data, "5m")

    assert len(result) == 5


def test_missing_minute_does_not_create_incomplete_candle():
    """A candle with missing 1-minute data must be excluded."""

    data = create_test_data()

    # Remove one minute from the first 5-minute group.
    data = data.drop(
        pd.Timestamp("2026-08-31 09:17")
    )

    result = resample_ohlcv(data, "5m")

    # The first 5-minute candle is incomplete.
    assert len(result) == 5


def test_multiple_days_are_kept_separate():
    """Candles from different days must never be mixed."""

    day_one = create_test_data()

    day_two = create_test_data()
    day_two.index = day_two.index + pd.Timedelta(days=1)

    data = pd.concat([day_one, day_two])

    result = resample_ohlcv(data, "5m")

    assert len(result) == 12

    assert result.index[0].date() != result.index[6].date()
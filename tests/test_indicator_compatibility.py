import pandas as pd
import pytest

from src.validation.indicator_compatibility import (
    IndicatorCompatibilityChecker,
)


def make_market_data(
    start: str = "2026-08-31 09:15",
    periods: int = 2000,
    volume: float = 1000.0,
) -> pd.DataFrame:
    index = pd.date_range(
        start=start,
        periods=periods,
        freq="min",
    )

    close = [
        100.0 + (index_position * 0.01)
        for index_position in range(periods)
    ]

    return pd.DataFrame(
        {
            "open": close,
            "high": [
                price + 0.5
                for price in close
            ],
            "low": [
                price - 0.5
                for price in close
            ],
            "close": close,
            "volume": [volume] * periods,
        },
        index=index,
    )


def test_sufficient_data_is_indicator_compatible():
    data = make_market_data()

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is True
    assert result.total_source_candles == 2000
    assert result.processed_source_candles == 2000

    assert result.ema20_ready is True
    assert result.ema50_ready is True
    assert result.rsi14_ready is True
    assert result.atr14_ready is True

    assert result.compatible_timeframes == (
        "5m",
        "10m",
        "15m",
        "30m",
    )

    assert result.compatibility_score == 100.0
    assert result.issues == ()


def test_all_required_timeframes_are_checked():
    data = make_market_data()

    result = IndicatorCompatibilityChecker().check(data)

    assert result.required_timeframes == (
        "5m",
        "10m",
        "15m",
        "30m",
    )

    for timeframe in result.required_timeframes:
        assert (
            result.timeframe_candle_counts[
                timeframe
            ] > 0
        )

        assert (
            result.timeframe_ready_counts[
                timeframe
            ] > 0
        )

        assert (
            result.timeframe_indicator_ready[
                timeframe
            ]
            is True
        )


def test_rvol_becomes_ready_with_positive_volume():
    data = make_market_data(
        volume=1000.0
    )

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is True
    assert result.rvol20_ready is True


def test_zero_volume_does_not_make_rvol_required():
    data = make_market_data(
        volume=0.0
    )

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is True
    assert result.rvol20_ready is False
    assert result.compatibility_score == 100.0
    assert result.issues == ()


def test_insufficient_data_fails():
    data = make_market_data(
        periods=100
    )

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is False
    assert result.compatibility_score < 100.0
    assert len(result.issues) > 0


def test_empty_dataframe_fails():
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

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is False
    assert result.total_source_candles == 0
    assert result.issues == (
        "Market data cannot be empty.",
    )


def test_non_dataframe_input_fails():
    result = IndicatorCompatibilityChecker().check(
        "invalid"
    )

    assert result.passed is False
    assert result.total_source_candles == 0
    assert result.issues == (
        "Market data must be a pandas DataFrame.",
    )


def test_invalid_index_fails():
    data = pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000.0],
        }
    )

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is False
    assert result.issues == (
        "Market data index must be a DatetimeIndex.",
    )


def test_missing_required_column_fails():
    data = make_market_data().drop(
        columns=["volume"]
    )

    result = IndicatorCompatibilityChecker().check(data)

    assert result.passed is False
    assert result.total_source_candles == 0
    assert len(result.issues) == 1
    assert "Missing required columns" in result.issues[0]


def test_input_is_not_modified():
    data = make_market_data()
    original = data.copy(deep=True)

    IndicatorCompatibilityChecker().check(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_custom_required_timeframes():
    data = make_market_data()

    checker = IndicatorCompatibilityChecker(
        required_timeframes=(
            "5m",
            "15m",
        )
    )

    result = checker.check(data)

    assert result.passed is True
    assert result.required_timeframes == (
        "5m",
        "15m",
    )

    assert result.compatible_timeframes == (
        "5m",
        "15m",
    )

    assert result.compatibility_score == 100.0


def test_unknown_timeframe_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported timeframes",
    ):
        IndicatorCompatibilityChecker(
            required_timeframes=(
                "5m",
                "1h",
            )
        )


def test_empty_timeframe_configuration_is_rejected():
    with pytest.raises(
        ValueError,
        match="required_timeframes must not be empty",
    ):
        IndicatorCompatibilityChecker(
            required_timeframes=()
        )


def test_invalid_minimum_ready_observations_is_rejected():
    with pytest.raises(
        ValueError,
        match="minimum_ready_observations must be greater than zero",
    ):
        IndicatorCompatibilityChecker(
            minimum_ready_observations=0
        )


def test_boolean_minimum_ready_observations_is_rejected():
    with pytest.raises(
        TypeError,
        match="minimum_ready_observations must be an integer",
    ):
        IndicatorCompatibilityChecker(
            minimum_ready_observations=True
        )

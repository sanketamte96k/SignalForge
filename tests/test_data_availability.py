import pandas as pd
import pytest

from src.validation.data_availability import (
    DEFAULT_REQUIRED_TIMEFRAMES,
    DataAvailabilityChecker,
)


def make_data(
    start: str = "2026-08-31 09:15",
    periods: int = 30,
) -> pd.DataFrame:
    index = pd.date_range(
        start=start,
        periods=periods,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": range(100, 100 + periods),
            "high": range(101, 101 + periods),
            "low": range(99, 99 + periods),
            "close": range(100, 100 + periods),
            "volume": [1000] * periods,
        },
        index=index,
    )


def make_full_session_data(
    days: int = 2,
) -> pd.DataFrame:
    frames = []

    for day in range(days):
        start = pd.Timestamp("2026-08-31 09:15") + pd.Timedelta(
            days=day
        )

        frames.append(
            make_data(
                start=str(start),
                periods=376,
            )
        )

    return pd.concat(frames)


def test_default_required_timeframes_are_supported():
    assert DEFAULT_REQUIRED_TIMEFRAMES == (
        "5m",
        "10m",
        "15m",
        "30m",
    )


def test_checker_accepts_valid_full_session_history():
    data = make_full_session_data(days=2)

    checker = DataAvailabilityChecker(
        minimum_candles=1,
        minimum_sessions=1,
    )

    result = checker.check(data)

    assert result.available is True
    assert result.has_data is True
    assert result.candle_count == 752
    assert result.session_count == 2

    assert result.first_timestamp == pd.Timestamp(
        "2026-08-31 09:15"
    )

    assert result.last_timestamp == pd.Timestamp(
        "2026-09-01 15:30"
    )

    assert result.timeframe_candle_counts == {
        "5m": 150,
        "10m": 74,
        "15m": 50,
        "30m": 24,
    }

    assert result.reasons == ()


def test_checker_excludes_out_of_session_candles():
    data = make_data(
        start="2026-08-31 08:00",
        periods=500,
    )

    checker = DataAvailabilityChecker()

    result = checker.check(data)

    assert result.first_timestamp == pd.Timestamp(
        "2026-08-31 09:15"
    )

    assert result.last_timestamp == pd.Timestamp(
        "2026-08-31 15:30"
    )

    assert result.session_count == 1


def test_checker_reports_insufficient_candles():
    data = make_data(periods=10)

    checker = DataAvailabilityChecker(
        minimum_candles=100,
    )

    result = checker.check(data)

    assert result.available is False
    assert any(
        "Insufficient 1-minute candle history"
        in reason
        for reason in result.reasons
    )


def test_checker_reports_insufficient_sessions():
    data = make_data(periods=376)

    checker = DataAvailabilityChecker(
        minimum_sessions=2,
    )

    result = checker.check(data)

    assert result.available is False
    assert result.session_count == 1
    assert any(
        "Insufficient trading-session history"
        in reason
        for reason in result.reasons
    )


def test_checker_reports_missing_complete_timeframe():
    data = make_data(periods=4)

    checker = DataAvailabilityChecker(
        required_timeframes=("5m",),
    )

    result = checker.check(data)

    assert result.available is False
    assert result.timeframe_candle_counts["5m"] == 0
    assert any(
        "No complete 5m candles"
        in reason
        for reason in result.reasons
    )


def test_checker_handles_empty_data():
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

    checker = DataAvailabilityChecker()

    result = checker.check(data)

    assert result.available is False
    assert result.candle_count == 0
    assert result.session_count == 0
    assert result.first_timestamp is None
    assert result.last_timestamp is None


def test_checker_handles_invalid_market_data():
    data = make_data(periods=10).drop(
        columns=["volume"]
    )

    checker = DataAvailabilityChecker()

    result = checker.check(data)

    assert result.available is False
    assert result.candle_count == 0
    assert len(result.reasons) == 1
    assert "Missing required columns" in result.reasons[0]


def test_checker_rejects_invalid_minimum_candles():
    with pytest.raises(ValueError, match="at least 1"):
        DataAvailabilityChecker(
            minimum_candles=0,
        )


def test_checker_rejects_invalid_minimum_sessions():
    with pytest.raises(ValueError, match="at least 1"):
        DataAvailabilityChecker(
            minimum_sessions=0,
        )


def test_checker_rejects_unsupported_timeframe():
    with pytest.raises(
        ValueError,
        match="Unsupported required timeframes",
    ):
        DataAvailabilityChecker(
            required_timeframes=("1h",),
        )


def test_checker_rejects_duplicate_timeframes():
    with pytest.raises(
        ValueError,
        match="must not contain duplicates",
    ):
        DataAvailabilityChecker(
            required_timeframes=("5m", "5m"),
        )


def test_checker_does_not_modify_input_data():
    data = make_full_session_data(days=1)
    original = data.copy(deep=True)

    checker = DataAvailabilityChecker()
    checker.check(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )

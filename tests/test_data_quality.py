import pandas as pd

from src.validation.data_quality import (
    EXPECTED_SESSION_CANDLES,
    DataQualityChecker,
)


def make_session_data(
    start: str = "2026-08-31 09:15",
    periods: int = EXPECTED_SESSION_CANDLES,
) -> pd.DataFrame:
    index = pd.date_range(
        start=start,
        periods=periods,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100.0] * periods,
            "high": [101.0] * periods,
            "low": [99.0] * periods,
            "close": [100.0] * periods,
            "volume": [1000.0] * periods,
        },
        index=index,
    )


def test_complete_session_passes_quality_check():
    data = make_session_data()

    result = DataQualityChecker().check(data)

    assert result.passed is True
    assert result.total_rows == 376
    assert result.session_count == 1
    assert result.complete_session_count == 1
    assert result.incomplete_session_count == 0
    assert result.missing_candle_count == 0
    assert result.issues == ()
    assert result.quality_score == 100.0


def test_multiple_complete_sessions_pass():
    first = make_session_data(
        start="2026-08-31 09:15"
    )

    second = make_session_data(
        start="2026-09-01 09:15"
    )

    data = pd.concat(
        [
            first,
            second,
        ]
    )

    result = DataQualityChecker().check(data)

    assert result.passed is True
    assert result.session_count == 2
    assert result.complete_session_count == 2
    assert result.incomplete_session_count == 0


def test_duplicate_timestamps_are_reported():
    data = make_session_data()

    duplicate = data.iloc[[100]]

    data = pd.concat(
        [
            data,
            duplicate,
        ]
    )

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.duplicate_timestamp_count == 2
    assert any(
        "Duplicate timestamps detected"
        in issue
        for issue in result.issues
    )


def test_out_of_order_timestamps_are_reported():
    data = make_session_data()

    indexes = list(data.index)

    indexes[10], indexes[11] = (
        indexes[11],
        indexes[10],
    )

    data.index = pd.DatetimeIndex(indexes)

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.out_of_order is True
    assert any(
        "not sorted" in issue
        for issue in result.issues
    )


def test_missing_minute_is_reported():
    data = make_session_data()

    missing_timestamp = pd.Timestamp(
        "2026-08-31 10:00"
    )

    data = data.drop(
        index=missing_timestamp
    )

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.missing_candle_count == 1
    assert result.incomplete_session_count == 1
    assert any(
        "Missing 1-minute candles"
        in issue
        for issue in result.issues
    )


def test_incomplete_session_is_reported():
    data = make_session_data(
        periods=300
    )

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.session_count == 1
    assert result.complete_session_count == 0
    assert result.incomplete_session_count == 1


def test_invalid_ohlc_is_reported():
    data = make_session_data()

    data.loc[
        data.index[10],
        "high",
    ] = 98.0

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.invalid_ohlc_count == 1
    assert any(
        "Invalid OHLC relationships"
        in issue
        for issue in result.issues
    )


def test_negative_volume_is_reported():
    data = make_session_data()

    data.loc[
        data.index[10],
        "volume",
    ] = -1.0

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.negative_volume_count == 1


def test_zero_volume_is_reported_but_not_failed():
    data = make_session_data()

    data.loc[
        data.index[10],
        "volume",
    ] = 0.0

    result = DataQualityChecker().check(data)

    assert result.passed is True
    assert result.zero_volume_count == 1
    assert result.zero_volume_ratio > 0
    assert result.issues == ()


def test_missing_values_are_reported():
    data = make_session_data()

    data.loc[
        data.index[10],
        "close",
    ] = float("nan")

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.missing_value_count == 1


def test_missing_required_column_is_reported():
    data = make_session_data().drop(
        columns=["volume"]
    )

    result = DataQualityChecker().check(data)

    assert result.passed is False
    assert result.total_rows == 0
    assert len(result.issues) == 1
    assert "Missing required columns" in result.issues[0]


def test_non_dataframe_input_is_reported():
    result = DataQualityChecker().check(
        "invalid"
    )

    assert result.passed is False
    assert result.total_rows == 0
    assert result.issues == (
        "Market data must be a pandas DataFrame.",
    )


def test_input_is_not_modified():
    data = make_session_data()
    original = data.copy(deep=True)

    DataQualityChecker().check(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_premarket_only_rows_are_not_counted_as_sessions():
    premarket = make_session_data(
        start="2026-08-31 08:00",
        periods=60,
    )

    result = DataQualityChecker().check(
        premarket
    )

    assert result.session_count == 0
    assert result.complete_session_count == 0
    assert result.incomplete_session_count == 0
    assert result.missing_candle_count == 0

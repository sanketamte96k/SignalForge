from datetime import time

import pandas as pd
import pytest

from src.data.session import (
    MARKET_CLOSE,
    MARKET_OPEN,
    filter_market_session,
    is_market_session_timestamp,
    prepare_market_session,
    remove_duplicate_timestamps,
    validate_session_parameters,
)


def make_data():
    index = pd.to_datetime(
        [
            "2026-08-31 09:00",
            "2026-08-31 09:15",
            "2026-08-31 09:16",
            "2026-08-31 12:00",
            "2026-08-31 15:30",
            "2026-08-31 15:31",
            "2026-08-31 16:00",
        ]
    )

    return pd.DataFrame(
        {
            "close": [
                99,
                100,
                101,
                105,
                110,
                111,
                112,
            ]
        },
        index=index,
    )


def test_default_market_open():
    assert MARKET_OPEN == time(9, 15)


def test_default_market_close():
    assert MARKET_CLOSE == time(15, 30)


def test_valid_session_parameters():
    validate_session_parameters(
        time(9, 15),
        time(15, 30),
    )


def test_invalid_market_open_type():
    with pytest.raises(TypeError):
        validate_session_parameters(
            "09:15",
            time(15, 30),
        )


def test_invalid_market_close_type():
    with pytest.raises(TypeError):
        validate_session_parameters(
            time(9, 15),
            "15:30",
        )


def test_open_must_be_before_close():
    with pytest.raises(ValueError):
        validate_session_parameters(
            time(15, 30),
            time(9, 15),
        )


def test_equal_open_and_close_is_invalid():
    with pytest.raises(ValueError):
        validate_session_parameters(
            time(9, 15),
            time(9, 15),
        )


def test_filter_returns_dataframe():
    result = filter_market_session(
        make_data()
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )


def test_pre_market_data_is_removed():
    result = filter_market_session(
        make_data()
    )

    assert pd.Timestamp(
        "2026-08-31 09:00"
    ) not in result.index


def test_market_open_is_included():
    result = filter_market_session(
        make_data()
    )

    assert pd.Timestamp(
        "2026-08-31 09:15"
    ) in result.index


def test_intraday_data_is_kept():
    result = filter_market_session(
        make_data()
    )

    assert pd.Timestamp(
        "2026-08-31 12:00"
    ) in result.index


def test_market_close_is_included():
    result = filter_market_session(
        make_data()
    )

    assert pd.Timestamp(
        "2026-08-31 15:30"
    ) in result.index


def test_after_market_data_is_removed():
    result = filter_market_session(
        make_data()
    )

    assert pd.Timestamp(
        "2026-08-31 15:31"
    ) not in result.index

    assert pd.Timestamp(
        "2026-08-31 16:00"
    ) not in result.index


def test_expected_number_of_rows():
    result = filter_market_session(
        make_data()
    )

    assert len(result) == 4


def test_empty_dataframe_is_supported():
    data = pd.DataFrame(
        {"close": []},
        index=pd.DatetimeIndex([]),
    )

    result = filter_market_session(
        data
    )

    assert result.empty


def test_invalid_dataframe_type():
    with pytest.raises(TypeError):
        filter_market_session(
            "invalid"
        )


def test_invalid_index():
    data = pd.DataFrame(
        {"close": [100, 101]}
    )

    with pytest.raises(TypeError):
        filter_market_session(
            data
        )


def test_custom_session():
    data = make_data()

    result = filter_market_session(
        data,
        market_open=time(10, 0),
        market_close=time(14, 0),
    )

    assert list(result["close"]) == [105]


def test_market_open_timestamp_is_valid():
    timestamp = pd.Timestamp(
        "2026-08-31 09:15"
    )

    assert is_market_session_timestamp(
        timestamp
    ) is True


def test_market_close_timestamp_is_valid():
    timestamp = pd.Timestamp(
        "2026-08-31 15:30"
    )

    assert is_market_session_timestamp(
        timestamp
    ) is True


def test_before_market_timestamp_is_invalid():
    timestamp = pd.Timestamp(
        "2026-08-31 09:14"
    )

    assert is_market_session_timestamp(
        timestamp
    ) is False


def test_after_market_timestamp_is_invalid():
    timestamp = pd.Timestamp(
        "2026-08-31 15:31"
    )

    assert is_market_session_timestamp(
        timestamp
    ) is False


def test_timestamp_type_is_validated():
    with pytest.raises(TypeError):
        is_market_session_timestamp(
            "2026-08-31 09:15"
        )


def test_remove_duplicate_timestamps():
    index = pd.to_datetime(
        [
            "2026-08-31 09:15",
            "2026-08-31 09:15",
            "2026-08-31 09:16",
        ]
    )

    data = pd.DataFrame(
        {
            "close": [
                100,
                101,
                102,
            ]
        },
        index=index,
    )

    result = remove_duplicate_timestamps(
        data
    )

    assert len(result) == 2

    assert result.iloc[0]["close"] == 100


def test_remove_duplicate_timestamps_preserves_first():
    index = pd.to_datetime(
        [
            "2026-08-31 09:15",
            "2026-08-31 09:15",
        ]
    )

    data = pd.DataFrame(
        {
            "close": [
                100,
                999,
            ]
        },
        index=index,
    )

    result = remove_duplicate_timestamps(
        data
    )

    assert result.iloc[0]["close"] == 100


def test_prepare_market_session_sorts_data():
    data = make_data().iloc[::-1]

    result = prepare_market_session(
        data
    )

    assert result.index.is_monotonic_increasing


def test_prepare_market_session_removes_duplicates():
    data = make_data()

    duplicate = data.iloc[[1]]

    data = pd.concat(
        [data, duplicate]
    )

    result = prepare_market_session(
        data
    )

    assert not result.index.has_duplicates


def test_prepare_market_session_filters_session():
    result = prepare_market_session(
        make_data()
    )

    assert len(result) == 4


def test_prepare_market_session_preserves_data():
    result = prepare_market_session(
        make_data()
    )

    assert result.loc[
        pd.Timestamp("2026-08-31 09:15"),
        "close",
    ] == 100


def test_prepare_market_session_invalid_index():
    data = pd.DataFrame(
        {
            "close": [100]
        }
    )

    with pytest.raises(TypeError):
        prepare_market_session(
            data
        )
"""Tests for causal higher-timeframe construction."""

import pandas as pd
import pytest

from src.strategy.causal_timeframes import (
    CausalTimeframeBuilder,
)


def make_candle(
    timestamp: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
) -> pd.Series:
    candle = pd.Series(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )

    candle.name = pd.Timestamp(timestamp)

    return candle


def test_five_minute_candle_requires_five_source_candles():
    builder = CausalTimeframeBuilder()

    for minute in range(4):
        result = builder.process_candle(
            make_candle(
                f"2026-08-25 09:{15 + minute:02d}",
                100 + minute,
                101 + minute,
                99 + minute,
                100.5 + minute,
            )
        )

        assert "5m" not in result

    result = builder.process_candle(
        make_candle(
            "2026-08-25 09:19",
            104,
            105,
            103,
            104.5,
        )
    )

    assert "5m" in result

    candle = result["5m"]

    assert candle.timestamp == pd.Timestamp(
        "2026-08-25 09:15"
    )
    assert candle.open == 100
    assert candle.high == 105
    assert candle.low == 99
    assert candle.close == 104.5
    assert candle.volume == 500


def test_ten_minute_candle_requires_ten_source_candles():
    builder = CausalTimeframeBuilder()

    for minute in range(10):
        result = builder.process_candle(
            make_candle(
                f"2026-08-25 09:{15 + minute:02d}",
                100,
                101,
                99,
                100,
            )
        )

    assert "10m" in result

    candle = result["10m"]

    assert candle.timestamp == pd.Timestamp(
        "2026-08-25 09:15"
    )


def test_no_future_candle_is_used():
    builder = CausalTimeframeBuilder()

    for minute in range(4):
        result = builder.process_candle(
            make_candle(
                f"2026-08-25 09:{15 + minute:02d}",
                100,
                101,
                99,
                100,
            )
        )

        assert "5m" not in result

    # The fifth candle completes the 5m candle.
    result = builder.process_candle(
        make_candle(
            "2026-08-25 09:19",
            100,
            101,
            99,
            100,
        )
    )

    assert "5m" in result


def test_incomplete_bucket_is_discarded():
    builder = CausalTimeframeBuilder()

    for minute in range(3):
        result = builder.process_candle(
            make_candle(
                f"2026-08-25 09:{15 + minute:02d}",
                100,
                101,
                99,
                100,
            )
        )

        assert "5m" not in result

    # Jump to the next 5-minute bucket.
    result = builder.process_candle(
        make_candle(
            "2026-08-25 09:20",
            100,
            101,
            99,
            100,
        )
    )

    assert "5m" not in result


def test_all_timeframes_complete_at_expected_points():
    builder = CausalTimeframeBuilder()

    completed_at: dict[str, pd.Timestamp] = {}

    for minute in range(30):
        timestamp = pd.Timestamp(
            "2026-08-25 09:15"
        ) + pd.Timedelta(minutes=minute)

        result = builder.process_candle(
            make_candle(
                str(timestamp),
                100,
                101,
                99,
                100,
            )
        )

        for timeframe in result:
            completed_at[timeframe] = timestamp

    assert completed_at["5m"] == pd.Timestamp(
        "2026-08-25 09:44"
    )
    assert completed_at["10m"] == pd.Timestamp(
        "2026-08-25 09:44"
    )
    assert completed_at["15m"] == pd.Timestamp(
        "2026-08-25 09:44"
    )
    assert completed_at["30m"] == pd.Timestamp(
        "2026-08-25 09:44"
    )


def test_invalid_candle_type():
    builder = CausalTimeframeBuilder()

    with pytest.raises(TypeError):
        builder.process_candle("not a candle")


def test_missing_ohlcv_column():
    builder = CausalTimeframeBuilder()

    candle = make_candle(
        "2026-08-25 09:15",
        100,
        101,
        99,
        100,
    )

    candle = candle.drop("volume")

    with pytest.raises(ValueError):
        builder.process_candle(candle)


def test_invalid_high_low():
    builder = CausalTimeframeBuilder()

    candle = make_candle(
        "2026-08-25 09:15",
        100,
        98,
        99,
        100,
    )

    with pytest.raises(ValueError):
        builder.process_candle(candle)
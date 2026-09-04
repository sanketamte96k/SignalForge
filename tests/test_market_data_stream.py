"""Tests for the causal market-data streaming interface."""

from __future__ import annotations

import pandas as pd
import pytest

from src.market_data.replay_adapter import (
    ReplayMarketDataAdapter,
)


def make_market_data(
    rows: int = 10,
) -> pd.DataFrame:
    """
    Create deterministic 1-minute OHLCV test data.
    """

    index = pd.date_range(
        "2026-08-24 09:15:00",
        periods=rows,
        freq="min",
    )

    values = range(100, 100 + rows)

    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1000] * rows,
        },
        index=index,
    )


def test_replay_adapter_implements_stream_interface() -> None:
    """Replay adapter exposes the causal stream contract."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    assert adapter.has_next()
    assert adapter.current_timestamp is None
    assert adapter.remaining_candles == 10


def test_next_candle_consumes_exactly_one_candle() -> None:
    """Each next_candle call exposes only the next candle."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    first = adapter.next_candle()

    assert first.name == data.index[0]
    assert adapter.current_timestamp == data.index[0]
    assert adapter.remaining_candles == 9


def test_stream_is_chronological() -> None:
    """Candle timestamps are exposed strictly chronologically."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    timestamps = []

    while adapter.has_next():
        candle = adapter.next_candle()
        timestamps.append(candle.name)

    assert timestamps == list(data.index)


def test_stream_never_returns_future_candle() -> None:
    """
    Once a candle has been consumed, the latest candle is exactly
    the consumed candle and not a future candle.
    """

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    first = adapter.next_candle()

    latest = adapter.get_latest_candle()

    assert latest.name == first.name
    assert latest["close"] == first["close"]

    second = adapter.next_candle()

    latest = adapter.get_latest_candle()

    assert latest.name == second.name
    assert latest.name > first.name


def test_recent_candles_contain_only_consumed_data() -> None:
    """Recent-candle access cannot expose future candles."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    adapter.next_candle()
    adapter.next_candle()
    adapter.next_candle()

    recent = adapter.get_recent_candles(10)

    assert len(recent) == 3
    assert list(recent.index) == list(
        data.index[:3]
    )

    assert recent.index[-1] == data.index[2]


def test_recent_candles_respect_limit() -> None:
    """Recent-candle history respects the requested limit."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    for _ in range(5):
        adapter.next_candle()

    recent = adapter.get_recent_candles(2)

    assert len(recent) == 2
    assert list(recent.index) == list(
        data.index[3:5]
    )


def test_recent_candles_before_consumption_are_empty() -> None:
    """No historical candles are available before consumption."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    recent = adapter.get_recent_candles(5)

    assert recent.empty
    assert list(recent.columns) == list(
        data.columns
    )


def test_reset_restores_stream_to_beginning() -> None:
    """Reset returns the stream to its initial state."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    adapter.next_candle()
    adapter.next_candle()

    assert adapter.remaining_candles == 8

    adapter.reset()

    assert adapter.remaining_candles == 10
    assert adapter.current_timestamp is None
    assert adapter.has_next()

    first = adapter.next_candle()

    assert first.name == data.index[0]


def test_next_candle_raises_after_end() -> None:
    """The stream raises StopIteration after all candles are consumed."""

    data = make_market_data(2)

    adapter = ReplayMarketDataAdapter(data)

    adapter.next_candle()
    adapter.next_candle()

    assert not adapter.has_next()
    assert adapter.remaining_candles == 0

    with pytest.raises(StopIteration):
        adapter.next_candle()


def test_data_property_returns_copy() -> None:
    """
    The public data property cannot mutate the adapter's internal data.
    """

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    exposed = adapter.data

    exposed.iloc[0, exposed.columns.get_loc("close")] = 999999

    latest = adapter.data

    assert latest.iloc[0]["close"] == data.iloc[0]["close"]
import pandas as pd
import pytest

from src.market_data.adapter import MarketDataValidationError
from src.market_data.replay_adapter import ReplayMarketDataAdapter


def make_data(rows: int = 5) -> pd.DataFrame:
    index = pd.date_range(
        "2023-01-02 09:15:00",
        periods=rows,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(rows)],
            "high": [101.0 + i for i in range(rows)],
            "low": [99.0 + i for i in range(rows)],
            "close": [100.5 + i for i in range(rows)],
            "volume": [1000.0 + i for i in range(rows)],
        },
        index=index,
    )


def test_replay_adapter_initializes():
    adapter = ReplayMarketDataAdapter(make_data())

    assert adapter.current_timestamp is None
    assert adapter.remaining_candles == 5
    assert adapter.has_next() is True


def test_replay_adapter_next_candle_consumes_data():
    adapter = ReplayMarketDataAdapter(make_data())

    assert adapter.has_next() is True

    candle = adapter.next_candle()

    assert candle["open"] == 100.0
    assert candle["close"] == 100.5
    assert adapter.current_timestamp == pd.Timestamp("2023-01-02 09:15:00")
    assert adapter.remaining_candles == 4


def test_latest_candle_requires_consumed_data():
    adapter = ReplayMarketDataAdapter(make_data())

    with pytest.raises(
        MarketDataValidationError,
        match="No candle has been consumed",
    ):
        adapter.get_latest_candle()


def test_latest_candle_returns_last_consumed_candle():
    adapter = ReplayMarketDataAdapter(make_data())

    first = adapter.next_candle()
    latest = adapter.get_latest_candle()

    pd.testing.assert_series_equal(latest, first)


def test_recent_candles_returns_consumed_window():
    adapter = ReplayMarketDataAdapter(make_data())

    adapter.next_candle()
    adapter.next_candle()
    adapter.next_candle()

    recent = adapter.get_recent_candles(2)

    assert len(recent) == 2
    assert recent.index[0] == pd.Timestamp("2023-01-02 09:16:00")
    assert recent.index[1] == pd.Timestamp("2023-01-02 09:17:00")


def test_recent_candles_before_consumption_is_empty():
    adapter = ReplayMarketDataAdapter(make_data())

    recent = adapter.get_recent_candles(3)

    assert recent.empty


def test_recent_candles_validates_limit():
    adapter = ReplayMarketDataAdapter(make_data())

    with pytest.raises(TypeError, match="limit must be an integer"):
        adapter.get_recent_candles(2.5)

    with pytest.raises(ValueError, match="limit must be positive"):
        adapter.get_recent_candles(0)


def test_replay_stops_after_last_candle():
    adapter = ReplayMarketDataAdapter(make_data(rows=2))

    adapter.next_candle()
    adapter.next_candle()

    assert adapter.has_next() is False

    with pytest.raises(StopIteration):
        adapter.next_candle()


def test_reset_rewinds_replay():
    adapter = ReplayMarketDataAdapter(make_data())

    adapter.next_candle()
    adapter.next_candle()

    assert adapter.remaining_candles == 3

    adapter.reset()

    assert adapter.current_timestamp is None
    assert adapter.remaining_candles == 5
    assert adapter.has_next() is True


def test_replay_adapter_does_not_modify_input():
    data = make_data()
    original = data.copy(deep=True)

    ReplayMarketDataAdapter(data)

    pd.testing.assert_frame_equal(data, original)
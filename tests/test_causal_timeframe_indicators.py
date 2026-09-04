import pandas as pd

from src.strategy.causal_timeframe_indicators import (
    CausalTimeframeIndicatorCoordinator,
)


def make_candle(timestamp, price):
    return pd.Series(
        {
            "timestamp": pd.Timestamp(timestamp),
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000.0,
        }
    )


def test_higher_timeframe_candle_is_not_available_before_bucket_closes():
    coordinator = CausalTimeframeIndicatorCoordinator()

    for minute in range(15, 20):
        timestamp = f"2024-01-02 09:{minute:02d}:00"
        states = coordinator.process_candle(
            make_candle(timestamp, 100.0 + minute)
        )

        if minute < 19:
            assert "5m" not in states

    # The 09:15-09:20 candle is completed by the 09:19 source candle,
    # but must NOT be visible until 09:20.
    states = coordinator.process_candle(
        make_candle("2024-01-02 09:19:00", 119.0)
    )

    assert "5m" not in states

    states = coordinator.process_candle(
        make_candle("2024-01-02 09:20:00", 120.0)
    )

    assert "5m" in states


def test_multiple_timeframes_are_processed_causally():
    coordinator = CausalTimeframeIndicatorCoordinator()

    visible_history = []

    for minute in range(15, 46):
        timestamp = pd.Timestamp(
            f"2024-01-02 09:{minute:02d}:00"
        )

        states = coordinator.process_candle(
            make_candle(timestamp, 100.0 + minute)
        )

        visible_history.append(
            (timestamp, set(states.keys()))
        )

    # 5m should become visible at 09:20, 09:25, ...
    assert "5m" not in visible_history[0][1]
    assert "5m" in visible_history[5][1]

    # 10m should first become visible at 09:25
    assert "10m" not in visible_history[9][1]
    assert "10m" in visible_history[10][1]

    # 15m should first become visible at 09:30
    assert "15m" not in visible_history[14][1]
    assert "15m" in visible_history[15][1]

    # 30m should first become visible at 09:45
    assert "30m" not in visible_history[29][1]
    assert "30m" in visible_history[30][1]


def test_reset_clears_all_state():
    coordinator = CausalTimeframeIndicatorCoordinator()

    for minute in range(15, 21):
        coordinator.process_candle(
            make_candle(
                f"2024-01-02 09:{minute:02d}:00",
                100.0 + minute,
            )
        )

    coordinator.reset()

    states = coordinator.process_candle(
        make_candle("2024-01-02 09:15:00", 100.0)
    )

    assert states == {}
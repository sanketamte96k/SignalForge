import pandas as pd

from src.strategy.causal_indicators import CausalIndicatorState


EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
RVOL_PERIOD = 20


def make_indicator_state():
    return CausalIndicatorState(
        ema_fast_period=EMA_FAST_PERIOD,
        ema_slow_period=EMA_SLOW_PERIOD,
        rsi_period=RSI_PERIOD,
        atr_period=ATR_PERIOD,
        rvol_period=RVOL_PERIOD,
    )


def make_ohlcv(
    timestamps,
    closes,
    volume=1000.0,
):
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps),
            "open": closes,
            "high": [value + 1.0 for value in closes],
            "low": [value - 1.0 for value in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        }
    )


def feed_data(state, data):
    snapshots = []

    for _, row in data.iterrows():
        snapshot = state.update(
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )

        snapshots.append(snapshot)

    return snapshots


def test_future_candle_cannot_change_current_indicator_state():
    """Future data must not alter an already-observed indicator state."""

    timestamps = pd.date_range(
        "2024-01-02 09:15:00",
        periods=25,
        freq="min",
    )

    base_closes = [
        100.0 + i * 0.25
        for i in range(25)
    ]

    future_modified_closes = base_closes.copy()

    # Modify only candles after the observation point.
    for i in range(20, 25):
        future_modified_closes[i] += 500.0

    base_data = make_ohlcv(
        timestamps,
        base_closes,
    )

    modified_data = make_ohlcv(
        timestamps,
        future_modified_closes,
    )

    base_state = make_indicator_state()
    modified_state = make_indicator_state()

    base_snapshots = feed_data(
        base_state,
        base_data,
    )

    modified_snapshots = feed_data(
        modified_state,
        modified_data,
    )

    # Index 19 is the last candle before the modified future.
    base_current = base_snapshots[19]
    modified_current = modified_snapshots[19]

    assert base_current is not None
    assert modified_current is not None

    assert base_current.ema_fast == modified_current.ema_fast
    assert base_current.ema_slow == modified_current.ema_slow
    assert base_current.rsi == modified_current.rsi
    assert base_current.atr == modified_current.atr
    assert base_current.rvol == modified_current.rvol


def test_indicator_state_depends_only_on_data_seen_so_far():
    """Identical history must produce identical indicator states."""

    timestamps = pd.date_range(
        "2024-01-02 09:15:00",
        periods=25,
        freq="min",
    )

    closes = [
        100.0 + i * 0.5
        for i in range(25)
    ]

    data = make_ohlcv(
        timestamps,
        closes,
    )

    state_a = make_indicator_state()
    state_b = make_indicator_state()

    snapshots_a = feed_data(
        state_a,
        data.iloc[:20],
    )

    snapshots_b = feed_data(
        state_b,
        data.iloc[:20],
    )

    current_a = snapshots_a[-1]
    current_b = snapshots_b[-1]

    assert current_a is not None
    assert current_b is not None

    assert current_a == current_b
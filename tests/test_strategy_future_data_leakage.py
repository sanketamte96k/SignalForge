import pandas as pd

from src.backtest.simulator import Position
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


def make_data(
    periods: int,
    future_shift: float = 0.0,
) -> pd.DataFrame:
    """Create deterministic 1-minute OHLCV data."""

    timestamps = pd.date_range(
        "2024-01-02 09:15:00",
        periods=periods,
        freq="min",
    )

    closes = []

    for index in range(periods):
        price = 100.0 + index * 0.25

        if index >= 60:
            price += future_shift

        closes.append(price)

    return pd.DataFrame(
        {
            "open": closes,
            "high": [price + 1.0 for price in closes],
            "low": [price - 1.0 for price in closes],
            "close": closes,
            "volume": [1000.0] * periods,
        },
        index=timestamps,
    )


def make_config() -> StrategyConfig:
    """Return the frozen SignalForge strategy configuration."""

    return StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        minimum_long_rsi=60.0,
        use_rvol=True,
    )


def get_signal_at_timestamp(
    data: pd.DataFrame,
    timestamp: pd.Timestamp,
):
    """Evaluate the strategy at exactly one timestamp."""

    signal_function = create_signal_function(
        data,
        make_config(),
    )

    row = data.loc[timestamp]

    previous_timestamp = data.index[
        data.index < timestamp
    ][-1]

    previous_row = data.loc[previous_timestamp]

    return signal_function(
        row,
        previous_row,
    )


def test_future_data_cannot_change_signal_at_observation_time():
    """Adding future candles must not change an earlier signal."""

    observation_timestamp = pd.Timestamp(
        "2024-01-02 10:15:00"
    )

    history = make_data(
        periods=61,
        future_shift=0.0,
    )

    full_data = make_data(
        periods=80,
        future_shift=500.0,
    )

    history_signal = get_signal_at_timestamp(
        history,
        observation_timestamp,
    )

    full_data_signal = get_signal_at_timestamp(
        full_data,
        observation_timestamp,
    )

    assert history_signal == full_data_signal


def test_future_data_cannot_change_multiple_earlier_signals():
    """Several historical signals must remain independent of future data."""

    observation_timestamps = [
        pd.Timestamp("2024-01-02 10:05:00"),
        pd.Timestamp("2024-01-02 10:15:00"),
        pd.Timestamp("2024-01-02 10:25:00"),
    ]

    history = make_data(
        periods=71,
        future_shift=0.0,
    )

    full_data = make_data(
        periods=100,
        future_shift=1000.0,
    )

    for timestamp in observation_timestamps:
        history_signal = get_signal_at_timestamp(
            history,
            timestamp,
        )

        full_data_signal = get_signal_at_timestamp(
            full_data,
            timestamp,
        )

        assert history_signal == full_data_signal
from __future__ import annotations

import pandas as pd

from src.strategy.backtest_strategy import (
    create_signal_function,
)


def make_market_data(
    rows: int = 3000,
    start: str = "2026-08-24 09:15:00",
) -> pd.DataFrame:
    """
    Create deterministic 1-minute OHLCV data for causality tests.
    """

    index = pd.date_range(
        start,
        periods=rows,
        freq="min",
    )

    close = pd.Series(
        range(100, 100 + rows),
        index=index,
        dtype=float,
    )

    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def make_previous_row(
    data: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series:
    """Return the candle immediately before timestamp."""

    previous_timestamp = (
        timestamp - pd.Timedelta(minutes=1)
    )

    return data.loc[previous_timestamp]


def test_future_candles_do_not_change_signal_at_timestamp():
    """
    A signal at T must not depend on candles after T.
    """

    data = make_market_data()

    timestamp = pd.Timestamp(
        "2026-08-26 10:00:00"
    )

    historical_data = data.loc[
        :timestamp
    ].copy()

    future_data = data.loc[
        timestamp + pd.Timedelta(minutes=1):
    ].copy()

    # Make all future candles radically different.
    future_data.loc[:, "open"] = 1_000_000.0
    future_data.loc[:, "high"] = 1_000_001.0
    future_data.loc[:, "low"] = 999_999.0
    future_data.loc[:, "close"] = 1_000_000.0
    future_data.loc[:, "volume"] = 10_000_000.0

    full_data = pd.concat(
        [
            historical_data,
            future_data,
        ]
    )

    historical_strategy = create_signal_function(
        historical_data
    )

    full_strategy = create_signal_function(
        full_data
    )

    current_row = historical_data.loc[
        timestamp
    ]

    previous_row = make_previous_row(
        historical_data,
        timestamp,
    )

    historical_signal = historical_strategy(
        current_row,
        previous_row,
    )

    full_signal = full_strategy(
        current_row,
        previous_row,
    )

    assert historical_signal == full_signal


def test_future_candles_can_be_removed_without_changing_signal():
    """
    Removing candles after T must not change the signal at T.
    """

    data = make_market_data()

    timestamp = pd.Timestamp(
        "2026-08-26 10:00:00"
    )

    historical_data = data.loc[
        :timestamp
    ].copy()

    full_strategy = create_signal_function(
        data
    )

    historical_strategy = create_signal_function(
        historical_data
    )

    current_row = historical_data.loc[
        timestamp
    ]

    previous_row = make_previous_row(
        historical_data,
        timestamp,
    )

    signal_with_future = full_strategy(
        current_row,
        previous_row,
    )

    signal_without_future = historical_strategy(
        current_row,
        previous_row,
    )

    assert (
        signal_with_future
        == signal_without_future
    )


def test_future_price_extreme_does_not_affect_current_signal():
    """
    Extreme future price changes must not influence
    a signal generated at an earlier timestamp.
    """

    data = make_market_data()

    timestamp = pd.Timestamp(
        "2026-08-26 10:00:00"
    )

    normal_data = data.copy()

    modified_data = data.copy()

    future_mask = (
        modified_data.index
        > timestamp
    )

    modified_data.loc[
        future_mask,
        "open"
    ] = -1_000_000.0

    modified_data.loc[
        future_mask,
        "high"
    ] = 2_000_000.0

    modified_data.loc[
        future_mask,
        "low"
    ] = -2_000_000.0

    modified_data.loc[
        future_mask,
        "close"
    ] = 1_500_000.0

    modified_data.loc[
        future_mask,
        "volume"
    ] = 99_999_999.0

    normal_strategy = create_signal_function(
        normal_data
    )

    modified_strategy = create_signal_function(
        modified_data
    )

    current_row = normal_data.loc[
        timestamp
    ]

    previous_row = make_previous_row(
        normal_data,
        timestamp,
    )

    normal_signal = normal_strategy(
        current_row,
        previous_row,
    )

    modified_signal = modified_strategy(
        current_row,
        previous_row,
    )

    assert normal_signal == modified_signal
"""Tests for the causal strategy context."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.simulator import Position
from src.strategy.context import (
    CausalStrategyContext,
)


def make_market_data(
    rows: int = 3000,
) -> pd.DataFrame:
    """
    Create deterministic 1-minute OHLCV data.

    The dataset is long enough to provide the minimum historical
    context required by the multi-timeframe strategy.
    """

    index = pd.date_range(
        "2026-08-24 09:15:00",
        periods=rows,
        freq="min",
    )

    values = [
        100.0 + (index_position * 0.01)
        for index_position in range(rows)
    ]

    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 0.10 for value in values],
            "low": [value - 0.10 for value in values],
            "close": values,
            "volume": [1000.0] * rows,
        },
        index=index,
    )


def test_context_processes_first_candle_without_signal() -> None:
    """The first candle establishes previous-candle state."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    candle = data.iloc[0].copy()

    result = context.process_candle(candle)

    assert result.timestamp == data.index[0]
    assert result.position is None

    assert context.processed_count == 1
    assert context.last_timestamp == data.index[0]


def test_context_processes_candles_sequentially() -> None:
    """The context accepts strictly increasing candles."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    for position in range(5):
        result = context.process_candle(
            data.iloc[position].copy()
        )

        assert result.timestamp == data.index[position]

    assert context.processed_count == 5
    assert context.last_timestamp == data.index[4]


def test_context_rejects_duplicate_timestamp() -> None:
    """A candle cannot be processed twice."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    candle = data.iloc[0].copy()

    context.process_candle(candle)

    with pytest.raises(ValueError, match="strictly greater"):
        context.process_candle(candle)


def test_context_rejects_out_of_order_candle() -> None:
    """Candles must arrive chronologically."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    context.process_candle(
        data.iloc[5].copy()
    )

    with pytest.raises(ValueError, match="strictly greater"):
        context.process_candle(
            data.iloc[4].copy()
        )


def test_context_tracks_previous_candle() -> None:
    """Previous-candle state is updated after every candle."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    context.process_candle(
        data.iloc[0].copy()
    )

    previous = context.previous_candle

    assert previous is not None
    assert previous.name == data.index[0]

    context.process_candle(
        data.iloc[1].copy()
    )

    previous = context.previous_candle

    assert previous is not None
    assert previous.name == data.index[1]


def test_context_returns_copy_of_previous_candle() -> None:
    """External mutation cannot modify internal previous-candle state."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    context.process_candle(
        data.iloc[0].copy()
    )

    previous = context.previous_candle

    assert previous is not None

    previous["close"] = 999999999.0

    internal = context.previous_candle

    assert internal is not None
    assert internal["close"] == data.iloc[0]["close"]


def test_context_reset_restores_initial_state() -> None:
    """Reset clears sequential processing state."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    context.process_candle(
        data.iloc[0].copy()
    )

    context.process_candle(
        data.iloc[1].copy()
    )

    assert context.processed_count == 2
    assert context.last_timestamp == data.index[1]

    context.reset()

    assert context.processed_count == 0
    assert context.last_timestamp is None
    assert context.previous_candle is None


def test_context_rejects_non_series() -> None:
    """Only pandas Series candles are accepted."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    with pytest.raises(TypeError, match="pandas Series"):
        context.process_candle(
            data.iloc[[0]]
        )


def test_context_rejects_missing_timestamp() -> None:
    """Candles require a timestamp in Series.name."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    candle = data.iloc[0].copy()
    candle.name = None

    with pytest.raises(ValueError, match="timestamp"):
        context.process_candle(candle)


def test_context_produces_valid_position_values() -> None:
    """Returned strategy positions are valid SignalForge positions."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    positions = []

    for position in range(100):
        result = context.process_candle(
            data.iloc[position].copy()
        )

        positions.append(result.position)

    assert all(
        position in (
            None,
            Position.LONG,
            Position.SHORT,
        )
        for position in positions
    )


def test_context_does_not_modify_input_candle() -> None:
    """Processing a candle does not mutate the caller's Series."""

    data = make_market_data()

    context = CausalStrategyContext(data)

    candle = data.iloc[0].copy()
    original = candle.copy()

    context.process_candle(candle)

    pd.testing.assert_series_equal(
        candle,
        original,
    )


def test_context_future_candle_changes_do_not_change_past_signal() -> None:
    """
    Changing candles after a decision point cannot change the signal
    already produced at that decision point.
    """

    data = make_market_data()

    context_a = CausalStrategyContext(data)

    decision_index = 1000

    result_a = None

    for position in range(
        decision_index + 1
    ):
        result_a = context_a.process_candle(
            data.iloc[position].copy()
        )

    future_changed = data.copy()

    future_changed.iloc[
        decision_index + 1:
    ] = future_changed.iloc[
        decision_index + 1:
    ].assign(
        open=999999.0,
        high=1000000.0,
        low=999998.0,
        close=999999.5,
        volume=99999999.0,
    )

    context_b = CausalStrategyContext(
        future_changed
    )

    result_b = None

    for position in range(
        decision_index + 1
    ):
        result_b = context_b.process_candle(
            future_changed.iloc[position].copy()
        )

    assert result_a is not None
    assert result_b is not None

    assert result_a.timestamp == result_b.timestamp
    assert result_a.position == result_b.position
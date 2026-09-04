"""Tests for causal strategy-context replay integration."""

from __future__ import annotations

import pandas as pd

from src.market_data.replay_adapter import (
    ReplayMarketDataAdapter,
)
from src.paper_trading.replay_runner import (
    PaperTradingReplayRunner,
)
from src.strategy.context import (
    CausalStrategyContext,
)


def make_market_data(
    rows: int = 3000,
) -> pd.DataFrame:
    """Create deterministic 1-minute OHLCV data."""

    index = pd.date_range(
        "2026-08-24 09:15:00",
        periods=rows,
        freq="min",
    )

    values = [
        100.0 + index_position * 0.01
        for index_position in range(rows)
    ]

    return pd.DataFrame(
        {
            "open": values,
            "high": [
                value + 0.10
                for value in values
            ],
            "low": [
                value - 0.10
                for value in values
            ],
            "close": values,
            "volume": [1000.0] * rows,
        },
        index=index,
    )


def test_runner_creates_causal_strategy_context() -> None:
    """Replay runner uses CausalStrategyContext."""

    data = make_market_data()

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter,
    )

    runner.run()

    assert isinstance(
        runner.strategy_context,
        CausalStrategyContext,
    )


def test_runner_processes_all_replay_candles() -> None:
    """The strategy context processes every eligible session candle."""

    data = make_market_data(100)

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter,
    )

    runner.run()

    context = runner.strategy_context

    assert context is not None

    assert context.processed_count == 100

    assert context.last_timestamp == data.index[-1]


def test_runner_consumes_entire_adapter() -> None:
    """Replay runner consumes the adapter completely."""

    data = make_market_data(100)

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter,
    )

    runner.run()

    assert adapter.remaining_candles == 0
    assert not adapter.has_next()


def test_runner_preserves_report_generation() -> None:
    """Causal integration does not break paper-trading reporting."""

    data = make_market_data(3000)

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter,
    )

    runner.run()

    report = runner.report

    assert report is not None


def test_empty_replay_does_not_create_context() -> None:
    """An empty replay returns without creating strategy context."""

    data = make_market_data(1)

    adapter = ReplayMarketDataAdapter(data)

    # Consume the only candle before creating the runner.
    adapter.next_candle()

    runner = PaperTradingReplayRunner(
        adapter=adapter,
    )

    runner.run()

    assert runner.strategy_context is None
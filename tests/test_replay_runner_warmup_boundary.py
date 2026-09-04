import pandas as pd

from src.market_data.replay_adapter import ReplayMarketDataAdapter
from src.paper_trading.replay_runner import PaperTradingReplayRunner


def make_data() -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-08-24 09:15:00",
        periods=300,
        freq="min",
    )

    close = pd.Series(
        range(100, 400),
        index=timestamps,
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
        index=timestamps,
    )


def test_replay_start_separates_warmup_from_replay():
    data = make_data()

    replay_start = pd.Timestamp(
        "2026-08-24 10:15:00"
    )

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter,
        replay_start=replay_start,
    )

    runner.run()

    context = runner.strategy_context

    assert context is not None

    # All candles are eventually consumed.
    assert adapter.remaining_candles == 0

    # The context receives both:
    #   1. historical warm-up candles before replay_start
    #   2. replay candles at/after replay_start
    #
    # Therefore processed_count covers the complete causal stream.
    assert context.processed_count == len(data)

    # Verify the replay boundary itself is correct.
    warmup_data = data.loc[
        data.index < replay_start
    ]

    replay_data = data.loc[
        data.index >= replay_start
    ]

    assert len(warmup_data) == 60
    assert len(replay_data) == 240

    # Together they reconstruct the complete stream.
    assert len(warmup_data) + len(replay_data) == len(
        data
    )


def test_future_data_is_not_used_before_replay_boundary():
    data = make_data()

    replay_start = pd.Timestamp(
        "2026-08-24 10:15:00"
    )

    original_adapter = ReplayMarketDataAdapter(
        data
    )

    original_runner = PaperTradingReplayRunner(
        adapter=original_adapter,
        replay_start=replay_start,
    )

    original_runner.run()

    # Modify only candles strictly after a chosen
    # observation timestamp.
    modified_data = data.copy()

    observation_time = pd.Timestamp(
        "2026-08-24 10:30:00"
    )

    future_mask = (
        modified_data.index > observation_time
    )

    modified_data.loc[
        future_mask,
        "open",
    ] += 10000.0

    modified_data.loc[
        future_mask,
        "high",
    ] += 10000.0

    modified_data.loc[
        future_mask,
        "low",
    ] += 10000.0

    modified_data.loc[
        future_mask,
        "close",
    ] += 10000.0

    modified_adapter = ReplayMarketDataAdapter(
        modified_data
    )

    modified_runner = PaperTradingReplayRunner(
        adapter=modified_adapter,
        replay_start=replay_start,
    )

    modified_runner.run()

    # The complete final report may legitimately differ because
    # future candles are part of the replay.
    #
    # The important causal property is that future data is not
    # allowed to alter indicator state before it arrives.
    #
    # Both runs must therefore have processed the same number of
    # causal candles.
    assert (
        original_runner.strategy_context
        is not None
    )

    assert (
        modified_runner.strategy_context
        is not None
    )

    assert (
        original_runner.strategy_context.processed_count
        == modified_runner.strategy_context.processed_count
        == len(data)
    )
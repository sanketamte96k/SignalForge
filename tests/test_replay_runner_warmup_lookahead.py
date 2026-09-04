import pandas as pd

from src.paper_trading.replay_runner import PaperTradingReplayRunner


def make_replay_data(future_price_shift: float = 0.0) -> pd.DataFrame:
    """Create deterministic 1-minute replay data."""

    timestamps = pd.date_range(
        "2024-01-02 09:15:00",
        periods=80,
        freq="min",
    )

    prices = []

    for index in range(len(timestamps)):
        price = 100.0 + index * 0.25

        # Modify only future candles after the observation window.
        if index >= 60:
            price += future_price_shift

        prices.append(price)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": [price + 1.0 for price in prices],
            "low": [price - 1.0 for price in prices],
            "close": prices,
            "volume": [1000.0] * len(prices),
        }
    ).set_index("timestamp")


def run_replay(data: pd.DataFrame):
    """Run the paper replay and return its engine."""

    runner = PaperTradingReplayRunner(
        adapter_data=data,
        starting_capital=100000.0,
        quantity=1,
    )

    return runner.run()


def test_future_replay_data_cannot_change_earlier_replay_results():
    """Future candles must not change earlier strategy results."""

    base_data = make_replay_data(
        future_price_shift=0.0,
    )

    modified_data = make_replay_data(
        future_price_shift=500.0,
    )

    base_engine = run_replay(base_data)
    modified_engine = run_replay(modified_data)

    assert base_engine.trade_count == modified_engine.trade_count
    assert base_engine.realized_pnl == modified_engine.realized_pnl
    assert (
        base_engine.total_transaction_cost
        == modified_engine.total_transaction_cost
    )
    assert base_engine.ending_equity == modified_engine.ending_equity


def test_replay_runner_processes_candles_sequentially():
    """Replay must consume every source candle exactly once."""

    data = make_replay_data()

    runner = PaperTradingReplayRunner(
        adapter_data=data,
        starting_capital=100000.0,
        quantity=1,
    )

    runner.run()

    assert runner.adapter.remaining_candles == 0

    assert runner.strategy_context is not None

    # All 80 candles are inside the trading session.
    assert runner.strategy_context.processed_count == 80
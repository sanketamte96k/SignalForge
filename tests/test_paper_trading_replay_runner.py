import pandas as pd
import pytest

from src.market_data.replay_adapter import ReplayMarketDataAdapter
from src.paper_trading.replay_runner import PaperTradingReplayRunner


def make_data(
    rows: int = 500,
    start: str = "2023-01-02 09:15:00",
) -> pd.DataFrame:
    index = pd.date_range(
        start,
        periods=rows,
        freq="min",
    )

    close = [100.0 + i for i in range(rows)]

    return pd.DataFrame(
        {
            "open": close,
            "high": [price + 1.0 for price in close],
            "low": [price - 1.0 for price in close],
            "close": close,
            "volume": [1000.0] * rows,
        },
        index=index,
    )


def test_replay_runner_requires_replay_adapter():
    with pytest.raises(
        TypeError,
        match="adapter must be a ReplayMarketDataAdapter",
    ):
        PaperTradingReplayRunner(adapter=object())


def test_replay_runner_initializes_with_consumed_adapter():
    data = make_data(rows=1)

    adapter = ReplayMarketDataAdapter(data)

    adapter.next_candle()

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    result = runner.run()

    assert result is runner.engine
    assert runner.report.trade_count == 0


def test_replay_runner_consumes_all_candles():
    data = make_data()

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    assert adapter.has_next() is False
    assert adapter.remaining_candles == 0


def test_replay_runner_returns_engine():
    data = make_data()

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    result = runner.run()

    assert result is runner.engine


def test_replay_runner_report_is_available():
    data = make_data()

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    report = runner.report

    assert report.starting_capital == 100000.0
    assert report.trade_count >= 0
    assert report.ending_equity >= 0


def test_replay_runner_does_not_leave_position_open():
    data = make_data()

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    assert runner.engine.state.has_position is False


def test_replay_runner_is_deterministic():
    data = make_data()

    adapter_one = ReplayMarketDataAdapter(data)

    runner_one = PaperTradingReplayRunner(
        adapter=adapter_one
    )

    result_one = runner_one.run()

    adapter_two = ReplayMarketDataAdapter(data)

    runner_two = PaperTradingReplayRunner(
        adapter=adapter_two
    )

    result_two = runner_two.run()

    report_one = runner_one.report
    report_two = runner_two.report

    assert (
        report_one.trade_count
        == report_two.trade_count
    )

    assert (
        report_one.realized_pnl
        == report_two.realized_pnl
    )

    assert (
        report_one.total_transaction_cost
        == report_two.total_transaction_cost
    )

    assert (
        result_one.state.completed_trades
        == result_two.state.completed_trades
    )


def test_replay_runner_preserves_adapter_data():
    data = make_data()

    original = data.copy(deep=True)

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    pd.testing.assert_frame_equal(
        adapter.data,
        original,
    )


def test_replay_runner_handles_session_boundary():
    first_session = make_data(
        rows=2,
        start="2023-01-02 15:29:00",
    )

    second_session = make_data(
        rows=500,
        start="2023-01-03 09:15:00",
    )

    data = pd.concat(
        [
            first_session,
            second_session,
        ]
    )

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    assert adapter.has_next() is False
    assert runner.engine.state.has_position is False


def test_replay_runner_handles_post_market_data():
    session_data = make_data(
        rows=500,
        start="2023-01-02 09:15:00",
    )

    post_market = make_data(
        rows=2,
        start="2023-01-02 15:31:00",
    )

    data = pd.concat(
        [
            session_data,
            post_market,
        ]
    )

    adapter = ReplayMarketDataAdapter(data)

    runner = PaperTradingReplayRunner(
        adapter=adapter
    )

    runner.run()

    assert adapter.has_next() is False
    assert runner.engine.state.has_position is False
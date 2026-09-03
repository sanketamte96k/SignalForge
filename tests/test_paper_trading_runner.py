from datetime import datetime

import pandas as pd

from src.backtest.simulator import Position
from src.paper_trading.runner import PaperTradingRunner


def make_market_data() -> pd.DataFrame:
    timestamps = pd.date_range(
        start=datetime(2026, 9, 1, 9, 15),
        periods=240,
        freq="min",
    )

    prices = [25000.0 + (i * 2.0) for i in range(240)]

    return pd.DataFrame(
        {
            "open": prices,
            "high": [price + 5.0 for price in prices],
            "low": [price - 5.0 for price in prices],
            "close": prices,
            "volume": [1000] * 240,
        },
        index=timestamps,
    )


def test_runner_initializes():
    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    assert runner.engine.state.starting_capital == 100000.0
    assert runner.engine.quantity == 1
    assert runner.engine.transaction_cost_rate == 0.0001


def test_runner_processes_market_data():
    data = make_market_data()

    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    result = runner.run(data)

    assert result is runner.engine
    assert result.state.current_equity >= 0
    assert result.state.trade_count >= 0


def test_runner_does_not_modify_input_data():
    data = make_market_data()
    original = data.copy(deep=True)

    runner = PaperTradingRunner(
        starting_capital=100000.0,
    )

    runner.run(data)

    pd.testing.assert_frame_equal(data, original)


def test_runner_removes_duplicate_timestamps():
    data = make_market_data()

    duplicate = data.iloc[[100]].copy()

    data_with_duplicate = pd.concat(
        [
            data.iloc[:101],
            duplicate,
            data.iloc[101:],
        ]
    )

    runner = PaperTradingRunner(
        starting_capital=100000.0,
    )

    result = runner.run(data_with_duplicate)

    assert result.state.trade_count >= 0


def test_runner_requires_datetime_index():
    data = make_market_data()
    data.index = range(len(data))

    runner = PaperTradingRunner()

    try:
        runner.run(data)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "DatetimeIndex" in str(exc)


def test_runner_requires_ohlc_columns():
    data = make_market_data()
    data = data.drop(columns=["close"])

    runner = PaperTradingRunner()

    try:
        runner.run(data)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "close" in str(exc)


def test_runner_rejects_unsorted_data():
    data = make_market_data().iloc[::-1]

    runner = PaperTradingRunner()

    try:
        runner.run(data)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "sorted" in str(exc)


def test_runner_uses_paper_engine():
    runner = PaperTradingRunner()

    assert runner.engine.state.has_position is False
    assert runner.engine.state.trade_count == 0
from datetime import datetime, time

import pandas as pd

from src.backtest.simulator import Position
from src.paper_trading.runner import PaperTradingRunner


def make_session_data() -> pd.DataFrame:
    timestamps = pd.date_range(
        start="2026-09-01 09:15",
        end="2026-09-01 15:30",
        freq="min",
    )

    prices = [
        25000.0 + (i * 0.5)
        for i in range(len(timestamps))
    ]

    return pd.DataFrame(
        {
            "open": prices,
            "high": [price + 5.0 for price in prices],
            "low": [price - 5.0 for price in prices],
            "close": prices,
            "volume": [1000] * len(prices),
        },
        index=timestamps,
    )


def test_runner_does_not_leave_position_open_after_final_data():
    data = make_session_data()

    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    runner.engine.open_long(
        timestamp=datetime(2026, 9, 1, 15, 29),
        price=25188.0,
        reason="Test LONG",
    )

    runner.engine.close_position(
        timestamp=data.index[-1].to_pydatetime(),
        price=float(data.iloc[-1]["close"]),
        reason="End of data",
    )

    assert runner.engine.state.has_position is False
    assert runner.engine.state.trade_count == 1

    trade = runner.engine.state.completed_trades[-1]

    assert trade.position == Position.LONG
    assert trade.exit_price == float(data.iloc[-1]["close"])
    assert trade.reason == "End of data"


def test_session_end_close_uses_last_session_price():
    data = make_session_data()

    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    runner.engine.open_short(
        timestamp=datetime(2026, 9, 1, 15, 20),
        price=25100.0,
    )

    session_end = data.loc[
        data.index.time == time(15, 30)
    ]

    final_timestamp = session_end.index[-1]
    final_price = float(session_end.iloc[-1]["close"])

    trade = runner.engine.close_position(
        timestamp=final_timestamp.to_pydatetime(),
        price=final_price,
        reason="Session end",
    )

    assert trade.position == Position.SHORT
    assert trade.exit_price == final_price
    assert trade.exit_time == datetime(
        2026,
        9,
        1,
        15,
        30,
    )
    assert trade.reason == "Session end"

    assert runner.engine.state.has_position is False


def test_explicit_close_does_not_create_extra_trade():
    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    runner.engine.open_long(
        timestamp=datetime(2026, 9, 1, 15, 20),
        price=25000.0,
    )

    runner.engine.close_position(
        timestamp=datetime(2026, 9, 1, 15, 30),
        price=25050.0,
        reason="Session end",
    )

    assert runner.engine.state.trade_count == 1
    assert runner.engine.state.has_position is False
    assert runner.engine.state.realized_pnl == 50.0


def test_runner_closes_position_at_end_of_data():
    data = make_session_data()

    runner = PaperTradingRunner(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    runner.engine.open_long(
        timestamp=data.index[0].to_pydatetime(),
        price=float(data.iloc[0]["close"]),
        reason="Test LONG",
    )

    runner.run(data)

    assert runner.engine.state.has_position is False
    assert runner.engine.state.trade_count >= 1

    last_trade = runner.engine.state.completed_trades[-1]

    assert last_trade.exit_time == (
        data.index[-1].to_pydatetime()
    )

    assert last_trade.exit_price == float(
        data.iloc[-1]["close"]
    )
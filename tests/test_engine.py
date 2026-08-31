import pandas as pd
import pytest

from src.backtest.engine import (
    BacktestResult,
    run_backtest,
)
from src.backtest.simulator import Position


def make_data():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=6,
        freq="min",
    )

    return pd.DataFrame(
        {
            "close": [
                100,
                105,
                110,
                105,
                100,
                95,
            ]
        },
        index=index,
    )


def test_returns_backtest_result():
    data = make_data()

    def no_signal(row, previous_row):
        return None

    result = run_backtest(
        data=data,
        signal_function=no_signal,
        initial_capital=100000,
    )

    assert isinstance(
        result,
        BacktestResult,
    )


def test_no_signals_produce_no_trades():
    data = make_data()

    def no_signal(row, previous_row):
        return None

    result = run_backtest(
        data=data,
        signal_function=no_signal,
        initial_capital=100000,
    )

    assert result.trades == []
    assert result.metrics.total_trades == 0
    assert result.portfolio.equity == 100000


def test_long_position_is_closed_at_end():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.position == Position.LONG
    assert trade.entry_price == 100
    assert trade.exit_price == 95
    assert trade.net_pnl == -5


def test_short_position_is_closed_at_end():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.SHORT

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.position == Position.SHORT
    assert trade.entry_price == 100
    assert trade.exit_price == 95
    assert trade.net_pnl == 5


def test_opposite_signal_closes_and_reverses():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        if row.name == data.index[3]:
            return Position.SHORT

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
    )

    assert len(result.trades) == 2

    first_trade = result.trades[0]
    second_trade = result.trades[1]

    assert first_trade.position == Position.LONG
    assert first_trade.entry_price == 100
    assert first_trade.exit_price == 105

    assert second_trade.position == Position.SHORT
    assert second_trade.entry_price == 105
    assert second_trade.exit_price == 95


def test_same_signal_does_not_create_new_trade():
    data = make_data()

    def signal(row, previous_row):
        if row.name in (
            data.index[0],
            data.index[1],
            data.index[2],
        ):
            return Position.LONG

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
    )

    assert len(result.trades) == 1


def test_quantity_is_used():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
        quantity=10,
    )

    assert result.trades[0].net_pnl == -50


def test_transaction_cost_is_passed_to_trade():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
        transaction_cost_rate=0.001,
    )

    trade = result.trades[0]

    assert trade.transaction_cost > 0
    assert trade.net_pnl < trade.gross_pnl


def test_metrics_are_generated():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    result = run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
    )

    assert result.metrics.total_trades == 1
    assert (
        result.metrics.total_pnl
        == result.portfolio.total_pnl
    )


def test_data_must_be_dataframe():
    with pytest.raises(TypeError):
        run_backtest(
            data=[100, 101],
            signal_function=lambda row, previous: None,
            initial_capital=100000,
        )


def test_data_cannot_be_empty():
    data = pd.DataFrame(
        {"close": []},
        index=pd.DatetimeIndex([]),
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            signal_function=lambda row, previous: None,
            initial_capital=100000,
        )


def test_close_column_is_required():
    data = pd.DataFrame(
        {
            "open": [100, 101],
        },
        index=pd.date_range(
            "2026-08-31",
            periods=2,
            freq="min",
        ),
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            signal_function=lambda row, previous: None,
            initial_capital=100000,
        )


def test_signal_function_must_be_callable():
    data = make_data()

    with pytest.raises(TypeError):
        run_backtest(
            data=data,
            signal_function="invalid",
            initial_capital=100000,
        )


def test_signal_function_must_return_position_or_none():
    data = make_data()

    def invalid_signal(row, previous_row):
        return "LONG"

    with pytest.raises(TypeError):
        run_backtest(
            data=data,
            signal_function=invalid_signal,
            initial_capital=100000,
        )


def test_invalid_initial_capital():
    data = make_data()

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            signal_function=lambda row, previous: None,
            initial_capital=0,
        )


def test_invalid_quantity():
    data = make_data()

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            signal_function=lambda row, previous: None,
            initial_capital=100000,
            quantity=0,
        )
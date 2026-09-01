import pandas as pd
import pytest

from src.backtest.engine import (
    BacktestResult,
    run_backtest,
)
from src.backtest.simulator import (
    Position,
)


# ============================================================
# BASIC BACKTEST TESTS
# ============================================================

def make_data():
    index = pd.to_datetime(
        [
            "2026-08-31 09:15",
            "2026-08-31 09:16",
            "2026-08-31 09:17",
            "2026-08-31 09:18",
        ]
    )

    return pd.DataFrame(
        {
            "close": [
                100.0,
                110.0,
                105.0,
                115.0,
            ]
        },
        index=index,
    )


def test_run_backtest_returns_result():
    data = make_data()

    signals = [
        None,
        Position.LONG,
        Position.LONG,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert isinstance(
        result,
        BacktestResult,
    )


def test_no_signal_creates_no_trades():
    data = make_data()

    def signal_function(row, previous):
        return None

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 0
    assert result.portfolio.equity == 100000


# ============================================================
# POSITION TESTS
# ============================================================

def test_long_position_closes_on_opposite_signal():
    data = make_data()

    signals = [
        Position.LONG,
        Position.LONG,
        Position.SHORT,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 2

    first_trade = result.trades[0]

    assert first_trade.position == Position.LONG
    assert first_trade.entry_price == 100.0
    assert first_trade.exit_price == 105.0


def test_short_position_closes_on_opposite_signal():
    data = make_data()

    signals = [
        Position.SHORT,
        Position.SHORT,
        Position.LONG,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 2

    first_trade = result.trades[0]

    assert first_trade.position == Position.SHORT
    assert first_trade.entry_price == 100.0
    assert first_trade.exit_price == 105.0


def test_same_signal_does_not_create_extra_trade():
    data = make_data()

    signals = [
        Position.LONG,
        Position.LONG,
        Position.LONG,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.entry_price == 100.0
    assert trade.exit_price == 115.0


def test_open_position_is_closed_at_final_candle():
    data = make_data()

    signals = [
        Position.LONG,
        None,
        None,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.entry_price == 100.0
    assert trade.exit_price == 115.0
    assert trade.exit_time == data.index[-1]


def test_opposite_signal_reverses_position():
    data = make_data()

    signals = [
        Position.LONG,
        Position.SHORT,
        None,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 2

    assert result.trades[0].position == Position.LONG
    assert result.trades[1].position == Position.SHORT

    assert result.trades[0].exit_price == 110.0
    assert result.trades[1].entry_price == 110.0


# ============================================================
# TRANSACTION COST TEST
# ============================================================

def test_transaction_cost_is_applied():
    data = make_data()

    signals = [
        Position.LONG,
        None,
        None,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
        transaction_cost_rate=0.001,
    )

    trade = result.trades[0]

    assert trade.gross_pnl == 15.0
    assert trade.transaction_cost > 0
    assert trade.net_pnl < trade.gross_pnl


# ============================================================
# DETERMINISM
# ============================================================

def test_backtest_is_deterministic():
    data = make_data()

    def signal_function_1(row, previous):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    def signal_function_2(row, previous):
        if row.name == data.index[0]:
            return Position.LONG

        return None

    result_1 = run_backtest(
        data=data,
        signal_function=signal_function_1,
        initial_capital=100000,
    )

    result_2 = run_backtest(
        data=data,
        signal_function=signal_function_2,
        initial_capital=100000,
    )

    assert len(result_1.trades) == len(
        result_2.trades
    )

    assert (
        result_1.portfolio.equity
        == result_2.portfolio.equity
    )


# ============================================================
# VALIDATION
# ============================================================

def test_invalid_data_is_rejected():
    data = pd.DataFrame(
        {
            "close": [100.0, 101.0],
        }
    )

    def signal_function(row, previous):
        return None

    with pytest.raises(TypeError):
        run_backtest(
            data=data,
            signal_function=signal_function,
            initial_capital=100000,
        )


# ============================================================
# SESSION BOUNDARY TESTS
# ============================================================

def test_position_is_closed_at_market_session_boundary():
    data = pd.DataFrame(
        {
            "close": [
                100.0,
                110.0,
                120.0,
                90.0,
            ]
        },
        index=pd.to_datetime(
            [
                "2026-08-31 15:28:00",
                "2026-08-31 15:29:00",
                "2026-09-01 09:15:00",
                "2026-09-01 09:16:00",
            ]
        ),
    )

    signals = [
        Position.LONG,
        Position.LONG,
        None,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.position == Position.LONG
    assert trade.entry_price == 100.0
    assert trade.exit_price == 110.0
    assert trade.exit_time == pd.Timestamp(
        "2026-08-31 15:29:00"
    )


def test_position_does_not_carry_into_next_session():
    data = pd.DataFrame(
        {
            "close": [
                100.0,
                110.0,
                90.0,
            ]
        },
        index=pd.to_datetime(
            [
                "2026-08-31 15:29:00",
                "2026-09-01 09:15:00",
                "2026-09-01 09:16:00",
            ]
        ),
    )

    signals = [
        Position.LONG,
        None,
        None,
    ]

    def signal_function(row, previous):
        return signals.pop(0)

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=100000,
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.position == Position.LONG
    assert trade.entry_price == 100.0
    assert trade.exit_price == 100.0
    assert trade.exit_time == pd.Timestamp(
        "2026-08-31 15:29:00"
    )
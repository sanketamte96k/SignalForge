import pytest

from src.backtest.simulator import (
    Position,
    Trade,
    simulate_trade,
)


def test_profitable_long_trade():
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=110,
        quantity=1,
    )

    assert isinstance(trade, Trade)
    assert trade.gross_pnl == 10
    assert trade.net_pnl == 10
    assert trade.return_pct == 10


def test_losing_long_trade():
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=90,
        quantity=1,
    )

    assert trade.gross_pnl == -10
    assert trade.net_pnl == -10
    assert trade.return_pct == -10


def test_profitable_short_trade():
    trade = simulate_trade(
        position=Position.SHORT,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=90,
        quantity=1,
    )

    assert trade.gross_pnl == 10
    assert trade.net_pnl == 10
    assert trade.return_pct == 10


def test_losing_short_trade():
    trade = simulate_trade(
        position=Position.SHORT,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=110,
        quantity=1,
    )

    assert trade.gross_pnl == -10
    assert trade.net_pnl == -10
    assert trade.return_pct == -10


def test_quantity_scales_pnl():
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=110,
        quantity=10,
    )

    assert trade.gross_pnl == 100
    assert trade.net_pnl == 100


def test_transaction_cost_reduces_profit():
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=110,
        quantity=1,
        transaction_cost_rate=0.001,
    )

    assert trade.gross_pnl == 10
    assert trade.transaction_cost == pytest.approx(0.21)
    assert trade.net_pnl == pytest.approx(9.79)


def test_transaction_cost_can_turn_small_profit_into_loss():
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=100.05,
        quantity=1,
        transaction_cost_rate=0.001,
    )

    assert trade.net_pnl < 0


def test_zero_transaction_cost():
    trade = simulate_trade(
        position=Position.SHORT,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100,
        exit_price=90,
        quantity=2,
        transaction_cost_rate=0,
    )

    assert trade.transaction_cost == 0
    assert trade.net_pnl == 20


def test_invalid_position():
    with pytest.raises(TypeError):
        simulate_trade(
            position="LONG",
            entry_time="09:15",
            exit_time="09:30",
            entry_price=100,
            exit_price=110,
        )


def test_invalid_entry_price():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=0,
            exit_price=110,
        )


def test_negative_entry_price():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=-100,
            exit_price=110,
        )


def test_invalid_exit_price():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=100,
            exit_price=0,
        )


def test_invalid_quantity():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=100,
            exit_price=110,
            quantity=0,
        )


def test_negative_quantity():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=100,
            exit_price=110,
            quantity=-1,
        )


def test_invalid_transaction_cost():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time="09:30",
            entry_price=100,
            exit_price=110,
            transaction_cost_rate=-0.01,
        )


def test_none_entry_time():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time=None,
            exit_time="09:30",
            entry_price=100,
            exit_price=110,
        )


def test_none_exit_time():
    with pytest.raises(ValueError):
        simulate_trade(
            position=Position.LONG,
            entry_time="09:15",
            exit_time=None,
            entry_price=100,
            exit_price=110,
        )
from datetime import datetime

from src.backtest.simulator import Position
from src.paper_trading.models import (
    PaperOrder,
    PaperPosition,
    PaperTrade,
    PaperTradingState,
)


def test_paper_order_creation():
    timestamp = datetime(2026, 9, 1, 9, 30)

    order = PaperOrder(
        timestamp=timestamp,
        position=Position.LONG,
        price=25000.0,
        quantity=1,
        reason="Test signal",
    )

    assert order.position == Position.LONG
    assert order.price == 25000.0
    assert order.quantity == 1


def test_paper_position_direction():
    timestamp = datetime(2026, 9, 1, 9, 30)

    position = PaperPosition(
        position=Position.LONG,
        entry_price=25000.0,
        entry_time=timestamp,
        quantity=1,
    )

    assert position.is_long
    assert not position.is_short


def test_long_trade_return():
    trade = PaperTrade(
        position=Position.LONG,
        entry_price=100.0,
        exit_price=110.0,
        quantity=1,
        entry_time=datetime(2026, 9, 1, 9, 30),
        exit_time=datetime(2026, 9, 1, 10, 30),
        gross_pnl=10.0,
        transaction_cost=1.0,
        net_pnl=9.0,
    )

    assert trade.return_pct == 10.0


def test_short_trade_return():
    trade = PaperTrade(
        position=Position.SHORT,
        entry_price=110.0,
        exit_price=100.0,
        quantity=1,
        entry_time=datetime(2026, 9, 1, 9, 30),
        exit_time=datetime(2026, 9, 1, 10, 30),
        gross_pnl=10.0,
        transaction_cost=1.0,
        net_pnl=9.0,
    )

    assert round(trade.return_pct, 2) == 9.09


def test_initial_paper_state():
    state = PaperTradingState(
        starting_capital=100000.0,
    )

    assert state.current_equity == 100000.0
    assert state.trade_count == 0
    assert not state.has_position


def test_paper_state_with_position():
    position = PaperPosition(
        position=Position.LONG,
        entry_price=25000.0,
        entry_time=datetime(2026, 9, 1, 9, 30),
        quantity=1,
    )

    state = PaperTradingState(
        starting_capital=100000.0,
        open_position=position,
    )

    assert state.has_position
    assert state.open_position == position
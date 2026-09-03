from datetime import datetime

import pytest

from src.backtest.simulator import Position
from src.paper_trading.engine import PaperTradingEngine


def test_open_long():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=2,
        transaction_cost_rate=0.0001,
    )

    order = engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
        reason="LONG signal",
    )

    assert order.position == Position.LONG
    assert order.price == 25000.0
    assert order.quantity == 2
    assert order.reason == "LONG signal"

    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.LONG
    assert engine.state.open_position.entry_price == 25000.0
    assert engine.state.open_position.quantity == 2


def test_open_short():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    order = engine.open_short(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=25000.0,
        reason="SHORT signal",
    )

    assert order.position == Position.SHORT
    assert order.price == 25000.0
    assert order.quantity == 1
    assert order.reason == "SHORT signal"

    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.SHORT
    assert engine.state.open_position.entry_price == 25000.0


def test_close_long_calculates_pnl_and_cost():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    trade = engine.close_position(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=25100.0,
        reason="Exit",
    )

    assert trade.position == Position.LONG
    assert trade.entry_price == 25000.0
    assert trade.exit_price == 25100.0
    assert trade.quantity == 1

    assert trade.gross_pnl == pytest.approx(100.0)

    expected_cost = (
        (25000.0 + 25100.0) * 0.0001
    )

    assert trade.transaction_cost == pytest.approx(
        expected_cost
    )

    assert trade.net_pnl == pytest.approx(
        100.0 - expected_cost
    )

    assert trade.reason == "Exit"

    assert engine.state.has_position is False
    assert engine.state.trade_count == 1
    assert engine.state.realized_pnl == pytest.approx(
        trade.net_pnl
    )
    assert engine.state.total_transaction_cost == pytest.approx(
        expected_cost
    )


def test_close_short_calculates_pnl_and_cost():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_short(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    trade = engine.close_position(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=24900.0,
        reason="Exit",
    )

    assert trade.position == Position.SHORT
    assert trade.entry_price == 25000.0
    assert trade.exit_price == 24900.0

    assert trade.gross_pnl == pytest.approx(100.0)

    expected_cost = (
        (25000.0 + 24900.0) * 0.0001
    )

    assert trade.transaction_cost == pytest.approx(
        expected_cost
    )

    assert trade.net_pnl == pytest.approx(
        100.0 - expected_cost
    )

    assert engine.state.has_position is False
    assert engine.state.trade_count == 1


def test_losing_trade_updates_realized_pnl():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    trade = engine.close_position(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=24900.0,
        reason="Stop",
    )

    assert trade.gross_pnl == pytest.approx(-100.0)
    assert trade.net_pnl < -100.0
    assert engine.state.realized_pnl == pytest.approx(
        trade.net_pnl
    )


def test_same_signal_does_nothing():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 0),
        signal=Position.LONG,
        price=25100.0,
        reason="Same LONG",
    )

    assert result is None
    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.LONG
    assert engine.state.open_position.entry_price == 25000.0
    assert engine.state.trade_count == 0


def test_reverse_long_to_short():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 0),
        signal=Position.SHORT,
        price=25100.0,
        reason="Reverse SHORT",
    )

    assert isinstance(result, tuple)

    closed_trade, new_order = result

    assert closed_trade.position == Position.LONG
    assert closed_trade.entry_price == 25000.0
    assert closed_trade.exit_price == 25100.0

    assert new_order.position == Position.SHORT
    assert new_order.price == 25100.0

    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.SHORT
    assert engine.state.open_position.entry_price == 25100.0
    assert engine.state.trade_count == 1


def test_reverse_short_to_long():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_short(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=25000.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 0),
        signal=Position.LONG,
        price=24900.0,
        reason="Reverse LONG",
    )

    assert isinstance(result, tuple)

    closed_trade, new_order = result

    assert closed_trade.position == Position.SHORT
    assert closed_trade.entry_price == 25000.0
    assert closed_trade.exit_price == 24900.0

    assert new_order.position == Position.LONG
    assert new_order.price == 24900.0

    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.LONG
    assert engine.state.open_position.entry_price == 24900.0
    assert engine.state.trade_count == 1


def test_no_position_signal_holds_open_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        transaction_cost_rate=0.0,
    )

    engine.process_signal(
        timestamp=datetime(2026, 9, 1, 9, 30),
        signal=Position.LONG,
        price=100.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 0),
        signal=None,
        price=105.0,
        reason="No trade",
    )

    assert result is None
    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.LONG
    assert engine.state.open_position.entry_price == 100.0
    assert engine.state.trade_count == 0
    assert engine.state.realized_pnl == 0.0
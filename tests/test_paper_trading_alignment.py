from datetime import datetime

from src.backtest.simulator import Position
from src.paper_trading.engine import PaperTradingEngine


def test_none_signal_holds_existing_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    entry_time = datetime(2026, 9, 1, 10, 0)
    hold_time = datetime(2026, 9, 1, 10, 1)

    engine.open_long(
        timestamp=entry_time,
        price=25000.0,
        reason="Test LONG",
    )

    result = engine.process_signal(
        timestamp=hold_time,
        signal=None,
        price=25010.0,
        reason="NO_TRADE",
    )

    assert result is None
    assert engine.state.has_position is True
    assert engine.state.open_position is not None
    assert engine.state.open_position.position == Position.LONG
    assert engine.state.open_position.entry_price == 25000.0
    assert engine.state.trade_count == 0


def test_none_signal_does_not_realize_pnl():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=25000.0,
    )

    engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 1),
        signal=None,
        price=25100.0,
    )

    assert engine.state.realized_pnl == 0.0
    assert engine.state.trade_count == 0
    assert engine.state.has_position is True


def test_opposite_signal_still_reverses_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=25000.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 5),
        signal=Position.SHORT,
        price=25050.0,
        reason="Reverse SHORT",
    )

    assert isinstance(result, tuple)

    closed_trade, new_order = result

    assert closed_trade.position == Position.LONG
    assert new_order.position == Position.SHORT
    assert engine.state.has_position is True
    assert engine.state.open_position.position == Position.SHORT
    assert engine.state.trade_count == 1


def test_explicit_close_still_closes_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 10, 0),
        price=25000.0,
    )

    trade = engine.close_position(
        timestamp=datetime(2026, 9, 1, 15, 29),
        price=25100.0,
        reason="Session end",
    )

    assert trade.position == Position.LONG
    assert trade.exit_price == 25100.0
    assert trade.reason == "Session end"
    assert engine.state.has_position is False
    assert engine.state.trade_count == 1
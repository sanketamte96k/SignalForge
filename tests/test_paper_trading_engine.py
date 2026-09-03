from datetime import datetime

from src.backtest.simulator import Position
from src.paper_trading.engine import PaperTradingEngine


def test_open_long_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
    )

    timestamp = datetime(2026, 9, 1, 9, 30)

    order = engine.open_long(
        timestamp=timestamp,
        price=25000.0,
        reason="BUY signal",
    )

    assert order.position == Position.LONG
    assert order.price == 25000.0
    assert order.quantity == 1
    assert engine.state.has_position
    assert engine.state.open_position.position == Position.LONG


def test_open_short_position():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
    )

    timestamp = datetime(2026, 9, 1, 9, 30)

    order = engine.open_short(
        timestamp=timestamp,
        price=25000.0,
        reason="SELL signal",
    )

    assert order.position == Position.SHORT
    assert order.price == 25000.0
    assert order.quantity == 1
    assert engine.state.has_position
    assert engine.state.open_position.position == Position.SHORT


def test_close_long_position_with_profit():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    entry_time = datetime(2026, 9, 1, 9, 30)
    exit_time = datetime(2026, 9, 1, 10, 30)

    engine.open_long(
        timestamp=entry_time,
        price=100.0,
    )

    trade = engine.close_position(
        timestamp=exit_time,
        price=110.0,
        reason="Exit",
    )

    assert trade.position == Position.LONG
    assert trade.gross_pnl == 10.0
    assert trade.transaction_cost == 0.021
    assert round(trade.net_pnl, 3) == 9.979

    assert not engine.state.has_position
    assert engine.state.trade_count == 1


def test_close_short_position_with_profit():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    entry_time = datetime(2026, 9, 1, 9, 30)
    exit_time = datetime(2026, 9, 1, 10, 30)

    engine.open_short(
        timestamp=entry_time,
        price=110.0,
    )

    trade = engine.close_position(
        timestamp=exit_time,
        price=100.0,
    )

    assert trade.position == Position.SHORT
    assert trade.gross_pnl == 10.0
    assert round(trade.net_pnl, 3) == 9.979

    assert not engine.state.has_position
    assert engine.state.trade_count == 1


def test_long_loss_updates_realized_pnl():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    engine.open_long(
        timestamp=datetime(2026, 9, 1, 9, 30),
        price=100.0,
    )

    trade = engine.close_position(
        timestamp=datetime(2026, 9, 1, 10, 30),
        price=90.0,
    )

    assert trade.net_pnl == -10.0
    assert engine.state.realized_pnl == -10.0
    assert engine.state.current_equity == 99990.0


def test_same_signal_does_nothing():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
    )

    timestamp = datetime(2026, 9, 1, 9, 30)

    engine.process_signal(
        timestamp=timestamp,
        signal=Position.LONG,
        price=100.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 9, 35),
        signal=Position.LONG,
        price=105.0,
    )

    assert result is None
    assert engine.state.trade_count == 0
    assert engine.state.open_position.entry_price == 100.0


def test_long_to_short_reversal():
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
        signal=Position.SHORT,
        price=110.0,
        reason="Trend reversal",
    )

    closed_trade, new_order = result

    assert closed_trade.position == Position.LONG
    assert closed_trade.net_pnl == 10.0

    assert new_order.position == Position.SHORT
    assert new_order.price == 110.0

    assert engine.state.open_position.position == Position.SHORT
    assert engine.state.trade_count == 1


def test_short_to_long_reversal():
    engine = PaperTradingEngine(
        starting_capital=100000.0,
        transaction_cost_rate=0.0,
    )

    engine.process_signal(
        timestamp=datetime(2026, 9, 1, 9, 30),
        signal=Position.SHORT,
        price=100.0,
    )

    result = engine.process_signal(
        timestamp=datetime(2026, 9, 1, 10, 0),
        signal=Position.LONG,
        price=90.0,
    )

    closed_trade, new_order = result

    assert closed_trade.position == Position.SHORT
    assert closed_trade.net_pnl == 10.0

    assert new_order.position == Position.LONG
    assert new_order.price == 90.0

    assert engine.state.open_position.position == Position.LONG
    assert engine.state.trade_count == 1


def test_no_position_signal_closes_open_position():
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

    assert result.position == Position.LONG
    assert result.net_pnl == 5.0
    assert not engine.state.has_position
    assert engine.state.trade_count == 1
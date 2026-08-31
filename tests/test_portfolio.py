import pytest

from src.backtest.portfolio import Portfolio
from src.backtest.simulator import (
    Position,
    Trade,
    simulate_trade,
)


def make_trade(
    entry_price=100,
    exit_price=110,
    quantity=1,
    position=Position.LONG,
):
    return simulate_trade(
        position=position,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
    )


def test_portfolio_initializes_with_capital():
    portfolio = Portfolio(
        initial_capital=100000
    )

    assert portfolio.cash == 100000
    assert portfolio.equity == 100000
    assert portfolio.peak_equity == 100000
    assert portfolio.max_drawdown == 0
    assert portfolio.trade_count == 0
    assert portfolio.total_pnl == 0
    assert portfolio.total_return_pct == 0


def test_profitable_trade_increases_equity():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    portfolio.apply_trade(trade)

    assert portfolio.equity == 100010
    assert portfolio.total_pnl == 10


def test_losing_trade_reduces_equity():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=90,
    )

    portfolio.apply_trade(trade)

    assert portfolio.equity == 99990
    assert portfolio.total_pnl == -10


def test_multiple_trades_accumulate():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade_one = make_trade(
        entry_price=100,
        exit_price=110,
    )

    trade_two = make_trade(
        entry_price=100,
        exit_price=95,
    )

    portfolio.apply_trade(trade_one)
    portfolio.apply_trade(trade_two)

    assert portfolio.trade_count == 2
    assert portfolio.total_pnl == 5
    assert portfolio.equity == 100005


def test_trade_history_is_stored():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade()

    portfolio.apply_trade(trade)

    assert len(portfolio.trades) == 1
    assert portfolio.trades[0] == trade


def test_peak_equity_updates_after_profit():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    portfolio.apply_trade(trade)

    assert portfolio.peak_equity == 100010


def test_peak_equity_does_not_decrease_after_loss():
    portfolio = Portfolio(
        initial_capital=100000
    )

    profitable_trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    losing_trade = make_trade(
        entry_price=100,
        exit_price=90,
    )

    portfolio.apply_trade(
        profitable_trade
    )

    portfolio.apply_trade(
        losing_trade
    )

    assert portfolio.peak_equity == 100010


def test_drawdown_is_calculated():
    portfolio = Portfolio(
        initial_capital=100000
    )

    profitable_trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    losing_trade = make_trade(
        entry_price=100,
        exit_price=90,
        quantity=10,
    )

    portfolio.apply_trade(
        profitable_trade
    )

    portfolio.apply_trade(
        losing_trade
    )

    assert portfolio.equity == 99910
    assert portfolio.max_drawdown == pytest.approx(
        (100010 - 99910) / 100010 * 100
    )


def test_drawdown_does_not_count_new_highs_as_drawdown():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    portfolio.apply_trade(trade)

    assert portfolio.max_drawdown == 0


def test_total_return_percentage():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=110,
        quantity=100,
    )

    portfolio.apply_trade(trade)

    assert portfolio.total_return_pct == pytest.approx(
        1
    )


def test_short_trade_updates_portfolio():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=90,
        quantity=10,
        position=Position.SHORT,
    )

    portfolio.apply_trade(trade)

    assert portfolio.equity == 100100
    assert portfolio.total_pnl == 100


def test_invalid_trade_type():
    portfolio = Portfolio(
        initial_capital=100000
    )

    with pytest.raises(TypeError):
        portfolio.apply_trade(
            "not a trade"
        )


def test_invalid_initial_capital_type():
    with pytest.raises(TypeError):
        Portfolio(
            initial_capital="100000"
        )


def test_zero_initial_capital():
    with pytest.raises(ValueError):
        Portfolio(
            initial_capital=0
        )


def test_negative_initial_capital():
    with pytest.raises(ValueError):
        Portfolio(
            initial_capital=-100000
        )


def test_reset_restores_initial_state():
    portfolio = Portfolio(
        initial_capital=100000
    )

    trade = make_trade(
        entry_price=100,
        exit_price=110,
    )

    portfolio.apply_trade(trade)

    portfolio.reset()

    assert portfolio.cash == 100000
    assert portfolio.equity == 100000
    assert portfolio.peak_equity == 100000
    assert portfolio.max_drawdown == 0
    assert portfolio.trade_count == 0
    assert portfolio.total_pnl == 0
    assert portfolio.total_return_pct == 0


def test_reset_clears_trade_history():
    portfolio = Portfolio(
        initial_capital=100000
    )

    portfolio.apply_trade(
        make_trade()
    )

    assert len(portfolio.trades) == 1

    portfolio.reset()

    assert portfolio.trades == []
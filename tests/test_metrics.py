import math

import pytest

from src.backtest.metrics import (
    PerformanceMetrics,
    calculate_metrics,
)
from src.backtest.simulator import (
    Position,
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


def test_returns_performance_metrics():
    result = calculate_metrics(
        trades=[],
        initial_capital=100000,
    )

    assert isinstance(
        result,
        PerformanceMetrics,
    )


def test_empty_trade_list():
    result = calculate_metrics(
        trades=[],
        initial_capital=100000,
    )

    assert result.total_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.breakeven_trades == 0
    assert result.total_pnl == 0
    assert result.total_return_pct == 0
    assert result.win_rate_pct == 0
    assert result.average_win == 0
    assert result.average_loss == 0
    assert result.profit_factor == 0
    assert result.expectancy == 0


def test_counts_winning_trades():
    trades = [
        make_trade(100, 110),
        make_trade(100, 105),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.winning_trades == 2
    assert result.losing_trades == 0


def test_counts_losing_trades():
    trades = [
        make_trade(100, 90),
        make_trade(100, 95),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.winning_trades == 0
    assert result.losing_trades == 2


def test_counts_breakeven_trades():
    trades = [
        make_trade(100, 100),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.breakeven_trades == 1


def test_total_pnl():
    trades = [
        make_trade(100, 110),
        make_trade(100, 90),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.total_pnl == 0


def test_total_return_percentage():
    trades = [
        make_trade(
            100,
            110,
            quantity=100,
        ),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.total_return_pct == pytest.approx(
        1.0
    )


def test_win_rate():
    trades = [
        make_trade(100, 110),
        make_trade(100, 105),
        make_trade(100, 90),
        make_trade(100, 100),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.win_rate_pct == pytest.approx(
        50.0
    )


def test_average_win():
    trades = [
        make_trade(100, 110),
        make_trade(100, 120),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.average_win == pytest.approx(
        15.0
    )


def test_average_loss():
    trades = [
        make_trade(100, 90),
        make_trade(100, 80),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.average_loss == pytest.approx(
        -15.0
    )


def test_profit_factor():
    trades = [
        make_trade(100, 120),
        make_trade(100, 110),
        make_trade(100, 90),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.profit_factor == pytest.approx(
        3.0
    )


def test_profit_factor_with_no_losses():
    trades = [
        make_trade(100, 110),
        make_trade(100, 120),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert math.isinf(
        result.profit_factor
    )


def test_profit_factor_with_no_wins():
    trades = [
        make_trade(100, 90),
        make_trade(100, 80),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.profit_factor == 0


def test_expectancy():
    trades = [
        make_trade(100, 110),
        make_trade(100, 90),
        make_trade(100, 105),
    ]

    result = calculate_metrics(
        trades=trades,
        initial_capital=100000,
    )

    assert result.expectancy == pytest.approx(
        5 / 3
    )


def test_max_drawdown_is_preserved():
    result = calculate_metrics(
        trades=[],
        initial_capital=100000,
        max_drawdown_pct=7.5,
    )

    assert result.max_drawdown_pct == 7.5


def test_invalid_trade_collection():
    with pytest.raises(TypeError):
        calculate_metrics(
            trades="invalid",
            initial_capital=100000,
        )


def test_invalid_trade_object():
    with pytest.raises(TypeError):
        calculate_metrics(
            trades=["invalid"],
            initial_capital=100000,
        )


def test_invalid_initial_capital_type():
    with pytest.raises(TypeError):
        calculate_metrics(
            trades=[],
            initial_capital="100000",
        )


def test_invalid_initial_capital_value():
    with pytest.raises(ValueError):
        calculate_metrics(
            trades=[],
            initial_capital=0,
        )


def test_negative_initial_capital():
    with pytest.raises(ValueError):
        calculate_metrics(
            trades=[],
            initial_capital=-100000,
        )


def test_invalid_drawdown():
    with pytest.raises(ValueError):
        calculate_metrics(
            trades=[],
            initial_capital=100000,
            max_drawdown_pct=-1,
        )
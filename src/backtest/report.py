"""Backtest reporting and equity-curve utilities for SignalForge."""

from dataclasses import dataclass

import pandas as pd

from src.backtest.engine import BacktestResult


@dataclass(frozen=True)
class BacktestReport:
    """Human-readable summary of a completed backtest."""

    initial_capital: float
    final_equity: float

    total_pnl: float
    total_return_pct: float

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    win_rate_pct: float

    average_win: float
    average_loss: float

    profit_factor: float
    expectancy: float

    max_drawdown_pct: float


def build_equity_curve(
    result: BacktestResult,
) -> pd.Series:
    """
    Build equity after every completed trade.

    The first value represents starting capital.
    Each following value represents equity after
    one completed trade.
    """

    if not isinstance(
        result,
        BacktestResult,
    ):
        raise TypeError(
            "result must be a BacktestResult."
        )

    equity_values = [
        result.portfolio.initial_capital
    ]

    equity = result.portfolio.initial_capital

    for trade in result.trades:
        equity += trade.net_pnl
        equity_values.append(equity)

    return pd.Series(
        equity_values,
        name="equity",
        dtype=float,
    )


def build_drawdown_curve(
    result: BacktestResult,
) -> pd.Series:
    """
    Build percentage drawdown after every completed trade.

    Drawdown is measured from the running peak equity.
    """

    equity_curve = build_equity_curve(
        result
    )

    running_peak = (
        equity_curve.cummax()
    )

    drawdown = (
        (running_peak - equity_curve)
        / running_peak
    ) * 100

    return drawdown.rename(
        "drawdown_pct"
    )


def build_report(
    result: BacktestResult,
) -> BacktestReport:
    """
    Build a report from a completed backtest.

    Parameters
    ----------
    result:
        Completed BacktestResult.

    Returns
    -------
    BacktestReport
        Summary of the backtest.
    """

    if not isinstance(
        result,
        BacktestResult,
    ):
        raise TypeError(
            "result must be a BacktestResult."
        )

    metrics = result.metrics

    return BacktestReport(
        initial_capital=(
            result.portfolio.initial_capital
        ),
        final_equity=(
            result.portfolio.equity
        ),
        total_pnl=metrics.total_pnl,
        total_return_pct=(
            metrics.total_return_pct
        ),
        total_trades=(
            metrics.total_trades
        ),
        winning_trades=(
            metrics.winning_trades
        ),
        losing_trades=(
            metrics.losing_trades
        ),
        breakeven_trades=(
            metrics.breakeven_trades
        ),
        win_rate_pct=(
            metrics.win_rate_pct
        ),
        average_win=(
            metrics.average_win
        ),
        average_loss=(
            metrics.average_loss
        ),
        profit_factor=(
            metrics.profit_factor
        ),
        expectancy=(
            metrics.expectancy
        ),
        max_drawdown_pct=(
            metrics.max_drawdown_pct
        ),
    )
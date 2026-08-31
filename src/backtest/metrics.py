"""Performance metrics for SignalForge backtests."""

from dataclasses import dataclass
import math

from src.backtest.simulator import Trade


@dataclass(frozen=True)
class PerformanceMetrics:
    """Summary statistics for a collection of completed trades."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    total_pnl: float
    total_return_pct: float

    win_rate_pct: float

    average_win: float
    average_loss: float

    profit_factor: float
    expectancy: float

    max_drawdown_pct: float


def _validate_trades(
    trades: list[Trade],
) -> None:
    """Validate the trade collection."""

    if not isinstance(trades, list):
        raise TypeError(
            "trades must be a list."
        )

    for trade in trades:
        if not isinstance(trade, Trade):
            raise TypeError(
                "Every item in trades must be a Trade."
            )


def _validate_initial_capital(
    initial_capital: float,
) -> None:
    """Validate starting capital."""

    if not isinstance(
        initial_capital,
        (int, float),
    ):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if isinstance(initial_capital, bool):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if not math.isfinite(initial_capital):
        raise ValueError(
            "initial_capital must be finite."
        )

    if initial_capital <= 0:
        raise ValueError(
            "initial_capital must be greater than zero."
        )


def _validate_drawdown(
    max_drawdown_pct: float,
) -> None:
    """Validate maximum drawdown."""

    if not isinstance(
        max_drawdown_pct,
        (int, float),
    ):
        raise TypeError(
            "max_drawdown_pct must be numeric."
        )

    if isinstance(
        max_drawdown_pct,
        bool,
    ):
        raise TypeError(
            "max_drawdown_pct must be numeric."
        )

    if max_drawdown_pct < 0:
        raise ValueError(
            "max_drawdown_pct cannot be negative."
        )


def calculate_metrics(
    trades: list[Trade],
    initial_capital: float,
    max_drawdown_pct: float = 0.0,
) -> PerformanceMetrics:
    """
    Calculate performance metrics from completed trades.

    Parameters
    ----------
    trades:
        List of completed Trade objects.

    initial_capital:
        Starting portfolio capital.

    max_drawdown_pct:
        Maximum portfolio drawdown percentage.

    Returns
    -------
    PerformanceMetrics
        Calculated backtest statistics.

    Notes
    -----
    Profit factor is:

        gross profit / absolute gross loss

    If there are no losing trades, profit factor is infinity.

    Expectancy is the average net P&L per trade.
    """

    _validate_trades(trades)

    _validate_initial_capital(
        initial_capital
    )

    _validate_drawdown(
        max_drawdown_pct
    )

    total_trades = len(trades)

    winning_trades = sum(
        1
        for trade in trades
        if trade.net_pnl > 0
    )

    losing_trades = sum(
        1
        for trade in trades
        if trade.net_pnl < 0
    )

    breakeven_trades = sum(
        1
        for trade in trades
        if trade.net_pnl == 0
    )

    total_pnl = sum(
        trade.net_pnl
        for trade in trades
    )

    total_return_pct = (
        total_pnl
        / initial_capital
    ) * 100

    if total_trades > 0:
        win_rate_pct = (
            winning_trades
            / total_trades
        ) * 100
    else:
        win_rate_pct = 0.0

    winning_pnl = [
        trade.net_pnl
        for trade in trades
        if trade.net_pnl > 0
    ]

    losing_pnl = [
        trade.net_pnl
        for trade in trades
        if trade.net_pnl < 0
    ]

    if winning_pnl:
        average_win = (
            sum(winning_pnl)
            / len(winning_pnl)
        )
    else:
        average_win = 0.0

    if losing_pnl:
        average_loss = (
            sum(losing_pnl)
            / len(losing_pnl)
        )
    else:
        average_loss = 0.0

    gross_profit = sum(
        winning_pnl
    )

    gross_loss = abs(
        sum(losing_pnl)
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit
            / gross_loss
        )
    elif gross_profit > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0

    if total_trades > 0:
        expectancy = (
            total_pnl
            / total_trades
        )
    else:
        expectancy = 0.0

    return PerformanceMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=breakeven_trades,
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
        win_rate_pct=win_rate_pct,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown_pct=max_drawdown_pct,
    )
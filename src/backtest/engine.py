"""Orchestration engine for SignalForge backtesting."""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.backtest.metrics import (
    PerformanceMetrics,
    calculate_metrics,
)
from src.backtest.portfolio import Portfolio
from src.backtest.simulator import (
    Position,
    Trade,
    simulate_trade,
)


@dataclass(frozen=True)
class BacktestResult:
    """Complete result returned by the backtest engine."""

    trades: list[Trade]
    portfolio: Portfolio
    metrics: PerformanceMetrics


SignalFunction = Callable[
    [pd.Series, pd.Series],
    Position | None,
]


def _validate_data(
    data: pd.DataFrame,
) -> None:
    """Validate basic backtest input."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if data.empty:
        raise ValueError(
            "data cannot be empty."
        )

    required_columns = {
        "close",
    }

    missing_columns = (
        required_columns
        - set(data.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a "
            "pandas DatetimeIndex."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "data index cannot contain duplicates."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "data index must be sorted."
        )

    if data["close"].isna().any():
        raise ValueError(
            "close cannot contain missing values."
        )


def _validate_capital(
    initial_capital: float,
) -> None:
    """Validate initial capital."""

    if not isinstance(
        initial_capital,
        (int, float),
    ):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if isinstance(
        initial_capital,
        bool,
    ):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if initial_capital <= 0:
        raise ValueError(
            "initial_capital must be greater than zero."
        )


def _validate_quantity(
    quantity: int,
) -> None:
    """Validate trade quantity."""

    if not isinstance(
        quantity,
        int,
    ) or isinstance(quantity, bool):
        raise TypeError(
            "quantity must be an integer."
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than zero."
        )


def run_backtest(
    data: pd.DataFrame,
    signal_function: SignalFunction,
    initial_capital: float,
    quantity: int = 1,
    transaction_cost_rate: float = 0.0,
) -> BacktestResult:
    """
    Run a sequential backtest.

    The signal function is called once per row.

    A signal opens a position using the current candle close.
    The position remains open until an opposite signal appears.

    Parameters
    ----------
    data:
        OHLCV data indexed by timestamps.

    signal_function:
        Function receiving the current row and previous row.
        It must return Position.LONG, Position.SHORT, or None.

    initial_capital:
        Starting account capital.

    quantity:
        Fixed quantity used for each trade.

    transaction_cost_rate:
        Transaction cost rate passed to the trade simulator.

    Returns
    -------
    BacktestResult
        Completed trades, portfolio, and performance metrics.
    """

    _validate_data(data)

    _validate_capital(
        initial_capital
    )

    _validate_quantity(
        quantity
    )

    if not callable(signal_function):
        raise TypeError(
            "signal_function must be callable."
        )

    portfolio = Portfolio(
        initial_capital=initial_capital
    )

    trades: list[Trade] = []

    current_position: Position | None = None
    entry_time: pd.Timestamp | None = None
    entry_price: float | None = None

    for index in range(len(data)):
        row = data.iloc[index]

        if index == 0:
            previous_row = row
        else:
            previous_row = data.iloc[index - 1]

        signal = signal_function(
            row,
            previous_row,
        )

        if signal is not None and not isinstance(
            signal,
            Position,
        ):
            raise TypeError(
                "signal_function must return "
                "Position or None."
            )

        current_time = data.index[index]
        current_price = float(
            row["close"]
        )

        if current_position is None:

            if signal is None:
                continue

            current_position = signal
            entry_time = current_time
            entry_price = current_price

            continue

        if signal is None:
            continue

        if signal == current_position:
            continue

        trade = simulate_trade(
            position=current_position,
            entry_time=entry_time,
            exit_time=current_time,
            entry_price=entry_price,
            exit_price=current_price,
            quantity=quantity,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        )

        portfolio.apply_trade(
            trade
        )

        trades.append(trade)

        current_position = signal
        entry_time = current_time
        entry_price = current_price

    # Close any remaining open position
    # using the final available close.
    if current_position is not None:

        final_time = data.index[-1]
        final_price = float(
            data.iloc[-1]["close"]
        )

        trade = simulate_trade(
            position=current_position,
            entry_time=entry_time,
            exit_time=final_time,
            entry_price=entry_price,
            exit_price=final_price,
            quantity=quantity,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        )

        portfolio.apply_trade(
            trade
        )

        trades.append(trade)

    metrics = calculate_metrics(
        trades=trades,
        initial_capital=initial_capital,
        max_drawdown_pct=(
            portfolio.max_drawdown
        ),
    )

    return BacktestResult(
        trades=trades,
        portfolio=portfolio,
        metrics=metrics,
    )
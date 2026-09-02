"""SignalForge — Strategy-level entry filter backtest.

This script tests candidate entry filters through the REAL
SignalForge backtest engine.

It does NOT modify production strategy files.

Each candidate is evaluated by:
    1. Generating the official multi-timeframe signal.
    2. Applying the candidate entry filter.
    3. Passing that filtered signal into run_backtest().
    4. Comparing the resulting complete trading path against baseline.

This is fundamentally different from simply removing historical
trades after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from src.backtest.engine import (
    BacktestResult,
    run_backtest,
)
from src.backtest.simulator import Position
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    evaluate_timestamp,
    signal_result_to_position,
)


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1

# Same cost used by the official baseline.
TRANSACTION_COST_RATE = 0.0001


# ----------------------------------------------------------------------
# Candidate filters
# ----------------------------------------------------------------------

LONG_RSI_FILTERS = (
    ("No LONG filter", None),
    ("LONG RSI <= 70", 70.0),
    ("LONG RSI <= 75", 75.0),
    ("LONG RSI <= 80", 80.0),
)


LONG_EMA20_FILTERS = (
    ("No LONG EMA20 filter", None),
    ("LONG EMA20 <= 0.20%", 0.20),
    ("LONG EMA20 <= 0.25%", 0.25),
    ("LONG EMA20 <= 0.30%", 0.30),
)


LONG_EMA50_FILTERS = (
    ("No LONG EMA50 filter", None),
    ("LONG EMA50 <= 0.30%", 0.30),
    ("LONG EMA50 <= 0.40%", 0.40),
    ("LONG EMA50 <= 0.50%", 0.50),
)


SHORT_RSI_FILTERS = (
    ("No SHORT filter", None),
    ("SHORT RSI <= 30", 30.0),
    ("SHORT RSI <= 35", 35.0),
    ("SHORT RSI <= 40", 40.0),
    ("SHORT RSI <= 45", 45.0),
)


SHORT_EMA20_FILTERS = (
    ("No SHORT EMA20 filter", None),
    ("SHORT EMA20 <= 0.20%", 0.20),
    ("SHORT EMA20 <= 0.25%", 0.25),
    ("SHORT EMA20 <= 0.30%", 0.30),
)


SHORT_EMA50_FILTERS = (
    ("No SHORT EMA50 filter", None),
    ("SHORT EMA50 <= 0.20%", 0.20),
    ("SHORT EMA50 <= 0.25%", 0.25),
    ("SHORT EMA50 <= 0.30%", 0.30),
    ("SHORT EMA50 <= 0.40%", 0.40),
)


# ----------------------------------------------------------------------
# Filter specification
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FilterSpec:
    """One strategy-level entry filter."""

    name: str

    long_rsi_max: float | None = None
    long_ema20_max: float | None = None
    long_ema50_max: float | None = None

    short_rsi_max: float | None = None
    short_ema20_max: float | None = None
    short_ema50_max: float | None = None


# ----------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ResultRow:
    """Summary of one complete backtest."""

    name: str

    trades: int
    long_trades: int
    short_trades: int

    winning_trades: int
    losing_trades: int

    win_rate: float
    total_pnl: float
    return_pct: float

    average_trade: float
    profit_factor: float
    expectancy: float

    max_drawdown: float


# ----------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------


def load_data() -> pd.DataFrame:
    """Load the historical NIFTY 50 dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    )

    if data.empty:
        raise ValueError(
            "Dataset is empty."
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "Dataset index must be a DatetimeIndex."
        )

    data = data.sort_index()

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(
        required_columns.difference(
            data.columns
        )
    )

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    return data


# ----------------------------------------------------------------------
# Indicator helpers
# ----------------------------------------------------------------------


def latest_completed_5m(
    timestamp: pd.Timestamp,
    timeframe_data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """Return latest completed 5m candle before timestamp."""

    frame = timeframe_data["5m"]

    completed = frame[
        frame.index < timestamp
    ]

    if completed.empty:
        return None

    return completed.iloc[-1]


# ----------------------------------------------------------------------
# Filter evaluation
# ----------------------------------------------------------------------


def passes_filter(
    signal: Position,
    timestamp: pd.Timestamp,
    timeframe_data: dict[str, pd.DataFrame],
    spec: FilterSpec,
) -> bool:
    """Check whether a signal passes the candidate filter."""

    row = latest_completed_5m(
        timestamp,
        timeframe_data,
    )

    if row is None:
        return False

    required = (
        "rsi",
        "ema20",
        "ema50",
    )

    if row[
        list(required)
    ].isna().any():
        return False

    rsi = float(
        row["rsi"]
    )

    ema20 = float(
        row["ema20"]
    )

    ema50 = float(
        row["ema50"]
    )

    # --------------------------------------------------------------
    # LONG
    # --------------------------------------------------------------

    if signal == Position.LONG:

        if (
            spec.long_rsi_max is not None
            and rsi > spec.long_rsi_max
        ):
            return False

        # Distance from EMA20.
        #
        # Example:
        # price 0.23% above EMA20
        # -> distance = +0.23%
        distance_ema20 = (
            (
                float(
                    timeframe_data[
                        "_current_price"
                    ]
                )
                - ema20
            )
            / ema20
            * 100.0
        )

        if (
            spec.long_ema20_max is not None
            and distance_ema20
            > spec.long_ema20_max
        ):
            return False

        # Distance from EMA50.
        distance_ema50 = (
            (
                float(
                    timeframe_data[
                        "_current_price"
                    ]
                )
                - ema50
            )
            / ema50
            * 100.0
        )

        if (
            spec.long_ema50_max is not None
            and distance_ema50
            > spec.long_ema50_max
        ):
            return False

        return True

    # --------------------------------------------------------------
    # SHORT
    # --------------------------------------------------------------

    if signal == Position.SHORT:

        if (
            spec.short_rsi_max is not None
            and rsi > spec.short_rsi_max
        ):
            return False

        distance_ema20 = (
            (
                float(
                    timeframe_data[
                        "_current_price"
                    ]
                )
                - ema20
            )
            / ema20
            * 100.0
        )

        if (
            spec.short_ema20_max is not None
            and distance_ema20
            < -spec.short_ema20_max
        ):
            return False

        distance_ema50 = (
            (
                float(
                    timeframe_data[
                        "_current_price"
                    ]
                )
                - ema50
            )
            / ema50
            * 100.0
        )

        if (
            spec.short_ema50_max is not None
            and distance_ema50
            < -spec.short_ema50_max
        ):
            return False

        return True

    return False


# ----------------------------------------------------------------------
# Signal function factory
# ----------------------------------------------------------------------


def create_filtered_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
    spec: FilterSpec,
) -> Callable:
    """Create a filtered signal function for run_backtest()."""

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series,
    ) -> Position | None:
        """Generate and filter one strategy signal."""

        timestamp = row.name

        if not isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = pd.Timestamp(
                timestamp
            )

        result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        signal = signal_result_to_position(
            result
        )

        if signal is None:
            return None

        # Store current price temporarily so the filter can
        # calculate EMA extension from the actual entry candle.
        timeframe_data[
            "_current_price"
        ] = float(
            row["close"]
        )

        try:
            accepted = passes_filter(
                signal,
                timestamp,
                timeframe_data,
                spec,
            )
        finally:
            del timeframe_data[
                "_current_price"
            ]

        if not accepted:
            return None

        return signal

    return signal_function


# ----------------------------------------------------------------------
# Run one backtest
# ----------------------------------------------------------------------


def run_filtered_backtest(
    data: pd.DataFrame,
    config: StrategyConfig,
    spec: FilterSpec,
) -> BacktestResult:
    """Run a complete strategy-level filtered backtest."""

    signal_function = (
        create_filtered_signal_function(
            data,
            config,
            spec,
        )
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=(
            TRANSACTION_COST_RATE
        ),
    )


# ----------------------------------------------------------------------
# Convert result
# ----------------------------------------------------------------------


def convert_result(
    name: str,
    result: BacktestResult,
) -> ResultRow:
    """Convert BacktestResult into a compact result row."""

    trades = result.trades

    long_trades = sum(
        trade.position == Position.LONG
        for trade in trades
    )

    short_trades = sum(
        trade.position == Position.SHORT
        for trade in trades
    )

    metrics = result.metrics

    trade_count = len(
        trades
    )

    average_trade = (
        metrics.total_pnl
        / trade_count
        if trade_count > 0
        else 0.0
    )

    return ResultRow(
        name=name,
        trades=trade_count,
        long_trades=long_trades,
        short_trades=short_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        win_rate=metrics.win_rate_pct,
        total_pnl=metrics.total_pnl,
        return_pct=metrics.total_return_pct,
        average_trade=average_trade,
        profit_factor=metrics.profit_factor,
        expectancy=metrics.expectancy,
        max_drawdown=metrics.max_drawdown_pct,
    )


# ----------------------------------------------------------------------
# Printing
# ----------------------------------------------------------------------


def print_result(
    result: ResultRow,
) -> None:
    """Print one result row."""

    profit_factor = (
        f"{result.profit_factor:.2f}"
        if result.profit_factor != float("inf")
        else "INF"
    )

    print(
        f"{result.name:<32}"
        f" | Trades={result.trades:>2}"
        f" | L={result.long_trades:>2}"
        f" | S={result.short_trades:>2}"
        f" | Win={result.win_rate:>6.2f}%"
        f" | P&L={result.total_pnl:>9.2f}"
        f" | Avg={result.average_trade:>8.2f}"
        f" | PF={profit_factor:>5}"
        f" | Exp={result.expectancy:>8.2f}"
        f" | DD={result.max_drawdown:>6.2f}%"
    )


# ----------------------------------------------------------------------
# Experiment runner
# ----------------------------------------------------------------------


def run_experiment(
    data: pd.DataFrame,
    config: StrategyConfig,
    spec: FilterSpec,
) -> ResultRow:
    """Run one complete experiment."""

    result = run_filtered_backtest(
        data,
        config,
        spec,
    )

    return convert_result(
        spec.name,
        result,
    )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main() -> None:
    """Run the complete strategy-level filter experiment."""

    print("=" * 100)
    print(
        "SignalForge — Strategy-Level Entry Filter Backtest"
    )
    print("=" * 100)

    data = load_data()

    print()
    print("DATASET")
    print("-" * 100)
    print(
        f"Rows:  {len(data):,}"
    )
    print(
        f"Start: {data.index.min()}"
    )
    print(
        f"End:   {data.index.max()}"
    )

    config = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("BASELINE")
    print("=" * 100)

    baseline_spec = FilterSpec(
        name="BASELINE",
    )

    baseline = run_experiment(
        data,
        config,
        baseline_spec,
    )

    print_result(
        baseline
    )

    # ------------------------------------------------------------------
    # LONG RSI
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("LONG RSI FILTERS")
    print("=" * 100)

    for name, threshold in LONG_RSI_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            long_rsi_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # LONG EMA20
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("LONG EMA20 FILTERS")
    print("=" * 100)

    for name, threshold in LONG_EMA20_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            long_ema20_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # LONG EMA50
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("LONG EMA50 FILTERS")
    print("=" * 100)

    for name, threshold in LONG_EMA50_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            long_ema50_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # SHORT RSI
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("SHORT RSI FILTERS")
    print("=" * 100)

    for name, threshold in SHORT_RSI_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            short_rsi_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # SHORT EMA20
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("SHORT EMA20 FILTERS")
    print("=" * 100)

    for name, threshold in SHORT_EMA20_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            short_ema20_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # SHORT EMA50
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("SHORT EMA50 FILTERS")
    print("=" * 100)

    for name, threshold in SHORT_EMA50_FILTERS[1:]:

        spec = FilterSpec(
            name=name,
            short_ema50_max=threshold,
        )

        result = run_experiment(
            data,
            config,
            spec,
        )

        print_result(
            result
        )

    # ------------------------------------------------------------------
    # Final message
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("EXPERIMENT COMPLETE")
    print("=" * 100)
    print()
    print(
        "These are research experiments only."
    )
    print(
        "No production strategy files were modified."
    )
    print(
        "Do not select a filter from this 20-session sample alone."
    )


if __name__ == "__main__":
    main()
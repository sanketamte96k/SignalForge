from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------
# SignalForge imports
# ---------------------------------------------------------------------

from src.backtest.engine import Position, run_backtest
from src.signals.signal_engine import generate_signal
from src.strategy.backtest_strategy import (
    StrategyConfig,
    _make_cursors,
    calculate_timeframe_indicators,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001


# ---------------------------------------------------------------------
# Load historical data
# ---------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Load and validate the historical 1-minute dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Historical data not found:\n{DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    if "timestamp" not in data.columns:
        raise ValueError(
            "Dataset must contain a 'timestamp' column."
        )

    data = (
        data
        .set_index("timestamp")
        .sort_index()
    )

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    if data.index.has_duplicates:
        raise ValueError(
            "Historical dataset contains duplicate timestamps."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Historical dataset must be chronologically ordered."
        )

    return data


# ---------------------------------------------------------------------
# Frozen baseline strategy configuration
# ---------------------------------------------------------------------

def make_config() -> StrategyConfig:
    """Return the current frozen baseline strategy configuration."""

    return StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )


# ---------------------------------------------------------------------
# Baseline signal function
# ---------------------------------------------------------------------

def create_baseline_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """
    Create the existing baseline signal function.

    Indicator data is calculated over the complete historical
    dataset so indicator state is not artificially reset at
    calendar-year boundaries.
    """

    timeframe_data = calculate_timeframe_indicators(
        data,
        config,
    )

    cursors = _make_cursors(
        timeframe_data,
        config.use_rvol,
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series | None,
    ) -> Position | None:

        timestamp = pd.Timestamp(row.name)

        state_30m = cursors["30m"].update(timestamp)
        state_15m = cursors["15m"].update(timestamp)
        state_10m = cursors["10m"].update(timestamp)
        state_5m = cursors["5m"].update(timestamp)

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        result = generate_signal(
            state_30m,
            state_15m,
            state_10m,
            state_5m,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=config.use_rvol,
        )

        if result.signal.value == "BUY":
            return Position.LONG

        if result.signal.value == "SELL":
            return Position.SHORT

        return None

    return signal_function


# ---------------------------------------------------------------------
# Run complete baseline backtest
# ---------------------------------------------------------------------

def run_baseline_backtest(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Run one chronological backtest over the complete dataset."""

    signal_function = create_baseline_signal_function(
        data,
        config,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


# ---------------------------------------------------------------------
# Calculate metrics for a group of trades
# ---------------------------------------------------------------------

def calculate_trade_metrics(
    trades,
) -> dict:
    """Calculate performance metrics from completed trades."""

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "worst_losing_streak": 0,
        }

    pnl_values = [
        float(trade.net_pnl)
        for trade in trades
    ]

    wins = [
        pnl
        for pnl in pnl_values
        if pnl > 0
    ]

    losses = [
        pnl
        for pnl in pnl_values
        if pnl < 0
    ]

    win_count = len(wins)
    loss_count = len(losses)

    net_pnl = sum(pnl_values)

    win_rate = (
        win_count / len(pnl_values) * 100.0
    )

    gross_profit = sum(wins)

    gross_loss = abs(
        sum(losses)
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    avg_trade = (
        net_pnl / len(pnl_values)
    )

    # -------------------------------------------------------------
    # Drawdown
    # -------------------------------------------------------------

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL

    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    # -------------------------------------------------------------
    # Losing streak
    # -------------------------------------------------------------

    current_losing_streak = 0
    worst_losing_streak = 0

    for pnl in pnl_values:

        equity += pnl

        if equity > peak_equity:
            peak_equity = equity

        drawdown = (
            peak_equity - equity
        )

        drawdown_pct = (
            drawdown / peak_equity * 100.0
            if peak_equity > 0
            else 0.0
        )

        max_drawdown = max(
            max_drawdown,
            drawdown,
        )

        max_drawdown_pct = max(
            max_drawdown_pct,
            drawdown_pct,
        )

        if pnl < 0:
            current_losing_streak += 1

            worst_losing_streak = max(
                worst_losing_streak,
                current_losing_streak,
            )
        else:
            current_losing_streak = 0

    return {
        "trades": len(pnl_values),
        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "avg_trade": avg_trade,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "worst_losing_streak": worst_losing_streak,
    }


# ---------------------------------------------------------------------
# Group trades by exit year
# ---------------------------------------------------------------------

def group_trades_by_exit_year(
    trades,
) -> dict[int, list]:
    """
    Group completed trades by exit year.

    A trade belongs to the year in which it was completed.
    This is important because the backtest itself is executed
    continuously across the complete historical dataset.
    """

    grouped: dict[int, list] = {}

    for trade in trades:

        exit_time = pd.Timestamp(
            trade.exit_time
        )

        year = exit_time.year

        grouped.setdefault(
            year,
            [],
        ).append(trade)

    return grouped


# ---------------------------------------------------------------------
# Print metrics
# ---------------------------------------------------------------------

def print_metrics(
    year: int | str,
    metrics: dict,
) -> None:
    """Print one year's performance metrics."""

    profit_factor = metrics["profit_factor"]

    if profit_factor == float("inf"):
        pf_text = "INF"
    else:
        pf_text = f"{profit_factor:.3f}"

    print(
        f"\n{year}"
    )

    print(
        f"  Trades:              "
        f"{metrics['trades']}"
    )

    print(
        f"  Wins:                "
        f"{metrics['wins']}"
    )

    print(
        f"  Losses:              "
        f"{metrics['losses']}"
    )

    print(
        f"  Win Rate:            "
        f"{metrics['win_rate']:.2f}%"
    )

    print(
        f"  Net P&L:             "
        f"{metrics['net_pnl']:+.2f}"
    )

    print(
        f"  Avg Trade:           "
        f"{metrics['avg_trade']:+.2f}"
    )

    print(
        f"  Profit Factor:       "
        f"{pf_text}"
    )

    print(
        f"  Max Drawdown:        "
        f"{metrics['max_drawdown']:.2f}"
    )

    print(
        f"  Max Drawdown %:      "
        f"{metrics['max_drawdown_pct']:.2f}%"
    )

    print(
        f"  Worst Losing Streak: "
        f"{metrics['worst_losing_streak']}"
    )


# ---------------------------------------------------------------------
# Print yearly summary table
# ---------------------------------------------------------------------

def print_yearly_table(
    yearly_metrics: dict[int, dict],
) -> None:
    """Print a compact year-by-year summary."""

    print("\n" + "=" * 110)
    print("YEAR-BY-YEAR SUMMARY")
    print("=" * 110)

    header = (
        f"{'Year':<8}"
        f"{'Trades':>8}"
        f"{'Wins':>8}"
        f"{'Losses':>8}"
        f"{'Win %':>9}"
        f"{'Net P&L':>14}"
        f"{'Avg Trade':>14}"
        f"{'PF':>10}"
        f"{'Max DD':>14}"
        f"{'DD %':>10}"
        f"{'Lose Streak':>13}"
    )

    print(header)
    print("-" * 110)

    for year in sorted(yearly_metrics):

        metrics = yearly_metrics[year]

        pf = metrics["profit_factor"]

        if pf == float("inf"):
            pf_text = "INF"
        else:
            pf_text = f"{pf:.2f}"

        print(
            f"{year:<8}"
            f"{metrics['trades']:>8}"
            f"{metrics['wins']:>8}"
            f"{metrics['losses']:>8}"
            f"{metrics['win_rate']:>8.2f}%"
            f"{metrics['net_pnl']:>14.2f}"
            f"{metrics['avg_trade']:>14.2f}"
            f"{pf_text:>10}"
            f"{metrics['max_drawdown']:>14.2f}"
            f"{metrics['max_drawdown_pct']:>9.2f}%"
            f"{metrics['worst_losing_streak']:>13}"
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 72)
    print("SIGNALFORGE - YEAR-BY-YEAR PERFORMANCE")
    print("=" * 72)

    print(
        f"\nData: {DATA_PATH}"
    )

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Range: "
        f"{data.index.min()} "
        f"-> "
        f"{data.index.max()}"
    )

    config = make_config()

    print(
        "\nStrategy: FROZEN BASELINE"
    )

    print(
        f"Initial capital: "
        f"{INITIAL_CAPITAL:,.2f}"
    )

    print(
        f"Quantity: "
        f"{QUANTITY}"
    )

    print(
        f"Transaction cost rate: "
        f"{TRANSACTION_COST_RATE}"
    )

    print(
        "\nRunning one continuous chronological backtest..."
    )

    result = run_baseline_backtest(
        data=data,
        config=config,
    )

    print(
        f"Completed trades: "
        f"{len(result.trades):,}"
    )

    # -------------------------------------------------------------
    # Group completed trades by exit year
    # -------------------------------------------------------------

    grouped_trades = group_trades_by_exit_year(
        result.trades
    )

    years = sorted(
        data.index.year.unique()
    )

    yearly_metrics: dict[int, dict] = {}

    for year in years:

        trades = grouped_trades.get(
            year,
            [],
        )

        metrics = calculate_trade_metrics(
            trades
        )

        yearly_metrics[year] = metrics

    # -------------------------------------------------------------
    # Detailed yearly output
    # -------------------------------------------------------------

    for year in years:

        print(
            "\n" + "-" * 72
        )

        print(
            f"YEAR: {year}"
        )

        print(
            "-" * 72
        )

        print_metrics(
            year=year,
            metrics=yearly_metrics[year],
        )

    # -------------------------------------------------------------
    # Summary table
    # -------------------------------------------------------------

    print_yearly_table(
        yearly_metrics
    )

    # -------------------------------------------------------------
    # Overall metrics from the actual complete backtest
    # -------------------------------------------------------------

    overall_metrics = calculate_trade_metrics(
        result.trades
    )

    print(
        "\n" + "=" * 72
    )

    print(
        "OVERALL BASELINE PERFORMANCE"
    )

    print(
        "=" * 72
    )

    print_metrics(
        year="ALL",
        metrics=overall_metrics,
    )

    print(
        "\n" + "=" * 72
    )

    print(
        "YEAR-BY-YEAR ANALYSIS COMPLETE"
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()
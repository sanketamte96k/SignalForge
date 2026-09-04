import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
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
    """Load and validate the complete historical 1-minute dataset."""

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
# Frozen baseline configuration
# ---------------------------------------------------------------------

def make_config() -> StrategyConfig:
    """Return the exact frozen baseline configuration used in 7.1."""

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
    Create the same frozen baseline signal function used by 7.1.

    Indicator data is calculated across the complete historical
    dataset so indicator state is not reset at month boundaries.
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
# Run baseline backtest
# ---------------------------------------------------------------------

def run_baseline_backtest(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Run one continuous chronological backtest."""

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
# Group trades by month
# ---------------------------------------------------------------------

def group_trades_by_month(trades):
    """
    Group completed trades by exit month.

    Exit month is used so every completed trade belongs to exactly
    one reporting month.
    """

    grouped = defaultdict(list)

    for trade in trades:
        exit_time = pd.Timestamp(trade.exit_time)
        month = exit_time.to_period("M")
        grouped[month].append(trade)

    return dict(sorted(grouped.items()))


# ---------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------

def calculate_profit_factor(trades):
    """Calculate profit factor."""

    gross_profit = sum(
        max(float(trade.net_pnl), 0.0)
        for trade in trades
    )

    gross_loss = sum(
        abs(min(float(trade.net_pnl), 0.0))
        for trade in trades
    )

    if gross_loss == 0:
        if gross_profit > 0:
            return float("inf")

        return 0.0

    return gross_profit / gross_loss


def calculate_max_drawdown(trades):
    """
    Calculate local maximum drawdown for a trade group.

    The calculation starts from INITIAL_CAPITAL for the supplied
    group. The overall report separately calculates drawdown across
    the complete chronological trade sequence.
    """

    equity = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_drawdown = 0.0

    for trade in trades:
        equity += float(trade.net_pnl)

        peak = max(
            peak,
            equity,
        )

        drawdown = peak - equity

        max_drawdown = max(
            max_drawdown,
            drawdown,
        )

    max_drawdown_pct = (
        max_drawdown / INITIAL_CAPITAL * 100.0
        if INITIAL_CAPITAL > 0
        else 0.0
    )

    return max_drawdown, max_drawdown_pct


def calculate_worst_losing_streak(trades):
    """Calculate the longest consecutive losing-trade streak."""

    worst = 0
    current = 0

    for trade in trades:
        if float(trade.net_pnl) < 0:
            current += 1
            worst = max(
                worst,
                current,
            )
        else:
            current = 0

    return worst


def calculate_trade_metrics(trades):
    """Calculate performance metrics for a group of trades."""

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "average_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "worst_losing_streak": 0,
        }

    pnl_values = np.array(
        [
            float(trade.net_pnl)
            for trade in trades
        ],
        dtype=float,
    )

    total_trades = len(trades)

    wins = int(
        np.sum(pnl_values > 0)
    )

    losses = int(
        np.sum(pnl_values < 0)
    )

    win_rate = (
        wins / total_trades * 100.0
    )

    net_pnl = float(
        np.sum(pnl_values)
    )

    average_trade = (
        net_pnl / total_trades
    )

    profit_factor = calculate_profit_factor(
        trades
    )

    max_drawdown, max_drawdown_pct = (
        calculate_max_drawdown(
            trades
        )
    )

    worst_losing_streak = (
        calculate_worst_losing_streak(
            trades
        )
    )

    return {
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "average_trade": average_trade,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "worst_losing_streak": worst_losing_streak,
    }


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------

def format_profit_factor(value):
    """Format profit factor."""

    if np.isinf(value):
        return "INF"

    return f"{value:.3f}"


# ---------------------------------------------------------------------
# Monthly report
# ---------------------------------------------------------------------

def print_monthly_report(
    monthly_metrics,
    overall_trades,
):
    """Print the monthly performance analysis."""

    print()
    print("=" * 125)
    print(
        "SIGNALFORGE - PHASE 7.2 "
        "MONTHLY PERFORMANCE ANALYSIS"
    )
    print("=" * 125)

    print()
    print("Strategy: FROZEN BASELINE")
    print(
        "Indicators: "
        "EMA20 / EMA50 / RSI14 / ATR14 / RVOL20"
    )
    print(
        "MTF agreement: "
        "5m + 10m + 15m + 30m"
    )
    print(
        "Baseline thresholds are inherited "
        "directly from SignalForge signal engine."
    )
    print("RVOL enabled: False")
    print(
        f"Initial capital: "
        f"{INITIAL_CAPITAL:,.2f}"
    )
    print(
        f"Quantity: {QUANTITY}"
    )
    print(
        f"Transaction cost rate: "
        f"{TRANSACTION_COST_RATE:.6f}"
    )

    print()
    print("-" * 125)

    print(
        f"{'Month':<10}"
        f"{'Trades':>8}"
        f"{'Wins':>8}"
        f"{'Losses':>8}"
        f"{'Win %':>9}"
        f"{'Net P&L':>14}"
        f"{'Avg Trade':>14}"
        f"{'PF':>9}"
        f"{'Max DD':>14}"
        f"{'DD %':>9}"
        f"{'Lose Streak':>13}"
    )

    print("-" * 125)

    for metrics in monthly_metrics:

        print(
            f"{metrics['month']:<10}"
            f"{metrics['trades']:>8}"
            f"{metrics['wins']:>8}"
            f"{metrics['losses']:>8}"
            f"{metrics['win_rate']:>8.2f}%"
            f"{metrics['net_pnl']:>14.2f}"
            f"{metrics['average_trade']:>14.2f}"
            f"{format_profit_factor(metrics['profit_factor']):>9}"
            f"{metrics['max_drawdown']:>14.2f}"
            f"{metrics['max_drawdown_pct']:>8.2f}%"
            f"{metrics['worst_losing_streak']:>13}"
        )

    print("-" * 125)

    # -------------------------------------------------------------
    # Overall metrics
    # -------------------------------------------------------------

    overall = calculate_trade_metrics(
        overall_trades
    )

    print()
    print("OVERALL")
    print("-" * 125)

    print(
        f"Completed trades    : "
        f"{overall['trades']}"
    )

    print(
        f"Wins                : "
        f"{overall['wins']}"
    )

    print(
        f"Losses              : "
        f"{overall['losses']}"
    )

    print(
        f"Win rate            : "
        f"{overall['win_rate']:.2f}%"
    )

    print(
        f"Net P&L             : "
        f"{overall['net_pnl']:.2f}"
    )

    print(
        f"Average trade       : "
        f"{overall['average_trade']:.2f}"
    )

    print(
        f"Profit factor       : "
        f"{format_profit_factor(overall['profit_factor'])}"
    )

    print(
        f"Overall max DD      : "
        f"{overall['max_drawdown']:.2f}"
    )

    print(
        f"Overall max DD %    : "
        f"{overall['max_drawdown_pct']:.2f}%"
    )

    print(
        f"Worst losing streak : "
        f"{overall['worst_losing_streak']}"
    )

    # -------------------------------------------------------------
    # Month distribution
    # -------------------------------------------------------------

    positive_months = sum(
        metrics["net_pnl"] > 0
        for metrics in monthly_metrics
    )

    negative_months = sum(
        metrics["net_pnl"] < 0
        for metrics in monthly_metrics
    )

    flat_months = sum(
        metrics["net_pnl"] == 0
        for metrics in monthly_metrics
    )

    print()
    print("MONTH DISTRIBUTION")
    print("-" * 125)

    print(
        f"Positive months : "
        f"{positive_months}"
    )

    print(
        f"Negative months : "
        f"{negative_months}"
    )

    print(
        f"Flat months     : "
        f"{flat_months}"
    )

    print(
        f"Total months    : "
        f"{len(monthly_metrics)}"
    )

    # -------------------------------------------------------------
    # Best / worst month
    # -------------------------------------------------------------

    if monthly_metrics:

        best_month = max(
            monthly_metrics,
            key=lambda item: item["net_pnl"],
        )

        worst_month = min(
            monthly_metrics,
            key=lambda item: item["net_pnl"],
        )

        print()
        print("BEST MONTH")
        print("-" * 125)

        print(
            f"{best_month['month']} -> "
            f"{best_month['net_pnl']:.2f}"
        )

        print()
        print("WORST MONTH")
        print("-" * 125)

        print(
            f"{worst_month['month']} -> "
            f"{worst_month['net_pnl']:.2f}"
        )

    # -------------------------------------------------------------
    # Win-rate extremes
    # -------------------------------------------------------------

    if monthly_metrics:

        highest_win_rate_month = max(
            monthly_metrics,
            key=lambda item: item["win_rate"],
        )

        lowest_win_rate_month = min(
            monthly_metrics,
            key=lambda item: item["win_rate"],
        )

        print()
        print("WIN-RATE EXTREMES")
        print("-" * 125)

        print(
            f"Highest: "
            f"{highest_win_rate_month['month']} -> "
            f"{highest_win_rate_month['win_rate']:.2f}%"
        )

        print(
            f"Lowest : "
            f"{lowest_win_rate_month['month']} -> "
            f"{lowest_win_rate_month['win_rate']:.2f}%"
        )

    print()
    print("=" * 125)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    print(
        "Loading complete historical dataset..."
    )

    data = load_data()

    print(
        f"Rows: {len(data):,} | "
        f"Start: {data.index.min()} | "
        f"End: {data.index.max()}"
    )

    config = make_config()

    print()
    print(
        "Using frozen baseline configuration..."
    )

    print(
        f"EMA fast: "
        f"{config.ema_fast_period}"
    )

    print(
        f"EMA slow: "
        f"{config.ema_slow_period}"
    )

    print(
        f"RSI period: "
        f"{config.rsi_period}"
    )

    print(
        f"ATR period: "
        f"{config.atr_period}"
    )

    print(
        f"RVOL period: "
        f"{config.rvol_period}"
    )

    print(
        f"Minimum RVOL: "
        f"{config.minimum_rvol}"
    )

    print(
        f"Minimum ATR: "
        f"{config.minimum_atr}"
    )

    print(
        f"RVOL enabled: "
        f"{config.use_rvol}"
    )

    print()
    print(
        "Creating baseline signal function..."
    )

    signal_function = (
        create_baseline_signal_function(
            data,
            config,
        )
    )

    print()
    print(
        "Running one continuous chronological "
        "backtest..."
    )

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )

    trades = list(result.trades)

    print(
        f"Completed trades: "
        f"{len(trades):,}"
    )

    if not trades:
        raise RuntimeError(
            "Backtest produced no completed trades."
        )

    monthly_groups = (
        group_trades_by_month(
            trades
        )
    )

    monthly_metrics = []

    for month, month_trades in (
        monthly_groups.items()
    ):
        metrics = calculate_trade_metrics(
            month_trades
        )

        metrics["month"] = str(month)

        monthly_metrics.append(
            metrics
        )

    print_monthly_report(
        monthly_metrics=monthly_metrics,
        overall_trades=trades,
    )


if __name__ == "__main__":
    main()
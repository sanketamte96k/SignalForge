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

RSI_LONG_THRESHOLD = 60.0

PERIODS = {
    "Development": ("2015-01-01", "2020-12-31"),
    "Validation": ("2021-01-01", "2022-12-31"),
    "OOS": ("2023-01-01", "2024-03-31"),
}


# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------

def load_data() -> pd.DataFrame:

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

    return data


# ---------------------------------------------------------------------
# Strategy configuration
# ---------------------------------------------------------------------

def make_config() -> StrategyConfig:

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
# Create baseline signal function
# ---------------------------------------------------------------------

def create_baseline_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
):

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
# Create RSI >= 60 candidate signal function
# ---------------------------------------------------------------------

def create_candidate_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
):

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

        # -------------------------------------------------------------
        # LONG
        # -------------------------------------------------------------

        if result.signal.value == "BUY":

            if not all(
                state.rsi >= RSI_LONG_THRESHOLD
                for state in (
                    state_30m,
                    state_15m,
                    state_10m,
                    state_5m,
                )
            ):
                return None

            return Position.LONG

        # -------------------------------------------------------------
        # SHORT
        # -------------------------------------------------------------

        if result.signal.value == "SELL":
            return Position.SHORT

        return None

    return signal_function


# ---------------------------------------------------------------------
# Run backtest
# ---------------------------------------------------------------------

def run_strategy(
    data: pd.DataFrame,
    config: StrategyConfig,
    candidate: bool,
):

    if candidate:

        signal_function = (
            create_candidate_signal_function(
                data,
                config,
            )
        )

    else:

        signal_function = (
            create_baseline_signal_function(
                data,
                config,
            )
        )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


# ---------------------------------------------------------------------
# Trade statistics
# ---------------------------------------------------------------------

def calculate_distribution(
    result,
) -> dict:

    trades = result.trades

    if not trades:

        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "median_trade": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "top_5_profit": 0.0,
            "top_10_profit": 0.0,
            "top_5_pct_of_profit": 0.0,
            "top_10_pct_of_profit": 0.0,
            "bottom_5_loss": 0.0,
            "bottom_10_loss": 0.0,
            "long_trades": 0,
            "short_trades": 0,
        }

    pnl = pd.Series(
        [float(trade.net_pnl) for trade in trades],
        dtype="float64",
    )

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    top_5 = (
        wins
        .sort_values(ascending=False)
        .head(5)
    )

    top_10 = (
        wins
        .sort_values(ascending=False)
        .head(10)
    )

    bottom_5 = (
        losses
        .sort_values(ascending=True)
        .head(5)
    )

    bottom_10 = (
        losses
        .sort_values(ascending=True)
        .head(10)
    )

    top_5_profit = float(top_5.sum())
    top_10_profit = float(top_10.sum())

    top_5_pct = (
        top_5_profit / gross_profit * 100.0
        if gross_profit > 0
        else 0.0
    )

    top_10_pct = (
        top_10_profit / gross_profit * 100.0
        if gross_profit > 0
        else 0.0
    )

    long_trades = sum(
        1
        for trade in trades
        if trade.position == Position.LONG
    )

    short_trades = sum(
        1
        for trade in trades
        if trade.position == Position.SHORT
    )

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100.0,
        "net_pnl": float(pnl.sum()),
        "avg_trade": float(pnl.mean()),
        "median_trade": float(pnl.median()),
        "best_trade": float(pnl.max()),
        "worst_trade": float(pnl.min()),
        "avg_win": float(wins.mean()) if not wins.empty else 0.0,
        "avg_loss": float(losses.mean()) if not losses.empty else 0.0,
        "profit_factor": profit_factor,
        "top_5_profit": top_5_profit,
        "top_10_profit": top_10_profit,
        "top_5_pct_of_profit": top_5_pct,
        "top_10_pct_of_profit": top_10_pct,
        "bottom_5_loss": float(bottom_5.sum()),
        "bottom_10_loss": float(bottom_10.sum()),
        "long_trades": long_trades,
        "short_trades": short_trades,
    }


# ---------------------------------------------------------------------
# Print distribution
# ---------------------------------------------------------------------

def print_distribution(
    period_name: str,
    strategy_name: str,
    stats: dict,
):

    pf = stats["profit_factor"]

    pf_text = (
        "INF"
        if pf == float("inf")
        else f"{pf:.3f}"
    )

    print(
        f"\n{period_name} | {strategy_name}"
    )

    print(
        f"  Trades:                  "
        f"{stats['trades']}"
    )

    print(
        f"  Wins:                    "
        f"{stats['wins']}"
    )

    print(
        f"  Losses:                  "
        f"{stats['losses']}"
    )

    print(
        f"  Win Rate:                "
        f"{stats['win_rate']:.2f}%"
    )

    print(
        f"  Net P&L:                 "
        f"{stats['net_pnl']:+.2f}"
    )

    print(
        f"  Average Trade:           "
        f"{stats['avg_trade']:+.2f}"
    )

    print(
        f"  Median Trade:            "
        f"{stats['median_trade']:+.2f}"
    )

    print(
        f"  Best Trade:              "
        f"{stats['best_trade']:+.2f}"
    )

    print(
        f"  Worst Trade:             "
        f"{stats['worst_trade']:+.2f}"
    )

    print(
        f"  Average Win:             "
        f"{stats['avg_win']:+.2f}"
    )

    print(
        f"  Average Loss:            "
        f"{stats['avg_loss']:+.2f}"
    )

    print(
        f"  Profit Factor:           "
        f"{pf_text}"
    )

    print(
        f"  Top 5 Winner Profit:     "
        f"{stats['top_5_profit']:+.2f}"
    )

    print(
        f"  Top 5 % of Gross Profit: "
        f"{stats['top_5_pct_of_profit']:.2f}%"
    )

    print(
        f"  Top 10 Winner Profit:    "
        f"{stats['top_10_profit']:+.2f}"
    )

    print(
        f"  Top 10 % Gross Profit:   "
        f"{stats['top_10_pct_of_profit']:.2f}%"
    )

    print(
        f"  Bottom 5 Losses:         "
        f"{stats['bottom_5_loss']:+.2f}"
    )

    print(
        f"  Bottom 10 Losses:        "
        f"{stats['bottom_10_loss']:+.2f}"
    )

    print(
        f"  LONG trades:             "
        f"{stats['long_trades']}"
    )

    print(
        f"  SHORT trades:            "
        f"{stats['short_trades']}"
    )


# ---------------------------------------------------------------------
# Compare candidate against baseline
# ---------------------------------------------------------------------

def print_impact(
    baseline: dict,
    candidate: dict,
):

    print("\n  IMPACT OF RSI >= 60")

    print(
        f"  Trade count change:      "
        f"{candidate['trades'] - baseline['trades']:+d}"
    )

    print(
        f"  Win rate change:         "
        f"{candidate['win_rate'] - baseline['win_rate']:+.2f} pp"
    )

    print(
        f"  Net P&L change:          "
        f"{candidate['net_pnl'] - baseline['net_pnl']:+.2f}"
    )

    print(
        f"  Average trade change:    "
        f"{candidate['avg_trade'] - baseline['avg_trade']:+.2f}"
    )

    print(
        f"  Median trade change:     "
        f"{candidate['median_trade'] - baseline['median_trade']:+.2f}"
    )

    print(
        f"  Best trade change:       "
        f"{candidate['best_trade'] - baseline['best_trade']:+.2f}"
    )

    print(
        f"  Worst trade change:      "
        f"{candidate['worst_trade'] - baseline['worst_trade']:+.2f}"
    )

    print(
        f"  Profit factor change:    "
        f"{candidate['profit_factor'] - baseline['profit_factor']:+.3f}"
    )

    print(
        f"  Top 5 profit change:     "
        f"{candidate['top_5_profit'] - baseline['top_5_profit']:+.2f}"
    )

    print(
        f"  Top 10 profit change:    "
        f"{candidate['top_10_profit'] - baseline['top_10_profit']:+.2f}"
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 72)
    print("SIGNALFORGE — TRADE DISTRIBUTION & OUTLIER ANALYSIS")
    print("=" * 72)

    print(
        f"\nData: {DATA_PATH}"
    )

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"→ {data.index.max()}"
    )

    config = make_config()

    # -------------------------------------------------------------
    # Analyze Development / Validation / OOS
    # -------------------------------------------------------------

    for period_name, (start, end) in PERIODS.items():

        period_data = data[
            (data.index >= pd.Timestamp(start))
            & (data.index <= pd.Timestamp(end))
        ].copy()

        if period_data.empty:

            print(
                f"\n{period_name}: NO DATA"
            )

            continue

        print("\n" + "-" * 72)

        print(
            f"{period_name}: "
            f"{start} → {end}"
        )

        print(
            f"Rows: {len(period_data):,}"
        )

        print("-" * 72)

        # ---------------------------------------------------------
        # Baseline
        # ---------------------------------------------------------

        baseline_result = run_strategy(
            period_data,
            config,
            candidate=False,
        )

        baseline_stats = calculate_distribution(
            baseline_result
        )

        # ---------------------------------------------------------
        # Candidate
        # ---------------------------------------------------------

        candidate_result = run_strategy(
            period_data,
            config,
            candidate=True,
        )

        candidate_stats = calculate_distribution(
            candidate_result
        )

        # ---------------------------------------------------------
        # Output
        # ---------------------------------------------------------

        print_distribution(
            period_name,
            "BASELINE",
            baseline_stats,
        )

        print_distribution(
            period_name,
            "RSI >= 60 CANDIDATE",
            candidate_stats,
        )

        print_impact(
            baseline_stats,
            candidate_stats,
        )

    print("\n" + "=" * 72)
    print("TRADE DISTRIBUTION ANALYSIS COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
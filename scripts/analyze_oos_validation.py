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

# Established Phase 7 execution assumption.
TRANSACTION_COST_RATE = 0.0001

# ---------------------------------------------------------------------
# Frozen baseline
#
# IMPORTANT:
# These values are fixed BEFORE OOS evaluation.
# No parameter is selected from OOS performance.
# ---------------------------------------------------------------------

BASELINE = {
    "EMA_FAST": 20,
    "EMA_SLOW": 50,
    "RSI_PERIOD": 14,
    "ATR_PERIOD": 14,
    "RVOL_PERIOD": 20,
    "MINIMUM_RVOL": 1.5,
    "MINIMUM_ATR": 0.0,
    "USE_RVOL": False,
}

# ---------------------------------------------------------------------
# Chronological validation design
#
# The full historical dataset ends in March 2024.
#
# Development period:
#     2015-01-09 through 2021-12-31
#
# OOS period:
#     2022-01-01 through 2024-03-26
#
# The OOS period is evaluated only after the frozen baseline has
# already been established.
#
# IMPORTANT:
# This script does NOT optimize on the development period.
# It simply evaluates the already-frozen baseline on both periods.
# ---------------------------------------------------------------------

DEVELOPMENT_START = pd.Timestamp("2015-01-01")
DEVELOPMENT_END = pd.Timestamp("2021-12-31 23:59:59")

OOS_START = pd.Timestamp("2022-01-01")
OOS_END = pd.Timestamp("2024-03-26 23:59:59")


# ---------------------------------------------------------------------
# Load and validate historical data
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

    required_columns = [
        "timestamp",
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

    data = (
        data
        .set_index("timestamp")
        .sort_index()
    )

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "Historical dataset contains duplicate timestamps."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Historical dataset timestamps are not chronological."
        )

    return data


# ---------------------------------------------------------------------
# Build frozen baseline config
# ---------------------------------------------------------------------

def make_config() -> StrategyConfig:

    return StrategyConfig(
        ema_fast_period=BASELINE["EMA_FAST"],
        ema_slow_period=BASELINE["EMA_SLOW"],
        rsi_period=BASELINE["RSI_PERIOD"],
        atr_period=BASELINE["ATR_PERIOD"],
        rvol_period=BASELINE["RVOL_PERIOD"],
        minimum_rvol=BASELINE["MINIMUM_RVOL"],
        minimum_atr=BASELINE["MINIMUM_ATR"],
        use_rvol=BASELINE["USE_RVOL"],
    )


# ---------------------------------------------------------------------
# Frozen baseline signal function
# ---------------------------------------------------------------------

def create_signal_function(
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

    selected_timeframes = (
        "30m",
        "15m",
        "10m",
        "5m",
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series | None,
    ) -> Position | None:

        timestamp = pd.Timestamp(row.name)

        states = {}

        for timeframe in selected_timeframes:

            state = cursors[timeframe].update(
                timestamp
            )

            if state is None:
                return None

            states[timeframe] = state

        result = generate_signal(
            states["30m"],
            states["15m"],
            states["10m"],
            states["5m"],
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
# Run baseline
# ---------------------------------------------------------------------

def run_strategy(
    data: pd.DataFrame,
    config: StrategyConfig,
):

    signal_function = create_signal_function(
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
# Calculate metrics
# ---------------------------------------------------------------------

def calculate_metrics(result) -> dict:

    trades = result.trades

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
        }

    pnl = [
        float(trade.net_pnl)
        for trade in trades
    ]

    wins = [
        value
        for value in pnl
        if value > 0
    ]

    losses = [
        value
        for value in pnl
        if value < 0
    ]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    net_pnl = sum(pnl)

    win_rate = (
        len(wins)
        / len(pnl)
        * 100.0
    )

    avg_trade = (
        net_pnl
        / len(pnl)
    )

    # -------------------------------------------------------------
    # Sequential equity / drawdown
    # -------------------------------------------------------------

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL

    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for value in pnl:

        equity += value

        if equity > peak_equity:
            peak_equity = equity

        drawdown = (
            peak_equity
            - equity
        )

        drawdown_pct = (
            drawdown
            / peak_equity
            * 100.0
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

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "avg_trade": avg_trade,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
    }


# ---------------------------------------------------------------------
# Print metrics
# ---------------------------------------------------------------------

def print_metrics(
    label: str,
    metrics: dict,
):

    print(f"\n{label}")

    print(
        f"  Trades:        "
        f"{metrics['trades']:,}"
    )

    print(
        f"  Wins:          "
        f"{metrics['wins']:,}"
    )

    print(
        f"  Losses:        "
        f"{metrics['losses']:,}"
    )

    print(
        f"  Win rate:      "
        f"{metrics['win_rate']:.2f}%"
    )

    print(
        f"  Net P&L:       "
        f"{metrics['net_pnl']:+.2f}"
    )

    print(
        f"  Avg trade:     "
        f"{metrics['avg_trade']:+.2f}"
    )

    print(
        f"  Profit factor: "
        f"{metrics['profit_factor']:.3f}"
    )

    print(
        f"  Max drawdown:  "
        f"{metrics['max_drawdown']:.2f}"
        f" ({metrics['max_drawdown_pct']:.2f}%)"
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 96)
    print("SIGNALFORGE - PHASE 7.8 OUT-OF-SAMPLE VALIDATION")
    print("=" * 96)

    print("\nFrozen baseline:")
    print("  EMA fast = 20")
    print("  EMA slow = 50")
    print("  RSI period = 14")
    print("  ATR period = 14")
    print("  RVOL period = 20")
    print("  RVOL enabled = False")
    print("  Minimum ATR = 0.0")
    print("  Minimum RVOL = 1.5")
    print("  MTF = 30m / 15m / 10m / 5m")

    print("\nExecution assumptions:")
    print("  Transaction cost = 0.01%")
    print("  Quantity = 1")
    print("  Initial capital = 100,000")

    print("\nValidation design:")
    print(
        f"  Development = "
        f"{DEVELOPMENT_START} -> {DEVELOPMENT_END}"
    )

    print(
        f"  OOS = "
        f"{OOS_START} -> {OOS_END}"
    )

    print("\nRules:")
    print("  Frozen strategy only")
    print("  No parameter optimization")
    print("  No candidate strategy")
    print("  No regime filter")
    print("  No parameter selection from OOS")
    print("  Chronological data only")
    print("  Canonical signal engine")
    print("  Causal indicator/timeframe architecture")

    # -------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------

    print("\nLoading historical data...")

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Full range: {data.index.min()} "
        f"-> {data.index.max()}"
    )

    # -------------------------------------------------------------
    # Build period datasets
    # -------------------------------------------------------------

    development_data = data[
        (data.index >= DEVELOPMENT_START)
        & (data.index <= DEVELOPMENT_END)
    ].copy()

    oos_data = data[
        (data.index >= OOS_START)
        & (data.index <= OOS_END)
    ].copy()

    if development_data.empty:
        raise RuntimeError(
            "Development period contains no data."
        )

    if oos_data.empty:
        raise RuntimeError(
            "OOS period contains no data."
        )

    print(
        f"\nDevelopment rows: "
        f"{len(development_data):,}"
    )

    print(
        f"Development actual range: "
        f"{development_data.index.min()} "
        f"-> {development_data.index.max()}"
    )

    print(
        f"OOS rows: "
        f"{len(oos_data):,}"
    )

    print(
        f"OOS actual range: "
        f"{oos_data.index.min()} "
        f"-> {oos_data.index.max()}"
    )

    # -------------------------------------------------------------
    # Freeze configuration
    # -------------------------------------------------------------

    config = make_config()

    # -------------------------------------------------------------
    # Development evaluation
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("DEVELOPMENT PERIOD")
    print("=" * 96)

    development_result = run_strategy(
        data=development_data,
        config=config,
    )

    development_metrics = calculate_metrics(
        development_result
    )

    print_metrics(
        "Development performance:",
        development_metrics,
    )

    # -------------------------------------------------------------
    # OOS evaluation
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("OUT-OF-SAMPLE PERIOD")
    print("=" * 96)

    oos_result = run_strategy(
        data=oos_data,
        config=config,
    )

    oos_metrics = calculate_metrics(
        oos_result
    )

    print_metrics(
        "OOS performance:",
        oos_metrics,
    )

    # -------------------------------------------------------------
    # Compare Development vs OOS
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("DEVELOPMENT vs OOS")
    print("=" * 96)

    pnl_change = (
        oos_metrics["net_pnl"]
        - development_metrics["net_pnl"]
    )

    pf_change = (
        oos_metrics["profit_factor"]
        - development_metrics["profit_factor"]
    )

    win_rate_change = (
        oos_metrics["win_rate"]
        - development_metrics["win_rate"]
    )

    print(
        f"Net P&L change:       "
        f"{pnl_change:+.2f}"
    )

    print(
        f"Profit factor change: "
        f"{pf_change:+.3f}"
    )

    print(
        f"Win-rate change:      "
        f"{win_rate_change:+.2f} percentage points"
    )

    # -------------------------------------------------------------
    # OOS diagnostics
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("OOS DIAGNOSTIC")
    print("=" * 96)

    oos_profitable = (
        oos_metrics["net_pnl"] > 0
    )

    oos_pf_positive = (
        oos_metrics["profit_factor"] > 1.0
    )

    oos_has_trades = (
        oos_metrics["trades"] > 0
    )

    print(
        "OOS has completed trades: "
        f"{'PASS' if oos_has_trades else 'FAIL'}"
    )

    print(
        "OOS net P&L positive:    "
        f"{'PASS' if oos_profitable else 'FAIL'}"
    )

    print(
        "OOS profit factor > 1:   "
        f"{'PASS' if oos_pf_positive else 'FAIL'}"
    )

    # -------------------------------------------------------------
    # Important interpretation
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("OOS INTERPRETATION RULES")
    print("=" * 96)

    print(
        "1. OOS results are not used to change the strategy."
    )

    print(
        "2. Positive OOS performance does not prove future profitability."
    )

    print(
        "3. Negative OOS performance does not automatically invalidate"
        " the entire architecture."
    )

    print(
        "4. OOS performance must be considered together with"
        " transaction-cost and parameter-stress results."
    )

    print(
        "5. No parameter may be selected because it performs better"
        " on this OOS period."
    )

    print(
        "6. The frozen EMA 20/50 baseline remains the official"
        " SignalForge research baseline."
    )

    print("\n" + "=" * 96)
    print("PHASE 7.8 OUT-OF-SAMPLE VALIDATION RUN COMPLETE")
    print("=" * 96)


if __name__ == "__main__":
    main()

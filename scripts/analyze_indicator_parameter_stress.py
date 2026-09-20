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

# Phase 7 baseline execution assumption.
TRANSACTION_COST_RATE = 0.0001

# ---------------------------------------------------------------------
# Frozen baseline parameters
# ---------------------------------------------------------------------

BASELINE = {
    "EMA_FAST": 20,
    "EMA_SLOW": 50,
    "RSI_PERIOD": 14,
    "ATR_PERIOD": 14,
}

# ---------------------------------------------------------------------
# One-at-a-time parameter perturbations.
#
# IMPORTANT:
# These are stress tests, NOT optimization candidates.
#
# Each parameter is changed independently while every other
# parameter remains at the frozen baseline.
# ---------------------------------------------------------------------

PARAMETER_TESTS = {
    "EMA_FAST": [15, 20, 25],
    "EMA_SLOW": [40, 50, 60],
    "RSI_PERIOD": [12, 14, 16],
    "ATR_PERIOD": [12, 14, 16],
}

# ---------------------------------------------------------------------
# Established baseline research values.
# These are used only as integrity checks.
# ---------------------------------------------------------------------

EXPECTED_BASELINE_TRADES = 2_157
EXPECTED_BASELINE_NET_PNL = 1_472.06
EXPECTED_BASELINE_PROFIT_FACTOR = 1.022


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
# Build StrategyConfig
# ---------------------------------------------------------------------

def make_config(
    ema_fast: int,
    ema_slow: int,
    rsi_period: int,
    atr_period: int,
) -> StrategyConfig:

    if ema_fast >= ema_slow:
        raise ValueError(
            "EMA fast period must be smaller than EMA slow period."
        )

    return StrategyConfig(
        ema_fast_period=ema_fast,
        ema_slow_period=ema_slow,
        rsi_period=rsi_period,
        atr_period=atr_period,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )


# ---------------------------------------------------------------------
# Frozen baseline / parameterized signal function
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
# Run one continuous chronological backtest
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
# Calculate performance metrics
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
# Build parameter configuration
# ---------------------------------------------------------------------

def build_config(
    parameter: str,
    value: int,
) -> StrategyConfig:

    parameters = BASELINE.copy()

    if parameter not in parameters:
        raise ValueError(
            f"Unknown parameter: {parameter}"
        )

    parameters[parameter] = value

    return make_config(
        ema_fast=parameters["EMA_FAST"],
        ema_slow=parameters["EMA_SLOW"],
        rsi_period=parameters["RSI_PERIOD"],
        atr_period=parameters["ATR_PERIOD"],
    )


# ---------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------

def format_pf(value: float) -> str:

    if value == float("inf"):
        return "INF"

    return f"{value:.3f}"


def format_parameter_value(
    parameter: str,
    value: int,
) -> str:

    return f"{parameter}={value}"


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 96)
    print("SIGNALFORGE - PHASE 7.7 PARAMETER STRESS TESTING")
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
    print("  Backtest = one continuous chronological run")

    print("\nResearch methodology:")
    print("  One-at-a-time parameter perturbation")
    print("  No parameter optimization")
    print("  No candidate strategy")
    print("  No Development/Validation/OOS slicing")
    print("  No regime filter")
    print("  No strategy-rule modification")
    print("  Frozen signal engine used for every variant")

    print("\nStress-test values:")

    for parameter, values in PARAMETER_TESTS.items():

        print(
            f"  {parameter}: "
            f"{', '.join(str(value) for value in values)}"
        )

    # -------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------

    print("\nLoading historical data...")

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"-> {data.index.max()}"
    )

    # -------------------------------------------------------------
    # Baseline integrity check
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("BASELINE INTEGRITY CHECK")
    print("=" * 96)

    baseline_config = make_config(
        ema_fast=BASELINE["EMA_FAST"],
        ema_slow=BASELINE["EMA_SLOW"],
        rsi_period=BASELINE["RSI_PERIOD"],
        atr_period=BASELINE["ATR_PERIOD"],
    )

    baseline_result = run_strategy(
        data=data,
        config=baseline_config,
    )

    baseline_metrics = calculate_metrics(
        baseline_result
    )

    print(
        f"Baseline trades:        "
        f"{baseline_metrics['trades']:,}"
    )

    print(
        f"Baseline net P&L:       "
        f"{baseline_metrics['net_pnl']:+.2f}"
    )

    print(
        f"Baseline profit factor: "
        f"{format_pf(baseline_metrics['profit_factor'])}"
    )

    baseline_trade_ok = (
        baseline_metrics["trades"]
        == EXPECTED_BASELINE_TRADES
    )

    baseline_pnl_ok = (
        abs(
            baseline_metrics["net_pnl"]
            - EXPECTED_BASELINE_NET_PNL
        )
        < 0.10
    )

    baseline_pf_ok = (
        abs(
            baseline_metrics["profit_factor"]
            - EXPECTED_BASELINE_PROFIT_FACTOR
        )
        < 0.001
    )

    print(
        "Trade count check:      "
        f"{'PASS' if baseline_trade_ok else 'FAIL'}"
    )

    print(
        "Net P&L check:          "
        f"{'PASS' if baseline_pnl_ok else 'FAIL'}"
    )

    print(
        "Profit factor check:    "
        f"{'PASS' if baseline_pf_ok else 'FAIL'}"
    )

    if not (
        baseline_trade_ok
        and baseline_pnl_ok
        and baseline_pf_ok
    ):

        raise RuntimeError(
            "Baseline integrity check failed. "
            "Do not continue Phase 7.7."
        )

    # -------------------------------------------------------------
    # Parameter stress tests
    # -------------------------------------------------------------

    summary = []

    for parameter, values in PARAMETER_TESTS.items():

        print("\n" + "=" * 96)
        print(
            f"PARAMETER: {parameter}"
        )
        print("=" * 96)

        for value in values:

            config = build_config(
                parameter,
                value,
            )

            result = run_strategy(
                data=data,
                config=config,
            )

            metrics = calculate_metrics(
                result
            )

            delta_pnl = (
                metrics["net_pnl"]
                - baseline_metrics["net_pnl"]
            )

            delta_pf = (
                metrics["profit_factor"]
                - baseline_metrics["profit_factor"]
            )

            print("\n" + "-" * 96)
            print(
                format_parameter_value(
                    parameter,
                    value,
                )
            )
            print("-" * 96)

            print(
                f"  Trades:        "
                f"{metrics['trades']:,}"
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
                f"{format_pf(metrics['profit_factor'])}"
            )

            print(
                f"  Max drawdown:  "
                f"{metrics['max_drawdown']:.2f}"
                f" ({metrics['max_drawdown_pct']:.2f}%)"
            )

            print(
                f"  P&L vs baseline:"
                f" {delta_pnl:+.2f}"
            )

            print(
                f"  PF vs baseline: "
                f"{delta_pf:+.3f}"
            )

            summary.append(
                {
                    "parameter": parameter,
                    "value": value,
                    "is_baseline": (
                        value == BASELINE[parameter]
                    ),
                    "trades": metrics["trades"],
                    "win_rate": metrics["win_rate"],
                    "net_pnl": metrics["net_pnl"],
                    "avg_trade": metrics["avg_trade"],
                    "profit_factor": metrics[
                        "profit_factor"
                    ],
                    "max_drawdown": metrics[
                        "max_drawdown"
                    ],
                    "max_drawdown_pct": metrics[
                        "max_drawdown_pct"
                    ],
                    "pnl_vs_baseline": delta_pnl,
                    "pf_vs_baseline": delta_pf,
                }
            )

    # -------------------------------------------------------------
    # Summary table
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("PARAMETER STRESS SUMMARY")
    print("=" * 96)

    summary_df = pd.DataFrame(
        summary
    )

    print(
        summary_df.to_string(
            index=False,
            formatters={
                "value": lambda value: f"{int(value)}",
                "is_baseline": lambda value: (
                    "BASELINE" if value else ""
                ),
                "trades": lambda value: f"{int(value):,}",
                "win_rate": lambda value: (
                    f"{value:.2f}%"
                ),
                "net_pnl": lambda value: (
                    f"{value:+.2f}"
                ),
                "avg_trade": lambda value: (
                    f"{value:+.2f}"
                ),
                "profit_factor": lambda value: (
                    format_pf(value)
                ),
                "max_drawdown": lambda value: (
                    f"{value:.2f}"
                ),
                "max_drawdown_pct": lambda value: (
                    f"{value:.2f}%"
                ),
                "pnl_vs_baseline": lambda value: (
                    f"{value:+.2f}"
                ),
                "pf_vs_baseline": lambda value: (
                    f"{value:+.3f}"
                ),
            },
        )
    )

    # -------------------------------------------------------------
    # Diagnostic stability summary
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("PARAMETER STABILITY DIAGNOSTIC")
    print("=" * 96)

    for parameter in PARAMETER_TESTS:

        rows = [
            row
            for row in summary
            if row["parameter"] == parameter
        ]

        profitable_variants = sum(
            row["net_pnl"] > 0
            for row in rows
        )

        positive_pf_variants = sum(
            row["profit_factor"] > 1.0
            for row in rows
        )

        print(
            f"\n{parameter}:"
        )

        print(
            f"  Profitable variants: "
            f"{profitable_variants}/{len(rows)}"
        )

        print(
            f"  PF > 1 variants:     "
            f"{positive_pf_variants}/{len(rows)}"
        )

        print(
            f"  P&L range:           "
            f"{min(row['net_pnl'] for row in rows):+.2f}"
            f" to "
            f"{max(row['net_pnl'] for row in rows):+.2f}"
        )

        print(
            f"  PF range:            "
            f"{min(row['profit_factor'] for row in rows):.3f}"
            f" to "
            f"{max(row['profit_factor'] for row in rows):.3f}"
        )

    # -------------------------------------------------------------
    # Final methodology statement
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("RESEARCH RULES")
    print("=" * 96)

    print("1. This is diagnostic stress testing only.")
    print("2. The frozen strategy remains unchanged.")
    print("3. Parameters are perturbed one at a time.")
    print("4. No parameter value is selected as a new strategy.")
    print("5. No optimization is performed.")
    print("6. Every variant uses the complete chronological history.")
    print("7. Transaction cost remains fixed at 0.01%.")
    print("8. The canonical signal engine is used.")
    print("9. No Development/Validation/OOS slicing is used.")
    print("10. Results must be interpreted before any strategy modification.")

    print("\n" + "=" * 96)
    print("PHASE 7.7 PARAMETER STRESS TESTING RUN COMPLETE")
    print("=" * 96)


if __name__ == "__main__":
    main()

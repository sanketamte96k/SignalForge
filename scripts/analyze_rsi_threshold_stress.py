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

TRANSACTION_COST_RATE = 0.0001  # 0.01%

# ---------------------------------------------------------------------
# Stress-test RSI thresholds.
#
# 60 is the current candidate.
# We deliberately test values around it rather than optimizing over
# the entire possible RSI range.
# ---------------------------------------------------------------------

RSI_THRESHOLDS = [
    55.0,
    57.5,
    60.0,
    62.5,
    65.0,
]

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
# Create threshold-specific signal function
# ---------------------------------------------------------------------

def create_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
    rsi_threshold: float,
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

            long_states = (
                state_30m,
                state_15m,
                state_10m,
                state_5m,
            )

            if not all(
                state.rsi >= rsi_threshold
                for state in long_states
            ):
                return None

            return Position.LONG

        # -------------------------------------------------------------
        # SHORT
        #
        # Deliberately unchanged for this experiment.
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
    rsi_threshold: float,
):

    signal_function = create_signal_function(
        data,
        config,
        rsi_threshold,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


# ---------------------------------------------------------------------
# Metrics
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

    net_pnl = sum(pnl)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

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
    # Drawdown
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
# Profit-factor formatter
# ---------------------------------------------------------------------

def format_pf(value: float) -> str:

    if value == float("inf"):
        return "INF"

    return f"{value:.3f}"


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 72)
    print("SIGNALFORGE — RSI THRESHOLD STRESS TEST")
    print("=" * 72)

    print(
        f"\nTransaction cost: "
        f"{TRANSACTION_COST_RATE * 100:.2f}%"
    )

    print(
        f"Thresholds tested: "
        f"{', '.join(str(value) for value in RSI_THRESHOLDS)}"
    )

    data = load_data()

    print(
        f"\nRows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"→ {data.index.max()}"
    )

    config = make_config()

    summary = []

    # -----------------------------------------------------------------
    # Period loop
    # -----------------------------------------------------------------

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

        # -------------------------------------------------------------
        # Threshold loop
        # -------------------------------------------------------------

        for threshold in RSI_THRESHOLDS:

            result = run_strategy(
                period_data,
                config,
                threshold,
            )

            metrics = calculate_metrics(
                result
            )

            print(
                f"\nRSI >= {threshold:.1f}"
            )

            print(
                f"  Trades:       "
                f"{metrics['trades']}"
            )

            print(
                f"  Wins:         "
                f"{metrics['wins']}"
            )

            print(
                f"  Losses:       "
                f"{metrics['losses']}"
            )

            print(
                f"  Win Rate:     "
                f"{metrics['win_rate']:.2f}%"
            )

            print(
                f"  Net P&L:      "
                f"{metrics['net_pnl']:+.2f}"
            )

            print(
                f"  Avg Trade:    "
                f"{metrics['avg_trade']:+.2f}"
            )

            print(
                f"  PF:           "
                f"{format_pf(metrics['profit_factor'])}"
            )

            print(
                f"  Max DD:       "
                f"{metrics['max_drawdown_pct']:.2f}%"
            )

            summary.append(
                {
                    "period": period_name,
                    "rsi_threshold": threshold,
                    "trades": metrics["trades"],
                    "win_rate": metrics["win_rate"],
                    "net_pnl": metrics["net_pnl"],
                    "avg_trade": metrics["avg_trade"],
                    "profit_factor": metrics["profit_factor"],
                    "max_drawdown_pct": metrics[
                        "max_drawdown_pct"
                    ],
                }
            )

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------

    print("\n" + "=" * 72)
    print("RSI THRESHOLD STRESS SUMMARY")
    print("=" * 72)

    if summary:

        summary_df = pd.DataFrame(
            summary
        )

        print(
            summary_df.to_string(
                index=False,
                float_format=lambda value: f"{value:.3f}",
            )
        )

    # -----------------------------------------------------------------
    # Per-period best threshold
    # -----------------------------------------------------------------

    print("\n" + "=" * 72)
    print("BEST THRESHOLD BY PERIOD")
    print("=" * 72)

    if summary:

        for period_name in PERIODS:

            period_results = [
                row
                for row in summary
                if row["period"] == period_name
            ]

            if not period_results:
                continue

            best = max(
                period_results,
                key=lambda row: row["net_pnl"],
            )

            print(
                f"{period_name}: "
                f"RSI >= {best['rsi_threshold']:.1f} | "
                f"P&L {best['net_pnl']:+.2f} | "
                f"PF {format_pf(best['profit_factor'])}"
            )

    print("\n" + "=" * 72)
    print("RSI THRESHOLD STRESS TEST COMPLETE")
    print("=" * 72)


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()
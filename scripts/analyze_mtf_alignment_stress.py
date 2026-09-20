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

RSI_LONG_THRESHOLD = 60.0

MINIMUM_ATR = 0.0

# ---------------------------------------------------------------------
# Controlled MTF variants.
#
# Variant A is the current production research candidate.
# The remaining variants deliberately remove confirmation layers.
# ---------------------------------------------------------------------

MTF_VARIANTS = {
    "A_ALL_4": ("30m", "15m", "10m", "5m"),
    "B_NO_5M": ("30m", "15m", "10m"),
    "C_30M_15M": ("30m", "15m"),
    "D_30M_5M": ("30m", "5m"),
    "E_NO_30M": ("15m", "10m", "5m"),
}

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
        minimum_atr=MINIMUM_ATR,
        use_rvol=False,
    )


# ---------------------------------------------------------------------
# State direction
# ---------------------------------------------------------------------

def timeframe_direction(state) -> str:

    if state.close > state.ema20 > state.ema50:
        return "LONG"

    if state.close < state.ema20 < state.ema50:
        return "SHORT"

    return "NONE"


# ---------------------------------------------------------------------
# Candidate signal function for one MTF variant
# ---------------------------------------------------------------------

def create_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
    selected_timeframes: tuple[str, ...],
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

        states = {}

        for timeframe in selected_timeframes:

            state = cursors[timeframe].update(
                timestamp
            )

            if state is None:
                return None

            states[timeframe] = state

        # -------------------------------------------------------------
        # Direction of every selected timeframe
        # -------------------------------------------------------------

        directions = {
            timeframe: timeframe_direction(state)
            for timeframe, state in states.items()
        }

        # -------------------------------------------------------------
        # LONG
        #
        # Every selected timeframe must be bullish.
        # RSI >= 60 must also hold on every selected timeframe.
        # -------------------------------------------------------------

        if all(
            directions[timeframe] == "LONG"
            for timeframe in selected_timeframes
        ):

            if not all(
                states[timeframe].rsi >= RSI_LONG_THRESHOLD
                for timeframe in selected_timeframes
            ):
                return None

            if not all(
                states[timeframe].atr >= config.minimum_atr
                for timeframe in selected_timeframes
            ):
                return None

            return Position.LONG

        # -------------------------------------------------------------
        # SHORT
        #
        # Every selected timeframe must be bearish.
        # RSI remains unchanged from the original strategy:
        # no RSI >= 60 requirement for shorts.
        # -------------------------------------------------------------

        if all(
            directions[timeframe] == "SHORT"
            for timeframe in selected_timeframes
        ):

            if not all(
                states[timeframe].atr >= config.minimum_atr
                for timeframe in selected_timeframes
            ):
                return None

            return Position.SHORT

        return None

    return signal_function


# ---------------------------------------------------------------------
# Run strategy
# ---------------------------------------------------------------------

def run_strategy(
    data: pd.DataFrame,
    config: StrategyConfig,
    selected_timeframes: tuple[str, ...],
):

    signal_function = create_signal_function(
        data,
        config,
        selected_timeframes,
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
            "long_trades": 0,
            "short_trades": 0,
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
        "long_trades": long_trades,
        "short_trades": short_trades,
    }


# ---------------------------------------------------------------------
# Profit factor formatting
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
    print("SIGNALFORGE — MULTI-TIMEFRAME ALIGNMENT STRESS TEST")
    print("=" * 72)

    print(
        f"\nTransaction cost: "
        f"{TRANSACTION_COST_RATE * 100:.2f}%"
    )

    print(
        f"LONG RSI threshold: "
        f"{RSI_LONG_THRESHOLD:.1f}"
    )

    print(
        "\nVariants:"
    )

    for name, timeframes in MTF_VARIANTS.items():

        print(
            f"  {name}: "
            f"{' + '.join(timeframes)}"
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
        # Variant loop
        # -------------------------------------------------------------

        for variant_name, selected_timeframes in MTF_VARIANTS.items():

            result = run_strategy(
                period_data,
                config,
                selected_timeframes,
            )

            metrics = calculate_metrics(
                result
            )

            print(
                f"\n{variant_name}"
            )

            print(
                f"  Timeframes:   "
                f"{' + '.join(selected_timeframes)}"
            )

            print(
                f"  Trades:       "
                f"{metrics['trades']}"
            )

            print(
                f"  LONG:         "
                f"{metrics['long_trades']}"
            )

            print(
                f"  SHORT:        "
                f"{metrics['short_trades']}"
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
                    "variant": variant_name,
                    "timeframes": " + ".join(
                        selected_timeframes
                    ),
                    "trades": metrics["trades"],
                    "long_trades": metrics["long_trades"],
                    "short_trades": metrics["short_trades"],
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
    print("MULTI-TIMEFRAME ALIGNMENT SUMMARY")
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
    # OOS ranking
    #
    # This is informational only.
    # We do NOT automatically select the winner.
    # -----------------------------------------------------------------

    print("\n" + "=" * 72)
    print("OOS VARIANT COMPARISON")
    print("=" * 72)

    oos_rows = [
        row
        for row in summary
        if row["period"] == "OOS"
    ]

    if oos_rows:

        oos_df = pd.DataFrame(
            oos_rows
        ).sort_values(
            "net_pnl",
            ascending=False,
        )

        print(
            oos_df[
                [
                    "variant",
                    "timeframes",
                    "trades",
                    "win_rate",
                    "net_pnl",
                    "avg_trade",
                    "profit_factor",
                    "max_drawdown_pct",
                ]
            ].to_string(
                index=False,
                float_format=lambda value: f"{value:.3f}",
            )
        )

    print("\n" + "=" * 72)
    print("MULTI-TIMEFRAME ALIGNMENT STRESS TEST COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
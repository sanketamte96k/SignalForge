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

# Existing project transaction-cost assumption.
TRANSACTION_COST_RATE = 0.0001  # 0.01%

# Per-side execution slippage.
#
# 0.01% = 1 basis point per side
# 0.10% = 10 basis points per side
#
# Slippage is applied independently to entry and exit.
SLIPPAGE_RATES = [
    0.0000,
    0.0001,
    0.0002,
    0.0003,
    0.0005,
    0.0010,
]


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
            "Historical dataset timestamps are not chronological."
        )

    return data


# ---------------------------------------------------------------------
# Frozen baseline configuration
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
# Frozen baseline signal function
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
# Run one continuous baseline backtest
# ---------------------------------------------------------------------

def run_baseline(
    data: pd.DataFrame,
    config: StrategyConfig,
):

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
# Slippage calculation
# ---------------------------------------------------------------------

def trade_slippage(
    trade,
    slippage_rate: float,
) -> float:

    entry_price = float(trade.entry_price)
    exit_price = float(trade.exit_price)
    quantity = float(trade.quantity)

    return (
        entry_price
        + exit_price
    ) * quantity * slippage_rate


def calculate_total_slippage(
    trades,
    slippage_rate: float,
) -> float:

    return sum(
        trade_slippage(trade, slippage_rate)
        for trade in trades
    )


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

def calculate_metrics(
    trades,
    slippage_rate: float,
) -> dict:

    if not trades:

        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_pnl": 0.0,
            "slippage": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
        }

    adjusted_pnl = []

    for trade in trades:

        original_pnl = float(trade.net_pnl)

        slippage = trade_slippage(
            trade,
            slippage_rate,
        )

        adjusted_pnl.append(
            original_pnl - slippage
        )

    wins = [
        pnl
        for pnl in adjusted_pnl
        if pnl > 0
    ]

    losses = [
        pnl
        for pnl in adjusted_pnl
        if pnl < 0
    ]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    net_pnl = sum(adjusted_pnl)

    win_rate = (
        len(wins)
        / len(adjusted_pnl)
        * 100.0
    )

    avg_trade = (
        net_pnl
        / len(adjusted_pnl)
    )

    # -------------------------------------------------------------
    # Sequential equity / drawdown
    # -------------------------------------------------------------

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL

    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for pnl in adjusted_pnl:

        equity += pnl

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

    total_slippage = calculate_total_slippage(
        trades,
        slippage_rate,
    )

    original_pnl = sum(
        float(trade.net_pnl)
        for trade in trades
    )

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "gross_pnl": original_pnl,
        "slippage": total_slippage,
        "net_pnl": net_pnl,
        "avg_trade": avg_trade,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
    }


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------

def format_pf(value: float) -> str:

    if value == float("inf"):
        return "INF"

    return f"{value:.3f}"


def format_rate(rate: float) -> str:

    return f"{rate * 100.0:.2f}%"


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 96)
    print("SIGNALFORGE - PHASE 7.5 SLIPPAGE SENSITIVITY")
    print("=" * 96)

    print("\nFrozen baseline:")
    print("  EMA = 20 / 50")
    print("  RSI = 14")
    print("  ATR = 14")
    print("  RVOL = 20")
    print("  RVOL enabled = False")
    print("  MTF = 30m / 15m / 10m / 5m")
    print("  Minimum ATR = 0.0")
    print("  Minimum RVOL = 1.5")

    print("\nExecution assumptions:")
    print(
        f"  Transaction cost = "
        f"{TRANSACTION_COST_RATE * 100.0:.2f}%"
    )
    print("  Slippage = per-side percentage")
    print("  Quantity = 1")
    print("  Strategy = frozen baseline only")
    print("  Backtest = one continuous chronological run")
    print("  No candidate strategy")
    print("  No parameter optimization")
    print("  No period slicing")

    print("\nLoading historical data...")

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"-> {data.index.max()}"
    )

    config = make_config()

    print("\nRunning one continuous chronological baseline backtest...")

    result = run_baseline(
        data,
        config,
    )

    trades = result.trades

    print(
        f"Completed baseline trades: {len(trades):,}"
    )

    if not trades:
        raise RuntimeError(
            "Baseline backtest produced zero completed trades."
        )

    # -------------------------------------------------------------
    # Baseline cross-check
    # -------------------------------------------------------------

    baseline_metrics = calculate_metrics(
        trades,
        0.0,
    )

    print("\n" + "=" * 96)
    print("BASELINE CROSS-CHECK")
    print("=" * 96)

    print(
        f"Trades:        {baseline_metrics['trades']:,}"
    )

    print(
        f"Win rate:      {baseline_metrics['win_rate']:.2f}%"
    )

    print(
        f"Net P&L:       {baseline_metrics['net_pnl']:+.2f}"
    )

    print(
        f"Avg trade:     {baseline_metrics['avg_trade']:+.2f}"
    )

    print(
        f"Profit factor: {format_pf(baseline_metrics['profit_factor'])}"
    )

    print(
        f"Max drawdown:  {baseline_metrics['max_drawdown']:.2f}"
        f" ({baseline_metrics['max_drawdown_pct']:.2f}%)"
    )

    # -------------------------------------------------------------
    # Sanity check against known Phase 7 baseline.
    # -------------------------------------------------------------

    expected_trades = 2157
    expected_pnl = 1472.06

    trade_count_ok = (
        baseline_metrics["trades"] == expected_trades
    )

    pnl_ok = (
        abs(
            baseline_metrics["net_pnl"]
            - expected_pnl
        )
        < 0.10
    )

    print("\nBaseline integrity check:")

    print(
        f"  Trade count = "
        f"{'PASS' if trade_count_ok else 'FAIL'}"
    )

    print(
        f"  Net P&L     = "
        f"{'PASS' if pnl_ok else 'FAIL'}"
    )

    if not trade_count_ok or not pnl_ok:

        raise RuntimeError(
            "Frozen baseline integrity check failed. "
            "Do not continue with slippage analysis."
        )

    # -------------------------------------------------------------
    # Slippage sensitivity
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("SLIPPAGE SENSITIVITY RESULTS")
    print("=" * 96)

    print(
        "\nSlippage is charged on both entry and exit."
    )

    print(
        "Signals and trade count remain unchanged at every slippage level."
    )

    summary = []

    for slippage_rate in SLIPPAGE_RATES:

        metrics = calculate_metrics(
            trades,
            slippage_rate,
        )

        pnl_change = (
            metrics["net_pnl"]
            - baseline_metrics["net_pnl"]
        )

        pnl_change_pct = (
            pnl_change
            / abs(baseline_metrics["net_pnl"])
            * 100.0
            if baseline_metrics["net_pnl"] != 0
            else 0.0
        )

        print("\n" + "-" * 96)

        print(
            f"Slippage: {format_rate(slippage_rate)} per side"
        )

        print(
            f"  Trades:          {metrics['trades']:,}"
        )

        print(
            f"  Win rate:        {metrics['win_rate']:.2f}%"
        )

        print(
            f"  Slippage cost:   -{metrics['slippage']:.2f}"
        )

        print(
            f"  Net P&L:         {metrics['net_pnl']:+.2f}"
        )

        print(
            f"  Avg trade:       {metrics['avg_trade']:+.2f}"
        )

        print(
            f"  Profit factor:   {format_pf(metrics['profit_factor'])}"
        )

        print(
            f"  Max drawdown:    {metrics['max_drawdown']:.2f}"
            f" ({metrics['max_drawdown_pct']:.2f}%)"
        )

        print(
            f"  P&L change:      {pnl_change:+.2f}"
            f" ({pnl_change_pct:+.2f}% vs baseline)"
        )

        summary.append(
            {
                "slippage_pct": slippage_rate * 100.0,
                "trades": metrics["trades"],
                "win_rate": metrics["win_rate"],
                "slippage_cost": metrics["slippage"],
                "net_pnl": metrics["net_pnl"],
                "avg_trade": metrics["avg_trade"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown": metrics["max_drawdown"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
            }
        )

    # -------------------------------------------------------------
    # Summary table
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("SLIPPAGE SENSITIVITY SUMMARY TABLE")
    print("=" * 96)

    summary_df = pd.DataFrame(summary)

    print(
        summary_df.to_string(
            index=False,
            formatters={
                "slippage_pct": lambda value: f"{value:.2f}",
                "trades": lambda value: f"{int(value):,}",
                "win_rate": lambda value: f"{value:.2f}%",
                "slippage_cost": lambda value: f"{value:.2f}",
                "net_pnl": lambda value: f"{value:+.2f}",
                "avg_trade": lambda value: f"{value:+.2f}",
                "profit_factor": lambda value: format_pf(value),
                "max_drawdown": lambda value: f"{value:.2f}",
                "max_drawdown_pct": lambda value: f"{value:.2f}%",
            },
        )
    )

    # -------------------------------------------------------------
    # Break-even estimate
    # -------------------------------------------------------------

    total_notional_per_unit = sum(
        float(trade.entry_price) + float(trade.exit_price)
        for trade in trades
    )

    if total_notional_per_unit > 0:

        break_even_rate = (
            baseline_metrics["net_pnl"]
            / total_notional_per_unit
        )

        break_even_total_pct = (
            break_even_rate
            * 100.0
            * 2.0
        )

        print("\n" + "=" * 96)
        print("APPROXIMATE SLIPPAGE BREAK-EVEN")
        print("=" * 96)

        print(
            f"Approximate break-even slippage: "
            f"{break_even_rate * 100.0:.4f}% per side"
        )

        print(
            f"Approximate total round-trip equivalent: "
            f"{break_even_total_pct:.4f}%"
        )

        print(
            "\nInterpretation:"
        )

        print(
            "  This is a mathematical sensitivity threshold, "
            "not a recommended execution assumption."
        )

    # -------------------------------------------------------------
    # Research rules
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("RESEARCH RULES")
    print("=" * 96)

    print("1. Diagnostic analysis only.")
    print("2. Trading strategy remains frozen.")
    print("3. No slippage-adjusted parameter optimization.")
    print("4. No candidate strategy.")
    print("5. Transaction costs remain fixed.")
    print("6. Trade signals remain unchanged.")
    print("7. Slippage is applied only as an execution overlay.")
    print("8. Results must be interpreted before any strategy modification.")

    print("\n" + "=" * 96)
    print("PHASE 7.5 SLIPPAGE SENSITIVITY COMPLETE")
    print("=" * 96)


if __name__ == "__main__":
    main()

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

# Transaction-cost rates are applied by the canonical backtest engine.
#
# 0.0000 = 0.00%
# 0.0001 = 0.01%
# 0.0002 = 0.02%
# 0.0003 = 0.03%
# 0.0005 = 0.05%
# 0.0010 = 0.10%
COST_RATES = [
    0.0000,
    0.0001,
    0.0002,
    0.0003,
    0.0005,
    0.0010,
]

# Established Phase 7 baseline uses 0.01% transaction cost.
ESTABLISHED_BASELINE_COST = 0.0001


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
# Run one continuous chronological baseline backtest
# ---------------------------------------------------------------------

def run_baseline(
    data: pd.DataFrame,
    config: StrategyConfig,
    transaction_cost_rate: float,
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
        transaction_cost_rate=transaction_cost_rate,
    )


# ---------------------------------------------------------------------
# Performance metrics
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
    print("SIGNALFORGE - PHASE 7.6 TRANSACTION-COST SENSITIVITY")
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
    print("  Transaction cost = variable")
    print("  Cost applied by existing backtest engine")
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

    # -------------------------------------------------------------
    # Run the same frozen strategy at every cost level.
    # -------------------------------------------------------------

    results = []

    for cost_rate in COST_RATES:

        print("\n" + "-" * 96)

        print(
            f"Transaction cost: {format_rate(cost_rate)}"
        )

        result = run_baseline(
            data=data,
            config=config,
            transaction_cost_rate=cost_rate,
        )

        metrics = calculate_metrics(
            result,
        )

        print(
            f"  Trades:        {metrics['trades']:,}"
        )

        print(
            f"  Win rate:      {metrics['win_rate']:.2f}%"
        )

        print(
            f"  Net P&L:       {metrics['net_pnl']:+.2f}"
        )

        print(
            f"  Avg trade:     {metrics['avg_trade']:+.2f}"
        )

        print(
            f"  Profit factor: {format_pf(metrics['profit_factor'])}"
        )

        print(
            f"  Max drawdown:  {metrics['max_drawdown']:.2f}"
            f" ({metrics['max_drawdown_pct']:.2f}%)"
        )

        results.append(
            {
                "cost_rate": cost_rate,
                "cost_pct": cost_rate * 100.0,
                "result": result,
                "metrics": metrics,
            }
        )

    # -------------------------------------------------------------
    # Baseline integrity checks
    # -------------------------------------------------------------

    zero_cost = next(
        item
        for item in results
        if item["cost_rate"] == 0.0
    )

    established_cost = next(
        item
        for item in results
        if item["cost_rate"] == ESTABLISHED_BASELINE_COST
    )

    zero_metrics = zero_cost["metrics"]
    established_metrics = established_cost["metrics"]

    # Known values from the existing SignalForge baseline research.
    expected_zero_cost_trades = 2157
    expected_zero_cost_pnl = 6925.85

    expected_established_trades = 2157
    expected_established_pnl = 1472.06

    zero_trade_count_ok = (
        zero_metrics["trades"]
        == expected_zero_cost_trades
    )

    zero_pnl_ok = (
        abs(
            zero_metrics["net_pnl"]
            - expected_zero_cost_pnl
        )
        < 0.10
    )

    established_trade_count_ok = (
        established_metrics["trades"]
        == expected_established_trades
    )

    established_pnl_ok = (
        abs(
            established_metrics["net_pnl"]
            - expected_established_pnl
        )
        < 0.10
    )

    print("\n" + "=" * 96)
    print("BASELINE INTEGRITY CHECK")
    print("=" * 96)

    print(
        "Zero-cost trade count = "
        f"{'PASS' if zero_trade_count_ok else 'FAIL'}"
    )

    print(
        "Zero-cost net P&L     = "
        f"{'PASS' if zero_pnl_ok else 'FAIL'}"
    )

    print(
        "0.01% trade count     = "
        f"{'PASS' if established_trade_count_ok else 'FAIL'}"
    )

    print(
        "0.01% net P&L         = "
        f"{'PASS' if established_pnl_ok else 'FAIL'}"
    )

    if not (
        zero_trade_count_ok
        and zero_pnl_ok
        and established_trade_count_ok
        and established_pnl_ok
    ):

        raise RuntimeError(
            "Frozen baseline integrity check failed."
        )

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("TRANSACTION-COST SENSITIVITY SUMMARY")
    print("=" * 96)

    zero_cost_pnl = zero_metrics["net_pnl"]

    summary = []

    for item in results:

        metrics = item["metrics"]

        pnl_change = (
            metrics["net_pnl"]
            - zero_cost_pnl
        )

        summary.append(
            {
                "cost_pct": item["cost_pct"],
                "trades": metrics["trades"],
                "win_rate": metrics["win_rate"],
                "net_pnl": metrics["net_pnl"],
                "avg_trade": metrics["avg_trade"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "pnl_change_vs_zero": pnl_change,
            }
        )

    summary_df = pd.DataFrame(summary)

    print(
        summary_df.to_string(
            index=False,
            formatters={
                "cost_pct": lambda value: f"{value:.2f}",
                "trades": lambda value: f"{int(value):,}",
                "win_rate": lambda value: f"{value:.2f}%",
                "net_pnl": lambda value: f"{value:+.2f}",
                "avg_trade": lambda value: f"{value:+.2f}",
                "profit_factor": lambda value: format_pf(value),
                "max_drawdown_pct": lambda value: f"{value:.2f}%",
                "pnl_change_vs_zero": lambda value: f"{value:+.2f}",
            },
        )
    )

    # -------------------------------------------------------------
    # Approximate transaction-cost break-even
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("APPROXIMATE TRANSACTION-COST BREAK-EVEN")
    print("=" * 96)

    zero_backtest = zero_cost["result"]

    total_round_trip_notional = sum(
        (
            float(trade.entry_price)
            + float(trade.exit_price)
        )
        * float(trade.quantity)
        for trade in zero_backtest.trades
    )

    if total_round_trip_notional <= 0:

        raise RuntimeError(
            "Unable to calculate transaction-cost break-even."
        )

    break_even_rate = (
        zero_cost_pnl
        / total_round_trip_notional
    )

    print(
        f"Approximate break-even transaction cost: "
        f"{break_even_rate * 100.0:.4f}%"
    )

    print(
        f"Approximate round-trip equivalent: "
        f"{break_even_rate * 200.0:.4f}%"
    )

    print("\nInterpretation:")

    print(
        "  This is a mathematical sensitivity threshold, "
        "not a recommended brokerage/fee assumption."
    )

    # -------------------------------------------------------------
    # Established baseline interpretation
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("ESTABLISHED BASELINE INTERPRETATION")
    print("=" * 96)

    print(
        "The SignalForge Phase 7 baseline uses "
        f"{format_rate(ESTABLISHED_BASELINE_COST)} transaction cost."
    )

    print(
        f"At that cost: P&L = "
        f"{established_metrics['net_pnl']:+.2f}, "
        f"PF = "
        f"{format_pf(established_metrics['profit_factor'])}"
    )

    # -------------------------------------------------------------
    # Research rules
    # -------------------------------------------------------------

    print("\n" + "=" * 96)
    print("RESEARCH RULES")
    print("=" * 96)

    print("1. Diagnostic analysis only.")
    print("2. Trading strategy remains frozen.")
    print("3. No transaction-cost optimization.")
    print("4. No candidate strategy.")
    print("5. No Development/Validation/OOS slicing.")
    print("6. Transaction cost is the only changed variable.")
    print("7. Trade signals must remain unchanged across cost levels.")
    print("8. Results must be interpreted before any strategy modification.")

    print("\n" + "=" * 96)
    print("PHASE 7.6 TRANSACTION-COST SENSITIVITY COMPLETE")
    print("=" * 96)


if __name__ == "__main__":
    main()

"""Final frozen-strategy validation gate for SignalForge."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

PERIODS = {
    "Development (2015-2020)": (
        "2015-01-01",
        "2020-12-31 23:59:59",
    ),
    "Validation (2021-2022)": (
        "2021-01-01",
        "2022-12-31 23:59:59",
    ),
    "Out-of-Sample (2023-2024)": (
        "2023-01-01",
        "2024-12-31 23:59:59",
    ),
}


def load_data() -> pd.DataFrame:
    """Load and validate the SignalForge research dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(
        required_columns.difference(data.columns)
    )

    if missing:
        raise ValueError(
            f"Dataset is missing columns: {missing}"
        )

    return data


def run_period(
    name: str,
    data: pd.DataFrame,
    config: StrategyConfig,
) -> dict:
    """Run one independent validation period."""

    start, end = PERIODS[name]

    period_data = data.loc[start:end].copy()

    if period_data.empty:
        raise ValueError(
            f"No data available for {name}."
        )

    signal_function = create_signal_function(
        period_data,
        config,
    )

    result = run_backtest(
        data=period_data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )

    trades = result.trades

    winning = sum(
        trade.net_pnl > 0
        for trade in trades
    )

    losing = sum(
        trade.net_pnl < 0
        for trade in trades
    )

    breakeven = sum(
        trade.net_pnl == 0
        for trade in trades
    )

    total_trades = len(trades)

    win_rate = (
        winning / total_trades * 100
        if total_trades
        else 0.0
    )

    long_trades = sum(
        trade.position.value == "LONG"
        for trade in trades
    )

    short_trades = sum(
        trade.position.value == "SHORT"
        for trade in trades
    )

    gross_profit = sum(
        trade.net_pnl
        for trade in trades
        if trade.net_pnl > 0
    )

    gross_loss = abs(
        sum(
            trade.net_pnl
            for trade in trades
            if trade.net_pnl < 0
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    # Calculate realized P&L directly from the Trade records.
    net_pnl = sum(
        trade.net_pnl
        for trade in trades
    )

    avg_trade = (
        net_pnl / total_trades
        if total_trades
        else 0.0
    )

    # Current SignalForge PerformanceMetrics uses
    # max_drawdown_pct, not max_drawdown.
    max_drawdown_pct = result.metrics.max_drawdown_pct

    transaction_costs = sum(
        trade.transaction_cost
        for trade in trades
    )

    return {
        "period": name,
        "rows": len(period_data),
        "start": period_data.index.min(),
        "end": period_data.index.max(),
        "trades": total_trades,
        "winning": winning,
        "losing": losing,
        "breakeven": breakeven,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "avg_trade": avg_trade,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
        "long": long_trades,
        "short": short_trades,
        "costs": transaction_costs,
    }


def print_result(result: dict) -> None:
    """Print one validation-period result."""

    print()
    print("=" * 72)
    print(result["period"])
    print("=" * 72)

    print(
        f"Rows            : {result['rows']:,}"
    )

    print(
        f"Range           : "
        f"{result['start']} → {result['end']}"
    )

    print(
        f"Trades          : {result['trades']:,}"
    )

    print(
        f"Winning         : {result['winning']:,}"
    )

    print(
        f"Losing          : {result['losing']:,}"
    )

    print(
        f"Breakeven       : {result['breakeven']:,}"
    )

    print(
        f"Win rate        : {result['win_rate']:.2f}%"
    )

    print(
        f"Net P&L         : ₹{result['net_pnl']:,.2f}"
    )

    print(
        f"Avg trade       : ₹{result['avg_trade']:,.2f}"
    )

    print(
        f"Profit factor   : {result['profit_factor']:.3f}"
    )

    print(
        f"Max drawdown    : "
        f"{result['max_drawdown_pct']:.2f}%"
    )

    print(
        f"LONG trades     : {result['long']:,}"
    )

    print(
        f"SHORT trades    : {result['short']:,}"
    )

    print(
        f"Transaction cost: ₹{result['costs']:,.2f}"
    )


def print_summary(results: list[dict]) -> None:
    """Print final cross-period summary."""

    print()
    print("=" * 72)
    print("FINAL SUMMARY")
    print("=" * 72)

    header = (
        f"{'Period':<27}"
        f"{'Trades':>8}"
        f"{'Win%':>8}"
        f"{'P&L':>14}"
        f"{'PF':>8}"
        f"{'DD%':>8}"
    )

    print(header)
    print("-" * len(header))

    for result in results:
        print(
            f"{result['period']:<27}"
            f"{result['trades']:>8}"
            f"{result['win_rate']:>8.2f}"
            f"{result['net_pnl']:>14.2f}"
            f"{result['profit_factor']:>8.3f}"
            f"{result['max_drawdown_pct']:>8.2f}"
        )


def evaluate_gate(results: list[dict]) -> None:
    """Evaluate the strict final validation gate."""

    print()
    print("=" * 72)
    print("VALIDATION GATE STATUS")
    print("=" * 72)

    profitable_periods = sum(
        result["net_pnl"] > 0
        for result in results
    )

    positive_pf_periods = sum(
        result["profit_factor"] > 1.0
        for result in results
    )

    print(
        f"Profitable periods : "
        f"{profitable_periods}/{len(results)}"
    )

    print(
        f"PF > 1 periods     : "
        f"{positive_pf_periods}/{len(results)}"
    )

    if (
        profitable_periods == len(results)
        and positive_pf_periods == len(results)
    ):
        print()
        print("GATE: PASS")
        print(
            "The frozen strategy is eligible "
            "to proceed to paper-trading preparation."
        )
    else:
        print()
        print("GATE: CONDITIONAL")
        print(
            "The frozen strategy does not meet "
            "the strict all-period profitability gate."
        )

    print()
    print(
        "IMPORTANT: This is research evidence only."
    )

    print(
        "It is NOT authorization for live trading."
    )


def main() -> None:
    """Run the final frozen-strategy validation gate."""

    print("=" * 72)
    print("SIGNALFORGE — FINAL STRATEGY VALIDATION GATE")
    print("=" * 72)

    print()
    print("LOCKED STRATEGY")
    print("-" * 72)
    print("EMA             : 20 / 50")
    print("RSI period      : 14")
    print("LONG RSI        : >= 60")
    print("ATR period      : 14")
    print("Minimum ATR     : 0.0")
    print("MTF             : 30m / 15m / 10m / 5m")
    print("RVOL            : Disabled when unavailable")
    print("Initial capital : ₹100,000.00")
    print("Quantity        : 1")
    print("Cost rate       : 0.0001 (0.01%)")

    print()
    print("RULE")
    print("-" * 72)
    print(
        "No parameter optimization is performed."
    )
    print(
        "All periods use the production strategy path."
    )
    print(
        "Development → Validation → OOS."
    )

    data = load_data()

    print()
    print("DATASET")
    print("-" * 72)
    print(f"Path            : {DATA_PATH}")
    print(f"Rows            : {len(data):,}")
    print(
        f"Range           : "
        f"{data.index.min()} → {data.index.max()}"
    )

    config = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        minimum_long_rsi=60.0,
        use_rvol=False,
    )

    results: list[dict] = []

    for name in PERIODS:
        print()
        print(
            f"Running {name}..."
        )

        result = run_period(
            name=name,
            data=data,
            config=config,
        )

        results.append(result)

        print_result(result)

    print_summary(results)

    evaluate_gate(results)


if __name__ == "__main__":
    main()
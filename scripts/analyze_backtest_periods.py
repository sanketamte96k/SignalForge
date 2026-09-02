from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


DEFAULT_DATA_PATH = Path(
    "data/historical/nifty50_1m_signalforge.csv"
)


PERIODS = {
    "Development (2015-2020)": (
        "2015-01-01",
        "2020-12-31",
    ),
    "Validation (2021-2022)": (
        "2021-01-01",
        "2022-12-31",
    ),
    "Out-of-Sample (2023-2024)": (
        "2023-01-01",
        "2024-12-31",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the unchanged SignalForge baseline "
            "across chronological periods."
        )
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help=(
            "Path to 1-minute OHLCV CSV "
            f"(default: {DEFAULT_DATA_PATH})"
        ),
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
        help="Initial capital.",
    )

    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
        help="Quantity per trade.",
    )

    parser.add_argument(
        "--cost-rate",
        type=float,
        default=0.0002,
        help="Transaction cost rate.",
    )

    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    """Load SignalForge market data."""

    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}"
        )

    df = pd.read_csv(
        path,
        parse_dates=["timestamp"],
    )

    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = (
        df.sort_values("timestamp")
        .set_index("timestamp")
    )

    if not isinstance(
        df.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "Data index must be a DatetimeIndex."
        )

    if df.index.has_duplicates:
        raise ValueError(
            "Data contains duplicate timestamps."
        )

    return df


def get_trade_pnl(trade) -> float:
    """Extract net P&L from a SignalForge Trade."""

    return float(trade.net_pnl)


def get_trade_position(trade) -> str:
    """Extract LONG/SHORT from a SignalForge Trade."""

    position = trade.position

    if hasattr(position, "value"):
        position = position.value

    return str(position).upper()


def get_trade_cost(trade) -> float:
    """Extract transaction cost from a SignalForge Trade."""

    return float(trade.transaction_cost)


def calculate_max_drawdown(
    trades,
    initial_capital: float,
) -> float:
    """
    Reconstruct the equity curve from completed trades
    and calculate maximum drawdown.
    """

    if not trades:
        return 0.0

    equity = float(initial_capital)
    peak = equity
    max_drawdown = 0.0

    for trade in trades:
        equity += get_trade_pnl(trade)

        if equity > peak:
            peak = equity

        if peak > 0:
            drawdown = (
                (equity - peak)
                / peak
                * 100.0
            )

            if drawdown < max_drawdown:
                max_drawdown = drawdown

    return abs(max_drawdown)


def calculate_metrics(
    result,
    initial_capital: float,
) -> dict:
    """Calculate performance metrics."""

    trades = result.trades

    if not trades:
        return {
            "trades": 0,
            "winning": 0,
            "losing": 0,
            "win_rate": 0.0,
            "pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "total_cost": 0.0,
        }

    # Convert Trade objects into P&L values.
    pnl_values = pd.Series(
        [
            get_trade_pnl(trade)
            for trade in trades
        ],
        dtype=float,
    )

    winning = pnl_values[
        pnl_values > 0
    ]

    losing = pnl_values[
        pnl_values < 0
    ]

    gross_profit = float(
        winning.sum()
    )

    gross_loss = abs(
        float(losing.sum())
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    else:
        profit_factor = float("inf")

    positions = [
        get_trade_position(trade)
        for trade in trades
    ]

    long_trades = sum(
        position == "LONG"
        for position in positions
    )

    short_trades = sum(
        position == "SHORT"
        for position in positions
    )

    total_cost = sum(
        get_trade_cost(trade)
        for trade in trades
    )

    max_drawdown = calculate_max_drawdown(
        trades,
        initial_capital,
    )

    total_trades = len(trades)

    return {
        "trades": total_trades,
        "winning": len(winning),
        "losing": len(losing),
        "win_rate": (
            len(winning)
            / total_trades
            * 100.0
        ),
        "pnl": float(
            pnl_values.sum()
        ),
        "avg_trade": float(
            pnl_values.mean()
        ),
        "profit_factor": profit_factor,
        "expectancy": float(
            pnl_values.mean()
        ),
        "max_drawdown": max_drawdown,
        "long_trades": long_trades,
        "short_trades": short_trades,
        "total_cost": total_cost,
    }


def print_period_result(
    name: str,
    metrics: dict,
) -> None:

    print()
    print("=" * 72)
    print(name)
    print("=" * 72)

    print(
        f"Trades          : "
        f"{metrics['trades']:,}"
    )

    print(
        f"Winning         : "
        f"{metrics['winning']:,}"
    )

    print(
        f"Losing          : "
        f"{metrics['losing']:,}"
    )

    print(
        f"Win rate        : "
        f"{metrics['win_rate']:.2f}%"
    )

    print(
        f"Net P&L         : "
        f"₹{metrics['pnl']:,.2f}"
    )

    print(
        f"Avg trade       : "
        f"₹{metrics['avg_trade']:,.2f}"
    )

    print(
        f"Profit factor   : "
        f"{metrics['profit_factor']:.2f}"
    )

    print(
        f"Expectancy      : "
        f"₹{metrics['expectancy']:,.2f}"
    )

    print(
        f"Max drawdown    : "
        f"{metrics['max_drawdown']:.2f}%"
    )

    print(
        f"LONG trades     : "
        f"{metrics['long_trades']:,}"
    )

    print(
        f"SHORT trades    : "
        f"{metrics['short_trades']:,}"
    )

    print(
        f"Transaction cost: "
        f"₹{metrics['total_cost']:,.2f}"
    )


def main() -> None:

    args = parse_args()

    print("=" * 72)
    print(
        "SIGNALFORGE — "
        "CHRONOLOGICAL ROBUSTNESS TEST"
    )
    print("=" * 72)

    print(
        f"Data            : "
        f"{args.data}"
    )

    print(
        f"Initial capital : "
        f"₹{args.capital:,.2f}"
    )

    print(
        f"Quantity        : "
        f"{args.quantity}"
    )

    print(
        f"Cost rate       : "
        f"{args.cost_rate}"
    )

    # ---------------------------------------------------------
    # LOAD DATA
    # ---------------------------------------------------------

    df = load_data(
        args.data
    )

    print(
        f"Full data range : "
        f"{df.index.min()} → "
        f"{df.index.max()}"
    )

    print(
        f"Total rows      : "
        f"{len(df):,}"
    )

    # ---------------------------------------------------------
    # UNCHANGED BASELINE
    # ---------------------------------------------------------

    config = StrategyConfig()

    all_results = []

    # ---------------------------------------------------------
    # RUN CHRONOLOGICAL PERIODS
    # ---------------------------------------------------------

    for name, (
        start_date,
        end_date,
    ) in PERIODS.items():

        start = pd.Timestamp(
            start_date
        )

        end = (
            pd.Timestamp(end_date)
            + pd.Timedelta(days=1)
        )

        period_df = df[
            (df.index >= start)
            & (df.index < end)
        ].copy()

        if period_df.empty:
            print()
            print(
                f"{name}: NO DATA"
            )
            continue

        print()
        print(
            f"Running {name}..."
        )

        print(
            f"Rows: {len(period_df):,} | "
            f"{period_df.index.min()} → "
            f"{period_df.index.max()}"
        )

        # Create indicators using ONLY this period.
        signal_function = (
            create_signal_function(
                period_df,
                config=config,
            )
        )

        result = run_backtest(
            period_df,
            signal_function=signal_function,
            initial_capital=args.capital,
            quantity=args.quantity,
            transaction_cost_rate=args.cost_rate,
        )

        metrics = calculate_metrics(
            result,
            args.capital,
        )

        print_period_result(
            name,
            metrics,
        )

        all_results.append(
            {
                "Period": name,
                "Trades": metrics["trades"],
                "Win Rate %": metrics[
                    "win_rate"
                ],
                "Net P&L": metrics[
                    "pnl"
                ],
                "Avg Trade": metrics[
                    "avg_trade"
                ],
                "Profit Factor": metrics[
                    "profit_factor"
                ],
                "Expectancy": metrics[
                    "expectancy"
                ],
                "Max DD %": metrics[
                    "max_drawdown"
                ],
                "LONG": metrics[
                    "long_trades"
                ],
                "SHORT": metrics[
                    "short_trades"
                ],
                "Costs": metrics[
                    "total_cost"
                ],
            }
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    if all_results:

        summary = pd.DataFrame(
            all_results
        )

        print(
            summary.to_string(
                index=False,
                formatters={
                    "Win Rate %": (
                        "{:.2f}".format
                    ),
                    "Net P&L": (
                        "₹{:,.2f}".format
                    ),
                    "Avg Trade": (
                        "₹{:,.2f}".format
                    ),
                    "Profit Factor": (
                        "{:.2f}".format
                    ),
                    "Expectancy": (
                        "₹{:,.2f}".format
                    ),
                    "Max DD %": (
                        "{:.2f}".format
                    ),
                    "Costs": (
                        "₹{:,.2f}".format
                    ),
                },
            )
        )

    print()
    print("=" * 72)
    print("IMPORTANT")
    print("=" * 72)

    print(
        "This test uses the unchanged baseline strategy."
    )

    print(
        "No parameter optimization was performed."
    )

    print(
        "Periods were evaluated independently."
    )

    print(
        "Results are research evidence only, "
        "not live-trading proof."
    )


if __name__ == "__main__":
    main()
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
            "Analyze LONG vs SHORT performance "
            "for the unchanged SignalForge baseline."
        )
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
    )

    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--cost-rate",
        type=float,
        default=0.0002,
    )

    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
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
            "Duplicate timestamps detected."
        )

    return df


def trade_position(trade) -> str:
    position = trade.position

    if hasattr(position, "value"):
        position = position.value

    return str(position).upper()


def trade_pnl(trade) -> float:
    return float(trade.net_pnl)


def trade_cost(trade) -> float:
    return float(trade.transaction_cost)


def calculate_direction_metrics(
    trades,
    direction: str,
) -> dict:

    selected = [
        trade
        for trade in trades
        if trade_position(trade) == direction
    ]

    if not selected:
        return {
            "trades": 0,
            "winning": 0,
            "losing": 0,
            "win_rate": 0.0,
            "pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "cost": 0.0,
        }

    pnl = pd.Series(
        [
            trade_pnl(trade)
            for trade in selected
        ],
        dtype=float,
    )

    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]

    gross_profit = float(
        winners.sum()
    )

    gross_loss = abs(
        float(losers.sum())
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit
            / gross_loss
        )
    else:
        profit_factor = float("inf")

    return {
        "trades": len(selected),
        "winning": len(winners),
        "losing": len(losers),
        "win_rate": (
            len(winners)
            / len(selected)
            * 100
        ),
        "pnl": float(pnl.sum()),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "expectancy": float(pnl.mean()),
        "avg_win": (
            float(winners.mean())
            if len(winners)
            else 0.0
        ),
        "avg_loss": (
            float(losers.mean())
            if len(losers)
            else 0.0
        ),
        "cost": sum(
            trade_cost(trade)
            for trade in selected
        ),
    }


def print_direction(
    direction: str,
    metrics: dict,
) -> None:

    print()
    print(
        f"--- {direction} ---"
    )

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
        f"Gross profit    : "
        f"₹{metrics['gross_profit']:,.2f}"
    )

    print(
        f"Gross loss      : "
        f"₹{metrics['gross_loss']:,.2f}"
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
        f"Average win     : "
        f"₹{metrics['avg_win']:,.2f}"
    )

    print(
        f"Average loss    : "
        f"₹{metrics['avg_loss']:,.2f}"
    )

    print(
        f"Transaction cost: "
        f"₹{metrics['cost']:,.2f}"
    )


def main() -> None:

    args = parse_args()

    print("=" * 72)
    print(
        "SIGNALFORGE — "
        "LONG vs SHORT DECOMPOSITION"
    )
    print("=" * 72)

    print(
        f"Data            : {args.data}"
    )

    print(
        f"Initial capital : "
        f"₹{args.capital:,.2f}"
    )

    print(
        f"Quantity        : {args.quantity}"
    )

    print(
        f"Cost rate       : {args.cost_rate}"
    )

    df = load_data(
        args.data
    )

    print(
        f"Full data range : "
        f"{df.index.min()} → "
        f"{df.index.max()}"
    )

    config = StrategyConfig()

    summary_rows = []

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
            print(
                f"\n{name}: NO DATA"
            )
            continue

        print()
        print("=" * 72)
        print(name)
        print("=" * 72)

        print(
            f"Rows: {len(period_df):,}"
        )

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

        trades = result.trades

        long_metrics = (
            calculate_direction_metrics(
                trades,
                "LONG",
            )
        )

        short_metrics = (
            calculate_direction_metrics(
                trades,
                "SHORT",
            )
        )

        print_direction(
            "LONG",
            long_metrics,
        )

        print_direction(
            "SHORT",
            short_metrics,
        )

        summary_rows.append(
            {
                "Period": name,
                "LONG Trades": long_metrics[
                    "trades"
                ],
                "LONG Win %": long_metrics[
                    "win_rate"
                ],
                "LONG P&L": long_metrics[
                    "pnl"
                ],
                "LONG PF": long_metrics[
                    "profit_factor"
                ],
                "LONG Exp": long_metrics[
                    "expectancy"
                ],
                "SHORT Trades": short_metrics[
                    "trades"
                ],
                "SHORT Win %": short_metrics[
                    "win_rate"
                ],
                "SHORT P&L": short_metrics[
                    "pnl"
                ],
                "SHORT PF": short_metrics[
                    "profit_factor"
                ],
                "SHORT Exp": short_metrics[
                    "expectancy"
                ],
            }
        )

    print()
    print("=" * 72)
    print("DIRECTIONAL SUMMARY")
    print("=" * 72)

    if summary_rows:

        summary = pd.DataFrame(
            summary_rows
        )

        print(
            summary.to_string(
                index=False,
                formatters={
                    "LONG Win %": (
                        "{:.2f}".format
                    ),
                    "LONG P&L": (
                        "₹{:,.2f}".format
                    ),
                    "LONG PF": (
                        "{:.2f}".format
                    ),
                    "LONG Exp": (
                        "₹{:,.2f}".format
                    ),
                    "SHORT Win %": (
                        "{:.2f}".format
                    ),
                    "SHORT P&L": (
                        "₹{:,.2f}".format
                    ),
                    "SHORT PF": (
                        "{:.2f}".format
                    ),
                    "SHORT Exp": (
                        "₹{:,.2f}".format
                    ),
                },
            )
        )

    print()
    print("=" * 72)
    print("RESEARCH RULE")
    print("=" * 72)
    print(
        "No strategy parameters were changed."
    )
    print(
        "This analysis only identifies where "
        "the baseline gains or loses."
    )
    print(
        "Do not use these results as evidence "
        "for live trading."
    )


if __name__ == "__main__":
    main()
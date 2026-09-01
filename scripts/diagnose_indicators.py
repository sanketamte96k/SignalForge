"""Diagnose indicator warm-up on historical NIFTY data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


def main() -> None:
    """Print indicator NaN diagnostics."""

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    config = StrategyConfig()

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    print("=" * 60)
    print("SignalForge — Indicator Diagnostic")
    print("=" * 60)

    for timeframe, frame in timeframe_data.items():

        print()
        print("-" * 60)
        print(f"TIMEFRAME: {timeframe}")
        print("-" * 60)

        indicator_columns = [
            "ema20",
            "ema50",
            "rsi",
            "rvol",
            "atr",
        ]

        print(
            f"Total candles: {len(frame)}"
        )

        for column in indicator_columns:

            missing = int(
                frame[column].isna().sum()
            )

            valid = int(
                frame[column].notna().sum()
            )

            print(
                f"{column:<6} "
                f"valid={valid:<5} "
                f"NaN={missing:<5}"
            )

        valid_rows = frame.dropna(
            subset=indicator_columns
        )

        print(
            f"ALL indicators valid: "
            f"{len(valid_rows)}"
        )

        if not valid_rows.empty:

            print(
                f"First valid: "
                f"{valid_rows.index[0]}"
            )

            print(
                f"Last valid:  "
                f"{valid_rows.index[-1]}"
            )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
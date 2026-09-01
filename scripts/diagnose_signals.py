"""Diagnose SignalForge signals on historical market data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.signals.signal_engine import Signal
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    evaluate_timestamp,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


def main() -> None:
    """Diagnose indicator readiness and generated signals."""

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    # NIFTY 50 index data has no usable volume.
    # Therefore RVOL is intentionally disabled.
    config = StrategyConfig(
        use_rvol=False,
    )

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    print("=" * 60)
    print("SignalForge — Signal Diagnosis")
    print("=" * 60)

    print()
    print("SOURCE DATA")
    print(
        f"Rows:  {len(data):,}"
    )
    print(
        f"Start: {data.index.min()}"
    )
    print(
        f"End:   {data.index.max()}"
    )

    print()
    print("VOLUME")
    print("-" * 60)

    volume_available = bool(
        (data["volume"] > 0).any()
    )

    print(
        f"Usable volume: "
        f"{volume_available}"
    )

    if not volume_available:
        print(
            "RVOL: disabled "
            "(NIFTY index volume unavailable)"
        )

    print()
    print("TIMEFRAME DATA")

    indicator_columns = [
        "ema20",
        "ema50",
        "rsi",
        "atr",
    ]

    for timeframe, frame in (
        timeframe_data.items()
    ):

        valid = frame.dropna(
            subset=indicator_columns
        )

        print(
            f"{timeframe:>3}: "
            f"{len(frame):>4} candles | "
            f"{len(valid):>4} indicator-valid"
        )

    print()
    print("SIGNAL COUNTS")
    print("-" * 60)

    counts = {
        Signal.BUY: 0,
        Signal.SELL: 0,
        Signal.NO_TRADE: 0,
    }

    insufficient = 0

    examples = {
        Signal.BUY: [],
        Signal.SELL: [],
        Signal.NO_TRADE: [],
    }

    insufficient_examples = []

    for timestamp in data.index:

        result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        if result is None:

            insufficient += 1

            if len(
                insufficient_examples
            ) < 3:
                insufficient_examples.append(
                    timestamp
                )

            continue

        counts[result.signal] += 1

        if len(
            examples[result.signal]
        ) < 3:
            examples[result.signal].append(
                (
                    timestamp,
                    result.score,
                    result.confidence,
                    result.reason,
                )
            )

    print(
        f"BUY:          "
        f"{counts[Signal.BUY]:>6}"
    )

    print(
        f"SELL:         "
        f"{counts[Signal.SELL]:>6}"
    )

    print(
        f"NO_TRADE:     "
        f"{counts[Signal.NO_TRADE]:>6}"
    )

    print(
        f"INSUFFICIENT: "
        f"{insufficient:>6}"
    )

    print()
    print("EXAMPLES")
    print("-" * 60)

    for signal in (
        Signal.BUY,
        Signal.SELL,
        Signal.NO_TRADE,
    ):

        print()
        print(
            f"{signal.value} examples:"
        )

        if not examples[signal]:
            print("  None")
            continue

        for (
            timestamp,
            score,
            confidence,
            reason,
        ) in examples[signal]:

            print(
                f"  {timestamp} | "
                f"score={score} | "
                f"confidence={confidence:.2f}% | "
                f"{reason}"
            )

    print()
    print("INSUFFICIENT examples:")

    if not insufficient_examples:
        print("  None")
    else:
        for timestamp in (
            insufficient_examples
        ):
            print(
                f"  {timestamp}"
            )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
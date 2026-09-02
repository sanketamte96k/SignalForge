"""Measure forward outcomes of SignalForge signals."""

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

HORIZONS = (
    5,
    15,
    30,
    60,
)


def load_data() -> pd.DataFrame:
    """Load historical market data."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    )

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    return data


def calculate_outcome(
    data: pd.DataFrame,
    position: str,
    entry_index: int,
    horizon: int,
) -> tuple[
    float | None,
    float | None,
    float | None,
]:
    """
    Calculate forward return, MFE, and MAE.

    All values are percentages relative
    to the entry price.

    For LONG:
        positive return = favorable
        positive MFE = favorable
        negative MAE = adverse

    For SHORT:
        positive return = favorable
        positive MFE = favorable
        negative MAE = adverse
    """

    end_index = min(
        entry_index + horizon,
        len(data) - 1,
    )

    if end_index <= entry_index:
        return None, None, None

    entry_price = float(
        data.iloc[entry_index]["close"]
    )

    future = data.iloc[
        entry_index + 1 : end_index + 1
    ]

    if future.empty:
        return None, None, None

    future_high = float(
        future["high"].max()
    )

    future_low = float(
        future["low"].min()
    )

    final_price = float(
        future.iloc[-1]["close"]
    )

    if position == "LONG":

        forward_return = (
            (final_price - entry_price)
            / entry_price
        ) * 100

        mfe = (
            (future_high - entry_price)
            / entry_price
        ) * 100

        mae = (
            (future_low - entry_price)
            / entry_price
        ) * 100

    else:

        forward_return = (
            (entry_price - final_price)
            / entry_price
        ) * 100

        mfe = (
            (entry_price - future_low)
            / entry_price
        ) * 100

        mae = (
            (entry_price - future_high)
            / entry_price
        ) * 100

    return (
        forward_return,
        mfe,
        mae,
    )


def main() -> None:
    """Run SignalForge signal outcome diagnostics."""

    print("=" * 60)
    print(
        "SignalForge — Signal Outcome Diagnostic"
    )
    print("=" * 60)

    data = load_data()

    print()
    print("SOURCE DATA")
    print("-" * 60)
    print(
        f"Rows:  {len(data):,}"
    )
    print(
        f"Start: {data.index.min()}"
    )
    print(
        f"End:   {data.index.max()}"
    )

    config = StrategyConfig(
        use_rvol=False
    )

    print()
    print("STRATEGY")
    print("-" * 60)
    print(
        f"EMA: {config.ema_fast_period} / "
        f"{config.ema_slow_period}"
    )
    print(
        f"RSI: {config.rsi_period}"
    )
    print(
        f"ATR: {config.atr_period}"
    )
    print(
        "RVOL: disabled"
    )

    print()
    print("Preparing indicators...")

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    records: list[dict] = []

    print("Evaluating signals...")

    for index in range(len(data)):

        timestamp = data.index[index]

        result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        if result is None:
            continue

        if result.signal not in (
            Signal.BUY,
            Signal.SELL,
        ):
            continue

        if result.signal == Signal.BUY:
            position = "LONG"
        else:
            position = "SHORT"

        record = {
            "timestamp": timestamp,
            "position": position,
            "entry_price": float(
                data.iloc[index]["close"]
            ),
            "score": result.score,
            "confidence": result.confidence,
        }

        for horizon in HORIZONS:

            (
                forward_return,
                mfe,
                mae,
            ) = calculate_outcome(
                data=data,
                position=position,
                entry_index=index,
                horizon=horizon,
            )

            record[
                f"return_{horizon}m"
            ] = forward_return

            record[
                f"mfe_{horizon}m"
            ] = mfe

            record[
                f"mae_{horizon}m"
            ] = mae

        records.append(record)

    results = pd.DataFrame(
        records
    )

    print()
    print("-" * 60)
    print("SIGNAL OUTCOMES")
    print("-" * 60)

    if results.empty:
        print(
            "No directional signals found."
        )
        return

    print(
        f"Directional signals: "
        f"{len(results):,}"
    )

    print(
        f"BUY signals:  "
        f"{(results['position'] == 'LONG').sum():,}"
    )

    print(
        f"SELL signals: "
        f"{(results['position'] == 'SHORT').sum():,}"
    )

    for position in (
        "LONG",
        "SHORT",
    ):

        subset = results[
            results["position"] == position
        ]

        print()
        print(
            f"{position} SIGNALS"
        )
        print("-" * 60)

        if subset.empty:
            print("None")
            continue

        for horizon in HORIZONS:

            return_column = (
                f"return_{horizon}m"
            )

            mfe_column = (
                f"mfe_{horizon}m"
            )

            mae_column = (
                f"mae_{horizon}m"
            )

            valid = subset[
                return_column
            ].dropna()

            if valid.empty:
                continue

            positive = (
                valid > 0
            ).sum()

            win_rate = (
                positive / len(valid)
            ) * 100

            average_return = (
                valid.mean()
            )

            average_mfe = (
                subset[mfe_column]
                .dropna()
                .mean()
            )

            average_mae = (
                subset[mae_column]
                .dropna()
                .mean()
            )

            print(
                f"{horizon:>2}m | "
                f"Win rate={win_rate:6.2f}% | "
                f"Avg return={average_return:8.4f}% | "
                f"Avg MFE={average_mfe:8.4f}% | "
                f"Avg MAE={average_mae:8.4f}%"
            )

    print()
    print("-" * 60)
    print("TOP SIGNAL EXAMPLES")
    print("-" * 60)

    display_columns = [
        "timestamp",
        "position",
        "entry_price",
        "score",
        "confidence",
        "return_5m",
        "return_15m",
        "return_30m",
        "return_60m",
        "mfe_60m",
        "mae_60m",
    ]

    print(
        results[
            display_columns
        ]
        .head(10)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
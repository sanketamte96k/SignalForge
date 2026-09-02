"""Measure forward outcomes from actual SignalForge entries."""

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

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = (
        required_columns
        - set(data.columns)
    )

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "Dataset index must be DatetimeIndex."
        )

    return data.sort_index()


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
    Calculate forward return, MFE and MAE.

    Returns percentages relative to entry price.
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

    elif position == "SHORT":

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

    else:
        raise ValueError(
            f"Unsupported position: {position}"
        )

    return (
        forward_return,
        mfe,
        mae,
    )


def is_new_entry(
    previous_signal: Signal | None,
    current_signal: Signal,
) -> bool:
    """
    Determine whether a signal represents
    a new position entry.

    BUY after BUY is not a new entry.
    SELL after SELL is not a new entry.

    BUY after SELL or NO_TRADE is an entry.
    SELL after BUY or NO_TRADE is an entry.
    """

    if current_signal not in (
        Signal.BUY,
        Signal.SELL,
    ):
        return False

    if previous_signal == current_signal:
        return False

    return True


def main() -> None:
    """Run actual-entry outcome diagnostics."""

    print("=" * 60)
    print(
        "SignalForge — Actual Entry Outcome Diagnostic"
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

    print("Evaluating signals...")

    records: list[dict] = []

    previous_signal: Signal | None = None

    for index in range(len(data)):

        timestamp = data.index[index]

        result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        if result is None:
            continue

        current_signal = result.signal

        if not is_new_entry(
            previous_signal,
            current_signal,
        ):
            if current_signal in (
                Signal.BUY,
                Signal.SELL,
            ):
                previous_signal = current_signal

            continue

        if current_signal == Signal.BUY:
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

        previous_signal = current_signal

    results = pd.DataFrame(
        records
    )

    print()
    print("-" * 60)
    print("ACTUAL ENTRY OUTCOMES")
    print("-" * 60)

    if results.empty:
        print(
            "No actual entries found."
        )
        return

    print(
        f"Actual entries: "
        f"{len(results):,}"
    )

    long_count = (
        results["position"] == "LONG"
    ).sum()

    short_count = (
        results["position"] == "SHORT"
    ).sum()

    print(
        f"LONG entries:  {long_count:,}"
    )

    print(
        f"SHORT entries: {short_count:,}"
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
            f"{position} ENTRIES"
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

            win_rate = (
                (valid > 0).sum()
                / len(valid)
            ) * 100

            average_return = (
                valid.mean()
            )

            median_return = (
                valid.median()
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
                f"Avg={average_return:8.4f}% | "
                f"Median={median_return:8.4f}% | "
                f"MFE={average_mfe:8.4f}% | "
                f"MAE={average_mae:8.4f}%"
            )

    print()
    print("-" * 60)
    print("ACTUAL ENTRY LIST")
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
        ].to_string(
            index=False
        )
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
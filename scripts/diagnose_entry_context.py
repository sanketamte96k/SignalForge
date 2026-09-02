"""Inspect indicator conditions at actual SignalForge entries."""

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

TIMEFRAMES = (
    "30m",
    "15m",
    "10m",
    "5m",
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


def get_latest_state(
    frame: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series | None:
    """
    Get the latest available timeframe candle
    at or before the signal timestamp.

    Higher timeframe candles use their opening
    timestamp as the index, so an exact timestamp
    match is not expected.
    """

    available = frame.loc[
        frame.index <= timestamp
    ]

    if available.empty:
        return None

    state = available.iloc[-1]

    required = [
        "close",
        "ema20",
        "ema50",
        "rsi",
        "atr",
    ]

    if state[required].isna().any():
        return None

    return state


def print_timeframe_state(
    timeframe: str,
    candle_time: pd.Timestamp,
    state: pd.Series,
) -> None:
    """Print indicator state for one timeframe."""

    close = float(
        state["close"]
    )

    ema20 = float(
        state["ema20"]
    )

    ema50 = float(
        state["ema50"]
    )

    rsi = float(
        state["rsi"]
    )

    atr = float(
        state["atr"]
    )

    ema20_distance = (
        (close - ema20)
        / ema20
    ) * 100

    ema50_distance = (
        (close - ema50)
        / ema50
    ) * 100

    if close > ema20 > ema50:
        direction = "LONG"

    elif close < ema20 < ema50:
        direction = "SHORT"

    else:
        direction = "NO_TRADE"

    print(
        f"{timeframe:>3} | "
        f"Candle={candle_time} | "
        f"Direction={direction}"
    )

    print(
        f"     | "
        f"Close={close:10.2f} | "
        f"EMA20={ema20:10.2f} | "
        f"EMA50={ema50:10.2f}"
    )

    print(
        f"     | "
        f"RSI={rsi:6.2f} | "
        f"ATR={atr:8.2f}"
    )

    print(
        f"     | "
        f"Price-EMA20={ema20_distance:+8.3f}% | "
        f"Price-EMA50={ema50_distance:+8.3f}%"
    )


def main() -> None:
    """Inspect actual strategy entries."""

    print("=" * 70)
    print(
        "SignalForge — Actual Entry Context Diagnostic"
    )
    print("=" * 70)

    data = load_data()

    config = StrategyConfig(
        use_rvol=False
    )

    print()
    print("SOURCE DATA")
    print("-" * 70)

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
    print("STRATEGY")
    print("-" * 70)

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
    print(
        "Preparing multi-timeframe indicators..."
    )

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    actual_entries: list[dict] = []

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

        if current_signal not in (
            Signal.BUY,
            Signal.SELL,
        ):
            continue

        if current_signal == previous_signal:
            continue

        position = (
            "LONG"
            if current_signal == Signal.BUY
            else "SHORT"
        )

        actual_entries.append(
            {
                "index": index,
                "timestamp": timestamp,
                "position": position,
                "score": result.score,
                "confidence": result.confidence,
            }
        )

        previous_signal = current_signal

    print()
    print("-" * 70)
    print("ACTUAL ENTRIES")
    print("-" * 70)

    if not actual_entries:
        print(
            "No actual entries found."
        )
        return

    print(
        f"Entries found: "
        f"{len(actual_entries)}"
    )

    for number, entry in enumerate(
        actual_entries,
        start=1,
    ):

        timestamp = entry["timestamp"]

        position = entry["position"]

        entry_price = float(
            data.iloc[
                entry["index"]
            ]["close"]
        )

        print()
        print("=" * 70)
        print(
            f"ENTRY {number} — "
            f"{position}"
        )
        print("=" * 70)

        print(
            f"Timestamp:  {timestamp}"
        )

        print(
            f"Price:      "
            f"{entry_price:.2f}"
        )

        print(
            f"Score:      "
            f"{entry['score']}"
        )

        print(
            f"Confidence: "
            f"{entry['confidence']:.2f}%"
        )

        print()
        print(
            "TIMEFRAME INDICATORS"
        )
        print("-" * 70)

        for timeframe in TIMEFRAMES:

            frame = timeframe_data[
                timeframe
            ]

            state = get_latest_state(
                frame,
                timestamp,
            )

            if state is None:
                print(
                    f"{timeframe:>3} | "
                    "No valid completed "
                    "indicator state."
                )
                continue

            candle_time = frame.loc[
                frame.index <= timestamp
            ].index[-1]

            print_timeframe_state(
                timeframe,
                candle_time,
                state,
            )

        print()
        print(
            "SIGNAL → TIMEFRAME TIMING"
        )
        print("-" * 70)

        for timeframe in TIMEFRAMES:

            frame = timeframe_data[
                timeframe
            ]

            available = frame.loc[
                frame.index <= timestamp
            ]

            if available.empty:
                continue

            candle_time = available.index[-1]

            minutes_difference = (
                timestamp - candle_time
            ).total_seconds() / 60

            print(
                f"{timeframe:>3} | "
                f"Signal={timestamp} | "
                f"Candle={candle_time} | "
                f"Age={minutes_difference:.0f}m"
            )

    print()
    print("=" * 70)
    print(
        "End of entry-context diagnostic."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
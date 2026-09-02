"""Analyze the quality of SignalForge directional signals."""

from pathlib import Path

import pandas as pd

from src.signals.signal_engine import Signal
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    generate_signals,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)

TIMEFRAMES = (
    "5m",
    "10m",
    "15m",
    "30m",
)


FORWARD_WINDOWS = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
}


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

    data = data.sort_index()

    return data


def add_forward_returns(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate future close-to-close returns."""

    result = data.copy()

    close = result["close"]

    for name, periods in FORWARD_WINDOWS.items():

        future_price = close.shift(-periods)

        result[
            f"forward_{name}"
        ] = (
            (
                future_price
                - close
            )
            / close
        ) * 100

    return result


def add_forward_excursions(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate future MFE and MAE.

    These are measured from the current close
    over the requested number of 1-minute candles.
    """

    result = data.copy()

    close = data["close"]
    high = data["high"]
    low = data["low"]

    for name, periods in FORWARD_WINDOWS.items():

        mfe = []
        mae = []

        for index in range(len(data)):

            start = index + 1
            end = start + periods

            if end > len(data):
                mfe.append(float("nan"))
                mae.append(float("nan"))
                continue

            entry_price = close.iloc[index]

            future_high = high.iloc[
                start:end
            ].max()

            future_low = low.iloc[
                start:end
            ].min()

            mfe.append(
                (
                    (
                        future_high
                        - entry_price
                    )
                    / entry_price
                )
                * 100
            )

            mae.append(
                (
                    (
                        future_low
                        - entry_price
                    )
                    / entry_price
                )
                * 100
            )

        result[
            f"mfe_{name}"
        ] = mfe

        result[
            f"mae_{name}"
        ] = mae

    return result


def latest_completed_candle(
    frame: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series | None:
    """
    Return the latest timeframe candle available
    at or before the signal timestamp.

    The strategy's indicators are based on completed
    higher-timeframe candles. We therefore use the
    latest candle whose timestamp is <= signal time.
    """

    available = frame.loc[
        frame.index <= timestamp
    ]

    if available.empty:
        return None

    return available.iloc[-1]


def attach_timeframe_indicators(
    data: pd.DataFrame,
    indicators: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Attach the actual timeframe indicator state
    used at every signal timestamp.
    """

    result = data.copy()

    for timeframe in TIMEFRAMES:

        frame = indicators[
            timeframe
        ]

        columns = (
            "close",
            "ema20",
            "ema50",
            "rsi",
            "atr",
        )

        for column in columns:

            result[
                f"{column}_{timeframe}"
            ] = float("nan")

        for timestamp in result.index:

            candle = latest_completed_candle(
                frame,
                timestamp,
            )

            if candle is None:
                continue

            for column in columns:

                if column not in candle.index:
                    continue

                value = candle[column]

                if pd.isna(value):
                    continue

                result.at[
                    timestamp,
                    f"{column}_{timeframe}",
                ] = float(value)

    return result


def add_diagnostic_features(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate normalized 5m diagnostic features."""

    result = data.copy()

    result[
        "rsi_5m_diagnostic"
    ] = result[
        "rsi_5m"
    ]

    result[
        "ema20_distance_pct"
    ] = (
        (
            result["close"]
            - result["ema20_5m"]
        )
        / result["ema20_5m"]
    ) * 100

    result[
        "ema50_distance_pct"
    ] = (
        (
            result["close"]
            - result["ema50_5m"]
        )
        / result["ema50_5m"]
    ) * 100

    result[
        "atr_pct"
    ] = (
        result["atr_5m"]
        / result["close"]
    ) * 100

    return result


def prepare_data(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare signals, indicators, and forward outcomes."""

    config = StrategyConfig()

    print(
        "Preparing timeframe indicators..."
    )

    indicators = (
        calculate_timeframe_indicators(
            data,
            config=config,
        )
    )

    print(
        "Generating official strategy signals..."
    )

    signals = generate_signals(
        data,
        config=config,
    )

    result = signals.copy()

    result = add_forward_returns(
        result
    )

    result = add_forward_excursions(
        result
    )

    result = attach_timeframe_indicators(
        result,
        indicators,
    )

    result = add_diagnostic_features(
        result
    )

    return result


def is_signal(
    value,
    signal: Signal,
) -> bool:
    """Safely compare a generated signal."""

    return value == signal


def directional_subset(
    data: pd.DataFrame,
    signal: Signal,
) -> pd.DataFrame:
    """Return rows containing one directional signal."""

    return data[
        data["signal"].apply(
            lambda value:
                is_signal(
                    value,
                    signal,
                )
        )
    ].copy()


def directional_return(
    values: pd.Series,
    signal: Signal,
) -> pd.Series:
    """
    Convert raw market returns into
    trade-direction returns.
    """

    values = values.dropna()

    if signal == Signal.SELL:
        return -values

    return values


def print_summary(
    data: pd.DataFrame,
) -> None:
    """Print official signal counts."""

    print()
    print(
        "SIGNAL QUALITY SUMMARY"
    )
    print("-" * 70)

    buy = directional_subset(
        data,
        Signal.BUY,
    )

    sell = directional_subset(
        data,
        Signal.SELL,
    )

    no_trade = data[
        data["signal"]
        == Signal.NO_TRADE
    ]

    print(
        f"Directional signals: "
        f"{len(buy) + len(sell)}"
    )

    print(
        f"BUY signals:  {len(buy)}"
    )

    print(
        f"SELL signals: {len(sell)}"
    )

    print(
        f"NO_TRADE:     {len(no_trade)}"
    )


def print_overall_performance(
    data: pd.DataFrame,
) -> None:
    """Print directional forward performance."""

    print()
    print(
        "DIRECTIONAL SIGNAL PERFORMANCE"
    )
    print("-" * 70)

    for signal in (
        Signal.BUY,
        Signal.SELL,
    ):

        subset = directional_subset(
            data,
            signal,
        )

        print()
        print(
            f"{signal.value}: "
            f"{len(subset)} signals"
        )

        for horizon in (
            "5m",
            "15m",
            "30m",
            "60m",
        ):

            values = directional_return(
                subset[
                    f"forward_{horizon}"
                ],
                signal,
            )

            if values.empty:
                continue

            win_rate = (
                values.gt(0).mean()
                * 100
            )

            print(
                f"  {horizon:>3} | "
                f"WR={win_rate:>6.2f}% | "
                f"Avg={values.mean():>9.4f}% | "
                f"Median={values.median():>9.4f}%"
            )


def print_bucket_analysis(
    data: pd.DataFrame,
    column: str,
    buckets: list[float],
    title: str,
) -> None:
    """Analyze directional performance by feature bucket."""

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    for signal in (
        Signal.BUY,
        Signal.SELL,
    ):

        subset = directional_subset(
            data,
            signal,
        )

        print()
        print(
            signal.value
        )
        print("-" * 70)

        for lower, upper in zip(
            buckets[:-1],
            buckets[1:],
        ):

            bucket = subset[
                (
                    subset[column]
                    >= lower
                )
                & (
                    subset[column]
                    < upper
                )
            ]

            if bucket.empty:
                continue

            values_5m = directional_return(
                bucket[
                    "forward_5m"
                ],
                signal,
            )

            values_15m = directional_return(
                bucket[
                    "forward_15m"
                ],
                signal,
            )

            values_30m = directional_return(
                bucket[
                    "forward_30m"
                ],
                signal,
            )

            values_60m = directional_return(
                bucket[
                    "forward_60m"
                ],
                signal,
            )

            if values_15m.empty:
                continue

            win_rate = (
                values_15m.gt(0).mean()
                * 100
            )

            print(
                f"{lower:>7.2f} to "
                f"{upper:>7.2f} | "
                f"N={len(bucket):>4} | "
                f"WR15={win_rate:>6.2f}% | "
                f"5m={values_5m.mean():>8.4f}% | "
                f"15m={values_15m.mean():>8.4f}% | "
                f"30m={values_30m.mean():>8.4f}% | "
                f"60m={values_60m.mean():>8.4f}%"
            )


def print_entry_context_sample(
    data: pd.DataFrame,
) -> None:
    """Print a few actual directional signal contexts."""

    directional = data[
        data["signal"].isin(
            [
                Signal.BUY,
                Signal.SELL,
            ]
        )
    ].copy()

    if directional.empty:
        return

    print()
    print("=" * 70)
    print(
        "SAMPLE SIGNAL CONTEXT"
    )
    print("=" * 70)

    columns = [
        "signal",
        "close",
        "score",
        "confidence",
        "rsi_5m",
        "ema20_distance_pct",
        "ema50_distance_pct",
        "atr_pct",
        "forward_15m",
        "forward_60m",
    ]

    available = [
        column
        for column in columns
        if column in directional.columns
    ]

    sample = directional[
        available
    ].head(10)

    print(
        sample.to_string()
    )


def main() -> None:
    """Run the complete diagnostic."""

    print(
        "=" * 70
    )
    print(
        "SignalForge — Signal Quality Diagnostic"
    )
    print(
        "=" * 70
    )

    data = load_data()

    print()
    print(
        "SOURCE DATA"
    )
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

    result = prepare_data(
        data
    )

    print_summary(
        result
    )

    print_overall_performance(
        result
    )

    print_bucket_analysis(
        result,
        "rsi_5m_diagnostic",
        [
            0,
            30,
            40,
            50,
            60,
            70,
            80,
            90,
            101,
        ],
        "RSI QUALITY ANALYSIS",
    )

    print_bucket_analysis(
        result,
        "ema20_distance_pct",
        [
            -2.0,
            -1.0,
            -0.5,
            -0.25,
            0.0,
            0.25,
            0.5,
            1.0,
            2.0,
        ],
        "PRICE DISTANCE FROM 5M EMA20",
    )

    print_bucket_analysis(
        result,
        "ema50_distance_pct",
        [
            -2.0,
            -1.0,
            -0.5,
            -0.25,
            0.0,
            0.25,
            0.5,
            1.0,
            2.0,
        ],
        "PRICE DISTANCE FROM 5M EMA50",
    )

    print_bucket_analysis(
        result,
        "atr_pct",
        [
            0.0,
            0.03,
            0.05,
            0.075,
            0.10,
            0.15,
            0.25,
            0.50,
            1.0,
        ],
        "5M ATR AS % OF PRICE",
    )

    print_entry_context_sample(
        result
    )

    print()
    print(
        "=" * 70
    )
    print(
        "Diagnostic complete."
    )
    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()
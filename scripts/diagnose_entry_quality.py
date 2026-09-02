"""SignalForge — Actual Backtest Entry Quality Diagnostic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.simulator import Position
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    create_signal_function,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)

INITIAL_CAPITAL = 100_000

CONFIG = StrategyConfig(
    ema_fast_period=20,
    ema_slow_period=50,
    rsi_period=14,
    atr_period=14,
    rvol_period=20,
    minimum_rvol=1.5,
    minimum_atr=0.0,
    use_rvol=False,
)


def load_data() -> pd.DataFrame:
    """Load historical NIFTY data."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    )

    required = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(
        required.difference(data.columns)
    )

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    data = data.sort_index()

    if data.index.has_duplicates:
        raise ValueError(
            "Dataset contains duplicate timestamps."
        )

    return data


def get_latest_indicator_candle(
    timeframe_data: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series | None:
    """Get the latest completed timeframe candle."""

    eligible = timeframe_data.loc[
        timeframe_data.index <= timestamp
    ]

    if eligible.empty:
        return None

    return eligible.iloc[-1]


def directional_return(
    position: Position,
    entry_price: float,
    future_price: float,
) -> float:
    """Calculate directional percentage return."""

    if position == Position.LONG:
        return (
            (future_price - entry_price)
            / entry_price
        ) * 100

    return (
        (entry_price - future_price)
        / entry_price
    ) * 100


def forward_price(
    data: pd.DataFrame,
    timestamp: pd.Timestamp,
    minutes: int,
) -> float | None:
    """Get the first available price at or after target time."""

    target = (
        timestamp
        + pd.Timedelta(minutes=minutes)
    )

    future = data.loc[
        data.index >= target
    ]

    if future.empty:
        return None

    return float(
        future.iloc[0]["close"]
    )


def calculate_mfe_mae(
    data: pd.DataFrame,
    timestamp: pd.Timestamp,
    position: Position,
    entry_price: float,
    minutes: int = 60,
) -> tuple[float, float]:
    """Calculate 60-minute maximum favorable/adverse excursion."""

    end_time = (
        timestamp
        + pd.Timedelta(minutes=minutes)
    )

    window = data.loc[
        (data.index > timestamp)
        & (data.index <= end_time)
    ]

    if window.empty:
        return 0.0, 0.0

    if position == Position.LONG:

        favorable = (
            (window["high"] - entry_price)
            / entry_price
        ) * 100

        adverse = (
            (window["low"] - entry_price)
            / entry_price
        ) * 100

    else:

        favorable = (
            (entry_price - window["low"])
            / entry_price
        ) * 100

        adverse = (
            (entry_price - window["high"])
            / entry_price
        ) * 100

    return (
        float(favorable.max()),
        float(adverse.min()),
    )


def build_entry_record(
    trade,
    data: pd.DataFrame,
    indicators: dict[str, pd.DataFrame],
) -> dict:
    """Build diagnostic information for one actual trade."""

    timestamp = pd.Timestamp(
        trade.entry_time
    )

    entry_price = float(
        trade.entry_price
    )

    timeframe_5m = get_latest_indicator_candle(
        indicators["5m"],
        timestamp,
    )

    if timeframe_5m is None:
        raise ValueError(
            f"No 5m indicator candle for {timestamp}"
        )

    ema20 = float(
        timeframe_5m["ema20"]
    )

    ema50 = float(
        timeframe_5m["ema50"]
    )

    rsi = float(
        timeframe_5m["rsi"]
    )

    atr = float(
        timeframe_5m["atr"]
    )

    candle_time = pd.Timestamp(
        timeframe_5m.name
    )

    signal_age = (
        timestamp - candle_time
    ).total_seconds() / 60

    forward = {}

    for label, minutes in (
        ("5m", 5),
        ("15m", 15),
        ("30m", 30),
        ("60m", 60),
    ):

        price = forward_price(
            data,
            timestamp,
            minutes,
        )

        if price is None:
            forward[label] = np.nan
        else:
            forward[label] = directional_return(
                trade.position,
                entry_price,
                price,
            )

    mfe, mae = calculate_mfe_mae(
        data=data,
        timestamp=timestamp,
        position=trade.position,
        entry_price=entry_price,
        minutes=60,
    )

    return {
        "timestamp": timestamp,
        "position": trade.position.value,
        "entry_price": entry_price,

        "trade_net_pnl": float(
            trade.net_pnl
        ),

        "trade_return_pct": float(
            trade.return_pct
        ),

        "signal_age_minutes": signal_age,

        "rsi_5m": rsi,

        "ema20_distance_pct": (
            (entry_price - ema20)
            / ema20
        ) * 100,

        "ema50_distance_pct": (
            (entry_price - ema50)
            / ema50
        ) * 100,

        "atr_pct": (
            atr
            / entry_price
        ) * 100,

        "forward_5m": forward["5m"],
        "forward_15m": forward["15m"],
        "forward_30m": forward["30m"],
        "forward_60m": forward["60m"],

        "mfe_60m": mfe,
        "mae_60m": mae,
    }


def print_header(
    title: str,
) -> None:
    """Print section header."""

    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def print_performance(
    frame: pd.DataFrame,
) -> None:
    """Print forward performance."""

    print_header(
        "FORWARD PERFORMANCE OF ACTUAL TRADES"
    )

    for position in (
        "LONG",
        "SHORT",
    ):

        subset = frame[
            frame["position"] == position
        ]

        print()
        print(position)
        print("-" * 70)

        if subset.empty:
            print("No trades.")
            continue

        for period in (
            "5m",
            "15m",
            "30m",
            "60m",
        ):

            column = (
                f"forward_{period}"
            )

            values = subset[column].dropna()

            if values.empty:
                print(
                    f"{period:>3} | No data"
                )
                continue

            win_rate = (
                (values > 0).mean()
                * 100
            )

            print(
                f"{period:>3} | "
                f"N={len(values):2d} | "
                f"WR={win_rate:6.2f}% | "
                f"Avg={values.mean():8.4f}% | "
                f"Median={values.median():8.4f}%"
            )


def print_quality_factors(
    frame: pd.DataFrame,
) -> None:
    """Print indicator quality statistics."""

    print_header(
        "ENTRY QUALITY FACTORS"
    )

    for position in (
        "LONG",
        "SHORT",
    ):

        subset = frame[
            frame["position"] == position
        ]

        print()
        print(position)
        print("-" * 70)

        if subset.empty:
            print("No trades.")
            continue

        print(
            f"RSI 5m mean: "
            f"{subset['rsi_5m'].mean():.2f}"
        )

        print(
            f"EMA20 distance mean: "
            f"{subset['ema20_distance_pct'].mean():.4f}%"
        )

        print(
            f"EMA50 distance mean: "
            f"{subset['ema50_distance_pct'].mean():.4f}%"
        )

        print(
            f"ATR % price mean: "
            f"{subset['atr_pct'].mean():.4f}%"
        )

        print(
            f"Signal age mean: "
            f"{subset['signal_age_minutes'].mean():.2f}m"
        )

        print(
            f"60m MFE mean: "
            f"{subset['mfe_60m'].mean():.4f}%"
        )

        print(
            f"60m MAE mean: "
            f"{subset['mae_60m'].mean():.4f}%"
        )


def print_entry_table(
    frame: pd.DataFrame,
) -> None:
    """Print detailed actual entry table."""

    print_header(
        "ACTUAL ENTRY LIST"
    )

    if frame.empty:
        print("No entries.")
        return

    display = frame.copy()

    display["entry_price"] = (
        display["entry_price"]
        .round(2)
    )

    numeric_columns = [
        "trade_net_pnl",
        "trade_return_pct",
        "signal_age_minutes",
        "rsi_5m",
        "ema20_distance_pct",
        "ema50_distance_pct",
        "atr_pct",
        "forward_5m",
        "forward_15m",
        "forward_30m",
        "forward_60m",
        "mfe_60m",
        "mae_60m",
    ]

    for column in numeric_columns:
        display[column] = (
            display[column]
            .round(4)
        )

    print(
        display.to_string(
            index=False
        )
    )


def main() -> None:
    """Run the diagnostic."""

    print(
        "=" * 70
    )

    print(
        "SignalForge — "
        "Entry Quality & Freshness Diagnostic"
    )

    print(
        "=" * 70
    )

    data = load_data()

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
        f"EMA: {CONFIG.ema_fast_period} / "
        f"{CONFIG.ema_slow_period}"
    )

    print(
        f"RSI: {CONFIG.rsi_period}"
    )

    print(
        f"ATR: {CONFIG.atr_period}"
    )

    print(
        "RVOL: "
        f"{'enabled' if CONFIG.use_rvol else 'disabled'}"
    )

    print()
    print(
        "Preparing timeframe indicators..."
    )

    indicators = (
        calculate_timeframe_indicators(
            data,
            config=CONFIG,
        )
    )

    print(
        "Generating official strategy..."
    )

    signal_function = (
        create_signal_function(
            data,
            config=CONFIG,
        )
    )

    print(
        "Running official backtest..."
    )

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
    )

    print(
        f"Actual completed trades: "
        f"{len(result.trades)}"
    )

    if not result.trades:
        print()
        print(
            "No completed trades were produced."
        )
        return

    records = []

    for trade in result.trades:

        records.append(
            build_entry_record(
                trade=trade,
                data=data,
                indicators=indicators,
            )
        )

    frame = pd.DataFrame(
        records
    )

    frame = frame.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    print_performance(
        frame
    )

    print_quality_factors(
        frame
    )

    print_entry_table(
        frame
    )

    print()
    print("=" * 70)

    print(
        "Diagnostic complete."
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()
"""Verify real historical market data for SignalForge."""

from pathlib import Path

import pandas as pd

from src.data.downloader import load_market_data
from src.data.session import (
    MARKET_CLOSE,
    MARKET_OPEN,
    prepare_market_session,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


def verify_dataset(
    path: str | Path = DATA_PATH,
) -> pd.DataFrame:
    """Load and verify a historical market dataset."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Historical dataset not found: {path}"
        )

    data = load_market_data(path)

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "Historical dataset contains duplicate timestamps."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Historical dataset index is not sorted."
        )

    prepared = prepare_market_session(data)

    if len(prepared) != len(data):
        raise ValueError(
            "Historical dataset contains "
            "timestamps outside the market session."
        )

    if prepared.index.time.min() < MARKET_OPEN:
        raise ValueError(
            "Dataset contains data before market open."
        )

    if prepared.index.time.max() > MARKET_CLOSE:
        raise ValueError(
            "Dataset contains data after market close."
        )

    daily_counts = prepared.groupby(
        prepared.index.date
    ).size()

    if daily_counts.empty:
        raise ValueError(
            "No trading sessions found."
        )

    if daily_counts.min() != 375:
        raise ValueError(
            "At least one trading day does not "
            "contain the expected 375 one-minute candles."
        )

    if daily_counts.max() != 375:
        raise ValueError(
            "At least one trading day contains "
            "more than the expected 375 candles."
        )

    return prepared


def main() -> None:
    """Run historical dataset verification."""

    print("Verifying SignalForge historical dataset...")
    print(f"File: {DATA_PATH}")

    data = verify_dataset()

    daily_counts = data.groupby(
        data.index.date
    ).size()

    print()
    print("VERIFICATION PASSED")
    print("-------------------")
    print(f"Rows: {len(data)}")
    print(f"Trading days: {len(daily_counts)}")
    print(f"Market open: {MARKET_OPEN}")
    print(f"Market close: {MARKET_CLOSE}")
    print(f"Start: {data.index.min()}")
    print(f"End: {data.index.max()}")
    print()
    print("Candles per trading day:")
    print(daily_counts)


if __name__ == "__main__":
    main()
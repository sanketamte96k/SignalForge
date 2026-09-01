"""Download extended NIFTY 50 intraday data in safe chunks."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.data.downloader import (
    download_market_data,
    save_market_data,
)


TICKER = "^NSEI"
INTERVAL = "1m"

# Yahoo Finance currently limits historical 1-minute
# data to a short intraday lookback window.
#
# Keep this conservative so every request remains valid.
CHUNK_DAYS = 7

START_DATE = "2026-08-01"
END_DATE = "2026-09-01"

OUTPUT_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


def build_date_chunks(
    start_date: str,
    end_date: str,
    chunk_days: int,
) -> list[tuple[str, str]]:
    """Build non-overlapping date chunks."""

    if chunk_days <= 0:
        raise ValueError(
            "chunk_days must be greater than zero."
        )

    start = datetime.strptime(
        start_date,
        "%Y-%m-%d",
    )

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d",
    )

    if start >= end:
        raise ValueError(
            "start_date must be before end_date."
        )

    chunks = []

    current = start

    while current < end:

        chunk_end = min(
            current + timedelta(
                days=chunk_days
            ),
            end,
        )

        chunks.append(
            (
                current.strftime(
                    "%Y-%m-%d"
                ),
                chunk_end.strftime(
                    "%Y-%m-%d"
                ),
            )
        )

        current = chunk_end

    return chunks


def combine_chunks(
    chunks: list[pd.DataFrame],
) -> pd.DataFrame:
    """Combine downloaded chunks safely."""

    if not chunks:
        raise ValueError(
            "No market-data chunks were downloaded."
        )

    combined = pd.concat(
        chunks,
        axis=0,
    )

    combined = combined[
        ~combined.index.duplicated(
            keep="first"
        )
    ]

    combined = combined.sort_index()

    if combined.empty:
        raise ValueError(
            "Combined market data is empty."
        )

    return combined


def main() -> None:
    """Download and combine historical NIFTY data."""

    print("=" * 60)
    print(
        "SignalForge — Extended NIFTY 50 Downloader"
    )
    print("=" * 60)

    chunks = build_date_chunks(
        START_DATE,
        END_DATE,
        CHUNK_DAYS,
    )

    print()
    print(
        f"Requested range: "
        f"{START_DATE} → {END_DATE}"
    )

    print(
        f"Chunk size:      "
        f"{CHUNK_DAYS} days"
    )

    print(
        f"Chunks:          "
        f"{len(chunks)}"
    )

    downloaded = []

    for number, (
        chunk_start,
        chunk_end,
    ) in enumerate(
        chunks,
        start=1,
    ):

        print()
        print(
            f"[{number}/{len(chunks)}] "
            f"{chunk_start} → {chunk_end}"
        )

        try:

            data = download_market_data(
                ticker=TICKER,
                start=chunk_start,
                end=chunk_end,
                interval=INTERVAL,
            )

        except Exception as exc:

            print(
                f"FAILED: {exc}"
            )

            continue

        print(
            f"Downloaded: "
            f"{len(data):,} rows"
        )

        if not data.empty:
            downloaded.append(data)

    if not downloaded:
        raise RuntimeError(
            "No chunks were downloaded successfully."
        )

    combined = combine_chunks(
        downloaded
    )

    # --------------------------------------------------------
    # Basic dataset summary
    # --------------------------------------------------------

    print()
    print("-" * 60)
    print("COMBINED DATA")
    print("-" * 60)

    print(
        f"Rows:   {len(combined):,}"
    )

    print(
        f"Start:  {combined.index.min()}"
    )

    print(
        f"End:    {combined.index.max()}"
    )

    print(
        f"Days:   "
        f"{combined.index.normalize().nunique()}"
    )

    # --------------------------------------------------------
    # Duplicate check
    # --------------------------------------------------------

    duplicates = (
        combined.index.duplicated()
        .sum()
    )

    print(
        f"Duplicate timestamps: "
        f"{duplicates}"
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output = save_market_data(
        combined,
        OUTPUT_PATH,
    )

    print()
    print(
        f"Saved dataset to: {output}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
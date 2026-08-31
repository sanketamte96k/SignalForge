from pathlib import Path

from src.data.downloader import (
    download_market_data,
    save_market_data,
)
from src.data.session import prepare_market_session


TICKER = "^NSEI"
INTERVAL = "1m"

# Keep the request below Yahoo Finance's
# 1-minute historical-data limit.
START = "2026-08-24"
END = "2026-08-31"

OUTPUT_PATH = Path(
    "data/historical/nifty50_1m.csv"
)


def main():
    print("Downloading NIFTY 50 historical data...")
    print(f"Ticker: {TICKER}")
    print(f"Interval: {INTERVAL}")
    print(f"Start: {START}")
    print(f"End: {END}")

    data = download_market_data(
        ticker=TICKER,
        start=START,
        end=END,
        interval=INTERVAL,
    )

    print(
        f"Downloaded {len(data)} rows."
    )

    data = prepare_market_session(data)

    print(
        "Rows after market-session filtering: "
        f"{len(data)}"
    )

    if data.empty:
        raise ValueError(
            "No regular-session market data "
            "remains after filtering."
        )

    save_market_data(
        data,
        OUTPUT_PATH,
    )

    print(
        f"Saved dataset to: {OUTPUT_PATH}"
    )

    print(
        f"Start: {data.index.min()}"
    )

    print(
        f"End: {data.index.max()}"
    )


if __name__ == "__main__":
    main()
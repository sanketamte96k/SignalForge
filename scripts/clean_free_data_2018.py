from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_DIR = Path("research/free_data_2018")
OUTPUT_DIR = Path("research/clean_data_2018")

STOCKS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]

REQUIRED_COLUMNS = [
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]


def clean_stock(symbol: str) -> dict:
    source = SOURCE_DIR / f"{symbol}.parquet"
    output = OUTPUT_DIR / f"{symbol}_2018.csv"

    df = pd.read_parquet(source)

    source_rows = len(df)

    # Normalize timestamp.
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Keep only valid 2018 records.
    df = df[df["Date"].dt.year == 2018].copy()
    year_rows = len(df)

    # Sort before all deterministic filtering.
    df = df.sort_values("Date")

    # Remove the 15:30 boundary candle.
    boundary_mask = df["Date"].dt.strftime("%H:%M") == "15:30"
    boundary_removed = int(boundary_mask.sum())
    df = df.loc[~boundary_mask].copy()

    # Remove non-regular evening-session candles.
    evening_mask = (
        (df["Date"].dt.time >= pd.Timestamp("17:30").time())
        & (df["Date"].dt.time <= pd.Timestamp("18:29").time())
    )
    evening_removed = int(evening_mask.sum())
    df = df.loc[~evening_mask].copy()

    # Identify invalid OHLC candles.
    invalid_ohlc_mask = (
        (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
        | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
    )

    invalid_ohlc_removed = int(invalid_ohlc_mask.sum())
    df = df.loc[~invalid_ohlc_mask].copy()

    # Remove rows with invalid timestamps.
    invalid_timestamp_mask = df["Date"].isna()
    invalid_timestamp_removed = int(invalid_timestamp_mask.sum())
    df = df.loc[~invalid_timestamp_mask].copy()

    # Keep only the required research columns.
    df = df[REQUIRED_COLUMNS].copy()

    # Ensure numeric OHLCV fields.
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # Drop rows that became invalid after numeric conversion.
    numeric_invalid_mask = df[
        ["Open", "High", "Low", "Close", "Volume"]
    ].isna().any(axis=1)

    numeric_invalid_removed = int(numeric_invalid_mask.sum())
    df = df.loc[~numeric_invalid_mask].copy()

    # Final deterministic ordering.
    df = df.sort_values("Date")

    # Final duplicate check.
    duplicate_count = int(df["Date"].duplicated().sum())

    # We do not silently deduplicate.
    if duplicate_count:
        raise ValueError(
            f"{symbol}: {duplicate_count} duplicate timestamps remain after cleaning."
        )

    # Final OHLC validation.
    bad_ohlc_final = int(
        (
            (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
            | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
        ).sum()
    )

    if bad_ohlc_final:
        raise ValueError(
            f"{symbol}: {bad_ohlc_final} invalid OHLC rows remain after cleaning."
        )

    # Final NaN validation.
    remaining_nan = int(
        df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        .isna()
        .sum()
        .sum()
    )

    if remaining_nan:
        raise ValueError(
            f"{symbol}: {remaining_nan} NaN values remain after cleaning."
        )

    # Session statistics.
    session_sizes = df.groupby(df["Date"].dt.date).size()

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    return {
        "symbol": symbol,
        "source_rows": source_rows,
        "2018_source_rows": year_rows,
        "15_30_removed": boundary_removed,
        "evening_session_removed": evening_removed,
        "invalid_ohlc_removed": invalid_ohlc_removed,
        "invalid_timestamp_removed": invalid_timestamp_removed,
        "numeric_invalid_removed": numeric_invalid_removed,
        "final_rows": len(df),
        "sessions": int(df["Date"].dt.date.nunique()),
        "min_bars_per_session": int(session_sizes.min()),
        "median_bars_per_session": float(session_sizes.median()),
        "max_bars_per_session": int(session_sizes.max()),
        "duplicate_timestamps_final": duplicate_count,
        "nan_values_final": remaining_nan,
        "bad_ohlc_final": bad_ohlc_final,
        "first_timestamp": str(df["Date"].min()),
        "last_timestamp": str(df["Date"].max()),
        "output": str(output),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for symbol in STOCKS:
        print(f"\n=== CLEANING {symbol} ===")

        result = clean_stock(symbol)
        results.append(result)

        print(f"Source rows:              {result['source_rows']}")
        print(f"2018 rows:                {result['2018_source_rows']}")
        print(f"15:30 candles removed:    {result['15_30_removed']}")
        print(f"Evening candles removed:  {result['evening_session_removed']}")
        print(f"Invalid OHLC removed:     {result['invalid_ohlc_removed']}")
        print(f"Final rows:               {result['final_rows']}")
        print(f"Sessions:                 {result['sessions']}")
        print(
            "Session bars min/median/max: "
            f"{result['min_bars_per_session']}/"
            f"{result['median_bars_per_session']}/"
            f"{result['max_bars_per_session']}"
        )
        print(f"Final duplicates:         {result['duplicate_timestamps_final']}")
        print(f"Final NaNs:               {result['nan_values_final']}")
        print(f"Final bad OHLC:           {result['bad_ohlc_final']}")
        print(f"First timestamp:          {result['first_timestamp']}")
        print(f"Last timestamp:           {result['last_timestamp']}")

    report = pd.DataFrame(results)
    report_path = OUTPUT_DIR / "audit_report.csv"
    report.to_csv(report_path, index=False)

    print("\n========================================")
    print("2018 CLEANING COMPLETE")
    print("========================================")
    print(f"Audit report: {report_path}")
    print(f"Stocks processed: {len(results)}")


if __name__ == "__main__":
    main()
"""Audit the free GitHub NIFTY 50 1-minute dataset."""

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/historical/nifty50_github_1m.csv")


def load_data() -> pd.DataFrame:
    df = pd.read_csv(INPUT_PATH)

    required = {
        "Instrument",
        "Date",
        "Time",
        "Open",
        "High",
        "Low",
        "Close",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        dayfirst=True,
        errors="coerce",
    )

    if df["timestamp"].isna().any():
        raise ValueError("Invalid timestamps found.")

    return df.sort_values("timestamp").reset_index(drop=True)


def audit_timestamps(df: pd.DataFrame) -> None:
    print("\n=== TIMESTAMP AUDIT ===")

    duplicates = df["timestamp"].duplicated().sum()
    seconds_nonzero = (df["timestamp"].dt.second != 0).sum()

    print(f"Duplicate timestamps : {duplicates:,}")
    print(f"Seconds != 00        : {seconds_nonzero:,}")

    # Round timestamps only for collision analysis.
    rounded = df["timestamp"].dt.floor("min")

    collisions = rounded.duplicated().sum()

    print(f"Collisions after floor : {collisions:,}")


def audit_regular_sessions(df: pd.DataFrame) -> pd.DataFrame:
    print("\n=== REGULAR SESSION AUDIT ===")

    start = pd.Timestamp("09:15:00").time()
    end = pd.Timestamp("15:29:00").time()

    regular = df[
        (df["timestamp"].dt.time >= start)
        & (df["timestamp"].dt.time <= end)
    ].copy()

    regular["date"] = regular["timestamp"].dt.date

    counts = regular.groupby("date").size()

    print(f"Regular-session rows : {len(regular):,}")
    print(f"Trading dates        : {len(counts):,}")
    print(f"Minimum rows/day     : {counts.min():,}")
    print(f"Maximum rows/day     : {counts.max():,}")
    print(f"Average rows/day     : {counts.mean():.2f}")

    incomplete = counts[counts < 370]

    print(f"Incomplete days <370 : {len(incomplete):,}")

    if not incomplete.empty:
        print("\nIncomplete regular sessions:")
        print(incomplete.to_string())

    return regular


def audit_gaps(regular: pd.DataFrame) -> None:
    print("\n=== GAP AUDIT ===")

    gaps = []

    for date, group in regular.groupby("date"):
        timestamps = (
            group["timestamp"]
            .dt.floor("min")
            .drop_duplicates()
            .sort_values()
            .reset_index(drop=True)
        )

        differences = timestamps.diff().dt.total_seconds().div(60)

        bad = differences[
            differences.notna() & (differences != 1)
        ]

        if not bad.empty:
            for index in bad.index:
                gaps.append(
                    {
                        "date": date,
                        "previous": timestamps.iloc[index - 1],
                        "current": timestamps.iloc[index],
                        "minutes": differences.iloc[index],
                    }
                )

    gap_df = pd.DataFrame(gaps)

    print(f"Non-1-minute gaps : {len(gap_df):,}")

    if not gap_df.empty:
        print("\nFirst 20 gaps:")
        print(gap_df.head(20).to_string(index=False))

        print("\nGap size distribution:")
        print(
            gap_df["minutes"]
            .value_counts()
            .sort_index()
            .head(20)
            .to_string()
        )


def audit_ohlc(df: pd.DataFrame) -> None:
    print("\n=== OHLC AUDIT ===")

    numeric = ["Open", "High", "Low", "Close"]

    for column in numeric:
        invalid = pd.to_numeric(df[column], errors="coerce").isna().sum()
        print(f"{column} non-numeric : {invalid:,}")

    high_invalid = (
        df["High"]
        < df[["Open", "Close", "Low"]].max(axis=1)
    ).sum()

    low_invalid = (
        df["Low"]
        > df[["Open", "Close", "High"]].min(axis=1)
    ).sum()

    non_positive = (
        df[["Open", "High", "Low", "Close"]] <= 0
    ).any(axis=1).sum()

    print(f"High below OHLC max : {high_invalid:,}")
    print(f"Low above OHLC min  : {low_invalid:,}")
    print(f"Non-positive prices : {non_positive:,}")


def audit_date_range(df: pd.DataFrame) -> None:
    print("\n=== DATE RANGE ===")

    print(f"First timestamp : {df['timestamp'].min()}")
    print(f"Last timestamp  : {df['timestamp'].max()}")

    years = df["timestamp"].dt.year.value_counts().sort_index()

    print("\nRows by year:")
    print(years.to_string())


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_PATH}"
        )

    print("SignalForge — NIFTY 50 Free Dataset Audit")
    print("=" * 50)

    df = load_data()

    print(f"Total rows : {len(df):,}")

    audit_date_range(df)
    audit_timestamps(df)

    regular = audit_regular_sessions(df)
    audit_gaps(regular)
    audit_ohlc(df)

    print("\n=== AUDIT COMPLETE ===")


if __name__ == "__main__":
    main()
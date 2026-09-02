"""Create a clean NIFTY 50 1-minute research dataset."""

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/historical/nifty50_github_1m.csv")
OUTPUT_PATH = Path("data/historical/nifty50_1m_research.csv")

SESSION_START = "09:15"
SESSION_END = "15:29"


def load_raw_data() -> pd.DataFrame:
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

    numeric_columns = ["Open", "High", "Low", "Close"]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if df[numeric_columns].isna().any().any():
        raise ValueError("Invalid OHLC values found.")

    return df.sort_values("timestamp").reset_index(drop=True)


def keep_regular_session(df: pd.DataFrame) -> pd.DataFrame:
    start = pd.Timestamp(SESSION_START).time()
    end = pd.Timestamp(SESSION_END).time()

    return df[
        (df["timestamp"].dt.time >= start)
        & (df["timestamp"].dt.time <= end)
    ].copy()


def remove_incomplete_sessions(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    df["date"] = df["timestamp"].dt.date

    daily_counts = df.groupby("date").size()

    # A complete regular NSE session should contain approximately
    # 375 one-minute candles.
    valid_dates = daily_counts[daily_counts >= 370].index

    incomplete_dates = sorted(
        set(daily_counts.index) - set(valid_dates)
    )

    cleaned = df[df["date"].isin(valid_dates)].copy()

    return cleaned, incomplete_dates


def normalize_to_minutes(df: pd.DataFrame) -> pd.DataFrame:
    # The source contains some second-level timestamps in 2015.
    # Convert all timestamps into their minute bucket.
    df["timestamp"] = df["timestamp"].dt.floor("min")

    # Multiple source records can occur inside the same minute.
    # Rebuild one OHLC candle from all records in that minute.
    df = (
        df.groupby("timestamp", as_index=False)
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


def validate_clean_data(df: pd.DataFrame) -> None:
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps remain.")

    invalid_high = (
        df["High"]
        < df[["Open", "Close", "Low"]].max(axis=1)
    )

    invalid_low = (
        df["Low"]
        > df[["Open", "Close", "High"]].min(axis=1)
    )

    non_positive = (
        df[["Open", "High", "Low", "Close"]] <= 0
    ).any(axis=1)

    if invalid_high.any():
        raise ValueError("Invalid High values remain.")

    if invalid_low.any():
        raise ValueError("Invalid Low values remain.")

    if non_positive.any():
        raise ValueError("Non-positive OHLC values remain.")

    if (df["timestamp"].dt.second != 0).any():
        raise ValueError("Non-zero seconds remain.")

    start = pd.Timestamp(SESSION_START).time()
    end = pd.Timestamp(SESSION_END).time()

    outside_session = (
        (df["timestamp"].dt.time < start)
        | (df["timestamp"].dt.time > end)
    )

    if outside_session.any():
        raise ValueError("Out-of-session timestamps remain.")


def print_summary(
    raw: pd.DataFrame,
    regular: pd.DataFrame,
    cleaned: pd.DataFrame,
    incomplete_dates: list,
) -> None:
    print()
    print("=" * 60)
    print("SignalForge — Clean NIFTY 50 Research Dataset")
    print("=" * 60)

    print(f"Raw rows                  : {len(raw):,}")
    print(f"Regular-session rows      : {len(regular):,}")
    print(f"Removed incomplete days   : {len(incomplete_dates):,}")
    print(f"Clean rows                : {len(cleaned):,}")

    print()
    print("DATE RANGE")
    print(f"Start : {cleaned['timestamp'].min()}")
    print(f"End   : {cleaned['timestamp'].max()}")

    print()
    print("TRADING DAYS")
    print(f"Days : {cleaned['timestamp'].dt.date.nunique():,}")

    daily_counts = cleaned.groupby(
        cleaned["timestamp"].dt.date
    ).size()

    print(f"Min candles/day : {daily_counts.min()}")
    print(f"Max candles/day : {daily_counts.max()}")
    print(f"Avg candles/day : {daily_counts.mean():.2f}")

    print()
    print("TIMESTAMP QUALITY")
    print(
        "Duplicate timestamps :",
        cleaned["timestamp"].duplicated().sum(),
    )
    print(
        "Seconds != 00        :",
        (cleaned["timestamp"].dt.second != 0).sum(),
    )

    print()
    print("INCOMPLETE DAYS REMOVED")

    if incomplete_dates:
        for date in incomplete_dates:
            print(f"  {date}")
    else:
        print("  None")

    print()
    print(f"Output: {OUTPUT_PATH}")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input dataset not found: {INPUT_PATH}"
        )

    raw = load_raw_data()

    regular = keep_regular_session(raw)

    regular, incomplete_dates = remove_incomplete_sessions(
        regular
    )

    cleaned = normalize_to_minutes(regular)

    validate_clean_data(cleaned)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cleaned.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print_summary(
        raw=raw,
        regular=keep_regular_session(raw),
        cleaned=cleaned,
        incomplete_dates=incomplete_dates,
    )


if __name__ == "__main__":
    main()
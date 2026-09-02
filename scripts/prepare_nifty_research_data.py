"""Prepare the cleaned NIFTY 50 research dataset for SignalForge."""

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/historical/nifty50_1m_research.csv")
OUTPUT_PATH = Path("data/historical/nifty50_1m_signalforge.csv")


def load_data() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    required = {
        "timestamp",
        "Open",
        "High",
        "Low",
        "Close",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    if df["timestamp"].isna().any():
        raise ValueError("Invalid timestamps found.")

    for column in ["Open", "High", "Low", "Close"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    if df[["Open", "High", "Low", "Close"]].isna().any().any():
        raise ValueError("Invalid OHLC values found.")

    return df.sort_values("timestamp").reset_index(drop=True)


def validate(df: pd.DataFrame) -> None:
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found.")

    if (df["timestamp"].dt.second != 0).any():
        raise ValueError("Non-minute timestamps found.")

    if (
        df["High"]
        < df[["Open", "Close", "Low"]].max(axis=1)
    ).any():
        raise ValueError("Invalid High values found.")

    if (
        df["Low"]
        > df[["Open", "Close", "High"]].min(axis=1)
    ).any():
        raise ValueError("Invalid Low values found.")

    if (
        df[["Open", "High", "Low", "Close"]] <= 0
    ).any().any():
        raise ValueError("Non-positive prices found.")

    start = pd.Timestamp("09:15").time()
    end = pd.Timestamp("15:29").time()

    outside = (
        (df["timestamp"].dt.time < start)
        | (df["timestamp"].dt.time > end)
    )

    if outside.any():
        raise ValueError("Out-of-session timestamps found.")


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    # SignalForge expects lowercase OHLC column names.
    result = df[
        ["timestamp", "Open", "High", "Low", "Close"]
    ].copy()

    result.columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
    ]

    # NIFTY 50 index data has no usable volume.
    # Keep volume explicitly unavailable so SignalForge
    # can automatically disable RVOL.
    result["volume"] = 0.0

    return result


def main() -> None:
    df = load_data()

    validate(df)

    result = prepare(df)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("=" * 60)
    print("SignalForge — Research Data Preparation")
    print("=" * 60)
    print(f"Input rows  : {len(df):,}")
    print(f"Output rows : {len(result):,}")
    print(f"Start       : {result['timestamp'].min()}")
    print(f"End         : {result['timestamp'].max()}")
    print(f"Columns     : {list(result.columns)}")
    print(f"Output      : {OUTPUT_PATH}")
    print()
    print("Volume      : unavailable (set to 0)")
    print("RVOL        : will be automatically disabled")


if __name__ == "__main__":
    main()
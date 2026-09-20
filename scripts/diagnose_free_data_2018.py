"""
SignalForge — 2018 Free Data Gap Diagnostic

Research-only diagnostic.

Purpose:
    Identify exactly where missing 1-minute candles occur.

This script:
    - Does NOT modify source data.
    - Does NOT modify cleaned data.
    - Does NOT modify SignalForge validators.
    - Does NOT download anything.
    - Does NOT call APIs.
"""

from pathlib import Path
import sys

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PATHS
# ============================================================

INPUT_DIR = (
    PROJECT_ROOT
    / "research"
    / "clean_data_2018"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "research"
    / "validation_2018"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# STOCKS
# ============================================================

SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]


# ============================================================
# MARKET SESSION
# ============================================================

SESSION_START = 9 * 60 + 15
SESSION_END = 15 * 60 + 29


# ============================================================
# LOAD
# ============================================================

def load_stock(symbol):

    path = (
        INPUT_DIR
        / f"{symbol}_2018.csv"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

    df = pd.read_csv(path)

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["Date"]
    )

    df = df.sort_values(
        "Date"
    )

    return df


# ============================================================
# ANALYZE ONE STOCK
# ============================================================

def diagnose(symbol):

    print()
    print("=" * 60)
    print(f"DIAGNOSING {symbol}")
    print("=" * 60)

    df = load_stock(symbol)

    # --------------------------------------------------------
    # Only regular daytime market session
    # --------------------------------------------------------

    minutes = (
        df["Date"].dt.hour * 60
        + df["Date"].dt.minute
    )

    regular = df[
        (minutes >= SESSION_START)
        & (minutes <= SESSION_END)
    ].copy()

    regular["date_only"] = (
        regular["Date"].dt.date
    )

    print(
        f"Regular-session rows: "
        f"{len(regular):,}"
    )

    # --------------------------------------------------------
    # Expected timestamps
    # --------------------------------------------------------

    missing_records = []
    session_records = []

    for session_date, group in regular.groupby(
        "date_only"
    ):

        actual = pd.DatetimeIndex(
            group["Date"]
        ).sort_values()

        expected = pd.date_range(
            start=pd.Timestamp(
                session_date
            ) + pd.Timedelta(
                hours=9,
                minutes=15,
            ),
            end=pd.Timestamp(
                session_date
            ) + pd.Timedelta(
                hours=15,
                minutes=29,
            ),
            freq="1min",
        )

        actual_set = set(actual)
        expected_set = set(expected)

        missing = sorted(
            expected_set
            - actual_set
        )

        # ----------------------------------------------------
        # Session summary
        # ----------------------------------------------------

        session_records.append(
            {
                "symbol": symbol,
                "date": str(session_date),
                "actual_bars": len(actual),
                "expected_bars": len(expected),
                "missing_bars": len(missing),
                "first_timestamp": (
                    str(actual.min())
                    if len(actual)
                    else ""
                ),
                "last_timestamp": (
                    str(actual.max())
                    if len(actual)
                    else ""
                ),
            }
        )

        # ----------------------------------------------------
        # Missing timestamp records
        # ----------------------------------------------------

        for timestamp in missing:

            missing_records.append(
                {
                    "symbol": symbol,
                    "date": str(session_date),
                    "missing_timestamp": timestamp,
                }
            )

    # --------------------------------------------------------
    # DataFrames
    # --------------------------------------------------------

    missing_df = pd.DataFrame(
        missing_records
    )

    sessions_df = pd.DataFrame(
        session_records
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_missing = len(
        missing_df
    )

    incomplete_sessions = int(
        (
            sessions_df["missing_bars"]
            > 0
        ).sum()
    )

    print()
    print(
        f"Incomplete sessions: "
        f"{incomplete_sessions}"
    )

    print(
        f"Missing 1-minute bars: "
        f"{total_missing}"
    )

    # --------------------------------------------------------
    # Show missing bars
    # --------------------------------------------------------

    if total_missing:

        print()
        print(
            "First 30 missing timestamps:"
        )

        print(
            missing_df.head(30).to_string(
                index=False
            )
        )

    else:

        print(
            "No missing timestamps."
        )

    # --------------------------------------------------------
    # Session length distribution
    # --------------------------------------------------------

    print()
    print(
        "Session bar distribution:"
    )

    print(
        sessions_df[
            "actual_bars"
        ].value_counts()
        .sort_index()
        .to_string()
    )

    # --------------------------------------------------------
    # Save reports
    # --------------------------------------------------------

    missing_path = (
        OUTPUT_DIR
        / f"{symbol}_missing_minutes.csv"
    )

    sessions_path = (
        OUTPUT_DIR
        / f"{symbol}_session_diagnostic.csv"
    )

    missing_df.to_csv(
        missing_path,
        index=False,
    )

    sessions_df.to_csv(
        sessions_path,
        index=False,
    )

    print()
    print(
        f"Missing report: {missing_path}"
    )

    print(
        f"Session report: {sessions_path}"
    )

    return {
        "symbol": symbol,
        "incomplete_sessions": incomplete_sessions,
        "missing_minutes": total_missing,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "SIGNALFORGE — 2018 GAP DIAGNOSTIC"
    )
    print("=" * 60)

    results = []

    for symbol in SYMBOLS:

        result = diagnose(
            symbol
        )

        results.append(
            result
        )

    summary = pd.DataFrame(
        results
    )

    summary_path = (
        OUTPUT_DIR
        / "gap_diagnostic_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    print()
    print("=" * 60)
    print(
        "GAP DIAGNOSTIC SUMMARY"
    )
    print("=" * 60)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print(
        f"Summary saved: {summary_path}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
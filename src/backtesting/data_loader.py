from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================
# SIGNALFORGE — BACKTEST DATA LOADER
# ============================================================

REQUIRED_COLUMNS = [
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]

SESSION_START = "09:15"
SESSION_END = "15:29"


@dataclass
class DataQualityReport:
    symbol: str
    year: int

    total_rows: int
    sessions: int

    complete_sessions: int
    incomplete_sessions: int

    missing_minutes: int

    duplicate_timestamps: int
    nan_values: int
    bad_ohlc: int

    zero_volume_rows: int

    first_timestamp: Optional[pd.Timestamp]
    last_timestamp: Optional[pd.Timestamp]

    excluded_sessions: list[str]

    @property
    def total_sessions(self) -> int:
        """Total calendar trading sessions observed before exclusion."""
        return self.complete_sessions + self.incomplete_sessions

    @property
    def usable(self) -> bool:
        return (
            self.total_rows > 0
            and self.sessions > 0
            and self.complete_sessions > 0
        )


@dataclass
class BacktestData:
    symbol: str
    year: int
    data: pd.DataFrame
    quality: DataQualityReport


class BacktestDataLoader:
    """
    Loads SignalForge cleaned historical data.

    Important:
    - Never invent missing candles.
    - Never forward-fill OHLC.
    - Never silently hide bad sessions.
    - Incomplete sessions can be excluded from backtesting.
    """

    def __init__(
        self,
        data_dir: str | Path = "research/clean_data_2018",
        expected_session_bars: int = 375,
    ):
        self.data_dir = Path(data_dir)
        self.expected_session_bars = expected_session_bars

    # ========================================================
    # FIND FILE
    # ========================================================

    def find_file(self, symbol: str, year: int) -> Path:
        filename = f"{symbol.upper()}_{year}.csv"
        path = self.data_dir / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Historical data file not found:\n{path}"
            )

        return path

    # ========================================================
    # LOAD RAW DATA
    # ========================================================

    def load(
        self,
        symbol: str,
        year: int,
        exclude_incomplete_sessions: bool = True,
    ) -> BacktestData:

        symbol = symbol.upper()

        path = self.find_file(symbol, year)

        df = pd.read_csv(path)

        # ----------------------------------------------------
        # Column validation & Boundary Normalization
        # ----------------------------------------------------

        col_lookup = {str(c).strip().lower(): c for c in df.columns}
        required_lower = ["date", "open", "high", "low", "close", "volume"]
        missing_columns = [
            req for req in required_lower
            if req not in col_lookup
        ]

        if missing_columns:
            raise ValueError(
                f"{symbol}: Missing required columns: {missing_columns}"
            )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        df["Date"] = pd.to_datetime(
            df[col_lookup["date"]],
            errors="coerce",
        )

        # ----------------------------------------------------
        # Canonical lowercase OHLCV columns
        # ----------------------------------------------------

        for req in ["open", "high", "low", "close", "volume"]:
            df[req] = pd.to_numeric(
                df[col_lookup[req]],
                errors="coerce",
            )

        # Retain capitalized aliases for backward compatibility
        df["Open"] = df["open"]
        df["High"] = df["high"]
        df["Low"] = df["low"]
        df["Close"] = df["close"]
        df["Volume"] = df["volume"]

        # ----------------------------------------------------
        # Remove invalid timestamps
        # ----------------------------------------------------

        df = df.dropna(subset=["Date"])

        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        df = df.sort_values("Date").reset_index(drop=True)

        # ----------------------------------------------------
        # Year filter
        # ----------------------------------------------------

        df = df[df["Date"].dt.year == year].copy()

        # ----------------------------------------------------
        # Regular NSE session
        #
        # 09:15 through 15:29 = 375 one-minute bars
        # ----------------------------------------------------

        time_mask = (
            (df["Date"].dt.time >= pd.Timestamp(SESSION_START).time())
            &
            (df["Date"].dt.time <= pd.Timestamp(SESSION_END).time())
        )

        df = df[time_mask].copy()

        # ----------------------------------------------------
        # Duplicate timestamps
        # ----------------------------------------------------

        duplicate_count = int(
            df["Date"].duplicated().sum()
        )

        # Keep first duplicate only for backtest safety.
        #
        # We record the problem instead of allowing duplicated
        # timestamps to create artificial signals.
        df = df.drop_duplicates(
            subset=["Date"],
            keep="first",
        )

        # ----------------------------------------------------
        # NaN count
        # ----------------------------------------------------

        nan_values = int(
            df[
                [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                ]
            ].isna().sum().sum()
        )

        # Remove rows with invalid numerical data.
        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
        )

        # ----------------------------------------------------
        # OHLC validation
        # ----------------------------------------------------

        bad_ohlc_mask = (
            (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
            |
            (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
        )

        bad_ohlc = int(bad_ohlc_mask.sum())

        df = df[~bad_ohlc_mask].copy()

        # ----------------------------------------------------
        # Sessions
        # ----------------------------------------------------

        df["session_date"] = df["Date"].dt.date

        session_counts = (
            df.groupby("session_date")
            .size()
        )

        incomplete_sessions = session_counts[
            session_counts != self.expected_session_bars
        ]

        complete_sessions = session_counts[
            session_counts == self.expected_session_bars
        ]

        # ----------------------------------------------------
        # Missing minutes
        # ----------------------------------------------------

        missing_minutes = 0

        for session_date, session_df in df.groupby("session_date"):

            expected_index = pd.date_range(
                start=f"{session_date} {SESSION_START}",
                end=f"{session_date} {SESSION_END}",
                freq="1min",
            )

            actual_index = pd.DatetimeIndex(
                session_df["Date"]
            )

            missing = expected_index.difference(
                actual_index
            )

            missing_minutes += len(missing)

        # ----------------------------------------------------
        # Excluded sessions
        # ----------------------------------------------------

        excluded_sessions = [
            str(session)
            for session in incomplete_sessions.index
        ]

        # ----------------------------------------------------
        # Remove incomplete sessions from actual backtest
        # ----------------------------------------------------

        if exclude_incomplete_sessions:

            df = df[
                ~df["session_date"].isin(
                    incomplete_sessions.index
                )
            ].copy()

        # ----------------------------------------------------
        # Zero volume
        # ----------------------------------------------------

        zero_volume_rows = int(
            (df["Volume"] <= 0).sum()
        )

        # ----------------------------------------------------
        # Final cleanup
        # ----------------------------------------------------

        df = (
            df.sort_values("Date")
            .reset_index(drop=True)
        )

        # session_date is metadata for validation, not strategy
        # input.
        df = df.drop(columns=["session_date"])

        # ----------------------------------------------------
        # Final report
        # ----------------------------------------------------

        report = DataQualityReport(
            symbol=symbol,
            year=year,

            total_rows=len(df),

            sessions=(
                df["Date"]
                .dt.date
                .nunique()
            ),

            complete_sessions=len(complete_sessions),

            incomplete_sessions=len(
                incomplete_sessions
            ),

            missing_minutes=missing_minutes,

            duplicate_timestamps=duplicate_count,

            nan_values=nan_values,

            bad_ohlc=bad_ohlc,

            zero_volume_rows=zero_volume_rows,

            first_timestamp=(
                df["Date"].min()
                if not df.empty
                else None
            ),

            last_timestamp=(
                df["Date"].max()
                if not df.empty
                else None
            ),

            excluded_sessions=excluded_sessions,
        )

        return BacktestData(
            symbol=symbol,
            year=year,
            data=df,
            quality=report,
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def load_backtest_data(
    symbol: str,
    year: int,
    data_dir: str | Path = "research/clean_data_2018",
    exclude_incomplete_sessions: bool = True,
) -> BacktestData:

    loader = BacktestDataLoader(
        data_dir=data_dir
    )

    return loader.load(
        symbol=symbol,
        year=year,
        exclude_incomplete_sessions=exclude_incomplete_sessions,
    )


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("SIGNALFORGE — BACKTEST DATA LOADER TEST")
    print("=" * 60)

    loader = BacktestDataLoader(
        data_dir="research/clean_data_2018"
    )

    symbols = [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
    ]

    for symbol in symbols:

        print("\n" + "=" * 50)
        print(f"LOADING {symbol} — 2018")
        print("=" * 50)

        try:

            result = loader.load(
                symbol=symbol,
                year=2018,
                exclude_incomplete_sessions=True,
            )

            q = result.quality

            print(f"Final rows:             {q.total_rows:,}")
            print(f"Backtest sessions:      {q.sessions}")
            print(
                f"Complete sessions:      "
                f"{q.complete_sessions}"
            )
            print(
                f"Incomplete sessions:    "
                f"{q.incomplete_sessions}"
            )
            print(
                f"Missing minutes:        "
                f"{q.missing_minutes}"
            )
            print(
                f"Duplicate timestamps:   "
                f"{q.duplicate_timestamps}"
            )
            print(
                f"NaN values:             "
                f"{q.nan_values}"
            )
            print(
                f"Bad OHLC:               "
                f"{q.bad_ohlc}"
            )
            print(
                f"Zero volume rows:       "
                f"{q.zero_volume_rows}"
            )

            print(
                f"First timestamp:        "
                f"{q.first_timestamp}"
            )

            print(
                f"Last timestamp:         "
                f"{q.last_timestamp}"
            )

            print(
                f"Excluded sessions:      "
                f"{len(q.excluded_sessions)}"
            )

            print(
                "USABLE:                 "
                f"{q.usable}"
            )

        except Exception as exc:

            print(
                f"ERROR: {type(exc).__name__}: {exc}"
            )
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.resampler import REQUIRED_COLUMNS
from src.data.session import MARKET_CLOSE, MARKET_OPEN


EXPECTED_SESSION_CANDLES = 376


@dataclass(frozen=True)
class DataQualityResult:
    """Result of historical OHLCV data-quality analysis."""

    passed: bool
    total_rows: int
    session_count: int
    complete_session_count: int
    incomplete_session_count: int
    duplicate_timestamp_count: int
    out_of_order: bool
    missing_value_count: int
    non_numeric_column_count: int
    invalid_ohlc_count: int
    negative_volume_count: int
    zero_volume_count: int
    zero_volume_ratio: float
    missing_candle_count: int
    issues: tuple[str, ...]

    @property
    def quality_score(self) -> float:
        """Return a simple 0-100 quality score."""

        penalties = 0.0

        if self.total_rows > 0:
            structural_errors = (
                self.duplicate_timestamp_count
                + self.missing_value_count
                + self.non_numeric_column_count
                + self.invalid_ohlc_count
                + self.negative_volume_count
            )

            penalties += min(
                100.0,
                structural_errors / self.total_rows * 100.0,
            )

        if self.total_rows > 0:
            penalties += min(
                25.0,
                self.missing_candle_count
                / self.total_rows
                * 100.0,
            )

        if self.incomplete_session_count > 0:
            if self.session_count > 0:
                penalties += min(
                    25.0,
                    self.incomplete_session_count
                    / self.session_count
                    * 25.0,
                )

        return max(
            0.0,
            round(100.0 - penalties, 2),
        )


class DataQualityChecker:
    """
    Analyze the quality of raw 1-minute OHLCV data.

    This stage is diagnostic and does not mutate the supplied
    DataFrame. It does not approve or reject an instrument for
    signal generation.
    """

    def check(
        self,
        data: pd.DataFrame,
    ) -> DataQualityResult:
        """Analyze raw historical OHLCV data."""

        issues: list[str] = []

        if not isinstance(data, pd.DataFrame):
            return self._failed_result(
                "Market data must be a pandas DataFrame."
            )

        if not isinstance(data.index, pd.DatetimeIndex):
            return self._failed_result(
                "Market data index must be a DatetimeIndex."
            )

        total_rows = len(data)

        if total_rows == 0:
            return self._failed_result(
                "Market data cannot be empty."
            )

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in data.columns
        ]

        if missing_columns:
            return self._failed_result(
                "Missing required columns: "
                f"{missing_columns}"
            )

        duplicate_timestamp_count = int(
            data.index.duplicated(
                keep=False
            ).sum()
        )

        if duplicate_timestamp_count > 0:
            issues.append(
                "Duplicate timestamps detected: "
                f"{duplicate_timestamp_count} rows."
            )

        out_of_order = not data.index.is_monotonic_increasing

        if out_of_order:
            issues.append(
                "Market data timestamps are not sorted "
                "in ascending order."
            )

        numeric_data = data.loc[
            :,
            list(REQUIRED_COLUMNS),
        ].copy()

        non_numeric_column_count = 0

        for column in REQUIRED_COLUMNS:
            if not pd.api.types.is_numeric_dtype(
                numeric_data[column]
            ):
                non_numeric_column_count += 1

        if non_numeric_column_count > 0:
            issues.append(
                "One or more OHLCV columns are non-numeric."
            )

        numeric_data = numeric_data.apply(
            pd.to_numeric,
            errors="coerce",
        )

        missing_value_count = int(
            numeric_data.isna().sum().sum()
        )

        if missing_value_count > 0:
            issues.append(
                "Missing or non-numeric OHLCV values detected: "
                f"{missing_value_count} cells."
            )

        invalid_ohlc_mask = (
            (numeric_data["high"] < numeric_data["low"])
            | (numeric_data["open"] < numeric_data["low"])
            | (numeric_data["open"] > numeric_data["high"])
            | (numeric_data["close"] < numeric_data["low"])
            | (numeric_data["close"] > numeric_data["high"])
        )

        invalid_ohlc_mask = invalid_ohlc_mask.fillna(False)

        invalid_ohlc_count = int(
            invalid_ohlc_mask.sum()
        )

        if invalid_ohlc_count > 0:
            issues.append(
                "Invalid OHLC relationships detected: "
                f"{invalid_ohlc_count} rows."
            )

        negative_volume_mask = (
            numeric_data["volume"] < 0
        ).fillna(False)

        negative_volume_count = int(
            negative_volume_mask.sum()
        )

        if negative_volume_count > 0:
            issues.append(
                "Negative volume detected: "
                f"{negative_volume_count} rows."
            )

        zero_volume_mask = (
            numeric_data["volume"] == 0
        ).fillna(False)

        zero_volume_count = int(
            zero_volume_mask.sum()
        )

        zero_volume_ratio = round(
            zero_volume_count / total_rows,
            6,
        )

        session_data = self._session_data(data)

        session_count = self._count_sessions(
            session_data
        )

        complete_session_count = 0
        incomplete_session_count = 0
        missing_candle_count = 0

        for session_date, session in session_data.groupby(
            session_data.index.date
        ):
            session = session.sort_index()

            expected_index = pd.date_range(
                start=pd.Timestamp.combine(
                    session_date,
                    MARKET_OPEN,
                ),
                end=pd.Timestamp.combine(
                    session_date,
                    MARKET_CLOSE,
                ),
                freq="min",
            )

            actual_index = pd.DatetimeIndex(
                session.index.unique()
            ).sort_values()

            missing = expected_index.difference(
                actual_index
            )

            extra = actual_index.difference(
                expected_index
            )

            session_missing_count = len(missing)

            missing_candle_count += session_missing_count

            if (
                len(actual_index) == EXPECTED_SESSION_CANDLES
                and session_missing_count == 0
                and len(extra) == 0
            ):
                complete_session_count += 1
            else:
                incomplete_session_count += 1

        if incomplete_session_count > 0:
            issues.append(
                "Incomplete trading sessions detected: "
                f"{incomplete_session_count}."
            )

        if missing_candle_count > 0:
            issues.append(
                "Missing 1-minute candles detected: "
                f"{missing_candle_count}."
            )

        return DataQualityResult(
            passed=not issues,
            total_rows=total_rows,
            session_count=session_count,
            complete_session_count=complete_session_count,
            incomplete_session_count=incomplete_session_count,
            duplicate_timestamp_count=duplicate_timestamp_count,
            out_of_order=out_of_order,
            missing_value_count=missing_value_count,
            non_numeric_column_count=non_numeric_column_count,
            invalid_ohlc_count=invalid_ohlc_count,
            negative_volume_count=negative_volume_count,
            zero_volume_count=zero_volume_count,
            zero_volume_ratio=zero_volume_ratio,
            missing_candle_count=missing_candle_count,
            issues=tuple(issues),
        )

    @staticmethod
    def _session_data(
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Return rows inside the regular market session."""

        timestamps = data.index

        mask = (
            (timestamps.time >= MARKET_OPEN)
            & (timestamps.time <= MARKET_CLOSE)
        )

        return data.loc[mask].copy()

    @staticmethod
    def _count_sessions(
        data: pd.DataFrame,
    ) -> int:
        """Count unique trading dates."""

        if data.empty:
            return 0

        return len(
            set(
                timestamp.date()
                for timestamp in data.index
            )
        )

    @staticmethod
    def _failed_result(
        issue: str,
    ) -> DataQualityResult:
        """Build a failed result for invalid input structure."""

        return DataQualityResult(
            passed=False,
            total_rows=0,
            session_count=0,
            complete_session_count=0,
            incomplete_session_count=0,
            duplicate_timestamp_count=0,
            out_of_order=False,
            missing_value_count=0,
            non_numeric_column_count=0,
            invalid_ohlc_count=0,
            negative_volume_count=0,
            zero_volume_count=0,
            zero_volume_ratio=0.0,
            missing_candle_count=0,
            issues=(issue,),
        )

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategy.backtest_strategy import create_signal_function


REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True)
class CausalityResult:
    """Result of historical future-data leakage validation."""

    passed: bool
    total_candles: int
    observations_checked: int
    mismatches: int
    first_mismatch_timestamp: pd.Timestamp | None
    issues: tuple[str, ...]

    @property
    def has_evidence(self) -> bool:
        """Return True when at least one observation was tested."""
        return self.observations_checked > 0

    @property
    def causal(self) -> bool:
        """Return True when all tested observations are causal."""
        return (
            self.has_evidence
            and self.mismatches == 0
        )


class CausalityValidator:
    """
    Validate that strategy decisions do not depend on future candles.

    Observations are tested only after enough historical candles are
    available for the SignalForge strategy to operate normally.
    """

    def __init__(
        self,
        minimum_observations: int = 1,
        observation_step: int = 1,
        minimum_history_candles: int = 50,
    ) -> None:
        if minimum_observations < 1:
            raise ValueError(
                "minimum_observations must be at least 1"
            )

        if observation_step < 1:
            raise ValueError(
                "observation_step must be at least 1"
            )

        if minimum_history_candles < 2:
            raise ValueError(
                "minimum_history_candles must be at least 2"
            )

        self.minimum_observations = minimum_observations
        self.observation_step = observation_step
        self.minimum_history_candles = (
            minimum_history_candles
        )

    def check(
        self,
        data: pd.DataFrame,
    ) -> CausalityResult:
        """Run future-data leakage validation."""

        issues: list[str] = []

        if not isinstance(data, pd.DataFrame):
            return CausalityResult(
                passed=False,
                total_candles=0,
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "market data must be a pandas DataFrame",
                ),
            )

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in data.columns
        ]

        if missing_columns:
            return CausalityResult(
                passed=False,
                total_candles=len(data),
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "missing required columns: "
                    + ", ".join(missing_columns),
                ),
            )

        if not isinstance(data.index, pd.DatetimeIndex):
            return CausalityResult(
                passed=False,
                total_candles=len(data),
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "market data must use a DatetimeIndex",
                ),
            )

        if data.empty:
            return CausalityResult(
                passed=False,
                total_candles=0,
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=("market data is empty",),
            )

        working_data = data.copy()

        if not working_data.index.is_monotonic_increasing:
            working_data = working_data.sort_index()

        if working_data.index.has_duplicates:
            return CausalityResult(
                passed=False,
                total_candles=len(working_data),
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "market data contains duplicate timestamps",
                ),
            )

        required_data = working_data[
            list(REQUIRED_COLUMNS)
        ]

        if required_data.isna().any().any():
            return CausalityResult(
                passed=False,
                total_candles=len(working_data),
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "market data contains missing values",
                ),
            )

        if len(working_data) < self.minimum_history_candles + 1:
            return CausalityResult(
                passed=False,
                total_candles=len(working_data),
                observations_checked=0,
                mismatches=0,
                first_mismatch_timestamp=None,
                issues=(
                    "insufficient historical candles for "
                    "causality validation: "
                    f"{len(working_data)} < "
                    f"{self.minimum_history_candles + 1}",
                ),
            )

        first_observation_index = (
            self.minimum_history_candles
        )

        observation_indices = list(
            range(
                first_observation_index,
                len(working_data),
                self.observation_step,
            )
        )

        observations_checked = 0
        mismatches = 0
        first_mismatch_timestamp = None

        for index_position in observation_indices:
            timestamp = working_data.index[index_position]

            historical_data = working_data.iloc[
                : index_position + 1
            ].copy()

            full_data = working_data.copy()

            current_row = historical_data.iloc[-1].copy()
            previous_row = historical_data.iloc[-2].copy()

            try:
                historical_strategy = create_signal_function(
                    historical_data
                )

                full_strategy = create_signal_function(
                    full_data
                )

                historical_signal = historical_strategy(
                    current_row,
                    previous_row,
                )

                full_signal = full_strategy(
                    current_row,
                    previous_row,
                )

            except Exception as exc:
                issues.append(
                    "causality evaluation failed at "
                    f"{timestamp}: {exc}"
                )
                continue

            observations_checked += 1

            if historical_signal != full_signal:
                mismatches += 1

                if first_mismatch_timestamp is None:
                    first_mismatch_timestamp = timestamp

        if observations_checked < self.minimum_observations:
            issues.append(
                "insufficient causality observations: "
                f"{observations_checked} < "
                f"{self.minimum_observations}"
            )

        if mismatches > 0:
            issues.append(
                "future data changed strategy decisions "
                f"at {mismatches} observation(s)"
            )

        evaluation_failures = any(
            issue.startswith(
                "causality evaluation failed"
            )
            for issue in issues
        )

        passed = (
            observations_checked >= self.minimum_observations
            and mismatches == 0
            and not evaluation_failures
        )

        return CausalityResult(
            passed=passed,
            total_candles=len(working_data),
            observations_checked=observations_checked,
            mismatches=mismatches,
            first_mismatch_timestamp=first_mismatch_timestamp,
            issues=tuple(issues),
        )

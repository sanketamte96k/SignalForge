"""Final approval gate for SignalForge instrument validation."""

from __future__ import annotations

from dataclasses import dataclass

from src.universe.validation import ValidationStatus

from src.validation.causality import CausalityResult
from src.validation.cost_slippage import CostSlippageResult
from src.validation.data_availability import DataAvailabilityResult
from src.validation.data_quality import DataQualityResult
from src.validation.historical_backtest import HistoricalBacktestResult
from src.validation.indicator_compatibility import (
    IndicatorCompatibilityResult,
)
from src.validation.regime_oos import RegimeOOSResult


@dataclass(frozen=True)
class ApprovalResult:
    """Final validation decision for an instrument."""

    status: ValidationStatus
    signal_eligible: bool
    approved: bool
    passed_gates: tuple[str, ...]
    failed_gates: tuple[str, ...]
    issues: tuple[str, ...]

    @property
    def validated(self) -> bool:
        """Return whether the instrument is fully validated."""

        return self.status == ValidationStatus.VALIDATED

    @property
    def failed(self) -> bool:
        """Return whether the instrument failed validation."""

        return self.status == ValidationStatus.FAILED

    @property
    def gate_count(self) -> int:
        """Return the number of validation gates evaluated."""

        return (
            len(self.passed_gates)
            + len(self.failed_gates)
        )


class ApprovalValidator:
    """
    Make the final SignalForge validation decision.

    This stage consumes the results of validation stages 9.1
    through 9.7. It does not rerun any validation and does not
    modify strategy parameters.

    An instrument becomes signal-eligible only when every required
    validation gate passes.
    """

    GATE_DATA_AVAILABILITY = "DATA_AVAILABILITY"
    GATE_DATA_QUALITY = "DATA_QUALITY"
    GATE_INDICATOR_COMPATIBILITY = (
        "INDICATOR_COMPATIBILITY"
    )
    GATE_HISTORICAL_BACKTEST = (
        "HISTORICAL_BACKTEST"
    )
    GATE_CAUSALITY = "CAUSALITY"
    GATE_COST_SLIPPAGE = "COST_SLIPPAGE"
    GATE_REGIME_OOS = "REGIME_OOS"

    REQUIRED_GATES = (
        GATE_DATA_AVAILABILITY,
        GATE_DATA_QUALITY,
        GATE_INDICATOR_COMPATIBILITY,
        GATE_HISTORICAL_BACKTEST,
        GATE_CAUSALITY,
        GATE_COST_SLIPPAGE,
        GATE_REGIME_OOS,
    )

    def evaluate(
        self,
        *,
        data_availability: DataAvailabilityResult,
        data_quality: DataQualityResult,
        indicator_compatibility: IndicatorCompatibilityResult,
        historical_backtest: HistoricalBacktestResult,
        causality: CausalityResult,
        cost_slippage: CostSlippageResult,
        regime_oos: RegimeOOSResult,
    ) -> ApprovalResult:
        """
        Evaluate all validation gates.

        Parameters
        ----------
        data_availability:
            Result from validation stage 9.1.

        data_quality:
            Result from validation stage 9.2.

        indicator_compatibility:
            Result from validation stage 9.3.

        historical_backtest:
            Result from validation stage 9.4.

        causality:
            Result from validation stage 9.5.

        cost_slippage:
            Result from validation stage 9.6.

        regime_oos:
            Result from validation stage 9.7.
        """

        self._validate_result_types(
            data_availability=data_availability,
            data_quality=data_quality,
            indicator_compatibility=indicator_compatibility,
            historical_backtest=historical_backtest,
            causality=causality,
            cost_slippage=cost_slippage,
            regime_oos=regime_oos,
        )

        gate_results = (
            (
                self.GATE_DATA_AVAILABILITY,
                data_availability.available,
                data_availability.reasons,
            ),
            (
                self.GATE_DATA_QUALITY,
                data_quality.passed,
                data_quality.issues,
            ),
            (
                self.GATE_INDICATOR_COMPATIBILITY,
                indicator_compatibility.passed,
                indicator_compatibility.issues,
            ),
            (
                self.GATE_HISTORICAL_BACKTEST,
                historical_backtest.passed,
                historical_backtest.issues,
            ),
            (
                self.GATE_CAUSALITY,
                causality.passed,
                causality.issues,
            ),
            (
                self.GATE_COST_SLIPPAGE,
                (
                    cost_slippage.passed
                    and cost_slippage.friction_resistant
                ),
                cost_slippage.issues,
            ),
            (
                self.GATE_REGIME_OOS,
                regime_oos.passed,
                regime_oos.issues,
            ),
        )

        passed_gates: list[str] = []
        failed_gates: list[str] = []
        issues: list[str] = []

        for gate, passed, gate_issues in gate_results:
            if passed:
                passed_gates.append(gate)
                continue

            failed_gates.append(gate)

            if gate_issues:
                for issue in gate_issues:
                    issues.append(
                        f"{gate}: {issue}"
                    )
            else:
                issues.append(
                    f"{gate}: validation gate failed."
                )

        approved = (
            len(failed_gates) == 0
            and len(passed_gates)
            == len(self.REQUIRED_GATES)
        )

        if approved:
            status = ValidationStatus.VALIDATED
            signal_eligible = True
        else:
            status = ValidationStatus.FAILED
            signal_eligible = False

        return ApprovalResult(
            status=status,
            signal_eligible=signal_eligible,
            approved=approved,
            passed_gates=tuple(passed_gates),
            failed_gates=tuple(failed_gates),
            issues=tuple(issues),
        )

    @staticmethod
    def _validate_result_types(
        *,
        data_availability: DataAvailabilityResult,
        data_quality: DataQualityResult,
        indicator_compatibility: IndicatorCompatibilityResult,
        historical_backtest: HistoricalBacktestResult,
        causality: CausalityResult,
        cost_slippage: CostSlippageResult,
        regime_oos: RegimeOOSResult,
    ) -> None:
        """Validate that every supplied result is the correct type."""

        expected = (
            (
                "data_availability",
                data_availability,
                DataAvailabilityResult,
            ),
            (
                "data_quality",
                data_quality,
                DataQualityResult,
            ),
            (
                "indicator_compatibility",
                indicator_compatibility,
                IndicatorCompatibilityResult,
            ),
            (
                "historical_backtest",
                historical_backtest,
                HistoricalBacktestResult,
            ),
            (
                "causality",
                causality,
                CausalityResult,
            ),
            (
                "cost_slippage",
                cost_slippage,
                CostSlippageResult,
            ),
            (
                "regime_oos",
                regime_oos,
                RegimeOOSResult,
            ),
        )

        for name, value, expected_type in expected:
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{name} must be a "
                    f"{expected_type.__name__}."
                )

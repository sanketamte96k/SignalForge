import pandas as pd
import pytest

from src.universe.validation import ValidationStatus
from src.validation import (
    ApprovalResult,
    ApprovalValidator,
    CausalityResult,
    CostSlippageResult,
    CostSlippageScenario,
    DataAvailabilityResult,
    DataQualityResult,
    HistoricalBacktestResult,
    IndicatorCompatibilityResult,
    OOSMetrics,
    RegimeMetrics,
    RegimeOOSResult,
)


def make_data_availability(passed=True):
    return DataAvailabilityResult(
        available=passed,
        candle_count=1000,
        session_count=10,
        first_timestamp=None,
        last_timestamp=None,
        timeframe_candle_counts={
            "5m": 200,
            "10m": 100,
            "15m": 66,
            "30m": 33,
        },
        required_timeframes=("5m", "10m", "15m", "30m"),
        minimum_candles=1,
        minimum_sessions=1,
        reasons=() if passed else (
            "Insufficient historical data.",
        ),
    )


def make_data_quality(passed=True):
    return DataQualityResult(
        passed=passed,
        total_rows=1000,
        session_count=10,
        complete_session_count=10 if passed else 9,
        incomplete_session_count=0 if passed else 1,
        duplicate_timestamp_count=0,
        out_of_order=False,
        missing_value_count=0,
        non_numeric_column_count=0,
        invalid_ohlc_count=0,
        negative_volume_count=0,
        zero_volume_count=1000,
        zero_volume_ratio=1.0,
        missing_candle_count=0 if passed else 376,
        issues=() if passed else (
            "Incomplete market session detected.",
        ),
    )


def make_indicator_compatibility(passed=True):
    return IndicatorCompatibilityResult(
        passed=passed,
        total_source_candles=2000,
        processed_source_candles=2000,
        required_timeframes=("5m", "10m", "15m", "30m"),
        timeframe_candle_counts={
            "5m": 400,
            "10m": 200,
            "15m": 133,
            "30m": 66,
        },
        timeframe_ready_counts={
            "5m": 300,
            "10m": 150,
            "15m": 100,
            "30m": 50,
        },
        timeframe_indicator_ready={
            "5m": passed,
            "10m": passed,
            "15m": passed,
            "30m": passed,
        },
        ema20_ready=passed,
        ema50_ready=passed,
        rsi14_ready=passed,
        atr14_ready=passed,
        rvol20_ready=True,
        issues=() if passed else (
            "Required indicators are not ready.",
        ),
    )


def make_historical_backtest(passed=True):
    return HistoricalBacktestResult(
        passed=passed,
        total_candles=1000,
        total_trades=100 if passed else 0,
        winning_trades=60 if passed else 0,
        losing_trades=40 if passed else 0,
        win_rate=60.0 if passed else 0.0,
        net_pnl=2000.0 if passed else 0.0,
        profit_factor=1.20 if passed else 0.0,
        max_drawdown=500.0,
        max_losing_streak=4,
        minimum_trades_required=1,
        minimum_net_pnl_required=0.0,
        issues=() if passed else (
            "Historical backtest validation failed.",
        ),
    )


def make_causality(passed=True):
    return CausalityResult(
        passed=passed,
        total_candles=1000,
        observations_checked=900,
        mismatches=0 if passed else 1,
        first_mismatch_timestamp=None,
        issues=() if passed else (
            "Future-data mismatch detected.",
        ),
    )


def make_cost_slippage(
    passed=True,
    friction_resistant=None,
):
    if friction_resistant is None:
        friction_resistant = passed

    selected_net_pnl = (
        1000.0
        if friction_resistant
        else -100.0
    )

    selected_scenario = CostSlippageScenario(
        transaction_cost_rate=0.0001,
        slippage_rate=0.0001,
        trades=100,
        winning_trades=60,
        losing_trades=40,
        win_rate=60.0,
        gross_pnl=1500.0,
        transaction_cost=300.0,
        slippage_cost=200.0,
        net_pnl=selected_net_pnl,
        profit_factor=1.20 if friction_resistant else 0.90,
        max_drawdown=500.0,
        max_drawdown_pct=0.5,
    )

    return CostSlippageResult(
        passed=passed,
        total_candles=1000,
        scenarios_checked=9,
        baseline_trades=100,
        baseline_net_pnl=2000.0,
        selected_scenario=selected_scenario,
        scenarios=(selected_scenario,),
        issues=() if passed else (
            "Cost/slippage validation failed.",
        ),
    )


def make_regime_oos(passed=True):
    oos_net_pnl = 500.0 if passed else -100.0
    oos_profit_factor = 1.10 if passed else 0.90
    oos_win_rate = 56.0 if passed else 40.0

    oos_metrics = OOSMetrics(
        period="OOS",
        start=pd.Timestamp("2022-01-01"),
        end=pd.Timestamp("2024-03-26 23:59:59"),
        candles=300,
        trades=30,
        winning_trades=17,
        losing_trades=13,
        win_rate=oos_win_rate,
        net_pnl=oos_net_pnl,
        profit_factor=oos_profit_factor,
        max_drawdown=200.0,
        max_drawdown_pct=0.2,
    )

    return RegimeOOSResult(
        passed=passed,
        total_candles=1000,
        development_candles=700,
        oos_candles=300,
        development_trades=70,
        oos_trades=30,
        development_net_pnl=1500.0,
        oos_net_pnl=oos_net_pnl,
        development_profit_factor=1.15,
        oos_profit_factor=oos_profit_factor,
        oos_win_rate=oos_win_rate,
        pnl_change=-1000.0,
        profit_factor_change=-0.05,
        win_rate_change=-4.0,
        direction_regimes=(
            RegimeMetrics(
                regime="TREND_UP",
                trades=10,
                winning_trades=6,
                losing_trades=4,
                win_rate=60.0,
                net_pnl=200.0,
                profit_factor=1.20,
                max_drawdown=100.0,
                max_drawdown_pct=0.1,
            ),
        ),
        volatility_regimes=(
            RegimeMetrics(
                regime="LOW_VOL",
                trades=20,
                winning_trades=12,
                losing_trades=8,
                win_rate=60.0,
                net_pnl=300.0,
                profit_factor=1.20,
                max_drawdown=100.0,
                max_drawdown_pct=0.1,
            ),
        ),
        oos_metrics=oos_metrics,
        minimum_oos_trades=1,
        minimum_oos_net_pnl=0.0,
        minimum_oos_profit_factor=1.0,
        issues=() if passed else (
            "OOS validation failed.",
        ),
    )


def make_all_results():
    return {
        "data_availability": make_data_availability(),
        "data_quality": make_data_quality(),
        "indicator_compatibility": make_indicator_compatibility(),
        "historical_backtest": make_historical_backtest(),
        "causality": make_causality(),
        "cost_slippage": make_cost_slippage(),
        "regime_oos": make_regime_oos(),
    }


def test_all_gates_pass_returns_validated():
    validator = ApprovalValidator()

    result = validator.evaluate(
        **make_all_results()
    )

    assert isinstance(result, ApprovalResult)
    assert result.approved is True
    assert result.signal_eligible is True
    assert result.status is ValidationStatus.VALIDATED

    assert result.passed_gates == (
        "DATA_AVAILABILITY",
        "DATA_QUALITY",
        "INDICATOR_COMPATIBILITY",
        "HISTORICAL_BACKTEST",
        "CAUSALITY",
        "COST_SLIPPAGE",
        "REGIME_OOS",
    )

    assert result.failed_gates == ()
    assert result.issues == ()
    assert result.gate_count == 7


@pytest.mark.parametrize(
    "failed_field,expected_gate",
    [
        (
            "data_availability",
            ApprovalValidator.GATE_DATA_AVAILABILITY,
        ),
        (
            "data_quality",
            ApprovalValidator.GATE_DATA_QUALITY,
        ),
        (
            "indicator_compatibility",
            ApprovalValidator.GATE_INDICATOR_COMPATIBILITY,
        ),
        (
            "historical_backtest",
            ApprovalValidator.GATE_HISTORICAL_BACKTEST,
        ),
        (
            "causality",
            ApprovalValidator.GATE_CAUSALITY,
        ),
        (
            "cost_slippage",
            ApprovalValidator.GATE_COST_SLIPPAGE,
        ),
        (
            "regime_oos",
            ApprovalValidator.GATE_REGIME_OOS,
        ),
    ],
)
def test_each_failed_gate_blocks_approval(
    failed_field,
    expected_gate,
):
    validator = ApprovalValidator()

    results = make_all_results()

    factories = {
        "data_availability": lambda: make_data_availability(False),
        "data_quality": lambda: make_data_quality(False),
        "indicator_compatibility": lambda: make_indicator_compatibility(False),
        "historical_backtest": lambda: make_historical_backtest(False),
        "causality": lambda: make_causality(False),
        "cost_slippage": lambda: make_cost_slippage(False),
        "regime_oos": lambda: make_regime_oos(False),
    }

    results[failed_field] = factories[failed_field]()

    result = validator.evaluate(
        **results
    )

    assert result.approved is False
    assert result.signal_eligible is False
    assert result.status is ValidationStatus.FAILED
    assert expected_gate in result.failed_gates


def test_multiple_failed_gates_are_all_reported():
    validator = ApprovalValidator()

    results = make_all_results()

    results["data_quality"] = make_data_quality(False)
    results["causality"] = make_causality(False)
    results["regime_oos"] = make_regime_oos(False)

    result = validator.evaluate(
        **results
    )

    assert result.approved is False
    assert result.signal_eligible is False
    assert len(result.failed_gates) == 3

    assert (
        ApprovalValidator.GATE_DATA_QUALITY
        in result.failed_gates
    )
    assert (
        ApprovalValidator.GATE_CAUSALITY
        in result.failed_gates
    )
    assert (
        ApprovalValidator.GATE_REGIME_OOS
        in result.failed_gates
    )

    assert (
        ApprovalValidator.GATE_COST_SLIPPAGE
        not in result.failed_gates
    )


def test_failed_cost_slippage_blocks_signal_eligibility():
    validator = ApprovalValidator()

    results = make_all_results()

    results["cost_slippage"] = make_cost_slippage(
        passed=False,
        friction_resistant=False,
    )

    result = validator.evaluate(
        **results
    )

    assert result.approved is False
    assert result.signal_eligible is False
    assert (
        ApprovalValidator.GATE_COST_SLIPPAGE
        in result.failed_gates
    )


def test_cost_slippage_requires_both_pass_and_friction_resistance():
    validator = ApprovalValidator()

    results = make_all_results()

    results["cost_slippage"] = make_cost_slippage(
        passed=True,
        friction_resistant=False,
    )

    result = validator.evaluate(
        **results
    )

    assert result.approved is False
    assert result.signal_eligible is False
    assert (
        ApprovalValidator.GATE_COST_SLIPPAGE
        in result.failed_gates
    )


@pytest.mark.parametrize(
    "field_name,expected_type_name",
    [
        (
            "data_availability",
            "DataAvailabilityResult",
        ),
        (
            "data_quality",
            "DataQualityResult",
        ),
        (
            "indicator_compatibility",
            "IndicatorCompatibilityResult",
        ),
        (
            "historical_backtest",
            "HistoricalBacktestResult",
        ),
        (
            "causality",
            "CausalityResult",
        ),
        (
            "cost_slippage",
            "CostSlippageResult",
        ),
        (
            "regime_oos",
            "RegimeOOSResult",
        ),
    ],
)
def test_wrong_result_type_is_rejected(
    field_name,
    expected_type_name,
):
    validator = ApprovalValidator()

    results = make_all_results()
    results[field_name] = object()

    with pytest.raises(
        TypeError,
        match=expected_type_name,
    ):
        validator.evaluate(
            **results
        )


def test_required_gates_are_exactly_the_seven_pipeline_stages():
    assert ApprovalValidator.REQUIRED_GATES == (
        "DATA_AVAILABILITY",
        "DATA_QUALITY",
        "INDICATOR_COMPATIBILITY",
        "HISTORICAL_BACKTEST",
        "CAUSALITY",
        "COST_SLIPPAGE",
        "REGIME_OOS",
    )


def test_failed_result_contains_gate_specific_issue():
    validator = ApprovalValidator()

    results = make_all_results()

    results["causality"] = make_causality(False)

    result = validator.evaluate(
        **results
    )

    assert (
        ApprovalValidator.GATE_CAUSALITY
        in result.failed_gates
    )

    assert any(
        issue.startswith(
            "CAUSALITY:"
        )
        for issue in result.issues
    )


def test_approval_result_properties_are_consistent():
    result = ApprovalResult(
        status=ValidationStatus.VALIDATED,
        signal_eligible=True,
        approved=True,
        passed_gates=(
            "DATA_AVAILABILITY",
            "DATA_QUALITY",
        ),
        failed_gates=(),
        issues=(),
    )

    assert result.validated is True
    assert result.failed is False
    assert result.gate_count == 2

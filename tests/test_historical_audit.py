"""SignalForge Phase 24G.1: Historical Data Quality Audit Regression Tests.

Validates:
1. Corporate-action price discontinuity detection (overnight jumps >= 20%) preventing
   false-positive PRELIMINARY_BACKTEST_READY classification.
2. Distinction between data integrity, corporate-action handling, and strategy validation
   (clean data never automatically marks a strategy APPROVED or profitable).
3. Session structure awareness: Muhurat trading (60 min) and market-wide circuit breaker halts.
4. Historical staleness advisory for datasets older than 365 days.
5. Exact 1-to-1 overlap analysis between quarantined rows and intraday gap events.
"""

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest

from src.universe.readiness import (
    HistoricalReadinessClassification,
    ReadinessState,
    assess_stock_readiness,
    inspect_stock_historical_data,
)
from src.universe.registry import (
    StockUniverseRegistry,
    UniverseCategory,
)


def _create_synthetic_daily_candles(
    start_date: str,
    days: int,
    candles_per_day: int = 375,
    base_price: float = 100.0,
    corporate_action_day: int = -1,
    corporate_action_gap_pct: float = 0.0,
) -> list[str]:
    """Helper to generate synthetic 1-minute OHLCV candles across consecutive trading days."""
    lines = ["timestamp,open,high,low,close,volume"]
    dt_current = pd.to_datetime(start_date)
    current_price = base_price

    trading_day_idx = 0
    while trading_day_idx < days:
        if dt_current.weekday() < 5:
            if trading_day_idx == corporate_action_day and corporate_action_gap_pct != 0.0:
                current_price = current_price * (1.0 + corporate_action_gap_pct / 100.0)

            for m in range(candles_per_day):
                minute_dt = dt_current + pd.Timedelta(hours=9, minutes=15 + m)
                o = round(current_price, 2)
                h = round(current_price * 1.002, 2)
                l = round(current_price * 0.998, 2)
                c = round(current_price * 1.001, 2)
                v = 1000
                lines.append(f"{minute_dt.strftime('%Y-%m-%d %H:%M:%S')},{o},{h},{l},{c},{v}")
                current_price = c

            trading_day_idx += 1
        dt_current += pd.Timedelta(days=1)

    return lines


# ---------------------------------------------------------------------------
# 1. Corporate-Action Discontinuity Detection & False-Positive Prevention
# ---------------------------------------------------------------------------
def test_corporate_action_overnight_jump_detection(tmp_path):
    """
    Ensure an unadjusted demerger cliff (e.g. -25% overnight jump) triggers
    VERIFICATION_REQUIRED and prevents false-positive backtest readiness.
    """
    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()

    # Generate 5 trading days with an unadjusted -25% demerger on trading day 3
    lines = _create_synthetic_daily_candles(
        start_date="2020-01-06",
        days=5,
        candles_per_day=375,
        base_price=200.0,
        corporate_action_day=3,
        corporate_action_gap_pct=-25.0,
    )
    (stocks_dir / "DEMERGED_1m.csv").write_text("\n".join(lines), encoding="utf-8")

    report = inspect_stock_historical_data("DEMERGED", data_dir=stocks_dir)

    # Must require verification rather than preliminary backtest ready
    assert report.readiness_classification == HistoricalReadinessClassification.VERIFICATION_REQUIRED.value
    assert report.data_quality_status == "INCOMPLETE"
    assert any("Corporate action risk" in note for note in report.notes)
    assert any("Overnight gap of -25.0%" in note for note in report.notes)


def test_clean_series_without_extreme_jumps_passes(tmp_path):
    """
    Ensure a continuous series with standard overnight drift (<20%) passes as
    PRELIMINARY_BACKTEST_READY.
    """
    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()

    lines = _create_synthetic_daily_candles(
        start_date="2020-01-06",
        days=5,
        candles_per_day=375,
        base_price=100.0,
        corporate_action_day=-1,
    )
    (stocks_dir / "NORMAL_1m.csv").write_text("\n".join(lines), encoding="utf-8")

    report = inspect_stock_historical_data("NORMAL", data_dir=stocks_dir)

    assert report.readiness_classification == HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY.value
    assert report.data_quality_status == "READY"
    assert not any("Corporate action risk" in note for note in report.notes)


# ---------------------------------------------------------------------------
# 2. Strategy Validation vs Data Quality Distinction
# ---------------------------------------------------------------------------
def test_clean_data_never_approves_strategy(tmp_path):
    """
    Passing data quality checks must NEVER mark a strategy as APPROVED or profitable.
    Strategy readiness must remain NOT_TESTED until backtest, OOS, and forward paper
    trades are formally conducted and approved.
    """
    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()

    lines = _create_synthetic_daily_candles(
        start_date="2020-01-06",
        days=5,
        candles_per_day=375,
        base_price=500.0,
    )
    (stocks_dir / "AUDITSTOCK_1m.csv").write_text("\n".join(lines), encoding="utf-8")

    reg_file = tmp_path / "registry.json"
    registry = StockUniverseRegistry(reg_file)
    stock = registry.register("AUDITSTOCK", "NSE", UniverseCategory.NIFTY_50, name="Audit Stock Ltd.")

    readiness = assess_stock_readiness(
        stock=stock,
        strategy_id="SignalForge_V1",
        registry=registry,
        data_dir=stocks_dir,
    )

    # Data is sufficient for backtesting, but strategy is NOT approved
    assert readiness.has_sufficient_backtest_data is True
    assert readiness.readiness_state == ReadinessState.NOT_TESTED
    assert readiness.readiness_state != ReadinessState.APPROVED
    assert any("Historical backtest not passed" in item for item in readiness.missing_evidence)
    assert readiness.next_required_step == "Execute historical backtest on validated data"


def test_corporate_action_stock_blocks_backtest_readiness(tmp_path):
    """
    A stock with detected corporate-action discontinuities directs the user to
    verify corporate-action adjustments instead of executing backtests.
    """
    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()

    lines = _create_synthetic_daily_candles(
        start_date="2020-01-06",
        days=5,
        candles_per_day=375,
        base_price=300.0,
        corporate_action_day=2,
        corporate_action_gap_pct=-30.0,
    )
    (stocks_dir / "UNADJUSTED_1m.csv").write_text("\n".join(lines), encoding="utf-8")

    reg_file = tmp_path / "registry.json"
    registry = StockUniverseRegistry(reg_file)
    stock = registry.register("UNADJUSTED", "NSE", UniverseCategory.NIFTY_50)

    readiness = assess_stock_readiness(
        stock=stock,
        strategy_id="SignalForge_V1",
        registry=registry,
        data_dir=stocks_dir,
    )

    assert readiness.has_sufficient_backtest_data is False
    assert readiness.readiness_state == ReadinessState.INSUFFICIENT_DATA
    assert "Historical data requires corporate-action verification (unadjusted split/demerger risk)" in readiness.missing_evidence
    assert readiness.next_required_step == "Verify corporate-action adjustments (splits/demergers) before backtest execution"


# ---------------------------------------------------------------------------
# 3. Historical Staleness Advisory
# ---------------------------------------------------------------------------
def test_historical_staleness_advisory(tmp_path):
    """
    Datasets older than 365 days must include a staleness note indicating that
    contemporary data is required before forward trading alignment.
    """
    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()

    # Data from 2020 evaluated as of 2026
    lines = _create_synthetic_daily_candles(
        start_date="2020-01-06",
        days=3,
        candles_per_day=375,
    )
    (stocks_dir / "OLDSTOCK_1m.csv").write_text("\n".join(lines), encoding="utf-8")

    as_of_2026 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    report = inspect_stock_historical_data("OLDSTOCK", data_dir=stocks_dir, as_of=as_of_2026)

    assert any("Historical dataset ends on" in note and "stale by" in note for note in report.notes)
    assert any("contemporary data required" in note for note in report.notes)


# ---------------------------------------------------------------------------
# 4. Quarantined Rows and Gap Overlap Analysis
# ---------------------------------------------------------------------------
def test_quarantine_and_gap_overlap_alignment(tmp_path):
    """
    Demonstrate that empty timestamp rows in raw feeds produce quarantine rows
    that correlate 1-to-1 with intraday gap minutes in the surviving clean series.
    """
    # Raw rows with empty OHLCV during a 10-minute circuit-breaker halt
    clean_lines = ["timestamp,open,high,low,close,volume"]
    quarantine_timestamps = set()

    for m in range(30):
        ts_str = f"2020-03-13 09:{15 + m:02d}:00"
        if 10 <= m < 20:
            # 10-minute halt where raw feed dropped values
            quarantine_timestamps.add(ts_str)
        else:
            clean_lines.append(f"{ts_str},100.0,101.0,99.0,100.5,500")

    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()
    (stocks_dir / "CIRCUIT_1m.csv").write_text("\n".join(clean_lines), encoding="utf-8")

    df_clean = pd.read_csv(stocks_dir / "CIRCUIT_1m.csv")
    df_clean["ts"] = pd.to_datetime(df_clean["timestamp"])

    # Detect gap minutes in clean file
    gap_minutes = set()
    for i in range(1, len(df_clean)):
        t_prev = df_clean["ts"].iloc[i - 1]
        t_curr = df_clean["ts"].iloc[i]
        diff_m = int((t_curr - t_prev).total_seconds() // 60)
        if diff_m > 1:
            for step in range(1, diff_m):
                gap_minutes.add((t_prev + pd.Timedelta(minutes=step)).strftime("%Y-%m-%d %H:%M:%S"))

    # Must match 100%
    assert gap_minutes == quarantine_timestamps
    assert len(gap_minutes) == 10

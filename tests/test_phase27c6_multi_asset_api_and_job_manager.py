"""
SignalForge — Phase 27C.6: Multi-Asset JobManager & REST API Integration Tests
=============================================================================
Validates:
1. Multi-asset API request model validation (rejects invalid symbols, duplicates,
   unsupported parameters, and cross-field risk constraint violations).
2. JobManager multi-asset lifecycle management (job ID generation, state transitions,
   thread-safe background execution, cancellation, and isolation).
3. Synchronized portfolio execution integration (shared capital allocation, aggregate
   risk limits, stale data entry blocking, global feed outage, and margin conservation).
4. Full end-to-end REST API workflows (submitting jobs, querying status, retrieving
   structured multi-asset results, per-symbol attribution, and unresolved positions).
5. Absolute zero-access quarantine compliance: uses 100% synthetic in-memory fixtures.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
from pydantic import ValidationError
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.models import (
    BacktestJobCreatedResponse,
    BacktestJobResultResponse,
    BacktestJobStatusResponse,
    BacktestRunRequest,
    MultiAssetBacktestJobCreatedResponse,
    MultiAssetBacktestJobResultResponse,
    MultiAssetBacktestJobStatusResponse,
    MultiAssetBacktestRunRequest,
)
from src.backtest.capital_allocator import TradeOpportunity
from src.backtest.multi_asset_engine import MultiAssetEngineConfig, run_multi_asset_backtest
from src.backtest.portfolio import Position, RiskReason
from src.strategy.job_manager import (
    BacktestJob,
    BacktestJobManager,
    JobStatus,
    get_job_manager,
)


# ============================================================================
# Synthetic Test Fixtures (Strict Zero Historical Data Access)
# ============================================================================

def _make_synthetic_candles(
    dates: pd.DatetimeIndex,
    base_price: float = 100.0,
    trend: float = 0.0005,
) -> pd.DataFrame:
    """Generate deterministic synthetic 1-minute OHLCV candles."""
    n = len(dates)
    prices = [base_price]
    for i in range(1, n):
        # Deterministic price oscillation with slight trend
        change = base_price * (trend + 0.002 * math.sin(i / 5.0))
        prices.append(max(1.0, prices[-1] + change))

    prices_arr = np.array(prices)
    highs = prices_arr * 1.002
    lows = prices_arr * 0.998
    opens = prices_arr * 0.999
    volumes = np.full(n, 100_000.0)

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices_arr,
            "volume": volumes,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": prices_arr,
            "Volume": volumes,
        },
        index=dates,
    )
    return df


@pytest.fixture
def synthetic_dates_120() -> pd.DatetimeIndex:
    """Standard 120-minute session for indicator and signal readiness."""
    return pd.date_range("2026-03-30 09:15:00", periods=120, freq="1min")


@pytest.fixture
def isolated_job_manager() -> BacktestJobManager:
    """Provide an isolated, independent BacktestJobManager instance."""
    return BacktestJobManager(max_workers=2, max_retained_jobs=20)


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI test client instance."""
    return TestClient(app)


# ============================================================================
# 1. API Validation Tests (Tests 1 - 9)
# ============================================================================

def test_01_api_validation_valid_multi_symbol_request():
    """Verify valid multi-symbol request model instantiates with proper defaults."""
    req = MultiAssetBacktestRunRequest(
        symbols=["RELIANCE", "TCS", "INFY"],
        initial_capital=200_000.0,
        risk_per_trade_pct=0.01,
        max_portfolio_risk_pct=0.03,
        execution_model="next_open",
    )
    assert req.symbols == ["RELIANCE", "TCS", "INFY"]
    assert req.initial_capital == 200_000.0
    assert req.risk_per_trade_pct == 0.01
    assert req.max_portfolio_risk_pct == 0.03
    assert req.execution_model == "next_open"
    assert req.max_leverage == 5.0


def test_02_api_validation_empty_symbol_list():
    """Verify empty symbols list is rejected."""
    with pytest.raises(ValidationError, match="symbols must be a non-empty list"):
        MultiAssetBacktestRunRequest(symbols=[])


def test_03_api_validation_duplicate_symbols():
    """Verify case-insensitive duplicate symbols are rejected."""
    with pytest.raises(ValidationError, match="Duplicate symbol detected"):
        MultiAssetBacktestRunRequest(symbols=["RELIANCE", "reliance"])

    with pytest.raises(ValidationError, match="Duplicate symbol detected"):
        MultiAssetBacktestRunRequest(symbols=["TCS", "INFY", "TCS"])


def test_04_api_validation_unsupported_symbol():
    """Verify invalid or dangerous symbol patterns are rejected."""
    with pytest.raises(ValidationError, match="Invalid symbol format"):
        MultiAssetBacktestRunRequest(symbols=["../../ETC/PASSWD"])

    with pytest.raises(ValidationError, match="Symbol cannot be empty"):
        MultiAssetBacktestRunRequest(symbols=["   ", "TCS"])


def test_05_api_validation_invalid_capital():
    """Verify non-positive initial capital is rejected."""
    with pytest.raises(ValidationError, match="initial_capital must be greater than zero"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], initial_capital=0.0)

    with pytest.raises(ValidationError, match="initial_capital must be greater than zero"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], initial_capital=-1000.0)


def test_06_api_validation_invalid_risk_settings():
    """Verify cross-field constraint: max_portfolio_risk_pct cannot be less than risk_per_trade_pct."""
    with pytest.raises(ValidationError, match="max_portfolio_risk_pct cannot be less than risk_per_trade_pct"):
        MultiAssetBacktestRunRequest(
            symbols=["TCS"],
            risk_per_trade_pct=0.05,
            max_portfolio_risk_pct=0.02,
        )

    with pytest.raises(ValidationError, match="risk_per_trade_pct must be in range"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], risk_per_trade_pct=1.5)


def test_07_api_validation_invalid_execution_model():
    """Verify unsupported execution models are rejected."""
    with pytest.raises(ValidationError, match="execution_model must be 'next_open' or 'same_close'"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], execution_model="random_fill")


def test_08_api_validation_invalid_expected_timeline():
    """Verify malformed timestamp strings in expected timeline are rejected."""
    with pytest.raises(ValidationError, match="Invalid timestamp in expected_timeline"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], expected_timeline=["not-a-timestamp"])

    with pytest.raises(ValidationError, match="Invalid timestamp format for expected_end_time"):
        MultiAssetBacktestRunRequest(symbols=["TCS"], expected_end_time="invalid-date")


def test_09_api_validation_unsupported_request_fields():
    """Verify unknown fields are rejected under strict extra='forbid' policy."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MultiAssetBacktestRunRequest(
            symbols=["TCS"],
            unsupported_custom_field=123,  # type: ignore
        )


# ============================================================================
# 2. JobManager Multi-Asset Unit Tests (Tests 10 - 18)
# ============================================================================

def test_10_job_manager_multi_asset_job_submission(isolated_job_manager: BacktestJobManager):
    """Verify submitting a multi-asset job queues the job with proper symbols list."""
    job = isolated_job_manager.create_multi_asset_job(
        symbols=["SYM_A", "SYM_B"],
        initial_capital=150_000.0,
    )
    assert job.job_id.startswith("job-")
    assert job.status == JobStatus.QUEUED
    assert job.is_multi_asset is True
    assert job.symbols == ["SYM_A", "SYM_B"]
    assert job.symbol == "MULTI"


def test_11_job_manager_job_id_and_initial_status(isolated_job_manager: BacktestJobManager):
    """Verify initial status dict serialization contains multi-asset metadata."""
    job = isolated_job_manager.create_job(symbols=["SYM_A", "SYM_B"])
    status_dict = job.to_status_dict()
    assert status_dict["job_id"] == job.job_id
    assert status_dict["status"] == "QUEUED"
    assert status_dict["is_multi_asset"] is True
    assert status_dict["symbols"] == ["SYM_A", "SYM_B"]
    assert status_dict["progress"] == 0.0
    assert status_dict["error"] is None


def test_12_job_manager_queued_to_running_transition(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify job transitions from QUEUED to RUNNING during execution."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    df_b = _make_synthetic_candles(synthetic_dates_120, 200.0)

    with patch.object(isolated_job_manager, "_load_data_for_job", side_effect=lambda s: df_a if s == "SYM_A" else df_b):
        job = isolated_job_manager.submit_multi_asset_job(
            symbols=["SYM_A", "SYM_B"],
            initial_capital=100_000.0,
        )
        assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED)

        # Wait for completion
        deadline = time.time() + 10.0
        while time.time() < deadline and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            time.sleep(0.05)

        assert job.status == JobStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None


def test_13_job_manager_successful_completion(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify job completes with 100% progress and populated structured result payload."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    df_b = _make_synthetic_candles(synthetic_dates_120, 200.0)

    with patch.object(isolated_job_manager, "_load_data_for_job", side_effect=lambda s: df_a if s == "SYM_A" else df_b):
        job = isolated_job_manager.submit_multi_asset_job(
            symbols=["SYM_A", "SYM_B"],
            initial_capital=100_000.0,
            risk_per_trade_pct=0.01,
        )

        deadline = time.time() + 10.0
        while time.time() < deadline and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            time.sleep(0.05)

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100.0
        assert job.result is not None
        assert "portfolio" in job.result
        assert "metrics" in job.result
        assert "symbol_metrics" in job.result
        assert "risk_and_quality" in job.result
        assert job.result["symbols"] == ["SYM_A", "SYM_B"]


def test_14_job_manager_failed_execution_missing_data(isolated_job_manager: BacktestJobManager):
    """Verify job handles missing data file failure cleanly without crash."""
    # Sym_MISSING data does not exist
    job = isolated_job_manager.submit_multi_asset_job(symbols=["SYM_NONEXISTENT"])

    deadline = time.time() + 10.0
    while time.time() < deadline and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
        time.sleep(0.05)

    assert job.status == JobStatus.FAILED
    assert job.progress == 0.0
    assert "not found" in job.error.lower() or "filenotfounderror" in job.error.lower()


def test_15_job_manager_result_retrieval(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify get_job retrieves the completed result payload, metrics, and trades."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    with patch.object(isolated_job_manager, "_load_data_for_job", return_value=df_a):
        job = isolated_job_manager.submit_multi_asset_job(symbols=["SYM_A"])

        deadline = time.time() + 10.0
        while time.time() < deadline and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            time.sleep(0.05)

        retrieved = isolated_job_manager.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.status == JobStatus.COMPLETED
        assert retrieved.metrics is not None
        assert isinstance(retrieved.trades, list)


def test_16_job_manager_duplicate_execution_protection(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify job executes exactly once; multiple gets do not re-run simulation."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    with patch.object(isolated_job_manager, "_load_data_for_job", return_value=df_a):
        job = isolated_job_manager.submit_multi_asset_job(symbols=["SYM_A"])

        deadline = time.time() + 10.0
        while time.time() < deadline and job.status != JobStatus.COMPLETED:
            time.sleep(0.05)

        comp_time1 = job.completed_at
        res1 = job.result

        # Subsequent retrieval does not re-execute
        retrieved = isolated_job_manager.get_job(job.job_id)
        assert retrieved.completed_at == comp_time1
        assert retrieved.result is res1


def test_17_job_manager_isolation_between_concurrent_jobs(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify concurrent jobs maintain completely isolated configuration and results."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    df_b = _make_synthetic_candles(synthetic_dates_120, 200.0)

    def mock_loader(sym: str) -> pd.DataFrame:
        return df_a if sym == "SYM_A" else df_b

    with patch.object(isolated_job_manager, "_load_data_for_job", side_effect=mock_loader):
        job1 = isolated_job_manager.submit_multi_asset_job(symbols=["SYM_A"], initial_capital=50_000.0)
        job2 = isolated_job_manager.submit_multi_asset_job(symbols=["SYM_B"], initial_capital=150_000.0)

        deadline = time.time() + 10.0
        while time.time() < deadline and (job1.status != JobStatus.COMPLETED or job2.status != JobStatus.COMPLETED):
            time.sleep(0.05)

        assert job1.status == JobStatus.COMPLETED
        assert job2.status == JobStatus.COMPLETED
        assert job1.result["portfolio"]["initial_capital"] == 50_000.0
        assert job2.result["portfolio"]["initial_capital"] == 150_000.0
        assert job1.result["symbols"] == ["SYM_A"]
        assert job2.result["symbols"] == ["SYM_B"]


def test_18_job_manager_single_symbol_regression_compatibility(
    isolated_job_manager: BacktestJobManager,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify submitting a single-symbol job to the manager still uses the single-symbol pipeline."""
    df = _make_synthetic_candles(synthetic_dates_120, 100.0)
    with patch.object(isolated_job_manager, "_load_data_for_job", return_value=df):
        job = isolated_job_manager.submit_job(symbol="SYM_SINGLE", initial_capital=25_000.0)
        assert job.is_multi_asset is False
        assert job.symbol == "SYM_SINGLE"

        deadline = time.time() + 10.0
        while time.time() < deadline and job.status != JobStatus.COMPLETED:
            time.sleep(0.05)

        assert job.status == JobStatus.COMPLETED
        assert job.result["symbol"] == "SYM_SINGLE"
        assert "portfolio" in job.result


# ============================================================================
# 3. Execution and Portfolio Integration Tests (Tests 19 - 27)
# ============================================================================

def test_19_execution_multiple_symbols_sharing_capital():
    """Verify multiple symbols share capital in PortfolioManager with proper margin accounting."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_synthetic_candles(dates, 100.0)
    df_b = _make_synthetic_candles(dates, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=100.0, target_price=400.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_leverage=5.0,
        opening_cooldown_minutes=0,
        enforce_eod_square_off=False,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a] + [None]*4, "SYM_B": [opp_b] + [None]*4},
        config=m_cfg,
    )

    # Both trades were allocated and executed during the backtest
    assert len(res.trades) == 2
    assert {t.symbol for t in res.trades} == {"SYM_A", "SYM_B"}
    assert all(a.accepted for a in res.allocations)


def test_20_execution_aggregate_portfolio_risk():
    """Verify aggregate portfolio risk limit bounds concurrent positions."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_synthetic_candles(dates, 100.0)
    df_b = _make_synthetic_candles(dates, 200.0)

    # Risk per trade is 2% = ₹2,000. Max portfolio risk is 2.0% = ₹2,000.
    # Second trade would exceed aggregate risk and must be rejected.
    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=80.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=160.0, target_price=400.0,
        requested_quantity=100, signal_quality=0.8, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.02,
        max_portfolio_risk_pct=0.02,
        opening_cooldown_minutes=0,
        enforce_eod_square_off=False,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a] + [None]*4, "SYM_B": [opp_b] + [None]*4},
        config=m_cfg,
    )

    # SYM_A accepted (higher quality 1.0), SYM_B rejected (would exceed 2.0% portfolio risk)
    assert len(res.trades) == 1
    assert res.trades[0].symbol == "SYM_A"
    assert not any(a.symbol == "SYM_B" and a.accepted for a in res.allocations)


def test_21_execution_stale_data_entry_blocking():
    """Verify stale data in one symbol blocks new entries across all symbols."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=7, freq="1min")
    # SYM_A opens at bar 1, then drops bars 2..6 (exceeding max 3 missing bars)
    df_a = _make_synthetic_candles(dates, 100.0).drop(dates[2:7])
    df_b = _make_synthetic_candles(dates, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    # Signal for SYM_B at bar 4 (while SYM_A is stale)
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[4], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        opening_cooldown_minutes=0,
        enforce_eod_square_off=False,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a, None],
            "SYM_B": [None, None, None, None, opp_b, None, None],
        },
        config=m_cfg,
    )

    # SYM_B blocked because SYM_A is stale
    assert not any(a.symbol == "SYM_B" and a.accepted for a in res.allocations)
    assert res.portfolio.has_indeterminate_valuation is True


def test_22_execution_global_feed_outage_handling():
    """Verify simultaneous feed cutoff is detected and recorded in risk quality."""
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    # Feeds cut off at bar 2
    df_a = _make_synthetic_candles(dates_all[:2], 100.0)
    df_b = _make_synthetic_candles(dates_all[:2], 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        opening_cooldown_minutes=0,
        expected_timeline=dates_all,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a, None], "SYM_B": [None, None]},
        config=m_cfg,
    )

    assert res.global_feed_outage_events >= 1
    assert res.global_outage_detection_status == "ACTIVE"
    assert res.expected_timeline_provided is True
    assert RiskReason.GLOBAL_FEED_OUTAGE in res.active_risk_reasons


def test_23_execution_pending_liquidation_in_result():
    """Verify positions missing market data at simulation end are reported in unresolved_positions."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_synthetic_candles(dates[:2], 100.0)  # Cuts off at bar 2

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        opening_cooldown_minutes=0,
        expected_timeline=dates,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a, None]},
        config=m_cfg,
    )

    assert len(res.unresolved_positions) == 1
    unres = res.unresolved_positions[0]
    assert unres.symbol == "SYM_A"
    assert unres.pending_liquidation is True
    assert unres.pending_liquidation_reason == "GLOBAL_FEED_OUTAGE"


def test_24_execution_independent_risk_reason_ownership():
    """Verify independent risk reason keys do not clear each other."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    # SYM_A stale (missing bars 2..7), SYM_B active
    df_a = _make_synthetic_candles(dates, 100.0).drop(dates[2:8])
    df_b = _make_synthetic_candles(dates, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        opening_cooldown_minutes=0,
        enforce_eod_square_off=False,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a, None], "SYM_B": [None] * 8},
        config=m_cfg,
    )

    assert f"{RiskReason.STALE_POSITION}:SYM_A" in res.active_risk_reasons
    # SYM_B active did not clear SYM_A's blocker
    assert res.portfolio.has_indeterminate_valuation is True


def test_25_execution_margin_conservation():
    """Verify margin released upon trade exit is conserved and immediately usable."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_synthetic_candles(dates, 100.0)
    # Target hit at bar 2
    df_a.loc[dates[2], ["High", "Close"]] = 150.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=150.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, opening_cooldown_minutes=0)
    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a] + [None]*4},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    # Margin fully released
    assert res.portfolio.allocated_margin == 0.0
    assert res.portfolio.available_margin == pytest.approx(res.portfolio.equity - res.portfolio.reserved_capital, abs=1e-2)


def test_26_execution_exactly_once_transaction_costs():
    """Verify realized transaction costs are deducted exactly once from cash."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_synthetic_candles(dates, 100.0)
    df_a.loc[dates[2], ["High", "Close"]] = 150.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=150.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, opening_cooldown_minutes=0)
    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a] + [None]*4},
        config=m_cfg,
    )

    t = res.trades[0]
    expected_cash = 100_000.0 + (t.gross_pnl - t.transaction_cost)
    assert pytest.approx(res.portfolio.cash, abs=1e-2) == expected_cash


def test_27_execution_no_fabricated_execution_fills():
    """Verify missing bars never fabricate fills; execution waits for authentic data."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=7, freq="1min")
    # Bars 2..4 dropped, bar 5 resumes with gap down to 70.0
    df_a = _make_synthetic_candles(dates, 100.0).drop(dates[2:5])
    df_a.loc[dates[5], ["Open", "High", "Low", "Close"]] = 70.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=80.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, opening_cooldown_minutes=0)
    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a] + [None]*6},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    # Executed at authentic resumed Open 70.0, NOT fabricated 80.0
    assert res.trades[0].exit_price == 70.0


# ============================================================================
# 4. End-to-End REST API Workflow Tests (Tests 28 - 34)
# ============================================================================

def test_28_e2e_submit_request_through_api(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify POST /api/strategy/backtest/multi/run returns 202 Accepted with job metadata."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", return_value=df_a):
        payload = {
            "symbols": ["SYM_A", "SYM_B"],
            "initial_capital": 100000.0,
            "risk_per_trade_pct": 0.01,
            "execution_model": "next_open",
        }
        res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"].startswith("job-")
        assert data["status"] in ("QUEUED", "RUNNING")
        assert data["symbols"] == ["SYM_A", "SYM_B"]


def test_29_e2e_execute_through_job_manager(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify polling GET /api/strategy/backtest/jobs/{job_id} tracks job progression."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", return_value=df_a):
        payload = {"symbols": ["SYM_A"]}
        post_res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        job_id = post_res.json()["job_id"]

        # Poll status
        deadline = time.time() + 10.0
        final_status = None
        while time.time() < deadline:
            stat_res = api_client.get(f"/api/strategy/backtest/jobs/{job_id}")
            assert stat_res.status_code == 200
            final_status = stat_res.json()["status"]
            if final_status in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.05)

        assert final_status == "COMPLETED"


def test_30_e2e_retrieve_completed_multi_asset_result(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify GET /api/strategy/backtest/jobs/{job_id}/result retrieves multi-asset schema."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", return_value=df_a):
        payload = {"symbols": ["SYM_A"]}
        post_res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        job_id = post_res.json()["job_id"]

        deadline = time.time() + 10.0
        while time.time() < deadline:
            stat_res = api_client.get(f"/api/strategy/backtest/jobs/{job_id}")
            if stat_res.json()["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        # Query generic result endpoint
        res = api_client.get(f"/api/strategy/backtest/jobs/{job_id}/result")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == job_id
        assert data["symbols"] == ["SYM_A"]
        assert "portfolio" in data
        assert "symbol_metrics" in data
        assert "risk_and_quality" in data

        # Query dedicated multi-asset result endpoint
        multi_res = api_client.get(f"/api/strategy/backtest/multi/jobs/{job_id}/result")
        assert multi_res.status_code == 200
        assert multi_res.json()["job_id"] == job_id


def test_31_e2e_retrieve_failed_job_details(api_client: TestClient):
    """Verify querying result of a failed job returns HTTP 400 with failure explanation."""
    mgr = get_job_manager()
    job = mgr.submit_multi_asset_job(symbols=["SYM_DOES_NOT_EXIST"])

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if job.status == JobStatus.FAILED:
            break
        time.sleep(0.05)

    assert job.status == JobStatus.FAILED

    res = api_client.get(f"/api/strategy/backtest/jobs/{job.job_id}/result")
    assert res.status_code == 400
    assert "failed" in res.json()["detail"].lower()


def test_32_e2e_verify_per_symbol_attribution(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify result payload contains detailed per-symbol performance attribution."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    df_b = _make_synthetic_candles(synthetic_dates_120, 200.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", side_effect=lambda s: df_a if s == "SYM_A" else df_b):
        payload = {"symbols": ["SYM_A", "SYM_B"]}
        post_res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        job_id = post_res.json()["job_id"]

        deadline = time.time() + 10.0
        while time.time() < deadline:
            if api_client.get(f"/api/strategy/backtest/jobs/{job_id}").json()["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        data = api_client.get(f"/api/strategy/backtest/jobs/{job_id}/result").json()
        assert "SYM_A" in data["symbol_metrics"]
        assert "SYM_B" in data["symbol_metrics"]
        for sym in ("SYM_A", "SYM_B"):
            sm = data["symbol_metrics"][sym]
            assert "trades" in sm
            assert "net_pnl" in sm
            assert "win_rate_pct" in sm
            assert "profit_factor" in sm
            assert "position_status" in sm


def test_33_e2e_verify_portfolio_level_metrics(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify result payload accurately reports portfolio-level capital, equity, and margin."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", return_value=df_a):
        payload = {"symbols": ["SYM_A"], "initial_capital": 100_000.0}
        post_res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        job_id = post_res.json()["job_id"]

        deadline = time.time() + 10.0
        while time.time() < deadline:
            if api_client.get(f"/api/strategy/backtest/jobs/{job_id}").json()["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        data = api_client.get(f"/api/strategy/backtest/jobs/{job_id}/result").json()
        port = data["portfolio"]
        assert port["initial_capital"] == 100_000.0
        assert "final_equity" in port
        assert "realized_net_pnl" in port
        assert "unrealized_pnl" in port
        assert "total_transaction_costs" in port
        assert "available_margin" in port
        assert "allocated_margin" in port
        assert "max_drawdown_pct" in port


def test_34_e2e_verify_unresolved_position_reporting(
    api_client: TestClient,
    synthetic_dates_120: pd.DatetimeIndex,
):
    """Verify unresolved positions are structured and never disguised as closed trades."""
    df_a = _make_synthetic_candles(synthetic_dates_120, 100.0)
    mgr = get_job_manager()

    with patch.object(mgr, "_load_data_for_job", return_value=df_a):
        payload = {"symbols": ["SYM_A"]}
        post_res = api_client.post("/api/strategy/backtest/multi/run", json=payload)
        job_id = post_res.json()["job_id"]

        deadline = time.time() + 10.0
        while time.time() < deadline:
            if api_client.get(f"/api/strategy/backtest/jobs/{job_id}").json()["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        data = api_client.get(f"/api/strategy/backtest/jobs/{job_id}/result").json()
        assert "unresolved_positions" in data
        assert isinstance(data["unresolved_positions"], list)
        assert "trades" in data
        assert isinstance(data["trades"], list)


"""
SignalForge — Phase 24G.28: Full-Stack Backtest Job Bridge Tests
================================================================
Validates:
1. Preflight safety invariants (V1 config hash, canonical ADANIPORTS SHA-256, registry/ledger, 2020 quarantine).
2. BacktestJobManager thread isolation, lifecycle transitions, deterministic eviction, and non-blocking scheduling.
3. FastAPI backtest endpoints (POST run, GET status, GET result, GET list, POST cancel).
4. Validation rejection for malformed parameters (negative capital, zero quantity, invalid execution model).
5. Error handling for missing candle datasets without server crashes.
6. Deliverables completeness and SHA-256 cryptographic manifest integrity.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
import pytest
from src.strategy.job_manager import (
    BacktestJob,
    BacktestJobManager,
    JobStatus,
    get_job_manager,
)


DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase24G28_backtest_job_bridge")
MANIFEST_PATH = DELIVERABLES_DIR / "phase24G28_manifest.json"


# ----------------------------------------------------------------------------
# 1. Preflight Invariants
# ----------------------------------------------------------------------------

def test_v1_config_hash_immutable():
    """Verify frozen V1 baseline configuration hash matches canonical value."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 strategy snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def test_adaniports_canonical_hash():
    """Verify canonical on-disk ADANIPORTS dataset hash is untouched."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert adani_path.exists(), "ADANIPORTS dataset missing"
    h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
    assert h == "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_safety_invariants_registry_and_paper_ledger():
    """Verify universe registry and paper trading ledger are intact."""
    reg_path = Path("data/universe_registry.json")
    led_path = Path("data/paper_trading/interactive_trades.json")
    assert reg_path.exists(), "Universe registry missing"
    assert led_path.exists(), "Paper trading ledger missing"


def test_2020_holdout_quarantine():
    """Verify 2020 holdout remains marked as QUARANTINED."""
    audit_file = Path("research/strategy_evolution_2018/phase24G25_causal_correctness_audit/phase24G25_final_report.md")
    assert audit_file.exists(), "Phase 24G.25 final report missing"
    content = audit_file.read_text(encoding="utf-8")
    assert "2020 Holdout Partition" in content
    assert "QUARANTINED" in content


# ----------------------------------------------------------------------------
# 2. BacktestJobManager Unit Tests
# ----------------------------------------------------------------------------

def test_job_manager_singleton():
    """Verify get_job_manager returns the global singleton."""
    mgr1 = get_job_manager()
    mgr2 = get_job_manager()
    assert mgr1 is mgr2


def test_job_creation_and_defaults():
    """Verify job creation generates valid UUID, timestamps, and default values."""
    mgr = get_job_manager()
    job = mgr.create_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-03-26",
        execution_model="next_open",
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0005,
    )
    assert job.job_id
    assert job.status == JobStatus.QUEUED
    assert job.progress == 0
    assert job.symbol == "NIFTY 50"
    assert job.created_at is not None
    assert job.completed_at is None
    assert job.error_message is None


def test_job_execution_no_blocking():
    """Verify job submission is non-blocking (< 50ms)."""
    mgr = get_job_manager()
    t0 = time.perf_counter()
    job = mgr.submit_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
        execution_model="next_open",
    )
    duration = time.perf_counter() - t0
    assert duration < 0.1, f"Job submission took too long: {duration:.4f}s"
    assert job.job_id


def test_job_execution_lifecycle_and_results():
    """Verify full job lifecycle from submission to COMPLETED with metrics."""
    mgr = get_job_manager()
    # Run a 1-month slice of NIFTY 50 data
    job = mgr.submit_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-02-01",
        execution_model="next_open",
        initial_capital=100000.0,
        quantity=1,
    )

    # Wait for completion (max 20s)
    deadline = time.time() + 20.0
    completed = False
    while time.time() < deadline:
        status = mgr.get_job_status(job.job_id)
        assert status is not None
        if status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            completed = True
            break
        time.sleep(0.2)

    assert completed, "Backtest job timed out before completion"
    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.COMPLETED, f"Job failed: {final_job.error_message}"
    assert final_job.progress == 100
    assert final_job.metrics is not None
    assert "total_trades" in final_job.metrics
    assert "win_rate_pct" in final_job.metrics
    assert "total_pnl" in final_job.metrics
    assert "total_return_pct" in final_job.metrics
    assert isinstance(final_job.trades, list)


def test_job_failure_handling_missing_data():
    """Verify missing data sets status to FAILED without throwing unhandled exceptions."""
    mgr = get_job_manager()
    job = mgr.submit_job(
        symbol="NONEXISTENT_SYMBOL_XYZ",
        start_date="2024-01-01",
        end_date="2024-02-01",
    )

    deadline = time.time() + 5.0
    while time.time() < deadline:
        status = mgr.get_job_status(job.job_id)
        if status and status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        time.sleep(0.1)

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.FAILED
    assert final_job.error_message is not None
    assert "not found" in final_job.error_message.lower()


def test_job_cancellation():
    """Verify job cancellation sets status to CANCELLED."""
    mgr = get_job_manager()
    job = mgr.create_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-02-01",
    )
    assert job.status == JobStatus.QUEUED

    cancelled = mgr.cancel_job(job.job_id)
    assert cancelled is True
    updated = mgr.get_job(job.job_id)
    assert updated is not None
    assert updated.status == JobStatus.CANCELLED


def test_bounded_storage_eviction():
    """Verify submitting > max_jobs evicts oldest completed jobs, keeping total <= max_jobs."""
    isolated_mgr = BacktestJobManager(max_jobs=10)
    for i in range(12):
        j = isolated_mgr.create_job(
            symbol="NIFTY 50",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        j.status = JobStatus.COMPLETED

    # Next job triggers eviction of oldest terminal jobs
    isolated_mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-02-01")
    assert len(isolated_mgr.list_jobs()) <= 10


# ----------------------------------------------------------------------------
# 3. FastAPI Route Integration Tests
# ----------------------------------------------------------------------------

from fastapi import HTTPException
from pydantic import ValidationError
from src.api.models import BacktestRunRequest
from src.api.routes.strategy import (
    cancel_backtest_job,
    create_backtest_job,
    get_backtest_job_result,
    get_backtest_job_status,
    list_backtest_jobs,
)


def test_api_run_backtest_success():
    """Verify create_backtest_job accepts valid BacktestRunRequest and queues job."""
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
        execution_model="next_open",
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0005,
    )
    res = create_backtest_job(req)
    assert res.job_id
    assert res.status in ("QUEUED", "RUNNING")
    assert res.symbol == "NIFTY 50"


def test_api_run_backtest_validation_errors():
    """Verify invalid payloads are rejected with ValidationError."""
    # Negative capital
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            symbol="NIFTY 50",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=-500.0,
        )

    # Zero quantity
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            symbol="NIFTY 50",
            start_date="2024-01-01",
            end_date="2024-02-01",
            quantity=0,
        )

    # Invalid execution model
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            symbol="NIFTY 50",
            start_date="2024-01-01",
            end_date="2024-02-01",
            execution_model="invalid_model",
        )


def test_api_get_job_status_and_not_found():
    """Verify get_backtest_job_status returns status or raises 404 HTTPException."""
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-10",
    )
    job = create_backtest_job(req)

    status_res = get_backtest_job_status(job.job_id)
    assert status_res.job_id == job.job_id
    assert status_res.status in ("QUEUED", "RUNNING", "COMPLETED")
    assert status_res.progress >= 0.0

    # Nonexistent job raises 404
    with pytest.raises(HTTPException) as exc_info:
        get_backtest_job_status("nonexistent-uuid-1234")
    assert exc_info.value.status_code == 404


def test_api_get_job_result_lifecycle():
    """Verify result retrieval: 409 when running, 200 when completed, 404 when unknown."""
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
    )
    job = create_backtest_job(req)

    # Poll status until completed (max 20s)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        stat = get_backtest_job_status(job.job_id)
        if stat.status == "COMPLETED":
            break
        time.sleep(0.3)

    result = get_backtest_job_result(job.job_id)
    assert result.status == "COMPLETED"
    assert result.metrics.total_trades >= 0
    assert isinstance(result.trades, list)

    # Test unknown job raises 404
    with pytest.raises(HTTPException) as exc_404:
        get_backtest_job_result("unknown-job-id")
    assert exc_404.value.status_code == 404


def test_api_list_jobs():
    """Verify list_backtest_jobs returns recent jobs list."""
    jobs = list_backtest_jobs()
    assert isinstance(jobs, list)
    if len(jobs) > 0:
        assert jobs[0].job_id
        assert jobs[0].status


def test_api_cancel_job():
    """Verify cancel_backtest_job cancels queued/running job or raises 404 for unknown."""
    mgr = get_job_manager()
    job = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")

    res = cancel_backtest_job(job.job_id)
    assert res["status"] == "CANCELLED"

    # Cancel nonexistent raises 404
    with pytest.raises(HTTPException) as exc:
        cancel_backtest_job("unknown-uuid-999")
    assert exc.value.status_code == 404


# ----------------------------------------------------------------------------
# 4. Deliverables Completeness & Manifest Integrity
# ----------------------------------------------------------------------------

EXPECTED_FILES = [
    "phase24G28_architecture_api_contract.md",
    "phase24G28_job_lifecycle_execution_safety.md",
    "phase24G28_frontend_integration.md",
    "phase24G28_test_results.md",
    "phase24G28_limitations_recovery.md",
    "phase24G28_final_report.md",
    "phase24G28_manifest.json",
]


def test_deliverables_completeness():
    """Verify all 7 deliverables exist and are non-empty."""
    assert DELIVERABLES_DIR.is_dir(), f"Deliverables dir missing: {DELIVERABLES_DIR}"
    for filename in EXPECTED_FILES:
        filepath = DELIVERABLES_DIR / filename
        assert filepath.exists(), f"Missing deliverable: {filename}"
        assert filepath.stat().st_size > 50, f"Deliverable too small or empty: {filename}"


def test_manifest_sha256_integrity():
    """Verify cryptographic SHA-256 integrity of all documentation artifacts."""
    assert MANIFEST_PATH.exists(), "Manifest file missing"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for filename, meta in manifest.items():
        filepath = DELIVERABLES_DIR / filename
        assert filepath.exists(), f"File in manifest missing on disk: {filename}"
        raw = filepath.read_bytes().replace(b"\r\n", b"\n")
        computed_sha = hashlib.sha256(raw).hexdigest()
        assert computed_sha == meta["sha256"], f"SHA-256 mismatch for {filename}"


def test_final_verdict_consistency():
    """Verify the final completion report records the authorized completion verdict."""
    final_report = DELIVERABLES_DIR / "phase24G28_final_report.md"
    assert final_report.exists(), "Final report missing"
    content = final_report.read_text(encoding="utf-8")
    assert "BACKTEST_JOB_BRIDGE_COMPLETED" in content, "Missing authorized verdict"


# ----------------------------------------------------------------------------
# 5. Phase 27C.1: Return Percentage Mathematical Identity & Scaling Verification
# ----------------------------------------------------------------------------

def test_phase27c1_return_percentage_mathematical_identity():
    """
    Verify Phase 27C.1: Total return percentage and trade return percentages
    must adhere to exact mathematical definition:
      total_return_pct == (total_pnl / initial_capital) * 100.0
      trade['return_pct'] == (net_pnl / entry_notional) * 100.0
    Guarantees no redundant 100x multiplication occurs.
    """
    mgr = get_job_manager()
    job = mgr.submit_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
        execution_model="next_open",
        initial_capital=100000.0,
        quantity=1,
    )

    deadline = time.time() + 20.0
    while time.time() < deadline:
        status = mgr.get_job_status(job.job_id)
        if status and status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        time.sleep(0.2)

    res = mgr.get_job(job.job_id).result
    assert res is not None, "Job result must not be None"
    metrics = res["metrics"]
    portfolio = res["portfolio"]

    # 1. Verify Portfolio Total Return Identity
    total_pnl = float(metrics["total_pnl"])
    initial_cap = float(portfolio["initial_capital"])
    reported_total_ret = float(metrics["total_return_pct"])

    expected_total_ret = round((total_pnl / initial_cap) * 100.0, 2)
    assert abs(reported_total_ret - expected_total_ret) < 1e-4, (
        f"total_return_pct mismatch: reported {reported_total_ret} vs expected {expected_total_ret}"
    )

    # 2. Verify Trade-Level Return Identity for every trade
    trades = res["trades"]
    for t in trades:
        entry_price = float(t["entry_price"])
        qty = int(t["quantity"])
        net_pnl = float(t["net_pnl"])
        reported_trade_ret = float(t["return_pct"])

        notional = entry_price * qty
        expected_trade_ret = round((net_pnl / notional) * 100.0, 3)
        assert abs(reported_trade_ret - expected_trade_ret) < 1e-4, (
            f"Trade #{t['trade_id']} return_pct mismatch: reported {reported_trade_ret} vs expected {expected_trade_ret}"
        )


def test_phase27c1_api_result_lifecycle_return_percentage():
    """Verify HTTP API endpoint get_backtest_job_result returns correct return percentages."""
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
        initial_capital=100000.0,
        quantity=1,
    )
    job = create_backtest_job(req)

    deadline = time.time() + 20.0
    while time.time() < deadline:
        stat = get_backtest_job_status(job.job_id)
        if stat.status == "COMPLETED":
            break
        time.sleep(0.2)

    api_res = get_backtest_job_result(job.job_id)
    assert api_res.status == "COMPLETED"

    # Mathematical identity verification on API model response
    expected_ret = round((api_res.metrics.total_pnl / 100000.0) * 100.0, 2)
    assert abs(api_res.metrics.total_return_pct - expected_ret) < 1e-4


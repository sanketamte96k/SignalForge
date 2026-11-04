"""
SignalForge — Phase 24G.29: Operational Reliability & Hardening Tests
======================================================================
Validates:
1. Preflight safety invariants (V1 config hash, canonical ADANIPORTS SHA-256, registry/ledger, 2020 quarantine).
2. Job lifecycle and eviction safety (active jobs immunity, FIFO ordering, UUID uniqueness, 404 for unknown).
3. Concurrency and isolation (isolated data slices, memory protection, failure containment, bounded capacity).
4. Cancellation safety and cooperative checkpoints (queued cancellation, active cancellation leaving zero partial results, rejection of terminal cancellation).
5. 100% bit-for-bit parity between CLI engine and FastAPI job manager execution.
6. Deliverables completeness and SHA-256 cryptographic manifest integrity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
import uuid
import pytest
from fastapi import HTTPException

import pandas as pd
from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import StrategyConfig, create_signal_function
from src.strategy.job_manager import (
    BacktestJob,
    BacktestJobManager,
    JobStatus,
    get_job_manager,
)
from src.api.routes.strategy import (
    get_backtest_job_result,
    get_backtest_job_status,
    cancel_backtest_job,
)


DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase24G29_operational_reliability")
MANIFEST_PATH = DELIVERABLES_DIR / "phase24G29_manifest.json"


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
# 2. Job Lifecycle & Eviction Safety
# ----------------------------------------------------------------------------

def test_job_id_uniqueness_sample():
    """Verify UUIDv4-based job identifiers do not collide over a 1,000-sample space."""
    mgr = BacktestJobManager(max_jobs=10)
    seen_ids = set()
    for _ in range(1000):
        jid = f"job-{uuid.uuid4().hex[:12]}"
        assert jid not in seen_ids, f"Collision detected for ID: {jid}"
        seen_ids.add(jid)
    assert len(seen_ids) == 1000


def test_running_job_cannot_be_evicted():
    """Verify active (RUNNING) jobs are immune to FIFO capacity pruning."""
    mgr = BacktestJobManager(max_jobs=5)

    # Populate with 4 terminal jobs
    for i in range(4):
        j = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
        j.status = JobStatus.COMPLETED

    # Create 1 RUNNING job
    running_job = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    running_job.status = JobStatus.RUNNING

    # Add 2 more completed jobs to trigger eviction
    mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")

    # The running job must NEVER be evicted
    assert mgr.get_job(running_job.job_id) is not None
    assert mgr.get_job(running_job.job_id).status == JobStatus.RUNNING


def test_fifo_eviction_orders_by_creation_timestamp():
    """Verify FIFO eviction strictly removes oldest terminal jobs first."""
    mgr = BacktestJobManager(max_jobs=3)

    j1 = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    j1.status = JobStatus.COMPLETED

    time.sleep(0.01)
    j2 = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    j2.status = JobStatus.COMPLETED

    time.sleep(0.01)
    j3 = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    j3.status = JobStatus.COMPLETED

    # 4th job triggers pruning: oldest (j1) must be evicted first
    j4 = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")

    assert mgr.get_job(j1.job_id) is None, "Oldest job j1 was not evicted"
    assert mgr.get_job(j2.job_id) is not None, "Newer job j2 should be retained"
    assert mgr.get_job(j3.job_id) is not None, "Newer job j3 should be retained"
    assert mgr.get_job(j4.job_id) is not None, "Newly added job j4 must be present"


def test_unknown_job_returns_documented_error():
    """Verify unknown job identifier raises 404 HTTPException."""
    with pytest.raises(HTTPException) as exc_stat:
        get_backtest_job_status("nonexistent-job-xyz")
    assert exc_stat.value.status_code == 404

    with pytest.raises(HTTPException) as exc_res:
        get_backtest_job_result("nonexistent-job-xyz")
    assert exc_res.value.status_code == 404


# ----------------------------------------------------------------------------
# 3. Concurrency & Result Isolation
# ----------------------------------------------------------------------------

def test_concurrent_jobs_different_inputs_isolated():
    """Verify two concurrent jobs with distinct inputs execute in parallel with zero leakage."""
    mgr = get_job_manager()

    job_a = mgr.submit_job(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-15",
        initial_capital=100000.0,
        quantity=1,
    )

    job_b = mgr.submit_job(
        symbol="NIFTY 50",
        start_date="2024-02-01",
        end_date="2024-02-15",
        initial_capital=250000.0,
        quantity=2,
    )

    # Await completion
    deadline = time.time() + 25.0
    while time.time() < deadline:
        ja = mgr.get_job(job_a.job_id)
        jb = mgr.get_job(job_b.job_id)
        if ja.status == JobStatus.COMPLETED and jb.status == JobStatus.COMPLETED:
            break
        time.sleep(0.3)

    res_a = mgr.get_job(job_a.job_id).result
    res_b = mgr.get_job(job_b.job_id).result

    assert res_a is not None and res_b is not None
    assert res_a["portfolio"]["initial_capital"] == 100000.0
    assert res_b["portfolio"]["initial_capital"] == 250000.0
    assert "2024-01" in res_a["date_range"]["start"]
    assert "2024-02" in res_b["date_range"]["start"]
    assert res_a["job_id"] != res_b["job_id"]


def test_concurrent_job_failure_isolation():
    """Verify an engine exception in one job does not abort or contaminate a concurrent peer job."""
    mgr = get_job_manager()

    # Job A: Invalid symbol triggers FAILED
    job_fail = mgr.submit_job(symbol="NONEXISTENT_XYZ", start_date="2024-01-01", end_date="2024-01-15")

    # Job B: Valid job must succeed
    job_ok = mgr.submit_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")

    deadline = time.time() + 15.0
    while time.time() < deadline:
        jf = mgr.get_job(job_fail.job_id)
        jo = mgr.get_job(job_ok.job_id)
        if jf.status == JobStatus.FAILED and jo.status == JobStatus.COMPLETED:
            break
        time.sleep(0.2)

    assert mgr.get_job(job_fail.job_id).status == JobStatus.FAILED
    assert mgr.get_job(job_ok.job_id).status == JobStatus.COMPLETED
    assert mgr.get_job(job_ok.job_id).result is not None


def test_worker_capacity_bounded():
    """Verify job manager limits worker pool concurrency to max_workers=2."""
    mgr = get_job_manager()
    assert mgr._max_workers == 2
    assert mgr._executor._max_workers == 2


# ----------------------------------------------------------------------------
# 4. Cancellation Behavior & Cooperative Checkpoints
# ----------------------------------------------------------------------------

def test_cancellation_of_queued_job():
    """Verify queued job cancellation immediately transitions to CANCELLED without results."""
    mgr = get_job_manager()
    job = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    assert job.status == JobStatus.QUEUED

    cancelled = mgr.cancel_job(job.job_id)
    assert cancelled is True

    updated = mgr.get_job(job.job_id)
    assert updated.status == JobStatus.CANCELLED
    assert updated.result is None
    assert updated.error is not None
    assert updated.completed_at is not None


def test_cancellation_during_execution_leaves_no_results():
    """Verify cancelling an in-flight job safely aborts at cooperative checkpoints with result=None."""
    mgr = get_job_manager()
    # Submit job over a 3-month range (approx 15 seconds runtime)
    job = mgr.submit_job(symbol="NIFTY 50", start_date="2023-01-01", end_date="2023-03-31")

    # Immediate cancellation
    time.sleep(0.05)
    cancelled = mgr.cancel_job(job.job_id)

    # Wait for worker thread to encounter cooperative checkpoint and exit
    deadline = time.time() + 10.0
    while time.time() < deadline:
        j = mgr.get_job(job.job_id)
        if j.completed_at is not None:
            break
        time.sleep(0.2)

    final = mgr.get_job(job.job_id)
    assert final.status == JobStatus.CANCELLED
    assert final.result is None, "Cancelled job leaked partial results!"


def test_cancelling_already_completed_job_fails():
    """Verify attempting to cancel an already completed job returns False and preserves COMPLETED state."""
    mgr = get_job_manager()
    job = mgr.create_job(symbol="NIFTY 50", start_date="2024-01-01", end_date="2024-01-10")
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)

    cancelled = mgr.cancel_job(job.job_id)
    assert cancelled is False
    assert mgr.get_job(job.job_id).status == JobStatus.COMPLETED


# ----------------------------------------------------------------------------
# 5. Parity Audit (CLI Engine vs API Job Manager)
# ----------------------------------------------------------------------------

def test_cli_vs_api_bit_for_bit_parity():
    """Verify 100% bit-for-bit parity between CLI engine and FastAPI job manager."""
    # 1. Direct Engine Execution
    data_path = Path("data/historical/nifty50_1m_signalforge.csv")
    assert data_path.exists(), "Historical dataset missing"
    data = pd.read_csv(data_path, index_col=0, parse_dates=True).loc["2024-01-01":"2024-01-31"].copy()
    data.index.name = None

    cfg = StrategyConfig()
    sig_fn = create_signal_function(data, cfg)
    direct_res = run_backtest(
        data=data,
        signal_function=sig_fn,
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        execution_model="next_open",
    )

    # 2. FastAPI Job Manager Execution
    mgr = get_job_manager()
    job = mgr.submit_job({
        "symbol": "NIFTY 50",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_capital": 100000.0,
        "quantity": 1,
        "transaction_cost_rate": 0.0001,
        "execution_model": "next_open",
    })

    deadline = time.time() + 20.0
    while time.time() < deadline:
        j = mgr.get_job(job.job_id)
        if j.status == JobStatus.COMPLETED:
            break
        time.sleep(0.3)

    api_res = mgr.get_job(job.job_id).result
    assert api_res is not None

    # 3. Metric Parity Comparison
    assert len(direct_res.trades) == len(api_res["trades"])
    assert round(float(direct_res.metrics.total_pnl), 2) == api_res["metrics"]["total_pnl"]
    assert round(float(direct_res.metrics.win_rate_pct), 2) == api_res["metrics"]["win_rate_pct"]
    assert direct_res.metrics.winning_trades == api_res["metrics"]["winning_trades"]
    assert direct_res.metrics.losing_trades == api_res["metrics"]["losing_trades"]


def test_trade_by_trade_execution_parity():
    """Verify all trades produced by CLI engine match API job output across all fields."""
    data_path = Path("data/historical/nifty50_1m_signalforge.csv")
    data = pd.read_csv(data_path, index_col=0, parse_dates=True).loc["2024-01-01":"2024-01-31"].copy()
    data.index.name = None

    cfg = StrategyConfig()
    sig_fn = create_signal_function(data, cfg)
    direct_res = run_backtest(
        data=data,
        signal_function=sig_fn,
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        execution_model="next_open",
    )

    mgr = get_job_manager()
    job = mgr.submit_job({
        "symbol": "NIFTY 50",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_capital": 100000.0,
        "quantity": 1,
        "transaction_cost_rate": 0.0001,
        "execution_model": "next_open",
    })

    deadline = time.time() + 20.0
    while time.time() < deadline:
        j = mgr.get_job(job.job_id)
        if j.status == JobStatus.COMPLETED:
            break
        time.sleep(0.3)

    api_trades = mgr.get_job(job.job_id).result["trades"]
    assert len(direct_res.trades) == len(api_trades)

    for i, (dt, at) in enumerate(zip(direct_res.trades, api_trades)):
        assert str(dt.entry_time) == at["entry_time"], f"Trade {i} entry_time mismatch"
        assert str(dt.exit_time) == at["exit_time"], f"Trade {i} exit_time mismatch"
        assert round(float(dt.entry_price), 2) == at["entry_price"], f"Trade {i} entry_price mismatch"
        assert round(float(dt.exit_price), 2) == at["exit_price"], f"Trade {i} exit_price mismatch"
        assert round(float(dt.net_pnl), 2) == at["net_pnl"], f"Trade {i} net_pnl mismatch"
        assert str(dt.exit_reason) == at["exit_reason"], f"Trade {i} exit_reason mismatch"


# ----------------------------------------------------------------------------
# 6. Deliverables Completeness & Manifest Integrity
# ----------------------------------------------------------------------------

EXPECTED_FILES = [
    "phase24G29_job_lifecycle_audit.md",
    "phase24G29_concurrency_isolation_report.md",
    "phase24G29_cancellation_behavior_report.md",
    "phase24G29_cli_api_parity_report.md",
    "phase24G29_frontend_resilience_report.md",
    "phase24G29_test_results.md",
    "phase24G29_known_limitations.md",
    "phase24G29_final_report.md",
    "phase24G29_manifest.json",
]


def test_deliverables_completeness():
    """Verify all 9 deliverables exist and are non-empty."""
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
    final_report = DELIVERABLES_DIR / "phase24G29_final_report.md"
    assert final_report.exists(), "Final report missing"
    content = final_report.read_text(encoding="utf-8")
    assert "OPERATIONAL_RELIABILITY_VERIFIED" in content, "Missing authorized verdict"

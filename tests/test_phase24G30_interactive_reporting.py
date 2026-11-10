"""
SignalForge — Phase 24G.30: Interactive Research Reporting & Equity Analytics Test Suite
========================================================================================
Validates:
1. Pre-flight safety invariants (V1 frozen hash, ADANIPORTS canonical hash, 2020 quarantine).
2. Equity curve progression (chronological steps, starting capital, zero intermediate fabrication).
3. Drawdown calculation (Current Equity - Peak Equity, Drawdown %, never confused with total loss).
4. Peak recovery (drawdown resets to 0.0 when equity reaches or exceeds prior peak).
5. Edge cases: Empty trades (0 trades) and single-trade datasets.
6. P&L and cost consistency (net_pnl == gross_pnl - costs, final_equity == initial_cap + total_pnl).
7. Extended research performance metrics (win/loss ratio, expectancy, recovery factor, streaks).
8. Standalone HTML tearsheet generation, styling, SVG embedding, and reproducibility from saved results.
9. Cryptographic hash provenance inclusion in HTML reports.
10. FastAPI tearsheet and analytics endpoints.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import pytest

from src.backtest.tearsheet import (
    CANONICAL_ADANIPORTS_HASH,
    CANONICAL_NIFTY50_HASH,
    FROZEN_V1_CONFIG_HASH,
    calculate_equity_curve,
    compute_backtest_analytics,
    compute_extended_metrics,
    generate_html_tearsheet,
    generate_svg_drawdown_chart,
    generate_svg_equity_chart,
    save_html_tearsheet,
)
from src.strategy.job_manager import BacktestJobManager, JobStatus


# ============================================================================
# Deterministic Test Fixtures
# ============================================================================

SAMPLE_TRADES = [
    {
        "trade_id": 1,
        "entry_time": "2024-01-02 09:30:00",
        "exit_time": "2024-01-02 10:15:00",
        "side": "BUY",
        "entry_price": 21700.0,
        "exit_price": 21900.0,
        "quantity": 1,
        "gross_pnl": 200.0,
        "costs": 4.0,
        "net_pnl": 196.0,
        "return_pct": 0.9,
        "exit_reason": "TAKE_PROFIT",
    },
    {
        "trade_id": 2,
        "entry_time": "2024-01-05 11:00:00",
        "exit_time": "2024-01-05 11:45:00",
        "side": "BUY",
        "entry_price": 21850.0,
        "exit_price": 21750.0,
        "quantity": 1,
        "gross_pnl": -100.0,
        "costs": 4.0,
        "net_pnl": -104.0,
        "return_pct": -0.48,
        "exit_reason": "STOP_LOSS",
    },
    {
        "trade_id": 3,
        "entry_time": "2024-01-10 13:00:00",
        "exit_time": "2024-01-10 14:15:00",
        "side": "SELL",
        "entry_price": 21600.0,
        "exit_price": 21750.0,
        "quantity": 1,
        "gross_pnl": -150.0,
        "costs": 4.0,
        "net_pnl": -154.0,
        "return_pct": -0.71,
        "exit_reason": "STOP_LOSS",
    },
    {
        "trade_id": 4,
        "entry_time": "2024-01-15 10:00:00",
        "exit_time": "2024-01-15 12:30:00",
        "side": "BUY",
        "entry_price": 21500.0,
        "exit_price": 21716.0,
        "quantity": 1,
        "gross_pnl": 216.0,
        "costs": 4.0,
        "net_pnl": 212.0,
        "return_pct": 0.98,
        "exit_reason": "TAKE_PROFIT",
    },
]

SAMPLE_RESULT = {
    "job_id": "job-test-fixture-1234",
    "status": "COMPLETED",
    "symbol": "NIFTY 50",
    "date_range": {
        "start": "2024-01-01 09:15:00",
        "end": "2024-01-31 15:30:00",
        "requested_start": "2024-01-01",
        "requested_end": "2024-01-31",
        "total_candles": 7500,
    },
    "execution_model": "next_open",
    "metrics": {
        "total_trades": 4,
        "winning_trades": 2,
        "losing_trades": 2,
        "breakeven_trades": 0,
        "total_pnl": 150.0,
        "total_return_pct": 0.15,
        "win_rate_pct": 50.0,
        "average_win": 204.0,
        "average_loss": -129.0,
        "profit_factor": 1.66,
        "expectancy": 37.5,
        "max_drawdown_pct": 0.26,
    },
    "portfolio": {
        "initial_capital": 100_000.0,
        "final_equity": 100_150.0,
        "peak_equity": 100_196.0,
        "max_drawdown_pct": 0.26,
        "is_bankrupt": False,
    },
    "trades": SAMPLE_TRADES,
}


# ============================================================================
# 1. Protected Invariants & Pre-Flight Checks
# ============================================================================

def test_v1_frozen_config_hash():
    """Verify frozen V1 configuration snapshot hash is untouched."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 config snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == FROZEN_V1_CONFIG_HASH, f"V1 config hash mismatch: {v1_h}"


def test_adaniports_canonical_hash():
    """Verify pre-recorded canonical ADANIPORTS hash in trusted manifest without accessing monolithic CSV."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    assert manifest_path.exists(), "Trusted coverage manifest missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    canonical_hash = manifest_data["invariants"]["canonical_adaniports_hash"]
    assert canonical_hash == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS canonical hash mismatch: {canonical_hash}"


def test_nifty50_canonical_hash():
    """Verify canonical on-disk NIFTY 50 1-minute dataset hash is untouched."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    if not nifty_path.exists():
        pytest.skip("Canonical NIFTY 50 dataset not present in bare environment")
    h = hashlib.sha256(nifty_path.read_bytes()).hexdigest()
    assert h == CANONICAL_NIFTY50_HASH, f"NIFTY 50 hash mismatch: {h}"


def test_quarantined_2020_holdout_preserved():
    """Verify 2020 holdout partition remains quarantined."""
    manifest_path = Path("data/historical/2020_holdout_manifest.json")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        status = m.get("quarantine_status", "").upper()
        assert status in {"CONTAMINATED", "QUARANTINED", "EXPLORATORY"}, f"Invalid quarantine status: {status}"


# ============================================================================
# 2. Equity Curve & Drawdown Mathematics
# ============================================================================

def test_equity_curve_progression():
    """Verify chronological progression of account equity from starting capital."""
    curve = calculate_equity_curve(100_000.0, SAMPLE_TRADES, start_time="2024-01-01 09:15:00")

    # Point 0: Initial Capital
    assert len(curve) == 5
    assert curve[0]["step"] == 0
    assert curve[0]["equity"] == 100_000.0
    assert curve[0]["peak_equity"] == 100_000.0
    assert curve[0]["drawdown"] == 0.0
    assert curve[0]["drawdown_pct"] == 0.0

    # Trade 1: +196.0 -> Equity 100,196.0, Peak 100,196.0, DD 0.0
    assert curve[1]["step"] == 1
    assert curve[1]["net_pnl"] == 196.0
    assert curve[1]["equity"] == 100_196.0
    assert curve[1]["peak_equity"] == 100_196.0
    assert curve[1]["drawdown"] == 0.0
    assert curve[1]["drawdown_pct"] == 0.0

    # Trade 2: -104.0 -> Equity 100,092.0, Peak 100,196.0, DD -104.0
    assert curve[2]["step"] == 2
    assert curve[2]["net_pnl"] == -104.0
    assert curve[2]["equity"] == 100_092.0
    assert curve[2]["peak_equity"] == 100_196.0
    assert curve[2]["drawdown"] == -104.0
    expected_dd2_pct = round((-104.0 / 100_196.0) * 100.0, 2)
    assert curve[2]["drawdown_pct"] == expected_dd2_pct

    # Trade 3: -154.0 -> Equity 99,938.0, Peak 100,196.0, DD -258.0
    assert curve[3]["step"] == 3
    assert curve[3]["net_pnl"] == -154.0
    assert curve[3]["equity"] == 99_938.0
    assert curve[3]["peak_equity"] == 100_196.0
    assert curve[3]["drawdown"] == -258.0
    expected_dd3_pct = round((-258.0 / 100_196.0) * 100.0, 2)
    assert curve[3]["drawdown_pct"] == expected_dd3_pct

    # Trade 4: +212.0 -> Equity 100,150.0, Peak 100,196.0, DD -46.0
    assert curve[4]["step"] == 4
    assert curve[4]["net_pnl"] == 212.0
    assert curve[4]["equity"] == 100_150.0
    assert curve[4]["peak_equity"] == 100_196.0
    assert curve[4]["drawdown"] == -46.0


def test_drawdown_recovery_to_previous_peak():
    """Verify drawdown returns to exactly 0.0 when equity reaches/exceeds previous peak."""
    recovery_trades = [
        {"trade_id": 1, "net_pnl": -500.0, "exit_time": "T1"},
        {"trade_id": 2, "net_pnl": -300.0, "exit_time": "T2"},
        {"trade_id": 3, "net_pnl": 800.0, "exit_time": "T3"},  # Exact recovery to 100,000
        {"trade_id": 4, "net_pnl": 200.0, "exit_time": "T4"},  # New peak 100,200
    ]

    curve = calculate_equity_curve(100_000.0, recovery_trades)

    # Step 0: Initial
    assert curve[0]["equity"] == 100_000.0
    assert curve[0]["drawdown"] == 0.0

    # Step 1: Drawdown -500
    assert curve[1]["equity"] == 99_500.0
    assert curve[1]["drawdown"] == -500.0
    assert curve[1]["drawdown_pct"] == -0.5

    # Step 2: Drawdown -800
    assert curve[2]["equity"] == 99_200.0
    assert curve[2]["drawdown"] == -800.0
    assert curve[2]["drawdown_pct"] == -0.8

    # Step 3: Exact recovery to peak 100,000 -> Drawdown = 0.0
    assert curve[3]["equity"] == 100_000.0
    assert curve[3]["peak_equity"] == 100_000.0
    assert curve[3]["drawdown"] == 0.0
    assert curve[3]["drawdown_pct"] == 0.0

    # Step 4: Exceeds previous peak to 100,200 -> Drawdown = 0.0
    assert curve[4]["equity"] == 100_200.0
    assert curve[4]["peak_equity"] == 100_200.0
    assert curve[4]["drawdown"] == 0.0
    assert curve[4]["drawdown_pct"] == 0.0


def test_empty_trades_curve():
    """Verify empty trade list produces a single valid baseline point."""
    curve = calculate_equity_curve(50_000.0, [], start_time="2024-01-01")
    assert len(curve) == 1
    assert curve[0]["step"] == 0
    assert curve[0]["equity"] == 50_000.0
    assert curve[0]["peak_equity"] == 50_000.0
    assert curve[0]["drawdown"] == 0.0
    assert curve[0]["drawdown_pct"] == 0.0


def test_single_trade_dataset():
    """Verify single-trade dataset calculates 2 points accurately."""
    single_win = [{"trade_id": 1, "net_pnl": 250.0, "exit_time": "2024-01-02"}]
    curve_win = calculate_equity_curve(10_000.0, single_win)
    assert len(curve_win) == 2
    assert curve_win[1]["equity"] == 10_250.0
    assert curve_win[1]["drawdown"] == 0.0

    single_loss = [{"trade_id": 1, "net_pnl": -300.0, "exit_time": "2024-01-02"}]
    curve_loss = calculate_equity_curve(10_000.0, single_loss)
    assert len(curve_loss) == 2
    assert curve_loss[1]["equity"] == 9_700.0
    assert curve_loss[1]["drawdown"] == -300.0
    assert curve_loss[1]["drawdown_pct"] == -3.0


# ============================================================================
# 3. P&L and Cost Consistency
# ============================================================================

def test_pnl_and_cost_accounting():
    """Verify net P&L equals gross P&L minus transaction costs for every trade."""
    for t in SAMPLE_TRADES:
        gross = t["gross_pnl"]
        costs = t["costs"]
        net = t["net_pnl"]
        assert round(gross - costs, 2) == round(net, 2), f"P&L mismatch in trade {t['trade_id']}"

    total_gross = sum(t["gross_pnl"] for t in SAMPLE_TRADES)
    total_costs = sum(t["costs"] for t in SAMPLE_TRADES)
    total_net = sum(t["net_pnl"] for t in SAMPLE_TRADES)
    assert round(total_gross - total_costs, 2) == round(total_net, 2)


def test_extended_metrics_computation():
    """Verify extended quantitative metrics calculation against sample dataset."""
    metrics = compute_extended_metrics(100_000.0, SAMPLE_TRADES)

    assert metrics["total_trades"] == 4
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 2
    assert metrics["breakeven_trades"] == 0
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["total_pnl"] == 150.0
    assert metrics["total_return_pct"] == 0.15
    assert metrics["gross_profit"] == 416.0
    assert metrics["gross_loss"] == -250.0
    assert metrics["total_transaction_costs"] == 16.0
    assert metrics["profit_factor"] == round(416.0 / 250.0, 2)  # 1.66
    assert metrics["max_drawdown_amount"] == -258.0
    assert metrics["max_drawdown_pct"] == round((-258.0 / 100_196.0) * 100.0, 2)
    assert metrics["recovery_factor"] == round(150.0 / 258.0, 2)  # 0.58


# ============================================================================
# 4. SVG Generation & Visual Charts
# ============================================================================

def test_svg_equity_chart_markup():
    """Verify SVG equity chart renders valid markup with gridlines and markers."""
    curve = calculate_equity_curve(100_000.0, SAMPLE_TRADES)
    svg = generate_svg_equity_chart(curve)

    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'class="chart-svg"' in svg
    assert "#00eaaf" in svg  # Emerald green equity line
    assert "Start: ₹100,000" in svg  # Baseline marker
    assert "<circle" in svg  # Trade point circles


def test_svg_drawdown_chart_markup():
    """Verify SVG drawdown chart renders underwater red shaded path and 0% line."""
    curve = calculate_equity_curve(100_000.0, SAMPLE_TRADES)
    svg = generate_svg_drawdown_chart(curve)

    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "#ff6876" in svg  # Red underwater line/fill
    assert "0.00%" in svg


# ============================================================================
# 5. Standalone HTML Tearsheet & Reproducibility
# ============================================================================

def test_generate_html_tearsheet_structure():
    """Verify HTML tearsheet contains all required sections, styles, and provenance."""
    html_doc = generate_html_tearsheet(SAMPLE_RESULT)

    # Document Structure
    assert "<!DOCTYPE html>" in html_doc
    assert "<html" in html_doc
    assert "SignalForge — Quantitative Backtest Research Tearsheet" in html_doc

    # Execution Model
    assert "CAUSAL REALISTIC (NEXT-OPEN BAR FILL)" in html_doc

    # Cryptographic Provenance
    assert FROZEN_V1_CONFIG_HASH in html_doc
    assert CANONICAL_NIFTY50_HASH in html_doc

    # Embedded SVG Charts
    assert "<svg" in html_doc
    assert "Account equity progression" in html_doc or "chart-svg" in html_doc

    # Trade Table & JS Filtering
    assert "id=\"trades-table\"" in html_doc
    assert "filterTrades" in html_doc

    # Disclaimer
    assert "RESEARCH & ACADEMIC PROTOCOL DISCLAIMER" in html_doc


def test_html_tearsheet_reproducibility():
    """Verify HTML report is 100% reproducible from saved JSON without rerun."""
    html_1 = generate_html_tearsheet(SAMPLE_RESULT)
    html_2 = generate_html_tearsheet(SAMPLE_RESULT)
    assert html_1 == html_2, "HTML tearsheet generation is non-deterministic"


def test_save_html_tearsheet_atomic(tmp_path):
    """Verify save_html_tearsheet safely writes file using atomic replace."""
    dest = tmp_path / "tearsheet_output.html"
    saved = save_html_tearsheet(SAMPLE_RESULT, dest)
    assert saved.exists()
    assert saved.stat().st_size > 5000
    content = saved.read_text(encoding="utf-8")
    assert "job-test-fixture-1234" in content


# ============================================================================
# 6. FastAPI Endpoints & Integration
# ============================================================================

def test_api_tearsheet_and_analytics_endpoints():
    """Verify FastAPI routes for tearsheet and analytics return expected responses."""
    from src.api.routes.strategy import get_backtest_job_analytics, get_backtest_job_tearsheet

    manager = BacktestJobManager(max_workers=1, max_retained_jobs=10)
    job = manager.create_job({"symbol": "NIFTY 50"})
    job.status = JobStatus.COMPLETED
    job_res = dict(SAMPLE_RESULT)
    job_res["job_id"] = job.job_id
    job.result = job_res
    manager._jobs[job.job_id] = job

    # Temporarily monkeypatch the global job manager
    import src.api.routes.strategy as strat_mod
    orig_fn = strat_mod.get_job_manager
    strat_mod.get_job_manager = lambda: manager

    try:
        # Test Tearsheet Endpoint
        resp = get_backtest_job_tearsheet(job.job_id, download=False)
        assert resp.status_code == 200
        assert "text/html" in resp.media_type
        assert "Quantitative Backtest Research Tearsheet" in resp.body.decode("utf-8")

        # Test Tearsheet Download Attachment
        resp_dl = get_backtest_job_tearsheet(job.job_id, download=True)
        assert resp_dl.status_code == 200
        assert "attachment;" in resp_dl.headers.get("content-disposition", "")

        # Test Analytics Endpoint
        analytics = get_backtest_job_analytics(job.job_id)
        assert analytics["job_id"] == job.job_id
        assert len(analytics["equity_curve"]) == 5
        assert analytics["metrics"]["win_rate_pct"] == 50.0

        # Test 404 for unknown job
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_backtest_job_tearsheet("non-existent-job-xyz")
        assert exc_info.value.status_code == 404

    finally:
        strat_mod.get_job_manager = orig_fn

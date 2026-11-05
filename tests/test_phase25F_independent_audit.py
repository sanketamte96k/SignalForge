"""
SignalForge — Phase 25F Independent Forensic Audit Test Suite
=============================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config hash, ADANIPORTS, NIFTY 50, paper ledger, universe registry, 2020 quarantine).
  2. Deliverables completeness (9 files in research/strategy_evolution_2018/phase25F_independent_audit/).
  3. Discrepancy threshold enforcement (0 failures across all 418 metric checks, max P&L difference <= 0.01).
  4. Classification distribution integrity (0 positive, 31 negative, 4 inconclusive, 3 insufficient sample).
  5. Cost reconciliation mathematical identities (turnover scaling, 100% brokerage cap saturation in portfolio, exact statutory tax ratios).
  6. Shared-capital portfolio simulation reproduction (₹10 Lakh starting, ₹285,174.66 ending equity, 90.30% drawdown, 78.20% rejection rate).
  7. Final research verdict verification (REPRODUCED_AND_CONFIRMED).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
import pandas as pd

FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25F_independent_audit")


# ============================================================================
# 1. Protected Invariants & Provenance Verification
# ============================================================================

def test_v1_frozen_strategy_config_hash():
    """Verify frozen V1 configuration snapshot hash is untouched."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 config snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == FROZEN_V1_CONFIG_HASH, f"V1 config hash mismatch: {v1_h}"


def test_canonical_adaniports_dataset_hash():
    """Verify canonical ADANIPORTS 1m dataset SHA-256 hash is identical."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert adani_path.exists(), "Canonical ADANIPORTS file missing"
    h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
    assert h == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS hash mismatch: {h}"


def test_canonical_nifty50_dataset_hash():
    """Verify canonical NIFTY 50 dataset SHA-256 hash is untouched."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    assert nifty_path.exists(), "Canonical NIFTY 50 file missing"
    h = hashlib.sha256(nifty_path.read_bytes()).hexdigest()
    assert h == CANONICAL_NIFTY50_HASH, f"NIFTY 50 hash mismatch: {h}"


def test_paper_trading_ledger_and_universe_registry_preserved():
    """Verify active paper trading ledger and universe registry exist untouched."""
    paper_ledger = Path("data/paper_trading/interactive_trades.json")
    assert paper_ledger.exists(), "Active paper ledger missing"
    registry = Path("data/universe_registry.json")
    assert registry.exists(), "Universe registry missing"


def test_watchlist_test_preserved():
    """Verify tests/test_watchlist.py exists in working tree."""
    wl_path = Path("tests/test_watchlist.py")
    assert wl_path.exists(), "tests/test_watchlist.py must be preserved"


def test_quarantined_2020_dataset_quarantine_enforced():
    """Verify 2020 quarantine directory exists and no 2020 trades exist in reproduction."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"
    cache_path = Path("research/strategy_evolution_2018/phase25E_historical_backtest/phase25E_38stock_raw_trades_cache.json")
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    for item in cache:
        for t in item["raw_trades"]:
            assert str(t["entry_time"]) < "2020-01-01", f"Quarantine breach: trade in 2020 for {item['symbol']}!"
            assert str(t["exit_time"]) < "2020-01-01", f"Quarantine breach: exit in 2020 for {item['symbol']}!"


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_phase25f_deliverables_completeness():
    """Verify all 9 Phase 25F deliverables exist and have non-zero size."""
    expected_files = [
        "phase25F_cost_reconciliation.md",
        "phase25F_shared_capital_audit.md",
        "phase25F_statistical_audit.md",
        "phase25F_membership_integrity_audit.md",
        "phase25F_final_equity_research_verdict.md",
        "phase25F_independent_reproduction.csv",
        "phase25F_discrepancy_register.csv",
        "phase25F_results_manifest.json",
        "run_phase25F_independent_audit.py",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Deliverable {fn} missing"
        assert p.stat().st_size > 0, f"Deliverable {fn} is empty"


# ============================================================================
# 3. Discrepancy Register & Threshold Verification
# ============================================================================

def test_discrepancy_register_zero_failures():
    """Verify all 418 metric checks passed with zero discrepancies exceeding threshold."""
    disc_path = DELIVERABLES_DIR / "phase25F_discrepancy_register.csv"
    df_disc = pd.read_csv(disc_path)
    assert len(df_disc) == 418, f"Expected 418 metric checks, got {len(df_disc)}"
    failed = df_disc[df_disc["status"] != "PASS"]
    assert len(failed) == 0, f"Discrepancy checks failed: {failed.to_dict('records')}"

    # P&L and cost discrepancies must be <= 0.01 INR
    pnl_cost_metrics = ["gross_pnl", "net_pnl", "total_transaction_costs", "training_net_pnl", "validation_net_pnl"]
    pnl_disc = df_disc[df_disc["metric"].isin(pnl_cost_metrics)]
    assert (pnl_disc["absolute_difference"] <= 0.01).all(), "P&L/Cost discrepancy exceeded 0.01 INR"


# ============================================================================
# 4. Classification Distribution Exact Match
# ============================================================================

def test_classification_distribution():
    """Verify classifications match Phase 25E exactly: 0 POSITIVE, 31 NEGATIVE, 4 INCONCLUSIVE, 3 INSUFFICIENT."""
    repro_path = DELIVERABLES_DIR / "phase25F_independent_reproduction.csv"
    df_repro = pd.read_csv(repro_path)
    assert len(df_repro) == 38, f"Expected 38 stocks, got {len(df_repro)}"

    counts = df_repro["classification"].value_counts().to_dict()
    assert counts.get("POSITIVE_RESEARCH_RESULT", 0) == 0, "No stock should be classified POSITIVE"
    assert counts.get("NEGATIVE_RESEARCH_RESULT", 0) == 31, f"Expected 31 NEGATIVE, got {counts.get('NEGATIVE_RESEARCH_RESULT')}"
    assert counts.get("STATISTICALLY_INCONCLUSIVE", 0) == 4, f"Expected 4 INCONCLUSIVE, got {counts.get('STATISTICALLY_INCONCLUSIVE')}"
    assert counts.get("INSUFFICIENT_SAMPLE", 0) == 3, f"Expected 3 INSUFFICIENT, got {counts.get('INSUFFICIENT_SAMPLE')}"

    # Inconclusive set verification
    inconclusive_syms = set(df_repro[df_repro["classification"] == "STATISTICALLY_INCONCLUSIVE"]["symbol"])
    assert inconclusive_syms == {"ADANIPORTS", "EICHERMOT", "IBULHSGFIN", "MARUTI"}

    # Insufficient sample set verification
    insufficient_syms = set(df_repro[df_repro["classification"] == "INSUFFICIENT_SAMPLE"]["symbol"])
    assert insufficient_syms == {"BHEL", "IDEA", "NESTLEIND"}


# ============================================================================
# 5. Cost Reconciliation Mathematical Proof
# ============================================================================

def test_cost_reconciliation_identities():
    """Verify the mathematical turnover scaling and brokerage cap dynamics."""
    manifest_path = DELIVERABLES_DIR / "phase25F_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    proof = m["cost_reconciliation_proof"]
    # 1. Turnover scaling: Portfolio turnover is ~17.388x larger than unit-share turnover
    assert 17.0 <= proof["turnover_multiplier"] <= 18.0, f"Unexpected turnover multiplier: {proof['turnover_multiplier']}"

    # 2. Brokerage cap saturation: 100% of portfolio trades hit the ₹20/leg (₹40 round-trip) cap
    assert proof["portfolio_brokerage_cap_hit_rate_pct"] == 100.0, "All portfolio trades must hit flat ₹40 cap"

    # 3. Portfolio brokerage exact identity: 4,074 trades * ₹40.00 = ₹162,960.00
    port_b = m["reproduced_shared_capital_portfolio"]["model_b_discount_broker"]
    assert port_b["total_brokerage"] == 162960.0, f"Expected brokerage 162960.0, got {port_b['total_brokerage']}"
    assert port_b["accepted_trades_count"] * 40.0 == port_b["total_brokerage"]


# ============================================================================
# 6. Shared-Capital Portfolio Simulation Reproduction
# ============================================================================

def test_shared_capital_portfolio_exact_metrics():
    """Verify portfolio simulation results match bit-for-bit with Phase 25E manifest."""
    manifest_path = DELIVERABLES_DIR / "phase25F_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    port_b = m["reproduced_shared_capital_portfolio"]["model_b_discount_broker"]

    # Model B Core Metrics
    assert port_b["initial_capital"] == 1000000.0
    assert port_b["final_equity"] == 285174.66
    assert port_b["net_portfolio_pnl"] == -714825.34
    assert port_b["portfolio_return_pct"] == -71.48
    assert port_b["max_drawdown_amount"] == 902997.58
    assert port_b["max_drawdown_pct"] == 90.30
    assert port_b["total_signals"] == 18686
    assert port_b["accepted_trades_count"] == 4074
    assert port_b["rejected_trades_count"] == 14612
    assert port_b["rejection_rate_pct"] == 78.20
    assert port_b["total_costs"] == 459066.11
    assert port_b["gross_win_rate_pct"] == 46.78
    assert port_b["net_win_rate_pct"] == 42.54
    assert port_b["flipped_trades"] == 173

    # Accounting Identities
    assert round(port_b["initial_capital"] + port_b["net_portfolio_pnl"], 2) == port_b["final_equity"]
    assert round(port_b["gross_pnl"] - port_b["total_costs"], 2) == port_b["net_portfolio_pnl"]
    assert port_b["accepted_trades_count"] + port_b["rejected_trades_count"] == port_b["total_signals"]


# ============================================================================
# 7. Official Research Verdict
# ============================================================================

def test_official_audit_verdict():
    """Verify official verdict in manifest and verdict document is REPRODUCED_AND_CONFIRMED."""
    manifest_path = DELIVERABLES_DIR / "phase25F_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["verdict"] == "REPRODUCED_AND_CONFIRMED"

    verdict_doc = (DELIVERABLES_DIR / "phase25F_final_equity_research_verdict.md").read_text(encoding="utf-8")
    assert "**`REPRODUCED_AND_CONFIRMED`**" in verdict_doc

"""SignalForge — Phase 25A: NIFTY 50 & NIFTY F&O Research Coverage Test Suite.
=============================================================================
Validates:
1. Pre-flight safety invariants (V1 frozen hash, ADANIPORTS canonical hash, 2020 holdout quarantine).
2. NIFTY 50 authoritative constituent count and schema (exactly 50 stocks).
3. Equity data coverage breakdown (34 with 1m data, 16 missing).
4. Data quality and OHLC/volume mathematical integrity.
5. Derivatives availability audit (0 futures, 0 options, BLOCKED_NO_DATA eligibility).
6. Strict ₹0 budget compliance.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import pytest

FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


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
    if adani_path.exists():
        h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
        assert h == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS hash mismatch: {h}"


def test_quarantined_2020_holdout_status():
    """Verify 2020 holdout partition remains quarantined."""
    manifest_path = Path("data/historical/2020_holdout_manifest.json")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        status = m.get("quarantine_status", "").upper()
        assert status in {"CONTAMINATED", "QUARANTINED", "EXPLORATORY"}, f"Invalid quarantine status: {status}"


# ============================================================================
# 2. Authoritative NIFTY 50 Universe Inventory
# ============================================================================

def test_nifty50_constituent_count():
    """Verify authoritative NIFTY 50 constituent inventory has exactly 50 stocks."""
    inv_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_nifty50_inventory.csv")
    assert inv_path.exists(), "Inventory CSV missing"
    
    with open(inv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 50, f"Expected 50 constituents, found {len(rows)}"
    symbols = [r["symbol"] for r in rows]
    assert len(set(symbols)) == 50, "Duplicate symbols detected in inventory"


def test_nifty50_source_metadata():
    """Verify constituent inventory retains source provenance and effective date."""
    manifest_path = Path("data/universe/sources/manifest.json")
    assert manifest_path.exists(), "Universe source manifest missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    nifty50_meta = data["sources"]["NIFTY_50"]
    assert nifty50_meta["constituent_count"] == 50
    assert nifty50_meta["as_of_date"] == "2026-10-13"
    assert "ind_nifty50list.csv" in nifty50_meta["local_file"]


# ============================================================================
# 3. Equity Data Coverage & Breakdown
# ============================================================================

def test_equity_coverage_matrix_breakdown():
    """Verify equity coverage breakdown: 34 with 1m data, 16 insufficient."""
    cov_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_equity_coverage_matrix.csv")
    assert cov_path.exists(), "Coverage matrix CSV missing"
    
    with open(cov_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 50
    has_data = [r for r in rows if r["has_1m_data"] == "True"]
    no_data = [r for r in rows if r["has_1m_data"] == "False"]
    
    assert len(has_data) == 34, f"Expected 34 stocks with data, found {len(has_data)}"
    assert len(no_data) == 16, f"Expected 16 stocks without data, found {len(no_data)}"


def test_canonical_clean_stocks_identified():
    """Verify exactly 5 canonical clean stocks exist in data/historical/stocks/."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    assert manifest_path.exists(), "Coverage manifest JSON missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    clean_count = m["summary"]["canonical_clean_stocks_count"]
    assert clean_count == 5, f"Expected 5 canonical clean stocks, found {clean_count}"
    
    clean_syms = {s["symbol"] for s in m["constituents_summary"] if s["data_tier"] == "CANONICAL_CLEAN"}
    assert clean_syms == {"ADANIENT", "ADANIPORTS", "ICICIBANK", "INFY", "RELIANCE"}


def test_data_quality_zero_ohlc_violations_clean_tier():
    """Verify clean canonical stocks have 0 OHLC violations and positive prices."""
    cov_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_equity_coverage_matrix.csv")
    with open(cov_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    clean_rows = [r for r in rows if r["data_tier"] == "CANONICAL_CLEAN"]
    for r in clean_rows:
        assert int(r["ohlc_violations"]) == 0, f"OHLC violation in {r['symbol']}"
        assert int(r["negative_volume_rows"]) == 0, f"Negative volume in {r['symbol']}"
        assert int(r["valid_candles"]) >= 370000


# ============================================================================
# 4. Derivatives Coverage Audit (Futures & Options)
# ============================================================================

def test_nifty_futures_zero_data_and_blocked():
    """Verify zero historical futures contracts exist and eligibility is BLOCKED_NO_DATA."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    fut = m["futures_audit"]
    assert fut["contracts_identified"] == 0
    assert fut["historical_ohlcv_available"] is False
    assert fut["testing_eligibility"] == "BLOCKED_NO_DATA"


def test_nifty_options_zero_data_and_blocked():
    """Verify zero options contracts (CE/PE) exist and eligibility is BLOCKED_NO_DATA."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    opt = m["options_audit"]
    assert opt["call_options_ce"]["contracts_identified"] == 0
    assert opt["put_options_pe"]["contracts_identified"] == 0
    assert opt["testing_eligibility"] == "BLOCKED_NO_DATA"


def test_spot_index_not_substituted_for_derivatives():
    """Verify cash spot index is not treated as a tradeable futures or options derivative."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    # Summary should explicitly reflect 0 derivatives despite presence of nifty50_1m_signalforge.csv
    assert m["summary"]["futures_contracts_count"] == 0
    assert m["summary"]["options_contracts_count"] == 0


# ============================================================================
# 5. Budget Compliance & Causal Boundaries
# ============================================================================

def test_zero_cost_budget_compliance():
    """Verify ₹0 budget adherence and zero expenditure."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    assert m["budget_expenditure_inr"] == 0.00


def test_no_backtesting_claimed_in_phase25a():
    """Verify that Phase 25A is strictly an audit phase and executes no backtests."""
    manifest_path = Path("research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    assert m["audit_verdict"] == "EQUITY_PARTIAL_FNO_BLOCKED"

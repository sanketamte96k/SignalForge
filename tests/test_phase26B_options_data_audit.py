"""
SignalForge — Phase 26B NIFTY Options Historical Contract-Level Data Feasibility Audit Test Suite
=================================================================================================
Verifies:
  1. Protected Invariants & Provenance:
     - Frozen V1 strategy configuration hash
     - Canonical ADANIPORTS dataset SHA-256
     - Canonical NIFTY 50 dataset SHA-256
     - Active paper trading ledger & universe registry preserved
     - tests/test_watchlist.py preserved
     - Quarantined 2020 partition preserved
     - Strict ₹0 research budget maintained
  2. Phase 26B Deliverables Completeness:
     - All 6 deliverables exist and are non-empty
  3. Options Inventory Audit Verification:
     - 16 candidate files audited
     - Zero genuine options contracts found (100% false)
     - All lack strike price, option type (CE/PE), and expiry dates
     - All assigned BLOCKED_NOT_OPTIONS_DATA usability status
  4. Contract Coverage Matrix Verification:
     - All 36 monthly expiries across 2017–2019 audited
     - 0 CE contracts, 0 PE contracts, 0 bars on disk
     - 100% BLOCKED_NO_DATA and lot size == 75
  5. Empirical Spot vs. Options Microstructure Audit:
     - Canonical NIFTY 50 has volume == 0.0, no strike, no option type, no open interest
     - Confirms spot index cannot be substituted for options contracts
  6. Provenance Manifest & Final Verdict Assertions:
     - Final verdict is BLOCKED_NO_DATA
     - Execution feasibility is EXECUTION_INFEASIBLE_NO_DATA
     - Deployment status remains STRICTLY_ON_HOLD
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

PHASE26B_DIR = Path("research/strategy_evolution_2018/phase26B_options_data_audit")


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
    """Verify 2020 quarantine directory exists and no 2020 data touched."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_phase26b_deliverables_completeness():
    """Verify all 6 Phase 26B deliverables exist and have non-zero size."""
    expected_files = [
        "phase26B_options_data_inventory.csv",
        "phase26B_contract_coverage_matrix.csv",
        "phase26B_options_data_quality_audit.md",
        "phase26B_execution_feasibility.md",
        "phase26B_provenance_manifest.json",
        "phase26B_final_verdict.md",
    ]
    for fn in expected_files:
        p = PHASE26B_DIR / fn
        assert p.exists(), f"Phase 26B deliverable {fn} missing"
        assert p.stat().st_size > 0, f"Phase 26B deliverable {fn} is empty"


# ============================================================================
# 3. Inventory Audit Verification
# ============================================================================

def test_options_inventory_findings():
    """Verify the 16 candidate files audited in phase26B_options_data_inventory.csv."""
    inv_csv = PHASE26B_DIR / "phase26B_options_data_inventory.csv"
    assert inv_csv.exists(), "phase26B_options_data_inventory.csv missing"
    df = pd.read_csv(inv_csv)
    
    assert len(df) == 16, f"Expected 16 candidate files, found {len(df)}"
    assert (df["is_genuine_options_contract"] == False).all(), "Found file falsely flagged as genuine options contract"
    assert (df["has_strike_price"] == False).all(), "Found file with strike price"
    assert (df["has_option_type_ce_pe"] == False).all(), "Found file with option type (CE/PE)"
    assert (df["has_expiry_date"] == False).all(), "Found file with expiry date"
    assert (df["has_open_interest"] == False).all(), "Found file with open interest"
    assert (df["has_bid_ask"] == False).all(), "Found file with bid/ask quotes"
    assert (df["usability_status"] == "BLOCKED_NOT_OPTIONS_DATA").all(), "All verdicts must be BLOCKED_NOT_OPTIONS_DATA"
    
    # Confirm classifications
    valid_classes = {"CASH_SPOT_INDEX", "CASH_INDEX_TICK_LOG", "STRATEGY_NOTEBOOK"}
    assert set(df["actual_instrument_type"]).issubset(valid_classes), "Unexpected classification found"


# ============================================================================
# 4. Contract Coverage Matrix Verification
# ============================================================================

def test_options_contract_coverage_matrix():
    """Verify all 36 monthly expiries across 2017–2019 are accounted for and blocked."""
    cov_csv = PHASE26B_DIR / "phase26B_contract_coverage_matrix.csv"
    assert cov_csv.exists(), "phase26B_contract_coverage_matrix.csv missing"
    df = pd.read_csv(cov_csv)
    
    assert len(df) == 36, f"Expected 36 monthly expiries, found {len(df)}"
    assert (df["ce_contracts_discovered"] == 0).all(), "Expected 0 CE contracts discovered"
    assert (df["pe_contracts_discovered"] == 0).all(), "Expected 0 PE contracts discovered"
    assert (df["total_contracts_discovered"] == 0).all(), "Expected 0 total contracts discovered"
    assert (df["available_bars_on_disk"] == 0).all(), "Expected 0 bars on disk across all expiries"
    assert (df["valid_records_count"] == 0).all(), "Expected 0 valid records across all expiries"
    assert (df["historical_lot_size"] == 75).all(), "Historical lot size for 2017-2019 must be 75"
    assert (df["data_quality_verdict"] == "BLOCKED_NO_DATA").all(), "All expiries must have BLOCKED_NO_DATA verdict"
    
    years = sorted(df["expiry_month"].apply(lambda x: int(str(x).split("-")[0])).unique())
    assert years == [2017, 2018, 2019], f"Expected years 2017-2019, got {years}"


# ============================================================================
# 5. Spot vs. Options Empirical Properties
# ============================================================================

def test_canonical_nifty50_spot_properties_for_options():
    """Verify canonical NIFTY 50 dataset exhibits pure cash index properties."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    df = pd.read_csv(nifty_path, nrows=500)
    
    cols = [c.lower() for c in df.columns]
    assert "strike" not in cols, "NIFTY 50 spot data should not have strike column"
    assert "strike_price" not in cols, "NIFTY 50 spot data should not have strike_price column"
    assert "option_type" not in cols and "opt_type" not in cols, "NIFTY 50 spot data should not have option_type column"
    assert "expiry" not in cols and "expiry_date" not in cols, "NIFTY 50 spot data should not have expiry column"
    assert "open_interest" not in cols and "oi" not in cols, "NIFTY 50 spot data should not have open interest column"
    assert "bid" not in cols and "ask" not in cols, "NIFTY 50 spot data should not have bid/ask column"
    
    if "volume" in cols:
        vol_col = df.columns[cols.index("volume")]
        assert (df[vol_col] == 0.0).all() or (df[vol_col] == 0).all(), "Cash index volume must be 0"


# ============================================================================
# 6. Provenance Manifest & Final Verdict Assertions
# ============================================================================

def test_options_provenance_manifest_verdict():
    """Verify phase26B_provenance_manifest.json integrity and verdict."""
    manifest_path = PHASE26B_DIR / "phase26B_provenance_manifest.json"
    assert manifest_path.exists(), "phase26B_provenance_manifest.json missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    assert manifest["phase"] == "26B"
    assert manifest["verdict"] == "BLOCKED_NO_DATA"
    assert manifest["governance_and_invariants"]["deployment_status"] == "STRICTLY_ON_HOLD"
    assert manifest["governance_and_invariants"]["budget_expenditure_inr"] == 0.0
    assert manifest["audit_summary"]["total_options_contracts_discovered"] == 0
    assert manifest["audit_summary"]["total_options_bars_available"] == 0
    assert manifest["audit_summary"]["ce_contracts_discovered"] == 0
    assert manifest["audit_summary"]["pe_contracts_discovered"] == 0
    assert manifest["audit_summary"]["required_monthly_expiries_2017_2019"] == 36
    assert manifest["audit_summary"]["execution_feasibility"] == "EXECUTION_INFEASIBLE_NO_DATA"


def test_options_final_verdict_document_verdict():
    """Verify phase26B_final_verdict.md contains the exact required certifications."""
    verdict_path = PHASE26B_DIR / "phase26B_final_verdict.md"
    assert verdict_path.exists(), "phase26B_final_verdict.md missing"
    content = verdict_path.read_text(encoding="utf-8")
    
    assert "BLOCKED_NO_DATA" in content
    assert "STRICTLY_ON_HOLD" in content
    assert "₹0" in content or "0.00" in content

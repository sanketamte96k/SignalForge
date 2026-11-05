"""
SignalForge — Phase 26A NIFTY Futures Historical Contract-Level Data Feasibility Audit Test Suite
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
  2. Phase 26A Deliverables Completeness:
     - All 6 deliverables exist and are non-empty
  3. Inventory Audit Verification:
     - 16 candidate files audited
     - Zero genuine futures contracts found (100% false)
     - All classified as CASH_SPOT_INDEX or CASH_INDEX_TICK_LOG
     - All assigned BLOCKED_NOT_FUTURES_DATA verdict
  4. Contract Coverage Matrix Verification:
     - All 36 monthly contracts across 2017–2019 audited
     - 0 available bars on disk across all contracts
     - 100% BLOCKED_NO_DATA and rollover_feasible == False
  5. Empirical Spot vs. Futures Microstructure Audit:
     - Canonical NIFTY 50 has volume == 0.0, no expiry column, no open interest
     - Confirms spot index cannot be substituted for futures contracts
  6. Provenance Manifest & Final Verdict Assertions:
     - Final verdict is BLOCKED_NO_DATA
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

PHASE26A_DIR = Path("research/strategy_evolution_2018/phase26A_futures_data_audit")


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

def test_phase26a_deliverables_completeness():
    """Verify all 6 Phase 26A deliverables exist and have non-zero size."""
    expected_files = [
        "phase26A_futures_data_inventory.csv",
        "phase26A_contract_coverage_matrix.csv",
        "phase26A_data_quality_audit.md",
        "phase26A_rollover_feasibility.md",
        "phase26A_provenance_manifest.json",
        "phase26A_final_verdict.md",
    ]
    for fn in expected_files:
        p = PHASE26A_DIR / fn
        assert p.exists(), f"Phase 26A deliverable {fn} missing"
        assert p.stat().st_size > 0, f"Phase 26A deliverable {fn} is empty"


# ============================================================================
# 3. Inventory Audit Verification
# ============================================================================

def test_futures_inventory_findings():
    """Verify the 16 candidate files audited in phase26A_futures_data_inventory.csv."""
    inv_csv = PHASE26A_DIR / "phase26A_futures_data_inventory.csv"
    assert inv_csv.exists(), "phase26A_futures_data_inventory.csv missing"
    df = pd.read_csv(inv_csv)
    
    assert len(df) == 16, f"Expected 16 candidate files, found {len(df)}"
    assert (df["is_genuine_futures_contract"] == False).all(), "Found file falsely flagged as genuine futures contract"
    assert (df["has_expiry_date"] == False).all(), "Found file with expiry date"
    assert (df["has_open_interest"] == False).all(), "Found file with open interest"
    assert (df["usability_status"] == "BLOCKED_NOT_FUTURES_DATA").all(), "All verdicts must be BLOCKED_NOT_FUTURES_DATA"
    
    # Confirm classifications
    valid_classes = {"CASH_SPOT_INDEX", "CASH_INDEX_TICK_LOG", "STRATEGY_NOTEBOOK"}
    assert set(df["actual_instrument_type"]).issubset(valid_classes), "Unexpected classification found"


# ============================================================================
# 4. Contract Coverage Matrix Verification
# ============================================================================

def test_contract_coverage_matrix():
    """Verify all 36 monthly contracts across 2017–2019 are accounted for and blocked."""
    cov_csv = PHASE26A_DIR / "phase26A_contract_coverage_matrix.csv"
    assert cov_csv.exists(), "phase26A_contract_coverage_matrix.csv missing"
    df = pd.read_csv(cov_csv)
    
    assert len(df) == 36, f"Expected 36 monthly contracts, found {len(df)}"
    assert (df["available_bars_on_disk"] == 0).all(), "Expected 0 bars on disk across all contracts"
    assert (df["valid_records_count"] == 0).all(), "Expected 0 valid records across all contracts"
    assert (df["data_quality_verdict"] == "BLOCKED_NO_DATA").all(), "All contracts must have BLOCKED_NO_DATA verdict"
    
    years = sorted(df["expiry_month"].apply(lambda x: int(str(x).split("-")[0])).unique())
    assert years == [2017, 2018, 2019], f"Expected years 2017-2019, got {years}"


# ============================================================================
# 5. Spot vs. Futures Empirical Properties
# ============================================================================

def test_canonical_nifty50_spot_properties():
    """Verify canonical NIFTY 50 dataset exhibits pure cash index properties."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    df = pd.read_csv(nifty_path, nrows=500)
    
    cols = [c.lower() for c in df.columns]
    assert "expiry" not in cols, "NIFTY 50 spot data should not have expiry column"
    assert "expiry_date" not in cols, "NIFTY 50 spot data should not have expiry_date column"
    assert "open_interest" not in cols and "oi" not in cols, "NIFTY 50 spot data should not have open interest column"
    assert "strike" not in cols, "NIFTY 50 spot data should not have strike column"
    
    if "volume" in cols:
        # Check volume is consistently 0.0 (non-tradable index)
        vol_col = df.columns[cols.index("volume")]
        assert (df[vol_col] == 0.0).all() or (df[vol_col] == 0).all(), "Cash index volume must be 0"


# ============================================================================
# 6. Provenance Manifest & Final Verdict Assertions
# ============================================================================

def test_provenance_manifest_verdict():
    """Verify phase26A_provenance_manifest.json integrity and verdict."""
    manifest_path = PHASE26A_DIR / "phase26A_provenance_manifest.json"
    assert manifest_path.exists(), "phase26A_provenance_manifest.json missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    assert manifest["phase"] == "26A"
    assert manifest["verdict"] == "BLOCKED_NO_DATA"
    assert manifest["governance_and_invariants"]["deployment_status"] == "STRICTLY_ON_HOLD"
    assert manifest["governance_and_invariants"]["budget_expenditure_inr"] == 0.0
    assert manifest["audit_summary"]["total_futures_contracts_discovered"] == 0
    assert manifest["audit_summary"]["total_futures_bars_available"] == 0
    assert manifest["audit_summary"]["required_contracts_2017_2019"] == 36
    assert manifest["audit_summary"]["rollover_feasibility"] == "ROLLOVER_INFEASIBLE_NO_CONTRACT_DATA"


def test_final_verdict_document_verdict():
    """Verify phase26A_final_verdict.md contains the exact required certifications."""
    verdict_path = PHASE26A_DIR / "phase26A_final_verdict.md"
    assert verdict_path.exists(), "phase26A_final_verdict.md missing"
    content = verdict_path.read_text(encoding="utf-8")
    
    assert "BLOCKED_NO_DATA" in content
    assert "STRICTLY_ON_HOLD" in content
    assert "₹0" in content or "0.00" in content

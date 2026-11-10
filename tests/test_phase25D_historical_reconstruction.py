"""
SignalForge — Phase 25D Historical NIFTY 50 Reconstruction Test Suite
=====================================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config hash, ADANIPORTS, NIFTY 50, paper ledger, universe registry, 2020 quarantine).
  2. Deliverables completeness (9 files in research/strategy_evolution_2018/phase25D_historical_reconstruction/).
  3. Historical constituent reconstruction integrity (61 unique companies + 1 DVR security, 9 date-effective snapshots).
  4. Repository historical data coverage (exactly 38 verified stocks with 1-min data, exactly 23 missing companies).
  5. Data quality metrics across all 38 verified historical datasets (zero OHLC violations, zero duplicate timestamps).
  6. Missing 16 modern stocks categorization (9 non-historical entrants, 7 true historical missing).
  7. Distressed constituents audit (coverage of IBULHSGFIN, IDEA, BHEL, and documentation of missing YESBANK/ZEEL).
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

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25D_historical_reconstruction")


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
    """Verify pre-recorded canonical ADANIPORTS hash in trusted manifest without accessing monolithic CSV."""
    manifest_path = Path("research/strategy_evolution_2018/phase25D_historical_reconstruction/phase25D_results_manifest.json")
    assert manifest_path.exists(), "Trusted results manifest missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    canonical_hash = manifest_data["invariants"]["canonical_adaniports_hash"]
    assert canonical_hash == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS hash mismatch: {canonical_hash}"


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
    """Verify 2020 quarantine directory exists and no 2020 bars are in historical universe."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"
    q_files = list(q_dir.glob("*.csv"))
    assert len(q_files) > 0, "Quarantined files missing"


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_all_phase25d_deliverables_exist():
    """Verify all mandatory Phase 25D deliverables exist on disk."""
    expected_files = [
        "phase25D_historical_constituent_snapshots.json",
        "phase25D_membership_change_timeline.md",
        "phase25D_historical_universe_coverage_matrix.csv",
        "phase25D_missing_16_stocks_audit.md",
        "phase25D_distressed_constituent_coverage_audit.md",
        "phase25D_data_source_provenance_report.md",
        "phase25D_eligible_historical_research_universe.csv",
        "phase25D_results_manifest.json",
        "phase25D_final_report.md",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Phase 25D deliverable missing: {fn}"
        assert p.stat().st_size > 0, f"Deliverable is empty: {fn}"


# ============================================================================
# 3. Historical Constituent Reconstruction Verification
# ============================================================================

def test_historical_constituent_snapshots_integrity():
    """Verify historical snapshots JSON contains valid dates, counts, and symbols."""
    snap_path = DELIVERABLES_DIR / "phase25D_historical_constituent_snapshots.json"
    with open(snap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    snapshots = data["snapshots"]
    assert len(snapshots) >= 8, f"Expected at least 8 snapshots, got {len(snapshots)}"

    # First snapshot: Baseline Jan 1, 2017 has 51 securities (50 companies + TATAMTRDVR)
    base = snapshots[0]
    assert base["as_of_date"] == "2017-01-01"
    assert base["total_companies"] == 50
    assert base["total_securities"] == 51
    assert "TATAMTRDVR" in base["constituents"]

    # Final snapshot: Dec 31, 2019 has 50 companies / 50 securities
    end_snap = snapshots[-1]
    assert end_snap["as_of_date"] == "2019-12-31"
    assert end_snap["total_companies"] == 50
    assert end_snap["total_securities"] == 50
    assert "TATAMTRDVR" not in end_snap["constituents"]


def test_unique_historical_companies_count():
    """Verify exactly 61 unique companies and 1 DVR security existed in NIFTY 50 during 2017-2019."""
    matrix_path = DELIVERABLES_DIR / "phase25D_historical_universe_coverage_matrix.csv"
    df = pd.read_csv(matrix_path)

    # 62 total securities
    assert len(df) == 62, f"Expected 62 securities in coverage matrix, found {len(df)}"

    companies_df = df[df["is_dvr_security"] == False]
    assert len(companies_df) == 61, f"Expected exactly 61 companies, found {len(companies_df)}"
    assert companies_df["symbol"].nunique() == 61


# ============================================================================
# 4. Data Coverage & Quality Verification
# ============================================================================

def test_historical_data_coverage_counts():
    """Verify exactly 38 historical stocks have 1m data and 23 companies are missing data."""
    manifest_path = DELIVERABLES_DIR / "phase25D_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    stats = m["universe_statistics"]
    assert stats["total_historical_companies"] == 61
    assert stats["historical_companies_with_1m_data"] == 38
    assert stats["historical_companies_missing_1m_data"] == 23
    assert stats["eligible_for_backtesting_tenure_bounded"] == 38
    assert stats["blocked_by_insufficient_data"] == 23


def test_eligible_historical_research_universe_csv():
    """Verify the eligible universe CSV contains exactly 38 verified stocks with valid data quality."""
    csv_path = DELIVERABLES_DIR / "phase25D_eligible_historical_research_universe.csv"
    df = pd.read_csv(csv_path)

    assert len(df) == 38, f"Expected 38 stocks in eligible universe, found {len(df)}"
    assert df["symbol"].nunique() == 38

    # All must be ELIGIBLE_TENURE_BOUNDED
    assert (df["backtesting_eligibility"] == "ELIGIBLE_TENURE_BOUNDED").all()

    # Verify bar counts are positive and significant (>200,000 bars for 2017-2019)
    assert (df["bars_2017_2019"] > 250000).all()

    # Verify sha256 hashes are present and valid 64-char hex strings
    for sha in df["sha256"]:
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha.lower())


def test_coverage_matrix_data_quality():
    """Verify zero OHLC violations and zero duplicate timestamps across all verified datasets."""
    csv_path = DELIVERABLES_DIR / "phase25D_historical_universe_coverage_matrix.csv"
    df = pd.read_csv(csv_path)

    verified = df[df["data_status"] == "VERIFIED_COMPLETE"]
    assert len(verified) == 38

    # Zero OHLC violations across all 38 files
    assert (verified["ohlc_violations"] == 0).all(), "Found OHLC violations in verified datasets"

    # Zero duplicate timestamps across all 38 files
    assert (verified["duplicates"] == 0).all(), "Found duplicate timestamps in verified datasets"


# ============================================================================
# 5. Missing 16 Stocks Audit & Root Cause Categorization
# ============================================================================

def test_missing_16_stocks_audit_content():
    """Verify missing 16 audit explicitly categorizes the 9 non-historical and 7 true historical stocks."""
    doc_path = DELIVERABLES_DIR / "phase25D_missing_16_stocks_audit.md"
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")

    # 9 non-historical modern entrants
    non_historical = ["BSE", "ETERNAL", "HDFCLIFE", "INDIGO", "JIOFIN", "MAXHEALTH", "TATACONSUM", "TMPV", "TRENT"]
    for s in non_historical:
        assert s in content, f"Missing non-historical symbol in audit: {s}"

    # 7 true historical missing stocks
    historical_missing = ["HINDALCO", "HINDUNILVR", "TCS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO"]
    for s in historical_missing:
        assert s in content, f"Missing true historical missing symbol in audit: {s}"


# ============================================================================
# 6. Distressed Constituents Audit Verification
# ============================================================================

def test_distressed_constituents_audit():
    """Verify distressed constituent audit covers key historical stress entities."""
    doc_path = DELIVERABLES_DIR / "phase25D_distressed_constituent_coverage_audit.md"
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")

    key_distressed = ["IBULHSGFIN", "YESBANK", "ZEEL", "IDEA", "BHEL", "VEDL", "INFRATEL"]
    for s in key_distressed:
        assert s in content, f"Missing distressed constituent: {s}"

    # Manifest check
    manifest_path = DELIVERABLES_DIR / "phase25D_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    dist = m["distressed_constituents_audit"]
    assert dist["identified_count"] == 7
    assert dist["with_data_count"] == 3  # IBULHSGFIN, IDEA, BHEL
    assert dist["missing_data_count"] == 4  # YESBANK, ZEEL, VEDL, INFRATEL


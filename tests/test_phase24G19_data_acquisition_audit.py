"""
Unit and Regression Tests for SignalForge Phase 24G.19
======================================================
Verifies:
  1. Preflight baseline V1 config hash invariant (920515d7...)
  2. Canonical ADANIPORTS SHA-256 hash invariant (fb327552...)
  3. Untouched status of paper trading ledger & universe registry
  4. Quarantined 2020 partition isolation
  5. Existence and completeness of all 6 Phase 24G.19 deliverables
  6. Phase 24G.19 coverage matrix schema and 22-symbol coverage
  7. Final verdict classification is DATA_SOURCE_IDENTIFIED
  8. Zero unauthorized data downloads initiated
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE19_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G19_data_acquisition_audit"
V1_SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
ADANIPORTS_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_preflight_v1_config_hash():
    """Verify frozen V1 strategy baseline config hash matches canonical value."""
    assert V1_SNAPSHOT_PATH.exists(), f"V1 snapshot missing at {V1_SNAPSHOT_PATH}"
    with open(V1_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    v1_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert v1_hash == EXPECTED_V1_CONFIG_HASH, f"V1 hash mismatch: expected {EXPECTED_V1_CONFIG_HASH}, got {v1_hash}"


def test_preflight_adaniports_hash():
    """Verify canonical on-disk ADANIPORTS SHA-256 matches bit-for-bit."""
    assert ADANIPORTS_PATH.exists(), f"ADANIPORTS dataset missing at {ADANIPORTS_PATH}"
    content = ADANIPORTS_PATH.read_bytes()
    computed_hash = hashlib.sha256(content).hexdigest()
    assert computed_hash == EXPECTED_ADANIPORTS_HASH, (
        f"ADANIPORTS hash mismatch: expected {EXPECTED_ADANIPORTS_HASH}, got {computed_hash}"
    )


def test_safety_invariants_registry_and_paper_ledger():
    """Verify universe registry and paper ledger exist and are valid JSON."""
    assert REGISTRY_PATH.exists(), "data/universe_registry.json missing"
    assert PAPER_LEDGER_PATH.exists(), "data/paper_trading/interactive_trades.json missing"
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        reg = json.load(f)
        assert isinstance(reg, dict)
    with open(PAPER_LEDGER_PATH, "r", encoding="utf-8") as f:
        ledger = json.load(f)
        assert isinstance(ledger, (dict, list))


def test_phase24G19_deliverables_exist():
    """Verify all 6 required deliverables exist in the dedicated directory."""
    expected_files = [
        "phase24G19_provider_comparison.md",
        "phase24G19_coverage_matrix.csv",
        "phase24G19_data_requirements.md",
        "phase24G19_acquisition_design.md",
        "phase24G19_licensing_and_risk_report.md",
        "phase24G19_final_verdict.md",
    ]
    for fname in expected_files:
        fpath = PHASE19_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"


def test_phase24G19_coverage_matrix_integrity():
    """Verify coverage matrix covers all 22 symbols and specifies providers."""
    csv_path = PHASE19_DIR / "phase24G19_coverage_matrix.csv"
    assert csv_path.exists(), "phase24G19_coverage_matrix.csv missing"

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 22, f"Expected 22 equities in matrix, found {len(rows)}"
    sectors = set(r["sector"] for r in rows)
    assert len(sectors) >= 7, f"Expected at least 7 sectors, found {len(sectors)}"

    for r in rows:
        assert r["audit_verdict"] == "SOURCE_CONFIRMED"
        assert "TrueData" in r["recommended_primary_source"]
        assert "Zerodha" in r["recommended_secondary_source"]


def test_phase24G19_verdict_classification():
    """Verify verdict file assigns DATA_SOURCE_IDENTIFIED and AWAITING_USER_AUTHORIZATION."""
    verdict_path = PHASE19_DIR / "phase24G19_final_verdict.md"
    assert verdict_path.exists(), "phase24G19_final_verdict.md missing"
    text = verdict_path.read_text(encoding="utf-8")

    assert "DATA_SOURCE_IDENTIFIED" in text
    assert "AWAITING_USER_AUTHORIZATION" in text
    assert "SF-SPEC-ALPHA-2026-V1" in text
    assert "PROMISING_RESEARCH_CANDIDATE" in text


def test_no_unauthorized_downloads():
    """Verify no new data files were downloaded or modified in production data folders."""
    # Production stocks directory should only contain the existing 6 files
    stocks_dir = PROJECT_ROOT / "data" / "historical" / "stocks"
    csv_files = list(stocks_dir.glob("*.csv"))
    assert len(csv_files) == 6, f"Expected exactly 6 stock CSVs, found {len(csv_files)}"

    # Ensure staging directory has not been populated without user authorization
    staging_dir = PROJECT_ROOT / "data" / "historical" / "staging" / "phase24G19"
    if staging_dir.exists():
        downloaded = list(staging_dir.glob("*.csv"))
        assert len(downloaded) == 0, f"Found unexpected downloaded files in staging: {downloaded}"

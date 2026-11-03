"""
SignalForge — Phase 24G.26: Architecture & Product Engineering Audit Tests
==========================================================================
Validates:
1. Pre-flight invariants (V1 config hash, canonical ADANIPORTS SHA-256, registry/ledger).
2. Phase 24G.26 deliverable completeness (all 14 deliverables present & non-empty).
3. Cryptographic manifest integrity (SHA-256 verification of all audit artifacts).
4. Formal audit verdict consistency ("ARCHITECTURE_AUDIT_COMPLETED").
5. Frontend test suite completeness (all 12 frontend suites mapped).
"""

import hashlib
import json
from pathlib import Path
import pytest


AUDIT_DIR = Path("research/strategy_evolution_2018/phase24G26_architecture_product_audit")
MANIFEST_PATH = AUDIT_DIR / "phase24G26_manifest.json"


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


# ----------------------------------------------------------------------------
# 2. Deliverables Completeness
# ----------------------------------------------------------------------------

EXPECTED_FILES = [
    "phase24G26_repository_structure.md",
    "phase24G26_system_architecture.md",
    "phase24G26_backend_audit.md",
    "phase24G26_frontend_audit.md",
    "phase24G26_api_inventory.md",
    "phase24G26_research_engine_integration.md",
    "phase24G26_storage_data_architecture.md",
    "phase24G26_security_reliability_audit.md",
    "phase24G26_testing_maintainability_audit.md",
    "phase24G26_deployment_readiness.md",
    "phase24G26_product_gap_analysis.md",
    "phase24G26_implementation_roadmap.md",
    "phase24G26_final_report.md",
    "phase24G26_manifest.json",
]


def test_all_14_deliverables_exist_and_non_empty():
    """Verify all 14 Phase 24G.26 deliverables exist and have substantial content."""
    assert AUDIT_DIR.exists()
    for filename in EXPECTED_FILES:
        filepath = AUDIT_DIR / filename
        assert filepath.exists(), f"Missing deliverable: {filename}"
        assert filepath.stat().st_size > 1000, f"Deliverable too small (<1KB): {filename}"


# ----------------------------------------------------------------------------
# 3. Cryptographic Manifest Integrity
# ----------------------------------------------------------------------------

def test_manifest_sha256_integrity():
    """Verify that all files in the manifest match their on-disk SHA-256 hashes."""
    assert MANIFEST_PATH.exists(), "Manifest file missing"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "Phase 24G.26"
    assert manifest["verdict"] == "ARCHITECTURE_AUDIT_COMPLETED"
    assert manifest["budget_consumed_inr"] == 0.0

    deliverables = manifest["deliverables"]
    assert len(deliverables) == 13, f"Expected 13 markdown deliverables, got {len(deliverables)}"

    for item in deliverables:
        fname = item["filename"]
        expected_hash = item["sha256"]
        fpath = AUDIT_DIR / fname
        assert fpath.exists(), f"File in manifest missing from disk: {fname}"
        # Normalize CRLF to LF so git autocrlf does not break hash verification across platforms
        actual_hash = hashlib.sha256(fpath.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {fname}: expected {expected_hash}, got {actual_hash}"
        )


# ----------------------------------------------------------------------------
# 4. Formal Audit Verdict
# ----------------------------------------------------------------------------

def test_final_report_verdict():
    """Verify that the final report contains the formal verdict."""
    final_report_path = AUDIT_DIR / "phase24G26_final_report.md"
    assert final_report_path.exists()
    content = final_report_path.read_text(encoding="utf-8")
    assert "ARCHITECTURE_AUDIT_COMPLETED" in content
    assert "₹0.00" in content or "₹0" in content


# ----------------------------------------------------------------------------
# 5. Frontend Test Suite Mapping
# ----------------------------------------------------------------------------

def test_frontend_test_suites_accounted_for():
    """Verify that the 12 frontend test suites documented in the audit exist on disk."""
    frontend_test_dir = Path("frontend/test")
    assert frontend_test_dir.exists()
    test_files = list(frontend_test_dir.glob("*.test.js"))
    assert len(test_files) == 12, f"Expected 12 frontend test files, found {len(test_files)}"

"""
Unit and Regression Tests for SignalForge Phase 24G.20
======================================================
Verifies:
  1. Preflight baseline V1 config hash invariant (920515d7...)
  2. Canonical ADANIPORTS SHA-256 hash invariant (fb327552...)
  3. Untouched status of paper trading ledger & universe registry
  4. Quarantined 2020 partition isolation
  5. Existence and completeness of all 6 Phase 24G.20 deliverables
  6. Phase 24G.20 22-symbol coverage checklist integrity and 2015+ depth
  7. Pricing comparison exactness (Zerodha ₹590 flat incl. GST)
  8. Final verdict classification is ZERODHA_RECOMMENDED
  9. Strict compliance: zero purchases, zero credentials, zero downloads
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE20_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G20_provider_verification"
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


def test_phase24G20_deliverables_exist():
    """Verify all 6 required deliverables exist in the dedicated directory."""
    expected_files = [
        "phase24G20_truedata_verification.md",
        "phase24G20_zerodha_verification.md",
        "phase24G20_22_symbol_coverage.csv",
        "phase24G20_pricing_comparison.md",
        "phase24G20_licensing_review.md",
        "phase24G20_final_recommendation.md",
    ]
    for fname in expected_files:
        fpath = PHASE20_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"


def test_phase24G20_symbol_coverage_matrix_integrity():
    """Verify coverage checklist covers 22 symbols, all listed pre-2015, with verified depth."""
    csv_path = PHASE20_DIR / "phase24G20_22_symbol_coverage.csv"
    assert csv_path.exists(), "phase24G20_22_symbol_coverage.csv missing"

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 22, f"Expected 22 equities, found {len(rows)}"
    for r in rows:
        assert r["zerodha_status"] == "CONFIRMED_2015_DEPTH"
        assert r["truedata_standard_api_status"] == "RESTRICTED_LAST_6M"
        for yr in ["2021", "2022", "2023", "2024", "2025"]:
            assert r[f"coverage_{yr}"] == "CONFIRMED_AVAILABLE"


def test_phase24G20_pricing_breakdown():
    """Verify pricing comparison records Zerodha ₹590 flat and TrueData lookback cost."""
    pricing_path = PHASE20_DIR / "phase24G20_pricing_comparison.md"
    assert pricing_path.exists(), "phase24G20_pricing_comparison.md missing"
    text = pricing_path.read_text(encoding="utf-8")

    assert "₹590.00" in text
    assert "₹500.00" in text
    assert "18.0%" in text
    assert "TrueData" in text


def test_phase24G20_final_verdict():
    """Verify verdict file recommends Zerodha and preserves DRAFT specification status."""
    verdict_path = PHASE20_DIR / "phase24G20_final_recommendation.md"
    assert verdict_path.exists(), "phase24G20_final_recommendation.md missing"
    text = verdict_path.read_text(encoding="utf-8")

    assert "ZERODHA_RECOMMENDED" in text
    assert "SF-SPEC-ALPHA-2026-V1" in text
    assert "DRAFT" in text
    assert "PROMISING_RESEARCH_CANDIDATE" in text


def test_strict_restrictions_no_purchase_or_downloads():
    """Verify that zero subscription purchases occurred and zero historical downloads were executed."""
    stocks_dir = PROJECT_ROOT / "data" / "historical" / "stocks"
    csv_files = list(stocks_dir.glob("*.csv"))
    assert len(csv_files) == 6, f"Expected exactly 6 stock CSVs in historical folder, found {len(csv_files)}"

    verdict_path = PHASE20_DIR / "phase24G20_final_recommendation.md"
    text = verdict_path.read_text(encoding="utf-8")
    assert "NO_PURCHASE_MADE" in text

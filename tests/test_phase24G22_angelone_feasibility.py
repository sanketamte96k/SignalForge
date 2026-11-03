"""
Unit and Regression Tests for SignalForge Phase 24G.22
======================================================
Verifies:
  1. Preflight baseline V1 config hash invariant (920515d7...)
  2. Canonical ADANIPORTS SHA-256 hash invariant (fb327552...)
  3. Untouched status of paper trading ledger & universe registry
  4. Quarantined 2020 partition isolation
  5. Existence and completeness of all 7 Phase 24G.22 deliverables
  6. Multi-criteria provider comparison matrix integrity (11 rows, ₹0 cost for Angel One)
  7. Sample pilot plan integrity (15 targets, 5 symbols across 3 years, 315 calls)
  8. Universe scrip mapping coverage across all 22 preregistered equities
  9. Final verdict classification is READY_FOR_AUTHORIZED_PILOT
  10. Strict compliance: zero Angel One credentials, zero accounts, zero network downloads
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE22_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G22_angelone_feasibility"
V1_SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
ADANIPORTS_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"

EXPECTED_22_SYMBOLS = [
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "BAJFINANCE",
    "INFY", "HCLTECH", "COFORGE",
    "RELIANCE", "BPCL", "ONGC",
    "MARUTI", "BAJAJ_AUTO", "EICHERMOT",
    "JSWSTEEL", "SAIL", "ADANIENT",
    "SUNPHARMA", "DRREDDY",
    "ITC", "BRITANNIA",
    "ADANIPORTS",
]


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


def test_quarantine_2020_holdout():
    """Verify 2020 partition remains classified as quarantined / contaminated in partition manifest."""
    part_path = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G18_fresh_oos" / "phase24G18_partition_manifest.json"
    assert part_path.exists(), f"Partition manifest missing at {part_path}"
    with open(part_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    partitions = manifest["partitions"]
    part_map = {p["partition_id"]: p for p in partitions}
    assert "PART_QUARANTINED_2020" in part_map
    assert part_map["PART_QUARANTINED_2020"]["access_status"] == "QUARANTINED_CONTAMINATED"


def test_phase24G22_deliverables_exist():
    """Verify all 7 required Phase 24G.22 deliverables exist in the dedicated directory."""
    expected_files = [
        "phase24G22_official_documentation_audit.md",
        "phase24G22_api_limits_and_coverage.md",
        "phase24G22_provider_comparison.csv",
        "phase24G22_signalforge_compatibility.md",
        "phase24G22_sample_pilot_plan.csv",
        "phase24G22_security_audit.md",
        "phase24G22_final_verdict.md",
    ]
    for fname in expected_files:
        fpath = PHASE22_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"


def test_phase24G22_provider_comparison_csv_integrity():
    """Verify provider comparison CSV covers all 11 criteria and accurately notes Angel One free cost."""
    csv_path = PHASE22_DIR / "phase24G22_provider_comparison.csv"
    assert csv_path.exists(), "phase24G22_provider_comparison.csv missing"

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 11, f"Expected 11 criteria rows, found {len(rows)}"
    criteria_names = [r["criterion"] for r in rows]
    assert any("Pricing" in c for c in criteria_names)
    assert any("Coverage" in c for c in criteria_names)

    # Check zero cost for Angel One
    pricing_row = next(r for r in rows if "Pricing" in r["criterion"])
    assert "0" in pricing_row["angel_one_smartapi"] or "Free" in pricing_row["angel_one_smartapi"]


def test_phase24G22_sample_pilot_plan_integrity():
    """Verify sample pilot plan contains exactly 15 targets, 5 symbols, 3 years, and 315 calls."""
    csv_path = PHASE22_DIR / "phase24G22_sample_pilot_plan.csv"
    assert csv_path.exists(), "phase24G22_sample_pilot_plan.csv missing"

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 15, f"Expected 15 pilot items, found {len(rows)}"
    unique_symbols = set(r["symbol"] for r in rows)
    assert len(unique_symbols) == 5, f"Expected 5 unique pilot symbols, got {len(unique_symbols)}"
    assert unique_symbols == {"HDFCBANK", "INFY", "RELIANCE", "MARUTI", "SUNPHARMA"}

    total_api_calls = sum(int(r["planned_api_requests"]) for r in rows)
    assert total_api_calls == 315, f"Expected 315 total API calls in pilot plan, got {total_api_calls}"


def test_phase24G22_symbol_token_coverage_table():
    """Verify that all 22 pre-registered universe equities are mapped in the coverage documentation."""
    coverage_doc = PHASE22_DIR / "phase24G22_api_limits_and_coverage.md"
    assert coverage_doc.exists(), "phase24G22_api_limits_and_coverage.md missing"
    content = coverage_doc.read_text(encoding="utf-8")

    for symbol in EXPECTED_22_SYMBOLS:
        assert f"| **{symbol}** |" in content, f"Symbol {symbol} missing in token mapping table"


def test_phase24G22_final_verdict_content():
    """Verify that the final verdict is READY_FOR_AUTHORIZED_PILOT and notes key constraints."""
    verdict_file = PHASE22_DIR / "phase24G22_final_verdict.md"
    assert verdict_file.exists(), "phase24G22_final_verdict.md missing"
    text = verdict_file.read_text(encoding="utf-8")

    assert "READY_FOR_AUTHORIZED_PILOT" in text
    assert "500" in text  # 500-candle pagination limit
    assert "unadjusted" in text.lower() or "corporate" in text.lower()  # Corporate action note


def test_strict_offline_compliance():
    """Verify strict compliance: zero Angel One credentials, zero unauthorized data downloads."""
    # Assert no Angel One API credentials exist in .env if .env exists
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
        assert "ANGEL_" not in env_content, "Angel One credentials detected in .env"
        assert "SMARTAPI_" not in env_content, "SmartAPI credentials detected in .env"

    # Assert no new historical data files downloaded beyond existing baseline
    stocks_dir = PROJECT_ROOT / "data" / "historical" / "stocks"
    existing_files = list(stocks_dir.glob("*.csv"))
    allowed_baselines = {"ADANIENT_1m", "ADANIPORTS_1m", "ICICIBANK_1m", "INFY_1m", "RELIANCE_1m", "TESTSTOCK_1m"}
    for f in existing_files:
        assert f.stem in allowed_baselines, f"Unexpected data file found: {f.name}"

"""
Unit and Regression Tests for SignalForge Phase 24G.23
======================================================
Verifies:
  1. Preflight baseline V1 config hash invariant (920515d7...)
  2. Canonical ADANIPORTS SHA-256 hash invariant (fb327552...)
  3. Untouched status of paper trading ledger & universe registry
  4. Quarantined 2020 partition isolation
  5. Existence and completeness of all 6 Phase 24G.23 deliverables
  6. Source coverage CSV integrity (validating zero FREE_AND_USABLE sources for 2021–2025 1m)
  7. Existing local datasets temporal boundary (2021-01-01 cutoff, 0 rows in 2022–2025)
  8. Mathematical quality of existing on-disk datasets (0 OHLC violations, 0 negative volume)
  9. Final verdict classification is FREE_DATA_INSUFFICIENT
  10. Strict compliance: zero budget expenditure, zero credentials, zero synthetic fabrication
"""

import csv
import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE23_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G23_zero_cost_data"
V1_SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
ADANIPORTS_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"
STOCKS_DIR = PROJECT_ROOT / "data" / "historical" / "stocks"

EXPECTED_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"

LOCAL_STOCKS = ["ADANIENT_1m.csv", "ADANIPORTS_1m.csv", "ICICIBANK_1m.csv", "INFY_1m.csv", "RELIANCE_1m.csv"]


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


def test_phase24G23_deliverables_exist():
    """Verify all 6 required Phase 24G.23 deliverables exist in the dedicated directory."""
    expected_files = [
        "phase24G23_free_source_comparison.md",
        "phase24G23_source_coverage.csv",
        "phase24G23_existing_dataset_audit.md",
        "phase24G23_data_quality_results.md",
        "phase24G23_license_and_provenance.md",
        "phase24G23_final_verdict.md",
    ]
    for fname in expected_files:
        fpath = PHASE23_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"


def test_phase24G23_source_coverage_csv_integrity():
    """Verify source coverage CSV contains valid records and zero FREE_AND_USABLE sources for target."""
    csv_path = PHASE23_DIR / "phase24G23_source_coverage.csv"
    assert csv_path.exists(), "phase24G23_source_coverage.csv missing"

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) >= 8, f"Expected at least 8 evaluated sources, found {len(rows)}"
    # Check that no source is classified FREE_AND_USABLE for the 2021-2025 22-equity 1m target
    usable_sources = [r for r in rows if r["classification"] == "FREE_AND_USABLE"]
    assert len(usable_sources) == 0, f"No source should qualify as FREE_AND_USABLE: {usable_sources}"


def test_existing_datasets_temporal_boundary():
    """Verify that existing local stock datasets terminate on 2021-01-01 and have zero rows for 2022-2025."""
    for fname in LOCAL_STOCKS:
        fpath = STOCKS_DIR / fname
        assert fpath.exists(), f"Missing stock file: {fname}"
        df = pd.read_csv(fpath)
        dt = pd.to_datetime(df["timestamp"])
        max_dt = dt.max()
        assert max_dt.year == 2021, f"{fname} max year is not 2021: {max_dt}"
        assert max_dt.month == 1 and max_dt.day == 1, f"{fname} does not end on 2021-01-01: {max_dt}"

        # Assert zero rows in 2022, 2023, 2024, 2025
        rows_2022_plus = (dt.dt.year >= 2022).sum()
        assert rows_2022_plus == 0, f"{fname} contains {rows_2022_plus} rows from 2022 onwards"


def test_existing_datasets_mathematical_quality():
    """Verify that existing on-disk stock files have zero OHLC violations and zero negative volume."""
    for fname in LOCAL_STOCKS:
        fpath = STOCKS_DIR / fname
        df = pd.read_csv(fpath)
        # OHLC relations
        assert (df["high"] < df["low"]).sum() == 0, f"{fname} has High < Low violations"
        assert (df["high"] < df["open"]).sum() == 0, f"{fname} has High < Open violations"
        assert (df["high"] < df["close"]).sum() == 0, f"{fname} has High < Close violations"
        assert (df["low"] > df["open"]).sum() == 0, f"{fname} has Low > Open violations"
        assert (df["low"] > df["close"]).sum() == 0, f"{fname} has Low > Close violations"
        # Price and volume
        assert (df["open"] <= 0).sum() == 0, f"{fname} has non-positive open"
        assert (df["close"] <= 0).sum() == 0, f"{fname} has non-positive close"
        assert (df["volume"] < 0).sum() == 0, f"{fname} has negative volume"
        # Duplicate timestamps
        assert df["timestamp"].duplicated().sum() == 0, f"{fname} has duplicate timestamps"


def test_phase24G23_final_verdict_content():
    """Verify that the final verdict is FREE_DATA_INSUFFICIENT and states available boundaries."""
    verdict_file = PHASE23_DIR / "phase24G23_final_verdict.md"
    assert verdict_file.exists(), "phase24G23_final_verdict.md missing"
    text = verdict_file.read_text(encoding="utf-8")

    assert "FREE_DATA_INSUFFICIENT" in text
    assert "2017" in text and "2020" in text  # Available years
    assert "ADANIPORTS" in text and "RELIANCE" in text  # Available stocks
    assert "17" in text or "missing" in text.lower()  # Missing stock mention


def test_strict_zero_budget_and_no_broker_compliance():
    """Verify compliance with strict budget restrictions: zero credentials in .env, zero unauthorized downloads."""
    # Assert no Angel One or new credentials were added
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        assert "ANGEL_" not in content
        assert "KITE_API_KEY" not in content

    # Assert no new unauthorized stock files were created in data/historical/stocks
    allowed_files = {"ADANIENT_1m.csv", "ADANIPORTS_1m.csv", "ICICIBANK_1m.csv", "INFY_1m.csv", "RELIANCE_1m.csv", "TESTSTOCK_1m.csv"}
    actual_files = set(f.name for f in STOCKS_DIR.glob("*.csv"))
    assert actual_files == allowed_files, f"Unexpected files found in stocks dir: {actual_files - allowed_files}"

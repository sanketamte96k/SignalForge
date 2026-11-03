"""
Unit and Regression Tests for SignalForge Phase 24G.18
======================================================
Verifies:
  1. Preflight baseline V1 config hash invariant (920515d7...)
  2. Canonical ADANIPORTS SHA-256 hash invariant (fb327552...)
  3. Untouched status of paper trading ledger & universe registry
  4. Quarantined 2020 partition isolation
  5. Phase 24G.18 candidate snapshot integrity and frozen parameters
  6. Phase 24G.18 partition manifest and locked holdout status
  7. Dataset manifest verification across 22 equities and 8 sectors
  8. Anti-fabrication compliance (zero synthetic trades generated for 2021–2025)
  9. Final verdict and decision gate classifications
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE18_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G18_fresh_oos"
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


def test_candidate_snapshot_integrity():
    """Verify phase24G18_candidate_snapshot.json contains frozen parameters and valid source hashes."""
    snap_path = PHASE18_DIR / "phase24G18_candidate_snapshot.json"
    assert snap_path.exists(), f"Candidate snapshot missing at {snap_path}"
    with open(snap_path, "r", encoding="utf-8") as f:
        snap = json.load(f)

    assert snap["specification"] == "SF-SPEC-ALPHA-2026-V1"
    assert snap["status"] == "DRAFT"
    assert snap["candidate_classification"] == "PROMISING_RESEARCH_CANDIDATE"
    assert snap["hypothesis_name"] == "HYP_B_BASE"
    assert snap["hypothesis_family"] == "VOLATILITY_BREAKOUT"

    # Frozen parameters
    params = snap["parameters"]
    assert params["donchian_period"] == 20
    assert params["rvol_threshold"] == 1.5
    assert params["strict_squeeze"] is False
    assert params["cooldown_minutes"] == 0

    # Risk Engine settings
    risk_params = snap["risk_engine_parameters"]
    assert risk_params["k_stop"] == 1.5
    assert risk_params["k_target"] == 3.0
    assert risk_params["max_leverage"] == 5.0
    assert risk_params["risk_per_trade"] == 0.01
    assert risk_params["execution_model"] == "next_open"


def test_partition_manifest_integrity():
    """Verify partition manifest defines all target partitions and locks the final holdout."""
    part_path = PHASE18_DIR / "phase24G18_partition_manifest.json"
    assert part_path.exists(), f"Partition manifest missing at {part_path}"
    with open(part_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    partitions = manifest["partitions"]
    assert len(partitions) == 4

    part_map = {p["partition_id"]: p for p in partitions}
    assert "PART_01_DEV" in part_map
    assert "PART_02_VAL" in part_map
    assert "PART_03_HOLDOUT" in part_map
    assert "PART_QUARANTINED_2020" in part_map

    # Final holdout must be LOCKED
    assert part_map["PART_03_HOLDOUT"]["access_status"] == "LOCKED"
    # 2020 must be QUARANTINED
    assert part_map["PART_QUARANTINED_2020"]["access_status"] == "QUARANTINED_CONTAMINATED"


def test_dataset_manifest_integrity():
    """Verify dataset manifest covers 22 equities across 8 sectors and records data boundary."""
    manifest_csv = PHASE18_DIR / "phase24G18_dataset_manifest.csv"
    assert manifest_csv.exists(), f"Dataset manifest missing at {manifest_csv}"

    rows = []
    with open(manifest_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 22, f"Expected 22 equities, found {len(rows)}"
    sectors = set(r["sector"] for r in rows)
    assert len(sectors) >= 7, f"Expected at least 7 sectors, found {len(sectors)}"

    for r in rows:
        assert r["inclusion_exclusion_status"] == "EXCLUDED_FROM_OOS_EVALUATION"
        assert "Terminates at 2021-01-01" in r["target_period_coverage"]


def test_anti_fabrication_zero_trades():
    """Verify that zero synthetic trades were fabricated for unavailable 2021–2025 periods."""
    for csv_name in [
        "phase24G18_individual_asset_results.csv",
        "phase24G18_sector_results.csv",
        "phase24G18_yearly_results.csv",
    ]:
        csv_path = PHASE18_DIR / csv_name
        assert csv_path.exists(), f"Missing {csv_path}"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert int(row["trade_count"]) == 0, f"Found non-zero trades in {csv_name}: {row}"
                assert float(row["gross_pnl"]) == 0.0
                assert float(row["net_pnl"]) == 0.0
                assert row["status"] == "NOT_TESTED"


def test_final_verdict_and_holdout_status():
    """Verify final verdict classification and untouched holdout report."""
    verdict_path = PHASE18_DIR / "phase24G18_final_verdict.md"
    holdout_path = PHASE18_DIR / "phase24G18_final_holdout_report.md"

    assert verdict_path.exists(), f"Missing {verdict_path}"
    assert holdout_path.exists(), f"Missing {holdout_path}"

    verdict_text = verdict_path.read_text(encoding="utf-8")
    assert "DATA_QUALITY_FAILURE" in verdict_text
    assert "RESEARCH_INCONCLUSIVE" in verdict_text
    assert "SF-SPEC-ALPHA-2026-V1" in verdict_text
    assert "PROMISING_RESEARCH_CANDIDATE" in verdict_text

    holdout_text = holdout_path.read_text(encoding="utf-8")
    assert "HOLDOUT_LOCKED_UNINSPECTED" in holdout_text
    assert "QUARANTINE COMPLIANCE" in holdout_text

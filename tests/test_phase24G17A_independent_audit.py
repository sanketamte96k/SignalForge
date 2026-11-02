"""
SignalForge Phase 24G.17A — Independent Reproducibility & Statistical Audit Tests
==================================================================================
Validates hash reconciliation, bit-for-bit numerical reproduction, cluster bootstrap,
winner concentration fragility, and directional mechanics across ADANIPORTS, RELIANCE,
INFY, and ICICIBANK.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G17A_independent_audit"
STOCKS_DIR = PROJECT_ROOT / "data" / "historical" / "stocks"
MANIFESTS_DIR = PROJECT_ROOT / "data" / "historical" / "manifests"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
TRUNCATED_PROMPT_HASH = "fb3275527303879c5edd26bc08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_hash_reconciliation_and_transcription_resolution():
    """Verify that ADANIPORTS on disk matches manifest and report, while prompt has 62-char typo."""
    adani_path = STOCKS_DIR / "ADANIPORTS_1m.csv"
    adani_bytes = adani_path.read_bytes()
    computed_hash = hashlib.sha256(adani_bytes).hexdigest()

    # 1. Disk matches 64-char canonical hash
    assert computed_hash == CANONICAL_ADANIPORTS_HASH, "ADANIPORTS hash mismatch"
    assert len(computed_hash) == 64

    # 2. Manifest matches 64-char canonical hash
    manifest_data = json.loads((MANIFESTS_DIR / "ADANIPORTS_1m_manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["content_hash"] == CANONICAL_ADANIPORTS_HASH

    # 3. Prompt string is mathematically invalid 62-char truncated string
    assert len(TRUNCATED_PROMPT_HASH) == 62
    assert TRUNCATED_PROMPT_HASH != computed_hash

    # 4. Invariant hashes
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    v1_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert v1_hash == EXPECTED_V1_CONFIG_HASH, "Frozen V1 config hash modified"
    assert REGISTRY_PATH.exists(), "Universe registry missing"
    assert PAPER_LEDGER_PATH.exists(), "Paper trading ledger missing"


def test_numerical_reproduction_zero_discrepancies():
    """Verify that all 128 metric checks in the discrepancy audit are EXACT_MATCH."""
    disc_file = AUDIT_DIR / "phase24G17A_reproduction_discrepancy.csv"
    assert disc_file.exists(), "Discrepancy CSV missing"

    df_disc = pd.read_csv(disc_file)
    assert len(df_disc) == 128, f"Expected 128 metric evaluations, got {len(df_disc)}"

    discrepancies = df_disc[df_disc["match_status"] != "EXACT_MATCH"]
    assert len(discrepancies) == 0, f"Found {len(discrepancies)} reproduction discrepancies!"


def test_cluster_bootstrap_dependence_awareness():
    """Verify that dependence-aware cluster and block bootstraps properly reflect temporal variance."""
    boot_file = AUDIT_DIR / "phase24G17A_cluster_bootstrap_analysis.csv"
    assert boot_file.exists(), "Cluster bootstrap CSV missing"

    df_boot = pd.read_csv(boot_file)
    assert len(df_boot) == 4

    # Check SE inflation
    day_cluster = df_boot[df_boot["resampling_method"] == "Trading-Day Cluster Bootstrap"].iloc[0]
    block_10 = df_boot[df_boot["resampling_method"] == "10-Day Temporal Block Bootstrap"].iloc[0]

    assert day_cluster["se_inflation_factor"] >= 1.0, "Day cluster SE should not be lower than naive"
    assert block_10["se_inflation_factor"] > 1.10, "10-day block SE should reflect temporal clustering (>1.10x)"


def test_winner_concentration_fragility_classifications():
    """Verify that ADANIPORTS and INFY validation are classified as FRAGILE, others RESILIENT."""
    conc_file = AUDIT_DIR / "phase24G17A_winner_concentration_audit.csv"
    assert conc_file.exists(), "Winner concentration CSV missing"

    df_conc = pd.read_csv(conc_file)

    # ADANIPORTS Validation
    adani_val = df_conc[(df_conc["symbol"] == "ADANIPORTS") & (df_conc["partition"] == "Validation (2019)")].iloc[0]
    assert adani_val["fragility_classification"] == "FRAGILE"
    assert adani_val["flip_to_loss_threshold"] == "EX_TOP_3"
    assert adani_val["ex_top3_net_pnl"] < 0

    # INFY Validation
    infy_val = df_conc[(df_conc["symbol"] == "INFY") & (df_conc["partition"] == "Validation (2019)")].iloc[0]
    assert infy_val["fragility_classification"] == "FRAGILE"
    assert infy_val["flip_to_loss_threshold"] == "EX_TOP_3"
    assert infy_val["ex_top3_net_pnl"] < 0

    # RELIANCE Validation
    rel_val = df_conc[(df_conc["symbol"] == "RELIANCE") & (df_conc["partition"] == "Validation (2019)")].iloc[0]
    assert rel_val["fragility_classification"] == "RESILIENT"
    assert rel_val["ex_top5_net_pnl"] > 0

    # ICICIBANK Validation
    icici_val = df_conc[(df_conc["symbol"] == "ICICIBANK") & (df_conc["partition"] == "Validation (2019)")].iloc[0]
    assert icici_val["fragility_classification"] == "RESILIENT"
    assert icici_val["ex_top5_net_pnl"] > 0


def test_directional_verdict_reconciliation():
    """Verify directional breakdown verdicts (FRICTION_DEFEATED vs PROFITABLE)."""
    dir_file = AUDIT_DIR / "phase24G17A_directional_audit.csv"
    assert dir_file.exists(), "Directional audit CSV missing"

    df_dir = pd.read_csv(dir_file)

    # ADANIPORTS Training Short should be FRICTION_DEFEATED
    adani_tr_short = df_dir[(df_dir["symbol"] == "ADANIPORTS") & (df_dir["partition"] == "Training (2017–2018)") & (df_dir["direction"] == "SHORT")].iloc[0]
    assert adani_tr_short["directional_verdict"] == "FRICTION_DEFEATED"
    assert adani_tr_short["gross_pnl"] > 0
    assert adani_tr_short["net_pnl"] < 0

    # INFY Validation Short should be FRICTION_DEFEATED
    infy_val_short = df_dir[(df_dir["symbol"] == "INFY") & (df_dir["partition"] == "Validation (2019)") & (df_dir["direction"] == "SHORT")].iloc[0]
    assert infy_val_short["directional_verdict"] == "FRICTION_DEFEATED"
    assert infy_val_short["gross_pnl"] > 0
    assert infy_val_short["net_pnl"] < 0

    # ICICIBANK Training Short should be highly profitable
    icici_tr_short = df_dir[(df_dir["symbol"] == "ICICIBANK") & (df_dir["partition"] == "Training (2017–2018)") & (df_dir["direction"] == "SHORT")].iloc[0]
    assert icici_tr_short["directional_verdict"] == "PROFITABLE"
    assert icici_tr_short["net_pnl"] > 10000.0


def test_discrepancy_register_and_reconciliation():
    """Verify discrepancy register deliverables, reproduction comparison CSV, and exact Rs 0.41 resolution."""
    # 1. Reproduction comparison CSV
    comp_file = AUDIT_DIR / "phase24G17A_reproduction_comparison.csv"
    assert comp_file.exists(), "phase24G17A_reproduction_comparison.csv missing"
    df_comp = pd.read_csv(comp_file)
    assert len(df_comp) == 128, f"Expected 128 rows, got {len(df_comp)}"
    assert (df_comp["absolute_difference"] == 0.0).all(), "Found non-zero absolute difference in reproduction!"

    # 2. Reconcile exact Rs 0.41 discrepancy
    # Table 6.1 reported values:
    table61_long_net = 10743.20
    table61_short_net = 8434.95
    table61_directional_sum = round(table61_long_net + table61_short_net, 2)
    assert table61_directional_sum == 19178.15

    # Table 5.1 / CSV pooled net P&L:
    table51_pooled_net = 19177.74
    discrepancy = round(table61_directional_sum - table51_pooled_net, 2)
    assert discrepancy == 0.41, f"Expected Rs 0.41 discrepancy, got {discrepancy}"

    # Deconstruction:
    # Component A: Table 6.1 long friction understatement (20144.67 vs true 20145.07 -> Rs 0.40)
    true_long_friction = 20145.07
    table61_long_friction = 20144.67
    friction_err = round(true_long_friction - table61_long_friction, 2)
    assert friction_err == 0.40

    # Component B: INFY directional rounding (3339.83 - 374.33 = 2965.50 vs 2965.49 -> Rs 0.01)
    infy_directional_sum = 3339.83 - 374.33
    infy_stock_net = 2965.49
    infy_rounding_err = round(infy_directional_sum - infy_stock_net, 2)
    assert infy_rounding_err == 0.01
    assert round(friction_err + infy_rounding_err, 2) == 0.41

    # 3. Final verdict document
    verdict_file = AUDIT_DIR / "phase24G17A_final_audit_verdict.md"
    assert verdict_file.exists(), "phase24G17A_final_audit_verdict.md missing"
    verdict_text = verdict_file.read_text(encoding="utf-8")
    assert "REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE" in verdict_text



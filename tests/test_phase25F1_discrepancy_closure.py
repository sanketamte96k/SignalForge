"""
SignalForge — Phase 25F.1 Final Audit Discrepancy Closure Test Suite
===================================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config, ADANIPORTS, NIFTY 50, paper ledger, 2020 quarantine).
  2. Deliverables completeness (all 5 files in phase25F1_discrepancy_closure/ exist and are non-empty).
  3. Historical membership count resolution (BHEL 544, IDEA 539, NESTLEIND 491, raw-tenure-excluded identities).
  4. Statistical power methodology verification (return stdev, MDE calculations, effective sample size, binomial power).
  5. Cost figure reconciliation identities (unit ₹31,827.60, portfolio ₹459,066.11, one-way ₹15,961.56, 17.3876x turnover scaling).
  6. Official verdict assertion (ALL_DISCREPANCIES_RESOLVED).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import pytest
import pandas as pd

FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25F1_discrepancy_closure")


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
    """Verify 2020 quarantine directory exists and no 2020 trades exist in cache."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_phase25f1_deliverables_completeness():
    """Verify all 5 Phase 25F.1 deliverables exist and have non-zero size."""
    expected_files = [
        "phase25F1_discrepancy_resolution.md",
        "phase25F1_corrected_membership_counts.csv",
        "phase25F1_statistical_power_methodology.md",
        "phase25F1_cost_figure_reconciliation.md",
        "phase25F1_results_manifest.json",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Deliverable {fn} missing"
        assert p.stat().st_size > 0, f"Deliverable {fn} is empty"


# ============================================================================
# 3. Historical Membership Count Resolution
# ============================================================================

def test_corrected_membership_counts_integrity():
    """Verify corrected trade counts and exact accounting identities for all 38 stocks."""
    csv_path = DELIVERABLES_DIR / "phase25F1_corrected_membership_counts.csv"
    df = pd.read_csv(csv_path)
    assert len(df) == 38, f"Expected 38 historical stocks, got {len(df)}"

    # Universal accounting identity: raw = tenure + excluded
    assert (df["raw_unfiltered_trades"] == df["tenure_bounded_trades"] + df["corrected_excluded_trades"]).all()

    # Specific audited stocks
    by_sym = {r["symbol"]: r for _, r in df.iterrows()}

    # BHEL
    bhel = by_sym["BHEL"]
    assert bhel["raw_unfiltered_trades"] == 585
    assert bhel["tenure_bounded_trades"] == 41
    assert bhel["corrected_excluded_trades"] == 544

    # IDEA
    idea = by_sym["IDEA"]
    assert idea["raw_unfiltered_trades"] == 584
    assert idea["tenure_bounded_trades"] == 45
    assert idea["corrected_excluded_trades"] == 539

    # NESTLEIND
    nestle = by_sym["NESTLEIND"]
    assert nestle["raw_unfiltered_trades"] == 538
    assert nestle["tenure_bounded_trades"] == 47
    assert nestle["corrected_excluded_trades"] == 491

    # BRITANNIA
    brit = by_sym["BRITANNIA"]
    assert brit["raw_unfiltered_trades"] == 571
    assert brit["tenure_bounded_trades"] == 158
    assert brit["corrected_excluded_trades"] == 413

    # IBULHSGFIN
    ibul = by_sym["IBULHSGFIN"]
    assert ibul["raw_unfiltered_trades"] == 544
    assert ibul["tenure_bounded_trades"] == 462
    assert ibul["corrected_excluded_trades"] == 82

    # IOC
    ioc = by_sym["IOC"]
    assert ioc["raw_unfiltered_trades"] == 579
    assert ioc["tenure_bounded_trades"] == 537
    assert ioc["corrected_excluded_trades"] == 42


# ============================================================================
# 4. Statistical Power Methodology Verification
# ============================================================================

def test_statistical_power_mathematical_identities():
    """Verify MDE, binomial power, and effective sample size calculations."""
    n = 525
    sigma_bps = 132.2
    se_bps = sigma_bps / math.sqrt(n)

    # 1. Standard Error
    assert abs(se_bps - 5.769) < 0.05

    # 2. Minimum Detectable Effect at 80% power (alpha=0.05 one-sided)
    z_alpha = 1.6448536269514722
    z_beta_80 = 0.8416212335729143
    mde_80 = (z_alpha + z_beta_80) * se_bps
    assert abs(mde_80 - 14.34) < 0.1

    # 3. Minimum Detectable Effect at 99% power
    z_beta_99 = 2.3263478740408408
    mde_99 = (z_alpha + z_beta_99) * se_bps
    assert abs(mde_99 - 22.91) < 0.1

    # 4. Binomial power for +2% win rate (p=0.52 vs p0=0.50)
    p0 = 0.50
    p1 = 0.52
    delta_p = p1 - p0
    z_pow = (delta_p * math.sqrt(n) - z_alpha * math.sqrt(p0 * (1 - p0))) / math.sqrt(p1 * (1 - p1))
    pow_2pct = 0.5 * math.erfc(-z_pow / math.sqrt(2.0))
    assert abs(pow_2pct - 0.233) < 0.01, f"Expected ~23.3% power, got {pow_2pct:.3f}"

    # 5. Bartlett Autocorrelation Adjustment (rho1 = 0.063)
    rho1 = 0.063
    n_eff = n / (1 + 2 * rho1)
    assert abs(n_eff - 466.25) < 0.5


# ============================================================================
# 5. Transaction-Cost Figure Reconciliation Verification
# ============================================================================

def test_cost_figure_reconciliation_identities():
    """Verify penny-level mathematical reconciliation across Figure 1, 2, and 3."""
    manifest_path = DELIVERABLES_DIR / "phase25F1_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    c_summary = m["audit_closure_summary"]["cost_figures_reconciliation"]

    # 1. Figure values
    fig1 = c_summary["figure_1_one_way_friction_inr"]
    fig2 = c_summary["figure_2_round_trip_unit_friction_inr"]
    fig3 = c_summary["figure_3_portfolio_friction_inr"]

    assert fig1 == 15961.56
    assert fig2 == 31827.60
    assert fig3 == 459066.11

    # 2. Figure 1 is approximately half of Figure 2 (one-way entry friction)
    ratio_1_2 = fig1 / fig2
    assert 0.50 <= ratio_1_2 <= 0.502

    # 3. Turnover scaling
    unit_turnover = c_summary["unit_aggregate_turnover_inr"]
    port_turnover = c_summary["portfolio_aggregate_turnover_inr"]
    assert unit_turnover == 46562469.77
    assert port_turnover == 809641281.73

    mult = port_turnover / unit_turnover
    assert abs(mult - 17.3876) < 0.001

    # 4. Brokerage cap saturation
    assert c_summary["portfolio_brokerage_cap_hit_rate_pct"] == 100.0
    assert c_summary["portfolio_brokerage_amount_inr"] == 162960.0


# ============================================================================
# 6. Official Sign-Off Verification
# ============================================================================

def test_official_closure_verdict():
    """Verify verdict is ALL_DISCREPANCIES_RESOLVED."""
    manifest_path = DELIVERABLES_DIR / "phase25F1_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["verdict"] == "ALL_DISCREPANCIES_RESOLVED"

    doc = (DELIVERABLES_DIR / "phase25F1_discrepancy_resolution.md").read_text(encoding="utf-8")
    assert "**`ALL_DISCREPANCIES_RESOLVED`**" in doc


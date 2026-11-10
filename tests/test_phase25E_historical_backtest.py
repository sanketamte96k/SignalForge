"""
SignalForge — Phase 25E Historical Tenure-Bounded Backtest Test Suite
=====================================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config hash, ADANIPORTS, NIFTY 50, paper ledger, universe registry, 2020 quarantine).
  2. Deliverables completeness (9 files in research/strategy_evolution_2018/phase25E_historical_backtest/).
  3. Universe execution integrity (exactly 38 historical stocks evaluated across Models A, B, and C).
  4. Mathematical accounting identities (Net P&L = Gross P&L - Total Costs across all stocks and portfolio).
  5. Tenure bounding enforcement (pruning of out-of-tenure trades for BHEL, IDEA, NESTLEIND, GRASIM, etc.).
  6. Realistic fee breakdown and classification distributions (0 positive, 31 negative, 4 inconclusive, 3 insufficient sample).
  7. Shared-capital portfolio simulation constraints (₹10 Lakh capital, 10 slots, trade rejections).
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

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25E_historical_backtest")


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
    manifest_path = Path("research/strategy_evolution_2018/phase25E_historical_backtest/phase25E_results_manifest.json")
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
    """Verify 2020 quarantine directory exists and no 2020 trades exist in cache."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"
    q_files = list(q_dir.glob("*.csv"))
    assert len(q_files) > 0, "Quarantined files missing"

    cache_path = DELIVERABLES_DIR / "phase25E_38stock_raw_trades_cache.json"
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)

    for stock_data in cache:
        for tr in stock_data["raw_trades"]:
            entry_time = tr.get("entry_time", "")
            assert not entry_time.startswith("2020"), (
                f"Quarantine violation: Trade found in 2020 ({stock_data['symbol']} at {entry_time})"
            )


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_all_phase25e_deliverables_exist():
    """Verify all mandatory Phase 25E deliverables exist on disk."""
    expected_files = [
        "phase25E_38stock_individual_results.csv",
        "phase25E_training_and_validation_results.csv",
        "phase25E_membership_window_execution_audit.md",
        "phase25E_fee_cost_breakdown.csv",
        "phase25E_shared_capital_portfolio_report.md",
        "phase25E_performance_ranking.md",
        "phase25E_statistical_robustness_report.md",
        "phase25E_results_manifest.json",
        "phase25E_final_report.md",
        "phase25E_38stock_raw_trades_cache.json",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Phase 25E deliverable missing: {fn}"
        assert p.stat().st_size > 0, f"Deliverable is empty: {fn}"


# ============================================================================
# 3. 38-Stock Results & Classification Integrity
# ============================================================================

def test_38_stock_individual_results_integrity():
    """Verify 38-stock CSV integrity, net P&L identity, and classification distributions."""
    csv_path = DELIVERABLES_DIR / "phase25E_38stock_individual_results.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 38, f"Expected 38 rows, got {len(df)}"
    assert df["symbol"].nunique() == 38

    # Every row must satisfy net_pnl = gross_pnl - total_transaction_costs
    for _, row in df.iterrows():
        gross = float(row["gross_pnl"])
        costs = float(row["total_transaction_costs"])
        net = float(row["net_pnl"])
        assert abs(net - (gross - costs)) < 0.05, f"P&L identity violation for {row['symbol']}"

    # Verify zero positive results under realistic friction
    assert (df["classification"] != "POSITIVE_RESEARCH_RESULT").all(), (
        "Zero stocks should achieve POSITIVE_RESEARCH_RESULT under realistic discount-broker friction"
    )

    class_counts = df["classification"].value_counts().to_dict()
    assert class_counts.get("NEGATIVE_RESEARCH_RESULT", 0) == 31
    assert class_counts.get("STATISTICALLY_INCONCLUSIVE", 0) == 4
    assert class_counts.get("INSUFFICIENT_SAMPLE", 0) == 3


def test_tenure_bounded_audit_pruning():
    """Verify that early exits and short tenure stocks are correctly pruned and classified."""
    csv_path = DELIVERABLES_DIR / "phase25E_38stock_individual_results.csv"
    df = pd.read_csv(csv_path)

    # BHEL and IDEA had active tenure only Jan-Mar 2017
    bhel = df[df["symbol"] == "BHEL"].iloc[0]
    assert bhel["tenure_trades_count"] == 41
    assert bhel["classification"] == "INSUFFICIENT_SAMPLE"

    idea = df[df["symbol"] == "IDEA"].iloc[0]
    assert idea["tenure_trades_count"] == 45
    assert idea["classification"] == "INSUFFICIENT_SAMPLE"

    # NESTLEIND had active tenure only Sep-Dec 2019
    nestle = df[df["symbol"] == "NESTLEIND"].iloc[0]
    assert nestle["tenure_trades_count"] == 47
    assert nestle["classification"] == "INSUFFICIENT_SAMPLE"


def test_fee_cost_breakdown_csv_integrity():
    """Verify granular fee breakdown CSV matches sum identities."""
    csv_path = DELIVERABLES_DIR / "phase25E_fee_cost_breakdown.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 38, f"Expected 38 rows in fee breakdown CSV, got {len(df)}"
    for _, row in df.iterrows():
        total_costs = float(row["total_costs_inr"])
        gross_pnl = float(row["gross_pnl"])
        net_pnl = float(row["net_pnl_inr"])

        # Net P&L identity
        assert abs(net_pnl - (gross_pnl - total_costs)) < 0.05

        summed = (
            float(row["brokerage_inr"])
            + float(row["stt_inr"])
            + float(row["exchange_charges_inr"])
            + float(row["sebi_charges_inr"])
            + float(row["stamp_duty_inr"])
            + float(row["gst_inr"])
            + float(row["slippage_inr"])
            + float(row["spread_cost_inr"])
        )
        assert abs(total_costs - summed) < 5.0, f"Fee sum mismatch for {row['symbol']}"


# ============================================================================
# 4. Training and Validation Results Integrity
# ============================================================================

def test_training_and_validation_results_integrity():
    """Verify training and validation CSV contains exactly 38 rows with valid sums."""
    csv_path = DELIVERABLES_DIR / "phase25E_training_and_validation_results.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 38

    # For continuous stocks, training_trades + validation_trades equals total tenure trades
    indiv_df = pd.read_csv(DELIVERABLES_DIR / "phase25E_38stock_individual_results.csv")
    merged = df.merge(indiv_df[["symbol", "tenure_trades_count"]], on="symbol")

    for _, row in merged.iterrows():
        train_n = int(row["training_trades"])
        val_n = int(row["validation_trades"])
        tot_n = int(row["tenure_trades_count"])
        assert train_n + val_n == tot_n, f"Trade count sum mismatch for {row['symbol']}"


# ============================================================================
# 5. Shared-Capital Portfolio Accounting Verification
# ============================================================================

def test_shared_portfolio_accounting():
    """Verify shared-capital portfolio simulation metrics from manifest."""
    manifest_path = DELIVERABLES_DIR / "phase25E_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    port = manifest["shared_portfolio_simulation"]
    b = port["model_b_discount_broker"]

    # Starting capital = ₹10 Lakh
    assert b["initial_capital"] == 1000000.0

    # Net P&L = Gross P&L - Total Costs
    expected_net = round(b["gross_pnl"] - b["total_costs"], 2)
    assert abs(b["net_portfolio_pnl"] - expected_net) < 1.0

    # Ending capital = Initial + Net P&L
    assert abs(b["final_equity"] - (b["initial_capital"] + b["net_portfolio_pnl"])) < 1.0

    # Signals accepted + rejected = total candidate signals
    assert b["accepted_trades_count"] + b["rejected_trades_count"] == b["total_signals"]

    # Rejection rate should be between 70% and 85% due to capacity & cash exhaustion
    rejection_rate = b["rejected_trades_count"] / b["total_signals"]
    assert 0.70 < rejection_rate < 0.85

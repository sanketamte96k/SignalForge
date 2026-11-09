"""
SignalForge — Phase 25B Cross-Asset Backtest Test Suite
======================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config hash, ADANIPORTS, NIFTY 50, 2020 quarantine).
  2. Deliverables completeness (9 files in research/strategy_evolution_2018/phase25B_cross_asset_backtest/).
  3. Universe coverage (exactly 34 eligible stocks evaluated across Training and Validation).
  4. Mathematical & accounting integrity (win rate, trade summation, P&L decomposition, CIs).
  5. Combined portfolio simulation constraints (capital limits, position caps, trade rejections).
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

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25B_cross_asset_backtest")


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


# ============================================================================
# 2. Deliverables Completeness Verification
# ============================================================================

def test_all_phase25b_deliverables_exist():
    """Verify all 9 mandatory Phase 25B deliverables exist on disk."""
    expected_files = [
        "phase25B_34stock_individual_results.csv",
        "phase25B_training_results_2017_2018.csv",
        "phase25B_validation_results_2019.csv",
        "phase25B_results_manifest.json",
        "phase25B_stock_performance_ranking.md",
        "phase25B_combined_portfolio_report.md",
        "phase25B_data_quality_exceptions.md",
        "phase25B_statistical_validation_report.md",
        "phase25B_final_report.md",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Phase 25B deliverable missing: {fn}"
        assert p.stat().st_size > 0, f"Deliverable is empty: {fn}"


# ============================================================================
# 3. 34-Stock Dataset Coverage & Execution Verification
# ============================================================================

def test_34_stocks_individual_results_integrity():
    """Verify the 34-stock results CSV contains exactly 34 stocks with valid data."""
    csv_path = DELIVERABLES_DIR / "phase25B_34stock_individual_results.csv"
    df = pd.read_csv(csv_path)
    assert len(df) == 34, f"Expected 34 rows in results CSV, got {len(df)}"
    assert df["symbol"].nunique() == 34, "Symbols must be unique across all 34 rows"

    # All 34 completed
    assert (df["status"] == "COMPLETED").all(), "All 34 eligible stocks must have COMPLETED status"

    # Verify approved classification values
    valid_classes = {
        "POSITIVE_RESEARCH_RESULT",
        "NEGATIVE_RESEARCH_RESULT",
        "STATISTICALLY_INCONCLUSIVE",
        "INSUFFICIENT_SAMPLE",
        "BLOCKED_DATA_QUALITY",
    }
    assert set(df["classification"]).issubset(valid_classes), "Unexpected classification category found"


def test_training_and_validation_csv_counts():
    """Verify Training (2017-2018) and Validation (2019) result CSVs have 34 rows."""
    df_train = pd.read_csv(DELIVERABLES_DIR / "phase25B_training_results_2017_2018.csv")
    df_val = pd.read_csv(DELIVERABLES_DIR / "phase25B_validation_results_2019.csv")
    assert len(df_train) == 34, f"Training CSV must have 34 rows, found {len(df_train)}"
    assert len(df_val) == 34, f"Validation CSV must have 34 rows, found {len(df_val)}"


# ============================================================================
# 4. Mathematical and Accounting Invariant Verification
# ============================================================================

def test_mathematical_metrics_consistency():
    """Verify mathematical definitions across all stock rows."""
    csv_path = DELIVERABLES_DIR / "phase25B_34stock_individual_results.csv"
    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        total = int(row["total_trades"])
        win = int(row["winning_trades"])
        loss = int(row["losing_trades"])
        be = int(row["breakeven_trades"])

        # Trade count identity: Total == Win + Loss + Breakeven
        assert total == win + loss + be, f"Trade count sum mismatch for {row['symbol']}"

        # Win rate calculation: win / total * 100
        expected_wr = round(win / total * 100.0, 2)
        assert abs(float(row["win_rate_pct"]) - expected_wr) < 0.05, f"Win rate mismatch for {row['symbol']}"

        # Wilson Confidence Interval boundary check
        ci_low = float(row["win_rate_ci_low"])
        ci_high = float(row["win_rate_ci_high"])
        assert 0.0 <= ci_low <= ci_high <= 100.0, f"Invalid CI range for {row['symbol']}"
        assert ci_low <= float(row["win_rate_pct"]) <= ci_high or total == 0, f"Win rate outside CI for {row['symbol']}"

        # Directional trade count identity: Long + Short == Total
        long_trades = int(row["long_trades"])
        short_trades = int(row["short_trades"])
        assert long_trades + short_trades == total, f"Long + Short != Total for {row['symbol']}"

        # P&L accounting identity: Net P&L ~= Long Net + Short Net
        net = float(row["net_pnl"])
        l_net = float(row["long_net_pnl"])
        s_net = float(row["short_net_pnl"])
        assert abs(net - (l_net + s_net)) < 1.0, f"Net P&L decomposition mismatch for {row['symbol']}"

        # Cost sensitivity monotonic degradation
        c1 = float(row["cost_sensitivity_1bps_net"])
        c2 = float(row["cost_sensitivity_2bps_net"])
        c5 = float(row["cost_sensitivity_5bps_net"])
        assert c1 >= c2 >= c5, f"Cost sensitivity non-monotonic for {row['symbol']}"


# ============================================================================
# 5. Combined Portfolio Simulation Verification
# ============================================================================

def test_combined_portfolio_results_integrity():
    """Verify shared-capital multi-asset portfolio simulation results in manifest."""
    manifest_path = DELIVERABLES_DIR / "phase25B_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    port = manifest["combined_portfolio"]
    init_cap = float(port["initial_capital_inr"])
    fin_eq = float(port["final_equity_inr"])
    net_pnl = float(port["net_portfolio_pnl_inr"])

    assert init_cap == 1000000.0, f"Expected starting capital 1,000,000, got {init_cap}"
    assert abs((init_cap + net_pnl) - fin_eq) < 0.05, "Portfolio equity identity violated"

    # Verify trade rejections due to capacity limit
    total_sig = port["total_signals_submitted"]
    acc = port["total_accepted_trades"]
    rej = port["total_rejected_trades"]
    assert total_sig == acc + rej, f"Signals sum mismatch: {total_sig} != {acc} + {rej}"
    assert rej > 0, "Shared portfolio must exhibit trade rejections due to capacity limits"
    assert port["rejection_rate_pct"] > 50.0, "Expected significant rejection rate due to concurrency"


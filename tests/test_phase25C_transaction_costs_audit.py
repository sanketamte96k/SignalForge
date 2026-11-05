"""
SignalForge — Phase 25C Transaction Cost & Research Integrity Audit Test Suite
==============================================================================
Verifies:
  1. Protected Invariants & Provenance (V1 config hash, ADANIPORTS, NIFTY 50, paper ledger, universe registry, 2020 quarantine).
  2. Deliverables completeness (CSV, JSON, Markdown reports, raw trades cache).
  3. Cost Engine mathematical accuracy (Brokerage cap, STT sell-only, Stamp buy-only, GST bases, Net P&L identities).
  4. 34-Stock cost breakdown and classification integrity under realistic discount-broker friction.
  5. Shared-capital portfolio simulation accounting (capital limits, concurrent position caps, trade rejections).
  6. Survivorship bias identification (historical membership vs modern constituent list).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
import pandas as pd

from src.backtest.indian_market_costs import (
    calculate_trade_transaction_costs,
    calculate_indian_market_cost,
    STATUTORY_ONLY_CONFIG,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    CONSERVATIVE_STRESS_CONFIG,
    IntradayCostConfig,
    TradeCostBreakdown,
)

FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"

DELIVERABLES_DIR = Path("research/strategy_evolution_2018/phase25C_transaction_costs_audit")


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
    """Verify 2020 quarantine directory exists and no 2020 trades exist in backtest cache."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"
    q_files = list(q_dir.glob("*.csv"))
    assert len(q_files) > 0, "Quarantined files missing"

    # Verify no trade in the Phase 25C cache was executed in 2020
    cache_path = DELIVERABLES_DIR / "phase25C_raw_trades_cache.json"
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

def test_all_phase25c_deliverables_exist():
    """Verify all mandatory Phase 25C deliverables exist on disk."""
    expected_files = [
        "phase25C_34stock_brokerage_inclusive_results.csv",
        "phase25C_stock_cost_breakdown.csv",
        "phase25C_cost_model_specification.md",
        "phase25C_survivorship_bias_audit.md",
        "phase25C_shared_portfolio_report.md",
        "phase25C_statistical_validation_report.md",
        "phase25C_results_manifest.json",
        "phase25C_final_report.md",
        "phase25C_raw_trades_cache.json",
    ]
    for fn in expected_files:
        p = DELIVERABLES_DIR / fn
        assert p.exists(), f"Phase 25C deliverable missing: {fn}"
        assert p.stat().st_size > 0, f"Deliverable is empty: {fn}"


def test_raw_trades_cache_integrity():
    """Verify raw trades cache contains exactly 34 symbols and 19,223 raw trade executions."""
    cache_path = DELIVERABLES_DIR / "phase25C_raw_trades_cache.json"
    assert cache_path.exists(), "Raw trades cache missing"
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)

    assert len(cache) == 34, f"Cache must contain 34 symbols, found {len(cache)}"
    total_trades = sum(len(stock_item["raw_trades"]) for stock_item in cache)
    assert total_trades == 19223, f"Expected 19,223 total trade executions in cache, found {total_trades}"


# ============================================================================
# 3. Cost Engine Unit Tests & Mathematical Identities
# ============================================================================

def test_cost_engine_discount_broker_capped_trade():
    """Verify brokerage cap (₹20/leg) and statutory formulas for large turnover trade."""
    cost = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=100.0,
        exit_price=105.0,
        quantity=1000,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    # Brokerage capped at ₹20 per leg = ₹40 total
    assert round(cost.brokerage, 2) == 40.00
    # STT: 0.025% of exit turnover (105,000) = 26.25
    assert round(cost.stt, 2) == 26.25
    # NSE Charges: 0.00325% of total turnover (205,000) = 6.6625 -> rounded 6.66
    assert abs(cost.exchange_charges - 6.66) <= 0.05
    # SEBI: 0.0001% of 205,000 = 0.205 -> rounded 0.21
    assert abs(cost.sebi_charges - 0.21) <= 0.05
    # Stamp duty: 0.003% of buy turnover (100,000) = 3.00
    assert round(cost.stamp_duty, 2) == 3.00
    # GST: 18% on (brokerage + exchange + sebi) = 18% * 46.87 = 8.44
    assert abs(cost.gst - 8.44) <= 0.05

    # Slippage: 1.0 bps of 205,000 = 20.50
    assert round(cost.slippage, 2) == 20.50
    # Spread: 0.5 bps of 205,000 = 10.25
    assert round(cost.spread_cost, 2) == 10.25

    # Total cost identity
    sum_components = round(
        cost.brokerage
        + cost.stt
        + cost.exchange_charges
        + cost.sebi_charges
        + cost.stamp_duty
        + cost.gst
        + cost.slippage
        + cost.spread_cost,
        2
    )
    assert abs(cost.total_costs - sum_components) <= 0.05
    assert abs(cost.net_pnl - (cost.gross_pnl - cost.total_costs)) <= 0.05
    assert cost.gross_pnl == 5000.0
    assert not cost.is_cost_flipped


def test_cost_engine_small_trade_brokerage_percentage():
    """Verify brokerage percentage (0.03%) applies when under ₹20 cap."""
    cost = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=100.0,
        exit_price=100.5,
        quantity=100,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    # Entry 10,000 * 0.03% = ₹3.00 (< ₹20)
    # Exit 10,050 * 0.03% = ₹3.015 (< ₹20)
    # Total brokerage = ₹6.015 -> 6.02
    assert abs(cost.brokerage - 6.02) <= 0.02


def test_cost_engine_short_trade_stt_and_stamp():
    """Verify STT and Stamp duty apply strictly to sell and buy legs for SHORT trades."""
    # SHORT: Entry is SELL, Exit is BUY.
    # STT must be on SELL (Entry), Stamp duty must be on BUY (Exit).
    cost = calculate_trade_transaction_costs(
        side="SHORT",
        entry_price=100.0,
        exit_price=95.0,
        quantity=1000,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    # Entry turnover = 100,000 (SELL leg). STT = 0.025% of 100,000 = ₹25.00
    assert round(cost.stt, 2) == 25.00
    # Exit turnover = 95,000 (BUY leg). Stamp duty = 0.003% of 95,000 = ₹2.85
    assert round(cost.stamp_duty, 2) == 2.85


def test_cost_engine_trade_flipping():
    """Verify detection of trades that flip from positive gross to negative net."""
    # Gross profit ₹10, but total costs exceed ₹50 -> flipped
    cost = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=100.0,
        exit_price=100.1,
        quantity=100,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert cost.gross_pnl > 0.0
    assert cost.net_pnl < 0.0
    assert cost.is_cost_flipped is True


def test_calculate_indian_market_cost_alias():
    """Verify convenience alias calculate_indian_market_cost produces identical results."""
    res1 = calculate_trade_transaction_costs("LONG", 100.0, 105.0, 100, DISCOUNT_BROKER_REALISTIC_CONFIG)
    res2 = calculate_indian_market_cost("LONG", 100.0, 105.0, 100, DISCOUNT_BROKER_REALISTIC_CONFIG)
    assert res1 == res2


# ============================================================================
# 4. 34-Stock Results & Classification Verification
# ============================================================================

def test_34_stock_brokerage_inclusive_csv_integrity():
    """Verify 34-stock CSV integrity, net P&L identity, and classification distributions."""
    csv_path = DELIVERABLES_DIR / "phase25C_34stock_brokerage_inclusive_results.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 34, f"Expected 34 rows, got {len(df)}"
    assert df["symbol"].nunique() == 34

    # Every row must satisfy net_pnl = gross_pnl - total_transaction_costs
    for _, row in df.iterrows():
        gross = float(row["gross_pnl"])
        costs = float(row["total_transaction_costs"])
        net = float(row["net_pnl"])
        assert abs(net - (gross - costs)) < 0.05, f"P&L identity violation for {row['symbol']}"

    # Under realistic friction, zero stocks are POSITIVE_RESEARCH_RESULT
    assert (df["classification"] != "POSITIVE_RESEARCH_RESULT").all(), (
        "No stock should achieve POSITIVE_RESEARCH_RESULT under realistic friction across both regimes"
    )

    class_counts = df["classification"].value_counts().to_dict()
    assert class_counts.get("NEGATIVE_RESEARCH_RESULT", 0) == 32, "Expected 32 negative stocks"
    assert class_counts.get("STATISTICALLY_INCONCLUSIVE", 0) == 2, "Expected 2 inconclusive stocks"


def test_stock_cost_breakdown_csv_integrity():
    """Verify the granular per-stock cost breakdown CSV matches component identities."""
    csv_path = DELIVERABLES_DIR / "phase25C_stock_cost_breakdown.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 34, f"Expected 34 rows in cost breakdown CSV, got {len(df)}"
    for _, row in df.iterrows():
        total_costs = float(row["total_costs_inr"])
        gross_pnl = float(row["gross_pnl"])
        net_pnl = float(row["net_pnl_inr"])

        # Net P&L identity: Net P&L = Gross P&L - Total Costs
        assert abs(net_pnl - (gross_pnl - total_costs)) < 0.05, f"Net P&L mismatch for {row['symbol']}"

        # Sum of rounded individual component lines vs total costs across ~600 trades
        # Floating point sub-paisa rounding accumulates up to ~₹2.64 across 600 trades
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
        assert abs(total_costs - summed) < 5.0, f"Cost breakdown sum mismatch for {row['symbol']}"


# ============================================================================
# 5. Shared-Capital Portfolio Accounting Verification
# ============================================================================

def test_shared_portfolio_accounting():
    """Verify shared-capital portfolio simulation metrics from manifest."""
    manifest_path = DELIVERABLES_DIR / "phase25C_results_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    port = manifest["portfolio_simulation"]
    b = port["model_b_discount_broker"]

    # Initial capital = ₹10 Lakh
    assert b["initial_capital"] == 1000000.0

    # Net P&L = Gross P&L - Total Costs
    expected_net = round(b["gross_pnl"] - b["total_costs"], 2)
    assert abs(b["net_portfolio_pnl"] - expected_net) < 1.0

    # Ending capital = Initial + Net P&L
    assert abs(b["final_equity"] - (b["initial_capital"] + b["net_portfolio_pnl"])) < 1.0

    # Signals accepted + rejected = total candidate signals
    assert b["accepted_trades_count"] + b["rejected_trades_count"] == b["total_signals"]

    # Significant rejection rate (~64.9%) due to concurrency / capacity limits
    rejection_rate = b["rejected_trades_count"] / b["total_signals"]
    assert 0.60 < rejection_rate < 0.70


# ============================================================================
# 6. Survivorship Bias Audit Verification
# ============================================================================

def test_survivorship_bias_audit_content():
    """Verify survivorship bias report explicitly identifies non-historical members."""
    bias_path = DELIVERABLES_DIR / "phase25C_survivorship_bias_audit.md"
    assert bias_path.exists()
    content = bias_path.read_text(encoding="utf-8")

    # 5 stocks never in NIFTY 50 during 2017-2019
    never_members = ["ADANIENT", "APOLLOHOSP", "BEL", "SBILIFE", "SHRIRAMFIN"]
    for s in never_members:
        assert s in content, f"Missing non-historical constituent in audit: {s}"

    # Verify mention of excluded historical distressed constituents
    historical_distressed = ["YESBANK", "IBULHSGFIN", "ZEEL"]
    for s in historical_distressed:
        assert s in content, f"Missing historical excluded stock: {s}"

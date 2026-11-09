"""
SignalForge — Phase 27B: Transaction Cost Engine Unification Test Suite
======================================================================
Validates:
1. Buy and sell cost calculations independently (calculate_buy_side_costs, calculate_sell_side_costs).
2. Complete round-trip costs (calculate_trade_transaction_costs, leg additivity).
3. Brokerage minimum and percentage cap (0.03% vs ₹20/leg cap).
4. STT sell-side treatment (LONG exit vs SHORT entry).
5. GST calculation (18% on brokerage + exchange + SEBI).
6. Slippage and spread friction scaling.
7. Small and large turnover scaling (from small retail to large institutional).
8. Zero and invalid quantities, prices, and trade directions (ValueError).
9. Backtest and paper-trading simulation parity (bit-for-bit cost and P&L identity).
10. Regression safety and protected file hash invariance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
import pandas as pd

from src.backtest.indian_market_costs import (
    calculate_buy_side_costs,
    calculate_sell_side_costs,
    calculate_leg_transaction_costs,
    calculate_trade_transaction_costs,
    IntradayCostConfig,
    LegCostBreakdown,
    TradeCostBreakdown,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    STATUTORY_ONLY_CONFIG,
    CONSERVATIVE_STRESS_CONFIG,
    ZERO_COST_CONFIG,
    COST_PROFILES,
    get_cost_config,
)
from src.api.models import BacktestRunRequest
from src.strategy.job_manager import BacktestJobManager, JobStatus
from src.backtest.engine import run_backtest, BacktestResult, IntradayEngineConfig
from src.paper_trading.cost_model import (
    CostModel,
    calculate_trade_costs,
)
from src.backtest.simulator import (
    Position,
    simulate_trade,
)
from src.backtest.engine import (
    IntradayEngineConfig,
    run_backtest,
)


# ============================================================================
# 1. Buy and Sell Cost Calculations Independently
# ============================================================================

def test_01_buy_and_sell_costs_independently():
    """Verify buy-side and sell-side costs are computed independently with appropriate statutory taxes."""
    price = 500.0
    qty = 200
    turnover = price * qty  # 100,000

    buy_cost = calculate_buy_side_costs(price, qty, config=DISCOUNT_BROKER_REALISTIC_CONFIG)
    sell_cost = calculate_sell_side_costs(price, qty, config=DISCOUNT_BROKER_REALISTIC_CONFIG)

    assert buy_cost.leg == "BUY"
    assert buy_cost.turnover == 100000.0
    assert sell_cost.leg == "SELL"
    assert sell_cost.turnover == 100000.0

    # STT: strictly 0 on BUY, strictly 0.025% on SELL
    assert buy_cost.stt == 0.0
    assert sell_cost.stt == 25.0  # 100,000 * 0.025%

    # Stamp Duty: strictly 0.003% on BUY, strictly 0 on SELL
    assert buy_cost.stamp_duty == 3.0  # 100,000 * 0.003%
    assert sell_cost.stamp_duty == 0.0

    # Both legs have identical brokerage (capped at ₹20)
    assert buy_cost.brokerage == 20.0
    assert sell_cost.brokerage == 20.0

    # Both legs have identical exchange and SEBI charges
    assert buy_cost.exchange_charges == round(100000.0 * 0.0000325, 2)
    assert sell_cost.exchange_charges == round(100000.0 * 0.0000325, 2)
    assert buy_cost.sebi_charges == round(100000.0 * 0.000001, 2)
    assert sell_cost.sebi_charges == round(100000.0 * 0.000001, 2)


# ============================================================================
# 2. Complete Round-Trip Costs and Leg Additivity
# ============================================================================

def test_02_round_trip_costs_and_leg_additivity():
    """Verify complete round-trip costs and confirm buy + sell leg components sum to round-trip."""
    entry_p = 1000.0
    exit_p = 1050.0
    qty = 100

    round_trip = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    buy_leg = calculate_buy_side_costs(entry_p, qty, config=DISCOUNT_BROKER_REALISTIC_CONFIG)
    sell_leg = calculate_sell_side_costs(exit_p, qty, config=DISCOUNT_BROKER_REALISTIC_CONFIG)

    # Component additivity checks
    assert round(buy_leg.brokerage + sell_leg.brokerage, 2) == round_trip.brokerage
    assert round(buy_leg.stt + sell_leg.stt, 2) == round_trip.stt
    assert round(buy_leg.exchange_charges + sell_leg.exchange_charges, 2) == round_trip.exchange_charges
    assert round(buy_leg.sebi_charges + sell_leg.sebi_charges, 2) == round_trip.sebi_charges
    assert round(buy_leg.stamp_duty + sell_leg.stamp_duty, 2) == round_trip.stamp_duty
    assert abs(round(buy_leg.gst + sell_leg.gst, 2) - round_trip.gst) <= 0.01
    assert round(buy_leg.slippage + sell_leg.slippage, 2) == round_trip.slippage
    assert round(buy_leg.spread_cost + sell_leg.spread_cost, 2) == round_trip.spread_cost

    # Total cost identity
    expected_total = round(
        round_trip.brokerage
        + round_trip.stt
        + round_trip.exchange_charges
        + round_trip.sebi_charges
        + round_trip.stamp_duty
        + round_trip.gst
        + round_trip.slippage
        + round_trip.spread_cost,
        2,
    )
    assert round_trip.total_costs == expected_total
    assert round_trip.net_pnl == round(round_trip.gross_pnl - round_trip.total_costs, 2)


# ============================================================================
# 3. Brokerage Minimum and Percentage Cap
# ============================================================================

def test_03_brokerage_percentage_and_cap():
    """Verify 0.03% percentage applies when below ₹20, and ₹20 cap applies when above."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG

    # Sub-cap: Turnover ₹10,000 -> 10,000 * 0.0003 = ₹3.00 per leg
    sub_cap = calculate_buy_side_costs(100.0, 100, config=cfg)
    assert sub_cap.brokerage == 3.00

    # At-cap / Above-cap: Turnover ₹100,000 -> 100,000 * 0.0003 = ₹30.00 -> capped at ₹20.00
    above_cap = calculate_buy_side_costs(1000.0, 100, config=cfg)
    assert above_cap.brokerage == 20.00


# ============================================================================
# 4. STT Sell-Side Treatment
# ============================================================================

def test_04_stt_sell_side_treatment():
    """Verify STT is strictly charged on the SELL leg for both LONG and SHORT positions."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG
    entry_p = 100.0
    exit_p = 110.0
    qty = 1000

    # LONG: entry is BUY (100k), exit is SELL (110k) -> STT = 110,000 * 0.00025 = ₹27.50
    long_cost = calculate_trade_transaction_costs("LONG", entry_p, exit_p, qty, config=cfg)
    assert long_cost.stt == 27.50

    # SHORT: entry is SELL (100k), exit is BUY (110k) -> STT = 100,000 * 0.00025 = ₹25.00
    short_cost = calculate_trade_transaction_costs("SHORT", entry_p, exit_p, qty, config=cfg)
    assert short_cost.stt == 25.00


# ============================================================================
# 5. GST Calculation
# ============================================================================

def test_05_gst_calculation_taxable_base():
    """Verify GST is exactly 18% of (Brokerage + Exchange Charges + SEBI Charges)."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG
    cost = calculate_trade_transaction_costs("LONG", 200.0, 210.0, 500, config=cfg)

    # Taxable services
    taxable = cost.brokerage + cost.exchange_charges + cost.sebi_charges
    expected_gst = round(taxable * 0.18, 2)

    assert abs(cost.gst - expected_gst) <= 0.02


# ============================================================================
# 6. Slippage and Spread Friction
# ============================================================================

def test_06_slippage_and_spread():
    """Verify slippage and spread scale linearly with turnover and can be set to zero."""
    # Zero friction profile
    zero_cost = calculate_trade_transaction_costs("LONG", 100.0, 105.0, 100, config=ZERO_COST_CONFIG)
    assert zero_cost.brokerage == 0.0
    assert zero_cost.stt == 0.0
    assert zero_cost.exchange_charges == 0.0
    assert zero_cost.sebi_charges == 0.0
    assert zero_cost.stamp_duty == 0.0
    assert zero_cost.gst == 0.0
    assert zero_cost.slippage == 0.0
    assert zero_cost.spread_cost == 0.0
    assert zero_cost.total_costs == 0.0
    assert zero_cost.net_pnl == zero_cost.gross_pnl

    # With standard friction: slippage 1 bps, spread 0.5 bps
    turnover = (100.0 + 105.0) * 100  # 20,500
    cost = calculate_trade_transaction_costs("LONG", 100.0, 105.0, 100, config=DISCOUNT_BROKER_REALISTIC_CONFIG)
    assert cost.slippage == round(turnover * 0.0001, 2)
    assert cost.spread_cost == round(turnover * 0.00005, 2)


# ============================================================================
# 7. Small and Large Turnover Scaling
# ============================================================================

def test_07_small_and_large_turnover():
    """Verify cost model handles tiny retail orders and large institutional orders without overflow."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG

    # Tiny trade: 1 share of ₹50 stock (Turnover ₹100)
    tiny = calculate_trade_transaction_costs("LONG", 50.0, 52.0, 1, config=cfg)
    assert tiny.turnover == 102.0
    assert tiny.gross_pnl == 2.0
    assert tiny.brokerage == 0.03  # 50 * 0.03% (0.015) + 52 * 0.03% (0.0156) = 0.0306 -> 0.03
    assert tiny.total_costs > 0.0

    # Institutional trade: 10,000 shares of ₹2,500 stock (Turnover ₹50,000,000)
    large = calculate_trade_transaction_costs("LONG", 2500.0, 2550.0, 10000, config=cfg)
    assert large.turnover == 50500000.0
    assert large.brokerage == 40.0  # Capped at ₹20 per leg = ₹40
    assert large.stt == round(2550.0 * 10000 * 0.00025, 2)  # ₹6,375.00
    assert large.total_costs > 0.0
    assert large.net_pnl < large.gross_pnl


# ============================================================================
# 8. Zero and Invalid Quantities / Prices / Sides
# ============================================================================

def test_08_zero_and_invalid_inputs():
    """Verify input validation rejects non-positive quantities, invalid prices, and malformed sides."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG

    # Non-positive quantity
    with pytest.raises(ValueError, match="quantity must be greater than zero"):
        calculate_trade_transaction_costs("LONG", 100.0, 105.0, 0, config=cfg)

    with pytest.raises(ValueError, match="quantity must be greater than zero"):
        calculate_trade_transaction_costs("LONG", 100.0, 105.0, -10, config=cfg)

    # Non-positive entry or exit price
    with pytest.raises(ValueError, match="entry_price must be greater than zero"):
        calculate_trade_transaction_costs("LONG", 0.0, 105.0, 10, config=cfg)

    with pytest.raises(ValueError, match="exit_price must be greater than zero"):
        calculate_trade_transaction_costs("LONG", 100.0, -5.0, 10, config=cfg)

    # Unsupported side
    with pytest.raises(ValueError, match="Unsupported side"):
        calculate_trade_transaction_costs("UNKNOWN_DIRECTION", 100.0, 105.0, 10, config=cfg)


# ============================================================================
# 9. Backtest and Paper-Trading Parity
# ============================================================================

def test_09_backtest_and_paper_trading_parity():
    """Verify backtesting and paper trading produce identical costs, gross P&L, and net P&L."""
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG
    paper_model = CostModel.from_intraday_config(cfg)

    entry_p = 1980.0
    exit_p = 2020.0
    qty = 50

    # Backtest simulation
    backtest_trade = simulate_trade(
        position=Position.LONG,
        entry_time=pd.Timestamp("2024-01-02 10:00:00"),
        exit_time=pd.Timestamp("2024-01-02 10:30:00"),
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        cost_config=cfg,
    )

    # Paper trading simulation
    paper_cost = calculate_trade_costs(
        side="LONG",
        entry_signal_price=entry_p,
        exit_signal_price=exit_p,
        quantity=qty,
        cost_model=paper_model,
    )

    # Direct canonical engine call
    canonical = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        config=cfg,
    )

    # Verify exact parity
    assert backtest_trade.gross_pnl == canonical.gross_pnl == paper_cost.gross_pnl
    assert backtest_trade.transaction_cost == canonical.total_costs == paper_cost.total_cost
    assert backtest_trade.net_pnl == canonical.net_pnl == paper_cost.net_pnl
    assert backtest_trade.brokerage == canonical.brokerage == paper_cost.brokerage
    assert backtest_trade.statutory_fees == canonical.statutory_charges == paper_cost.taxes_and_fees
    assert backtest_trade.slippage == round(canonical.slippage + canonical.spread_cost, 4) == round(paper_cost.slippage_cost + paper_cost.spread_penalty, 4)


# ============================================================================
# 10. Regression Safety & Protected Hashes Invariance
# ============================================================================

def test_10_regression_safety_legacy_parameters():
    """Verify legacy simulate_trade behavior is preserved when cost_config is None."""
    entry_p = 100.0
    exit_p = 105.0
    qty = 10.0
    cost_rate = 0.0001
    brokerage_fee = 20.0

    trade = simulate_trade(
        position=Position.LONG,
        entry_time=pd.Timestamp("2024-01-02 10:00:00"),
        exit_time=pd.Timestamp("2024-01-02 10:15:00"),
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        transaction_cost_rate=cost_rate,
        brokerage=brokerage_fee,
    )

    expected_gross = (exit_p - entry_p) * qty  # 50.0
    turnover = (entry_p + exit_p) * qty  # 2,050
    expected_cost = brokerage_fee + (turnover * cost_rate)  # 20 + 0.205 = 20.205
    expected_net = expected_gross - expected_cost

    assert trade.gross_pnl == expected_gross
    assert abs(trade.transaction_cost - expected_cost) < 1e-6
    assert abs(trade.net_pnl - expected_net) < 1e-6


# ============================================================================
# 11. P1: API Cost Profile Validation (BacktestRunRequest)
# ============================================================================

def test_11_api_cost_profile_validation():
    """Verify BacktestRunRequest validates allowed profiles and rejects malicious/unsupported profiles."""
    from pydantic import ValidationError

    # Default profile is canonical DISCOUNT_BROKER_REALISTIC
    req = BacktestRunRequest()
    assert req.cost_profile == "DISCOUNT_BROKER_REALISTIC"

    # Approved profiles pass cleanly
    for profile in ["DISCOUNT_BROKER_REALISTIC", "STATUTORY_ONLY", "CONSERVATIVE_STRESS", "ZERO_COST", "LEGACY_LINEAR"]:
        r = BacktestRunRequest(cost_profile=profile)
        assert r.cost_profile == profile

    # Case-insensitive normalization
    r_lower = BacktestRunRequest(cost_profile="discount_broker_realistic")
    assert r_lower.cost_profile == "DISCOUNT_BROKER_REALISTIC"

    # Unsupported or malicious profiles are rejected
    for invalid in ["UNKNOWN_PROFILE", "CUSTOM_PROFILE", "eval('__import__')", ""]:
        with pytest.raises(ValidationError):
            BacktestRunRequest(cost_profile=invalid)


# ============================================================================
# 12. P0: Job Manager Cost Model Wiring and Metadata Reporting
# ============================================================================

def test_12_job_manager_cost_wiring_and_metadata():
    """Verify JobManager executes canonical cost model by default and records explicit metadata."""
    manager = BacktestJobManager(max_workers=1)

    # 1. Canonical run on short 5-day slice (2018)
    job = manager.submit_job(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        initial_capital=50000.0,
        quantity=10,
        cost_profile="DISCOUNT_BROKER_REALISTIC",
    )
    assert job._future is not None
    job._future.result(timeout=10.0)

    completed_job = manager.get_job(job.job_id)
    assert completed_job.status == JobStatus.COMPLETED
    assert completed_job.result is not None
    assert "cost_model" in completed_job.result
    cost_meta = completed_job.result["cost_model"]
    assert cost_meta["mode"] == "CANONICAL"
    assert cost_meta["profile_name"] == "DISCOUNT_BROKER_REALISTIC"
    assert cost_meta["brokerage_max_per_leg_inr"] == 20.0
    assert cost_meta["stt_rate_sell_pct"] == 0.00025

    # 2. Explicit Legacy run on short 5-day slice (2018)
    job_legacy = manager.submit_job(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        initial_capital=50000.0,
        quantity=10,
        cost_profile="LEGACY_LINEAR",
        transaction_cost_rate=0.0002,
    )
    assert job_legacy._future is not None
    job_legacy._future.result(timeout=10.0)

    completed_legacy = manager.get_job(job_legacy.job_id)
    assert completed_legacy.status == JobStatus.COMPLETED
    assert completed_legacy.result is not None
    cost_meta_legacy = completed_legacy.result["cost_model"]
    assert cost_meta_legacy["mode"] == "LEGACY_LINEAR"
    assert cost_meta_legacy["transaction_cost_rate"] == 0.0002


# ============================================================================
# 13. P2: Paper Trading Default Spread Consistency (0.5 bps)
# ============================================================================

def test_13_paper_trading_default_spread_consistency():
    """Verify bare default CostModel() has 0.5 bps spread matching DISCOUNT_BROKER_REALISTIC_CONFIG."""
    cm = CostModel()
    assert cm.spread_penalty_bps == 0.5
    assert cm.slippage_bps == 1.0

    # Explicit zero-cost constructor retains 0.0 spread
    cm_zero = CostModel.zero()
    assert cm_zero.spread_penalty_bps == 0.0
    assert cm_zero.slippage_bps == 0.0
    assert cm_zero.brokerage_rate == 0.0

    # Canonical config conversion round-trip
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG
    cm_from_cfg = CostModel.from_intraday_config(cfg)
    assert cm_from_cfg.spread_penalty_bps == 0.5
    assert cm_from_cfg.slippage_bps == 1.0


# ============================================================================
# 14. P3: Exact Numerical Examples & Subtotal Hierarchy Verification
# ============================================================================

def test_14_exact_numerical_examples_and_subtotals():
    """
    Test the two canonical numerical examples independently:
    Example 1: 100 shares @ Entry 1000, Exit 1020
    Example 2: 1 share @ Entry 50, Exit 52
    Verify all subtotal labels and document 1-paisa leg rounding invariance.
    """
    cfg = DISCOUNT_BROKER_REALISTIC_CONFIG

    # --- EXAMPLE 1: 100 shares @ ₹1000 to ₹1020 ---
    ex1 = calculate_trade_transaction_costs("LONG", 1000.0, 1020.0, 100, config=cfg)
    buy1 = calculate_buy_side_costs(1000.0, 100, config=cfg)
    sell1 = calculate_sell_side_costs(1020.0, 100, config=cfg)

    # Gross P&L
    assert ex1.gross_pnl == 2000.0

    # 1. Brokerage: ₹20 + ₹20 = ₹40 (Capped)
    assert ex1.brokerage == 40.0
    assert buy1.brokerage == 20.0
    assert sell1.brokerage == 20.0

    # 2. STT: Sell leg only (0.025% of ₹1,02,000 = ₹25.50)
    assert ex1.stt == 25.50
    assert buy1.stt == 0.0
    assert sell1.stt == 25.50

    # 3. Exchange Charges: 0.00325% on total turnover ₹202,000 = ₹6.565 -> ₹6.56 (Python round-half-to-even)
    assert ex1.exchange_charges in {6.56, 6.57}
    assert buy1.exchange_charges == 3.25
    assert sell1.exchange_charges == 3.31

    # 4. SEBI Charges: 0.0001% on total turnover ₹202,000 = ₹0.20
    assert ex1.sebi_charges == 0.20
    assert buy1.sebi_charges == 0.10
    assert sell1.sebi_charges == 0.10

    # 5. Stamp Duty: Buy leg only (0.003% of ₹100,000 = ₹3.00)
    assert ex1.stamp_duty == 3.00
    assert buy1.stamp_duty == 3.00
    assert sell1.stamp_duty == 0.0

    # 6. GST: 18% on (40 + 6.565 + 0.202) = ₹8.42
    assert ex1.gst == 8.42
    assert buy1.gst == 4.20
    assert sell1.gst == 4.22

    # Subtotal 1: Statutory Charges (Taxes & Fees strictly excluding brokerage)
    expected_statutory = round(ex1.stt + ex1.exchange_charges + ex1.sebi_charges + ex1.stamp_duty + ex1.gst, 2)
    assert ex1.statutory_charges in {43.68, 43.69}
    assert ex1.statutory_charges == expected_statutory
    assert abs(ex1.statutory_charges - 43.69) <= 0.01

    # Subtotal 2: Market Impact Friction (Slippage + Spread)
    assert ex1.slippage == 20.20
    assert ex1.spread_cost == 10.10
    market_friction = round(ex1.slippage + ex1.spread_cost, 2)
    assert market_friction == 30.30

    # Subtotal 3: Total Friction (Brokerage + Statutory + Market Friction)
    expected_total = round(ex1.brokerage + ex1.statutory_charges + market_friction, 2)
    assert ex1.total_costs in {113.98, 113.99}
    assert ex1.total_costs == expected_total
    assert abs(ex1.total_costs - 113.99) <= 0.01

    # Subtotal 4: Net P&L = Gross P&L - Total Friction
    assert ex1.net_pnl in {1886.01, 1886.02}
    assert ex1.net_pnl == round(ex1.gross_pnl - ex1.total_costs, 2)
    assert abs(ex1.net_pnl - 1886.01) <= 0.01

    # Document 1-paisa leg rounding invariance:
    # Buy leg total (₹45.55) + Sell leg total (₹68.43) = ₹113.98 vs Round-trip total (₹113.98/₹113.99)
    leg_sum_total = round(buy1.total_costs + sell1.total_costs, 2)
    assert abs(leg_sum_total - ex1.total_costs) <= 0.01

    # --- EXAMPLE 2: 1 share @ ₹50 to ₹52 ---
    ex2 = calculate_trade_transaction_costs("LONG", 50.0, 52.0, 1, config=cfg)
    assert ex2.gross_pnl == 2.0
    assert ex2.turnover == 102.0
    assert ex2.brokerage == 0.03
    assert ex2.stt == 0.01
    assert ex2.exchange_charges == 0.00
    assert ex2.sebi_charges == 0.00
    assert ex2.stamp_duty == 0.00
    assert ex2.gst == 0.01
    assert ex2.statutory_charges == 0.02
    assert ex2.slippage == 0.01
    assert ex2.spread_cost == 0.01
    assert ex2.total_costs == 0.07
    assert ex2.net_pnl == 1.93


# ============================================================================
# 15. P4: Backtest Engine Result Explicit Metadata
# ============================================================================

def test_15_backtest_result_explicit_cost_metadata():
    """Verify run_backtest records explicit cost_model_info for both canonical and legacy modes."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=10, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [99.0] * 10,
            "close": [102.0] * 10,
            "volume": [1000] * 10,
        },
        index=dates,
    )

    def dummy_sig(candle, history):
        return None

    # Canonical execution
    res_canonical = run_backtest(
        data=df,
        signal_function=dummy_sig,
        initial_capital=10000.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert res_canonical.cost_model_info is not None
    assert res_canonical.cost_model_info["mode"] == "CANONICAL"
    assert res_canonical.cost_model_info["profile_name"] == "DISCOUNT_BROKER_REALISTIC"

    # Legacy execution
    res_legacy = run_backtest(
        data=df,
        signal_function=dummy_sig,
        initial_capital=10000.0,
        transaction_cost_rate=0.0001,
        cost_config=None,
    )
    assert res_legacy.cost_model_info is not None
    assert res_legacy.cost_model_info["mode"] == "LEGACY_LINEAR"
    assert res_legacy.cost_model_info["transaction_cost_rate"] == 0.0001


# ============================================================================
# 16. P0: Strict Field Validation (extra="forbid") on BacktestRunRequest
# ============================================================================

def test_16_extra_forbidden_in_backtest_run_request():
    """Verify BacktestRunRequest rejects unexpected/unknown fields (HTTP 422 behavior)."""
    from pydantic import ValidationError

    # Valid payload parses cleanly
    valid_req = BacktestRunRequest(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        initial_capital=50000.0,
        quantity=5,
        cost_profile="DISCOUNT_BROKER_REALISTIC",
    )
    assert valid_req.symbol == "RELIANCE"

    # Unexpected extra fields are strictly forbidden
    for bad_field in [{"arbitrary_formula": "price * 0.05"}, {"custom_flag": True}, {"injected_sql": "DROP TABLE"}]:
        with pytest.raises(ValidationError) as exc_info:
            BacktestRunRequest(symbol="RELIANCE", **bad_field)
        assert "Extra inputs are not permitted" in str(exc_info.value)


# ============================================================================
# 17. P0: Unified Cost Profile Consistency Across Entry Points (No Silent Fallback)
# ============================================================================

def test_17_cost_profile_entry_point_consistency_and_safety():
    """
    Verify complete behavioral consistency between direct JobManager calls and HTTP API:
    1. Supplying only transaction_cost_rate defaults to CANONICAL (no silent legacy downgrade).
    2. Explicit cost_profile='LEGACY_LINEAR' activates LEGACY_LINEAR across both entry points.
    """
    from src.api.routes.strategy import create_backtest_job
    from src.strategy.job_manager import get_job_manager

    manager = get_job_manager()

    # 1. Direct JobManager: only transaction_cost_rate -> CANONICAL (safe default)
    job_direct_default = manager.submit_job(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        transaction_cost_rate=0.0005,
    )
    job_direct_default._future.result(timeout=10.0)
    res_direct_default = manager.get_job(job_direct_default.job_id).result
    assert res_direct_default["cost_model"]["mode"] == "CANONICAL"
    assert res_direct_default["cost_model"]["profile_name"] == "DISCOUNT_BROKER_REALISTIC"

    # 2. HTTP Request: only transaction_cost_rate -> CANONICAL (identical to direct)
    req_http_default = BacktestRunRequest(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        transaction_cost_rate=0.0005,
    )
    job_http_res = create_backtest_job(req_http_default)
    job_http = manager.get_job(job_http_res.job_id)
    job_http._future.result(timeout=10.0)
    res_http_default = manager.get_job(job_http.job_id).result
    assert res_http_default["cost_model"]["mode"] == "CANONICAL"
    assert res_http_default["cost_model"]["profile_name"] == "DISCOUNT_BROKER_REALISTIC"

    # 3. Direct JobManager: explicit LEGACY_LINEAR -> LEGACY_LINEAR
    job_direct_legacy = manager.submit_job(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        cost_profile="LEGACY_LINEAR",
        transaction_cost_rate=0.0003,
    )
    job_direct_legacy._future.result(timeout=10.0)
    res_direct_legacy = manager.get_job(job_direct_legacy.job_id).result
    assert res_direct_legacy["cost_model"]["mode"] == "LEGACY_LINEAR"
    assert res_direct_legacy["cost_model"]["transaction_cost_rate"] == 0.0003

    # 4. HTTP Request: explicit LEGACY_LINEAR -> LEGACY_LINEAR
    req_http_legacy = BacktestRunRequest(
        symbol="RELIANCE",
        start_date="2018-01-02",
        end_date="2018-01-05",
        cost_profile="LEGACY_LINEAR",
        transaction_cost_rate=0.0004,
    )
    job_http_legacy_res = create_backtest_job(req_http_legacy)
    job_http_legacy = manager.get_job(job_http_legacy_res.job_id)
    job_http_legacy._future.result(timeout=10.0)
    res_http_legacy = manager.get_job(job_http_legacy.job_id).result
    assert res_http_legacy["cost_model"]["mode"] == "LEGACY_LINEAR"
    assert res_http_legacy["cost_model"]["transaction_cost_rate"] == 0.0004


def test_canonical_file_hashes_intact():
    """Verify canonical datasets, paper trading ledger, and universe registry hashes."""
    expected_hashes = {
        "data/historical/stocks/ADANIPORTS_1m.csv": "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9",
        "data/historical/nifty50_1m_signalforge.csv": "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a",
        "data/paper_trading/interactive_trades.json": "f68a0ff20b5bd852eeac1a816c460b13aa27f67b73a293e2ebe8755b4c91ba63",
        "data/universe_registry.json": "adfb9294fc5defa337147d89955456a073a1834d992467956969c51db1062cc3",
    }
    for file_path, expected_hash in expected_hashes.items():
        data = Path(file_path).read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {file_path}"

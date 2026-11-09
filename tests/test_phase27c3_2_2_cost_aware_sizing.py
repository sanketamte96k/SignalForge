"""
Phase 27C.3.2.2: Canonical Cost-Aware Sizing & Allocation Regression Test Suite.

Verifies:
1. Cost-aware sizing enabled by default in CapitalAllocationConfig.
2. Explicit legacy mode with cost-aware sizing disabled.
3. Small trade size where minimum brokerage materially affects risk budget.
4. Larger trade size where brokerage caps (₹20/leg) affect cost scaling.
5. Long position round-trip canonical cost estimation.
6. Short position round-trip canonical cost estimation.
7. Separate entry and exit turnover cost dynamics.
8. Inclusion of brokerage, STT, ETC, SEBI, GST, stamp duty, and slippage per selected canonical profile.
9. Invariant: Cost-aware quantity <= gross-risk-only quantity.
10. Invariant: Final estimated total risk <= candidate risk budget.
11. Aggregate portfolio risk including estimated transaction costs.
12. Multiple candidates competing for shared risk budget under cost-aware allocation.
13. Zero or invalid cost estimates handled safely.
14. Canonical transaction costs deducted exactly once when trade actually closes in PortfolioManager.
15. Purity Invariant: Repeated allocator evaluation leaves PortfolioManager state completely unmutated.
16. Deterministic reproducibility across identical inputs.
"""

from __future__ import annotations

import pytest
import math

from src.backtest.simulator import Position
from src.backtest.portfolio import PortfolioManager
from src.backtest.capital_allocator import (
    CapitalAllocationConfig,
    TradeOpportunity,
    AllocationDecision,
    CapitalAllocator,
)
from src.backtest.indian_market_costs import (
    IntradayCostConfig,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    STATUTORY_ONLY_CONFIG,
    ZERO_COST_CONFIG,
    calculate_trade_transaction_costs,
)


# ============================================================================
# 1. DEFAULT BEHAVIOR & CONFIGURATION
# ============================================================================

def test_01_cost_aware_sizing_enabled_by_default():
    """Verify cost-aware sizing is enabled by default in CapitalAllocationConfig."""
    cfg = CapitalAllocationConfig()
    assert cfg.include_estimated_round_trip_costs_in_sizing is True
    assert cfg.cost_config is None  # Defaults dynamically to DISCOUNT_BROKER_REALISTIC_CONFIG


def test_02_explicit_legacy_mode_disabled():
    """
    Verify explicit legacy mode (include_estimated_round_trip_costs_in_sizing=False)
    sizes purely based on gross stop distance without cost friction.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator_legacy = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,  # ₹500 risk
        include_estimated_round_trip_costs_in_sizing=False,
    ))

    # Stop distance = 25 points -> Q = floor(500 / 25) = 20 shares exactly
    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator_legacy.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.allocated_quantity == 20
    assert dec.estimated_round_trip_cost == 0.0
    assert dec.estimated_risk == 500.0


# ============================================================================
# 2. TRADE SIZE SCALING: SMALL VS LARGE (BROKERAGE CAP IMPACT)
# ============================================================================

def test_03_small_trade_minimum_brokerage_impact():
    """
    Verify small trade size on small account (₹10,000 equity, 1% risk = ₹100).
    Stock: Entry 1000, Stop 990 (dist = 10).
    Gross Q = floor(100 / 10) = 10 shares.
    Turnover ~ ₹19,900.
    Taxes, slippage, and brokerage (~₹10) would push total loss to ~₹110 > ₹100 budget.
    Cost-aware sizing must reduce quantity to guarantee total risk <= ₹100.
    """
    pm = PortfolioManager(initial_capital=10_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(risk_per_trade_pct=0.01))

    opp = TradeOpportunity("STOCK", Position.LONG, 1000.0, 990.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.allocated_quantity < 10  # Reduced due to costs
    assert dec.allocated_quantity == 8  # 8 * 10 = 80 gross + ~12 costs <= 100
    assert dec.estimated_risk <= 100.0
    assert dec.estimated_round_trip_cost > 0.0


def test_04_large_trade_brokerage_cap_scaling():
    """
    Verify larger trade size where the ₹20/leg brokerage cap becomes active.
    ₹100,000 equity, 1% risk = ₹1,000.
    Stock: Entry 2500, Stop 2475 (dist = 25).
    Gross Q = floor(1000 / 25) = 40 shares.
    Turnover for 40 shares = ~₹199,000.
    Turnover * 0.03% = ₹59.7 > ₹20 cap, so brokerage is capped at ₹20 entry + ₹20 exit = ₹40.
    Cost-aware sizing correctly incorporates the capped brokerage + statutory taxes.
    """
    pm = PortfolioManager(initial_capital=100_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(risk_per_trade_pct=0.01))

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.allocated_quantity < 40
    assert dec.allocated_quantity == 35  # 35 * 25 = 875 gross + 104.48 costs = 979.48 <= 1000
    assert dec.estimated_risk <= 1000.0
    assert dec.estimated_round_trip_cost > 40.0  # Capped brokerage (40) + taxes & slippage


# ============================================================================
# 3. POSITION SIDES: LONG VS SHORT ROUND-TRIP COSTS
# ============================================================================

def test_05_long_position_round_trip_costs():
    """
    Verify LONG position cost estimation:
    Stamp duty on BUY (entry), STT on SELL (exit at stop).
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.estimated_round_trip_cost > 0.0
    # Canonical verification
    canonical = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=2500.0,
        exit_price=2475.0,
        quantity=dec.allocated_quantity,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert dec.estimated_round_trip_cost == pytest.approx(canonical.total_costs)


def test_06_short_position_round_trip_costs():
    """
    Verify SHORT position cost estimation:
    STT on SELL (entry), Stamp duty on BUY (exit at stop).
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    opp = TradeOpportunity("RELIANCE", Position.SHORT, 2500.0, 2525.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.estimated_round_trip_cost > 0.0
    canonical = calculate_trade_transaction_costs(
        side="SHORT",
        entry_price=2500.0,
        exit_price=2525.0,
        quantity=dec.allocated_quantity,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert dec.estimated_round_trip_cost == pytest.approx(canonical.total_costs)


# ============================================================================
# 4. CANONICAL PROFILE SELECTION & COMPONENT BREAKDOWN
# ============================================================================

def test_07_entry_and_exit_cost_estimation_breakdown():
    """Verify costs accurately reflect both entry and exit legs from the canonical engine."""
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG
    ))

    opp = TradeOpportunity("INFY", Position.LONG, 1500.0, 1470.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    canonical = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=1500.0,
        exit_price=1470.0,
        quantity=dec.allocated_quantity,
        config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert canonical.brokerage > 0.0
    assert canonical.stt > 0.0
    assert canonical.exchange_charges > 0.0
    assert canonical.gst > 0.0
    assert canonical.slippage > 0.0
    assert dec.estimated_round_trip_cost == pytest.approx(canonical.total_costs)


def test_08_canonical_profile_statutory_only():
    """Verify allocator respects custom profile (e.g. STATUTORY_ONLY: 0 brokerage)."""
    pm = PortfolioManager(initial_capital=50_000.0)

    alloc_statutory = CapitalAllocator(CapitalAllocationConfig(
        cost_config=STATUTORY_ONLY_CONFIG
    ))
    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec_stat = alloc_statutory.evaluate_opportunity(opp, pm)

    canonical_stat = calculate_trade_transaction_costs(
        side="LONG",
        entry_price=2500.0,
        exit_price=2475.0,
        quantity=dec_stat.allocated_quantity,
        config=STATUTORY_ONLY_CONFIG,
    )
    assert canonical_stat.brokerage == 0.0
    assert dec_stat.estimated_round_trip_cost == pytest.approx(canonical_stat.total_costs)


# ============================================================================
# 5. MATHEMATICAL INVARIANTS: QUANTITY & TOTAL RISK BOUNDS
# ============================================================================

def test_09_invariant_cost_aware_quantity_le_gross_quantity():
    """
    Mathematical Invariant:
    Cost-aware allocated quantity must always be <= gross-risk-only quantity.
    """
    pm = PortfolioManager(initial_capital=50_000.0)

    alloc_cost_aware = CapitalAllocator(CapitalAllocationConfig(include_estimated_round_trip_costs_in_sizing=True))
    alloc_gross_only = CapitalAllocator(CapitalAllocationConfig(include_estimated_round_trip_costs_in_sizing=False))

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec_cost = alloc_cost_aware.evaluate_opportunity(opp, pm)
    dec_gross = alloc_gross_only.evaluate_opportunity(opp, pm)

    assert dec_cost.allocated_quantity <= dec_gross.allocated_quantity
    assert dec_cost.allocated_quantity == 17
    assert dec_gross.allocated_quantity == 20


def test_10_invariant_estimated_total_risk_le_risk_budget():
    """
    Mathematical Invariant:
    Final estimated total risk (Gross Risk + Estimated Round-Trip Cost) must never exceed the candidate risk budget.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(risk_per_trade_pct=0.01))  # ₹500 budget

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.estimated_risk <= 500.0
    assert dec.gross_risk + dec.estimated_round_trip_cost == pytest.approx(dec.estimated_risk)


# ============================================================================
# 6. PORTFOLIO-WIDE AGGREGATE RISK INTEGRATION
# ============================================================================

def test_11_aggregate_portfolio_risk_includes_costs():
    """
    Verify that calculate_remaining_portfolio_risk correctly accounts for
    estimated round-trip costs across existing and virtual positions.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,      # ₹500
        max_portfolio_risk_pct=0.03,  # ₹1,500 total
    ))

    # Single trade evaluation
    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    # Remaining portfolio risk after trade should be exactly 1500 - dec.estimated_risk
    expected_remaining = 1500.0 - dec.estimated_risk
    assert dec.remaining_portfolio_risk == pytest.approx(expected_remaining)
    assert dec.remaining_portfolio_risk > 1000.0  # Since dec.estimated_risk < 500


def test_12_multiple_candidates_competing_under_cost_aware_budget():
    """
    Verify multiple candidates evaluated in a batch under cost-aware risk accounting.
    Total allocated risk across all accepted trades cannot exceed the aggregate portfolio risk budget.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,      # ₹500
        max_portfolio_risk_pct=0.02,  # ₹1,000 max total risk budget
    ))

    opp1 = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0, signal_quality=0.9)
    opp2 = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0, signal_quality=0.85)
    opp3 = TradeOpportunity("INFY", Position.LONG, 1500.0, 1480.0, signal_quality=0.8)

    decisions = allocator.allocate_batch([opp1, opp2, opp3], pm)

    accepted = [d for d in decisions if d.accepted]
    assert len(accepted) == 2  # First two fit within ₹1,000 budget; third is rejected

    total_risk = sum(d.estimated_risk for d in accepted)
    assert total_risk <= 1000.0

    rejected = [d for d in decisions if not d.accepted]
    assert len(rejected) == 1
    assert rejected[0].symbol == "INFY"
    assert rejected[0].limiting_constraint == "PORTFOLIO_RISK_LIMIT"


# ============================================================================
# 7. SAFETY & EDGE CASES
# ============================================================================

def test_13_zero_or_invalid_cost_estimates_handled_safely():
    """
    Verify that zero cost config (ZERO_COST_CONFIG) or invalid cost scenarios
    fall back cleanly without dividing by zero or raising exceptions.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(cost_config=ZERO_COST_CONFIG))

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.estimated_round_trip_cost == 0.0
    assert dec.allocated_quantity == 20  # Matches pure gross risk


def test_14_costs_deducted_once_upon_actual_trade_closure():
    """
    Verify that estimated costs used during allocator sizing are NOT deducted from cash,
    and that PortfolioManager remains the sole authority for actual cost deduction at trade exit.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    # Cash and equity must be completely unmutated by evaluation
    assert pm.cash == 50_000.0
    assert pm.equity == 50_000.0

    # Execute trade in portfolio
    pos = pm.open_position(
        symbol=dec.symbol,
        side=opp.side,
        entry_time="09:15",
        entry_price=dec.entry_price,
        quantity=dec.allocated_quantity,
        stop_price=dec.stop_loss,
        risk_amount=dec.estimated_risk,
    )

    # Margin is encumbered; cash remains ₹50,000!
    assert pm.cash == 50_000.0

    # Close trade at stop price with canonical cost profile
    trade = pm.close_position(
        symbol="RELIANCE",
        exit_time="09:45",
        exit_price=dec.stop_loss,
        exit_reason="SL",
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    # Transaction costs are deducted EXACTLY ONCE here upon trade exit
    assert trade.transaction_cost > 0.0
    assert pm.cash == pytest.approx(50_000.0 + trade.net_pnl)
    assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.transaction_cost)


def test_15_purity_invariant_repeated_allocator_evaluation():
    """Verify that multiple allocator evaluations leave PortfolioManager completely unchanged."""
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    initial_cash = pm.cash
    initial_equity = pm.equity
    initial_positions = len(pm.open_positions)
    initial_trades = len(pm.trades)

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)

    for _ in range(5):
        allocator.evaluate_opportunity(opp, pm)
        allocator.allocate_batch([opp], pm)

    assert pm.cash == initial_cash
    assert pm.equity == initial_equity
    assert len(pm.open_positions) == initial_positions
    assert len(pm.trades) == initial_trades


def test_16_deterministic_results_for_identical_inputs():
    """Verify that identical inputs produce bit-for-bit identical AllocationDecision results."""
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0)

    dec1 = allocator.evaluate_opportunity(opp, pm)
    dec2 = allocator.evaluate_opportunity(opp, pm)

    assert dec1 == dec2
    assert dec1.allocated_quantity == dec2.allocated_quantity
    assert dec1.estimated_risk == dec2.estimated_risk
    assert dec1.estimated_round_trip_cost == dec2.estimated_round_trip_cost

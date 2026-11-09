"""
Phase 27C.3.2: Intelligent Capital Sizing & Allocation Strategy Regression Tests.

Verifies:
1. Configurable allocation policy validation and constraints.
2. Sizing mathematical invariants (risk budget, stop distance, cost buffer).
3. Four-way allocation constraints (risk budget, per-stock cap, available margin, portfolio risk).
4. All 14 required synthetic scenarios from Phase 27C.3.2 specification:
   - Scenario 1: ₹50,000 capital with multiple eligible stock opportunities.
   - Scenario 2: One stock attempting to consume excessive capital.
   - Scenario 3: Several simultaneous positions approaching portfolio risk limit.
   - Scenario 4: Reserve capital preventing an otherwise affordable trade.
   - Scenario 5: Insufficient available margin rejection.
   - Scenario 6: Different stop-loss distances producing different quantities.
   - Scenario 7: High-quality opportunity competing with lower-quality opportunity.
   - Scenario 8: Deterministic tie-breaking for identical scores.
   - Scenario 9: Invalid prices and invalid stop-loss inputs.
   - Scenario 10: Existing unrealized losses reducing available capacity.
   - Scenario 11: Existing margin encumbrance limiting additional allocations.
   - Scenario 12: Protection floor or bankruptcy state rejecting new entries.
   - Scenario 13: Partially funded allocation (scaled down to fit limits).
   - Scenario 14: Zero eligible opportunities resulting in no allocation.
5. Invariant: Evaluation does NOT mutate PortfolioManager state.
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


# ============================================================================
# 1. CONFIGURATION & INPUT VALIDATION
# ============================================================================

def test_allocation_config_validation():
    """Verify validation boundaries on CapitalAllocationConfig."""
    # Valid default config
    cfg = CapitalAllocationConfig()
    assert cfg.risk_per_trade_pct == 0.01
    assert cfg.max_stock_allocation_pct == 0.35
    assert cfg.max_portfolio_risk_pct == 0.03
    assert cfg.reserve_capital_pct == 0.15
    assert cfg.max_leverage == 5.0
    assert cfg.min_trade_quantity == 1

    # Invalid risk per trade
    with pytest.raises(ValueError):
        CapitalAllocationConfig(risk_per_trade_pct=0.0)
    with pytest.raises(ValueError):
        CapitalAllocationConfig(risk_per_trade_pct=1.5)

    # Max portfolio risk < risk per trade
    with pytest.raises(ValueError):
        CapitalAllocationConfig(risk_per_trade_pct=0.02, max_portfolio_risk_pct=0.01)

    # Invalid reserve capital
    with pytest.raises(ValueError):
        CapitalAllocationConfig(reserve_capital_pct=-0.1)
    with pytest.raises(ValueError):
        CapitalAllocationConfig(reserve_capital_pct=1.0)

    # Invalid leverage
    with pytest.raises(ValueError):
        CapitalAllocationConfig(max_leverage=0)

    # Invalid min quantity
    with pytest.raises(ValueError):
        CapitalAllocationConfig(min_trade_quantity=0)


def test_trade_opportunity_auto_rr():
    """Verify reward_risk_ratio is auto-calculated when target_price is provided."""
    opp = TradeOpportunity(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_price=2500.0,
        stop_loss=2480.0,  # 20 risk
        target_price=2560.0,  # 60 reward
    )
    assert opp.reward_risk_ratio == pytest.approx(3.0)


# ============================================================================
# 2. SCENARIO 1: ₹50,000 CAPITAL WITH MULTIPLE ELIGIBLE OPPORTUNITIES
# ============================================================================

def test_scenario_01_multiple_eligible_opportunities():
    """
    Scenario 1: ₹50,000 capital with multiple eligible stock opportunities.
    Evaluates RELIANCE, ICICIBANK, and INFY.
    All should be accepted within available margin and portfolio risk limits.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0, reserve_capital_pct=0.15)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,         # ₹500 risk per trade
        max_portfolio_risk_pct=0.03,     # ₹1,500 total risk budget
        max_stock_allocation_pct=0.35,   # ₹87,500 max notional per stock
        reserve_capital_pct=0.15,        # ₹7,500 reserve -> ₹42,500 available margin
    ))

    opportunities = [
        TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0, signal_quality=0.9),  # 25 risk -> Q_risk = 500/25 = 20
        TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0, signal_quality=0.85), # 10 risk -> Q_risk = 500/10 = 50
        TradeOpportunity("INFY", Position.LONG, 1500.0, 1480.0, signal_quality=0.8),      # 20 risk -> Q_risk = 500/20 = 25
    ]

    decisions = allocator.allocate_batch(opportunities, pm)

    assert len(decisions) == 3
    for dec in decisions:
        assert dec.accepted is True
        assert dec.allocated_quantity > 0
        assert dec.estimated_risk <= 500.0

    # Total risk allocated across the 3 positions must not exceed 3% (₹1,500)
    total_risk = sum(d.estimated_risk for d in decisions)
    assert total_risk <= 1500.0
    assert total_risk > 1400.0


# ============================================================================
# 3. SCENARIO 2: ONE STOCK ATTEMPTING TO CONSUME EXCESSIVE CAPITAL
# ============================================================================

def test_scenario_02_per_stock_allocation_cap():
    """
    Scenario 2: One stock attempting to consume excessive capital.
    A stock with a very tight stop loss (e.g. ₹1 stop distance on ₹2500 stock)
    would have Q_risk = 500 / 1 = 500 shares = ₹1,250,000 notional.
    Per-stock allocation cap (35% of capacity = ₹87,500 notional) must strictly cap it.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,        # ₹500
        max_stock_allocation_pct=0.35,  # 50,000 * 5 * 0.35 = ₹87,500 max notional
    ))

    # Stop distance is only 1 point! Q_risk would be 500 shares.
    # But max stock notional is 87,500 / 2500 = 35 shares!
    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2499.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.allocated_quantity == 35  # Capped at 35 shares!
    assert dec.allocated_quantity * dec.entry_price <= 87_500.0
    assert dec.limiting_constraint == "STOCK_ALLOCATION_LIMIT"


# ============================================================================
# 4. SCENARIO 3: POSITIONS APPROACHING PORTFOLIO RISK LIMIT
# ============================================================================

def test_scenario_03_portfolio_risk_budget_exhaustion():
    """
    Scenario 3: Several simultaneous positions approaching the portfolio risk limit.
    1% risk per trade, 2% max portfolio risk.
    Trade 1 takes 1%, Trade 2 takes 1%. Trade 3 is rejected due to risk exhaustion.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,        # 1% = ₹500
        max_portfolio_risk_pct=0.02,    # 2% = ₹1,000 max total risk
    ))

    opp1 = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0, signal_quality=0.9)  # 20 sh * 25 = 500 risk
    opp2 = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0, signal_quality=0.8)  # 50 sh * 10 = 500 risk
    opp3 = TradeOpportunity("INFY", Position.LONG, 1500.0, 1480.0, signal_quality=0.7)      # 25 sh * 20 = 500 risk

    decisions = allocator.allocate_batch([opp1, opp2, opp3], pm)

    assert decisions[0].accepted is True
    assert decisions[0].estimated_risk <= 500.0

    assert decisions[1].accepted is True
    assert decisions[1].estimated_risk <= 500.0

    # Third trade rejected because portfolio risk budget (1000) is exhausted!
    assert decisions[2].accepted is False
    assert decisions[2].allocated_quantity == 0
    assert decisions[2].limiting_constraint == "PORTFOLIO_RISK_LIMIT"
    assert "risk budget exhausted" in decisions[2].rejection_reason.lower()


# ============================================================================
# 5. SCENARIO 4: RESERVE CAPITAL PREVENTING A TRADE
# ============================================================================

def test_scenario_04_reserve_capital_preservation():
    """
    Scenario 4: Reserve capital preventing an otherwise affordable trade.
    On ₹10,000 capital with 30% reserve capital (₹3,000 reserved), available margin is ₹7,000.
    At 5x leverage, maximum notional supported by available margin is ₹35,000.
    A trade requiring ₹40,000 notional (which would dip into the ₹3,000 reserve)
    must NOT be allowed to exceed available margin.
    """
    pm = PortfolioManager(
        initial_capital=10_000.0,
        max_leverage=5.0,
        reserve_capital_pct=0.30,  # ₹3,000 reserve -> Available margin ₹7,000
    )
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.05,        # ₹500 risk
        max_portfolio_risk_pct=0.10,    # ₹1,000 max portfolio risk
        max_stock_allocation_pct=1.0,   # Unconstrained stock cap to isolate reserve margin constraint
        reserve_capital_pct=0.30,
        max_leverage=5.0,
        min_trade_quantity=20,
    ))

    # Available margin is ₹7,000. Required margin for 20 shares @ 2500 is 50,000 / 5 = ₹10,000.
    # ₹10,000 > ₹7,000 available margin!
    opp = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0, requested_quantity=20)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is False
    assert dec.allocated_quantity == 0
    assert dec.limiting_constraint == "AVAILABLE_MARGIN"
    assert "Insufficient available margin" in dec.rejection_reason


# ============================================================================
# 6. SCENARIO 5: INSUFFICIENT AVAILABLE MARGIN
# ============================================================================

def test_scenario_05_insufficient_available_margin():
    """
    Scenario 5: Existing open positions consume most margin.
    A new opportunity requiring more margin than available is rejected.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0, reserve_capital_pct=0.0)
    # Open RELIANCE: 90 shares @ 2500 = ₹225,000 notional -> ₹45,000 margin encumbered!
    # Available margin is only ₹5,000.
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 90)
    assert pm.available_margin == pytest.approx(5_000.0)

    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        min_trade_quantity=20,
    ))

    # TCS requires: 20 shares * 3500 / 5 = ₹14,000 margin > ₹5,000 available margin
    opp = TradeOpportunity("TCS", Position.LONG, 3500.0, 3450.0, requested_quantity=20)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is False
    assert dec.allocated_quantity == 0
    assert dec.limiting_constraint == "AVAILABLE_MARGIN"


# ============================================================================
# 7. SCENARIO 6: DIFFERENT STOP-LOSS DISTANCES
# ============================================================================

def test_scenario_06_stop_loss_distance_sizing():
    """
    Scenario 6: Different stop-loss distances producing different quantities.
    Stock A: Stop distance 10 -> Q = floor(500 / 10) = 50.
    Stock B: Stop distance 50 -> Q = floor(500 / 50) = 10.
    Same rupee risk (₹500), but Stock A receives 5x the shares of Stock B.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        include_estimated_round_trip_costs_in_sizing=False,
    ))

    opp_a = TradeOpportunity("STOCK_A", Position.LONG, 1000.0, 990.0)   # dist = 10
    opp_b = TradeOpportunity("STOCK_B", Position.LONG, 1000.0, 950.0)   # dist = 50

    dec_a = allocator.evaluate_opportunity(opp_a, pm)
    dec_b = allocator.evaluate_opportunity(opp_b, pm)

    assert dec_a.allocated_quantity == 50
    assert dec_b.allocated_quantity == 10
    assert dec_a.allocated_quantity == 5 * dec_b.allocated_quantity
    assert dec_a.estimated_risk == pytest.approx(500.0)
    assert dec_b.estimated_risk == pytest.approx(500.0)


# ============================================================================
# 8. SCENARIO 7: HIGH-QUALITY VS LOWER-QUALITY OPPORTUNITY
# ============================================================================

def test_scenario_07_quality_based_priority():
    """
    Scenario 7: A high-quality opportunity competing with a lower-quality opportunity.
    Margin allows only 1 position.
    Candidate A has quality 0.95; Candidate B has quality 0.60.
    Candidate A is evaluated first and allocated; Candidate B is rejected due to margin exhaustion.
    """
    pm = PortfolioManager(initial_capital=10_000.0, max_leverage=5.0, reserve_capital_pct=0.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.10,        # ₹1,000 risk
        max_portfolio_risk_pct=0.20,    # ₹2,000 max portfolio risk
        max_stock_allocation_pct=1.0,   # Allow full capacity
        include_estimated_round_trip_costs_in_sizing=False,
    ))

    # Available margin = ₹10,000.
    # HIGH_Q: Entry 2500, Stop 2450 (50 risk) -> Q_risk = 1000 / 50 = 20 shares.
    # Required margin = 20 * 2500 / 5 = ₹10,000 margin (100% of available margin!).
    # LOW_Q: Entry 1000, Stop 990 (10 risk) -> Needs margin, but 0 margin remains.
    opp_high = TradeOpportunity("HIGH_Q", Position.LONG, 2500.0, 2450.0, signal_quality=0.95)
    opp_low = TradeOpportunity("LOW_Q", Position.LONG, 1000.0, 990.0, signal_quality=0.60)

    decisions = allocator.allocate_batch([opp_low, opp_high], pm)

    # HIGH_Q should be evaluated first despite appearing second in the list!
    assert decisions[0].symbol == "HIGH_Q"
    assert decisions[0].accepted is True
    assert decisions[0].allocated_quantity == 20
    assert decisions[0].remaining_available_margin == 0.0

    # LOW_Q should be rejected because remaining margin (0.0) is insufficient
    assert decisions[1].symbol == "LOW_Q"
    assert decisions[1].accepted is False
    assert decisions[1].limiting_constraint == "AVAILABLE_MARGIN"


# ============================================================================
# 9. SCENARIO 8: DETERMINISTIC TIE-BREAKING
# ============================================================================

def test_scenario_08_deterministic_tie_breaking():
    """
    Scenario 8: Two opportunities with identical scores producing deterministic ordering.
    RELIANCE and ICICIBANK have identical quality, R:R, and volume.
    Lexicographical tie-breaking ensures ICICIBANK comes before RELIANCE every time.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    opp1 = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2475.0, signal_quality=0.85, reward_risk_ratio=2.0)
    opp2 = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0, signal_quality=0.85, reward_risk_ratio=2.0)

    # Pass in both orders
    ranked1 = allocator.rank_opportunities([opp1, opp2])
    ranked2 = allocator.rank_opportunities([opp2, opp1])

    # Both must place ICICIBANK first because 'ICICIBANK' < 'RELIANCE'
    assert ranked1[0].symbol == "ICICIBANK"
    assert ranked1[1].symbol == "RELIANCE"
    assert ranked2[0].symbol == "ICICIBANK"
    assert ranked2[1].symbol == "RELIANCE"


# ============================================================================
# 10. SCENARIO 9: INVALID PRICES & STOP-LOSS INPUTS
# ============================================================================

def test_scenario_09_invalid_price_and_stop_inputs():
    """
    Scenario 9: Invalid prices and invalid stop-loss inputs.
    Verifies graceful rejection with clear reasons:
    - Zero/negative entry price.
    - Zero/negative stop loss.
    - Stop loss >= entry price for LONG.
    - Stop loss <= entry price for SHORT.
    - Zero stop distance.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    # 1. Negative entry price
    opp_neg_entry = TradeOpportunity("RELIANCE", Position.LONG, -2500.0, 2400.0)
    dec = allocator.evaluate_opportunity(opp_neg_entry, pm)
    assert dec.accepted is False
    assert "Invalid entry price" in dec.rejection_reason

    # 2. Stop loss on wrong side for LONG (stop >= entry)
    opp_wrong_long = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2550.0)
    dec = allocator.evaluate_opportunity(opp_wrong_long, pm)
    assert dec.accepted is False
    assert "Invalid stop loss for LONG" in dec.rejection_reason

    # 3. Stop loss on wrong side for SHORT (stop <= entry)
    opp_wrong_short = TradeOpportunity("RELIANCE", Position.SHORT, 2500.0, 2450.0)
    dec = allocator.evaluate_opportunity(opp_wrong_short, pm)
    assert dec.accepted is False
    assert "Invalid stop loss for SHORT" in dec.rejection_reason

    # 4. Zero stop distance
    opp_zero_dist = TradeOpportunity("RELIANCE", Position.LONG, 2500.0, 2500.0)
    dec = allocator.evaluate_opportunity(opp_zero_dist, pm)
    assert dec.accepted is False
    assert "Invalid stop loss" in dec.rejection_reason or "cannot be zero" in dec.rejection_reason


# ============================================================================
# 11. SCENARIO 10: EXISTING UNREALIZED LOSSES REDUCING CAPACITY
# ============================================================================

def test_scenario_10_unrealized_losses_reduce_capacity():
    """
    Scenario 10: Existing unrealized losses reducing available capacity.
    Account starts at ₹50,000. An open position suffers -₹5,000 MTM unrealized loss.
    Current equity is ₹45,000.
    Risk budget must be 1% of ₹45,000 = ₹450 (NOT 1% of ₹50,000 = ₹500).
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 10)  # margin = 5000
    pm.update_price("RELIANCE", 2000.0)  # -500/sh * 10 = -5000 unrealized loss!

    assert pm.equity == pytest.approx(45_000.0)

    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        include_estimated_round_trip_costs_in_sizing=False,
    ))
    opp = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0)  # 10 stop dist
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    # Risk budget must be 1% of 45,000 = 450
    assert dec.risk_budget == pytest.approx(450.0)
    # Quantity = floor(450 / 10) = 45 shares (NOT 50 shares)
    assert dec.allocated_quantity == 45


# ============================================================================
# 12. SCENARIO 11: EXISTING MARGIN ENCUMBRANCE
# ============================================================================

def test_scenario_11_existing_margin_encumbrance_limits_allocations():
    """
    Scenario 11: Existing margin encumbrance limiting additional allocations.
    ₹50,000 initial capital.
    Position 1 encumbers ₹35,000 margin.
    Available margin is only ₹15,000 (at 5x leverage, ₹75,000 notional max).
    Candidate requiring ₹100,000 notional cannot exceed ₹75,000.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0, reserve_capital_pct=0.0)
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 70)  # 70 * 2500 / 5 = 35,000 margin
    assert pm.allocated_margin == pytest.approx(35_000.0)
    assert pm.available_margin == pytest.approx(15_000.0)

    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.05,        # ₹2500 risk
        max_portfolio_risk_pct=0.10,    # ₹5000 max portfolio risk
    ))

    # Entry 1000, stop 980 -> 20 dist -> Q_risk = 2500 / 20 = 125 shares (₹125,000 notional)
    # But available margin is 15,000 -> supports at most 15,000 * 5 / 1000 = 75 shares!
    opp = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 980.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.allocated_quantity == 75  # Capped by available margin!
    assert dec.limiting_constraint == "AVAILABLE_MARGIN"


# ============================================================================
# 13. SCENARIO 12: PROTECTION FLOOR OR BANKRUPTCY REJECTING ENTRIES
# ============================================================================

def test_scenario_12_protection_floor_rejects_entries():
    """
    Scenario 12: A portfolio protection-floor or bankruptcy state rejecting new entries.
    When portfolio equity drops below floor, allocator immediately rejects all candidates.
    """
    pm = PortfolioManager(
        initial_capital=50_000.0,
        capital_protection_floor=45_000.0,
        max_leverage=5.0,
    )
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 20)
    pm.update_price("RELIANCE", 2200.0)  # -6000 loss -> Equity = 44,000 < 45,000 floor
    assert pm.is_bankrupt is True

    allocator = CapitalAllocator()
    opp = TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is False
    assert dec.allocated_quantity == 0
    assert "bankrupt" in dec.rejection_reason.lower()


# ============================================================================
# 14. SCENARIO 13: PARTIALLY FUNDED ALLOCATION
# ============================================================================

def test_scenario_13_partially_funded_allocation():
    """
    Scenario 13: A partially funded allocation where quantity is reduced
    rather than incorrectly exceeding limits.
    Candidate requests 100 shares, but risk budget only permits 40 shares.
    Quantity is safely scaled down to 40 shares and accepted.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        include_estimated_round_trip_costs_in_sizing=False,
    ))  # ₹500 risk

    # Stop distance is 12.5 -> Q_risk = 500 / 12.5 = 40 shares
    opp = TradeOpportunity("INFY", Position.LONG, 1500.0, 1487.5, requested_quantity=100)
    dec = allocator.evaluate_opportunity(opp, pm)

    assert dec.accepted is True
    assert dec.requested_quantity == 100
    assert dec.allocated_quantity == 40
    assert dec.limiting_constraint == "RISK_BUDGET"


# ============================================================================
# 15. SCENARIO 14: ZERO ELIGIBLE OPPORTUNITIES
# ============================================================================

def test_scenario_14_zero_eligible_opportunities():
    """
    Scenario 14: Zero eligible opportunities resulting in no allocation.
    Evaluates:
    - Empty candidate list.
    - List of untradeable/halted candidates.
    """
    pm = PortfolioManager(initial_capital=50_000.0)
    allocator = CapitalAllocator()

    # Empty list
    empty_res = allocator.allocate_batch([], pm)
    assert empty_res == []

    # Untradeable candidates
    opp1 = TradeOpportunity("CIRCUIT_STOCK", Position.LONG, 100.0, 95.0, is_tradeable=False)
    opp2 = TradeOpportunity("HALTED_STOCK", Position.LONG, 200.0, 190.0, is_tradeable=False)
    decisions = allocator.allocate_batch([opp1, opp2], pm)

    assert len(decisions) == 2
    for d in decisions:
        assert d.accepted is False
        assert d.allocated_quantity == 0
        assert "not tradeable" in d.rejection_reason.lower()


# ============================================================================
# 16. PURITY INVARIANT: EVALUATION DOES NOT MUTATE PORTFOLIO
# ============================================================================

def test_allocator_purity_invariant():
    """
    Verify that evaluating opportunities does NOT mutate the PortfolioManager state.
    """
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 10)

    # Snapshot initial state
    initial_cash = pm.cash
    initial_equity = pm.equity
    initial_positions_count = pm.open_position_count
    initial_trades_count = pm.trade_count
    initial_allocated_margin = pm.allocated_margin

    allocator = CapitalAllocator()
    opportunities = [
        TradeOpportunity("ICICIBANK", Position.LONG, 1000.0, 990.0),
        TradeOpportunity("INFY", Position.LONG, 1500.0, 1480.0),
        TradeOpportunity("TCS", Position.LONG, 3500.0, 3450.0),
    ]

    # Evaluate multiple times
    dec1 = allocator.evaluate_opportunity(opportunities[0], pm)
    dec_batch = allocator.allocate_batch(opportunities, pm)

    # Assert state is 100% unchanged
    assert pm.cash == initial_cash
    assert pm.equity == initial_equity
    assert pm.open_position_count == initial_positions_count
    assert pm.trade_count == initial_trades_count
    assert pm.allocated_margin == initial_allocated_margin
    assert "ICICIBANK" not in pm.open_positions
    assert "INFY" not in pm.open_positions
    assert "TCS" not in pm.open_positions


# ============================================================================
# 17. CONSERVATIVE COST BUFFER SIZING TEST
# ============================================================================

def test_conservative_cost_buffer_in_sizing():
    """
    Verify conservative_cost_buffer_rate reduces quantity to account for transaction costs.
    Without buffer: entry 1000, stop 990 -> dist = 10 -> Q = 500 / 10 = 50.
    With buffer (0.001 = 10 bps): cost buffer = 1000 * 0.001 = 1.0.
    Effective risk per share = 10 + 1 = 11.
    Quantity = floor(500 / 11) = 45 shares.
    """
    pm = PortfolioManager(initial_capital=50_000.0)

    # Without cost buffer (legacy mode to isolate buffer)
    alloc_raw = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        conservative_cost_buffer_rate=0.0,
        include_estimated_round_trip_costs_in_sizing=False,
    ))
    opp = TradeOpportunity("STOCK", Position.LONG, 1000.0, 990.0)
    dec_raw = alloc_raw.evaluate_opportunity(opp, pm)
    assert dec_raw.allocated_quantity == 50

    # With cost buffer (10 bps = 1.0 rupee per share)
    alloc_buffered = CapitalAllocator(CapitalAllocationConfig(
        risk_per_trade_pct=0.01,
        conservative_cost_buffer_rate=0.001,
        include_estimated_round_trip_costs_in_sizing=False,
    ))
    dec_buffered = alloc_buffered.evaluate_opportunity(opp, pm)
    assert dec_buffered.allocated_quantity == 45
    assert dec_buffered.allocated_quantity < dec_raw.allocated_quantity

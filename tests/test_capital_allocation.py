"""
Unit and integration tests for user-selectable capital allocation in SignalForge.

Tests cover:
1. Never using full account balance when a smaller allocation is selected (ring-fencing).
2. Integer share quantity enforcement (math.floor).
3. Rejection of trades exceeding allocated capital.
4. Independent performance tracking across concurrent allocations.
5. Telemetry display summary (selected capital, available cash, invested amount, realized/unrealized P&L, total returns).
6. Testing presets (₹10K, ₹25K, ₹50K, ₹1L, ₹2L) and custom capital allocations.
7. Critical example: ₹30,000 account balance with ₹10,000 SignalForge allocation.
8. REST API endpoints via TestClient.
"""

import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.capital_allocation import (
    PRESET_CAPITAL_ALLOCATIONS,
    PRESET_LABELS,
    AllocationType,
    CapitalAllocation,
    CapitalAllocationManager,
)
from src.api.routes.capital_allocation import router as capital_allocation_router


# -----------------------------------------------------------------------------
# 1. Preset & Custom Allocation Initialization Tests
# -----------------------------------------------------------------------------

def test_preset_capital_allocations_constants():
    """Verify standard preset definitions."""
    expected_presets = [10_000.0, 25_000.0, 50_000.0, 100_000.0, 200_000.0]
    assert PRESET_CAPITAL_ALLOCATIONS == expected_presets
    for p in expected_presets:
        assert p in PRESET_LABELS
        assert "₹" in PRESET_LABELS[p]


@pytest.mark.parametrize("preset_cap", [10_000.0, 25_000.0, 50_000.0, 100_000.0, 200_000.0])
def test_all_preset_allocations(preset_cap):
    """Verify all 5 standard presets can be initialized cleanly."""
    alloc = CapitalAllocation(
        allocation_id=f"alloc_preset_{int(preset_cap)}",
        total_account_balance=preset_cap * 2,  # Account has 2x funds
        allocated_capital=preset_cap,
    )
    expected_type = {
        10_000.0: AllocationType.PRESET_10K,
        25_000.0: AllocationType.PRESET_25K,
        50_000.0: AllocationType.PRESET_50K,
        100_000.0: AllocationType.PRESET_1L,
        200_000.0: AllocationType.PRESET_2L,
    }[preset_cap]
    assert alloc.allocation_type == expected_type
    assert alloc.allocated_capital == preset_cap
    assert alloc.available_cash == preset_cap
    assert alloc.ring_fenced_cash == preset_cap
    assert alloc.invested_amount == 0.0
    assert alloc.total_equity == preset_cap
    assert alloc.total_returns_pct == 0.0


def test_custom_capital_allocation():
    """Verify custom capital allocation works with arbitrary amounts."""
    alloc = CapitalAllocation(
        allocation_id="alloc_custom_75k",
        total_account_balance=150_000.0,
        allocated_capital=75_000.0,
        notes="Custom discretionary pool",
    )
    assert alloc.allocation_type == AllocationType.CUSTOM
    assert alloc.allocated_capital == 75_000.0
    assert alloc.ring_fenced_cash == 75_000.0
    assert alloc.available_cash == 75_000.0


def test_allocation_validation_errors():
    """Verify zero/negative amounts or allocations exceeding account balance are rejected."""
    with pytest.raises(ValueError, match="positive and finite"):
        CapitalAllocation(
            allocation_id="err1",
            total_account_balance=10_000.0,
            allocated_capital=0.0,
        )

    with pytest.raises(ValueError, match="positive and finite"):
        CapitalAllocation(
            allocation_id="err2",
            total_account_balance=10_000.0,
            allocated_capital=-500.0,
        )

    with pytest.raises(ValueError, match="cannot exceed total account balance"):
        CapitalAllocation(
            allocation_id="err3",
            total_account_balance=30_000.0,
            allocated_capital=50_000.0,
        )


# -----------------------------------------------------------------------------
# 2. Critical User Example: ₹30,000 Account / ₹10,000 SignalForge Allocation
# -----------------------------------------------------------------------------

def test_critical_example_ring_fencing_and_rejection():
    """
    CRITICAL USER REQUIREMENT:
    If total account balance is ₹30,000 but user selects ₹10,000 capital,
    the strategy must use ONLY ₹10,000.
    Ring-fenced ₹20,000 must remain completely untouched.
    Trades exceeding ₹10,000 must be rejected.
    """
    alloc = CapitalAllocation(
        allocation_id="user_session_30k_10k",
        total_account_balance=30_000.0,
        allocated_capital=10_000.0,
    )

    # 1. Verify ring-fenced state
    assert alloc.allocated_capital == 10_000.0
    assert alloc.total_account_balance == 30_000.0
    assert alloc.ring_fenced_cash == 20_000.0
    assert alloc.available_cash == 10_000.0
    assert alloc.total_equity == 10_000.0

    # 2. Position sizing calculation must base on ₹10,000, NOT ₹30,000
    # Risk 1% of ₹10,000 = ₹100.
    # Entry = ₹2,500, Stop = ₹2,450 (Risk per share = ₹50).
    # Shares by risk = 100 / 50 = 2 shares.
    # If it had used ₹30,000, risk would be ₹300 -> 6 shares.
    shares = alloc.calculate_position_size(
        entry_price=2500.0,
        stop_loss=2450.0,
        risk_fraction=0.01,
        max_notional_pct=0.50,
    )
    assert shares == 2
    assert isinstance(shares, int)

    # 3. Attempt trade that exceeds allocated capital (e.g. 5 shares @ ₹2,500 = ₹12,500)
    # Even though account balance has ₹30,000, allocation has only ₹10,000!
    valid, reason = alloc.validate_trade(symbol="RELIANCE", quantity=5, price=2500.0)
    assert not valid
    assert "exceeds available allocated cash" in reason

    # Attempting to execute it must raise ValueError
    with pytest.raises(ValueError, match="exceeds available allocated cash"):
        alloc.execute_trade(
            trade_id="tr_oversized",
            symbol="RELIANCE",
            quantity=5,
            price=2500.0,
            stop_loss=2450.0,
            statutory_costs=3.5,
        )

    # Cash and ring-fenced funds must remain completely unchanged
    assert alloc.available_cash == 10_000.0
    assert alloc.ring_fenced_cash == 20_000.0
    assert alloc.invested_amount == 0.0

    # 4. Execute valid trade within ₹10,000 (2 shares @ ₹2,500 = ₹5,000)
    trade = alloc.execute_trade(
        trade_id="tr_valid_01",
        symbol="RELIANCE",
        quantity=2,
        price=2500.0,
        stop_loss=2450.0,
        statutory_costs=1.54,
    )
    assert trade.quantity == 2
    assert alloc.available_cash == pytest.approx(10_000.0 - 5000.0 - 1.54)
    assert alloc.invested_amount == 5000.0
    # Ring-fenced cash in user account is strictly untouched:
    assert alloc.ring_fenced_cash == 20_000.0

    # 5. Mark to market update
    alloc.update_market_price("RELIANCE", 2600.0)
    summary = alloc.get_display_summary()
    assert summary["unrealized_pnl"] == 200.0  # 2 shares * (2600 - 2500)
    assert summary["ring_fenced_cash"] == 20_000.0
    assert summary["selected_capital"] == 10_000.0

    # 6. Close trade with profit
    closed = alloc.close_trade(
        trade_id="tr_valid_01",
        exit_price=2600.0,
        exit_costs=1.54,
    )
    # Gross profit: 2 * 100 = 200. Total costs = 1.54 + 1.54 = 3.08. Net profit = 196.92
    assert closed.net_pnl == pytest.approx(196.92)
    assert alloc.invested_amount == 0.0
    assert alloc.available_cash == pytest.approx(10_196.92)
    assert alloc.total_equity == pytest.approx(10_196.92)
    # Total return % is computed strictly off ₹10,000:
    assert alloc.total_returns_pct == pytest.approx(1.9692, rel=1e-3)
    # Ring-fenced cash remains ₹20,000:
    assert alloc.ring_fenced_cash == 20_000.0


# -----------------------------------------------------------------------------
# 3. Integer Share Quantity Enforcement
# -----------------------------------------------------------------------------

def test_integer_share_quantity_enforcement():
    """Verify shares are strictly mathematical floor integers under all conditions."""
    alloc = CapitalAllocation(
        allocation_id="alloc_shares_test",
        total_account_balance=50_000.0,
        allocated_capital=25_000.0,
    )

    # Example 1: 1% of ₹25,000 = ₹250.
    # Risk per share = ₹19.50.
    # 250 / 19.50 = 12.8205 shares -> with 100% notional cap, floors to exactly 12.
    shares1 = alloc.calculate_position_size(
        entry_price=1250.0,
        stop_loss=1230.50,
        risk_fraction=0.01,
        max_notional_pct=1.0,
    )
    assert isinstance(shares1, int)
    assert shares1 == 12

    # Under standard default notional cap of 35% (35% of ₹25k = ₹8,750 / ₹1,250 = 7 shares):
    shares1_capped = alloc.calculate_position_size(
        entry_price=1250.0,
        stop_loss=1230.50,
        risk_fraction=0.01,
    )
    assert isinstance(shares1_capped, int)
    assert shares1_capped == 7

    # Example 2: High priced share (e.g. ₹3,450) where risk would allow fractional
    # 1% risk = ₹250. Stop = ₹3,410 (risk ₹40). 250 / 40 = 6.25 shares -> 6
    shares2 = alloc.calculate_position_size(
        entry_price=3450.0,
        stop_loss=3410.0,
        risk_fraction=0.01,
        max_notional_pct=1.0,
    )
    assert isinstance(shares2, int)
    assert shares2 == 6

    # Example 3: Small capital where calculated shares < 1.0 -> must be 0
    small_alloc = CapitalAllocation(
        allocation_id="alloc_small",
        total_account_balance=10_000.0,
        allocated_capital=10_000.0,
    )
    # 1% risk = ₹100. Stop difference = ₹150. 100 / 150 = 0.666 -> 0 shares
    shares3 = small_alloc.calculate_position_size(
        entry_price=2500.0,
        stop_loss=2350.0,
        risk_fraction=0.01,
    )
    assert isinstance(shares3, int)
    assert shares3 == 0

    # Execute trade with integer quantity rejected if 0 or negative
    with pytest.raises(ValueError, match="Quantity must be a positive integer"):
        small_alloc.execute_trade(
            trade_id="tr_zero",
            symbol="INFY",
            quantity=0,
            price=1500.0,
        )


# -----------------------------------------------------------------------------
# 4. Rejection of Trades Exceeding Allocated Capital
# -----------------------------------------------------------------------------

def test_trade_rejection_when_exceeding_allocated_cash():
    """Verify that orders exceeding available cash within the allocation are safely rejected."""
    alloc = CapitalAllocation(
        allocation_id="alloc_rejection_test",
        total_account_balance=100_000.0,  # Account has 10x cash
        allocated_capital=10_000.0,
    )

    # 1. Available cash is ₹10,000. An order of ₹10,500 must fail validation
    valid, reason = alloc.validate_trade(symbol="TCS", quantity=3, price=3500.0)
    assert not valid
    assert "exceeds available allocated cash" in reason

    # 2. Execute trade for ₹7,000 (2 shares @ ₹3,500)
    alloc.execute_trade(
        trade_id="tr_tcs_1",
        symbol="TCS",
        quantity=2,
        price=3500.0,
        statutory_costs=2.1,
    )
    # Remaining cash ~₹2,997.90
    assert alloc.available_cash < 3000.0

    # 3. Second order for 1 share @ ₹3,500 in INFY must now be rejected because cash is insufficient
    valid2, reason2 = alloc.validate_trade(symbol="INFY", quantity=1, price=3500.0)
    assert not valid2
    assert "exceeds available allocated cash" in reason2


# -----------------------------------------------------------------------------
# 5. Independent Multi-Allocation Performance Tracking
# -----------------------------------------------------------------------------

def test_independent_allocation_isolation():
    """
    Verify multiple allocations (e.g. ₹10K, ₹50K, ₹1L) maintain completely
    isolated balances, trades, drawdowns, and returns.
    """
    mgr = CapitalAllocationManager()

    alloc10k = mgr.create_allocation(
        allocation_id="session_10k",
        total_account_balance=200_000.0,
        allocated_capital=10_000.0,
    )
    alloc50k = mgr.create_allocation(
        allocation_id="session_50k",
        total_account_balance=200_000.0,
        allocated_capital=50_000.0,
    )
    alloc100k = mgr.create_allocation(
        allocation_id="session_100k",
        total_account_balance=200_000.0,
        allocated_capital=100_000.0,
    )

    # Execute trade ONLY on 10k allocation
    alloc10k.execute_trade("tr1", "RELIANCE", 2, 2500.0, statutory_costs=1.5)
    alloc10k.close_trade(trade_id="tr1", exit_price=2600.0, exit_costs=1.5)

    # Verify 10k allocation reflects profit
    assert alloc10k.realized_pnl == pytest.approx(197.0)
    assert alloc10k.closed_trades_count == 1
    assert alloc10k.total_returns_pct > 1.9

    # Verify 50k and 100k allocations are completely untouched
    assert alloc50k.realized_pnl == 0.0
    assert alloc50k.closed_trades_count == 0
    assert alloc50k.available_cash == 50_000.0
    assert alloc50k.total_returns_pct == 0.0

    assert alloc100k.realized_pnl == 0.0
    assert alloc100k.closed_trades_count == 0
    assert alloc100k.available_cash == 100_000.0
    assert alloc100k.total_returns_pct == 0.0

    # Check manager list
    summaries = mgr.get_all_summaries()
    assert len(summaries) == 3
    ids = [s["allocation_id"] for s in summaries]
    assert "session_10k" in ids
    assert "session_50k" in ids
    assert "session_100k" in ids


# -----------------------------------------------------------------------------
# 6. Display Summary Requirement Verification
# -----------------------------------------------------------------------------

def test_telemetry_display_summary_fields():
    """
    Requirement 5:
    Display selected capital, available cash, invested amount, realized/unrealized P&L and total returns.
    """
    alloc = CapitalAllocation(
        allocation_id="alloc_disp_test",
        total_account_balance=80_000.0,
        allocated_capital=50_000.0,
    )

    # Execute a trade and keep it open
    alloc.execute_trade("tr_open_1", "INFY", 20, 1500.0, statutory_costs=4.5)
    alloc.update_market_price("INFY", 1550.0)

    summary = alloc.get_display_summary()

    # Verify all required keys are present with correct semantic values
    assert summary["selected_capital"] == 50_000.0
    assert summary["total_account_balance"] == 80_000.0
    assert summary["ring_fenced_cash"] == 30_000.0
    assert summary["invested_amount"] == 30_000.0  # 20 * 1500
    assert summary["available_cash"] == pytest.approx(50_000.0 - 30_000.0 - 4.5)
    assert summary["unrealized_pnl"] == 1000.0  # 20 * (1550 - 1500)
    assert summary["realized_pnl"] == 0.0
    assert summary["total_returns_amount"] == pytest.approx(1000.0 - 4.5)
    assert summary["open_positions_count"] == 1


# -----------------------------------------------------------------------------
# 7. FastAPI Route Functions & Model Validation Testing
# -----------------------------------------------------------------------------

def test_fastapi_capital_allocation_endpoints():
    """Verify FastAPI route handlers and request/response models directly."""
    from src.api.routes.capital_allocation import (
        get_presets,
        create_allocation,
        get_allocation_status,
        calculate_size,
        validate_trade,
        execute_trade,
        close_trade,
        list_allocations,
        AllocateCapitalRequest,
        PositionSizeRequest,
        ValidateTradeRequest,
        ExecuteTradeRequest,
        CloseTradeRequest,
    )

    # 1. Presets endpoint
    presets_data = get_presets()
    assert len(presets_data.presets) == 5
    assert presets_data.presets[0] == 10_000.0
    assert presets_data.presets[4] == 200_000.0
    assert "₹10,000" in presets_data.labels["10000.0"]

    # 2. Create allocation (Critical example: ₹30k account / ₹10k allocation)
    alloc_req = AllocateCapitalRequest(
        allocation_id="api_test_alloc_30k_10k",
        total_account_balance=30_000.0,
        allocated_capital=10_000.0,
        account_id="user_acct_01",
    )
    created = create_allocation(alloc_req)
    assert created["selected_capital"] == 10_000.0
    assert created["ring_fenced_cash"] == 20_000.0
    assert created["available_cash"] == 10_000.0
    assert created["unallocated_cash"] == 20_000.0

    # 3. Calculate position size
    size_req = PositionSizeRequest(
        entry_price=2500.0,
        stop_loss=2450.0,
        risk_pct=0.01,
        max_allocation_pct=0.5,
    )
    size_res = calculate_size("api_test_alloc_30k_10k", size_req)
    assert size_res["recommended_shares"] == 2
    assert isinstance(size_res["recommended_shares"], int)

    # 4. Validate trade - oversized trade rejection
    val_oversized_req = ValidateTradeRequest(symbol="RELIANCE", entry_price=2500.0, quantity=10)
    val_oversized = validate_trade("api_test_alloc_30k_10k", val_oversized_req)
    assert val_oversized["approved"] is False
    assert "exceeds available allocated cash" in val_oversized["message"]

    # 5. Execute valid trade
    exec_req = ExecuteTradeRequest(
        trade_id="api_tr_01",
        symbol="RELIANCE",
        side="BUY",
        quantity=2,
        entry_price=2500.0,
        entry_costs=1.5,
        stop_loss=2450.0,
    )
    exec_res = execute_trade("api_test_alloc_30k_10k", exec_req)
    assert exec_res["status"] == "EXECUTED"
    assert exec_res["trade"]["quantity"] == 2
    assert exec_res["allocation_summary"]["invested_amount"] == 5000.0

    # 6. Close trade
    close_req = CloseTradeRequest(
        symbol="RELIANCE",
        exit_price=2600.0,
        exit_costs=1.5,
    )
    close_res = close_trade("api_test_alloc_30k_10k", close_req)
    assert close_res["status"] == "CLOSED"
    assert close_res["trade"]["net_pnl"] == pytest.approx(197.0)
    assert close_res["allocation_summary"]["ring_fenced_cash"] == 20_000.0

    # 7. Query allocation details
    get_res = get_allocation_status("api_test_alloc_30k_10k")
    assert get_res["realized_pnl"] == pytest.approx(197.0)
    assert get_res["closed_trades_count"] == 1
    assert get_res["ring_fenced_cash"] == 20_000.0

    # 8. List allocations
    all_allocs = list_allocations()
    assert any(a["allocation_id"] == "api_test_alloc_30k_10k" for a in all_allocs)

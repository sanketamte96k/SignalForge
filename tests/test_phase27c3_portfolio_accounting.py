"""
Phase 27C.3.1: Core Portfolio Accounting Synthetic Regression Test Suite.

Verifies:
1. Symbol attribution and backward compatibility of Trade and simulate_trade.
2. PortfolioManager initialization with configurable starting capital (₹10k, ₹50k, ₹100k).
3. Multi-position simultaneous accounting across distinct equity symbols.
4. Margin encumbrance vs cash preservation on position entry.
5. Duplicate position prevention on identical symbol.
6. Mark-to-market unrealized P&L and dynamic portfolio equity calculation.
7. Peak equity and MTM drawdown tracking across simultaneous open positions.
8. Independent position closure, margin release, and single-point transaction cost deduction.
9. Margin exhaustion and maximum stock allocation limits.
10. Capital protection floor and bankruptcy enforcement.
11. Clean reset and backward compatibility with Portfolio.
"""

from __future__ import annotations

import pytest
import pandas as pd

from src.backtest.simulator import Position, Trade, simulate_trade
from src.backtest.portfolio import (
    Portfolio,
    PortfolioManager,
    OpenPosition,
    DuplicatePositionError,
    InsufficientMarginError,
    PositionNotFoundError,
    AllocationExceededError,
    PortfolioBankruptError,
)
from src.backtest.indian_market_costs import (
    IntradayCostConfig,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    ZERO_COST_CONFIG,
)


# ============================================================================
# 1. TRADE MODEL & SYMBOL ATTRIBUTION
# ============================================================================

def test_trade_symbol_attribution_default():
    """Verify default symbol is 'NIFTY 50' for 100% backward compatibility."""
    trade = Trade(
        entry_time="2026-08-25 09:15:00",
        exit_time="2026-08-25 09:30:00",
        position=Position.LONG,
        entry_price=100.0,
        exit_price=110.0,
        quantity=1.0,
        gross_pnl=10.0,
        transaction_cost=0.5,
        net_pnl=9.5,
        return_pct=9.5,
    )
    assert trade.symbol == "NIFTY 50"
    assert trade.exit_reason == "SIGNAL"


def test_trade_symbol_attribution_custom():
    """Verify custom stock symbol attribution on Trade."""
    trade = Trade(
        entry_time="2026-08-25 09:15:00",
        exit_time="2026-08-25 09:30:00",
        position=Position.LONG,
        entry_price=2500.0,
        exit_price=2550.0,
        quantity=10.0,
        gross_pnl=500.0,
        transaction_cost=25.0,
        net_pnl=475.0,
        return_pct=1.9,
        symbol="RELIANCE",
        exit_reason="TP",
    )
    assert trade.symbol == "RELIANCE"
    assert trade.exit_reason == "TP"


def test_simulate_trade_passes_symbol():
    """Verify simulate_trade accepts symbol parameter and populates Trade.symbol."""
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=1000.0,
        exit_price=1020.0,
        quantity=5,
        symbol="ICICIBANK",
    )
    assert trade.symbol == "ICICIBANK"
    assert trade.gross_pnl == pytest.approx(100.0)


# ============================================================================
# 2. CONFIGURABLE PORTFOLIO INITIALIZATION (₹10k, ₹50k, ₹100k)
# ============================================================================

@pytest.mark.parametrize("initial_capital", [10_000.0, 50_000.0, 100_000.0])
def test_portfolio_manager_initialization_configurable(initial_capital: float):
    """Verify PortfolioManager initializes cleanly across various capital levels."""
    pm = PortfolioManager(
        initial_capital=initial_capital,
        max_leverage=5.0,
        reserve_capital_pct=0.10,
        reserve_capital_fixed=1_000.0,
        capital_protection_floor=initial_capital * 0.80,
    )

    assert pm.initial_capital == initial_capital
    assert pm.cash == initial_capital
    assert pm.equity == initial_capital
    assert pm.peak_equity == initial_capital
    assert pm.max_drawdown == 0.0
    assert pm.is_bankrupt is False
    assert pm.open_position_count == 0
    assert pm.trade_count == 0
    assert pm.total_pnl == 0.0
    assert pm.total_return_pct == 0.0
    assert pm.unrealized_pnl == 0.0
    assert pm.allocated_margin == 0.0

    # Reserved capital: max(1000, initial_capital * 0.10)
    expected_reserve = max(1000.0, initial_capital * 0.10)
    assert pm.reserved_capital == pytest.approx(expected_reserve)

    # Available margin: initial_capital - reserved_capital
    assert pm.available_margin == pytest.approx(initial_capital - expected_reserve)


def test_portfolio_manager_invalid_arguments():
    """Verify strict type and boundary validation on PortfolioManager initialization."""
    with pytest.raises(TypeError):
        PortfolioManager(initial_capital="50000")
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=0)
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=-10000)
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=50000, max_leverage=0)
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=50000, reserve_capital_pct=1.5)
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=50000, reserve_capital_fixed=-100)
    with pytest.raises(ValueError):
        PortfolioManager(initial_capital=50000, max_stock_allocation_pct=0.0)


# ============================================================================
# 3. MULTI-STOCK POSITION ACCOUNTING & MARGIN ENCUMBRANCE
# ============================================================================

def test_multi_position_simultaneous_accounting():
    """
    Test opening 2 simultaneous positions (RELIANCE and ICICIBANK) on a ₹50,000 account.
    Verify margin encumbrance, cash preservation, and available margin reduction.
    """
    pm = PortfolioManager(
        initial_capital=50_000.0,
        max_leverage=5.0,
        reserve_capital_pct=0.0,  # 0 reserve for clear math
    )

    # Position 1: RELIANCE 20 shares @ ₹2,500 = ₹50,000 notional
    # Required margin at 5x leverage = ₹50,000 / 5 = ₹10,000
    pos1 = pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="2026-08-25 09:15:00",
        entry_price=2500.0,
        quantity=20,
    )

    assert pos1.symbol == "RELIANCE"
    assert pos1.allocated_margin == pytest.approx(10_000.0)
    assert pos1.notional_value == pytest.approx(50_000.0)

    # Crucial accounting rule: Margin is an encumbrance, NOT an expense!
    # Realized cash must remain exactly ₹50,000.
    assert pm.cash == pytest.approx(50_000.0)
    assert pm.allocated_margin == pytest.approx(10_000.0)
    assert pm.available_margin == pytest.approx(40_000.0)
    assert pm.equity == pytest.approx(50_000.0)
    assert pm.open_position_count == 1

    # Position 2: ICICIBANK 50 shares @ ₹1,000 = ₹50,000 notional
    # Required margin at 5x leverage = ₹50,000 / 5 = ₹10,000
    pos2 = pm.open_position(
        symbol="ICICIBANK",
        side=Position.SHORT,
        entry_time="2026-08-25 09:20:00",
        entry_price=1000.0,
        quantity=50,
    )

    assert pos2.symbol == "ICICIBANK"
    assert pos2.allocated_margin == pytest.approx(10_000.0)
    assert pos2.notional_value == pytest.approx(50_000.0)

    # Total allocated margin = ₹20,000. Cash remains ₹50,000. Available margin = ₹30,000.
    assert pm.cash == pytest.approx(50_000.0)
    assert pm.allocated_margin == pytest.approx(20_000.0)
    assert pm.available_margin == pytest.approx(30_000.0)
    assert pm.equity == pytest.approx(50_000.0)
    assert pm.open_position_count == 2
    assert "RELIANCE" in pm.open_positions
    assert "ICICIBANK" in pm.open_positions


def test_duplicate_position_prevention():
    """Verify attempting to open a duplicate active position on the same symbol is rejected."""
    pm = PortfolioManager(initial_capital=50_000.0)

    pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=2500.0,
        quantity=10,
    )

    # Attempt second position on RELIANCE
    with pytest.raises(DuplicatePositionError) as exc_info:
        pm.open_position(
            symbol="RELIANCE",
            side=Position.SHORT,
            entry_time="09:25",
            entry_price=2520.0,
            quantity=5,
        )
    assert "Duplicate active position" in str(exc_info.value)
    assert pm.open_position_count == 1


# ============================================================================
# 4. MARK-TO-MARKET ACCOUNTING & MTM DRAWDOWN TRACKING
# ============================================================================

def test_mark_to_market_unrealized_pnl_and_drawdown():
    """
    Test mark-to-market price updates for 2 open positions:
    - RELIANCE (LONG 20 shares @ 2500): rises to 2550 (+1000)
    - ICICIBANK (SHORT 50 shares @ 1000): falls to 980 (+1000)
    Then RELIANCE drops to 2400 (-2000) and ICICIBANK rises to 1050 (-2500).
    Verify MTM equity, peak equity, and intra-trade drawdown calculation.
    """
    pm = PortfolioManager(initial_capital=50_000.0)

    pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=2500.0,
        quantity=20,
    )
    pm.open_position(
        symbol="ICICIBANK",
        side=Position.SHORT,
        entry_time="09:15",
        entry_price=1000.0,
        quantity=50,
    )

    # Event 1: Favorable MTM moves
    # RELIANCE: (2550 - 2500) * 20 = +1000
    # ICICIBANK: (1000 - 980) * 50 = +1000
    pm.update_market_prices({"RELIANCE": 2550.0, "ICICIBANK": 980.0})

    assert pm.unrealized_pnl == pytest.approx(2000.0)
    assert pm.equity == pytest.approx(52_000.0)
    assert pm.peak_equity == pytest.approx(52_000.0)
    assert pm.max_drawdown == 0.0
    assert pm.cash == pytest.approx(50_000.0)  # Cash stays realized

    # Event 2: Adverse MTM moves
    # RELIANCE: (2450 - 2500) * 20 = -1000
    # ICICIBANK: (1000 - 1020) * 50 = -1000
    # Total unrealized = -2000 -> Equity = 48,000
    pm.update_market_prices({"RELIANCE": 2450.0, "ICICIBANK": 1020.0})

    assert pm.unrealized_pnl == pytest.approx(-2000.0)
    assert pm.equity == pytest.approx(48_000.0)
    assert pm.peak_equity == pytest.approx(52_000.0)  # Peak remains at high water mark

    # Drawdown from peak: (52000 - 48000) / 52000 * 100 = 4000 / 52000 * 100 = ~7.6923%
    expected_dd = (52_000.0 - 48_000.0) / 52_000.0 * 100.0
    assert pm.current_drawdown == pytest.approx(expected_dd)
    assert pm.max_drawdown == pytest.approx(expected_dd)


# ============================================================================
# 5. INDEPENDENT POSITION CLOSURE & MARGIN RELEASE
# ============================================================================

def test_independent_position_closure_and_margin_release():
    """
    Test closing one position while keeping another position active.
    Verify:
    - Margin is released for closed position.
    - Cash is updated with net P&L.
    - Active position remains intact.
    - Transaction costs are deducted exactly once.
    """
    pm = PortfolioManager(
        initial_capital=50_000.0,
        max_leverage=5.0,
        reserve_capital_pct=0.0,
    )

    pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=2500.0,
        quantity=20,
    )
    pm.open_position(
        symbol="ICICIBANK",
        side=Position.SHORT,
        entry_time="09:15",
        entry_price=1000.0,
        quantity=50,
    )

    assert pm.allocated_margin == pytest.approx(20_000.0)
    assert pm.available_margin == pytest.approx(30_000.0)

    # Close RELIANCE at ₹2,550 with realistic cost config
    cost_cfg = DISCOUNT_BROKER_REALISTIC_CONFIG
    rel_trade = pm.close_position(
        symbol="RELIANCE",
        exit_time="10:00",
        exit_price=2550.0,
        exit_reason="TP",
        cost_config=cost_cfg,
    )

    assert rel_trade.symbol == "RELIANCE"
    assert rel_trade.exit_reason == "TP"
    assert rel_trade.gross_pnl == pytest.approx(1000.0)
    assert rel_trade.transaction_cost > 0.0
    expected_net = rel_trade.gross_pnl - rel_trade.transaction_cost
    assert rel_trade.net_pnl == pytest.approx(expected_net)

    # RELIANCE margin (₹10,000) is released!
    # ICICIBANK margin (₹10,000) remains allocated.
    assert pm.open_position_count == 1
    assert "RELIANCE" not in pm.open_positions
    assert "ICICIBANK" in pm.open_positions
    assert pm.allocated_margin == pytest.approx(10_000.0)

    # Cash increased by net P&L of RELIANCE trade
    assert pm.cash == pytest.approx(50_000.0 + expected_net)
    assert pm.trade_count == 1

    # Close ICICIBANK at ₹1,020 (a loss of (1000 - 1020) * 50 = -1000 gross)
    ici_trade = pm.close_position(
        symbol="ICICIBANK",
        exit_time="11:00",
        exit_price=1020.0,
        exit_reason="SL",
        cost_config=cost_cfg,
    )

    assert ici_trade.symbol == "ICICIBANK"
    assert ici_trade.gross_pnl == pytest.approx(-1000.0)
    expected_ici_net = ici_trade.gross_pnl - ici_trade.transaction_cost
    assert ici_trade.net_pnl == pytest.approx(expected_ici_net)

    # All margins now released
    assert pm.open_position_count == 0
    assert pm.allocated_margin == 0.0
    assert pm.cash == pytest.approx(50_000.0 + expected_net + expected_ici_net)
    assert pm.equity == pm.cash
    assert pm.trade_count == 2
    assert pm.total_pnl == pytest.approx(expected_net + expected_ici_net)


def test_close_non_existent_position_raises():
    """Verify closing a position that does not exist raises PositionNotFoundError."""
    pm = PortfolioManager(initial_capital=50_000.0)
    with pytest.raises(PositionNotFoundError):
        pm.close_position(
            symbol="TCS",
            exit_time="10:00",
            exit_price=3500.0,
        )


def test_close_all_positions_eod():
    """Verify close_all_positions cleanly squares off all open positions."""
    pm = PortfolioManager(initial_capital=50_000.0, max_leverage=5.0)

    pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=2500.0,
        quantity=10,
    )
    pm.open_position(
        symbol="INFY",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=1500.0,
        quantity=10,
    )

    assert pm.open_position_count == 2

    closed_trades = pm.close_all_positions(
        exit_time="15:15",
        exit_prices={"RELIANCE": 2510.0, "INFY": 1520.0},
        exit_reason="EOD",
        cost_config=ZERO_COST_CONFIG,
    )

    assert len(closed_trades) == 2
    assert pm.open_position_count == 0
    assert pm.allocated_margin == 0.0
    assert pm.trade_count == 2
    # Reliance: +100, Infy: +200 -> Cash = 50,300
    assert pm.cash == pytest.approx(50_300.0)


# ============================================================================
# 6. MARGIN EXHAUSTION & MAXIMUM ALLOCATION LIMITS
# ============================================================================

def test_margin_exhaustion_rejection():
    """Verify opening a position that exceeds available margin is rejected."""
    pm = PortfolioManager(
        initial_capital=10_000.0,
        max_leverage=5.0,
        reserve_capital_pct=0.10,  # ₹1,000 reserve -> Available margin ₹9,000
    )

    assert pm.available_margin == pytest.approx(9_000.0)

    # 5x leverage allows up to ₹45,000 notional (9000 margin)
    # Attempting to buy 20 shares of RELIANCE @ 2500 = ₹50,000 notional (10,000 margin)
    can_open, reason = pm.can_open_position(
        symbol="RELIANCE",
        entry_price=2500.0,
        quantity=20,
    )
    assert can_open is False
    assert "Insufficient margin" in reason

    with pytest.raises(InsufficientMarginError) as exc_info:
        pm.open_position(
            symbol="RELIANCE",
            side=Position.LONG,
            entry_time="09:15",
            entry_price=2500.0,
            quantity=20,
        )
    assert "Insufficient available margin" in str(exc_info.value)
    assert pm.open_position_count == 0


def test_max_stock_allocation_limit():
    """Verify single-stock exposure cap is enforced when max_stock_allocation_pct is configured."""
    pm = PortfolioManager(
        initial_capital=50_000.0,
        max_leverage=5.0,
        max_stock_allocation_pct=0.20,  # Max 20% of total capacity (50k * 5 * 0.20 = 50,000 notional)
    )

    # 25 shares @ 2500 = ₹62,500 notional > ₹50,000 allowed
    can_open, reason = pm.can_open_position(
        symbol="RELIANCE",
        entry_price=2500.0,
        quantity=25,
    )
    assert can_open is False
    assert "exceeds max allocation" in reason

    with pytest.raises(AllocationExceededError) as exc_info:
        pm.open_position(
            symbol="RELIANCE",
            side=Position.LONG,
            entry_time="09:15",
            entry_price=2500.0,
            quantity=25,
        )
    assert "exceeds max allocation" in str(exc_info.value)


# ============================================================================
# 7. CAPITAL PROTECTION FLOOR & BANKRUPTCY
# ============================================================================

def test_capital_protection_floor_trigger():
    """Verify falling to or below capital protection floor triggers bankruptcy state."""
    pm = PortfolioManager(
        initial_capital=50_000.0,
        capital_protection_floor=45_000.0,  # ₹5,000 loss limit
    )

    assert pm.effective_protection_floor == 45_000.0

    pm.open_position(
        symbol="RELIANCE",
        side=Position.LONG,
        entry_time="09:15",
        entry_price=2500.0,
        quantity=20,
    )

    # Adverse price move: 2500 -> 2200 (-300/share * 20 = -₹6,000 MTM)
    # Equity drops to ₹44,000 < ₹45,000 floor
    pm.update_price("RELIANCE", 2200.0)

    assert pm.equity == pytest.approx(44_000.0)
    assert pm.is_bankrupt is True
    assert pm.bankruptcy_reason == "PROTECTION_FLOOR"

    # Further opening attempts must be rejected
    can_open, reason = pm.can_open_position("INFY", 1500.0, 10)
    assert can_open is False
    assert "bankrupt" in reason

    with pytest.raises(PortfolioBankruptError):
        pm.open_position(
            symbol="INFY",
            side=Position.LONG,
            entry_time="10:00",
            entry_price=1500.0,
            quantity=10,
        )


def test_overall_loss_limit_configures_effective_floor():
    """Verify overall_loss_limit correctly sets effective_protection_floor."""
    pm = PortfolioManager(
        initial_capital=10_000.0,
        overall_loss_limit=2_000.0,
    )
    assert pm.effective_protection_floor == 8_000.0


# ============================================================================
# 8. RESET & BACKWARD COMPATIBILITY WITH PORTFOLIO
# ============================================================================

def test_portfolio_manager_reset():
    """Verify reset restores pristine initial state."""
    pm = PortfolioManager(initial_capital=50_000.0)
    pm.open_position("RELIANCE", Position.LONG, "09:15", 2500.0, 10)
    pm.close_position("RELIANCE", "10:00", 2550.0)
    assert pm.trade_count == 1
    assert pm.cash > 50_000.0

    pm.reset()

    assert pm.cash == 50_000.0
    assert pm.equity == 50_000.0
    assert pm.peak_equity == 50_000.0
    assert pm.max_drawdown == 0.0
    assert pm.trade_count == 0
    assert pm.open_position_count == 0
    assert pm.is_bankrupt is False
    assert pm.trades == []


def test_portfolio_subclass_backward_compatibility():
    """Verify Portfolio class works seamlessly as a drop-in replacement."""
    portfolio = Portfolio(initial_capital=100_000.0)

    assert portfolio.cash == 100_000.0
    assert portfolio.equity == 100_000.0
    assert portfolio.peak_equity == 100_000.0
    assert portfolio.max_drawdown == 0.0
    assert portfolio.trade_count == 0
    assert portfolio.total_pnl == 0.0
    assert portfolio.total_return_pct == 0.0

    trade = simulate_trade(
        position=Position.LONG,
        entry_time="09:15",
        exit_time="09:30",
        entry_price=100.0,
        exit_price=110.0,
        quantity=10,
    )
    portfolio.apply_trade(trade)

    assert portfolio.trade_count == 1
    assert portfolio.equity == pytest.approx(100_100.0)
    assert portfolio.total_pnl == pytest.approx(100.0)


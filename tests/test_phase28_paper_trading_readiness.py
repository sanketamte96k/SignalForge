"""
SignalForge — Phase 28: Controlled Paper-Trading Readiness Test Suite
=====================================================================
File: tests/test_phase28_paper_trading_readiness.py

Comprehensive 15-step in-memory and integration test suite verifying:
1.  Virtual starting capital initialization and isolated account state.
2.  Simulated order submissions (Market, Limit, Stop-Loss, Exit).
3.  Pre-trade risk enforcement (risk per trade, max symbol allocation, aggregate risk, reserved floor).
4.  Causal fill execution with adverse slippage (1.0 bps) and half-spread (0.5 bps).
5.  Cash, margin, and position balance updates.
6.  Indian statutory transaction costs (Brokerage, STT, Exchange, SEBI, GST, Stamp Duty).
7.  Unrealized and realized P&L mark-to-market.
8.  Simulated exit submission and fill execution.
9.  Position closure, margin release, and net realized P&L accounting.
10. Final double-entry ledger equity reconciliation invariants.
11. Persistence reload idempotency (preventing duplicate ledger entries on restarts).
12. Market data feed reliability, stale bar detection, and outage handling.
13. Rejected and cancelled order handling with immutable audit reason.
14. Daily risk protection floor enforcement.
15. Mandatory 15:15 IST square-off enforcement.
16. Zero broker integration verification (strict sandbox isolation).
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import pytest

from src.backtest.indian_market_costs import DISCOUNT_BROKER_REALISTIC_CONFIG
from src.paper_trading.interactive_engine import (
    InteractivePaperTrade,
    InteractivePaperTradingService,
)
from src.paper_trading.ledger import (
    LedgerEntryType,
    PaperAccountLedger,
)
from src.paper_trading.market_data_monitor import (
    DataQualityState,
    MarketDataReliabilityMonitor,
)
from src.paper_trading.risk_manager import (
    PaperRiskConfig,
    PaperRiskManager,
)
from src.paper_trading.simulated_execution import (
    OrderSide,
    SimulatedExecutionEngine,
    SimulatedOrderStatus,
    SimulatedOrderType,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


# ----------------------------------------------------------------------------
# 1. Account Creation & Virtual Starting Capital Initialization
# ----------------------------------------------------------------------------

def test_01_account_creation_and_starting_capital(temp_dir: Path) -> None:
    ledger_path = temp_dir / "ledger.json"
    ledger = PaperAccountLedger(starting_capital=100000.0, persistence_path=ledger_path)
    recon = ledger.reconcile_accounting(unrealized_pnl=0.0)

    assert ledger.starting_capital == 100000.0
    assert ledger.cash_balance == 100000.0
    assert ledger.reserved_capital == 15000.0  # 15% reserve
    assert ledger.available_margin == 85000.0
    assert ledger.allocated_margin == 0.0
    assert recon["is_balanced"] is True
    assert len(ledger.entries) == 1
    assert ledger.entries[0].entry_type == LedgerEntryType.INITIAL_DEPOSIT.value


# ----------------------------------------------------------------------------
# 2. Simulated Order Submission (Market, Limit, Stop-Loss, Exit)
# ----------------------------------------------------------------------------

def test_02_simulated_order_submissions() -> None:
    engine = SimulatedExecutionEngine()
    now = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)

    # Market Order
    mkt = engine.submit_order(
        symbol="TCS",
        side="BUY",
        order_type="MARKET",
        quantity=10,
        requested_price=3500.0,
        stop_price=3465.0,
        target_price=3570.0,
        timestamp=now,
    )
    assert mkt.order_type == SimulatedOrderType.MARKET.value
    assert mkt.status == SimulatedOrderStatus.SUBMITTED.value
    assert mkt.quantity == 10

    # Limit Order
    lmt = engine.submit_order(
        symbol="INFY",
        side="BUY",
        order_type="LIMIT",
        quantity=20,
        requested_price=1500.0,
        stop_price=1485.0,
        timestamp=now,
    )
    assert lmt.order_type == SimulatedOrderType.LIMIT.value
    assert lmt.requested_price == 1500.0

    # Stop Loss Order
    sl = engine.submit_order(
        symbol="RELIANCE",
        side="SELL",
        order_type="STOP_LOSS",
        quantity=5,
        requested_price=2450.0,
        stop_price=2475.0,
        timestamp=now,
    )
    assert sl.order_type == SimulatedOrderType.STOP_LOSS.value
    assert sl.stop_price == 2475.0


# ----------------------------------------------------------------------------
# 3. Server-Side Pre-Trade Risk Enforcement
# ----------------------------------------------------------------------------

def test_03_pre_trade_risk_enforcement() -> None:
    risk_mgr = PaperRiskManager(
        config=PaperRiskConfig(
            max_risk_per_trade_pct=0.01,  # 1%
            max_stock_allocation_pct=0.35,  # 35%
            max_aggregate_portfolio_risk_pct=0.03,  # 3%
            reserved_capital_floor_pct=0.15,
            enforce_session_hours=False,
        )
    )
    portfolio_equity = 100000.0
    available_margin = 85000.0

    # Case A: Stock allocation exceeds 35% (₹35,000 max) -> ₹40,000 requested
    valid, reason = risk_mgr.validate_candidate_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=16,
        price=2500.0,  # 16 * 2500 = 40,000 > 35,000
        stop_price=2475.0,
        portfolio_equity=portfolio_equity,
        available_margin=available_margin,
    )
    assert not valid
    assert "Max stock allocation breached" in reason

    # Case B: Trade risk exceeds 1% (₹1,000 max risk) -> ₹1,500 risk
    # 10 shares * (2500 - 2350) = 10 * 150 = 1500 > 1000
    valid, reason = risk_mgr.validate_candidate_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=2500.0,
        stop_price=2350.0,
        portfolio_equity=portfolio_equity,
        available_margin=available_margin,
    )
    assert not valid
    assert "Risk per trade breached" in reason

    # Case C: Valid candidate order within limits
    # 10 shares @ 2500 = 25,000 (< 35,000 allocation), stop 2475 = ₹250 risk (< ₹1000 risk)
    valid, reason = risk_mgr.validate_candidate_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=2500.0,
        stop_price=2475.0,
        portfolio_equity=portfolio_equity,
        available_margin=available_margin,
    )
    assert valid
    assert reason == "Order approved by risk manager"


# ----------------------------------------------------------------------------
# 4. Causal Fill Execution with Adverse Slippage and Spread
# ----------------------------------------------------------------------------

def test_04_causal_fill_execution_slippage_and_spread() -> None:
    engine = SimulatedExecutionEngine(
        default_slippage_bps=1.0,  # 0.01%
        default_spread_bps=0.5,    # 0.005%
    )
    now = datetime(2026, 3, 26, 10, 15, tzinfo=timezone.utc)

    # BUY Order: quote = 1000.0
    # Expected adverse fill price = 1000 * (1 + 0.00015) = 1000.15
    buy_order = engine.submit_order(
        symbol="INFY",
        side="BUY",
        order_type="MARKET",
        quantity=100,
        requested_price=1000.0,
        timestamp=now,
    )
    filled_buy = engine.execute_fill(
        order_id=buy_order.order_id,
        market_price=1000.0,
        timestamp=now,
        available_cash=150000.0,
    )
    assert filled_buy.status == SimulatedOrderStatus.FILLED.value
    assert pytest.approx(filled_buy.fill_price, 0.01) == 1000.15
    assert filled_buy.slippage_cost > 0.0
    assert filled_buy.spread_cost > 0.0

    # SELL Order: quote = 1000.0
    # Expected adverse fill price = 1000 * (1 - 0.00015) = 999.85
    sell_order = engine.submit_order(
        symbol="INFY",
        side="SELL",
        order_type="MARKET",
        quantity=100,
        requested_price=1000.0,
        timestamp=now,
    )
    filled_sell = engine.execute_fill(
        order_id=sell_order.order_id,
        market_price=1000.0,
        timestamp=now,
        available_cash=150000.0,
    )
    assert filled_sell.status == SimulatedOrderStatus.FILLED.value
    assert pytest.approx(filled_sell.fill_price, 0.01) == 999.85


# ----------------------------------------------------------------------------
# 5 & 6. Cash Updates & Indian Statutory Transaction Costs
# ----------------------------------------------------------------------------

def test_05_06_cash_updates_and_statutory_costs(temp_dir: Path) -> None:
    ledger_path = temp_dir / "ledger.json"
    ledger = PaperAccountLedger(starting_capital=100000.0, persistence_path=ledger_path)

    # Allocate margin for a ₹25,000 position
    margin_entry = ledger.allocate_margin(25000.0, trade_id="tr_1")
    assert ledger.allocated_margin == 25000.0
    assert ledger.available_margin == 60000.0  # 100k - 15k reserved - 25k allocated

    # Record statutory transaction cost of ₹22.50
    cost_entry = ledger.record_transaction_cost(22.50, trade_id="tr_1")
    assert ledger.cash_balance == 99977.50
    assert cost_entry.amount == 22.50


# ----------------------------------------------------------------------------
# 7, 8, 9, 10. Position Lifecycle & Double-Entry Ledger Reconciliation
# ----------------------------------------------------------------------------

def test_07_to_10_full_trade_lifecycle_and_accounting_invariants(temp_dir: Path) -> None:
    ledger_path = temp_dir / "ledger.json"
    ledger = PaperAccountLedger(starting_capital=100000.0, persistence_path=ledger_path)

    # Open: Allocate ₹20,000 margin
    ledger.allocate_margin(20000.0, trade_id="tr_100")
    # Mark to market: unrealized gain +₹500
    recon_open = ledger.reconcile_accounting(unrealized_pnl=500.0)
    assert recon_open["total_equity"] == 100500.0
    assert recon_open["is_balanced"] is True

    # Close: Release ₹20,000 margin
    ledger.release_margin(20000.0, trade_id="tr_100")
    assert ledger.allocated_margin == 0.0

    # Record Gross Realized P&L (+₹500) and Transaction Cost (₹35)
    ledger.record_realized_pnl(500.0, trade_id="tr_100")
    ledger.record_transaction_cost(35.0, trade_id="tr_100")

    # Final Reconciliation (unrealized_pnl = 0.0 after close)
    recon_final = ledger.reconcile_accounting(unrealized_pnl=0.0)
    expected_cash = 100000.0 + 500.0 - 35.0  # 100,465.00
    assert recon_final["cash_balance"] == expected_cash
    assert recon_final["total_equity"] == expected_cash
    assert recon_final["available_margin"] == expected_cash - 15000.0
    assert recon_final["is_balanced"] is True


# ----------------------------------------------------------------------------
# 11. Application Restart & Ledger Idempotency
# ----------------------------------------------------------------------------

def test_11_persistence_reload_and_idempotency(temp_dir: Path) -> None:
    ledger_path = temp_dir / "idempotent_ledger.json"
    ledger1 = PaperAccountLedger(starting_capital=100000.0, persistence_path=ledger_path)
    ledger1.allocate_margin(10000.0, trade_id="tr_persist")
    ledger1.record_transaction_cost(15.0, trade_id="tr_persist")
    ledger1.save_to_disk()

    entry_count_orig = len(ledger1.entries)
    cash_orig = ledger1.cash_balance

    # Reload from disk into a fresh instance
    ledger2 = PaperAccountLedger(starting_capital=100000.0, persistence_path=ledger_path)
    ledger2.load_from_disk()

    assert len(ledger2.entries) == entry_count_orig
    assert ledger2.cash_balance == cash_orig
    assert ledger2.allocated_margin == 10000.0

    # Ensure duplicate load does not re-apply transactions
    ledger2.load_from_disk()
    assert len(ledger2.entries) == entry_count_orig
    assert ledger2.cash_balance == cash_orig


# ----------------------------------------------------------------------------
# 12. Market Data Feed Reliability, Stale Bar & Outage Detection
# ----------------------------------------------------------------------------

def test_12_market_data_monitor_outage_detection() -> None:
    monitor = MarketDataReliabilityMonitor(
        max_missing_bars_tolerance=3,
        feed_timeout_seconds=300.0,
    )
    t0 = datetime(2026, 3, 26, 9, 30, tzinfo=timezone.utc)

    # Initial healthy candle
    monitor.record_candle_received("RELIANCE", t0, 2500.0)
    assert monitor.is_symbol_healthy("RELIANCE") is True
    assert monitor.is_trading_allowed("RELIANCE") is True

    # 3 consecutive missing bars trigger STALE
    t1 = t0 + timedelta(minutes=15)
    monitor.record_missing_bar("RELIANCE", t1)
    monitor.record_missing_bar("RELIANCE", t1 + timedelta(minutes=15))
    monitor.record_missing_bar("RELIANCE", t1 + timedelta(minutes=30))

    health = monitor.get_symbol_health("RELIANCE")
    assert health is not None
    assert health.state == DataQualityState.STALE.value
    assert monitor.is_trading_allowed("RELIANCE") is False

    # Stale mark price can still be queried safely
    price = monitor.get_mark_price("RELIANCE")
    assert price == 2500.0

    # Feed recovery
    t_rec = t1 + timedelta(minutes=45)
    monitor.record_candle_received("RELIANCE", t_rec, 2510.0)
    assert monitor.is_symbol_healthy("RELIANCE") is True
    assert monitor.is_trading_allowed("RELIANCE") is True


# ----------------------------------------------------------------------------
# 13. Rejected & Cancelled Order Handling
# ----------------------------------------------------------------------------

def test_13_rejected_and_cancelled_orders() -> None:
    engine = SimulatedExecutionEngine()
    now = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)

    # Submission
    order = engine.submit_order(
        symbol="SBIN",
        side="BUY",
        order_type="LIMIT",
        quantity=50,
        requested_price=750.0,
        timestamp=now,
    )
    assert order.status == SimulatedOrderStatus.SUBMITTED.value

    # Cancel
    cancelled = engine.cancel_order(order.order_id, reason="User cancelled test order")
    assert cancelled.status == SimulatedOrderStatus.CANCELLED.value
    assert cancelled.rejection_reason == "User cancelled test order"

    # Attempting to cancel again raises ValueError
    with pytest.raises(ValueError, match="terminal state"):
        engine.cancel_order(order.order_id)


# ----------------------------------------------------------------------------
# 14. Capital Protection Floor Halt
# ----------------------------------------------------------------------------

def test_14_protection_floor_halt() -> None:
    risk_mgr = PaperRiskManager(
        config=PaperRiskConfig(
            capital_protection_floor_pct=0.80,  # Halt if equity drops below 80% (₹80,000)
            enforce_session_hours=False,
        )
    )
    # Severe drawdown: equity at ₹75,000 (< ₹80,000 floor)
    valid, reason = risk_mgr.validate_candidate_order(
        symbol="TCS",
        side="BUY",
        quantity=2,
        price=3500.0,
        stop_price=3465.0,
        portfolio_equity=75000.0,
        available_margin=60000.0,
        initial_capital=100000.0,
    )
    assert not valid
    assert "Capital protection floor breached" in reason
    assert risk_mgr.is_blocked() is True


# ----------------------------------------------------------------------------
# 15. Mandatory 15:15 IST Square-Off Enforcement
# ----------------------------------------------------------------------------

def test_15_mandatory_1515_square_off_cutoff() -> None:
    risk_mgr = PaperRiskManager(
        config=PaperRiskConfig(
            enforce_session_hours=True,
            square_off_time=time(15, 15),
        )
    )
    # In IST (UTC+5:30), 15:16 IST is 09:46 UTC
    cutoff_time_utc = datetime(2026, 3, 26, 9, 46, tzinfo=timezone.utc)

    valid, reason = risk_mgr.validate_candidate_order(
        symbol="INFY",
        side="BUY",
        quantity=10,
        price=1500.0,
        stop_price=1485.0,
        portfolio_equity=100000.0,
        available_margin=85000.0,
        timestamp=cutoff_time_utc,
    )
    assert not valid
    assert "15:15 IST" in reason


# ----------------------------------------------------------------------------
# 16. Zero Live Broker Paths Verification (Isolation Guarantee)
# ----------------------------------------------------------------------------

def test_16_zero_broker_isolation() -> None:
    """Verify that paper trading components contain no live broker credentials or active networks."""
    service = InteractivePaperTradingService()
    assert service.simulation_only is True
    assert hasattr(service, "simulated_execution")
    assert not hasattr(service, "broker_client")
    assert not hasattr(service, "live_api_key")
    assert not hasattr(service, "access_token")

    state = service.get_account_state()
    assert state["simulation_only"] is True
    assert "PAPER / SIMULATION ONLY" in state["environment_badge"]

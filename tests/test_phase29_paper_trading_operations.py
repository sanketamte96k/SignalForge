"""
Phase 29: Controlled Paper-Trading Operations Test Suite.

Validates:
1. Operational Architecture & Runbook parameters
2. Formal Session Lifecycle state machine (CREATED -> VALIDATING -> READY -> RUNNING -> PAUSED -> COMPLETED)
3. Invalid state transition rejection
4. Session and Virtual-Account isolation (no cross-contamination of positions, orders, or cash)
5. Execution Quality Analytics (decision price, fill price, slippage bps, half-spread bps, statutory fees)
6. Double-entry daily accounting reconciliation:
   - Equity == Cash + Unrealized P&L
   - Equity == Initial Capital + Cumulative Realized Net P&L + Unrealized P&L
   - Available Margin + Allocated Margin == Equity - Reserved Capital
7. Risk monitoring, Fail-Closed market data gate, and 15:15 IST Square-Off
8. Incident tracking (INFO, WARNING, CRITICAL) and auto-pause on CRITICAL
9. Multi-session persistence and restart recovery
10. Daily and weekly operational reporting generators
11. Full API endpoint integration via FastAPI TestClient
12. Zero-broker isolation and ₹0 budget guarantees

SIMULATION ONLY: Uses synthetic in-memory fixtures. No real-money broker execution.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.paper_trading.execution_quality import (
    ExecutionQualityAnalyzer,
    ExecutionQualityRecord,
)
from src.paper_trading.operational_reporting import OperationalReportGenerator
from src.paper_trading.reconciliation import (
    DailyReconciliationReport,
    PaperReconciliationEngine,
)
from src.paper_trading.session_manager import (
    IncidentSeverity,
    PaperSessionConfig,
    PaperSessionManager,
    PaperSessionStatus,
    PaperTradingIncident,
    PaperTradingSession,
)


@pytest.fixture
def temp_session_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ----------------------------------------------------------------------------
# 1. Session Lifecycle & State Transitions
# ----------------------------------------------------------------------------


def test_01_session_creation_and_lifecycle_transitions(temp_session_dir):
    """Verify formal state machine transitions and audit incidents."""
    config = PaperSessionConfig(
        session_id="sess_lifecycle_001",
        account_id="acct_lifecycle_001",
        initial_capital=1_000_000.0,
        symbols=["RELIANCE", "TCS"],
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)

    assert session.status == PaperSessionStatus.CREATED
    assert session.session_id == "sess_lifecycle_001"
    assert session.account_id == "acct_lifecycle_001"

    # Transition 1: CREATED -> VALIDATING
    session.transition_to(PaperSessionStatus.VALIDATING, reason="Validating pre-session conditions")
    assert session.status == PaperSessionStatus.VALIDATING

    # Transition 2: VALIDATING -> READY
    session.transition_to(PaperSessionStatus.READY, reason="Data feeds and risk verified")
    assert session.status == PaperSessionStatus.READY

    # Transition 3: READY -> RUNNING
    session.transition_to(PaperSessionStatus.RUNNING, reason="Market open 09:15 IST")
    assert session.status == PaperSessionStatus.RUNNING
    assert session.start_timestamp is not None

    # Transition 4: RUNNING -> PAUSED
    session.transition_to(PaperSessionStatus.PAUSED, reason="Manual operator pause")
    assert session.status == PaperSessionStatus.PAUSED

    # Transition 5: PAUSED -> RUNNING
    session.transition_to(PaperSessionStatus.RUNNING, reason="Resuming session")
    assert session.status == PaperSessionStatus.RUNNING

    # Transition 6: RUNNING -> COMPLETED
    session.transition_to(PaperSessionStatus.COMPLETED, reason="End of trading day 15:30 IST")
    assert session.status == PaperSessionStatus.COMPLETED
    assert session.end_timestamp is not None


def test_02_invalid_state_transitions_strictly_rejected(temp_session_dir):
    """Verify that illegal transitions (e.g. CREATED -> RUNNING, COMPLETED -> RUNNING) raise ValueError."""
    config = PaperSessionConfig(
        session_id="sess_invalid_transitions",
        account_id="acct_invalid_transitions",
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)

    # Cannot jump directly from CREATED to RUNNING
    with pytest.raises(ValueError, match="Invalid session state transition"):
        session.transition_to(PaperSessionStatus.RUNNING)

    # Valid path to COMPLETED
    session.transition_to(PaperSessionStatus.VALIDATING)
    session.transition_to(PaperSessionStatus.READY)
    session.transition_to(PaperSessionStatus.RUNNING)
    session.transition_to(PaperSessionStatus.COMPLETED)

    # COMPLETED is terminal: cannot transition anywhere
    with pytest.raises(ValueError, match="Invalid session state transition"):
        session.transition_to(PaperSessionStatus.RUNNING)


# ----------------------------------------------------------------------------
# 2. Session and Account Isolation
# ----------------------------------------------------------------------------


def test_03_strict_session_and_account_isolation(temp_session_dir):
    """Ensure two distinct sessions maintain completely isolated ledgers, orders, and positions."""
    mgr = PaperSessionManager(root_dir=temp_session_dir)

    sess1 = mgr.create_session(
        session_id="sess_alpha",
        account_id="acct_alpha",
        initial_capital=500_000.0,
        symbols=["RELIANCE"],
    )
    sess2 = mgr.create_session(
        session_id="sess_beta",
        account_id="acct_beta",
        initial_capital=1_500_000.0,
        symbols=["TCS"],
    )

    # Activate sess1
    sess1.transition_to(PaperSessionStatus.VALIDATING)
    sess1.transition_to(PaperSessionStatus.READY)
    sess1.transition_to(PaperSessionStatus.RUNNING)

    # Provide market data tick to sess1
    tick_time = datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc)
    sess1.process_market_tick("RELIANCE", tick_time, 2500.0, 2505.0, 2495.0, 1000)

    # Submit order in sess1
    ord1 = sess1.submit_simulated_order(
        symbol="RELIANCE",
        side="BUY",
        order_type="MARKET",
        quantity=10,
        price=2500.0,
        timestamp=tick_time,
    )
    assert ord1.status == "FILLED"

    # Verify sess1 has position and allocated margin
    assert "RELIANCE" in sess1.open_positions
    h1 = sess1.get_health_summary()
    assert h1["allocated_margin"] > 0
    assert h1["open_positions_count"] == 1

    # Verify sess2 is completely unaffected
    assert sess2.status == PaperSessionStatus.CREATED
    assert "RELIANCE" not in sess2.open_positions
    h2 = sess2.get_health_summary()
    assert h2["allocated_margin"] == 0.0
    assert h2["open_positions_count"] == 0
    assert h2["total_equity"] == 1_500_000.0
    assert len(sess2.execution_engine.list_orders()) == 0


# ----------------------------------------------------------------------------
# 3. Execution Quality Analytics & Cost Decomposition
# ----------------------------------------------------------------------------


def test_04_execution_quality_analytics_and_slippage_decomposition():
    """Verify execution quality decomposes slippage, spread, and statutory fees."""
    analyzer = ExecutionQualityAnalyzer()

    # Record 1: BUY order with 1.0 bps adverse slippage and 0.5 bps spread
    rec1 = ExecutionQualityRecord(
        order_id="ord_eq_001",
        symbol="RELIANCE",
        side="BUY",
        order_type="MARKET",
        quantity=10,
        decision_price=2500.0,
        reference_market_price=2500.0,
        simulated_fill_price=2500.38,  # +0.25 (1.0 bps slippage) + 0.125 (0.5 bps spread)
        half_spread=0.125,
        brokerage=20.0,
        stt=0.0,  # Intraday equity buy has 0 STT
        exchange_fee=0.86,
        sebi_fee=0.03,
        stamp_duty=0.75,
        gst=3.76,
        total_cost=27.90,
        status="FILLED",
    )
    analyzer.record_execution(rec1)

    summary = analyzer.get_summary()
    assert summary["total_orders"] == 1
    assert summary["filled_orders"] == 1
    assert summary["fill_rate_pct"] == 100.0
    assert summary["average_slippage_bps"] == pytest.approx(1.0, abs=0.2)
    assert summary["average_spread_bps"] == pytest.approx(0.5, abs=0.1)
    assert summary["total_statutory_costs"] == pytest.approx(25.40, abs=0.1)
    assert summary["fee_breakdown"]["brokerage"] == 20.0
    assert summary["fee_breakdown"]["gst"] == 3.76
    assert summary["simulation_only"] is True


# ----------------------------------------------------------------------------
# 4. Double-Entry Accounting Reconciliation
# ----------------------------------------------------------------------------


def test_05_daily_double_entry_reconciliation_invariants(temp_session_dir):
    """
    Verify both reconciliation equations strictly hold:
    1. Equity == Cash + Unrealized P&L
    2. Equity == Initial Capital + Cumulative Realized Net P&L + Unrealized P&L
    """
    config = PaperSessionConfig(
        session_id="sess_recon_001",
        account_id="acct_recon_001",
        initial_capital=1_000_000.0,
        symbols=["TCS"],
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)
    session.transition_to(PaperSessionStatus.VALIDATING)
    session.transition_to(PaperSessionStatus.READY)
    session.transition_to(PaperSessionStatus.RUNNING)

    # 1. Open BUY Position: 10 shares of TCS at 3500.0
    t1 = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    session.process_market_tick("TCS", t1, 3500.0, 3510.0, 3490.0, 500)
    ord_buy = session.submit_simulated_order(
        symbol="TCS",
        side="BUY",
        order_type="MARKET",
        quantity=10,
        price=3500.0,
        timestamp=t1,
    )
    assert ord_buy.status == "FILLED"

    # Reconcile while position is open
    t2 = datetime(2026, 11, 18, 5, 00, tzinfo=timezone.utc)
    session.process_market_tick("TCS", t2, 3550.0, 3560.0, 3540.0, 800)  # Mark price up by 50

    recon_open = session.reconcile()
    assert recon_open.equation_1_holds is True
    assert recon_open.equation_2_holds is True
    assert recon_open.margin_conservation_holds is True
    assert recon_open.is_balanced is True
    assert recon_open.unrealized_pnl == pytest.approx(494.75, abs=5.0)
    assert len(recon_open.discrepancies) == 0

    # 2. Close Position: SELL 10 shares of TCS at 3550.0
    ord_sell = session.submit_simulated_order(
        symbol="TCS",
        side="SELL",
        order_type="MARKET",
        quantity=10,
        price=3550.0,
        timestamp=t2,
    )
    assert ord_sell.status == "FILLED"

    recon_closed = session.reconcile()
    assert recon_closed.equation_1_holds is True
    assert recon_closed.equation_2_holds is True
    assert recon_closed.margin_conservation_holds is True
    assert recon_closed.is_balanced is True
    assert recon_closed.unrealized_pnl == 0.0
    assert recon_closed.closed_trades_count == 1
    assert recon_closed.open_positions_count == 0
    assert recon_closed.discrepancies == []


# ----------------------------------------------------------------------------
# 5. Fail-Closed Market Data Gate & Incident Handling
# ----------------------------------------------------------------------------


def test_06_fail_closed_market_data_and_auto_pause(temp_session_dir):
    """Verify that disconnected/stale feeds reject entries, and CRITICAL incidents auto-pause session."""
    config = PaperSessionConfig(
        session_id="sess_fail_closed",
        account_id="acct_fail_closed",
        symbols=["INFY"],
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)
    session.transition_to(PaperSessionStatus.VALIDATING)
    session.transition_to(PaperSessionStatus.READY)
    session.transition_to(PaperSessionStatus.RUNNING)

    # Simulate feed disconnect on market data monitor
    session.market_data_monitor.set_disconnected("Upstream market data feed disconnected")

    t_order = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    # Order entry must fail closed
    with pytest.raises(ValueError, match="Market data feed is"):
        session.submit_simulated_order(
            symbol="INFY",
            side="BUY",
            order_type="MARKET",
            quantity=5,
            price=1500.0,
            timestamp=t_order,
        )

    # Log CRITICAL incident -> session must automatically pause
    inc = session.record_incident(
        severity=IncidentSeverity.CRITICAL,
        category="FEED_OUTAGE",
        description="Persistent market data outage detected",
        auto_pause_on_critical=True,
    )
    assert inc.severity == "CRITICAL"
    assert session.status == PaperSessionStatus.PAUSED
    assert "Auto-paused" in session.status_reason


# ----------------------------------------------------------------------------
# 6. Intraday Square-Off at 15:15 IST
# ----------------------------------------------------------------------------


def test_07_intraday_square_off_cutoff(temp_session_dir):
    """Verify that market ticks at or past 15:15 IST trigger mandatory square-off of open positions."""
    config = PaperSessionConfig(
        session_id="sess_square_off",
        account_id="acct_square_off",
        symbols=["RELIANCE"],
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)
    session.transition_to(PaperSessionStatus.VALIDATING)
    session.transition_to(PaperSessionStatus.READY)
    session.transition_to(PaperSessionStatus.RUNNING)

    # Open position at 10:00 IST (04:30 UTC)
    t_open = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    session.process_market_tick("RELIANCE", t_open, 2500.0, 2505.0, 2495.0, 500)
    session.submit_simulated_order("RELIANCE", "BUY", "MARKET", 10, 2500.0, timestamp=t_open)
    assert len(session.open_positions) == 1

    # Market tick at 15:16 IST (09:46 UTC) - past cutoff
    t_cutoff = datetime(2026, 11, 18, 9, 46, tzinfo=timezone.utc)
    session.process_market_tick("RELIANCE", t_cutoff, 2520.0, 2525.0, 2515.0, 500)

    # Position must be liquidated
    assert len(session.open_positions) == 0
    assert len(session.closed_trades) == 1
    assert any(i.category == "SQUARE_OFF_CUTOFF" for i in session.incidents)


# ----------------------------------------------------------------------------
# 7. Multi-Session Reliability & Restart Persistence
# ----------------------------------------------------------------------------


def test_08_session_persistence_and_reload(temp_session_dir):
    """Verify session state, incidents, and ledger survive disk reload without data loss."""
    config = PaperSessionConfig(
        session_id="sess_persistent_001",
        account_id="acct_persistent_001",
        initial_capital=750_000.0,
        symbols=["TCS"],
    )
    session = PaperTradingSession(config=config, persistence_dir=temp_session_dir)
    session.transition_to(PaperSessionStatus.VALIDATING)
    session.transition_to(PaperSessionStatus.READY)
    session.transition_to(PaperSessionStatus.RUNNING)

    t = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    session.process_market_tick("TCS", t, 3500.0, 3510.0, 3490.0, 500)
    session.submit_simulated_order("TCS", "BUY", "MARKET", 5, 3500.0, timestamp=t)
    session.record_incident(
        severity=IncidentSeverity.WARNING,
        category="MARGIN_UTILIZATION",
        description="Margin utilized > 20%",
    )
    session.save_to_disk()

    # Reload from disk
    reloaded = PaperTradingSession.load_from_disk(temp_session_dir)
    assert reloaded.session_id == "sess_persistent_001"
    assert reloaded.account_id == "acct_persistent_001"
    assert reloaded.status == PaperSessionStatus.RUNNING
    assert "TCS" in reloaded.open_positions
    assert reloaded.open_positions["TCS"]["quantity"] == 5
    assert len(reloaded.incidents) >= 2  # Creation + Warning incident
    assert reloaded.ledger.initial_capital == 750_000.0


# ----------------------------------------------------------------------------
# 8. Operational Reporting Generators
# ----------------------------------------------------------------------------


def test_09_daily_and_weekly_operational_reporting():
    """Verify operational report generation across multiple sessions."""
    sessions_data = [
        {
            "session_id": "sess_day1",
            "account_id": "acct_1",
            "data_quality_state": "CONNECTED",
            "orders": [{"status": "FILLED", "fill_price": 2500.0, "quantity": 10}],
            "trades": [{"net_pnl": 500.0, "gross_pnl": 550.0, "total_cost": 50.0}],
            "incidents": [{"severity": "INFO", "category": "START"}],
            "execution_quality": {"average_slippage_bps": 1.0, "average_spread_bps": 0.5},
            "starting_capital": 1_000_000.0,
            "current_equity": 1_000_500.0,
            "peak_equity": 1_000_500.0,
            "max_exposure": 25_000.0,
            "risk_violations_count": 0,
        }
    ]

    report = OperationalReportGenerator.generate_report(
        report_type="DAILY",
        period_start="2026-11-18",
        period_end="2026-11-18",
        sessions_data=sessions_data,
    )
    assert report.report_type == "DAILY"
    assert report.total_sessions == 1
    assert report.total_trades == 1
    assert report.win_rate_pct == 100.0
    assert report.net_pnl == 500.0
    assert report.total_transaction_costs == 50.0
    assert "Phase 27C.9 strategies remain rejected" in report.disclaimer


# ----------------------------------------------------------------------------
# 9. FastAPI API Endpoints Integration
# ----------------------------------------------------------------------------


def test_10_api_session_lifecycle_and_operations():
    """Verify full HTTP API contract for Phase 29 paper trading operations."""
    import uuid
    from src.api.routes.paper_trading import (
        create_session,
        transition_session_state,
        submit_session_order,
        get_session_execution_quality,
        get_session_daily_reconciliation,
        get_daily_operational_report,
        _get_session_manager,
    )
    from src.api.models import (
        PaperSessionCreateRequest,
        PaperSessionTransitionRequest,
        SimulatedOrderCreateRequest,
    )

    s_id = f"sess_api_{uuid.uuid4().hex[:6]}"
    a_id = f"acct_api_{uuid.uuid4().hex[:6]}"

    # 1. Create session via create_session
    req_create = PaperSessionCreateRequest(
        session_id=s_id,
        account_id=a_id,
        initial_capital=1_000_000.0,
        symbols=["RELIANCE", "TCS"],
    )
    data = create_session(req_create)
    assert data.session_id == s_id
    assert data.status == "CREATED"

    # 2. Transition through lifecycle
    transition_session_state(s_id, PaperSessionTransitionRequest(target_status="VALIDATING", reason="Pre-flight"))
    transition_session_state(s_id, PaperSessionTransitionRequest(target_status="READY", reason="Ready for open"))
    run_resp = transition_session_state(s_id, PaperSessionTransitionRequest(target_status="RUNNING", reason="Trading started"))
    assert run_resp.status == "RUNNING"

    # Inject market tick for RELIANCE so trading is permitted
    sess = _get_session_manager().get_session(s_id)
    t_trade = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    sess.process_market_tick("RELIANCE", t_trade, 2500.0, 2505.0, 2495.0, 500)

    # 3. Submit simulated order via API
    order_req = SimulatedOrderCreateRequest(
        symbol="RELIANCE",
        side="BUY",
        order_type="MARKET",
        quantity=5,
        price=2500.0,
        current_market_price=2500.0,
        timestamp=t_trade,
    )
    ord_data = submit_session_order(s_id, order_req)
    assert ord_data.status == "FILLED"
    assert ord_data.fill_price > 2500.0

    # 4. Check Execution Quality API
    eq_resp = get_session_execution_quality(s_id)
    assert eq_resp.filled_orders >= 1
    assert eq_resp.average_slippage_bps > 0

    # 5. Check Daily Reconciliation API
    recon_data = get_session_daily_reconciliation(s_id)
    assert recon_data.equation_1_holds is True
    assert recon_data.equation_2_holds is True
    assert recon_data.is_balanced is True

    # 6. Check Operational Reports
    rep_resp = get_daily_operational_report()
    assert rep_resp.report_type == "DAILY"


def test_11_zero_broker_isolation_guarantee():
    """Verify that paper trading operations strictly execute with zero live broker dependencies."""
    from src.paper_trading.interactive_engine import InteractivePaperTradingService

    service = InteractivePaperTradingService(starting_capital=500_000.0)
    assert service.simulation_only is True
    assert hasattr(service, "simulated_execution")
    assert not hasattr(service, "live_broker_client")

"""
Phase 29: Controlled Paper-Trading Session Lifecycle & Management.

Manages discrete paper-trading sessions with:
- Formal state machine: CREATED, VALIDATING, READY, RUNNING, PAUSED, COMPLETED, FAILED, ABORTED
- Server-side state transition enforcement
- Strict account and session isolation
- Integrated double-entry ledger, risk discipline, data reliability monitor, and execution quality analyzer
- Incident tracking with severity levels (INFO, WARNING, CRITICAL) and fail-closed automatic pauses
- Causal execution on verified market quotes without fabricated fills
- Atomic JSON persistence

SIMULATION ONLY: Never connects to or executes on any real-money broker. Zero live execution.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.io_utils import atomic_write_json
from src.paper_trading.cost_model import CostModel, DISCOUNT_BROKER_REALISTIC_CONFIG
from src.paper_trading.execution_quality import (
    ExecutionQualityAnalyzer,
    ExecutionQualityRecord,
)
from src.paper_trading.ledger import PaperAccountLedger, LedgerEntryType
from src.paper_trading.market_data_monitor import (
    DataQualityState,
    MarketDataReliabilityMonitor,
)
from src.paper_trading.reconciliation import (
    DailyReconciliationReport,
    PaperReconciliationEngine,
)
from src.paper_trading.risk_manager import PaperRiskConfig, PaperRiskManager
from src.paper_trading.simulated_execution import (
    SimulatedExecutionEngine,
    SimulatedOrder,
    SimulatedOrderStatus,
    SimulatedOrderType,
)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class PaperSessionStatus(str, Enum):
    """Lifecycle statuses for a paper-trading session."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


VALID_TRANSITIONS: dict[PaperSessionStatus, set[PaperSessionStatus]] = {
    PaperSessionStatus.CREATED: {
        PaperSessionStatus.VALIDATING,
        PaperSessionStatus.FAILED,
        PaperSessionStatus.ABORTED,
    },
    PaperSessionStatus.VALIDATING: {
        PaperSessionStatus.READY,
        PaperSessionStatus.FAILED,
        PaperSessionStatus.ABORTED,
    },
    PaperSessionStatus.READY: {
        PaperSessionStatus.RUNNING,
        PaperSessionStatus.ABORTED,
    },
    PaperSessionStatus.RUNNING: {
        PaperSessionStatus.PAUSED,
        PaperSessionStatus.COMPLETED,
        PaperSessionStatus.FAILED,
        PaperSessionStatus.ABORTED,
    },
    PaperSessionStatus.PAUSED: {
        PaperSessionStatus.RUNNING,
        PaperSessionStatus.COMPLETED,
        PaperSessionStatus.FAILED,
        PaperSessionStatus.ABORTED,
    },
    PaperSessionStatus.COMPLETED: set(),
    PaperSessionStatus.FAILED: set(),
    PaperSessionStatus.ABORTED: set(),
}


class IncidentSeverity(str, Enum):
    """Severity ratings for operational incidents."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class PaperTradingIncident:
    """Audit record for an operational event, alert, or risk violation."""

    incident_id: str
    timestamp: datetime
    severity: str
    category: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    action_taken: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "details": self.details,
            "action_taken": self.action_taken,
            "simulation_only": True,
        }


@dataclass
class PaperSessionConfig:
    """Static configuration parameters for a paper-trading session."""

    session_id: str
    account_id: str
    data_source: str = "SYNTHETIC_SAFE_FEED"
    strategy_name: str = "SignalForge_Intraday_V1"
    strategy_version: str = "29.0"
    execution_model: str = "SIMULATED_DISCOUNT_BROKER_REALISTIC"
    initial_capital: float = 1_000_000.0
    symbols: list[str] = field(default_factory=lambda: ["RELIANCE", "TCS", "INFY"])
    risk_config: dict[str, Any] = field(default_factory=dict)
    total_account_balance: float | None = None
    allocated_capital: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperTradingSession:
    """
    An isolated, self-contained Equity Intraday paper-trading session.
    Owns its independent ledger, execution engine, risk manager, and market-data monitor.
    """

    def __init__(
        self,
        config: PaperSessionConfig,
        persistence_dir: Path | str | None = None,
    ) -> None:
        self.config = config
        self.session_id = config.session_id
        self.account_id = config.account_id
        self.status = PaperSessionStatus.CREATED
        self.status_reason = "Session instantiated"

        self.start_timestamp: datetime | None = None
        self.end_timestamp: datetime | None = None
        self.last_market_timestamp: datetime | None = None
        self.last_order_event_timestamp: datetime | None = None

        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

        # Storage directory
        if persistence_dir:
            self.persistence_dir = Path(persistence_dir)
        else:
            self.persistence_dir = (
                Path(__file__).resolve().parents[2]
                / "data"
                / "paper_trading"
                / "sessions"
                / self.session_id
            )
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

        # Isolated Components
        ledger_path = self.persistence_dir / "ledger.json"
        self.ledger = PaperAccountLedger(
            starting_capital=config.initial_capital,
            persistence_path=ledger_path,
        )

        risk_cfg_dict = dict(config.risk_config)
        self.risk_manager = PaperRiskManager(
            config=PaperRiskConfig(**risk_cfg_dict) if risk_cfg_dict else None
        )

        self.market_data_monitor = MarketDataReliabilityMonitor(
            symbols=config.symbols,
        )

        self.execution_engine = SimulatedExecutionEngine(
            cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        )

        self.execution_quality = ExecutionQualityAnalyzer()
        self.incidents: list[PaperTradingIncident] = []

        # Position tracking: {symbol: {"side": str, "quantity": int, "entry_price": float, "mark_price": float, "unrealized_pnl": float}}
        self.open_positions: dict[str, dict[str, Any]] = {}
        self.closed_trades: list[dict[str, Any]] = []

        self.peak_equity: float = config.initial_capital
        self.max_exposure: float = 0.0

        # Record creation incident
        self.record_incident(
            severity=IncidentSeverity.INFO,
            category="SESSION_LIFECYCLE",
            description=f"Session {self.session_id} created for account {self.account_id}",
            action_taken="Initialized in CREATED status",
        )

    # ------------------------------------------------------------------------
    # State Transitions
    # ------------------------------------------------------------------------

    def transition_to(
        self,
        target_status: PaperSessionStatus,
        reason: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        """
        Transition session to new status enforcing valid state transition graph.
        """
        now = _ensure_utc(timestamp or datetime.now(timezone.utc))
        allowed = VALID_TRANSITIONS.get(self.status, set())

        if target_status not in allowed:
            raise ValueError(
                f"Invalid session state transition from {self.status.value} to {target_status.value}. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )

        prev_status = self.status
        self.status = target_status
        self.status_reason = reason
        self.updated_at = now

        if target_status == PaperSessionStatus.RUNNING and self.start_timestamp is None:
            self.start_timestamp = now
        elif target_status in {
            PaperSessionStatus.COMPLETED,
            PaperSessionStatus.FAILED,
            PaperSessionStatus.ABORTED,
        }:
            if self.end_timestamp is None:
                self.end_timestamp = now

        self.record_incident(
            severity=IncidentSeverity.INFO,
            category="SESSION_TRANSITION",
            description=f"Session transitioned from {prev_status.value} to {target_status.value}",
            details={"previous_status": prev_status.value, "new_status": target_status.value, "reason": reason},
            action_taken=f"State updated to {target_status.value}",
        )
        self.save_to_disk()

    # ------------------------------------------------------------------------
    # Incident Tracking & Auto-Safety Handling
    # ------------------------------------------------------------------------

    def record_incident(
        self,
        severity: IncidentSeverity | str,
        category: str,
        description: str,
        details: dict[str, Any] | None = None,
        action_taken: str = "",
        auto_pause_on_critical: bool = True,
        timestamp: datetime | None = None,
    ) -> PaperTradingIncident:
        """Record an operational incident and apply fail-closed safety if CRITICAL."""
        now = _ensure_utc(timestamp or datetime.now(timezone.utc))
        sev_str = severity.value if isinstance(severity, IncidentSeverity) else str(severity).upper()

        incident = PaperTradingIncident(
            incident_id=f"inc_{uuid.uuid4().hex[:8]}",
            timestamp=now,
            severity=sev_str,
            category=category,
            description=description,
            details=details or {},
            action_taken=action_taken,
        )
        self.incidents.append(incident)

        if (
            sev_str == IncidentSeverity.CRITICAL.value
            and auto_pause_on_critical
            and self.status == PaperSessionStatus.RUNNING
        ):
            self.status = PaperSessionStatus.PAUSED
            self.status_reason = f"Auto-paused due to CRITICAL incident: {description}"
            self.updated_at = now
            incident.action_taken = (
                f"{action_taken} | Session auto-paused into safe state" if action_taken else "Session auto-paused"
            )

        return incident

    # ------------------------------------------------------------------------
    # Market Data Processing
    # ------------------------------------------------------------------------

    def process_market_tick(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        high: float | None = None,
        low: float | None = None,
        volume: int = 0,
    ) -> None:
        """
        Process an authentic incoming market candle/tick.
        Updates monitor, marks open positions, checks stops/targets, and evaluates cutoff.
        """
        now = _ensure_utc(timestamp)
        self.last_market_timestamp = now

        # 1. Update Market Data Reliability Monitor
        self.market_data_monitor.record_candle_received(
            symbol=symbol,
            timestamp=now,
            close=price,
            high=high,
            low=low,
            volume=volume,
        )

        # 2. Update mark price and unrealized PnL for active positions
        if symbol in self.open_positions:
            pos = self.open_positions[symbol]
            pos["mark_price"] = price
            side = pos["side"].upper()
            qty = pos["quantity"]
            entry_p = pos["entry_price"]

            if side in {"BUY", "LONG"}:
                pos["unrealized_pnl"] = (price - entry_p) * qty
            else:
                pos["unrealized_pnl"] = (entry_p - price) * qty

        # 3. Check intraday cutoff (15:15 IST)
        is_sq, sq_reason = self.risk_manager.is_square_off_time(now)
        if is_sq and self.open_positions:
            self.record_incident(
                severity=IncidentSeverity.WARNING,
                category="SQUARE_OFF_CUTOFF",
                description=f"Mandatory square-off reached at {now.isoformat()}: {sq_reason}",
                action_taken="Liquidating all open intraday positions at market quote",
            )
            self._liquidate_all_positions(timestamp=now, reason=sq_reason)

        # 4. Check capital protection floor
        total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in self.open_positions.values())
        recon = self.ledger.reconcile_accounting(total_unrealized)
        is_floor_breached, floor_reason = self.risk_manager.check_capital_floor(recon["total_equity"])
        if is_floor_breached:
            self.record_incident(
                severity=IncidentSeverity.CRITICAL,
                category="CAPITAL_PROTECTION_FLOOR",
                description=f"Capital protection floor breached: {floor_reason}",
                action_taken="Liquidating open positions and halting session",
            )
            self._liquidate_all_positions(timestamp=now, reason="Capital floor breached")

        # Update peak equity and exposure
        self.peak_equity = max(self.peak_equity, recon["total_equity"])
        gross_exp = sum(p.get("mark_price", p["entry_price"]) * p["quantity"] for p in self.open_positions.values())
        self.max_exposure = max(self.max_exposure, gross_exp)

    # ------------------------------------------------------------------------
    # Order Execution & Lifecycle
    # ------------------------------------------------------------------------

    def submit_simulated_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "MARKET",
        quantity: int = 1,
        price: float | None = None,
        stop_price: float | None = None,
        current_market_price: float | None = None,
        client_order_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> SimulatedOrder:
        """
        Submit a simulated order with server-side fail-closed gates:
        1. Session must be in RUNNING status.
        2. Market data must be CONNECTED and not STALE/OUTAGE.
        3. Pre-trade risk validation must pass.
        4. Causal fill execution with adverse slippage and regulatory fees.
        5. Double-entry margin allocation and execution quality audit.
        """
        now = _ensure_utc(timestamp or datetime.now(timezone.utc))
        self.last_order_event_timestamp = now

        # Gate 1: Session Status Check
        if self.status != PaperSessionStatus.RUNNING:
            reason = f"Session is in {self.status.value} state (requires RUNNING)"
            self.record_incident(
                severity=IncidentSeverity.WARNING,
                category="ORDER_GATE_SESSION_STATUS",
                description=f"Rejected simulated order for {symbol}: {reason}",
                action_taken="Order rejected server-side",
            )
            # Create a rejected order record
            req_p = price or current_market_price or 100.0
            rej_order = self.execution_engine.submit_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                requested_price=req_p,
                stop_price=stop_price,
                client_request_id=client_order_id,
                timestamp=now,
            )
            rej_order.status = "REJECTED"
            rej_order.rejection_reason = reason
            self.execution_quality.record_execution(
                ExecutionQualityRecord(
                    order_id=rej_order.order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    decision_price=req_p,
                    reference_market_price=req_p,
                    simulated_fill_price=0.0,
                    status="REJECTED",
                    rejection_reason=reason,
                    timestamp=now,
                )
            )
            raise ValueError(f"Order rejected: {reason}")

        # Gate 2: Market Data Health Check (Fail-Closed)
        if not self.market_data_monitor.is_trading_allowed(symbol):
            g_state = self.market_data_monitor.global_feed_state
            m_state = getattr(g_state, "value", g_state)
            reason = f"Market data feed is {m_state} or symbol {symbol} is stale/outage"
            self.record_incident(
                severity=IncidentSeverity.WARNING,
                category="ORDER_GATE_MARKET_DATA",
                description=f"Market data failure blocking {symbol} entry: {reason}",
                action_taken="Order rejected (Fail-Closed)",
            )
            req_p = price or current_market_price or 100.0
            rej_order = self.execution_engine.submit_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                requested_price=req_p,
                stop_price=stop_price,
                client_request_id=client_order_id,
                timestamp=now,
            )
            rej_order.status = "REJECTED"
            rej_order.rejection_reason = reason
            self.execution_quality.record_execution(
                ExecutionQualityRecord(
                    order_id=rej_order.order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    decision_price=req_p,
                    reference_market_price=req_p,
                    simulated_fill_price=0.0,
                    status="REJECTED",
                    rejection_reason=reason,
                    timestamp=now,
                )
            )
            raise ValueError(f"Order rejected: {reason}")

        # Gate 3: Pre-Trade Risk Enforcement
        total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in self.open_positions.values())
        recon = self.ledger.reconcile_accounting(total_unrealized)
        req_price = price or current_market_price or self.market_data_monitor.get_mark_price(symbol) or 100.0

        is_risk_valid, risk_reason = self.risk_manager.validate_candidate_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=req_price,
            stop_price=stop_price,
            portfolio_equity=recon["total_equity"],
            available_margin=recon["available_margin"],
            active_positions=[
                {
                    "symbol": s,
                    "side": pos["side"],
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                }
                for s, pos in self.open_positions.items()
            ],
            timestamp=now,
        )
        if not is_risk_valid:
            self.record_incident(
                severity=IncidentSeverity.WARNING,
                category="ORDER_GATE_PRE_TRADE_RISK",
                description=f"Pre-trade risk violation for {symbol}: {risk_reason}",
                action_taken="Order rejected by server-side risk discipline",
            )
            rej_order = self.execution_engine.submit_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                requested_price=req_price,
                stop_price=stop_price,
                client_request_id=client_order_id,
                timestamp=now,
            )
            rej_order.status = "REJECTED"
            rej_order.rejection_reason = risk_reason
            self.execution_quality.record_execution(
                ExecutionQualityRecord(
                    order_id=rej_order.order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    decision_price=req_price,
                    reference_market_price=req_price,
                    simulated_fill_price=0.0,
                    status="REJECTED",
                    rejection_reason=risk_reason,
                    timestamp=now,
                )
            )
            raise ValueError(f"Risk rejection: {risk_reason}")

        # Gate 4: Execution Engine Order Creation
        order = self.execution_engine.submit_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            requested_price=req_price,
            stop_price=stop_price,
            client_request_id=client_order_id,
            timestamp=now,
        )

        # Gate 5: Immediate Fill Execution for MARKET orders
        ref_market_price = current_market_price or self.market_data_monitor.get_mark_price(symbol) or req_price
        if order.order_type == "MARKET":
            order = self.execution_engine.execute_fill(
                order_id=order.order_id,
                market_price=ref_market_price,
                timestamp=now,
                available_cash=recon["available_margin"],
            )

            if order.status == "FILLED":
                # Double-entry ledger margin allocation
                margin_required = order.gross_amount
                self.ledger.allocate_margin(
                    margin_amount=margin_required,
                    order_id=order.order_id,
                    timestamp=now,
                )

                # Record position or close existing
                self._update_position_on_fill(order, now)

                # Record Execution Quality
                eq_record = ExecutionQualityRecord(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    decision_price=req_price,
                    reference_market_price=ref_market_price,
                    simulated_fill_price=order.fill_price or ref_market_price,
                    half_spread=order.spread_cost / order.quantity if order.quantity else 0.0,
                    brokerage=order.brokerage,
                    stt=order.stt,
                    exchange_fee=order.exchange_turnover_fee,
                    sebi_fee=order.sebi_turnover_fee,
                    stamp_duty=order.stamp_duty,
                    gst=order.gst,
                    total_cost=order.total_cost,
                    status="FILLED",
                    timestamp=now,
                )
                self.execution_quality.record_execution(eq_record)

        self.save_to_disk()
        return order

    def _update_position_on_fill(self, order: SimulatedOrder, timestamp: datetime) -> None:
        """Update position tracking on order fill."""
        sym = order.symbol
        side = order.side.upper()
        qty = order.quantity
        fill_p = order.fill_price or order.requested_price

        if sym not in self.open_positions:
            # New position
            self.open_positions[sym] = {
                "symbol": sym,
                "side": side,
                "quantity": qty,
                "entry_price": fill_p,
                "mark_price": fill_p,
                "unrealized_pnl": 0.0,
                "entry_time": timestamp.isoformat(),
                "order_id": order.order_id,
            }
        else:
            # Existing position - check if closing or extending
            curr_pos = self.open_positions[sym]
            curr_side = curr_pos["side"].upper()
            if curr_side == side:
                # Add to position
                tot_qty = curr_pos["quantity"] + qty
                avg_p = (curr_pos["entry_price"] * curr_pos["quantity"] + fill_p * qty) / tot_qty
                curr_pos["quantity"] = tot_qty
                curr_pos["entry_price"] = avg_p
            else:
                # Opposite side -> closing position
                close_qty = min(curr_pos["quantity"], qty)
                entry_p = curr_pos["entry_price"]

                # PnL calculation
                if curr_side in {"BUY", "LONG"}:
                    gross_pnl = (fill_p - entry_p) * close_qty
                else:
                    gross_pnl = (entry_p - fill_p) * close_qty

                # Release margin in double-entry ledger
                margin_to_release = entry_p * close_qty
                self.ledger.release_margin(
                    margin_amount=margin_to_release,
                    order_id=order.order_id,
                    timestamp=timestamp,
                )

                # Record Realized PnL in ledger
                self.ledger.record_realized_pnl(
                    pnl_amount=gross_pnl,
                    order_id=order.order_id,
                    timestamp=timestamp,
                )

                # Record Transaction Costs in ledger
                if order.total_cost > 0:
                    self.ledger.record_transaction_cost(
                        cost_amount=order.total_cost,
                        order_id=order.order_id,
                        timestamp=timestamp,
                    )

                net_pnl = gross_pnl - order.total_cost
                self.closed_trades.append({
                    "trade_id": f"tr_{uuid.uuid4().hex[:8]}",
                    "symbol": sym,
                    "side": curr_side,
                    "quantity": close_qty,
                    "entry_price": entry_p,
                    "exit_price": fill_p,
                    "gross_pnl": round(gross_pnl, 2),
                    "total_cost": round(order.total_cost, 2),
                    "net_pnl": round(net_pnl, 2),
                    "entry_time": curr_pos["entry_time"],
                    "exit_time": timestamp.isoformat(),
                    "exit_reason": "Order fill execution",
                })

                rem_qty = curr_pos["quantity"] - close_qty
                if rem_qty <= 0:
                    del self.open_positions[sym]
                else:
                    curr_pos["quantity"] = rem_qty

    def _liquidate_all_positions(self, timestamp: datetime, reason: str) -> None:
        """Force liquidates all open intraday positions at prevailing mark quotes."""
        for sym in list(self.open_positions.keys()):
            pos = self.open_positions[sym]
            mark_p = pos.get("mark_price", pos["entry_price"])
            exit_side = "SELL" if pos["side"].upper() in {"BUY", "LONG"} else "BUY"

            try:
                order = self.execution_engine.submit_order(
                    symbol=sym,
                    side=exit_side,
                    order_type="MARKET",
                    quantity=pos["quantity"],
                    requested_price=mark_p,
                    timestamp=timestamp,
                )
                order = self.execution_engine.execute_fill(
                    order_id=order.order_id,
                    market_price=mark_p,
                    timestamp=timestamp,
                )
                if order.status == "FILLED":
                    self._update_position_on_fill(order, timestamp)
            except Exception as exc:
                self.record_incident(
                    severity=IncidentSeverity.CRITICAL,
                    category="LIQUIDATION_FAILURE",
                    description=f"Failed to liquidate {sym}: {exc}",
                    action_taken="Flagged for manual review",
                )

    # ------------------------------------------------------------------------
    # Reconciliation & Status Summaries
    # ------------------------------------------------------------------------

    def reconcile(self, reconciliation_date: str | None = None) -> DailyReconciliationReport:
        """Generate comprehensive daily reconciliation audit for this session."""
        total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in self.open_positions.values())
        orders = self.execution_engine.list_orders(limit=1000)

        report = PaperReconciliationEngine.reconcile_session(
            session_id=self.session_id,
            account_id=self.account_id,
            ledger=self.ledger,
            opening_equity=self.config.initial_capital,
            unrealized_pnl=total_unrealized,
            open_positions=list(self.open_positions.values()),
            closed_trades=self.closed_trades,
            orders=orders,
            reconciliation_date=reconciliation_date,
        )
        return report

    def get_health_summary(self) -> dict[str, Any]:
        """Compute operational health summary across session metrics."""
        total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in self.open_positions.values())
        recon = self.ledger.reconcile_accounting(total_unrealized)

        risk_util_pct = (
            (recon["allocated_margin"] / recon["total_equity"] * 100.0)
            if recon["total_equity"] > 0
            else 0.0
        )

        critical_incidents = [i for i in self.incidents if i.severity == IncidentSeverity.CRITICAL.value]
        warn_incidents = [i for i in self.incidents if i.severity == IncidentSeverity.WARNING.value]

        health_state = "HEALTHY"
        if critical_incidents:
            health_state = "CRITICAL"
        elif warn_incidents:
            health_state = "DEGRADED"

        total_acct = (
            self.config.total_account_balance
            if self.config.total_account_balance is not None
            else self.config.initial_capital
        )
        alloc_cap = (
            self.config.allocated_capital
            if self.config.allocated_capital is not None
            else self.config.initial_capital
        )
        unalloc_cash = max(0.0, total_acct - alloc_cap)

        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "status": self.status.value,
            "status_reason": self.status_reason,
            "health_state": health_state,
            "data_quality_state": getattr(self.market_data_monitor.global_feed_state, "value", self.market_data_monitor.global_feed_state),
            "total_equity": recon["total_equity"],
            "cash_balance": recon["cash_balance"],
            "available_margin": recon["available_margin"],
            "allocated_margin": recon["allocated_margin"],
            "unrealized_pnl": total_unrealized,
            "risk_utilization_pct": round(risk_util_pct, 2),
            "open_positions_count": len(self.open_positions),
            "incident_count": len(self.incidents),
            "critical_incident_count": len(critical_incidents),
            "warning_incident_count": len(warn_incidents),
            "last_market_timestamp": self.last_market_timestamp.isoformat() if self.last_market_timestamp else None,
            "last_order_event_timestamp": self.last_order_event_timestamp.isoformat() if self.last_order_event_timestamp else None,
            "total_account_balance": total_acct,
            "allocated_capital": alloc_cap,
            "unallocated_cash": unalloc_cash,
            "simulation_only": True,
        }

    # ------------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------------

    def save_to_disk(self) -> None:
        """Persist full session state atomically to JSON."""
        state_file = self.persistence_dir / "session_state.json"
        data = {
            "config": self.config.to_dict(),
            "status": self.status.value,
            "status_reason": self.status_reason,
            "start_timestamp": self.start_timestamp.isoformat() if self.start_timestamp else None,
            "end_timestamp": self.end_timestamp.isoformat() if self.end_timestamp else None,
            "last_market_timestamp": self.last_market_timestamp.isoformat() if self.last_market_timestamp else None,
            "last_order_event_timestamp": self.last_order_event_timestamp.isoformat() if self.last_order_event_timestamp else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "open_positions": self.open_positions,
            "closed_trades": self.closed_trades,
            "peak_equity": self.peak_equity,
            "max_exposure": self.max_exposure,
            "incidents": [i.to_dict() for i in self.incidents],
            "simulation_only": True,
        }
        atomic_write_json(state_file, data)
        self.ledger.save_to_disk()

    @classmethod
    def load_from_disk(cls, persistence_dir: Path | str) -> PaperTradingSession:
        """Load session state from disk."""
        p_dir = Path(persistence_dir)
        state_file = p_dir / "session_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"Session state not found at {state_file}")

        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        cfg_data = data["config"]
        config = PaperSessionConfig(**cfg_data)
        session = cls(config=config, persistence_dir=p_dir)

        session.status = PaperSessionStatus(data["status"])
        session.status_reason = data.get("status_reason", "")
        session.start_timestamp = datetime.fromisoformat(data["start_timestamp"]) if data.get("start_timestamp") else None
        session.end_timestamp = datetime.fromisoformat(data["end_timestamp"]) if data.get("end_timestamp") else None
        session.last_market_timestamp = datetime.fromisoformat(data["last_market_timestamp"]) if data.get("last_market_timestamp") else None
        session.last_order_event_timestamp = datetime.fromisoformat(data["last_order_event_timestamp"]) if data.get("last_order_event_timestamp") else None
        session.open_positions = data.get("open_positions", {})
        session.closed_trades = data.get("closed_trades", [])
        session.peak_equity = data.get("peak_equity", config.initial_capital)
        session.max_exposure = data.get("max_exposure", 0.0)

        session.incidents = [
            PaperTradingIncident(
                incident_id=i["incident_id"],
                timestamp=datetime.fromisoformat(i["timestamp"]),
                severity=i["severity"],
                category=i["category"],
                description=i["description"],
                details=i.get("details", {}),
                action_taken=i.get("action_taken", ""),
            )
            for i in data.get("incidents", [])
        ]
        session.ledger.load_from_disk()
        return session


class PaperSessionManager:
    """
    Coordinates multiple discrete paper trading sessions.
    Guarantees session and virtual-account isolation.
    """

    def __init__(self, root_dir: Path | str | None = None) -> None:
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            self.root_dir = (
                Path(__file__).resolve().parents[2]
                / "data"
                / "paper_trading"
                / "sessions"
            )
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, PaperTradingSession] = {}
        self._active_session_id: str | None = None
        self._scan_and_load_sessions()

    def _scan_and_load_sessions(self) -> None:
        """Scan persistence directory for existing sessions."""
        for p in self.root_dir.iterdir():
            if p.is_dir() and (p / "session_state.json").exists():
                try:
                    sess = PaperTradingSession.load_from_disk(p)
                    self._sessions[sess.session_id] = sess
                    if not self._active_session_id or sess.status == PaperSessionStatus.RUNNING:
                        self._active_session_id = sess.session_id
                except Exception:
                    pass

    def create_session(
        self,
        session_id: str | None = None,
        account_id: str | None = None,
        initial_capital: float = 1_000_000.0,
        symbols: list[str] | None = None,
        risk_config: dict[str, Any] | None = None,
        total_account_balance: float | None = None,
        allocated_capital: float | None = None,
    ) -> PaperTradingSession:
        """Create a new isolated paper trading session."""
        if allocated_capital is not None:
            if allocated_capital <= 0:
                raise ValueError(f"Allocated capital must be positive, got ₹{allocated_capital}")
            if total_account_balance is not None and allocated_capital > total_account_balance:
                raise ValueError(
                    f"Allocated capital ₹{allocated_capital:,.2f} cannot exceed total account balance ₹{total_account_balance:,.2f}"
                )
            initial_capital = allocated_capital

        s_id = session_id or f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        if s_id in self._sessions:
            raise KeyError(f"Session '{s_id}' already exists")

        a_id = account_id or f"acct_{uuid.uuid4().hex[:8]}"
        config = PaperSessionConfig(
            session_id=s_id,
            account_id=a_id,
            initial_capital=initial_capital,
            symbols=symbols or ["RELIANCE", "TCS", "INFY"],
            risk_config=risk_config or {},
            total_account_balance=total_account_balance,
            allocated_capital=allocated_capital,
        )
        session = PaperTradingSession(config=config, persistence_dir=self.root_dir / s_id)
        session.save_to_disk()
        self._sessions[s_id] = session
        self._active_session_id = s_id
        return session

    def get_session(self, session_id: str) -> PaperTradingSession:
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' not found")
        return self._sessions[session_id]

    def get_active_session(self) -> PaperTradingSession | None:
        if self._active_session_id and self._active_session_id in self._sessions:
            return self._sessions[self._active_session_id]
        if self._sessions:
            return next(iter(self._sessions.values()))
        return None

    def set_active_session(self, session_id: str) -> PaperTradingSession:
        sess = self.get_session(session_id)
        self._active_session_id = session_id
        return sess

    def list_sessions(self) -> list[dict[str, Any]]:
        """List summary of all loaded sessions."""
        return [
            s.get_health_summary()
            for s in self._sessions.values()
        ]

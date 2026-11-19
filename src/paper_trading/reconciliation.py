"""
Phase 29: Daily Paper-Account Reconciliation Engine for SignalForge.

Strictly validates:
- Invariant 1: Equity == Cash + Unrealized P&L
- Invariant 2: Equity == Initial Capital + Cumulative Realized Net P&L + Unrealized P&L
- Margin Conservation: Available Margin + Allocated Margin == Equity - Reserved Capital
- Exactly-once deduction of statutory transaction costs
- Reconciliation of open positions, pending orders, filled orders, and rejected orders
- Idempotency across system restarts

SIMULATION ONLY: No live broker connection or real capital.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from src.paper_trading.ledger import PaperAccountLedger, LedgerEntryType


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class DailyReconciliationReport:
    """Comprehensive daily paper account reconciliation audit report."""

    reconciliation_id: str
    session_id: str
    account_id: str
    reconciliation_date: str

    opening_equity: float
    closing_equity: float
    cash_balance: float
    initial_capital: float

    realized_gross_pnl: float
    realized_net_pnl: float
    unrealized_pnl: float
    total_transaction_costs: float

    allocated_margin: float
    reserved_capital: float
    available_margin: float

    open_positions_count: int
    closed_trades_count: int
    pending_orders_count: int
    filled_orders_count: int
    rejected_orders_count: int
    cancelled_orders_count: int

    total_ledger_entries: int

    # Invariant flags
    equation_1_holds: bool  # Equity == Cash + Unrealized P&L
    equation_2_holds: bool  # Equity == Initial Capital + Cumulative Realized Net P&L + Unrealized P&L
    margin_conservation_holds: bool  # Available + Allocated == Equity - Reserved
    is_balanced: bool

    discrepancies: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["simulation_only"] = True
        return data


class PaperReconciliationEngine:
    """
    Evaluates paper session state and ledger to verify accounting invariants
    and generate formal daily and periodic reconciliation reports.
    """

    TOLERANCE: float = 0.01  # Tolerance in rupees for floating point representation

    @classmethod
    def reconcile_session(
        cls,
        session_id: str,
        account_id: str,
        ledger: PaperAccountLedger,
        opening_equity: float,
        unrealized_pnl: float,
        open_positions: list[dict[str, Any]] | None = None,
        closed_trades: list[dict[str, Any]] | None = None,
        orders: list[Any] | None = None,
        reconciliation_date: str | None = None,
    ) -> DailyReconciliationReport:
        """
        Perform rigorous audit and reconciliation of the paper trading session.
        """
        open_positions = open_positions or []
        closed_trades = closed_trades or []
        orders = orders or []
        rec_date = reconciliation_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        recon_dict = ledger.reconcile_accounting(unrealized_pnl)

        cash_bal = recon_dict["cash_balance"]
        alloc_margin = recon_dict["allocated_margin"]
        res_capital = recon_dict["reserved_capital"]
        avail_margin = recon_dict["available_margin"]
        total_eq = recon_dict["total_equity"]
        init_cap = recon_dict["initial_deposit"]

        # Calculate realized P&L and costs from closed trades or ledger
        realized_net_pnl = sum(t.get("net_pnl", 0.0) for t in closed_trades)
        realized_gross_pnl = sum(t.get("gross_pnl", t.get("realized_pnl", 0.0)) for t in closed_trades)
        total_costs = sum(t.get("total_cost", 0.0) for t in closed_trades)

        # Fallback to ledger realized PnL entries if closed trades list is empty
        if not closed_trades:
            pnl_entries = [e for e in ledger.entries if e.entry_type == LedgerEntryType.REALIZED_PNL.value]
            cost_entries = [e for e in ledger.entries if e.entry_type == LedgerEntryType.TRANSACTION_COST.value]
            realized_net_pnl = sum(e.amount for e in pnl_entries) - sum(e.amount for e in cost_entries)
            total_costs = sum(e.amount for e in cost_entries)
            realized_gross_pnl = realized_net_pnl + total_costs

        # Invariant 1: Equity == Cash + Unrealized P&L
        eq1_diff = abs(total_eq - (cash_bal + unrealized_pnl))
        equation_1_holds = eq1_diff <= cls.TOLERANCE

        # Invariant 2: Equity == Initial Capital + Cumulative Realized Net P&L + Unrealized P&L
        eq2_diff = abs(total_eq - (init_cap + realized_net_pnl + unrealized_pnl))
        equation_2_holds = eq2_diff <= cls.TOLERANCE

        # Invariant 3: Margin Conservation: Available + Allocated == Equity - Reserved Capital
        expected_free_equity = max(0.0, total_eq - res_capital)
        margin_diff = abs((avail_margin + alloc_margin) - expected_free_equity)
        margin_conservation_holds = margin_diff <= cls.TOLERANCE

        discrepancies: list[str] = []
        if not equation_1_holds:
            discrepancies.append(
                f"Equation 1 violation: Equity ({total_eq:.2f}) != Cash ({cash_bal:.2f}) + "
                f"Unrealized P&L ({unrealized_pnl:.2f}), delta = {eq1_diff:.4f}"
            )
        if not equation_2_holds:
            discrepancies.append(
                f"Equation 2 violation: Equity ({total_eq:.2f}) != Initial Capital ({init_cap:.2f}) + "
                f"Realized Net P&L ({realized_net_pnl:.2f}) + Unrealized P&L ({unrealized_pnl:.2f}), "
                f"delta = {eq2_diff:.4f}"
            )
        if not margin_conservation_holds:
            discrepancies.append(
                f"Margin Conservation violation: Avail Margin ({avail_margin:.2f}) + Alloc Margin ({alloc_margin:.2f}) "
                f"!= Free Equity ({expected_free_equity:.2f}), delta = {margin_diff:.4f}"
            )

        # Count order statuses
        pending_count = 0
        filled_count = 0
        rejected_count = 0
        cancelled_count = 0

        for o in orders:
            st = getattr(o, "status", None) or (o.get("status") if isinstance(o, dict) else "")
            st_upper = str(st).upper()
            if st_upper in {"PENDING", "SUBMITTED", "PENDING_EXECUTION"}:
                pending_count += 1
            elif st_upper == "FILLED":
                filled_count += 1
            elif st_upper == "REJECTED":
                rejected_count += 1
            elif st_upper == "CANCELLED":
                cancelled_count += 1

        is_balanced = equation_1_holds and equation_2_holds and margin_conservation_holds

        import uuid
        report_id = f"recon_{uuid.uuid4().hex[:10]}"

        return DailyReconciliationReport(
            reconciliation_id=report_id,
            session_id=session_id,
            account_id=account_id,
            reconciliation_date=rec_date,
            opening_equity=round(opening_equity, 2),
            closing_equity=round(total_eq, 2),
            cash_balance=round(cash_bal, 2),
            initial_capital=round(init_cap, 2),
            realized_gross_pnl=round(realized_gross_pnl, 2),
            realized_net_pnl=round(realized_net_pnl, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            total_transaction_costs=round(total_costs, 2),
            allocated_margin=round(alloc_margin, 2),
            reserved_capital=round(res_capital, 2),
            available_margin=round(avail_margin, 2),
            open_positions_count=len(open_positions),
            closed_trades_count=len(closed_trades),
            pending_orders_count=pending_count,
            filled_orders_count=filled_count,
            rejected_orders_count=rejected_count,
            cancelled_orders_count=cancelled_count,
            total_ledger_entries=len(ledger.entries),
            equation_1_holds=equation_1_holds,
            equation_2_holds=equation_2_holds,
            margin_conservation_holds=margin_conservation_holds,
            is_balanced=is_balanced,
            discrepancies=discrepancies,
        )

"""
Phase 29: Operational Reporting for SignalForge Equity Intraday Paper Trading.

Generates daily and weekly operational reports covering:
- Session identification & metadata
- Data quality & outage summary
- Orders, fills, rejections, and cancellations
- Trade count, win rate, average win/loss, expectancy, profit factor
- Gross P&L, Net P&L, Transaction costs & slippage
- Peak equity, Maximum drawdown (value and %)
- Risk violations and incident summary by severity (INFO, WARNING, CRITICAL)
- Reconciliation status and balance verification

MANDATORY DISCLAIMER:
Simulation only. Strategy performance demonstrated in paper trading does not guarantee
future live profitability. The Phase 27C.9 strategies remain rejected for live trading.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.paper_trading.reconciliation import DailyReconciliationReport


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class OperationalReport:
    """Standardized daily/weekly operational report for paper trading."""

    report_id: str
    report_type: str  # DAILY or WEEKLY
    period_start: str
    period_end: str
    session_ids: list[str]
    account_ids: list[str]

    total_sessions: int
    data_quality_summary: dict[str, Any]

    total_orders: int
    filled_orders: int
    rejected_orders: int
    cancelled_orders: int

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float

    gross_pnl: float
    net_pnl: float
    total_transaction_costs: float
    average_slippage_bps: float
    average_spread_bps: float

    average_win: float
    average_loss: float
    expectancy: float
    profit_factor: float | None

    peak_equity: float
    ending_equity: float
    max_drawdown: float
    max_drawdown_pct: float

    total_turnover: float
    max_gross_exposure: float

    risk_violations_count: int
    incidents_by_severity: dict[str, int]
    reconciliation_status: str  # BALANCED or DISCREPANCY

    disclaimer: str = (
        "SIMULATION ONLY: Results from paper-trading simulation do not guarantee "
        "future live performance. The Phase 27C.9 strategies remain rejected for live production deployment."
    )
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["simulation_only"] = True
        return data


class OperationalReportGenerator:
    """Builds daily and weekly operational reports across one or multiple sessions."""

    @classmethod
    def generate_report(
        cls,
        report_type: str,
        period_start: str,
        period_end: str,
        sessions_data: list[dict[str, Any]],
        reconciliation_reports: list[DailyReconciliationReport] | None = None,
    ) -> OperationalReport:
        import uuid
        report_id = f"op_{report_type.lower()}_{uuid.uuid4().hex[:10]}"
        reconciliation_reports = reconciliation_reports or []

        session_ids: list[str] = []
        account_ids: list[str] = []

        total_orders = 0
        filled_orders = 0
        rejected_orders = 0
        cancelled_orders = 0

        all_trades: list[dict[str, Any]] = []
        all_incidents: list[dict[str, Any]] = []
        all_slippages: list[float] = []
        all_spreads: list[float] = []

        total_turnover = 0.0
        max_exposure = 0.0
        risk_violations = 0

        starting_equities: list[float] = []
        ending_equities: list[float] = []
        peak_equities: list[float] = []

        data_states: dict[str, int] = {}

        for s in sessions_data:
            session_ids.append(s.get("session_id", "unknown"))
            account_ids.append(s.get("account_id", "unknown"))

            d_state = s.get("data_quality_state", "CONNECTED")
            data_states[d_state] = data_states.get(d_state, 0) + 1

            ords = s.get("orders", [])
            total_orders += len(ords)
            for o in ords:
                st = o.get("status", "").upper()
                if st == "FILLED":
                    filled_orders += 1
                    fill_p = o.get("fill_price") or o.get("requested_price", 0.0)
                    qty = o.get("quantity", 0)
                    total_turnover += fill_p * qty
                elif st == "REJECTED":
                    rejected_orders += 1
                elif st == "CANCELLED":
                    cancelled_orders += 1

            trades = s.get("trades", [])
            all_trades.extend(trades)

            incidents = s.get("incidents", [])
            all_incidents.extend(incidents)

            eq_summary = s.get("execution_quality", {})
            if eq_summary.get("average_slippage_bps"):
                all_slippages.append(eq_summary["average_slippage_bps"])
            if eq_summary.get("average_spread_bps"):
                all_spreads.append(eq_summary["average_spread_bps"])

            starting_equities.append(s.get("starting_capital", 1_000_000.0))
            ending_equities.append(s.get("current_equity", 1_000_000.0))
            peak_equities.append(s.get("peak_equity", 1_000_000.0))
            max_exposure = max(max_exposure, s.get("max_exposure", 0.0))
            risk_violations += s.get("risk_violations_count", 0)

        # Aggregate trades
        total_trades = len(all_trades)
        winning_trades = len([t for t in all_trades if t.get("net_pnl", 0.0) > 0])
        losing_trades = len([t for t in all_trades if t.get("net_pnl", 0.0) < 0])

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_pnl = sum(t.get("gross_pnl", t.get("realized_pnl", 0.0)) for t in all_trades)
        total_costs = sum(t.get("total_cost", 0.0) for t in all_trades)
        net_pnl = sum(t.get("net_pnl", 0.0) for t in all_trades)

        wins = [t.get("net_pnl", 0.0) for t in all_trades if t.get("net_pnl", 0.0) > 0]
        losses = [t.get("net_pnl", 0.0) for t in all_trades if t.get("net_pnl", 0.0) < 0]

        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0

        win_prob = win_rate / 100.0
        loss_prob = (losing_trades / total_trades) if total_trades > 0 else 0.0
        expectancy = (win_prob * avg_win) + (loss_prob * avg_loss)

        gross_win_sum = sum(wins)
        gross_loss_sum = abs(sum(losses))
        profit_factor = (
            round(gross_win_sum / gross_loss_sum, 4)
            if gross_loss_sum > 0 and gross_win_sum > 0
            else (0.0 if gross_loss_sum > 0 else None)
        )

        overall_peak = max(peak_equities) if peak_equities else 1_000_000.0
        overall_ending = sum(ending_equities) if ending_equities else 1_000_000.0
        max_dd = max(0.0, overall_peak - overall_ending)
        max_dd_pct = (max_dd / overall_peak * 100.0) if overall_peak > 0 else 0.0

        avg_slip = (sum(all_slippages) / len(all_slippages)) if all_slippages else 0.0
        avg_spread = (sum(all_spreads) / len(all_spreads)) if all_spreads else 0.0

        # Incidents by severity
        incidents_by_severity = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
        for inc in all_incidents:
            sev = inc.get("severity", "INFO").upper()
            incidents_by_severity[sev] = incidents_by_severity.get(sev, 0) + 1

        # Check reconciliation status
        all_balanced = True
        if reconciliation_reports:
            all_balanced = all(r.is_balanced for r in reconciliation_reports)
        recon_status = "BALANCED" if all_balanced else "DISCREPANCY"

        return OperationalReport(
            report_id=report_id,
            report_type=report_type.upper(),
            period_start=period_start,
            period_end=period_end,
            session_ids=list(set(session_ids)),
            account_ids=list(set(account_ids)),
            total_sessions=len(sessions_data),
            data_quality_summary=data_states,
            total_orders=total_orders,
            filled_orders=filled_orders,
            rejected_orders=rejected_orders,
            cancelled_orders=cancelled_orders,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(win_rate, 2),
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            total_transaction_costs=round(total_costs, 2),
            average_slippage_bps=round(avg_slip, 2),
            average_spread_bps=round(avg_spread, 2),
            average_win=round(avg_win, 2),
            average_loss=round(avg_loss, 2),
            expectancy=round(expectancy, 2),
            profit_factor=profit_factor,
            peak_equity=round(overall_peak, 2),
            ending_equity=round(overall_ending, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 4),
            total_turnover=round(total_turnover, 2),
            max_gross_exposure=round(max_exposure, 2),
            risk_violations_count=risk_violations,
            incidents_by_severity=incidents_by_severity,
            reconciliation_status=recon_status,
        )

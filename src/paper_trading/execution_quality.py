"""
Phase 29: Simulated Execution Quality Analytics for SignalForge Equity Intraday.

Tracks and analyzes:
- Decision price (price at signal/decision generation)
- Reference market price (prevailing market quote at order placement)
- Simulated fill price (causal fill price including half-spread and adverse slippage)
- Market movement between decision and reference quote
- Adverse execution slippage in basis points
- Half-spread impact in basis points
- Statutory regulatory cost breakdown (Brokerage, STT, Exchange fee, SEBI fee, Stamp duty, GST)
- Latency (order-to-fill simulation time)
- Rejection reasons

SIMULATION ONLY: This module measures simulated execution quality within the deterministic
simulation framework. It does not connect to or represent live broker execution.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class ExecutionQualityRecord:
    """Execution quality record for a single simulated order."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: int

    decision_price: float
    reference_market_price: float
    simulated_fill_price: float

    # Decomposed price movements
    market_movement: float = 0.0  # reference - decision (or reverse for short)
    market_movement_bps: float = 0.0
    slippage: float = 0.0  # adverse slippage: fill - reference (long) or reference - fill (short)
    slippage_bps: float = 0.0
    half_spread: float = 0.0
    half_spread_bps: float = 0.0

    # Statutory transaction costs
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_fee: float = 0.0
    sebi_fee: float = 0.0
    stamp_duty: float = 0.0
    gst: float = 0.0
    total_statutory_cost: float = 0.0
    total_cost: float = 0.0  # statutory fees + slippage + spread cost

    status: str = "FILLED"
    rejection_reason: str | None = None
    simulated_latency_ms: float = 5.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.timestamp = _ensure_utc(self.timestamp)
        if self.reference_market_price > 0 and self.simulated_fill_price > 0:
            ref = self.reference_market_price
            dec = self.decision_price if self.decision_price > 0 else ref
            fill = self.simulated_fill_price

            if self.side.upper() in {"BUY", "LONG"}:
                self.market_movement = ref - dec
                self.slippage = fill - (ref + self.half_spread)
            else:
                self.market_movement = dec - ref
                self.slippage = (ref - self.half_spread) - fill

            self.market_movement_bps = (self.market_movement / dec * 10000.0) if dec > 0 else 0.0
            self.slippage_bps = (abs(self.slippage) / ref * 10000.0) if ref > 0 else 0.0
            self.half_spread_bps = (self.half_spread / ref * 10000.0) if ref > 0 else 0.0

        self.total_statutory_cost = (
            self.brokerage
            + self.stt
            + self.exchange_fee
            + self.sebi_fee
            + self.stamp_duty
            + self.gst
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["simulation_only"] = True
        return data


class ExecutionQualityAnalyzer:
    """Aggregates and analyzes simulated execution quality records."""

    def __init__(self) -> None:
        self._records: list[ExecutionQualityRecord] = []

    def record_execution(self, record: ExecutionQualityRecord) -> None:
        self._records.append(record)

    @property
    def records(self) -> list[ExecutionQualityRecord]:
        return list(self._records)

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregate execution quality and cost decomposition metrics."""
        filled_records = [r for r in self._records if r.status == "FILLED"]
        rejected_records = [r for r in self._records if r.status == "REJECTED"]
        cancelled_records = [r for r in self._records if r.status == "CANCELLED"]

        total_orders = len(self._records)
        filled_count = len(filled_records)
        rejected_count = len(rejected_records)
        cancelled_count = len(cancelled_records)

        fill_rate_pct = (filled_count / total_orders * 100.0) if total_orders > 0 else 0.0

        if not filled_records:
            return {
                "total_orders": total_orders,
                "filled_orders": filled_count,
                "rejected_orders": rejected_count,
                "cancelled_orders": cancelled_count,
                "fill_rate_pct": 0.0,
                "average_slippage_bps": 0.0,
                "median_slippage_bps": 0.0,
                "max_slippage_bps": 0.0,
                "average_spread_bps": 0.0,
                "average_market_movement_bps": 0.0,
                "total_statutory_costs": 0.0,
                "total_slippage_cost": 0.0,
                "total_spread_cost": 0.0,
                "total_execution_costs": 0.0,
                "cost_decomposition_pct": {
                    "statutory_fees_pct": 0.0,
                    "slippage_pct": 0.0,
                    "spread_pct": 0.0,
                },
                "fee_breakdown": {
                    "brokerage": 0.0,
                    "stt": 0.0,
                    "exchange_fee": 0.0,
                    "sebi_fee": 0.0,
                    "stamp_duty": 0.0,
                    "gst": 0.0,
                },
                "rejection_reasons": {},
                "simulation_only": True,
            }

        slippages = [r.slippage_bps for r in filled_records]
        spreads = [r.half_spread_bps for r in filled_records]
        movements = [r.market_movement_bps for r in filled_records]

        slippages_sorted = sorted(slippages)
        mid = len(slippages_sorted) // 2
        median_slippage = (
            (slippages_sorted[mid - 1] + slippages_sorted[mid]) / 2.0
            if len(slippages_sorted) % 2 == 0
            else slippages_sorted[mid]
        )

        avg_slippage = sum(slippages) / filled_count
        max_slippage = max(slippages)
        avg_spread = sum(spreads) / filled_count
        avg_movement = sum(movements) / filled_count

        total_brokerage = sum(r.brokerage for r in filled_records)
        total_stt = sum(r.stt for r in filled_records)
        total_exchange = sum(r.exchange_fee for r in filled_records)
        total_sebi = sum(r.sebi_fee for r in filled_records)
        total_stamp = sum(r.stamp_duty for r in filled_records)
        total_gst = sum(r.gst for r in filled_records)

        total_statutory = (
            total_brokerage + total_stt + total_exchange + total_sebi + total_stamp + total_gst
        )

        total_slippage_cost = sum(
            abs(r.slippage) * r.quantity for r in filled_records
        )
        total_spread_cost = sum(
            r.half_spread * r.quantity for r in filled_records
        )
        total_exec_costs = total_statutory + total_slippage_cost + total_spread_cost

        stat_pct = (total_statutory / total_exec_costs * 100.0) if total_exec_costs > 0 else 0.0
        slip_pct = (total_slippage_cost / total_exec_costs * 100.0) if total_exec_costs > 0 else 0.0
        spread_pct = (total_spread_cost / total_exec_costs * 100.0) if total_exec_costs > 0 else 0.0

        rejection_reasons: dict[str, int] = {}
        for r in rejected_records:
            reason = r.rejection_reason or "Unknown"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        return {
            "total_orders": total_orders,
            "filled_orders": filled_count,
            "rejected_orders": rejected_count,
            "cancelled_orders": cancelled_count,
            "fill_rate_pct": round(fill_rate_pct, 2),
            "average_slippage_bps": round(avg_slippage, 2),
            "median_slippage_bps": round(median_slippage, 2),
            "max_slippage_bps": round(max_slippage, 2),
            "average_spread_bps": round(avg_spread, 2),
            "average_market_movement_bps": round(avg_movement, 2),
            "total_statutory_costs": round(total_statutory, 2),
            "total_slippage_cost": round(total_slippage_cost, 2),
            "total_spread_cost": round(total_spread_cost, 2),
            "total_execution_costs": round(total_exec_costs, 2),
            "cost_decomposition_pct": {
                "statutory_fees_pct": round(stat_pct, 2),
                "slippage_pct": round(slip_pct, 2),
                "spread_pct": round(spread_pct, 2),
            },
            "fee_breakdown": {
                "brokerage": round(total_brokerage, 2),
                "stt": round(total_stt, 2),
                "exchange_fee": round(total_exchange, 2),
                "sebi_fee": round(total_sebi, 2),
                "stamp_duty": round(total_stamp, 2),
                "gst": round(total_gst, 2),
            },
            "rejection_reasons": rejection_reasons,
            "simulation_only": True,
        }

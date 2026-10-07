"""
Centralized Realistic Transaction Cost & Slippage Engine for SignalForge (Phase 18).

Simulates:
- Brokerage (flat per order or percentage of turnover, whichever is lower)
- Securities Transaction Tax (STT)
- Exchange Transaction Charges (NSE)
- SEBI Turnover Fees
- Goods & Services Tax (GST on brokerage + exchange + SEBI charges)
- Stamp Duty (on buy side turnover)
- Deterministic Slippage (configurable basis points on entry and exit)
- Optional Spread / Execution Penalty

SIMULATION ONLY — NO REAL BROKER EXECUTION.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CostModel:
    """
    Configurable transaction cost and slippage parameters.

    Rates are expressed as decimals (e.g. 0.0003 = 0.03% = 3 bps),
    while slippage is expressed in basis points (1 bps = 0.01% = 0.0001).
    """

    config_id: str = "REALISTIC_INDIA_INTRADAY_V1"
    brokerage_per_order: float = 20.0
    brokerage_rate: float = 0.0003  # 0.03% per order capped at brokerage_per_order
    use_min_brokerage: bool = True
    stt_rate: float = 0.00025  # 0.025% on sell-side turnover
    exchange_fee_rate: float = 0.0000325  # 0.00325% on total turnover
    sebi_fee_rate: float = 0.000001  # 0.0001% (Rs 10 / crore)
    gst_rate: float = 0.18  # 18% on (brokerage + exchange_fee + sebi_fee)
    stamp_duty_rate: float = 0.00003  # 0.003% on buy-side turnover
    slippage_bps: float = 1.0  # Default 1.0 bps per leg if entry/exit not specified
    entry_slippage_bps: float | None = None
    exit_slippage_bps: float | None = None
    spread_penalty_bps: float = 0.0

    def __post_init__(self) -> None:
        for field_name in [
            "brokerage_per_order",
            "brokerage_rate",
            "stt_rate",
            "exchange_fee_rate",
            "sebi_fee_rate",
            "gst_rate",
            "stamp_duty_rate",
            "slippage_bps",
            "spread_penalty_bps",
        ]:
            val = getattr(self, field_name)
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val) or val < 0:
                raise ValueError(f"{field_name} must be a non-negative finite number, got {val}")

        for opt_field in ["entry_slippage_bps", "exit_slippage_bps"]:
            val = getattr(self, opt_field)
            if val is not None:
                if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val) or val < 0:
                    raise ValueError(f"{opt_field} must be a non-negative finite number, got {val}")

    @property
    def resolved_entry_slippage_bps(self) -> float:
        return float(self.entry_slippage_bps if self.entry_slippage_bps is not None else self.slippage_bps)

    @property
    def resolved_exit_slippage_bps(self) -> float:
        return float(self.exit_slippage_bps if self.exit_slippage_bps is not None else self.slippage_bps)

    @classmethod
    def zero(cls) -> CostModel:
        """Return a zero-cost, zero-slippage model."""
        return cls(
            config_id="ZERO_COST_MODEL",
            brokerage_per_order=0.0,
            brokerage_rate=0.0,
            use_min_brokerage=True,
            stt_rate=0.0,
            exchange_fee_rate=0.0,
            sebi_fee_rate=0.0,
            gst_rate=0.0,
            stamp_duty_rate=0.0,
            slippage_bps=0.0,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            spread_penalty_bps=0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeCostBreakdown:
    """Complete auditable cost and P&L breakdown for a single paper trade."""

    entry_signal_price: float
    actual_entry_price: float
    exit_signal_price: float
    actual_exit_price: float
    quantity: int
    side: str
    gross_pnl: float
    brokerage: float
    stt: float
    exchange_fee: float
    sebi_fee: float
    gst: float
    stamp_duty: float
    taxes_and_fees: float
    slippage_cost: float
    spread_penalty: float
    total_cost: float
    net_pnl: float
    config_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_entry_execution_price(
    signal_price: float,
    side: str,
    cost_model: CostModel,
) -> float:
    """
    Calculate deterministic entry execution price after adverse entry slippage.

    LONG (BUY): actual_entry = signal_price * (1 + entry_slippage_bps / 10000)
    SHORT (SELL): actual_entry = signal_price * (1 - entry_slippage_bps / 10000)
    """
    if signal_price <= 0 or math.isnan(signal_price) or math.isinf(signal_price):
        raise ValueError(f"Invalid signal_price: {signal_price}")

    norm_side = str(side).strip().upper()
    slip_factor = cost_model.resolved_entry_slippage_bps / 10000.0

    if norm_side in {"LONG", "BUY"}:
        return round(signal_price * (1.0 + slip_factor), 4)
    if norm_side in {"SHORT", "SELL"}:
        return round(signal_price * (1.0 - slip_factor), 4)
    raise ValueError(f"Unsupported side '{side}'")


def compute_exit_execution_price(
    signal_price: float,
    side: str,
    cost_model: CostModel,
) -> float:
    """
    Calculate deterministic exit execution price after adverse exit slippage.

    LONG position exits via SELL: actual_exit = signal_price * (1 - exit_slippage_bps / 10000)
    SHORT position exits via BUY: actual_exit = signal_price * (1 + exit_slippage_bps / 10000)
    """
    if signal_price <= 0 or math.isnan(signal_price) or math.isinf(signal_price):
        raise ValueError(f"Invalid signal_price: {signal_price}")

    norm_side = str(side).strip().upper()
    slip_factor = cost_model.resolved_exit_slippage_bps / 10000.0

    if norm_side in {"LONG", "BUY"}:
        return round(signal_price * (1.0 - slip_factor), 4)
    if norm_side in {"SHORT", "SELL"}:
        return round(signal_price * (1.0 + slip_factor), 4)
    raise ValueError(f"Unsupported side '{side}'")


def calculate_trade_costs(
    side: str,
    entry_signal_price: float,
    exit_signal_price: float,
    quantity: int,
    cost_model: CostModel | None = None,
) -> TradeCostBreakdown:
    """
    Compute complete deterministic cost, slippage, gross P&L, and net P&L breakdown.
    """
    model = cost_model or CostModel()

    if quantity <= 0:
        raise ValueError(f"quantity must be > 0, got {quantity}")

    norm_side = str(side).strip().upper()
    is_long = norm_side in {"LONG", "BUY"}
    if not is_long and norm_side not in {"SHORT", "SELL"}:
        raise ValueError(f"Invalid side: {side}")

    actual_entry = compute_entry_execution_price(entry_signal_price, norm_side, model)
    actual_exit = compute_exit_execution_price(exit_signal_price, norm_side, model)

    # Gross P&L based on unadjusted strategy signal prices
    if is_long:
        gross_pnl = (exit_signal_price - entry_signal_price) * quantity
        buy_turnover = actual_entry * quantity
        sell_turnover = actual_exit * quantity
    else:
        gross_pnl = (entry_signal_price - exit_signal_price) * quantity
        sell_turnover = actual_entry * quantity
        buy_turnover = actual_exit * quantity

    total_turnover = buy_turnover + sell_turnover

    # Slippage cost (entry + exit price degradation * quantity)
    entry_slip_cost = abs(actual_entry - entry_signal_price) * quantity
    exit_slip_cost = abs(exit_signal_price - actual_exit) * quantity
    slippage_cost = entry_slip_cost + exit_slip_cost

    # Optional spread penalty on total turnover
    spread_penalty = total_turnover * (model.spread_penalty_bps / 10000.0)

    # Brokerage per leg (entry order + exit order)
    if model.use_min_brokerage:
        entry_brok = min(model.brokerage_per_order, buy_turnover * model.brokerage_rate) if is_long else min(model.brokerage_per_order, sell_turnover * model.brokerage_rate)
        exit_brok = min(model.brokerage_per_order, sell_turnover * model.brokerage_rate) if is_long else min(model.brokerage_per_order, buy_turnover * model.brokerage_rate)
    else:
        entry_brok = model.brokerage_per_order + (buy_turnover if is_long else sell_turnover) * model.brokerage_rate
        exit_brok = model.brokerage_per_order + (sell_turnover if is_long else buy_turnover) * model.brokerage_rate

    brokerage = entry_brok + exit_brok

    # Statutory taxes and exchange fees
    stt = sell_turnover * model.stt_rate
    exchange_fee = total_turnover * model.exchange_fee_rate
    sebi_fee = total_turnover * model.sebi_fee_rate
    stamp_duty = buy_turnover * model.stamp_duty_rate
    gst = (brokerage + exchange_fee + sebi_fee) * model.gst_rate

    taxes_and_fees = stt + exchange_fee + sebi_fee + stamp_duty + gst
    total_cost = brokerage + taxes_and_fees + slippage_cost + spread_penalty
    net_pnl = gross_pnl - total_cost

    return TradeCostBreakdown(
        entry_signal_price=round(entry_signal_price, 4),
        actual_entry_price=round(actual_entry, 4),
        exit_signal_price=round(exit_signal_price, 4),
        actual_exit_price=round(actual_exit, 4),
        quantity=int(quantity),
        side="LONG" if is_long else "SHORT",
        gross_pnl=round(gross_pnl, 4),
        brokerage=round(brokerage, 4),
        stt=round(stt, 4),
        exchange_fee=round(exchange_fee, 4),
        sebi_fee=round(sebi_fee, 4),
        gst=round(gst, 4),
        stamp_duty=round(stamp_duty, 4),
        taxes_and_fees=round(taxes_and_fees, 4),
        slippage_cost=round(slippage_cost, 4),
        spread_penalty=round(spread_penalty, 4),
        total_cost=round(total_cost, 4),
        net_pnl=round(net_pnl, 4),
        config_id=model.config_id,
    )

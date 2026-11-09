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

from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    IntradayCostConfig,
    calculate_trade_transaction_costs,
)


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
    spread_penalty_bps: float = 0.5  # Default 0.5 bps to match DISCOUNT_BROKER_REALISTIC_CONFIG

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

    @classmethod
    def from_intraday_config(cls, config: IntradayCostConfig) -> CostModel:
        """Create a CostModel matching an IntradayCostConfig specification."""
        return cls(
            config_id=config.name,
            brokerage_per_order=config.brokerage_max_per_leg_inr,
            brokerage_rate=config.brokerage_rate_pct,
            use_min_brokerage=True,
            stt_rate=config.stt_rate_sell_pct,
            exchange_fee_rate=config.exchange_charge_rate_pct,
            sebi_fee_rate=config.sebi_charge_rate_pct,
            gst_rate=config.gst_rate_pct,
            stamp_duty_rate=config.stamp_duty_rate_buy_pct,
            slippage_bps=config.slippage_rate_pct * 10000.0,
            entry_slippage_bps=config.slippage_rate_pct * 10000.0,
            exit_slippage_bps=config.slippage_rate_pct * 10000.0,
            spread_penalty_bps=config.spread_rate_pct * 10000.0,
        )

    def to_intraday_cost_config(self) -> IntradayCostConfig:
        """Convert this CostModel to the canonical IntradayCostConfig."""
        return IntradayCostConfig(
            name=self.config_id,
            description="Unified paper trading cost configuration",
            brokerage_rate_pct=self.brokerage_rate,
            brokerage_max_per_leg_inr=self.brokerage_per_order,
            stt_rate_sell_pct=self.stt_rate,
            exchange_charge_rate_pct=self.exchange_fee_rate,
            sebi_charge_rate_pct=self.sebi_fee_rate,
            stamp_duty_rate_buy_pct=self.stamp_duty_rate,
            gst_rate_pct=self.gst_rate,
            slippage_rate_pct=self.resolved_entry_slippage_bps / 10000.0,
            spread_rate_pct=self.spread_penalty_bps / 10000.0,
            is_illustrative=False,
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
    Compute complete deterministic cost, slippage, gross P&L, and net P&L breakdown
    using the canonical Indian Equity Intraday Transaction Cost Engine.
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

    intraday_cfg = model.to_intraday_cost_config()
    canonical = calculate_trade_transaction_costs(
        side="LONG" if is_long else "SHORT",
        entry_price=entry_signal_price,
        exit_price=exit_signal_price,
        quantity=quantity,
        config=intraday_cfg,
    )

    return TradeCostBreakdown(
        entry_signal_price=round(entry_signal_price, 4),
        actual_entry_price=round(actual_entry, 4),
        exit_signal_price=round(exit_signal_price, 4),
        actual_exit_price=round(actual_exit, 4),
        quantity=int(quantity),
        side="LONG" if is_long else "SHORT",
        gross_pnl=round(canonical.gross_pnl, 4),
        brokerage=round(canonical.brokerage, 4),
        stt=round(canonical.stt, 4),
        exchange_fee=round(canonical.exchange_charges, 4),
        sebi_fee=round(canonical.sebi_charges, 4),
        gst=round(canonical.gst, 4),
        stamp_duty=round(canonical.stamp_duty, 4),
        taxes_and_fees=round(canonical.statutory_charges, 4),
        slippage_cost=round(canonical.slippage, 4),
        spread_penalty=round(canonical.spread_cost, 4),
        total_cost=round(canonical.total_costs, 4),
        net_pnl=round(canonical.net_pnl, 4),
        config_id=model.config_id,
    )

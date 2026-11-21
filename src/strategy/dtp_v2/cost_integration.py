"""
SignalForge — Phase 32E.1: DTP-V2 Delivery Cost Integration Adapter
===================================================================
File: src/strategy/dtp_v2/cost_integration.py

Integrates DTP-V2 with the certified Indian Equity Delivery Cost Engine
(src/backtest/indian_delivery_costs.py).

Guarantees:
  - 100% adherence to verified delivery cost classes, methods, and return types.
  - Zero modification or import of the intraday cost engine (indian_market_costs.py).
  - Explicit separation between the official ₹307/cr schedule and the hypothetical ₹317/cr stress profile.
  - Full itemization of STT, stamp duty, exchange charges, IPFT, SEBI fees, Groww brokerage, DP charges, GST, and slippage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from src.backtest.indian_delivery_costs import (
    CDSL_GROWW_FEMALE_PROFILE,
    CDSL_GROWW_MALE_PROFILE,
    CDSL_ZERODHA_PROFILE,
    CONSERVATIVE_STRESS_EXECUTION_ASSUMPTIONS,
    GROWW_DELIVERY_PROFILE,
    GROWW_DELIVERY_STRESS_317_PROFILE,
    REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    ZERO_EXECUTION_ASSUMPTIONS,
    BrokerChargeProfile,
    DeliveryCostBreakdown,
    DeliveryCostCalculator,
    DeliveryOrder,
    DepositoryChargeProfile,
    ExecutionCostAssumptions,
    OrderSide,
    RoundingMode,
    StatutoryCostSchedule,
    get_exchange_schedule,
    get_statutory_schedule,
)


@dataclass(frozen=True)
class DTPTradeCostSummary:
    """Summary of complete transaction costs and net performance for a DTP-V2 trade."""
    symbol: str
    quantity: int
    entry_price: float
    exit_price: float
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    gross_pnl: float
    total_friction_costs: float
    net_pnl: float
    net_return_pct: float
    breakeven_gross_pct: float

    # Itemized Breakdown
    total_stt: float
    total_stamp_duty: float
    exchange_charge: float
    ipft_charge: float
    sebi_turnover_fee: float
    total_brokerage: float
    total_dp_charge: float
    total_gst: float
    total_execution_friction: float

    # Audit Metadata
    is_hypothetical_override: bool
    broker_name: str
    statutory_schedule_id: str
    exchange_schedule_id: str
    notes: List[str]


def calculate_dtp_roundtrip_costs(
    symbol: str,
    isin: str,
    entry_date: date,
    exit_date: date,
    entry_price: float,
    exit_price: float,
    quantity: int,
    broker_profile: Optional[BrokerChargeProfile] = None,
    depository_profile: Optional[DepositoryChargeProfile] = None,
    execution_assumptions: Optional[ExecutionCostAssumptions] = None,
    rounding_mode: RoundingMode = RoundingMode.HALF_EVEN,
    use_stress_profile: bool = False,
    order_id_prefix: str = "DTP_V2",
) -> Tuple[DeliveryCostBreakdown, DTPTradeCostSummary]:
    """
    Computes complete, verified delivery transaction costs for a round-trip swing trade.
    Uses src/backtest/indian_delivery_costs.py without approximations.
    """
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive: {quantity}")
    if entry_price <= 0.0 or exit_price <= 0.0:
        raise ValueError(f"Prices must be positive: entry={entry_price}, exit={exit_price}")

    # Select profiles
    if broker_profile is None:
        broker_profile = GROWW_DELIVERY_STRESS_317_PROFILE if use_stress_profile else GROWW_DELIVERY_PROFILE
    if depository_profile is None:
        depository_profile = CDSL_GROWW_MALE_PROFILE
    if execution_assumptions is None:
        execution_assumptions = (
            CONSERVATIVE_STRESS_EXECUTION_ASSUMPTIONS if use_stress_profile else REALISTIC_SWING_EXECUTION_ASSUMPTIONS
        )

    # Decimal turnovers
    buy_turnover = Decimal(str(round(entry_price * quantity, 2)))
    sell_turnover = Decimal(str(round(exit_price * quantity, 2)))
    gross_pnl_dec = sell_turnover - buy_turnover

    buy_order = DeliveryOrder(
        order_id=f"{order_id_prefix}_BUY_{symbol}_{entry_date.isoformat()}",
        isin=isin,
        side=OrderSide.BUY,
        turnover=buy_turnover,
        trade_date=entry_date,
    )

    sell_order = DeliveryOrder(
        order_id=f"{order_id_prefix}_SELL_{symbol}_{exit_date.isoformat()}",
        isin=isin,
        side=OrderSide.SELL,
        turnover=sell_turnover,
        trade_date=exit_date,
    )

    breakdown = DeliveryCostCalculator.calculate_trade(
        orders=[buy_order, sell_order],
        broker_profile=broker_profile,
        depository_profile=depository_profile,
        execution_assumptions=execution_assumptions,
        statutory_schedule=get_statutory_schedule(entry_date),
        exchange_schedule=get_exchange_schedule(entry_date, exchange="NSE"),
        rounding_mode=rounding_mode,
        gross_pnl=gross_pnl_dec,
    )

    summary = DTPTradeCostSummary(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        buy_turnover=float(breakdown.buy_turnover),
        sell_turnover=float(breakdown.sell_turnover),
        total_turnover=float(breakdown.total_turnover),
        gross_pnl=float(breakdown.gross_pnl or Decimal("0")),
        total_friction_costs=float(breakdown.total_transaction_costs),
        net_pnl=float(breakdown.net_pnl or Decimal("0")),
        net_return_pct=float((breakdown.net_pnl or Decimal("0")) / breakdown.buy_turnover * Decimal("100")),
        breakeven_gross_pct=float(breakdown.breakeven_gross_pct or Decimal("0")),
        total_stt=float(breakdown.total_stt),
        total_stamp_duty=float(breakdown.total_stamp_duty),
        exchange_charge=float(breakdown.exchange_transaction_charge),
        ipft_charge=float(breakdown.ipft_charge),
        sebi_turnover_fee=float(breakdown.sebi_turnover_fee),
        total_brokerage=float(breakdown.total_brokerage),
        total_dp_charge=float(breakdown.total_dp_base),
        total_gst=float(breakdown.total_gst),
        total_execution_friction=float(breakdown.total_execution_friction),
        is_hypothetical_override=breakdown.is_hypothetical_override,
        broker_name=breakdown.broker_profile_name,
        statutory_schedule_id=breakdown.statutory_schedule_id,
        exchange_schedule_id=breakdown.exchange_schedule_id,
        notes=breakdown.notes,
    )

    return breakdown, summary


def calculate_pending_entry_costs(
    symbol: str,
    isin: str,
    entry_date: date,
    entry_price: float,
    quantity: int,
    broker_profile: Optional[BrokerChargeProfile] = None,
    execution_assumptions: Optional[ExecutionCostAssumptions] = None,
    rounding_mode: RoundingMode = RoundingMode.HALF_EVEN,
    use_stress_profile: bool = False,
    order_id_prefix: str = "DTP_V2",
) -> DeliveryCostBreakdown:
    """
    Computes verified delivery transaction costs incurred upon buy entry leg only.
    Excludes sell-side STT and DP charges until the exit leg actually occurs.
    """
    if broker_profile is None:
        broker_profile = GROWW_DELIVERY_STRESS_317_PROFILE if use_stress_profile else GROWW_DELIVERY_PROFILE
    if execution_assumptions is None:
        execution_assumptions = (
            CONSERVATIVE_STRESS_EXECUTION_ASSUMPTIONS if use_stress_profile else REALISTIC_SWING_EXECUTION_ASSUMPTIONS
        )

    buy_turnover = Decimal(str(round(entry_price * quantity, 2)))
    buy_order = DeliveryOrder(
        order_id=f"{order_id_prefix}_BUY_{symbol}_{entry_date.isoformat()}",
        isin=isin,
        side=OrderSide.BUY,
        turnover=buy_turnover,
        trade_date=entry_date,
    )

    return DeliveryCostCalculator.calculate_trade(
        orders=[buy_order],
        broker_profile=broker_profile,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=execution_assumptions,
        statutory_schedule=get_statutory_schedule(entry_date),
        exchange_schedule=get_exchange_schedule(entry_date, exchange="NSE"),
        rounding_mode=rounding_mode,
    )

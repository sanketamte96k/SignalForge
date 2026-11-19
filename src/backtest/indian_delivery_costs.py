"""
Indian Equity Delivery Transaction Cost Engine for SignalForge
==============================================================
Calculates complete statutory, regulatory, depository, brokerage, and execution
friction costs for delivery-based swing trading in Indian equities (NSE Cash):
  1. Date-aware Securities Transaction Tax (STT): 0.1% on buy and 0.1% on sell turnover.
  2. Date-aware Stamp Duty: buy-side only (0.015% national uniform from 1 July 2020;
     0.005% historical Maharashtra state rate before 1 July 2020).
  3. Date-aware NSE Exchange Transaction Charges and IPFT:
     - From 1 March 2026: ₹306.99/cr exchange + ₹0.01/cr IPFT = ₹307.00/cr total.
     - Oct 2024 to Feb 2026: ₹297.00/cr exchange + ₹10.00/cr IPFT = ₹307.00/cr total.
     - Historical baseline: 0.00325% base rate.
  4. Date-aware SEBI Turnover Fees: ₹15/cr before 1 April 2019; ₹10/cr thereafter.
  5. Date-aware GST on taxable financial services at 18%:
     - Brokerage, Exchange charges, IPFT, DP charges are taxable.
     - SEBI fees: 0% GST before 18 July 2022; 18% GST from 18 July 2022.
     - STT and Stamp Duty are strictly EXEMPT from GST.
  6. Depository Participant (DP) Charges:
     - Configurable modes: PER_EXECUTED_ORDER (Groww retail) vs PER_ISIN_PER_DAY (CDSL/Zerodha).
     - Groww Male (₹20 base = ₹3.50 CDSL + ₹16.50 Groww fee) / Female (₹19.75 base).
     - Sub-₹100 sale value waiver on Groww fee.
  7. Configurable Brokerage:
     - Groww profile: min(0.1%, ₹20), min ₹5 per executed order.
     - Zerodha profile: ₹0 delivery brokerage.
     - Hypothetical ₹317/cr stress-test override clearly marked and decoupled.
  8. Execution Friction: Slippage and Spread in bps on total turnover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderSide(str, Enum):
    """Side of the order."""
    BUY = "BUY"
    SELL = "SELL"


class DPBillingMode(str, Enum):
    """Billing aggregation mode for Depository Participant (DP) debit charges."""
    PER_EXECUTED_ORDER = "PER_EXECUTED_ORDER"  # Groww retail model: each sell order is billed
    PER_ISIN_PER_DAY = "PER_ISIN_PER_DAY"      # CDSL / Zerodha model: aggregated per ISIN per day


class RoundingMode(str, Enum):
    """Rounding mode for currency quantizations."""
    HALF_EVEN = ROUND_HALF_EVEN  # Banker's rounding (standard in financial systems)
    HALF_UP = ROUND_HALF_UP      # Commercial rounding


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeliveryOrder:
    """Represents a single order or partial execution leg in a delivery trade."""
    order_id: str
    isin: str
    side: OrderSide
    turnover: Decimal
    trade_date: date
    execution_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.turnover < Decimal("0"):
            raise ValueError(f"Order turnover cannot be negative: {self.turnover}")
        if not self.order_id:
            raise ValueError("Order ID cannot be empty")
        if not self.isin:
            raise ValueError("ISIN cannot be empty")


@dataclass(frozen=True)
class StatutoryCostSchedule:
    """Date-effective statutory taxes and sovereign duty schedule."""
    schedule_id: str
    effective_from: date
    effective_until: Optional[date]
    stt_buy_rate: Decimal          # e.g. 0.001 for 0.1%
    stt_sell_rate: Decimal         # e.g. 0.001 for 0.1%
    stamp_duty_buy_rate: Decimal   # e.g. 0.00015 for 0.015%
    stamp_duty_sell_rate: Decimal  # strictly 0 for delivery
    gst_rate: Decimal              # 0.18 for 18%
    gst_on_sebi_fees: bool         # False before 2022-07-18; True thereafter
    description: str = ""


@dataclass(frozen=True)
class ExchangeChargeSchedule:
    """Date-effective stock exchange (MII) transaction and regulatory charges."""
    schedule_id: str
    exchange: str
    effective_from: date
    effective_until: Optional[date]
    transaction_charge_rate: Decimal  # e.g. 306.99 / 1e7
    ipft_rate: Decimal                # e.g. 0.01 / 1e7
    sebi_turnover_rate: Decimal       # e.g. 10.00 / 1e7
    description: str = ""

    @property
    def combined_exchange_ipft_rate(self) -> Decimal:
        """Returns the total combined exchange outflow per side."""
        return self.transaction_charge_rate + self.ipft_rate


@dataclass(frozen=True)
class BrokerChargeProfile:
    """Broker-specific tariff configuration for delivery trading."""
    broker_name: str
    pricing_plan: str
    delivery_brokerage_rate: Decimal   # e.g. 0.001 for 0.1%
    brokerage_min_per_order: Decimal   # e.g. ₹5.00 (Groww) or ₹0.00
    brokerage_max_per_order: Decimal   # e.g. ₹20.00 or ₹0.00
    dp_billing_mode: DPBillingMode     # PER_EXECUTED_ORDER or PER_ISIN_PER_DAY
    exchange_turnover_rate_override: Optional[Decimal] = None
    is_hypothetical_override: bool = False
    override_description: Optional[str] = None


@dataclass(frozen=True)
class DepositoryChargeProfile:
    """Depository (CDSL/NSDL) and DP fee schedule."""
    depository_name: str
    profile_name: str
    broker_dp_fee: Decimal             # e.g. ₹16.50
    cdsl_fee: Decimal                  # e.g. ₹3.50 (male) or ₹3.25 (female)
    sub_100_waiver_threshold: Decimal  # e.g. ₹100.00 (Groww fee waived if turnover < ₹100)

    @property
    def total_base_dp_fee(self) -> Decimal:
        """Standard full base DP charge prior to waiver."""
        return self.broker_dp_fee + self.cdsl_fee


@dataclass(frozen=True)
class ExecutionCostAssumptions:
    """Execution friction assumptions for swing positions."""
    slippage_bps: Decimal = Decimal("0")   # e.g. Decimal("2.0") for 2.0 bps
    spread_bps: Decimal = Decimal("0")     # e.g. Decimal("1.0") for 1.0 bps


@dataclass(frozen=True)
class DeliveryCostBreakdown:
    """Complete, transparent itemized transaction cost breakdown for a delivery trade."""
    buy_turnover: Decimal
    sell_turnover: Decimal
    total_turnover: Decimal
    buy_order_count: int
    sell_order_count: int
    dp_charge_debit_count: int

    # Statutory Taxes (Exempt from GST)
    buy_stt: Decimal
    sell_stt: Decimal
    total_stt: Decimal
    buy_stamp_duty: Decimal
    sell_stamp_duty: Decimal
    total_stamp_duty: Decimal

    # Exchange & Regulatory Services (Subject to GST)
    exchange_transaction_charge: Decimal
    ipft_charge: Decimal
    combined_exchange_ipft_charge: Decimal
    sebi_turnover_fee: Decimal
    taxable_sebi_fee: Decimal

    # Broker & Depository Services (Subject to GST)
    buy_brokerage: Decimal
    sell_brokerage: Decimal
    total_brokerage: Decimal
    groww_dp_charge: Decimal
    cdsl_dp_charge: Decimal
    total_dp_base: Decimal

    # GST
    taxable_services_base: Decimal
    gst_rate: Decimal
    total_gst: Decimal

    # Execution Friction
    slippage_cost: Decimal
    spread_cost: Decimal
    total_execution_friction: Decimal

    # Aggregates
    statutory_broker_costs: Decimal
    total_transaction_costs: Decimal
    gross_pnl: Optional[Decimal]
    net_pnl: Optional[Decimal]
    breakeven_gross_pct: Optional[Decimal]

    # Audit Metadata
    statutory_schedule_id: str
    exchange_schedule_id: str
    broker_profile_name: str
    depository_profile_name: str
    dp_billing_mode: str
    is_hypothetical_override: bool
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pre-defined Schedules and Profiles
# ---------------------------------------------------------------------------

# Statutory Schedules
STATUTORY_SCHEDULE_HISTORICAL_MH = StatutoryCostSchedule(
    schedule_id="STATUTORY_MH_HISTORICAL_2017",
    effective_from=date(2017, 1, 1),
    effective_until=date(2020, 6, 30),
    stt_buy_rate=Decimal("0.001"),
    stt_sell_rate=Decimal("0.001"),
    stamp_duty_buy_rate=Decimal("0.00005"),  # 0.005% Maharashtra Article 51A
    stamp_duty_sell_rate=Decimal("0"),
    gst_rate=Decimal("0.18"),
    gst_on_sebi_fees=False,                 # Exempt before 18 July 2022
    description="Historical Maharashtra delivery schedule (0.005% stamp duty, 0% GST on SEBI)",
)

STATUTORY_SCHEDULE_MODERN_PRE_JULY2022 = StatutoryCostSchedule(
    schedule_id="STATUTORY_NATIONAL_UNIFORM_PRE2022",
    effective_from=date(2020, 7, 1),
    effective_until=date(2022, 7, 17),
    stt_buy_rate=Decimal("0.001"),
    stt_sell_rate=Decimal("0.001"),
    stamp_duty_buy_rate=Decimal("0.00015"), # 0.015% National Uniform
    stamp_duty_sell_rate=Decimal("0"),
    gst_rate=Decimal("0.18"),
    gst_on_sebi_fees=False,                 # Still exempt before 18 July 2022
    description="Uniform national schedule pre-July 2022 (0.015% stamp duty, 0% GST on SEBI)",
)

STATUTORY_SCHEDULE_MODERN = StatutoryCostSchedule(
    schedule_id="STATUTORY_NATIONAL_UNIFORM_CURRENT",
    effective_from=date(2022, 7, 18),
    effective_until=None,
    stt_buy_rate=Decimal("0.001"),
    stt_sell_rate=Decimal("0.001"),
    stamp_duty_buy_rate=Decimal("0.00015"), # 0.015% National Uniform
    stamp_duty_sell_rate=Decimal("0"),
    gst_rate=Decimal("0.18"),
    gst_on_sebi_fees=True,                  # 18% GST on SEBI fees from 18 July 2022
    description="Current uniform national schedule (0.015% stamp duty, 18% GST on SEBI)",
)


# Exchange Schedules (NSE Cash Segment)
NSE_CASH_SCHEDULE_HISTORICAL_2017 = ExchangeChargeSchedule(
    schedule_id="NSE_CASH_HISTORICAL_2017",
    exchange="NSE",
    effective_from=date(2017, 1, 1),
    effective_until=date(2019, 3, 31),
    transaction_charge_rate=Decimal("0.0000325"),          # 0.00325%
    ipft_rate=Decimal("0.01") / Decimal("10000000"),       # ₹0.01 per crore
    sebi_turnover_rate=Decimal("15.00") / Decimal("10000000"), # ₹15 per crore
    description="Historical NSE schedule 2017 to Mar 2019 (0.00325% exchange, ₹15/cr SEBI)",
)

NSE_CASH_SCHEDULE_HISTORICAL_2019 = ExchangeChargeSchedule(
    schedule_id="NSE_CASH_HISTORICAL_2019",
    exchange="NSE",
    effective_from=date(2019, 4, 1),
    effective_until=date(2023, 3, 31),
    transaction_charge_rate=Decimal("0.0000325"),          # 0.00325%
    ipft_rate=Decimal("0.01") / Decimal("10000000"),       # ₹0.01 per crore
    sebi_turnover_rate=Decimal("10.00") / Decimal("10000000"), # ₹10 per crore
    description="Historical NSE schedule Apr 2019 to Mar 2023 (₹10/cr SEBI, ₹0.01/cr IPFT)",
)

NSE_CASH_SCHEDULE_2023_Q2 = ExchangeChargeSchedule(
    schedule_id="NSE_CASH_2023_Q2",
    exchange="NSE",
    effective_from=date(2023, 4, 1),
    effective_until=date(2024, 9, 30),
    transaction_charge_rate=Decimal("0.0000325"),          # 0.00325%
    ipft_rate=Decimal("10.00") / Decimal("10000000"),      # ₹10 per crore (NSE Circular 56129)
    sebi_turnover_rate=Decimal("10.00") / Decimal("10000000"), # ₹10 per crore
    description="NSE schedule Apr 2023 to Sept 2024 (₹10/cr IPFT)",
)

NSE_CASH_SCHEDULE_2024_Q4 = ExchangeChargeSchedule(
    schedule_id="NSE_CASH_2024_Q4",
    exchange="NSE",
    effective_from=date(2024, 10, 1),
    effective_until=date(2026, 2, 28),
    transaction_charge_rate=Decimal("297.00") / Decimal("10000000"), # ₹297 per crore (True-to-Label)
    ipft_rate=Decimal("10.00") / Decimal("10000000"),                # ₹10 per crore
    sebi_turnover_rate=Decimal("10.00") / Decimal("10000000"),       # ₹10 per crore
    description="NSE True-to-Label schedule Oct 2024 to Feb 2026 (₹297 exch + ₹10 IPFT = ₹307)",
)

NSE_CASH_SCHEDULE_2026_Q1 = ExchangeChargeSchedule(
    schedule_id="NSE_CASH_2026_Q1",
    exchange="NSE",
    effective_from=date(2026, 3, 1),
    effective_until=None,
    transaction_charge_rate=Decimal("306.99") / Decimal("10000000"), # ₹306.99 per crore (NSE FA/73061)
    ipft_rate=Decimal("0.01") / Decimal("10000000"),                # ₹0.01 per crore
    sebi_turnover_rate=Decimal("10.00") / Decimal("10000000"),       # ₹10 per crore
    description="NSE schedule from 1 March 2026 (₹306.99 exch + ₹0.01 IPFT = ₹307 total)",
)


# Broker Profiles
GROWW_DELIVERY_PROFILE = BrokerChargeProfile(
    broker_name="Groww",
    pricing_plan="Standard Delivery",
    delivery_brokerage_rate=Decimal("0.001"),          # min(0.1%, ₹20)
    brokerage_min_per_order=Decimal("5.00"),           # min ₹5 per executed order
    brokerage_max_per_order=Decimal("20.00"),          # capped at ₹20 per executed order
    dp_billing_mode=DPBillingMode.PER_EXECUTED_ORDER,  # Retail per-order billing
)

GROWW_DELIVERY_STRESS_317_PROFILE = BrokerChargeProfile(
    broker_name="Groww",
    pricing_plan="Hypothetical Stress Test (₹317/cr)",
    delivery_brokerage_rate=Decimal("0.001"),
    brokerage_min_per_order=Decimal("5.00"),
    brokerage_max_per_order=Decimal("20.00"),
    dp_billing_mode=DPBillingMode.PER_EXECUTED_ORDER,
    exchange_turnover_rate_override=Decimal("317.00") / Decimal("10000000"), # ₹317 per crore
    is_hypothetical_override=True,
    override_description="Optional sensitivity scenario testing hypothetical ₹317/cr web display",
)

ZERODHA_DELIVERY_PROFILE = BrokerChargeProfile(
    broker_name="Zerodha",
    pricing_plan="Equity Delivery (Free)",
    delivery_brokerage_rate=Decimal("0"),
    brokerage_min_per_order=Decimal("0"),
    brokerage_max_per_order=Decimal("0"),
    dp_billing_mode=DPBillingMode.PER_ISIN_PER_DAY,     # Depository EOD net batching
)


# Depository Profiles
CDSL_GROWW_MALE_PROFILE = DepositoryChargeProfile(
    depository_name="CDSL",
    profile_name="Groww Male Retail",
    broker_dp_fee=Decimal("16.50"),
    cdsl_fee=Decimal("3.50"),
    sub_100_waiver_threshold=Decimal("100.00"),
)

CDSL_GROWW_FEMALE_PROFILE = DepositoryChargeProfile(
    depository_name="CDSL",
    profile_name="Groww Female Retail",
    broker_dp_fee=Decimal("16.50"),
    cdsl_fee=Decimal("3.25"),                          # ₹0.25 CDSL concession
    sub_100_waiver_threshold=Decimal("100.00"),
)

CDSL_ZERODHA_PROFILE = DepositoryChargeProfile(
    depository_name="CDSL",
    profile_name="Zerodha Retail",
    broker_dp_fee=Decimal("9.50"),
    cdsl_fee=Decimal("3.50"),                          # Total ₹13.00 base post-Oct 2024
    sub_100_waiver_threshold=Decimal("0.00"),
)


# Execution Assumptions
ZERO_EXECUTION_ASSUMPTIONS = ExecutionCostAssumptions(
    slippage_bps=Decimal("0"),
    spread_bps=Decimal("0"),
)

REALISTIC_SWING_EXECUTION_ASSUMPTIONS = ExecutionCostAssumptions(
    slippage_bps=Decimal("2.0"),                       # 2.0 bps
    spread_bps=Decimal("1.0"),                         # 1.0 bp
)

CONSERVATIVE_STRESS_EXECUTION_ASSUMPTIONS = ExecutionCostAssumptions(
    slippage_bps=Decimal("5.0"),                       # 5.0 bps
    spread_bps=Decimal("2.0"),                         # 2.0 bps
)


# ---------------------------------------------------------------------------
# Rate Resolvers
# ---------------------------------------------------------------------------

def get_statutory_schedule(trade_date: date, state: str = "MH") -> StatutoryCostSchedule:
    """
    Resolves the date-effective statutory tax schedule.
    Fails safely if date is prior to supported historical validation period (2017).
    """
    if trade_date < date(2017, 1, 1):
        raise ValueError(f"Unsupported historical date {trade_date}: SignalForge delivery schedules start 2017-01-01")

    if trade_date < date(2020, 7, 1):
        if state.upper() == "MH":
            return STATUTORY_SCHEDULE_HISTORICAL_MH
        raise ValueError(f"State {state} stamp duty prior to 1 July 2020 is unresolved; use 'MH' or configure custom schedule")
    elif trade_date < date(2022, 7, 18):
        return STATUTORY_SCHEDULE_MODERN_PRE_JULY2022
    else:
        return STATUTORY_SCHEDULE_MODERN


def get_exchange_schedule(trade_date: date, exchange: str = "NSE") -> ExchangeChargeSchedule:
    """
    Resolves the date-effective stock exchange transaction charge schedule.
    Fails safely if date or exchange is unsupported.
    """
    if exchange.upper() != "NSE":
        raise ValueError(f"Exchange '{exchange}' unsupported; only 'NSE' cash segment is certified")

    if trade_date < date(2017, 1, 1):
        raise ValueError(f"Unsupported historical date {trade_date}: exchange schedules start 2017-01-01")
    elif trade_date < date(2019, 4, 1):
        return NSE_CASH_SCHEDULE_HISTORICAL_2017
    elif trade_date < date(2023, 4, 1):
        return NSE_CASH_SCHEDULE_HISTORICAL_2019
    elif trade_date < date(2024, 10, 1):
        return NSE_CASH_SCHEDULE_2023_Q2
    elif trade_date < date(2026, 3, 1):
        return NSE_CASH_SCHEDULE_2024_Q4
    else:
        return NSE_CASH_SCHEDULE_2026_Q1


# ---------------------------------------------------------------------------
# Delivery Cost Calculator
# ---------------------------------------------------------------------------

class DeliveryCostCalculator:
    """
    Auditable delivery transaction cost engine for Indian equities (NSE Cash).
    Operates strictly with Python Decimal and explicit rounding.
    """

    @staticmethod
    def _round(val: Decimal, mode: RoundingMode = RoundingMode.HALF_EVEN) -> Decimal:
        """Quantizes Decimal to 2 decimal places (exact paisa)."""
        return val.quantize(Decimal("0.01"), rounding=mode.value)

    @classmethod
    def calculate_trade(
        cls,
        orders: List[DeliveryOrder],
        broker_profile: BrokerChargeProfile,
        depository_profile: DepositoryChargeProfile,
        execution_assumptions: Optional[ExecutionCostAssumptions] = None,
        statutory_schedule: Optional[StatutoryCostSchedule] = None,
        exchange_schedule: Optional[ExchangeChargeSchedule] = None,
        rounding_mode: RoundingMode = RoundingMode.HALF_EVEN,
        gross_pnl: Optional[Decimal] = None,
    ) -> DeliveryCostBreakdown:
        """
        Calculates complete itemized delivery transaction costs for a set of orders.
        """
        if not orders:
            raise ValueError("At least one DeliveryOrder is required to calculate costs")

        if execution_assumptions is None:
            execution_assumptions = ZERO_EXECUTION_ASSUMPTIONS

        notes: List[str] = []

        # Reference date from the first order if schedules not explicitly passed
        ref_date = orders[0].trade_date

        if statutory_schedule is None:
            statutory_schedule = get_statutory_schedule(ref_date)
        if exchange_schedule is None:
            exchange_schedule = get_exchange_schedule(ref_date)

        # 1. Group orders by Order ID to handle partial fills
        # Multiple fills sharing the same order_id are aggregated into one executed order.
        buy_orders_map: Dict[str, Tuple[Decimal, str, date]] = {}
        sell_orders_map: Dict[str, Tuple[Decimal, str, date]] = {}

        for o in orders:
            if o.turnover < Decimal("0"):
                raise ValueError(f"Order {o.order_id} has invalid negative turnover: {o.turnover}")

            if o.side == OrderSide.BUY:
                if o.order_id in buy_orders_map:
                    prev_turnover, isin, dt = buy_orders_map[o.order_id]
                    buy_orders_map[o.order_id] = (prev_turnover + o.turnover, isin, dt)
                else:
                    buy_orders_map[o.order_id] = (o.turnover, o.isin, o.trade_date)
            elif o.side == OrderSide.SELL:
                if o.order_id in sell_orders_map:
                    prev_turnover, isin, dt = sell_orders_map[o.order_id]
                    sell_orders_map[o.order_id] = (prev_turnover + o.turnover, isin, dt)
                else:
                    sell_orders_map[o.order_id] = (o.turnover, o.isin, o.trade_date)

        total_buy_turnover = sum((t for t, _, _ in buy_orders_map.values()), Decimal("0"))
        total_sell_turnover = sum((t for t, _, _ in sell_orders_map.values()), Decimal("0"))
        total_turnover = total_buy_turnover + total_sell_turnover

        # 2. Brokerage (Order-Aware)
        buy_brokerage = Decimal("0.00")
        for order_id, (order_t, _, _) in buy_orders_map.items():
            raw_b = cls._round(order_t * broker_profile.delivery_brokerage_rate, rounding_mode)
            b = max(broker_profile.brokerage_min_per_order, min(broker_profile.brokerage_max_per_order, raw_b))
            buy_brokerage += b

        sell_brokerage = Decimal("0.00")
        for order_id, (order_t, _, _) in sell_orders_map.items():
            raw_b = cls._round(order_t * broker_profile.delivery_brokerage_rate, rounding_mode)
            b = max(broker_profile.brokerage_min_per_order, min(broker_profile.brokerage_max_per_order, raw_b))
            sell_brokerage += b

        total_brokerage = buy_brokerage + sell_brokerage

        # 3. Securities Transaction Tax (STT) - 0.1% on Buy & Sell
        buy_stt = cls._round(total_buy_turnover * statutory_schedule.stt_buy_rate, rounding_mode)
        sell_stt = cls._round(total_sell_turnover * statutory_schedule.stt_sell_rate, rounding_mode)
        total_stt = buy_stt + sell_stt

        # 4. Stamp Duty - Buy-side only
        buy_stamp_duty = cls._round(total_buy_turnover * statutory_schedule.stamp_duty_buy_rate, rounding_mode)
        sell_stamp_duty = Decimal("0.00")
        total_stamp_duty = buy_stamp_duty + sell_stamp_duty

        # 5. Exchange Transaction Charges & IPFT
        is_override = False
        if broker_profile.exchange_turnover_rate_override is not None:
            is_override = True
            exchange_charge = cls._round(total_turnover * broker_profile.exchange_turnover_rate_override, rounding_mode)
            ipft_charge = Decimal("0.00")
            combined_exchange_ipft = exchange_charge
            notes.append(f"Broker override active: {broker_profile.override_description or 'Hypothetical rate'}")
        else:
            exchange_charge = cls._round(total_turnover * exchange_schedule.transaction_charge_rate, rounding_mode)
            ipft_charge = cls._round(total_turnover * exchange_schedule.ipft_rate, rounding_mode)
            combined_exchange_ipft = exchange_charge + ipft_charge

        # 6. SEBI Turnover Fees
        sebi_turnover_fee = cls._round(total_turnover * exchange_schedule.sebi_turnover_rate, rounding_mode)

        # 7. Depository Participant (DP) Charges (Sell-side only)
        groww_dp_total = Decimal("0.00")
        cdsl_dp_total = Decimal("0.00")
        debit_count = 0

        if broker_profile.dp_billing_mode == DPBillingMode.PER_EXECUTED_ORDER:
            # Mode A: Billed per executed sell order
            for order_id, (order_t, isin, dt) in sell_orders_map.items():
                debit_count += 1
                if order_t < depository_profile.sub_100_waiver_threshold:
                    groww_dp_total += Decimal("0.00")
                    cdsl_dp_total += depository_profile.cdsl_fee
                    notes.append(f"Sub-₹100 sale waiver applied on order {order_id} (turnover: ₹{order_t})")
                else:
                    groww_dp_total += depository_profile.broker_dp_fee
                    cdsl_dp_total += depository_profile.cdsl_fee
        elif broker_profile.dp_billing_mode == DPBillingMode.PER_ISIN_PER_DAY:
            # Mode B: Aggregated per ISIN per settlement day
            isin_day_map: Dict[Tuple[str, date], Decimal] = {}
            for order_id, (order_t, isin, dt) in sell_orders_map.items():
                key = (isin, dt)
                isin_day_map[key] = isin_day_map.get(key, Decimal("0")) + order_t

            for (isin, dt), day_t in isin_day_map.items():
                debit_count += 1
                if day_t < depository_profile.sub_100_waiver_threshold:
                    groww_dp_total += Decimal("0.00")
                    cdsl_dp_total += depository_profile.cdsl_fee
                else:
                    groww_dp_total += depository_profile.broker_dp_fee
                    cdsl_dp_total += depository_profile.cdsl_fee

        total_dp_base = groww_dp_total + cdsl_dp_total

        # 8. GST (18% on Taxable Financial Services)
        # STT and Stamp Duty are strictly exempt.
        # SEBI fees: 0% GST before 18 July 2022; 18% GST thereafter.
        taxable_sebi = sebi_turnover_fee if statutory_schedule.gst_on_sebi_fees else Decimal("0.00")
        taxable_services_base = (
            total_brokerage
            + exchange_charge
            + ipft_charge
            + taxable_sebi
            + total_dp_base
        )
        total_gst = cls._round(taxable_services_base * statutory_schedule.gst_rate, rounding_mode)

        # 9. Execution Friction (Slippage & Spread)
        slippage_cost = cls._round(total_turnover * (execution_assumptions.slippage_bps / Decimal("10000")), rounding_mode)
        spread_cost = cls._round(total_turnover * (execution_assumptions.spread_bps / Decimal("10000")), rounding_mode)
        total_execution = slippage_cost + spread_cost

        # 10. Aggregates and P&L
        statutory_broker_costs = (
            total_brokerage
            + total_stt
            + total_stamp_duty
            + exchange_charge
            + ipft_charge
            + sebi_turnover_fee
            + total_dp_base
            + total_gst
        )
        total_transaction_costs = statutory_broker_costs + total_execution

        computed_gross_pnl: Optional[Decimal] = None
        computed_net_pnl: Optional[Decimal] = None
        breakeven_gross_pct: Optional[Decimal] = None

        if gross_pnl is not None:
            computed_gross_pnl = gross_pnl
            computed_net_pnl = gross_pnl - total_transaction_costs
        elif total_buy_turnover > Decimal("0") and total_sell_turnover > Decimal("0"):
            computed_gross_pnl = total_sell_turnover - total_buy_turnover
            computed_net_pnl = computed_gross_pnl - total_transaction_costs

        if total_buy_turnover > Decimal("0"):
            breakeven_gross_pct = (total_transaction_costs / total_buy_turnover) * Decimal("100")
            breakeven_gross_pct = breakeven_gross_pct.quantize(Decimal("0.0001"), rounding=rounding_mode.value)

        return DeliveryCostBreakdown(
            buy_turnover=total_buy_turnover,
            sell_turnover=total_sell_turnover,
            total_turnover=total_turnover,
            buy_order_count=len(buy_orders_map),
            sell_order_count=len(sell_orders_map),
            dp_charge_debit_count=debit_count,
            buy_stt=buy_stt,
            sell_stt=sell_stt,
            total_stt=total_stt,
            buy_stamp_duty=buy_stamp_duty,
            sell_stamp_duty=sell_stamp_duty,
            total_stamp_duty=total_stamp_duty,
            exchange_transaction_charge=exchange_charge,
            ipft_charge=ipft_charge,
            combined_exchange_ipft_charge=combined_exchange_ipft,
            sebi_turnover_fee=sebi_turnover_fee,
            taxable_sebi_fee=taxable_sebi,
            buy_brokerage=buy_brokerage,
            sell_brokerage=sell_brokerage,
            total_brokerage=total_brokerage,
            groww_dp_charge=groww_dp_total,
            cdsl_dp_charge=cdsl_dp_total,
            total_dp_base=total_dp_base,
            taxable_services_base=taxable_services_base,
            gst_rate=statutory_schedule.gst_rate,
            total_gst=total_gst,
            slippage_cost=slippage_cost,
            spread_cost=spread_cost,
            total_execution_friction=total_execution,
            statutory_broker_costs=statutory_broker_costs,
            total_transaction_costs=total_transaction_costs,
            gross_pnl=computed_gross_pnl,
            net_pnl=computed_net_pnl,
            breakeven_gross_pct=breakeven_gross_pct,
            statutory_schedule_id=statutory_schedule.schedule_id,
            exchange_schedule_id=exchange_schedule.schedule_id,
            broker_profile_name=broker_profile.broker_name,
            depository_profile_name=depository_profile.profile_name,
            dp_billing_mode=broker_profile.dp_billing_mode.value,
            is_hypothetical_override=is_override,
            notes=notes,
        )

    @classmethod
    def calculate_simple_trade(
        cls,
        buy_turnover: Union[Decimal, float, int, str],
        sell_turnovers: Union[Decimal, float, int, str, List[Union[Decimal, float, int, str]]],
        isin: str = "DEFAULT",
        trade_date: Optional[date] = None,
        broker_profile: Optional[BrokerChargeProfile] = None,
        depository_profile: Optional[DepositoryChargeProfile] = None,
        execution_assumptions: Optional[ExecutionCostAssumptions] = None,
        statutory_schedule: Optional[StatutoryCostSchedule] = None,
        exchange_schedule: Optional[ExchangeChargeSchedule] = None,
        sell_order_dates: Optional[List[date]] = None,
        rounding_mode: RoundingMode = RoundingMode.HALF_EVEN,
        gross_pnl: Optional[Decimal] = None,
    ) -> DeliveryCostBreakdown:
        """
        Convenience API to calculate costs for simple single-buy / multi-sell delivery trades.
        """
        if trade_date is None:
            trade_date = date(2026, 3, 1)

        if broker_profile is None:
            broker_profile = GROWW_DELIVERY_PROFILE
        if depository_profile is None:
            depository_profile = CDSL_GROWW_MALE_PROFILE
        if execution_assumptions is None:
            execution_assumptions = REALISTIC_SWING_EXECUTION_ASSUMPTIONS

        b_t = Decimal(str(buy_turnover))
        orders: List[DeliveryOrder] = [
            DeliveryOrder(order_id="BUY_1", isin=isin, side=OrderSide.BUY, turnover=b_t, trade_date=trade_date)
        ]

        if not isinstance(sell_turnovers, list):
            sell_turnovers = [sell_turnovers]

        for idx, s in enumerate(sell_turnovers, 1):
            s_t = Decimal(str(s))
            s_date = sell_order_dates[idx - 1] if sell_order_dates and idx - 1 < len(sell_order_dates) else trade_date
            orders.append(
                DeliveryOrder(order_id=f"SELL_{idx}", isin=isin, side=OrderSide.SELL, turnover=s_t, trade_date=s_date)
            )

        return cls.calculate_trade(
            orders=orders,
            broker_profile=broker_profile,
            depository_profile=depository_profile,
            execution_assumptions=execution_assumptions,
            statutory_schedule=statutory_schedule,
            exchange_schedule=exchange_schedule,
            rounding_mode=rounding_mode,
            gross_pnl=gross_pnl,
        )

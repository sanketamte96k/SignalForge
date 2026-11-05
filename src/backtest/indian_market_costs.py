"""
Indian Equity Intraday Transaction Cost Engine for SignalForge
==============================================================
Calculates complete statutory, regulatory, brokerage, and execution friction
costs for intraday equity cash trading in India (NSE):
  1. Brokerage on entry and exit legs (configurable rate & cap)
  2. Securities Transaction Tax (STT) on SELL leg turnover only (0.025%)
  3. NSE Exchange Transaction Charges (ETC) on total turnover
  4. SEBI Turnover Charges (STC) on total turnover
  5. State Stamp Duty on BUY leg turnover only (0.003%)
  6. Goods & Services Tax (GST) at 18% on (Brokerage + ETC + STC)
  7. Slippage (configurable bps on turnover)
  8. Bid-Ask Spread cost (configurable half-spread on turnover)
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Literal, Optional


@dataclass(frozen=True)
class IntradayCostConfig:
    """Configuration schedule for Indian equity intraday transaction costs."""
    name: str
    description: str
    brokerage_rate_pct: float          # e.g. 0.0003 for 0.03%
    brokerage_max_per_leg_inr: float   # e.g. 20.0 (Zerodha/AngelOne standard)
    stt_rate_sell_pct: float           # 0.00025 for 0.025% (Sell leg only)
    exchange_charge_rate_pct: float    # 0.0000325 for 0.00325% NSE cash
    sebi_charge_rate_pct: float        # 0.000001 for 0.0001% (₹10/crore)
    stamp_duty_rate_buy_pct: float     # 0.00003 for 0.003% (Buy leg only)
    gst_rate_pct: float                # 0.18 (18% on Brokerage + Exchange + SEBI)
    slippage_rate_pct: float           # 0.0001 for 1.0 bps
    spread_rate_pct: float             # 0.00005 for 0.5 bps
    is_illustrative: bool = False


# Pre-defined Cost Model Profiles
STATUTORY_ONLY_CONFIG = IntradayCostConfig(
    name="STATUTORY_ONLY",
    description="Broker-agnostic statutory & regulatory charges only (zero brokerage, 1 bps slippage)",
    brokerage_rate_pct=0.0,
    brokerage_max_per_leg_inr=0.0,
    stt_rate_sell_pct=0.00025,
    exchange_charge_rate_pct=0.0000325,
    sebi_charge_rate_pct=0.000001,
    stamp_duty_rate_buy_pct=0.00003,
    gst_rate_pct=0.18,
    slippage_rate_pct=0.0001,
    spread_rate_pct=0.0,
    is_illustrative=False,
)

DISCOUNT_BROKER_REALISTIC_CONFIG = IntradayCostConfig(
    name="DISCOUNT_BROKER_REALISTIC",
    description="Industry-standard retail discount broker schedule (min(0.03%, ₹20) per leg, full statutory taxes, 1.0 bps slippage, 0.5 bps spread)",
    brokerage_rate_pct=0.0003,
    brokerage_max_per_leg_inr=20.0,
    stt_rate_sell_pct=0.00025,
    exchange_charge_rate_pct=0.0000325,
    sebi_charge_rate_pct=0.000001,
    stamp_duty_rate_buy_pct=0.00003,
    gst_rate_pct=0.18,
    slippage_rate_pct=0.0001,
    spread_rate_pct=0.00005,
    is_illustrative=False,
)

CONSERVATIVE_STRESS_CONFIG = IntradayCostConfig(
    name="CONSERVATIVE_STRESS",
    description="Conservative stress model (min(0.03%, ₹20) brokerage, elevated exchange/SEBI rates, 2.5 bps slippage, 1.0 bps spread)",
    brokerage_rate_pct=0.0003,
    brokerage_max_per_leg_inr=20.0,
    stt_rate_sell_pct=0.00025,
    exchange_charge_rate_pct=0.0000345,
    sebi_charge_rate_pct=0.0000015,
    stamp_duty_rate_buy_pct=0.00003,
    gst_rate_pct=0.18,
    slippage_rate_pct=0.00025,
    spread_rate_pct=0.0001,
    is_illustrative=True,
)


@dataclass(frozen=True)
class TradeCostBreakdown:
    """Granular cost accounting for an individual executed trade."""
    turnover: float
    entry_turnover: float
    exit_turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    slippage: float
    spread_cost: float
    total_costs: float
    gross_pnl: float
    net_pnl: float
    is_gross_win: bool
    is_net_win: bool
    is_cost_flipped: bool  # True if gross_pnl > 0 but net_pnl <= 0


def calculate_trade_transaction_costs(
    side: Literal["LONG", "SHORT"] | str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    config: Optional[IntradayCostConfig] = None,
) -> TradeCostBreakdown:
    """
    Calculate comprehensive transaction costs for an intraday equity trade.
    
    Formula Reference (Indian Equity Intraday):
      - Entry turnover = entry_price * quantity
      - Exit turnover = exit_price * quantity
      - Total turnover = entry_turnover + exit_turnover
      - Brokerage = min(cap, entry_turnover * rate) + min(cap, exit_turnover * rate)
      - STT = exit_turnover * 0.025% (if LONG) or entry_turnover * 0.025% (if SHORT)
      - Exchange Charges = total_turnover * 0.00325%
      - SEBI Charges = total_turnover * 0.0001%
      - Stamp Duty = entry_turnover * 0.003% (if LONG) or exit_turnover * 0.003% (if SHORT)
      - GST = 18% * (Brokerage + Exchange Charges + SEBI Charges)
      - Slippage = total_turnover * slippage_rate
      - Spread Cost = total_turnover * spread_rate
    """
    if config is None:
        config = DISCOUNT_BROKER_REALISTIC_CONFIG

    side_norm = side.upper()
    qty = max(1, int(quantity))
    entry_t = round(float(entry_price) * qty, 2)
    exit_t = round(float(exit_price) * qty, 2)
    total_t = round(entry_t + exit_t, 2)

    # 1. Brokerage on entry and exit legs
    if config.brokerage_rate_pct > 0.0:
        brok_entry = min(config.brokerage_max_per_leg_inr, entry_t * config.brokerage_rate_pct)
        brok_exit = min(config.brokerage_max_per_leg_inr, exit_t * config.brokerage_rate_pct)
        brokerage = brok_entry + brok_exit
    else:
        brokerage = 0.0

    # 2. STT: on SELL leg only (Exit for LONG, Entry for SHORT)
    sell_turnover = exit_t if side_norm == "LONG" else entry_t
    stt = sell_turnover * config.stt_rate_sell_pct

    # 3. NSE Exchange Charges on total turnover
    exchange_charges = total_t * config.exchange_charge_rate_pct

    # 4. SEBI Turnover Charges on total turnover
    sebi_charges = total_t * config.sebi_charge_rate_pct

    # 5. Stamp Duty: on BUY leg only (Entry for LONG, Exit for SHORT)
    buy_turnover = entry_t if side_norm == "LONG" else exit_t
    stamp_duty = buy_turnover * config.stamp_duty_rate_buy_pct

    # 6. GST: 18% on (Brokerage + Exchange Charges + SEBI Charges)
    taxable_services = brokerage + exchange_charges + sebi_charges
    gst = taxable_services * config.gst_rate_pct

    # 7. Slippage
    slippage = total_t * config.slippage_rate_pct

    # 8. Spread Cost
    spread_cost = total_t * config.spread_rate_pct

    # Total Costs
    total_costs = (
        brokerage
        + stt
        + exchange_charges
        + sebi_charges
        + stamp_duty
        + gst
        + slippage
        + spread_cost
    )

    # Gross P&L
    if side_norm == "LONG":
        gross_pnl = (float(exit_price) - float(entry_price)) * qty
    else:
        gross_pnl = (float(entry_price) - float(exit_price)) * qty

    gross_pnl = round(gross_pnl, 2)
    net_pnl = round(gross_pnl - total_costs, 2)

    is_gross_win = gross_pnl > 0.0
    is_net_win = net_pnl > 0.0
    is_cost_flipped = is_gross_win and not is_net_win

    return TradeCostBreakdown(
        turnover=total_t,
        entry_turnover=entry_t,
        exit_turnover=exit_t,
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange_charges=round(exchange_charges, 2),
        sebi_charges=round(sebi_charges, 2),
        stamp_duty=round(stamp_duty, 2),
        gst=round(gst, 2),
        slippage=round(slippage, 2),
        spread_cost=round(spread_cost, 2),
        total_costs=round(total_costs, 2),
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        is_gross_win=is_gross_win,
        is_net_win=is_net_win,
        is_cost_flipped=is_cost_flipped,
    )


# Convenience aliases
calculate_indian_market_cost = calculate_trade_transaction_costs
CostModelConfig = IntradayCostConfig



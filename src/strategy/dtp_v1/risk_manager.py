"""
SignalForge — Phase 32C.5: DTP-V1 Position Sizing & Risk Management
===================================================================
File: src/strategy/dtp_v1/risk_manager.py

Implements conservative fixed-fractional risk sizing, cash delivery constraints,
and exposure allocation caps for DTP-V1 swing trading:
  - 1.0% equity risk per trade based on true stop distance.
  - 33.3% maximum single-position capital allocation cap.
  - 100% total cash delivery constraint (strictly zero margin leverage).
  - 40.0% maximum sector exposure cap.
  - ₹5,000 minimum trade notional floor to prevent transaction-cost distortion.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from src.strategy.dtp_v1.config import DTPV1Config


def calculate_dtp_position_size(
    equity: float,
    available_cash: float,
    entry_price: float,
    stop_price: float,
    sector: str = "General",
    current_sector_exposure: float = 0.0,
    config: Optional[DTPV1Config] = None,
) -> Tuple[int, str]:
    """
    Calculates deterministic share quantity for a delivery swing trade:
      1. Risk-based quantity: floor((Equity * 1.0%) / (Entry - Stop))
      2. Capital allocation cap: floor((Equity * 33.3%) / (Entry * (1 + CostBuffer)))
      3. Available cash cap: floor(AvailableCash / (Entry * (1 + CostBuffer)))
      4. Sector allocation cap: floor(RemainingSectorBudget / (Entry * (1 + CostBuffer)))
      5. Minimum trade notional check (>= ₹5,000)

    Returns: (approved_shares, audit_reason)
    """
    if config is None:
        config = DTPV1Config()

    if equity <= 0.0:
        return 0, f"Invalid non-positive portfolio equity: ₹{equity:.2f}"
    if available_cash <= 0.0:
        return 0, f"Insufficient cash available: ₹{available_cash:.2f}"
    if entry_price <= 0.0:
        return 0, f"Invalid entry price: ₹{entry_price:.2f}"
    if stop_price <= 0.0 or stop_price >= entry_price:
        return 0, f"Invalid stop price {stop_price:.2f} relative to entry {entry_price:.2f}"

    stop_distance = entry_price - stop_price

    # Cost buffer (0.50% to cover STT, stamp duty, brokerage, DP charge, and GST)
    cost_buffer = config.breakeven_cost_buffer_pct
    effective_entry_cost = entry_price * (1.0 + cost_buffer)

    # 1. Risk-based sizing
    risk_budget = equity * config.risk_fraction_per_trade
    q_risk = int(math.floor(risk_budget / stop_distance))

    # 2. Maximum single-position allocation cap (33.3%)
    max_position_capital = equity * config.max_position_allocation_pct
    q_cap = int(math.floor(max_position_capital / effective_entry_cost))

    # 3. Available cash constraint (strictly no margin leverage)
    q_cash = int(math.floor(available_cash / effective_entry_cost))

    # 4. Sector exposure constraint (max 40%)
    max_sector_capital = equity * config.max_sector_exposure_pct
    remaining_sector_capital = max(0.0, max_sector_capital - current_sector_exposure)
    q_sector = int(math.floor(remaining_sector_capital / effective_entry_cost))

    # Take the conservative binding constraint
    approved_shares = min(q_risk, q_cap, q_cash, q_sector)

    if approved_shares <= 0:
        reasons = []
        if q_risk <= 0:
            reasons.append("risk budget too small for stop distance")
        if q_cap <= 0:
            reasons.append("position cap reached")
        if q_cash <= 0:
            reasons.append("insufficient unallocated cash")
        if q_sector <= 0:
            reasons.append("sector exposure cap reached")
        return 0, f"Position rejected: {', '.join(reasons)}"

    # 5. Minimum notional floor (₹5,000)
    notional = approved_shares * entry_price
    if notional < config.min_trade_notional:
        return (
            0,
            f"Notional ₹{notional:,.2f} below minimum efficiency floor ₹{config.min_trade_notional:,.2f} ({approved_shares} shares)",
        )

    return approved_shares, (
        f"Approved {approved_shares} shares (Notional: ₹{notional:,.2f}, Risk: ₹{approved_shares * stop_distance:,.2f}, "
        f"Constrained by min[Risk={q_risk}, Cap={q_cap}, Cash={q_cash}, Sector={q_sector}])"
    )

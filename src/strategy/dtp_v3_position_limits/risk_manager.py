"""
SignalForge — Phase 32J.5: Position Sizing & A2 Overlay Engine
==============================================================
File: src/strategy/dtp_v3_position_limits/risk_manager.py

Calculates deterministic integer share quantities with optional A2 risk discount:
  - Base fixed-fractional risk sizing (E1: 1%, E2: 2%, E3: 3%).
  - Optional A2 overlay: 50% risk discount when Nifty 50 is in Caution zone (0-2% above SMA100).
  - 33.3% maximum single-position capital allocation cap.
  - Cash constraint (100% cash delivery, zero margin leverage).
  - 40.0% sector exposure cap.
  - ₹5,000 minimum trade notional floor.
  - Drawdown Circuit Breaker (halts if DD >= 15.0%).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from src.strategy.dtp_v3_position_limits.config import DTPV3PositionLimitsConfig


def calculate_position_limit_sizing(
    equity: float,
    available_cash: float,
    entry_price: float,
    stop_price: float,
    sector: str = "General",
    current_sector_exposure: float = 0.0,
    current_drawdown_pct: float = 0.0,
    risk_multiplier: float = 1.0,
    config: Optional[DTPV3PositionLimitsConfig] = None,
) -> Tuple[int, str]:
    """
    Calculates deterministic integer share quantity:
      1. Drawdown Circuit Breaker: If DD >= 15%, trading paused.
      2. Dynamic Risk-based quantity: floor((Equity * BaseRisk * RiskMultiplier) / (Entry - Stop))
      3. Capital allocation cap: floor((Equity * 33.3%) / (Entry * (1 + CostBuffer)))
      4. Available cash cap: floor(AvailableCash / (Entry * (1 + CostBuffer)))
      5. Sector allocation cap: floor(max(0, Equity * 40% - CurrentSectorExposure) / (Entry * (1 + CostBuffer)))
      6. Minimum trade notional check (>= ₹5,000).

    Returns: (approved_shares, audit_reason)
    """
    if config is None:
        config = DTPV3PositionLimitsConfig()

    # 1. Drawdown Circuit Breaker
    if current_drawdown_pct >= config.max_allowable_drawdown_pct:
        return (
            0,
            f"Circuit breaker active: Portfolio drawdown ({current_drawdown_pct:.1%}) exceeds limit ({config.max_allowable_drawdown_pct:.1%})",
        )

    if equity <= 0.0:
        return 0, f"Invalid non-positive portfolio equity: ₹{equity:.2f}"
    if available_cash <= 0.0:
        return 0, f"Insufficient cash available: ₹{available_cash:.2f}"
    if entry_price <= 0.0:
        return 0, f"Invalid entry price: ₹{entry_price:.2f}"
    if stop_price <= 0.0 or stop_price >= entry_price:
        return 0, f"Invalid stop price {stop_price:.2f} relative to entry {entry_price:.2f}"

    stop_distance = entry_price - stop_price
    cost_buffer = config.breakeven_cost_buffer_pct
    effective_entry_cost = entry_price * (1.0 + cost_buffer)

    # 2. Risk-based sizing with dynamic risk multiplier
    effective_risk_pct = config.risk_fraction_per_trade * max(0.0, min(1.0, risk_multiplier))
    risk_budget = equity * effective_risk_pct
    q_risk = int(math.floor(risk_budget / stop_distance))

    # 3. Maximum single-position allocation cap (33.3%)
    max_position_capital = equity * config.max_position_allocation_pct
    q_cap = int(math.floor(max_position_capital / effective_entry_cost))

    # 4. Available cash constraint (strictly no margin leverage)
    q_cash = int(math.floor(available_cash / effective_entry_cost))

    # 5. Sector exposure constraint (max 40%)
    max_sector_capital = equity * config.max_sector_exposure_pct
    remaining_sector_capital = max(0.0, max_sector_capital - current_sector_exposure)
    q_sector = int(math.floor(remaining_sector_capital / effective_entry_cost))

    # Conservative binding constraint
    approved_shares = min(q_risk, q_cap, q_cash, q_sector)

    if approved_shares <= 0:
        reasons = []
        if q_risk <= 0:
            reasons.append(f"risk budget (₹{risk_budget:.2f}) too small for stop distance (₹{stop_distance:.2f})")
        if q_cap <= 0:
            reasons.append("position cap reached")
        if q_cash <= 0:
            reasons.append(f"insufficient unallocated cash (₹{available_cash:,.2f})")
        if q_sector <= 0:
            reasons.append(f"sector cap for {sector} fully saturated")
        return 0, f"Position rejected: {', '.join(reasons)}"

    # 6. Minimum trade notional check (>= ₹5,000)
    trade_notional = approved_shares * entry_price
    if trade_notional < config.min_trade_notional:
        return 0, f"Position rejected: Notional ₹{trade_notional:,.2f} < ₹{config.min_trade_notional:,.2f} floor"

    return approved_shares, f"Approved {approved_shares} shares"

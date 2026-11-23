"""
SignalForge — Phase 32J.4: Portfolio Risk Position Sizing Engine
=================================================================
File: src/strategy/dtp_v3_portfolio_risk/risk_manager.py

Implements deterministic integer share sizing incorporating:
  - Fixed-fractional risk sizing scaled by dynamic risk multiplier (Experiment A: 50% discount).
  - Configurable sector concentration cap (Experiment B: 40%, 30%, 25%).
  - 33.3% single-position capital allocation cap.
  - Cash constraint (100% cash delivery, zero margin leverage).
  - Minimum trade notional floor (₹5,000).
  - Portfolio Drawdown Circuit Breaker (halts if DD >= 15.0%).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from src.strategy.dtp_v3_portfolio_risk.config import DTPV3PortfolioRiskConfig


def calculate_portfolio_risk_position_size(
    equity: float,
    available_cash: float,
    entry_price: float,
    stop_price: float,
    sector: str = "General",
    current_sector_exposure: float = 0.0,
    current_drawdown_pct: float = 0.0,
    risk_multiplier: float = 1.0,
    sector_cap_pct: float = 0.40,
    config: Optional[DTPV3PortfolioRiskConfig] = None,
) -> Tuple[int, str]:
    """
    Calculates deterministic integer share quantity under portfolio risk constraints:
      1. Drawdown Circuit Breaker: If DD >= 15%, trading paused.
      2. Dynamic Risk-based quantity: floor((Equity * BaseRisk * RiskMultiplier) / (Entry - Stop))
      3. Capital allocation cap: floor((Equity * 33.3%) / (Entry * (1 + CostBuffer)))
      4. Available cash cap: floor(AvailableCash / (Entry * (1 + CostBuffer)))
      5. Sector allocation cap: floor(max(0, Equity * SectorCap - CurrentSectorExposure) / (Entry * (1 + CostBuffer)))
      6. Minimum trade notional check (>= ₹5,000).

    Returns: (approved_shares, audit_reason)
    """
    if config is None:
        config = DTPV3PortfolioRiskConfig()

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

    # 5. Sector exposure constraint (dynamic cap: 40%, 30%, 25%)
    max_sector_capital = equity * sector_cap_pct
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
            reasons.append(f"sector cap ({sector_cap_pct:.0%}) for {sector} fully saturated")
        return 0, f"Position rejected: {', '.join(reasons)}"

    # 6. Minimum trade notional check (>= ₹5,000)
    trade_notional = approved_shares * entry_price
    if trade_notional < config.min_trade_notional:
        return 0, f"Position rejected: Notional ₹{trade_notional:,.2f} < ₹{config.min_trade_notional:,.2f} floor"

    return approved_shares, f"Approved {approved_shares} shares (Binding: {min([('risk', q_risk), ('cap', q_cap), ('cash', q_cash), ('sector', q_sector)], key=lambda x: x[1])[0]})"

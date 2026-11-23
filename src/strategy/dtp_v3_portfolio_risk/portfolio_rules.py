"""
SignalForge — Phase 32J.4: Portfolio Rules & Exposure Tracker
=============================================================
File: src/strategy/dtp_v3_portfolio_risk/portfolio_rules.py

Enforces portfolio constraints for DTP-V3 with configurable sector caps:
  - Maximum 3 concurrent open positions.
  - Zero duplicate positions per symbol.
  - 100% total equity exposure cap (zero leverage).
  - Dynamic sector exposure cap (40%, 30%, 25%).
  - Real-time mark-to-market drawdown circuit breaker (halts if DD >= 15.0%).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Tuple

from src.strategy.dtp_v3.portfolio_rules import DTPActivePosition
from src.strategy.dtp_v3_portfolio_risk.config import DTPV3PortfolioRiskConfig


class DTPPortfolioRiskTracker:
    """
    Manages portfolio state, cash ledger, active positions, drawdown tracking,
    and sector exposures with dynamic sector exposure caps.
    """

    def __init__(
        self,
        initial_capital: float,
        config: Optional[DTPV3PortfolioRiskConfig] = None,
        sector_cap_pct: float = 0.40,
    ) -> None:
        if initial_capital <= 0.0:
            raise ValueError(f"Initial capital must be positive: ₹{initial_capital:.2f}")

        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.config = config or DTPV3PortfolioRiskConfig()
        self.sector_cap_pct = sector_cap_pct
        self.positions: Dict[str, DTPActivePosition] = {}
        self.peak_equity = initial_capital
        self.max_drawdown_observed = 0.0

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def total_invested_capital(self) -> float:
        return sum(pos.cost_basis for pos in self.positions.values())

    def get_portfolio_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Computes total portfolio equity = cash + mark-to-market position value."""
        if current_prices is None:
            eq = self.cash + self.total_invested_capital()
        else:
            mtm_value = sum(
                pos.market_value(current_prices.get(symbol, pos.entry_price))
                for symbol, pos in self.positions.items()
            )
            eq = self.cash + mtm_value

        if eq > self.peak_equity:
            self.peak_equity = eq
        dd = (self.peak_equity - eq) / self.peak_equity if self.peak_equity > 0 else 0.0
        if dd > self.max_drawdown_observed:
            self.max_drawdown_observed = dd
        return eq

    def get_current_drawdown(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Returns the current drawdown from peak equity."""
        eq = self.get_portfolio_equity(current_prices)
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - eq) / self.peak_equity)

    def get_sector_exposure(self, sector: str, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Returns total value of positions in the specified sector."""
        total = 0.0
        for pos in self.positions.values():
            if pos.sector == sector:
                px = current_prices.get(pos.symbol, pos.entry_price) if current_prices else pos.entry_price
                total += pos.market_value(px)
        return total

    def can_open_position(
        self,
        symbol: str,
        entry_price: float,
        proposed_shares: int,
        sector: Optional[str] = None,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str]:
        """
        Validates all portfolio constraints:
          1. Drawdown circuit breaker.
          2. Concurrent position count <= 3.
          3. No duplicate position.
          4. Proposed shares > 0.
          5. Cash required <= available cash.
          6. Total exposure <= 100% equity.
          7. Sector exposure <= sector_cap_pct.
        """
        if self.get_current_drawdown(current_prices) >= self.config.max_allowable_drawdown_pct:
            return False, f"Trading halted: Drawdown ({self.get_current_drawdown(current_prices):.1%}) exceeds limit"

        if len(self.positions) >= self.config.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({len(self.positions)}/{self.config.max_concurrent_positions})"

        if symbol in self.positions:
            return False, f"Duplicate position in {symbol} rejected"

        if proposed_shares <= 0:
            return False, f"Invalid proposed share count: {proposed_shares}"

        cost_buffer = self.config.breakeven_cost_buffer_pct
        required_capital = proposed_shares * entry_price * (1.0 + cost_buffer)

        if required_capital > self.cash:
            return False, f"Insufficient cash (Required: ₹{required_capital:,.2f}, Available: ₹{self.cash:,.2f})"

        equity = self.get_portfolio_equity(current_prices)
        new_total_invested = self.total_invested_capital() + (proposed_shares * entry_price)
        if new_total_invested > (equity * self.config.max_portfolio_exposure_pct):
            return False, f"Total portfolio exposure would exceed {self.config.max_portfolio_exposure_pct:.0%}"

        sec = sector or self.config.symbol_sector_map.get(symbol, "General")
        curr_sec_val = self.get_sector_exposure(sec, current_prices)
        new_sec_val = curr_sec_val + (proposed_shares * entry_price)
        if new_sec_val > (equity * self.sector_cap_pct):
            return False, f"Sector exposure for {sec} would exceed {self.sector_cap_pct:.0%}"

        return True, "Portfolio constraints satisfied"

    def open_position(
        self,
        symbol: str,
        entry_price: float,
        shares: int,
        stop_price: float,
        r_distance: float,
        entry_date: date,
        order_id: str,
        sector: Optional[str] = None,
    ) -> DTPActivePosition:
        """Opens a new position and debits cash."""
        sec = sector or self.config.symbol_sector_map.get(symbol, "General")
        isin = self.config.symbol_isin_map.get(symbol, f"INE_{symbol}_01")

        cost = shares * entry_price
        self.cash -= cost

        pos = DTPActivePosition(
            symbol=symbol,
            isin=isin,
            sector=sec,
            entry_date=entry_date,
            entry_price=entry_price,
            quantity=shares,
            initial_stop_price=stop_price,
            current_stop_price=stop_price,
            r_distance=r_distance,
            order_id=order_id,
        )
        self.positions[symbol] = pos
        return pos

    def close_position(self, symbol: str, exit_price: float, net_proceeds: float) -> DTPActivePosition:
        """Closes an active position and credits net proceeds."""
        if symbol not in self.positions:
            raise KeyError(f"No active position to close for symbol: {symbol}")
        pos = self.positions.pop(symbol)
        self.cash += net_proceeds
        return pos

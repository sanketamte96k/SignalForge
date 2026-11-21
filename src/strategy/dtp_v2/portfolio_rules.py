"""
SignalForge — Phase 32E.1: DTP-V2 Portfolio Rules & Exposure Limits
===================================================================
File: src/strategy/dtp_v2/portfolio_rules.py

Enforces portfolio-level constraints for DTP-V2 delivery swing trading:
  - Maximum 3 concurrent open positions.
  - Zero duplicate positions per symbol (no pyramiding).
  - 100% maximum total equity exposure (strictly zero leverage).
  - 40.0% maximum exposure in any single industry sector.

Preserves exact parity with DTP-V1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from src.strategy.dtp_v2.config import DTPV2Config


@dataclass
class DTPActivePosition:
    """Represents an active open delivery position."""
    symbol: str
    isin: str
    sector: str
    entry_date: date
    entry_price: float
    quantity: int
    initial_stop_price: float
    current_stop_price: float
    r_distance: float
    order_id: str

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.entry_price

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price


class DTPPortfolioTracker:
    """
    Manages portfolio state, cash ledger, active positions, and sector exposures for DTP-V2.
    """

    def __init__(self, initial_capital: float, config: Optional[DTPV2Config] = None) -> None:
        if initial_capital <= 0.0:
            raise ValueError(f"Initial capital must be positive: ₹{initial_capital:.2f}")

        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.config = config or DTPV2Config()
        self.positions: Dict[str, DTPActivePosition] = {}

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def total_invested_capital(self) -> float:
        return sum(pos.cost_basis for pos in self.positions.values())

    def get_portfolio_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Computes total portfolio equity = cash + mark-to-market position value."""
        if current_prices is None:
            return self.cash + self.total_invested_capital()

        mtm_value = sum(
            pos.market_value(current_prices.get(symbol, pos.entry_price))
            for symbol, pos in self.positions.items()
        )
        return self.cash + mtm_value

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
        Validates all portfolio constraints before an order is placed:
          1. Concurrent position count <= 3.
          2. No duplicate position in symbol (no pyramiding).
          3. Total exposure <= 100% of equity (no leverage).
          4. Cash required <= uncommitted cash.
          5. Sector exposure <= 40% of equity.
        """
        if symbol in self.positions:
            return False, f"Duplicate position rejected: {symbol} already open (pyramiding prohibited)"

        if self.position_count >= self.config.max_concurrent_positions:
            return (
                False,
                f"Position limit reached: {self.position_count}/{self.config.max_concurrent_positions} concurrent positions active",
            )

        if proposed_shares <= 0 or entry_price <= 0.0:
            return False, f"Invalid shares ({proposed_shares}) or price ({entry_price})"

        proposed_notional = proposed_shares * entry_price
        cost_buffer = self.config.breakeven_cost_buffer_pct
        required_cash = proposed_notional * (1.0 + cost_buffer)

        if required_cash > self.cash:
            return (
                False,
                f"Insufficient unallocated cash: required ₹{required_cash:,.2f} > available ₹{self.cash:,.2f}",
            )

        equity = self.get_portfolio_equity(current_prices)
        new_total_invested = self.total_invested_capital() + proposed_notional
        if new_total_invested > (equity * self.config.max_portfolio_exposure_pct):
            return (
                False,
                f"Portfolio exposure cap exceeded: ₹{new_total_invested:,.2f} > 100% equity ₹{equity:,.2f}",
            )

        sec = sector or self.config.symbol_sector_map.get(symbol, "General")
        curr_sector_val = self.get_sector_exposure(sec, current_prices)
        if (curr_sector_val + proposed_notional) > (equity * self.config.max_sector_exposure_pct):
            return (
                False,
                f"Sector cap exceeded for {sec}: ₹{curr_sector_val + proposed_notional:,.2f} > 40% equity ₹{equity:,.2f}",
            )

        return True, "Portfolio rules satisfied"

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
        isin: Optional[str] = None,
    ) -> DTPActivePosition:
        """Records a new open delivery position and deducts purchase cash."""
        sec = sector or self.config.symbol_sector_map.get(symbol, "General")
        isin_code = isin or self.config.symbol_isin_map.get(symbol, "DEFAULT_ISIN")

        cost = shares * entry_price
        self.cash -= cost

        pos = DTPActivePosition(
            symbol=symbol,
            isin=isin_code,
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

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        net_proceeds: float,
    ) -> DTPActivePosition:
        """Removes closed position and returns net cash proceeds to ledger."""
        if symbol not in self.positions:
            raise KeyError(f"No active position for {symbol} to close")

        pos = self.positions.pop(symbol)
        self.cash += net_proceeds
        return pos

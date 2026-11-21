"""
SignalForge — Core Capital Allocation Management System
========================================================
File: src/core/capital_allocation.py

Enables user-selectable capital allocation across SignalForge trading strategies.
Features:
- Presets: ₹10,000, ₹25,000, ₹50,000, ₹1,00,000, ₹2,00,000, or Custom Amount.
- Strict Ring-Fencing: When a user allocates a sub-portion of their total balance
  (e.g., ₹10,000 allocated from a ₹30,000 total balance), the strategy is strictly
  restricted to using ONLY the allocated amount.
- Position Sizing & Cash Discipline: Sizing and available cash checks are bounded
  entirely by the allocated equity and cash bucket; unallocated funds are never touched.
- Integer Quantity Enforcement: Zero fractional shares; all allocations enforce floor integers.
- Trade Rejection: Proactively rejects any order where required capital exceeds allocated cash.
- Multi-Allocation Isolation: Maintains independent performance, P&L, drawdowns, and trade
  histories for different capital allocations.
- Full Telemetry & State Display: Real-time tracking of selected capital, available cash,
  invested amount, realized/unrealized P&L, and total returns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple


PRESET_CAPITAL_ALLOCATIONS: List[float] = [
    10_000.0,
    25_000.0,
    50_000.0,
    100_000.0,
    200_000.0,
]

PRESET_LABELS: Dict[float, str] = {
    10_000.0: "₹10,000 (Starter)",
    25_000.0: "₹25,000 (Conservative)",
    50_000.0: "₹50,000 (Moderate)",
    100_000.0: "₹1,00,000 (Standard)",
    200_000.0: "₹2,00,000 (Growth)",
}


class AllocationType(str, Enum):
    PRESET_10K = "10K"
    PRESET_25K = "25K"
    PRESET_50K = "50K"
    PRESET_1L = "1L"
    PRESET_2L = "2L"
    CUSTOM = "CUSTOM"


def classify_allocation_type(amount: float) -> AllocationType:
    """Classifies an allocation amount into a preset or custom type."""
    if math.isclose(amount, 10_000.0, rel_tol=1e-5):
        return AllocationType.PRESET_10K
    if math.isclose(amount, 25_000.0, rel_tol=1e-5):
        return AllocationType.PRESET_25K
    if math.isclose(amount, 50_000.0, rel_tol=1e-5):
        return AllocationType.PRESET_50K
    if math.isclose(amount, 100_000.0, rel_tol=1e-5):
        return AllocationType.PRESET_1L
    if math.isclose(amount, 200_000.0, rel_tol=1e-5):
        return AllocationType.PRESET_2L
    return AllocationType.CUSTOM


@dataclass
class AllocatedTradeRecord:
    """Record of a trade executed under a specific capital allocation."""

    trade_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    quantity: int  # Must be positive integer
    allocated_capital_at_entry: float
    entry_timestamp: datetime
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    entry_costs: float = 0.0
    exit_costs: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    exit_reason: Optional[str] = None
    status: str = "OPEN"  # "OPEN" or "CLOSED"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["entry_timestamp"] = self.entry_timestamp.isoformat() if self.entry_timestamp else None
        d["exit_timestamp"] = self.exit_timestamp.isoformat() if self.exit_timestamp else None
        return d


class CapitalAllocation:
    """
    Manages a ring-fenced capital allocation bucket.
    Guarantees that strategies NEVER access or draw down unallocated account balance.
    """

    def __init__(
        self,
        allocation_id: str,
        total_account_balance: float,
        allocated_capital: float,
        account_id: str = "default_account",
        notes: str = "",
    ) -> None:
        if allocated_capital <= 0 or math.isnan(allocated_capital) or math.isinf(allocated_capital):
            raise ValueError(f"Allocated capital must be positive and finite, got ₹{allocated_capital}")

        if total_account_balance <= 0 or math.isnan(total_account_balance) or math.isinf(total_account_balance):
            raise ValueError(f"Total account balance must be positive and finite, got ₹{total_account_balance}")

        if allocated_capital > total_account_balance:
            raise ValueError(
                f"Allocated capital ₹{allocated_capital:,.2f} cannot exceed total account balance ₹{total_account_balance:,.2f}"
            )

        self.allocation_id: str = str(allocation_id)
        self.account_id: str = str(account_id)
        self.total_account_balance: float = float(total_account_balance)
        self.allocated_capital: float = float(allocated_capital)
        self.notes: str = str(notes)
        self.allocation_type: AllocationType = classify_allocation_type(self.allocated_capital)

        # Available cash in the allocated bucket
        self.available_cash: float = float(allocated_capital)

        # Invested capital (cost basis of open positions)
        self.invested_amount: float = 0.0

        # Current market value of open positions (mark-to-market)
        self.current_position_value: float = 0.0

        # Cumulative performance
        self.realized_pnl: float = 0.0
        self.unrealized_pnl: float = 0.0
        self.total_costs: float = 0.0

        # Equity Tracking
        self.peak_equity: float = float(allocated_capital)
        self.max_drawdown_inr: float = 0.0
        self.max_drawdown_pct: float = 0.0

        # Positions and Trade History
        self.open_positions: Dict[str, AllocatedTradeRecord] = {}
        self.completed_trades: List[AllocatedTradeRecord] = []

        now = datetime.now(timezone.utc)
        self.created_at: datetime = now
        self.updated_at: datetime = now

    @property
    def unallocated_cash(self) -> float:
        """Cash in total account that is strictly ring-fenced from the strategy."""
        return max(0.0, self.total_account_balance - self.allocated_capital)

    @property
    def ring_fenced_cash(self) -> float:
        """Alias for unallocated_cash strictly ring-fenced from the strategy."""
        return self.unallocated_cash

    @property
    def total_equity(self) -> float:
        """Current equity within the allocated container = cash + position market value."""
        return self.available_cash + self.current_position_value

    @property
    def total_returns_inr(self) -> float:
        """Nominal return in INR relative to the selected capital."""
        return self.total_equity - self.allocated_capital

    @property
    def total_returns_amount(self) -> float:
        """Alias for nominal return in INR relative to the selected capital."""
        return self.total_returns_inr

    @property
    def total_returns_pct(self) -> float:
        """Return percentage relative to the selected capital."""
        if self.allocated_capital <= 0:
            return 0.0
        return ((self.total_equity / self.allocated_capital) - 1.0) * 100.0

    @property
    def current_drawdown_inr(self) -> float:
        """Current drawdown from peak in INR."""
        return max(0.0, self.peak_equity - self.total_equity)

    @property
    def current_drawdown_pct(self) -> float:
        """Current drawdown percentage from peak."""
        if self.peak_equity <= 0:
            return 0.0
        return (self.current_drawdown_inr / self.peak_equity) * 100.0

    @property
    def closed_trades_count(self) -> int:
        """Total number of completed/closed trades."""
        return len(self.completed_trades)

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        risk_pct: float = 0.01,
        risk_fraction: Optional[float] = None,
        max_allocation_pct: float = 0.35,
        max_notional_pct: Optional[float] = None,
    ) -> Any:
        """
        Calculates position size strictly using allocated capital.
        - Enforces Rule 1: Never uses full account balance when smaller allocation is selected.
        - Enforces Rule 2: Strictly integer share quantities (floor rounding).
        - Enforces Rule 3: Never exceeds available allocated cash.
        """
        if entry_price <= 0:
            return 0

        actual_stop = stop_loss if stop_loss is not None else stop_loss_price
        if actual_stop is None:
            return 0

        risk_distance = abs(entry_price - actual_stop)
        if risk_distance <= 0:
            return 0

        actual_risk_pct = risk_fraction if risk_fraction is not None else risk_pct
        actual_max_alloc = max_notional_pct if max_notional_pct is not None else max_allocation_pct

        # Sizing is based STRICTLY on allocated equity, NEVER total_account_balance
        max_risk_inr = self.total_equity * actual_risk_pct
        shares_by_risk = int(math.floor(max_risk_inr / risk_distance))

        # Position notional cap
        max_notional_inr = self.total_equity * actual_max_alloc
        shares_by_notional = int(math.floor(max_notional_inr / entry_price))

        # Hard cash constraint: cannot exceed available cash within the allocated bucket
        shares_by_cash = int(math.floor(self.available_cash / entry_price))

        final_shares = max(0, min(shares_by_risk, shares_by_notional, shares_by_cash))
        return int(final_shares)

    def calculate_shares(
        self,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        risk_pct: float = 0.01,
        risk_fraction: Optional[float] = None,
        max_allocation_pct: float = 0.35,
        max_notional_pct: Optional[float] = None,
    ) -> int:
        """Direct alias for calculate_position_size returning integer shares."""
        return self.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            stop_loss=stop_loss,
            risk_pct=risk_pct,
            risk_fraction=risk_fraction,
            max_allocation_pct=max_allocation_pct,
            max_notional_pct=max_notional_pct,
        )

    def validate_trade(
        self,
        symbol: str,
        entry_price: Optional[float] = None,
        quantity: int = 0,
        price: Optional[float] = None,
        estimated_costs: float = 0.0,
    ) -> Tuple[bool, str]:
        """
        Validates whether a proposed order can be accommodated within the allocated capital.
        Rejects orders that exceed allocated cash.
        """
        px = price if price is not None else (entry_price or 0.0)
        if not isinstance(quantity, int) or quantity <= 0:
            return False, f"Trade rejected: Quantity must be a positive integer, got {quantity}"

        if px <= 0:
            return False, f"Trade rejected: Entry price must be positive, got ₹{px}"

        if symbol in self.open_positions:
            return False, f"Trade rejected: Active position already exists for symbol '{symbol}'"

        required_capital = (quantity * px) + estimated_costs
        if required_capital > self.available_cash:
            return False, (
                f"Trade rejected: Required capital ₹{required_capital:,.2f} exceeds available allocated cash "
                f"₹{self.available_cash:,.2f}. (Total account balance ₹{self.total_account_balance:,.2f} has "
                f"₹{self.unallocated_cash:,.2f} safely ring-fenced/unallocated)"
            )

        return True, "Trade approved within allocated capital."

    def open_position(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        entry_costs: float = 0.0,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> AllocatedTradeRecord:
        """
        Executes a position entry under the allocated capital bucket.
        Deducts funds strictly from available allocated cash.
        """
        valid, msg = self.validate_trade(symbol, entry_price, quantity, estimated_costs=entry_costs)
        if not valid:
            raise ValueError(msg)

        now = timestamp or datetime.now(timezone.utc)
        record = AllocatedTradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            side=side.upper(),
            entry_price=entry_price,
            quantity=int(quantity),
            allocated_capital_at_entry=self.allocated_capital,
            entry_timestamp=now,
            stop_loss=stop_loss,
            target=target,
            entry_costs=entry_costs,
            status="OPEN",
        )

        cost_outflow = (quantity * entry_price) + entry_costs
        self.available_cash -= cost_outflow
        self.invested_amount += quantity * entry_price
        self.current_position_value += quantity * entry_price
        self.total_costs += entry_costs
        self.open_positions[symbol] = record
        self.updated_at = now

        # Update peak equity
        self._refresh_peak_and_drawdown()
        return record

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_costs: float = 0.0,
        exit_reason: str = "TARGET_OR_STOP",
        timestamp: Optional[datetime] = None,
    ) -> AllocatedTradeRecord:
        """
        Closes an open position and credits proceeds back into allocated cash.
        """
        if symbol not in self.open_positions:
            raise KeyError(f"No active position found for symbol '{symbol}'")

        if exit_price <= 0:
            raise ValueError(f"Exit price must be positive, got ₹{exit_price}")

        now = timestamp or datetime.now(timezone.utc)
        record = self.open_positions.pop(symbol)

        record.exit_price = exit_price
        record.exit_timestamp = now
        record.exit_costs = exit_costs
        record.exit_reason = exit_reason
        record.status = "CLOSED"

        # Calculate PnL
        if record.side == "BUY":
            gross_pnl = (exit_price - record.entry_price) * record.quantity
        else:
            gross_pnl = (record.entry_price - exit_price) * record.quantity

        all_costs = record.entry_costs + exit_costs
        net_pnl = gross_pnl - all_costs

        record.gross_pnl = gross_pnl
        record.net_pnl = net_pnl

        # Cash return: entry notional + gross_pnl - exit_costs
        cash_inflow = (record.quantity * exit_price) - exit_costs
        self.available_cash += cash_inflow
        self.invested_amount -= record.quantity * record.entry_price
        self.realized_pnl += net_pnl
        self.total_costs += exit_costs

        self.completed_trades.append(record)
        self.updated_at = now

        # Recompute open position mark-to-market
        self._recompute_open_position_value()
        self._refresh_peak_and_drawdown()
        return record

    def execute_trade(
        self,
        trade_id: str,
        symbol: str,
        quantity: int,
        price: Optional[float] = None,
        entry_price: Optional[float] = None,
        side: str = "BUY",
        statutory_costs: float = 0.0,
        entry_costs: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> AllocatedTradeRecord:
        """Alias for open_position supporting common trade execution kwargs."""
        px = price if price is not None else (entry_price or 0.0)
        costs = statutory_costs if statutory_costs > 0 else (entry_costs or 0.0)
        return self.open_position(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=px,
            entry_costs=costs,
            stop_loss=stop_loss,
            target=target,
            timestamp=timestamp,
        )

    def close_trade(
        self,
        trade_id: Optional[str] = None,
        symbol: Optional[str] = None,
        exit_price: float = 0.0,
        exit_costs: float = 0.0,
        exit_reason: str = "TARGET_OR_STOP",
        timestamp: Optional[datetime] = None,
    ) -> AllocatedTradeRecord:
        """Alias for close_position supporting lookup by trade_id or symbol."""
        target_symbol = symbol
        if target_symbol is None and trade_id is not None:
            for s, rec in self.open_positions.items():
                if rec.trade_id == trade_id:
                    target_symbol = s
                    break
        if target_symbol is None:
            raise KeyError(f"No active position found for trade_id='{trade_id}' or symbol='{symbol}'")
        return self.close_position(
            symbol=target_symbol,
            exit_price=exit_price,
            exit_costs=exit_costs,
            exit_reason=exit_reason,
            timestamp=timestamp,
        )

    def update_market_price(self, symbol: str, current_price: float) -> None:
        """Updates the mark-to-market price for an open position."""
        if symbol in self.open_positions and current_price > 0:
            self._recompute_open_position_value(override_prices={symbol: current_price})
            self._refresh_peak_and_drawdown()

    def _recompute_open_position_value(self, override_prices: Optional[Dict[str, float]] = None) -> None:
        """Recomputes mark-to-market open position values and unrealized P&L."""
        prices = override_prices or {}
        val = 0.0
        u_pnl = 0.0

        for sym, rec in self.open_positions.items():
            px = prices.get(sym, rec.entry_price)
            pos_val = rec.quantity * px
            val += pos_val
            if rec.side == "BUY":
                u_pnl += (px - rec.entry_price) * rec.quantity
            else:
                u_pnl += (rec.entry_price - px) * rec.quantity

        self.current_position_value = val
        self.unrealized_pnl = u_pnl

    def _refresh_peak_and_drawdown(self) -> None:
        """Updates peak equity and maximum drawdown records."""
        curr_eq = self.total_equity
        if curr_eq > self.peak_equity:
            self.peak_equity = curr_eq

        dd_inr = self.peak_equity - curr_eq
        dd_pct = (dd_inr / self.peak_equity * 100.0) if self.peak_equity > 0 else 0.0

        if dd_inr > self.max_drawdown_inr:
            self.max_drawdown_inr = dd_inr
        if dd_pct > self.max_drawdown_pct:
            self.max_drawdown_pct = dd_pct

    def get_display_summary(self) -> Dict[str, Any]:
        """
        Returns full telemetry and state display as required by Requirement 5.
        """
        return {
            "allocation_id": self.allocation_id,
            "account_id": self.account_id,
            "allocation_type": self.allocation_type.value,
            "selected_capital": round(self.allocated_capital, 2),
            "total_account_balance": round(self.total_account_balance, 2),
            "unallocated_cash": round(self.unallocated_cash, 2),
            "ring_fenced_cash": round(self.unallocated_cash, 2),
            "available_cash": round(self.available_cash, 2),
            "invested_amount": round(self.invested_amount, 2),
            "current_position_value": round(self.current_position_value, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_costs": round(self.total_costs, 2),
            "total_equity": round(self.total_equity, 2),
            "total_returns_inr": round(self.total_returns_inr, 2),
            "total_returns_amount": round(self.total_returns_inr, 2),
            "total_returns_pct": round(self.total_returns_pct, 2),
            "peak_equity": round(self.peak_equity, 2),
            "current_drawdown_inr": round(self.current_drawdown_inr, 2),
            "current_drawdown_pct": round(self.current_drawdown_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "open_positions_count": len(self.open_positions),
            "completed_trades_count": len(self.completed_trades),
            "closed_trades_count": len(self.completed_trades),
        }


class CapitalAllocationManager:
    """
    Registry that maintains separate performance results for different capital allocations.
    Allows concurrent tracking of ₹10K, ₹25K, ₹50K, ₹1L, ₹2L, and custom allocations.
    """

    def __init__(self) -> None:
        self._allocations: Dict[str, CapitalAllocation] = {}

    def create_allocation(
        self,
        allocation_id: str,
        total_account_balance: float,
        allocated_capital: float,
        account_id: str = "default_account",
        notes: str = "",
    ) -> CapitalAllocation:
        """Creates and stores a new isolated capital allocation container."""
        if allocation_id in self._allocations:
            raise KeyError(f"Allocation with ID '{allocation_id}' already exists")

        alloc = CapitalAllocation(
            allocation_id=allocation_id,
            total_account_balance=total_account_balance,
            allocated_capital=allocated_capital,
            account_id=account_id,
            notes=notes,
        )
        self._allocations[allocation_id] = alloc
        return alloc

    def get_allocation(self, allocation_id: str) -> CapitalAllocation:
        """Retrieves an existing capital allocation."""
        if allocation_id not in self._allocations:
            raise KeyError(f"Allocation '{allocation_id}' not found")
        return self._allocations[allocation_id]

    def get_or_create(
        self,
        allocation_id: str,
        total_account_balance: float,
        allocated_capital: float,
        account_id: str = "default_account",
    ) -> CapitalAllocation:
        """Retrieves an existing allocation or creates a new one if not present."""
        if allocation_id in self._allocations:
            return self._allocations[allocation_id]
        return self.create_allocation(allocation_id, total_account_balance, allocated_capital, account_id)

    def list_allocations(self) -> List[CapitalAllocation]:
        """Lists all active allocations."""
        return list(self._allocations.values())

    def get_all_summaries(self) -> List[Dict[str, Any]]:
        """Returns telemetry summaries for all registered allocations."""
        return [alloc.get_display_summary() for alloc in self.list_allocations()]

    def remove_allocation(self, allocation_id: str) -> None:
        """Removes an allocation from the manager."""
        if allocation_id in self._allocations:
            del self._allocations[allocation_id]

    def clear(self) -> None:
        """Clears all allocations."""
        self._allocations.clear()


# Global Singleton Manager
_default_manager: Optional[CapitalAllocationManager] = None


def get_capital_allocation_manager() -> CapitalAllocationManager:
    """Returns the global CapitalAllocationManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = CapitalAllocationManager()
    return _default_manager

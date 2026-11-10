"""Portfolio management for SignalForge backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.backtest.indian_market_costs import IntradayCostConfig
from src.backtest.simulator import Position, Trade, simulate_trade


class PortfolioError(Exception):
    """Base exception for portfolio management operations."""


class DuplicatePositionError(PortfolioError, ValueError):
    """Raised when attempting to open a duplicate active position for the same symbol."""


class InsufficientMarginError(PortfolioError, ValueError):
    """Raised when available margin is insufficient to encumber a new position."""


class PositionNotFoundError(PortfolioError, KeyError):
    """Raised when closing or accessing a non-existent position."""


class AllocationExceededError(PortfolioError, ValueError):
    """Raised when a position exceeds maximum allowable allocation limits."""


class PortfolioBankruptError(PortfolioError, RuntimeError):
    """Raised when attempting trading actions on a bankrupt portfolio."""


@dataclass
class OpenPosition:
    """
    Representation of an active open position in a single symbol.

    Parameters
    ----------
    symbol:
        Market symbol (e.g. 'RELIANCE', 'ICICIBANK').
    side:
        Position direction (Position.LONG or Position.SHORT).
    entry_time:
        Timestamp representing entry.
    entry_price:
        Price at entry.
    quantity:
        Number of units/shares.
    stop_price:
        Stop-loss trigger price.
    target_price:
        Take-profit trigger price.
    allocated_margin:
        Margin encumbered for this position.
    risk_amount:
        Rupee risk planned for this trade.
    atr:
        ATR value frozen at entry.
    stop_distance:
        Absolute distance to stop loss.
    capital_before:
        Account cash before entry.
    risk_based_quantity:
        Quantity calculated from risk model.
    max_allowed_quantity:
        Quantity capped by leverage/notional limits.
    """

    symbol: str
    side: Position
    entry_time: object
    entry_price: float
    quantity: int
    stop_price: float = 0.0
    target_price: float = 0.0
    allocated_margin: float = 0.0
    risk_amount: float = 0.0
    atr: float = 0.0
    stop_distance: float = 0.0
    capital_before: float = 0.0
    risk_based_quantity: int = 0
    max_allowed_quantity: int = 0
    pending_liquidation: bool = False
    pending_liquidation_reason: Optional[str] = None
    is_stale: bool = False
    current_price: float = field(init=False)
    highest_price: float = field(init=False)
    lowest_price: float = field(init=False)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol).strip().upper()
        if isinstance(self.side, str):
            self.side = Position(self.side)
        self.entry_price = float(self.entry_price)
        self.quantity = int(self.quantity)
        self.current_price = self.entry_price
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price

    def unrealized_pnl(self, price: Optional[float] = None) -> float:
        """
        Compute mark-to-market unrealized P&L at the given or current price.
        """
        if price is not None:
            self.current_price = float(price)
            if self.current_price > self.highest_price:
                self.highest_price = self.current_price
            if self.current_price < self.lowest_price:
                self.lowest_price = self.current_price

        if self.side == Position.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def notional_value(self) -> float:
        """Entry notional value (entry_price * quantity)."""
        return self.entry_price * self.quantity

    @property
    def current_market_value(self) -> float:
        """Current mark-to-market value (current_price * quantity)."""
        return self.current_price * self.quantity

    @property
    def unrealized_return_pct(self) -> float:
        """Mark-to-market return percentage based on entry notional."""
        if self.notional_value > 0:
            return (self.unrealized_pnl() / self.notional_value) * 100.0
        return 0.0


class PortfolioManager:
    """
    Intelligent Portfolio and Capital Allocation Engine for Multi-Stock Intraday Trading.

    Manages multi-stock intraday positions, margin encumbrances, mark-to-market
    valuations, available collateral, liquidity reserves, and portfolio drawdown.
    """

    def __init__(
        self,
        initial_capital: float,
        max_leverage: float = 5.0,
        reserve_capital_pct: float = 0.0,
        reserve_capital_fixed: float = 0.0,
        capital_protection_floor: Optional[float] = None,
        overall_loss_limit: Optional[float] = None,
        max_stock_allocation_pct: float = 1.0,
    ) -> None:
        if not isinstance(initial_capital, (int, float)) or isinstance(initial_capital, bool):
            raise TypeError("initial_capital must be numeric.")
        if initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero.")

        if not isinstance(max_leverage, (int, float)) or isinstance(max_leverage, bool):
            raise TypeError("max_leverage must be numeric.")
        if max_leverage <= 0:
            raise ValueError("max_leverage must be greater than zero.")

        if not isinstance(reserve_capital_pct, (int, float)) or isinstance(reserve_capital_pct, bool):
            raise TypeError("reserve_capital_pct must be numeric.")
        if not (0.0 <= reserve_capital_pct <= 1.0):
            raise ValueError("reserve_capital_pct must be between 0.0 and 1.0.")

        if not isinstance(reserve_capital_fixed, (int, float)) or isinstance(reserve_capital_fixed, bool):
            raise TypeError("reserve_capital_fixed must be numeric.")
        if reserve_capital_fixed < 0:
            raise ValueError("reserve_capital_fixed cannot be negative.")

        if capital_protection_floor is not None:
            if not isinstance(capital_protection_floor, (int, float)) or isinstance(capital_protection_floor, bool):
                raise TypeError("capital_protection_floor must be numeric.")
            if capital_protection_floor < 0:
                raise ValueError("capital_protection_floor cannot be negative.")

        if overall_loss_limit is not None:
            if not isinstance(overall_loss_limit, (int, float)) or isinstance(overall_loss_limit, bool):
                raise TypeError("overall_loss_limit must be numeric.")
            if overall_loss_limit < 0:
                raise ValueError("overall_loss_limit cannot be negative.")

        if not isinstance(max_stock_allocation_pct, (int, float)) or isinstance(max_stock_allocation_pct, bool):
            raise TypeError("max_stock_allocation_pct must be numeric.")
        if not (0.0 < max_stock_allocation_pct <= 1.0):
            raise ValueError("max_stock_allocation_pct must be between 0.0 and 1.0.")

        self.initial_capital: float = float(initial_capital)
        self.max_leverage: float = float(max_leverage)
        self.reserve_capital_pct: float = float(reserve_capital_pct)
        self.reserve_capital_fixed: float = float(reserve_capital_fixed)
        self.capital_protection_floor: Optional[float] = (
            float(capital_protection_floor) if capital_protection_floor is not None else None
        )
        self.overall_loss_limit: Optional[float] = (
            float(overall_loss_limit) if overall_loss_limit is not None else None
        )
        self.max_stock_allocation_pct: float = float(max_stock_allocation_pct)

        self.cash: float = float(initial_capital)
        self.peak_equity: float = float(initial_capital)
        self.max_drawdown: float = 0.0
        self.is_bankrupt: bool = False
        self.bankruptcy_reason: Optional[str] = None
        self.has_indeterminate_valuation: bool = False
        self.indeterminate_valuation_reason: Optional[str] = None

        self.open_positions: dict[str, OpenPosition] = {}
        self.trades: list[Trade] = []

    @property
    def effective_protection_floor(self) -> Optional[float]:
        """Return the effective capital protection floor in rupees."""
        if self.capital_protection_floor is not None:
            return self.capital_protection_floor
        if self.overall_loss_limit is not None:
            return max(0.0, self.initial_capital - self.overall_loss_limit)
        return None

    @property
    def unrealized_pnl(self) -> float:
        """Return sum of mark-to-market unrealized P&L across all open positions."""
        return sum(pos.unrealized_pnl() for pos in self.open_positions.values())

    @property
    def equity(self) -> float:
        """Return current portfolio mark-to-market equity (cash + unrealized P&L)."""
        return self.cash + self.unrealized_pnl

    @property
    def allocated_margin(self) -> float:
        """Return total margin encumbered across all open positions."""
        return sum(pos.allocated_margin for pos in self.open_positions.values())

    @property
    def reserved_capital(self) -> float:
        """Return reserved capital buffer for liquidity."""
        pct_reserve = max(0.0, self.equity * self.reserve_capital_pct)
        return max(self.reserve_capital_fixed, pct_reserve)

    @property
    def available_margin(self) -> float:
        """
        Return available margin collateral for opening new positions.

        Available Margin = (Equity - Reserved Capital) - Allocated Margin.
        """
        usable_equity = self.equity - self.reserved_capital
        return max(0.0, usable_equity - self.allocated_margin)

    @property
    def gross_exposure(self) -> float:
        """Return total notional exposure of all active positions."""
        return sum(pos.notional_value for pos in self.open_positions.values())

    @property
    def effective_leverage(self) -> float:
        """Return current effective portfolio leverage ratio."""
        if self.equity > 0:
            return self.gross_exposure / self.equity
        return 0.0

    @property
    def total_pnl(self) -> float:
        """Return total net realized P&L from all completed trades."""
        return sum(trade.net_pnl for trade in self.trades)

    @property
    def total_return_pct(self) -> float:
        """Return total portfolio return percentage based on current MTM equity."""
        return ((self.equity - self.initial_capital) / self.initial_capital) * 100.0

    @property
    def trade_count(self) -> int:
        """Return count of completed trades."""
        return len(self.trades)

    @property
    def open_position_count(self) -> int:
        """Return count of currently open positions."""
        return len(self.open_positions)

    @property
    def current_drawdown(self) -> float:
        """Return current percentage drawdown from peak equity."""
        if self.peak_equity > 0:
            return max(0.0, ((self.peak_equity - self.equity) / self.peak_equity) * 100.0)
        return 0.0

    def _update_risk_and_drawdown(self) -> None:
        """Update peak equity, maximum drawdown, and check bankruptcy/floor breaches."""
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        dd = self.current_drawdown
        if dd > self.max_drawdown:
            self.max_drawdown = dd

        # Bankruptcy / Capital exhaustion
        if self.equity <= 0:
            self.is_bankrupt = True
            if self.bankruptcy_reason is None:
                self.bankruptcy_reason = "CAPITAL_EXHAUSTED"

        # Protection floor breach
        floor = self.effective_protection_floor
        if floor is not None and self.equity <= floor:
            self.is_bankrupt = True
            if self.bankruptcy_reason is None:
                self.bankruptcy_reason = "PROTECTION_FLOOR"

    @property
    def has_unresolved_liquidations(self) -> bool:
        """Check if any open position has pending emergency liquidation awaiting executable market data."""
        return any(pos.pending_liquidation for pos in self.open_positions.values())

    @property
    def unresolved_liquidation_positions(self) -> list[OpenPosition]:
        """Return list of open positions pending emergency liquidation."""
        return [pos for pos in self.open_positions.values() if pos.pending_liquidation]

    def mark_pending_liquidation(self, symbol: str, reason: str = "EMERGENCY_LIQUIDATION") -> None:
        """Mark an open position as pending liquidation when no executable market price exists."""
        sym = str(symbol).strip().upper()
        if sym in self.open_positions:
            self.open_positions[sym].pending_liquidation = True
            self.open_positions[sym].pending_liquidation_reason = reason

    def can_open_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        leverage: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Check if a new position can be opened.

        Returns (True, "OK") or (False, reason).
        """
        sym = str(symbol).strip().upper()

        if self.is_bankrupt:
            return False, f"Portfolio is bankrupt ({self.bankruptcy_reason})"

        if self.has_unresolved_liquidations:
            return False, "Portfolio has unresolved emergency liquidations pending valid market data"

        if self.has_indeterminate_valuation:
            return False, f"Portfolio has indeterminate valuation: {self.indeterminate_valuation_reason}"

        if sym in self.open_positions:
            return False, f"Active position already open for symbol '{sym}'"

        if entry_price <= 0:
            return False, "entry_price must be positive"

        if quantity <= 0:
            return False, "quantity must be positive"

        eff_lev = float(leverage) if leverage is not None else self.max_leverage
        if eff_lev <= 0:
            return False, "leverage must be positive"

        notional = float(entry_price) * quantity
        req_margin = notional / eff_lev

        if req_margin > self.available_margin:
            return False, (
                f"Insufficient margin: requires {req_margin:.2f}, "
                f"available {self.available_margin:.2f}"
            )

        max_alloc = self.equity * self.max_leverage * self.max_stock_allocation_pct
        if notional > max_alloc:
            return False, (
                f"Notional exposure ({notional:.2f}) exceeds max allocation "
                f"({max_alloc:.2f}) for symbol '{sym}'"
            )

        return True, "OK"

    def open_position(
        self,
        symbol: str,
        side: Position | str,
        entry_time: object,
        entry_price: float,
        quantity: int,
        stop_price: float = 0.0,
        target_price: float = 0.0,
        risk_amount: float = 0.0,
        atr: float = 0.0,
        stop_distance: float = 0.0,
        leverage: Optional[float] = None,
        risk_based_quantity: int = 0,
        max_allowed_quantity: int = 0,
    ) -> OpenPosition:
        """
        Open a new position, encumbering margin collateral.

        Allocated margin is an encumbrance on available collateral, NOT an expense.
        Realized cash is unchanged.
        """
        sym = str(symbol).strip().upper()

        if self.is_bankrupt:
            raise PortfolioBankruptError(
                f"Cannot open position for {sym}: portfolio is bankrupt ({self.bankruptcy_reason})"
            )

        if self.has_unresolved_liquidations:
            raise PortfolioBankruptError(
                f"Cannot open position for {sym}: portfolio has unresolved emergency liquidations"
            )

        if sym in self.open_positions:
            raise DuplicatePositionError(
                f"Duplicate active position: symbol '{sym}' is already open."
            )

        if not isinstance(entry_price, (int, float)) or entry_price <= 0:
            raise ValueError("entry_price must be a positive number.")

        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("quantity must be a positive integer.")

        eff_lev = float(leverage) if leverage is not None else self.max_leverage
        if eff_lev <= 0:
            raise ValueError("leverage must be greater than zero.")

        notional = float(entry_price) * quantity
        req_margin = notional / eff_lev

        if req_margin > self.available_margin:
            raise InsufficientMarginError(
                f"Insufficient available margin ({self.available_margin:.2f}) "
                f"to open {sym} (requires {req_margin:.2f})"
            )

        max_alloc = self.equity * self.max_leverage * self.max_stock_allocation_pct
        if notional > max_alloc:
            raise AllocationExceededError(
                f"Notional exposure ({notional:.2f}) exceeds max allocation "
                f"({max_alloc:.2f}) for symbol '{sym}'"
            )

        pos_side = Position(side) if isinstance(side, str) else side

        pos = OpenPosition(
            symbol=sym,
            side=pos_side,
            entry_time=entry_time,
            entry_price=float(entry_price),
            quantity=quantity,
            stop_price=float(stop_price),
            target_price=float(target_price),
            allocated_margin=req_margin,
            risk_amount=float(risk_amount),
            atr=float(atr),
            stop_distance=float(stop_distance),
            capital_before=self.cash,
            risk_based_quantity=risk_based_quantity,
            max_allowed_quantity=max_allowed_quantity,
        )

        self.open_positions[sym] = pos
        self._update_risk_and_drawdown()
        return pos

    def close_position(
        self,
        symbol: str,
        exit_time: object,
        exit_price: float,
        exit_reason: str = "SIGNAL",
        brokerage: float = 0.0,
        slippage_rate: float = 0.0,
        statutory_fee_rate: float = 0.0,
        transaction_cost_rate: float = 0.0,
        cost_config: Optional[IntradayCostConfig] = None,
    ) -> Trade:
        """
        Close an active open position.

        Releases the allocated margin encumbrance and updates realized cash
        with the trade's net P&L (after exactly one deduction of transaction costs).
        """
        sym = str(symbol).strip().upper()

        if sym not in self.open_positions:
            raise PositionNotFoundError(
                f"No active open position found for symbol '{symbol}'"
            )

        pos = self.open_positions.pop(sym)
        capital_before = self.cash

        trade = simulate_trade(
            position=pos.side,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_price=pos.entry_price,
            exit_price=float(exit_price),
            quantity=pos.quantity,
            brokerage=brokerage,
            slippage_rate=slippage_rate,
            statutory_fee_rate=statutory_fee_rate,
            transaction_cost_rate=transaction_cost_rate,
            exit_reason=exit_reason,
            capital_before=capital_before,
            capital_after=capital_before,
            risk_amount=pos.risk_amount,
            atr=pos.atr,
            stop_distance=pos.stop_distance,
            risk_based_quantity=pos.risk_based_quantity,
            max_allowed_quantity=pos.max_allowed_quantity,
            cost_config=cost_config,
            symbol=pos.symbol,
        )

        self.cash += trade.net_pnl
        self.trades.append(trade)
        self._update_risk_and_drawdown()
        return trade

    def close_all_positions(
        self,
        exit_time: object,
        exit_prices: Optional[dict[str, float]] = None,
        exit_reason: str = "EOD",
        brokerage: float = 0.0,
        slippage_rate: float = 0.0,
        statutory_fee_rate: float = 0.0,
        transaction_cost_rate: float = 0.0,
        cost_config: Optional[IntradayCostConfig] = None,
        require_executable_price: bool = False,
    ) -> list[Trade]:
        """
        Close all active open positions (e.g. at session boundary).

        If require_executable_price is True:
        Positions without an explicit executable price in exit_prices are marked as
        pending_liquidation instead of fabricating a synthetic fill. Margin remains encumbered.

        Returns list of closed trades.
        """
        closed_trades: list[Trade] = []
        open_symbols = list(self.open_positions.keys())
        for sym in open_symbols:
            pos = self.open_positions[sym]
            has_explicit_price = (
                exit_prices is not None and sym in exit_prices and exit_prices[sym] is not None
            )

            if require_executable_price and not has_explicit_price:
                # Do NOT fabricate fill! Mark pending liquidation and leave margin encumbered
                pos.pending_liquidation = True
                pos.pending_liquidation_reason = exit_reason
                continue

            price = exit_prices[sym] if has_explicit_price else pos.current_price
            trade = self.close_position(
                symbol=sym,
                exit_time=exit_time,
                exit_price=price,
                exit_reason=exit_reason,
                brokerage=brokerage,
                slippage_rate=slippage_rate,
                statutory_fee_rate=statutory_fee_rate,
                transaction_cost_rate=transaction_cost_rate,
                cost_config=cost_config,
            )
            closed_trades.append(trade)
        return closed_trades

    def update_price(self, symbol: str, price: float) -> None:
        """Update mark-to-market valuation for a single symbol."""
        sym = str(symbol).strip().upper()
        if sym in self.open_positions:
            self.open_positions[sym].unrealized_pnl(float(price))
            self._update_risk_and_drawdown()

    def update_market_prices(self, prices: dict[str, float]) -> None:
        """Update mark-to-market valuations for multiple symbols simultaneously."""
        for sym, price in prices.items():
            sym_upper = str(sym).strip().upper()
            if sym_upper in self.open_positions:
                self.open_positions[sym_upper].unrealized_pnl(float(price))
        self._update_risk_and_drawdown()

    def apply_trade(self, trade: Trade) -> None:
        """
        Apply a completed trade to the portfolio (for backward compatibility).

        Only the trade's net P&L changes account cash/equity.
        """
        if not isinstance(trade, Trade):
            raise TypeError("trade must be a Trade.")

        self.cash += trade.net_pnl
        self.trades.append(trade)
        self._update_risk_and_drawdown()

    def reset(self) -> None:
        """Reset the portfolio to its initial state."""
        self.cash = float(self.initial_capital)
        self.peak_equity = float(self.initial_capital)
        self.max_drawdown = 0.0
        self.is_bankrupt = False
        self.bankruptcy_reason = None
        self.open_positions.clear()
        self.trades.clear()


class Portfolio(PortfolioManager):
    """
    Manage account capital and completed trades.

    Retained for 100% backward compatibility with single-instrument workflows.
    Inherits full multi-position capabilities from PortfolioManager.
    """

    def __init__(self, initial_capital: float) -> None:
        super().__init__(initial_capital=initial_capital)

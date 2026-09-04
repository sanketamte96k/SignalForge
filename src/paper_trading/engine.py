from datetime import datetime

from src.backtest.simulator import Position

from src.paper_trading.models import (
    PaperOrder,
    PaperPosition,
    PaperTrade,
    PaperTradingState,
)


class PaperTradingEngine:
    """
    Simple paper-trading engine.

    Responsibilities:
    - Open a paper position.
    - Close a paper position explicitly.
    - Reverse long/short positions.
    - Track realized P&L and transaction costs.
    - Store completed paper trades.

    Signal semantics:
    - LONG  -> open/hold/reverse to LONG
    - SHORT -> open/hold/reverse to SHORT
    - None  -> NO_TRADE / HOLD
    """

    def __init__(
        self,
        starting_capital: float,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0001,
    ) -> None:
        if starting_capital <= 0:
            raise ValueError("starting_capital must be positive")

        if quantity <= 0:
            raise ValueError("quantity must be positive")

        if transaction_cost_rate < 0:
            raise ValueError(
                "transaction_cost_rate cannot be negative"
            )

        self.quantity = quantity
        self.transaction_cost_rate = transaction_cost_rate

        self.state = PaperTradingState(
            starting_capital=starting_capital,
        )

    @property
    def completed_trades(self) -> list[PaperTrade]:
        """Return the completed paper trades."""
        return self.state.completed_trades

    @property
    def trade_count(self) -> int:
        """Return the number of completed trades."""
        return self.state.trade_count

    @property
    def realized_pnl(self) -> float:
        """Return total realized P&L."""
        return self.state.realized_pnl

    @property
    def total_transaction_cost(self) -> float:
        """Return total transaction costs."""
        return self.state.total_transaction_cost

    @property
    def ending_equity(self) -> float:
        """Return current ending equity."""
        return self.state.current_equity

    def _validate_price(self, price: float) -> None:
        if price <= 0:
            raise ValueError("price must be positive")

    def _calculate_transaction_cost(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
    ) -> float:
        traded_value = (
            entry_price * quantity
            + exit_price * quantity
        )

        return traded_value * self.transaction_cost_rate

    def _calculate_gross_pnl(
        self,
        position: Position,
        entry_price: float,
        exit_price: float,
        quantity: int,
    ) -> float:
        if position == Position.LONG:
            return (exit_price - entry_price) * quantity

        if position == Position.SHORT:
            return (entry_price - exit_price) * quantity

        raise ValueError("Position must be LONG or SHORT")

    def _open_position(
        self,
        timestamp: datetime,
        position: Position,
        price: float,
        reason: str = "",
    ) -> PaperOrder:
        self._validate_price(price)

        if position not in (
            Position.LONG,
            Position.SHORT,
        ):
            raise ValueError(
                "Position must be LONG or SHORT"
            )

        if self.state.open_position is not None:
            raise ValueError(
                "A paper position is already open"
            )

        self.state.open_position = PaperPosition(
            position=position,
            entry_price=price,
            entry_time=timestamp,
            quantity=self.quantity,
        )

        return PaperOrder(
            timestamp=timestamp,
            position=position,
            price=price,
            quantity=self.quantity,
            reason=reason,
        )

    def _close_position(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> PaperTrade:
        self._validate_price(price)

        open_position = self.state.open_position

        if open_position is None:
            raise ValueError(
                "No paper position is open"
            )

        gross_pnl = self._calculate_gross_pnl(
            position=open_position.position,
            entry_price=open_position.entry_price,
            exit_price=price,
            quantity=open_position.quantity,
        )

        transaction_cost = self._calculate_transaction_cost(
            entry_price=open_position.entry_price,
            exit_price=price,
            quantity=open_position.quantity,
        )

        net_pnl = gross_pnl - transaction_cost

        trade = PaperTrade(
            position=open_position.position,
            entry_price=open_position.entry_price,
            exit_price=price,
            quantity=open_position.quantity,
            entry_time=open_position.entry_time,
            exit_time=timestamp,
            gross_pnl=gross_pnl,
            transaction_cost=transaction_cost,
            net_pnl=net_pnl,
            reason=reason,
        )

        self.state.realized_pnl += net_pnl
        self.state.total_transaction_cost += transaction_cost
        self.state.completed_trades.append(trade)
        self.state.open_position = None

        return trade

    def open_long(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> PaperOrder:
        return self._open_position(
            timestamp=timestamp,
            position=Position.LONG,
            price=price,
            reason=reason,
        )

    def open_short(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> PaperOrder:
        return self._open_position(
            timestamp=timestamp,
            position=Position.SHORT,
            price=price,
            reason=reason,
        )

    def close_position(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> PaperTrade:
        return self._close_position(
            timestamp=timestamp,
            price=price,
            reason=reason,
        )

    def reverse_to_long(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> tuple[PaperTrade, PaperOrder]:
        if self.state.open_position is None:
            raise ValueError(
                "No paper position to reverse"
            )

        if self.state.open_position.position == Position.LONG:
            raise ValueError("Already LONG")

        closed_trade = self.close_position(
            timestamp=timestamp,
            price=price,
            reason=reason,
        )

        new_order = self.open_long(
            timestamp=timestamp,
            price=price,
            reason=reason,
        )

        return closed_trade, new_order

    def reverse_to_short(
        self,
        timestamp: datetime,
        price: float,
        reason: str = "",
    ) -> tuple[PaperTrade, PaperOrder]:
        if self.state.open_position is None:
            raise ValueError(
                "No paper position to reverse"
            )

        if self.state.open_position.position == Position.SHORT:
            raise ValueError("Already SHORT")

        closed_trade = self.close_position(
            timestamp=timestamp,
            price=price,
            reason=reason,
        )

        new_order = self.open_short(
            timestamp=timestamp,
            price=price,
            reason=reason,
        )

        return closed_trade, new_order

    def process_signal(
        self,
        timestamp: datetime,
        signal: Position | None,
        price: float,
        reason: str = "",
    ) -> PaperOrder | tuple[PaperTrade, PaperOrder] | None:
        """
        Process a strategy position signal.

        Rules:
        - No position + LONG  -> open LONG
        - No position + SHORT -> open SHORT
        - No position + None  -> do nothing
        - LONG + LONG         -> do nothing
        - SHORT + SHORT       -> do nothing
        - LONG + SHORT        -> reverse to SHORT
        - SHORT + LONG        -> reverse to LONG
        - None signal         -> hold current position

        Explicit position closure must use close_position().
        """

        self._validate_price(price)

        current_position = self.state.open_position

        # NO_TRADE means HOLD.
        #
        # The strategy's None signal does not mean that
        # the current position should be closed.
        #
        # Explicit closure is handled separately through
        # close_position(), for example at session end.
        if signal is None:
            return None

        if current_position is None:
            if signal == Position.LONG:
                return self.open_long(
                    timestamp=timestamp,
                    price=price,
                    reason=reason,
                )

            if signal == Position.SHORT:
                return self.open_short(
                    timestamp=timestamp,
                    price=price,
                    reason=reason,
                )

            raise ValueError(
                "Signal must be LONG, SHORT, or None"
            )

        if current_position.position == signal:
            return None

        if signal == Position.LONG:
            return self.reverse_to_long(
                timestamp=timestamp,
                price=price,
                reason=reason,
            )

        if signal == Position.SHORT:
            return self.reverse_to_short(
                timestamp=timestamp,
                price=price,
                reason=reason,
            )

        raise ValueError(
            "Signal must be LONG, SHORT, or None"
        )
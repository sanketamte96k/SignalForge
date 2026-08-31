"""Trade simulation utilities for SignalForge."""

from dataclasses import dataclass
from enum import Enum


class Position(str, Enum):
    """Possible simulated position states."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class Trade:
    """A completed simulated trade."""

    entry_time: object
    exit_time: object
    position: Position
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    return_pct: float


def _validate_price(
    price: float,
    name: str,
) -> None:
    """Validate a price."""

    if not isinstance(price, (int, float)):
        raise TypeError(
            f"{name} must be numeric."
        )

    if price <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )


def _validate_quantity(
    quantity: float,
) -> None:
    """Validate trade quantity."""

    if not isinstance(quantity, (int, float)):
        raise TypeError(
            "quantity must be numeric."
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than zero."
        )


def _validate_cost_rate(
    transaction_cost_rate: float,
) -> None:
    """Validate transaction cost rate."""

    if not isinstance(
        transaction_cost_rate,
        (int, float),
    ):
        raise TypeError(
            "transaction_cost_rate must be numeric."
        )

    if transaction_cost_rate < 0:
        raise ValueError(
            "transaction_cost_rate cannot be negative."
        )


def simulate_trade(
    position: Position,
    entry_time: object,
    exit_time: object,
    entry_price: float,
    exit_price: float,
    quantity: float = 1.0,
    transaction_cost_rate: float = 0.0,
) -> Trade:
    """
    Simulate one completed trade.

    Parameters
    ----------
    position:
        LONG or SHORT.

    entry_time:
        Timestamp/object representing trade entry.

    exit_time:
        Timestamp/object representing trade exit.

    entry_price:
        Price at which the simulated position is opened.

    exit_price:
        Price at which the simulated position is closed.

    quantity:
        Number of units traded.

    transaction_cost_rate:
        Total transaction-cost rate applied to
        entry value + exit value.

    Returns
    -------
    Trade
        Completed simulated trade.
    """

    if not isinstance(position, Position):
        raise TypeError(
            "position must be a Position."
        )

    _validate_price(
        entry_price,
        "entry_price",
    )

    _validate_price(
        exit_price,
        "exit_price",
    )

    _validate_quantity(quantity)

    _validate_cost_rate(
        transaction_cost_rate
    )

    if entry_time is None:
        raise ValueError(
            "entry_time cannot be None."
        )

    if exit_time is None:
        raise ValueError(
            "exit_time cannot be None."
        )

    # --------------------------------------------------------
    # Gross P&L
    # --------------------------------------------------------

    if position == Position.LONG:
        gross_pnl = (
            exit_price - entry_price
        ) * quantity

    else:
        gross_pnl = (
            entry_price - exit_price
        ) * quantity

    # --------------------------------------------------------
    # Transaction costs
    #
    # Cost is applied to both entry and exit
    # notional values.
    # --------------------------------------------------------

    entry_value = (
        entry_price * quantity
    )

    exit_value = (
        exit_price * quantity
    )

    transaction_cost = (
        entry_value + exit_value
    ) * transaction_cost_rate

    net_pnl = (
        gross_pnl - transaction_cost
    )

    # --------------------------------------------------------
    # Return percentage
    #
    # Based on entry notional.
    # --------------------------------------------------------

    return_pct = (
        net_pnl / entry_value
    ) * 100

    return Trade(
        entry_time=entry_time,
        exit_time=exit_time,
        position=position,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        transaction_cost=transaction_cost,
        net_pnl=net_pnl,
        return_pct=return_pct,
    )
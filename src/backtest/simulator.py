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
    exit_reason: str = "SIGNAL"
    slippage: float = 0.0
    brokerage: float = 0.0
    statutory_fees: float = 0.0
    capital_before: float = 0.0
    capital_after: float = 0.0
    risk_amount: float = 0.0
    atr: float = 0.0
    stop_distance: float = 0.0
    risk_based_quantity: int = 0
    max_allowed_quantity: int = 0
    notional_value: float = 0.0
    effective_leverage: float = 0.0


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
    brokerage: float = 0.0,
    slippage_rate: float = 0.0,
    statutory_fee_rate: float = 0.0,
    exit_reason: str = "SIGNAL",
    capital_before: float = 0.0,
    capital_after: float = 0.0,
    risk_amount: float = 0.0,
    atr: float = 0.0,
    stop_distance: float = 0.0,
    risk_based_quantity: int = 0,
    max_allowed_quantity: int = 0,
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
        Generic cost rate applied to turnover.

    brokerage:
        Flat brokerage fee per trade.

    slippage_rate:
        Rate applied to turnover for slippage.

    statutory_fee_rate:
        Rate applied to turnover for statutory taxes/exchange fees.

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
    _validate_cost_rate(
        slippage_rate
    )
    _validate_cost_rate(
        statutory_fee_rate
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
    # Transaction costs (Turnover-based)
    # --------------------------------------------------------

    entry_value = (
        entry_price * quantity
    )

    exit_value = (
        exit_price * quantity
    )

    total_turnover = entry_value + exit_value

    slippage_cost = total_turnover * slippage_rate
    statutory_fee_cost = total_turnover * statutory_fee_rate
    brokerage_cost = float(brokerage)
    generic_cost = total_turnover * transaction_cost_rate

    transaction_cost = (
        brokerage_cost
        + slippage_cost
        + statutory_fee_cost
        + generic_cost
    )

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

    notional_value = entry_value
    effective_leverage = (
        notional_value / capital_before
        if capital_before > 0
        else 0.0
    )

    computed_capital_after = (
        capital_after
        if (capital_after != 0.0 and capital_after != capital_before)
        else (capital_before + net_pnl)
    )

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
        exit_reason=exit_reason,
        slippage=slippage_cost,
        brokerage=brokerage_cost,
        statutory_fees=statutory_fee_cost,
        capital_before=capital_before,
        capital_after=computed_capital_after,
        risk_amount=risk_amount,
        atr=atr,
        stop_distance=stop_distance,
        risk_based_quantity=risk_based_quantity,
        max_allowed_quantity=max_allowed_quantity,
        notional_value=notional_value,
        effective_leverage=effective_leverage,
    )
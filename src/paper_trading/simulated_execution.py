"""
SignalForge — Phase 28: Isolated Simulated Execution Engine
============================================================
File: src/paper_trading/simulated_execution.py

Capabilities:
- Isolated simulated execution engine for Equity Intraday paper trading.
- Supports Simulated Market, Limit, Stop-Loss, and Exit orders.
- Order lifecycle transitions: SUBMITTED -> PENDING_EXECUTION -> FILLED / REJECTED / CANCELLED.
- Causal execution timing: fills only at authentic bar open or current available quote,
  never using future same-candle high/low data (zero look-ahead bias).
- Deterministic slippage (default 1.0 bps) and half-spread (default 0.5 bps).
- Full canonical Indian statutory cost deduction using DISCOUNT_BROKER_REALISTIC_CONFIG.
- Rigorous server-side rejection for invalid quantities, invalid prices, duplicate requests,
  and insufficient margin.
- SIMULATION ONLY: Fully isolated with zero live broker execution paths.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    IntradayCostConfig,
    calculate_trade_transaction_costs,
)


class SimulatedOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    EXIT = "EXIT"


class SimulatedOrderStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PENDING_EXECUTION = "PENDING_EXECUTION"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


def _ensure_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class SimulatedOrder:
    """Represents a discrete simulated paper order with lifecycle audit."""

    order_id: str
    symbol: str
    side: str  # BUY or SELL
    order_type: str  # SimulatedOrderType
    quantity: int
    requested_price: float
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    client_request_id: Optional[str] = None
    timeframe: str = "15m"

    status: str = SimulatedOrderStatus.SUBMITTED.value
    rejection_reason: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None

    fill_price: Optional[float] = None
    slippage_cost: float = 0.0
    spread_cost: float = 0.0
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    gst: float = 0.0
    total_costs: float = 0.0
    gross_amount: float = 0.0
    net_amount: float = 0.0
    execution_notes: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            SimulatedOrderStatus.FILLED.value,
            SimulatedOrderStatus.REJECTED.value,
            SimulatedOrderStatus.CANCELLED.value,
        }

    @property
    def is_active(self) -> bool:
        return self.status in {
            SimulatedOrderStatus.SUBMITTED.value,
            SimulatedOrderStatus.PENDING_EXECUTION.value,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ["created_at", "updated_at", "filled_at"]:
            val = getattr(self, key, None)
            data[key] = val.isoformat() if isinstance(val, datetime) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SimulatedOrder:
        d = dict(data)
        for key in ["created_at", "updated_at", "filled_at"]:
            val = d.get(key)
            if isinstance(val, str) and val:
                d[key] = datetime.fromisoformat(val)
            elif not isinstance(val, datetime):
                d[key] = None
        return cls(**d)


class SimulatedExecutionEngine:
    """
    Deterministic simulated execution engine for equity intraday paper trading.
    Implements causal fill simulation, slippage, spread, and Indian market cost accounting.
    """

    def __init__(
        self,
        cost_config: Optional[IntradayCostConfig] = None,
        default_slippage_bps: float = 1.0,
        default_spread_bps: float = 0.5,
    ) -> None:
        self.cost_config: IntradayCostConfig = (
            cost_config or DISCOUNT_BROKER_REALISTIC_CONFIG
        )
        self.slippage_rate: float = default_slippage_bps / 10000.0
        self.spread_rate: float = default_spread_bps / 10000.0
        self._orders: Dict[str, SimulatedOrder] = {}

    def submit_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        requested_price: float,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        client_request_id: Optional[str] = None,
        timeframe: str = "15m",
        timestamp: Optional[datetime] = None,
    ) -> SimulatedOrder:
        """
        Validate and submit a new simulated order.
        Rejects invalid parameters or duplicate request IDs.
        """
        now = _ensure_utc(timestamp)

        # 1. Idempotency Check
        if client_request_id:
            clean_client_id = str(client_request_id).strip()
            for existing in self._orders.values():
                if existing.client_request_id == clean_client_id:
                    raise KeyError(
                        f"Duplicate request: client_request_id '{clean_client_id}' already exists as order {existing.order_id}"
                    )
        else:
            clean_client_id = None

        # 2. Symbol Validation
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            raise ValueError("symbol is required and cannot be empty")

        # 3. Side Validation
        norm_side = str(side or "").strip().upper()
        if norm_side not in {OrderSide.BUY.value, OrderSide.SELL.value, "LONG", "SHORT"}:
            raise ValueError(f"Invalid side '{side}'. Must be BUY or SELL")
        resolved_side = OrderSide.BUY.value if norm_side in {"BUY", "LONG"} else OrderSide.SELL.value

        # 4. Order Type Validation
        norm_type = str(order_type or "").strip().upper()
        if norm_type not in SimulatedOrderType.__members__:
            raise ValueError(
                f"Invalid order_type '{order_type}'. Supported: {[t.value for t in SimulatedOrderType]}"
            )

        # 5. Quantity Validation
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"quantity must be a positive integer, received {quantity}")

        # 6. Price Validation
        if (
            isinstance(requested_price, bool)
            or not isinstance(requested_price, (int, float))
            or math.isnan(requested_price)
            or math.isinf(requested_price)
            or requested_price <= 0
        ):
            raise ValueError(
                f"requested_price must be a positive finite number, received {requested_price}"
            )

        # 7. Bracket Geometry Check if supplied
        if stop_price is not None:
            if stop_price <= 0 or math.isnan(stop_price) or math.isinf(stop_price):
                raise ValueError(f"stop_price must be positive and finite, received {stop_price}")
            if resolved_side == OrderSide.BUY.value and stop_price >= requested_price:
                raise ValueError(
                    f"Invalid BUY stop: stop_price ({stop_price}) must be < requested_price ({requested_price})"
                )
            if resolved_side == OrderSide.SELL.value and stop_price <= requested_price:
                raise ValueError(
                    f"Invalid SELL stop: stop_price ({stop_price}) must be > requested_price ({requested_price})"
                )

        if target_price is not None:
            if target_price <= 0 or math.isnan(target_price) or math.isinf(target_price):
                raise ValueError(f"target_price must be positive and finite, received {target_price}")
            if resolved_side == OrderSide.BUY.value and target_price <= requested_price:
                raise ValueError(
                    f"Invalid BUY target: target_price ({target_price}) must be > requested_price ({requested_price})"
                )
            if resolved_side == OrderSide.SELL.value and target_price >= requested_price:
                raise ValueError(
                    f"Invalid SELL target: target_price ({target_price}) must be < requested_price ({requested_price})"
                )

        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        order = SimulatedOrder(
            order_id=order_id,
            symbol=clean_symbol,
            side=resolved_side,
            order_type=norm_type,
            quantity=int(quantity),
            requested_price=float(requested_price),
            stop_price=float(stop_price) if stop_price is not None else None,
            target_price=float(target_price) if target_price is not None else None,
            client_request_id=clean_client_id,
            timeframe=str(timeframe or "15m").strip().lower(),
            status=SimulatedOrderStatus.SUBMITTED.value,
            created_at=now,
            updated_at=now,
        )
        self._orders[order_id] = order
        return order

    def execute_fill(
        self,
        order_id: str,
        market_price: float,
        timestamp: Optional[datetime] = None,
        available_cash: Optional[float] = None,
    ) -> SimulatedOrder:
        """
        Execute a simulated fill for a submitted order using authentic market price.
        Applies causal slippage, spread penalty, and validates cash sufficiency.
        """
        order = self.get_order(order_id)
        if not order:
            raise KeyError(f"Order '{order_id}' not found")

        if order.status != SimulatedOrderStatus.SUBMITTED.value:
            raise ValueError(f"Cannot fill order {order_id} in state '{order.status}'")

        now = _ensure_utc(timestamp)
        if market_price <= 0 or math.isnan(market_price) or math.isinf(market_price):
            order.status = SimulatedOrderStatus.REJECTED.value
            order.rejection_reason = f"Invalid execution market price: {market_price}"
            order.updated_at = now
            return order

        # 1. Limit Order Price Check
        if order.order_type == SimulatedOrderType.LIMIT.value:
            if order.side == OrderSide.BUY.value and market_price > order.requested_price:
                # Price has moved above buy limit; remains pending
                order.status = SimulatedOrderStatus.PENDING_EXECUTION.value
                order.updated_at = now
                return order
            elif order.side == OrderSide.SELL.value and market_price < order.requested_price:
                # Price has moved below sell limit; remains pending
                order.status = SimulatedOrderStatus.PENDING_EXECUTION.value
                order.updated_at = now
                return order

        # 2. Stop Loss Order Trigger Check
        if order.order_type == SimulatedOrderType.STOP_LOSS.value:
            if order.side == OrderSide.SELL.value and market_price > order.requested_price:
                order.status = SimulatedOrderStatus.PENDING_EXECUTION.value
                order.updated_at = now
                return order
            elif order.side == OrderSide.BUY.value and market_price < order.requested_price:
                order.status = SimulatedOrderStatus.PENDING_EXECUTION.value
                order.updated_at = now
                return order

        # 3. Calculate Causal Execution Fill Price (adverse slippage + half spread)
        # For BUY: execution price is marked upward (adverse)
        # For SELL: execution price is marked downward (adverse)
        total_friction_rate = self.slippage_rate + self.spread_rate
        if order.side == OrderSide.BUY.value:
            fill_price = market_price * (1.0 + total_friction_rate)
        else:
            fill_price = market_price * (1.0 - total_friction_rate)

        gross_notional = fill_price * order.quantity
        slippage_cost = market_price * self.slippage_rate * order.quantity
        spread_cost = market_price * self.spread_rate * order.quantity

        # 4. Cash Sufficiency Check
        if available_cash is not None:
            if gross_notional > available_cash:
                order.status = SimulatedOrderStatus.REJECTED.value
                order.rejection_reason = (
                    f"Insufficient available cash: required ₹{gross_notional:.2f}, available ₹{available_cash:.2f}"
                )
                order.updated_at = now
                return order

        # 5. Calculate Transaction Costs for the leg
        # Brokerage, STT, Exchange, SEBI, Stamp Duty, GST
        # We calculate leg transaction costs using the canonical model
        turnover = gross_notional
        brok = (
            min(self.cost_config.brokerage_max_per_leg_inr, turnover * self.cost_config.brokerage_rate_pct)
            if self.cost_config.brokerage_rate_pct > 0.0
            else 0.0
        )
        stt = turnover * self.cost_config.stt_rate_sell_pct if order.side == OrderSide.SELL.value else 0.0
        exc = turnover * self.cost_config.exchange_charge_rate_pct
        sebi = turnover * self.cost_config.sebi_charge_rate_pct
        stamp = turnover * self.cost_config.stamp_duty_rate_buy_pct if order.side == OrderSide.BUY.value else 0.0
        taxable = brok + exc + sebi
        gst = taxable * self.cost_config.gst_rate_pct
        total_costs = brok + stt + exc + sebi + stamp + gst + slippage_cost + spread_cost

        # 6. Fill the Order
        order.status = SimulatedOrderStatus.FILLED.value
        order.fill_price = round(fill_price, 4)
        order.filled_at = now
        order.updated_at = now
        order.gross_amount = round(gross_notional, 2)
        order.slippage_cost = round(slippage_cost, 2)
        order.spread_cost = round(spread_cost, 2)
        order.brokerage = round(brok, 2)
        order.stt = round(stt, 2)
        order.exchange_charges = round(exc, 2)
        order.sebi_charges = round(sebi, 2)
        order.stamp_duty = round(stamp, 2)
        order.gst = round(gst, 2)
        order.total_costs = round(total_costs, 2)
        order.net_amount = (
            round(gross_notional + total_costs, 2)
            if order.side == OrderSide.BUY.value
            else round(gross_notional - total_costs, 2)
        )
        order.execution_notes = (
            f"Filled at {fill_price:.2f} (raw quote: {market_price:.2f}, friction: +{(total_friction_rate*10000):.1f}bps)"
        )
        return order

    def cancel_order(self, order_id: str, reason: str = "User cancelled") -> SimulatedOrder:
        """Cancel an unfulfilled simulated order."""
        order = self.get_order(order_id)
        if not order:
            raise KeyError(f"Order '{order_id}' not found")
        if order.is_terminal:
            raise ValueError(f"Cannot cancel order {order_id} in terminal state '{order.status}'")

        order.status = SimulatedOrderStatus.CANCELLED.value
        order.rejection_reason = reason
        order.updated_at = datetime.now(timezone.utc)
        return order

    def reject_order(self, order_id: str, reason: str) -> SimulatedOrder:
        """Explicitly reject a submitted order."""
        order = self.get_order(order_id)
        if not order:
            raise KeyError(f"Order '{order_id}' not found")
        order.status = SimulatedOrderStatus.REJECTED.value
        order.rejection_reason = reason
        order.updated_at = datetime.now(timezone.utc)
        return order

    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        return self._orders.get(order_id)

    def list_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SimulatedOrder]:
        results = list(self._orders.values())
        if symbol:
            clean_s = symbol.strip().upper()
            results = [o for o in results if o.symbol == clean_s]
        if status:
            clean_st = status.strip().upper()
            results = [o for o in results if o.status == clean_st]
        results.sort(key=lambda o: o.created_at, reverse=True)
        return results[:limit]

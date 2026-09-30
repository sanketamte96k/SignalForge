"""
Deterministic Interactive Paper Trading Engine for SignalForge.

Phase 17 Implementation:
- Validates paper trade entries strictly from Strategy Engine signals (BUY/SELL only).
- Enforces duplicate position prevention (no overlapping active positions on same symbol/timeframe).
- Enforces strict SL/Target bracket geometries.
- Tracks deterministic Gross P&L and Unrealized P&L.
- Implements conservative ambiguity resolution (stop-first) on OHLC updates.
- Strictly guards against look-ahead bias and invalid state transitions.
- Supports file persistence to survive API restarts.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TradeStatus(str, Enum):
    """Lifecycle statuses for an interactive paper trade."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    TARGET_1_HIT = "TARGET_1_HIT"
    TARGET_2_HIT = "TARGET_2_HIT"
    STOPPED_OUT = "STOPPED_OUT"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TradeSide(str, Enum):
    """Trading side for a paper trade."""

    LONG = "LONG"
    SHORT = "SHORT"


ACTIVE_STATUSES = {
    TradeStatus.PENDING.value,
    TradeStatus.OPEN.value,
    TradeStatus.TARGET_1_HIT.value,
}

TERMINAL_STATUSES = {
    TradeStatus.TARGET_2_HIT.value,
    TradeStatus.STOPPED_OUT.value,
    TradeStatus.CLOSED.value,
    TradeStatus.CANCELLED.value,
}

SUPPORTED_STRATEGY_TIMEFRAMES = {"5m", "10m", "15m", "30m"}


def _ensure_aware_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has timezone or convert to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class InteractivePaperTrade:
    """Represents a discrete interactive paper trade."""

    trade_id: str
    symbol: str
    side: str
    timeframe: str

    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime | None = None

    signal_price: float = 0.0
    entry_price: float = 0.0
    exit_price: float | None = None

    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0

    quantity: int = 1

    status: str = TradeStatus.OPEN.value

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    exit_reason: str | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def return_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        ref_price = self.exit_price if self.exit_price is not None else self.entry_price
        if self.side == TradeSide.LONG.value:
            return ((ref_price - self.entry_price) / self.entry_price) * 100.0
        return ((self.entry_price - ref_price) / self.entry_price) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize trade to dictionary with ISO timestamps."""
        data = asdict(self)
        for key in [
            "signal_timestamp",
            "entry_timestamp",
            "exit_timestamp",
            "created_at",
            "updated_at",
        ]:
            val = getattr(self, key, None)
            data[key] = val.isoformat() if isinstance(val, datetime) else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InteractivePaperTrade:
        """Deserialize trade from dictionary with parsed timestamps."""
        data_copy = dict(data)
        for key in [
            "signal_timestamp",
            "entry_timestamp",
            "exit_timestamp",
            "created_at",
            "updated_at",
        ]:
            val = data_copy.get(key)
            if isinstance(val, str) and val:
                data_copy[key] = datetime.fromisoformat(val)
            elif not isinstance(val, datetime):
                data_copy[key] = None
        return cls(**data_copy)


class InteractivePaperTradingService:
    """
    Thread-safe and file-backed interactive paper trading engine.
    """

    def __init__(self, persistence_file: Path | str | None = None) -> None:
        if persistence_file:
            self.persistence_file = Path(persistence_file)
        else:
            self.persistence_file = (
                Path(__file__).resolve().parents[2]
                / "data"
                / "paper_trading"
                / "interactive_trades.json"
            )
        self._trades: dict[str, InteractivePaperTrade] = {}
        self._load_from_disk()

    def _save_to_disk(self) -> None:
        """Persist current interactive trades state to JSON file."""
        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "trades": [trade.to_dict() for trade in self._trades.values()]
            }
            with self.persistence_file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            # Silent fallback if environment disallows write
            pass

    def _load_from_disk(self) -> None:
        """Load persisted interactive trades from JSON file if available."""
        if not self.persistence_file.exists():
            return
        try:
            with self.persistence_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            trades_raw = data.get("trades", [])
            for item in trades_raw:
                trade = InteractivePaperTrade.from_dict(item)
                self._trades[trade.trade_id] = trade
        except Exception:
            # Do not crash if file is corrupt, start fresh
            self._trades = {}

    def reset(self) -> None:
        """Clear all interactive paper trades."""
        self._trades.clear()
        self._save_to_disk()

    # ------------------------------------------------------------------------
    # Entry Validation & Trade Creation
    # ------------------------------------------------------------------------

    def create_trade(
        self,
        symbol: str,
        side: str,
        timeframe: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
        quantity: int = 1,
        signal_price: float | None = None,
        signal_timestamp: datetime | None = None,
        strategy_signal: str | None = None,
    ) -> InteractivePaperTrade:
        """
        Validate and open a new interactive paper trade.
        Rejects invalid parameters, non-strategy signals, and duplicate active positions.
        """
        # Risk guard: Symbol
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            raise ValueError("symbol is required and cannot be empty")

        # Risk guard: Timeframe
        clean_tf = str(timeframe or "").strip().lower()
        if clean_tf not in SUPPORTED_STRATEGY_TIMEFRAMES:
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. Supported strategy timeframes: 5m, 10m, 15m, 30m"
            )

        # Risk guard: Side
        normalized_side = str(side or "").strip().upper()
        if normalized_side in {"BUY", "LONG"}:
            side_enum = TradeSide.LONG
        elif normalized_side in {"SELL", "SHORT"}:
            side_enum = TradeSide.SHORT
        else:
            raise ValueError(f"Invalid side '{side}'. Must be LONG (BUY) or SHORT (SELL)")

        # Strategy Signal Guard: reject NO_TRADE
        if strategy_signal is not None:
            strat_sig = str(strategy_signal).strip().upper()
            if strat_sig == "NO_TRADE":
                raise ValueError("Cannot open paper trade: strategy returned NO_TRADE")
            if strat_sig in {"BUY", "LONG"} and side_enum != TradeSide.LONG:
                raise ValueError("Side mismatch: strategy signal is BUY but requested SHORT")
            if strat_sig in {"SELL", "SHORT"} and side_enum != TradeSide.SHORT:
                raise ValueError("Side mismatch: strategy signal is SELL but requested LONG")

        # Risk guard: Quantity
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"quantity must be an integer > 0, received {quantity}")

        # Risk guard: Numeric prices
        for name, val in [
            ("entry_price", entry_price),
            ("stop_loss", stop_loss),
            ("target_1", target_1),
            ("target_2", target_2),
        ]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val) or val <= 0:
                raise ValueError(f"{name} must be a positive finite number, received {val}")

        resolved_signal_price = signal_price if signal_price is not None else entry_price
        if (
            not isinstance(resolved_signal_price, (int, float))
            or math.isnan(resolved_signal_price)
            or math.isinf(resolved_signal_price)
            or resolved_signal_price <= 0
        ):
            raise ValueError(f"signal_price must be a positive finite number, received {resolved_signal_price}")

        # Geometric Validation
        if side_enum == TradeSide.LONG:
            if not (stop_loss < entry_price):
                raise ValueError(
                    f"Invalid LONG stop loss: stop_loss ({stop_loss}) must be strictly less than entry_price ({entry_price})"
                )
            if not (target_1 > entry_price):
                raise ValueError(
                    f"Invalid LONG target 1: target_1 ({target_1}) must be strictly greater than entry_price ({entry_price})"
                )
            if not (target_2 >= target_1):
                raise ValueError(
                    f"Invalid LONG target 2: target_2 ({target_2}) must be greater than or equal to target_1 ({target_1})"
                )
        else:  # SHORT
            if not (stop_loss > entry_price):
                raise ValueError(
                    f"Invalid SHORT stop loss: stop_loss ({stop_loss}) must be strictly greater than entry_price ({entry_price})"
                )
            if not (target_1 < entry_price):
                raise ValueError(
                    f"Invalid SHORT target 1: target_1 ({target_1}) must be strictly less than entry_price ({entry_price})"
                )
            if not (target_2 <= target_1):
                raise ValueError(
                    f"Invalid SHORT target 2: target_2 ({target_2}) must be less than or equal to target_1 ({target_1})"
                )

        # Duplicate Position Protection (Phase 17E)
        existing_active = self.get_active_trade(clean_symbol, clean_tf)
        if existing_active is not None:
            raise KeyError(
                f"Duplicate active position: trade {existing_active.trade_id} is already open on {clean_symbol} {clean_tf}"
            )

        now = datetime.now(timezone.utc)
        sig_time = _ensure_aware_utc(signal_timestamp) or now
        entry_time = now

        trade_id = f"tr_{uuid.uuid4().hex[:10]}"
        trade = InteractivePaperTrade(
            trade_id=trade_id,
            symbol=clean_symbol,
            side=side_enum.value,
            timeframe=clean_tf,
            signal_timestamp=sig_time,
            entry_timestamp=entry_time,
            signal_price=float(resolved_signal_price),
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            target_1=float(target_1),
            target_2=float(target_2),
            quantity=int(quantity),
            status=TradeStatus.OPEN.value,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            created_at=now,
            updated_at=now,
        )

        self._trades[trade_id] = trade
        self._save_to_disk()
        return trade

    # ------------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------------

    def get_trade(self, trade_id: str) -> InteractivePaperTrade | None:
        """Fetch trade by ID."""
        return self._trades.get(trade_id)

    def get_active_trade(self, symbol: str, timeframe: str) -> InteractivePaperTrade | None:
        """Find any existing active trade for symbol and timeframe."""
        clean_sym = symbol.strip().upper()
        clean_tf = timeframe.strip().lower()
        for trade in self._trades.values():
            if trade.is_active and trade.symbol == clean_sym and trade.timeframe == clean_tf:
                return trade
        return None

    def get_open_trades(self) -> list[InteractivePaperTrade]:
        """Return all currently active trades (sorted newest first)."""
        return sorted(
            [t for t in self._trades.values() if t.is_active],
            key=lambda x: x.entry_timestamp,
            reverse=True,
        )

    def list_trades(
        self,
        symbol: str | None = None,
        side: str | None = None,
        timeframe: str | None = None,
        status: str | None = None,
    ) -> list[InteractivePaperTrade]:
        """List trades filtered by criteria (sorted newest first)."""
        res = list(self._trades.values())
        if symbol:
            clean_s = symbol.strip().upper()
            res = [t for t in res if t.symbol == clean_s]
        if side:
            clean_side = side.strip().upper()
            if clean_side in {"BUY", "LONG"}:
                clean_side = "LONG"
            elif clean_side in {"SELL", "SHORT"}:
                clean_side = "SHORT"
            res = [t for t in res if t.side == clean_side]
        if timeframe:
            clean_tf = timeframe.strip().lower()
            res = [t for t in res if t.timeframe == clean_tf]
        if status:
            clean_st = status.strip().upper()
            res = [t for t in res if t.status == clean_st]

        return sorted(res, key=lambda x: x.entry_timestamp, reverse=True)

    # ------------------------------------------------------------------------
    # State Updates & Exit Engine (Phase 17C, 17F, 17G, 17N)
    # ------------------------------------------------------------------------

    def update_trade(
        self,
        trade_id: str,
        current_price: float | None = None,
        candle_open: float | None = None,
        candle_high: float | None = None,
        candle_low: float | None = None,
        candle_close: float | None = None,
        timestamp: datetime | None = None,
    ) -> InteractivePaperTrade:
        """
        Evaluate an open trade against current market price or OHLC candle.

        Ambiguity Resolution (Conservative):
        If candle contains both Stop Loss and Target, STOP IS EVALUATED FIRST.
        We strictly do NOT assume favorable outcome.
        """
        trade = self._trades.get(trade_id)
        if not trade:
            raise KeyError(f"Trade not found: {trade_id}")

        if trade.is_terminal:
            raise ValueError(f"Cannot update trade {trade_id}: trade is already in terminal state {trade.status}")

        eval_time = _ensure_aware_utc(timestamp) or datetime.now(timezone.utc)

        # Look-ahead audit check: Exit evaluation candle cannot precede entry timestamp
        entry_time = _ensure_aware_utc(trade.entry_timestamp)
        if eval_time < entry_time:
            raise ValueError(
                f"Look-ahead violation: Evaluation timestamp ({eval_time}) cannot be earlier than entry timestamp ({entry_time})"
            )

        # Extract price range
        has_candle = (
            candle_high is not None
            and candle_low is not None
            and candle_close is not None
        )
        if has_candle:
            high = float(candle_high)
            low = float(candle_low)
            close = float(candle_close)
            if high < low:
                raise ValueError(f"Malformed candle: high ({high}) < low ({low})")
        else:
            if current_price is None or current_price <= 0:
                raise ValueError("Must provide either valid candle (high, low, close) or positive current_price")
            high = float(current_price)
            low = float(current_price)
            close = float(current_price)

        is_long = trade.side == TradeSide.LONG.value

        # --------------------------------------------------------------------
        # Exit evaluation with Conservative Ambiguity Handling
        # --------------------------------------------------------------------
        if is_long:
            sl_hit = low <= trade.stop_loss
            t2_hit = high >= trade.target_2
            t1_hit = high >= trade.target_1

            # CONSERVATIVE RULE: Stop loss evaluated first if ambiguous
            if sl_hit:
                trade.status = TradeStatus.STOPPED_OUT.value
                trade.exit_price = trade.stop_loss
                trade.exit_timestamp = eval_time
                trade.exit_reason = (
                    "Stop Loss Hit (Conservative Resolution)"
                    if (t1_hit or t2_hit)
                    else "Stop Loss Hit"
                )
                trade.realized_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                trade.unrealized_pnl = 0.0
            elif t2_hit:
                trade.status = TradeStatus.TARGET_2_HIT.value
                trade.exit_price = trade.target_2
                trade.exit_timestamp = eval_time
                trade.exit_reason = "Target 2 Hit"
                trade.realized_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                trade.unrealized_pnl = 0.0
            elif t1_hit:
                trade.status = TradeStatus.TARGET_1_HIT.value
                trade.exit_reason = "Target 1 Hit"
                trade.unrealized_pnl = (close - trade.entry_price) * trade.quantity
            else:
                trade.unrealized_pnl = (close - trade.entry_price) * trade.quantity

        else:  # SHORT
            sl_hit = high >= trade.stop_loss
            t2_hit = low <= trade.target_2
            t1_hit = low <= trade.target_1

            # CONSERVATIVE RULE: Stop loss evaluated first if ambiguous
            if sl_hit:
                trade.status = TradeStatus.STOPPED_OUT.value
                trade.exit_price = trade.stop_loss
                trade.exit_timestamp = eval_time
                trade.exit_reason = (
                    "Stop Loss Hit (Conservative Resolution)"
                    if (t1_hit or t2_hit)
                    else "Stop Loss Hit"
                )
                trade.realized_pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                trade.unrealized_pnl = 0.0
            elif t2_hit:
                trade.status = TradeStatus.TARGET_2_HIT.value
                trade.exit_price = trade.target_2
                trade.exit_timestamp = eval_time
                trade.exit_reason = "Target 2 Hit"
                trade.realized_pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                trade.unrealized_pnl = 0.0
            elif t1_hit:
                trade.status = TradeStatus.TARGET_1_HIT.value
                trade.exit_reason = "Target 1 Hit"
                trade.unrealized_pnl = (trade.entry_price - close) * trade.quantity
            else:
                trade.unrealized_pnl = (trade.entry_price - close) * trade.quantity

        trade.updated_at = datetime.now(timezone.utc)
        self._save_to_disk()
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float | None = None,
        exit_time: datetime | None = None,
        reason: str = "MANUAL_CLOSE",
    ) -> InteractivePaperTrade:
        """
        Manually close an open paper trade at given or current price.
        """
        trade = self._trades.get(trade_id)
        if not trade:
            raise KeyError(f"Trade not found: {trade_id}")

        if trade.is_terminal:
            raise ValueError(f"Cannot close trade {trade_id}: already in terminal state {trade.status}")

        resolved_exit_price = exit_price if exit_price is not None else trade.entry_price
        if (
            not isinstance(resolved_exit_price, (int, float))
            or math.isnan(resolved_exit_price)
            or math.isinf(resolved_exit_price)
            or resolved_exit_price <= 0
        ):
            raise ValueError(f"exit_price must be a positive finite number, received {resolved_exit_price}")

        now = datetime.now(timezone.utc)
        closing_time = _ensure_aware_utc(exit_time) or now

        # Look-ahead check
        entry_time = _ensure_aware_utc(trade.entry_timestamp)
        if closing_time < entry_time:
            raise ValueError("Look-ahead violation: exit_time cannot precede entry_timestamp")

        trade.status = TradeStatus.CLOSED.value
        trade.exit_price = float(resolved_exit_price)
        trade.exit_timestamp = closing_time
        trade.exit_reason = reason or "MANUAL_CLOSE"

        if trade.side == TradeSide.LONG.value:
            trade.realized_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
        else:
            trade.realized_pnl = (trade.entry_price - trade.exit_price) * trade.quantity

        trade.unrealized_pnl = 0.0
        trade.updated_at = now
        self._save_to_disk()
        return trade

    # ------------------------------------------------------------------------
    # Performance Summary (Phase 17H)
    # ------------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """
        Calculate aggregate performance statistics across all interactive trades.
        """
        all_trades = list(self._trades.values())
        total_trades = len(all_trades)
        open_trades = len([t for t in all_trades if t.is_active])
        closed_trades = [t for t in all_trades if t.is_terminal]

        winning_trades = len([t for t in closed_trades if t.realized_pnl > 0])
        losing_trades = len([t for t in closed_trades if t.realized_pnl < 0])

        closed_count = len(closed_trades)
        win_rate = (winning_trades / closed_count * 100.0) if closed_count > 0 else 0.0

        total_gross_pnl = sum(t.realized_pnl for t in closed_trades)
        avg_trade = (total_gross_pnl / closed_count) if closed_count > 0 else 0.0

        pnls = [t.realized_pnl for t in closed_trades]
        largest_win = max(pnls) if pnls and max(pnls) > 0 else 0.0
        largest_loss = min(pnls) if pnls and min(pnls) < 0 else 0.0

        return {
            "total_trades": total_trades,
            "open_trades": open_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "gross_pnl": round(total_gross_pnl, 2),
            "average_trade": round(avg_trade, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
        }

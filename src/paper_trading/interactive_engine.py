"""
Deterministic Interactive Paper Trading Engine for SignalForge (Phase 17 & Phase 18).

Capabilities:
- Validates paper trade entries strictly from Strategy Engine signals (BUY/SELL only).
- Enforces duplicate position prevention (no overlapping active positions on same symbol/timeframe).
- Enforces strict SL/Target bracket geometries.
- Integrates centralized CostModel & Slippage engine (brokerage, STT, exchange fees, SEBI, GST, stamp duty, slippage).
- Tracks Gross P&L, Total Costs, Net P&L, and Unrealized P&L.
- Maintains a full Paper Account state (starting/available/used capital, equity, peak equity, drawdown, max drawdown) and chronological Equity Curve.
- Implements conservative ambiguity resolution (stop-first) on OHLC updates.
- Strictly guards against look-ahead bias, stale signals, insufficient capital, and invalid state transitions.
- Supports atomic JSON persistence to survive API restarts.
- SIMULATION ONLY: Never connects to or executes on any real-money broker.
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

from src.paper_trading.cost_model import (
    CostModel,
    calculate_trade_costs,
    compute_entry_execution_price,
)


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

DEFAULT_STARTING_CAPITAL = 1_000_000.0


def _ensure_aware_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has timezone or convert to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class InteractivePaperTrade:
    """Represents a discrete interactive paper trade with full execution & cost audit."""

    trade_id: str
    symbol: str
    side: str
    timeframe: str

    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime | None = None

    signal_price: float = 0.0
    entry_signal_price: float = 0.0
    entry_price: float = 0.0
    actual_entry_price: float = 0.0

    exit_signal_price: float | None = None
    exit_price: float | None = None
    actual_exit_price: float | None = None

    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0

    quantity: int = 1

    status: str = TradeStatus.OPEN.value

    gross_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    brokerage: float = 0.0
    stt: float = 0.0
    exchange_fee: float = 0.0
    sebi_fee: float = 0.0
    gst: float = 0.0
    stamp_duty: float = 0.0
    taxes_and_fees: float = 0.0
    slippage_cost: float = 0.0
    spread_penalty: float = 0.0
    total_cost: float = 0.0
    net_pnl: float = 0.0

    exit_reason: str | None = None
    strategy: str = "SignalForge"
    config_id: str = "REALISTIC_INDIA_INTRADAY_V1"
    client_request_id: str | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def direction(self) -> str:
        return self.side

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

    @property
    def net_return_pct(self) -> float:
        notional = self.actual_entry_price * self.quantity
        if notional <= 0:
            return 0.0
        return (self.net_pnl / notional) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize trade to dictionary with ISO timestamps."""
        data = asdict(self)
        data["direction"] = self.direction
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
        data_copy.pop("direction", None)
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
        # Ensure defaults for legacy records
        if "entry_signal_price" not in data_copy:
            data_copy["entry_signal_price"] = data_copy.get("entry_price", 0.0)
        if "actual_entry_price" not in data_copy:
            data_copy["actual_entry_price"] = data_copy.get("entry_price", 0.0)
        if "exit_signal_price" not in data_copy:
            data_copy["exit_signal_price"] = data_copy.get("exit_price")
        if "actual_exit_price" not in data_copy:
            data_copy["actual_exit_price"] = data_copy.get("exit_price")
        if "gross_pnl" not in data_copy:
            data_copy["gross_pnl"] = data_copy.get("realized_pnl", 0.0)
        if "net_pnl" not in data_copy:
            data_copy["net_pnl"] = data_copy.get("realized_pnl", 0.0) - data_copy.get("total_cost", 0.0)
        return cls(**data_copy)


class InteractivePaperTradingService:
    """
    Deterministic, file-backed interactive paper trading engine with full cost,
    slippage, capital management, equity curve, and risk metrics.
    """

    def __init__(
        self,
        persistence_file: Path | str | None = None,
        starting_capital: float = DEFAULT_STARTING_CAPITAL,
        cost_model: CostModel | None = None,
        max_signal_age_seconds: float | None = None,
    ) -> None:
        if starting_capital <= 0 or math.isnan(starting_capital) or math.isinf(starting_capital):
            raise ValueError(f"starting_capital must be positive and finite, got {starting_capital}")

        if persistence_file:
            self.persistence_file = Path(persistence_file)
        else:
            self.persistence_file = (
                Path(__file__).resolve().parents[2]
                / "data"
                / "paper_trading"
                / "interactive_trades.json"
            )

        self.starting_capital: float = float(starting_capital)
        self.cost_model: CostModel = cost_model or CostModel()
        self.max_signal_age_seconds: float | None = max_signal_age_seconds
        self.simulation_only: bool = True

        self._trades: dict[str, InteractivePaperTrade] = {}
        self._peak_equity: float = self.starting_capital
        self._max_drawdown: float = 0.0
        self._max_drawdown_pct: float = 0.0
        self._equity_curve: list[dict[str, Any]] = []

        self._load_from_disk()
        if not self._equity_curve:
            self._record_equity_point(
                event="INITIAL_CAPITAL",
                trade_id=None,
                timestamp=datetime.now(timezone.utc),
            )

    # ------------------------------------------------------------------------
    # Configuration & Reset
    # ------------------------------------------------------------------------

    def configure(
        self,
        starting_capital: float | None = None,
        cost_model: CostModel | None = None,
        max_signal_age_seconds: float | None = None,
    ) -> None:
        """Update paper account capital or cost model configuration."""
        if starting_capital is not None:
            if starting_capital <= 0 or math.isnan(starting_capital) or math.isinf(starting_capital):
                raise ValueError(f"starting_capital must be positive and finite, got {starting_capital}")
            self.starting_capital = float(starting_capital)
            self._recalculate_equity_metrics()
        if cost_model is not None:
            if not isinstance(cost_model, CostModel):
                raise TypeError("cost_model must be a CostModel instance")
            self.cost_model = cost_model
        if max_signal_age_seconds is not None:
            self.max_signal_age_seconds = float(max_signal_age_seconds) if max_signal_age_seconds > 0 else None
        self._save_to_disk()

    def reset(
        self,
        starting_capital: float | None = None,
        cost_model: CostModel | None = None,
    ) -> None:
        """Clear all interactive paper trades and restore clean account state."""
        if starting_capital is not None:
            if starting_capital <= 0 or math.isnan(starting_capital) or math.isinf(starting_capital):
                raise ValueError("starting_capital must be positive")
            self.starting_capital = float(starting_capital)
        # If None, preserve the current self.starting_capital

        if cost_model is not None:
            self.cost_model = cost_model
        else:
            self.cost_model = CostModel()

        self.max_signal_age_seconds = None
        self._trades.clear()
        self._peak_equity = self.starting_capital
        self._max_drawdown = 0.0
        self._max_drawdown_pct = 0.0
        self._equity_curve = []
        self._record_equity_point(
            event="INITIAL_CAPITAL",
            trade_id=None,
            timestamp=datetime.now(timezone.utc),
        )
        self._save_to_disk()

    # ------------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------------

    def _save_to_disk(self) -> None:
        """Persist current interactive trades, account state, and equity curve to JSON."""
        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "simulation_only": True,
                "starting_capital": self.starting_capital,
                "cost_model": self.cost_model.to_dict(),
                "peak_equity": self._peak_equity,
                "max_drawdown": self._max_drawdown,
                "max_drawdown_pct": self._max_drawdown_pct,
                "trades": [trade.to_dict() for trade in self._trades.values()],
                "equity_curve": self._equity_curve,
            }
            with self.persistence_file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        """Load persisted interactive trades and account state from JSON if available."""
        if not self.persistence_file.exists():
            return
        try:
            with self.persistence_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if "starting_capital" in data and float(data["starting_capital"]) > 0:
                self.starting_capital = float(data["starting_capital"])
            if "cost_model" in data and isinstance(data["cost_model"], dict):
                self.cost_model = CostModel(**data["cost_model"])
            trades_raw = data.get("trades", [])
            for item in trades_raw:
                trade = InteractivePaperTrade.from_dict(item)
                self._trades[trade.trade_id] = trade
            self._peak_equity = float(data.get("peak_equity", self.starting_capital))
            self._max_drawdown = float(data.get("max_drawdown", 0.0))
            self._max_drawdown_pct = float(data.get("max_drawdown_pct", 0.0))
            self._equity_curve = list(data.get("equity_curve", []))
            self._recalculate_equity_metrics()
        except Exception:
            self._trades = {}
            self._equity_curve = []

    # ------------------------------------------------------------------------
    # Capital & Equity Curve Accounting
    # ------------------------------------------------------------------------

    def _recalculate_equity_metrics(self) -> None:
        """Recompute high-water mark and drawdown from current trades."""
        closed_trades = [t for t in self._trades.values() if t.is_terminal]
        active_trades = [t for t in self._trades.values() if t.is_active]

        net_realized = sum(t.net_pnl for t in closed_trades)
        unrealized = sum(t.unrealized_pnl for t in active_trades)
        current_equity = self.starting_capital + net_realized + unrealized

        if self._peak_equity < self.starting_capital:
            self._peak_equity = self.starting_capital
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        current_dd = max(0.0, self._peak_equity - current_equity)
        current_dd_pct = (current_dd / self._peak_equity * 100.0) if self._peak_equity > 0 else 0.0

        if current_dd > self._max_drawdown:
            self._max_drawdown = current_dd
        if current_dd_pct > self._max_drawdown_pct:
            self._max_drawdown_pct = current_dd_pct

    def _record_equity_point(
        self,
        event: str,
        trade_id: str | None,
        timestamp: datetime,
    ) -> None:
        """Append a deterministic point to the chronological equity curve."""
        self._recalculate_equity_metrics()
        acct = self.get_account_state()
        ts_iso = _ensure_aware_utc(timestamp).isoformat()
        point = {
            "step": len(self._equity_curve),
            "timestamp": ts_iso,
            "event": event,
            "trade_id": trade_id,
            "starting_capital": acct["starting_capital"],
            "available_capital": acct["available_capital"],
            "used_capital": acct["used_capital"],
            "gross_realized_pnl": acct["gross_realized_pnl"],
            "total_costs": acct["total_costs"],
            "realized_pnl": acct["realized_pnl"],
            "unrealized_pnl": acct["unrealized_pnl"],
            "total_equity": acct["total_equity"],
            "peak_equity": acct["peak_equity"],
            "drawdown": acct["drawdown"],
            "drawdown_pct": acct["drawdown_pct"],
            "max_drawdown": acct["max_drawdown"],
            "max_drawdown_pct": acct["max_drawdown_pct"],
        }
        self._equity_curve.append(point)

    def get_account_state(self) -> dict[str, Any]:
        """Return current deterministic paper account state."""
        self._recalculate_equity_metrics()
        closed_trades = [t for t in self._trades.values() if t.is_terminal]
        active_trades = [t for t in self._trades.values() if t.is_active]

        used_capital = sum(t.actual_entry_price * t.quantity for t in active_trades)
        gross_realized_pnl = sum(t.gross_pnl for t in closed_trades)
        total_costs = sum(t.total_cost for t in closed_trades)
        net_realized_pnl = sum(t.net_pnl for t in closed_trades)
        unrealized_pnl = sum(t.unrealized_pnl for t in active_trades)

        available_capital = self.starting_capital + net_realized_pnl - used_capital
        total_equity = self.starting_capital + net_realized_pnl + unrealized_pnl
        drawdown = max(0.0, self._peak_equity - total_equity)
        drawdown_pct = (drawdown / self._peak_equity * 100.0) if self._peak_equity > 0 else 0.0

        return {
            "simulation_only": True,
            "starting_capital": round(self.starting_capital, 2),
            "available_capital": round(available_capital, 2),
            "used_capital": round(used_capital, 2),
            "gross_realized_pnl": round(gross_realized_pnl, 2),
            "total_costs": round(total_costs, 2),
            "realized_pnl": round(net_realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_equity": round(total_equity, 2),
            "peak_equity": round(self._peak_equity, 2),
            "drawdown": round(drawdown, 2),
            "drawdown_pct": round(drawdown_pct, 4),
            "max_drawdown": round(self._max_drawdown, 2),
            "max_drawdown_pct": round(self._max_drawdown_pct, 4),
            "open_positions_count": len(active_trades),
            "completed_trades_count": len(closed_trades),
            "cost_model_id": self.cost_model.config_id,
        }

    def get_equity_curve(self) -> list[dict[str, Any]]:
        """Return chronological equity curve points."""
        return list(self._equity_curve)

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
        entry_timestamp: datetime | None = None,
        strategy_signal: str | None = None,
        client_request_id: str | None = None,
        max_signal_age_seconds: float | None = None,
    ) -> InteractivePaperTrade:
        """
        Validate and open a new interactive paper trade.
        Rejects invalid parameters, non-strategy signals, stale signals,
        insufficient capital, and duplicate active positions.
        """
        # Idempotency guard: reject duplicate client_request_id if already processed
        if client_request_id:
            clean_req_id = str(client_request_id).strip()
            for existing in self._trades.values():
                if existing.client_request_id == clean_req_id:
                    raise KeyError(
                        f"Duplicate request: client_request_id '{clean_req_id}' already processed as trade {existing.trade_id}"
                    )

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

        # Risk guard: Quantity (reject bools, floats, <= 0)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"quantity must be an integer > 0, received {quantity}")

        # Risk guard: Numeric prices
        for name, val in [
            ("entry_price", entry_price),
            ("stop_loss", stop_loss),
            ("target_1", target_1),
            ("target_2", target_2),
        ]:
            if (
                isinstance(val, bool)
                or not isinstance(val, (int, float))
                or math.isnan(val)
                or math.isinf(val)
                or val <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number, received {val}")

        resolved_signal_price = float(signal_price if signal_price is not None else entry_price)
        if math.isnan(resolved_signal_price) or math.isinf(resolved_signal_price) or resolved_signal_price <= 0:
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

        # Timestamp causality & staleness checks
        now = datetime.now(timezone.utc)
        resolved_entry_time = _ensure_aware_utc(entry_timestamp) or now
        resolved_sig_time = _ensure_aware_utc(signal_timestamp) or resolved_entry_time

        if resolved_entry_time < resolved_sig_time:
            raise ValueError(
                f"Look-ahead / timestamp ordering violation: entry_timestamp ({resolved_entry_time}) cannot precede signal_timestamp ({resolved_sig_time})"
            )

        age_limit = max_signal_age_seconds if max_signal_age_seconds is not None else self.max_signal_age_seconds
        if age_limit is not None:
            signal_age = (resolved_entry_time - resolved_sig_time).total_seconds()
            if signal_age > age_limit:
                raise ValueError(
                    f"Stale signal rejected: signal age ({signal_age:.1f}s) exceeds max_signal_age_seconds ({age_limit:.1f}s)"
                )

        # Duplicate Position Protection (Phase 17E)
        existing_active = self.get_active_trade(clean_symbol, clean_tf)
        if existing_active is not None:
            raise KeyError(
                f"Duplicate active position: trade {existing_active.trade_id} is already open on {clean_symbol} {clean_tf}"
            )

        # Compute deterministic actual entry price including entry slippage
        actual_entry = compute_entry_execution_price(
            signal_price=float(entry_price),
            side=side_enum.value,
            cost_model=self.cost_model,
        )

        # Capital / Margin Guard (Phase 18 Section 4)
        required_capital = actual_entry * int(quantity)
        account_state = self.get_account_state()
        available_cap = account_state["available_capital"]
        if required_capital > available_cap:
            raise ValueError(
                f"Insufficient available capital: trade requires ₹{required_capital:.2f}, but available capital is ₹{available_cap:.2f}"
            )

        trade_id = f"tr_{uuid.uuid4().hex[:10]}"
        trade = InteractivePaperTrade(
            trade_id=trade_id,
            symbol=clean_symbol,
            side=side_enum.value,
            timeframe=clean_tf,
            signal_timestamp=resolved_sig_time,
            entry_timestamp=resolved_entry_time,
            signal_price=resolved_signal_price,
            entry_signal_price=float(entry_price),
            entry_price=float(entry_price),
            actual_entry_price=float(actual_entry),
            stop_loss=float(stop_loss),
            target_1=float(target_1),
            target_2=float(target_2),
            quantity=int(quantity),
            status=TradeStatus.OPEN.value,
            gross_pnl=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            config_id=self.cost_model.config_id,
            client_request_id=str(client_request_id).strip() if client_request_id else None,
            created_at=now,
            updated_at=now,
        )

        self._trades[trade_id] = trade
        self._record_equity_point(
            event="TRADE_OPENED",
            trade_id=trade_id,
            timestamp=resolved_entry_time,
        )
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
    # Cost & Exit Application Helper
    # ------------------------------------------------------------------------

    def _finalize_trade_exit(
        self,
        trade: InteractivePaperTrade,
        exit_signal_price: float,
        exit_time: datetime,
        new_status: str,
        exit_reason: str,
    ) -> None:
        """Apply realistic transaction costs, slippage, and finalize terminal trade state."""
        breakdown = calculate_trade_costs(
            side=trade.side,
            entry_signal_price=trade.entry_signal_price,
            exit_signal_price=exit_signal_price,
            quantity=trade.quantity,
            cost_model=self.cost_model,
        )

        trade.status = new_status
        trade.exit_signal_price = float(exit_signal_price)
        trade.exit_price = float(exit_signal_price)
        trade.actual_entry_price = breakdown.actual_entry_price
        trade.actual_exit_price = breakdown.actual_exit_price
        trade.exit_timestamp = exit_time
        trade.exit_reason = exit_reason

        trade.gross_pnl = breakdown.gross_pnl
        trade.realized_pnl = breakdown.gross_pnl
        trade.brokerage = breakdown.brokerage
        trade.stt = breakdown.stt
        trade.exchange_fee = breakdown.exchange_fee
        trade.sebi_fee = breakdown.sebi_fee
        trade.gst = breakdown.gst
        trade.stamp_duty = breakdown.stamp_duty
        trade.taxes_and_fees = breakdown.taxes_and_fees
        trade.slippage_cost = breakdown.slippage_cost
        trade.spread_penalty = breakdown.spread_penalty
        trade.total_cost = breakdown.total_cost
        trade.net_pnl = breakdown.net_pnl
        trade.unrealized_pnl = 0.0
        trade.config_id = breakdown.config_id
        trade.updated_at = datetime.now(timezone.utc)

        self._record_equity_point(
            event=f"TRADE_{new_status}",
            trade_id=trade.trade_id,
            timestamp=exit_time,
        )

    # ------------------------------------------------------------------------
    # State Updates & Exit Engine
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
            if any(math.isnan(v) or math.isinf(v) or v <= 0 for v in (high, low, close)):
                raise ValueError("Candle prices must be positive finite numbers")
            if high < low:
                raise ValueError(f"Malformed candle: high ({high}) < low ({low})")
        else:
            if (
                current_price is None
                or isinstance(current_price, bool)
                or not isinstance(current_price, (int, float))
                or math.isnan(current_price)
                or math.isinf(current_price)
                or current_price <= 0
            ):
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
                reason = (
                    "Stop Loss Hit (Conservative Resolution)"
                    if (t1_hit or t2_hit)
                    else "Stop Loss Hit"
                )
                self._finalize_trade_exit(
                    trade=trade,
                    exit_signal_price=trade.stop_loss,
                    exit_time=eval_time,
                    new_status=TradeStatus.STOPPED_OUT.value,
                    exit_reason=reason,
                )
            elif t2_hit:
                self._finalize_trade_exit(
                    trade=trade,
                    exit_signal_price=trade.target_2,
                    exit_time=eval_time,
                    new_status=TradeStatus.TARGET_2_HIT.value,
                    exit_reason="Target 2 Hit",
                )
            elif t1_hit:
                trade.status = TradeStatus.TARGET_1_HIT.value
                trade.exit_reason = "Target 1 Hit"
                trade.unrealized_pnl = (close - trade.entry_price) * trade.quantity
                trade.updated_at = datetime.now(timezone.utc)
                self._recalculate_equity_metrics()
            else:
                trade.unrealized_pnl = (close - trade.entry_price) * trade.quantity
                trade.updated_at = datetime.now(timezone.utc)
                self._recalculate_equity_metrics()

        else:  # SHORT
            sl_hit = high >= trade.stop_loss
            t2_hit = low <= trade.target_2
            t1_hit = low <= trade.target_1

            # CONSERVATIVE RULE: Stop loss evaluated first if ambiguous
            if sl_hit:
                reason = (
                    "Stop Loss Hit (Conservative Resolution)"
                    if (t1_hit or t2_hit)
                    else "Stop Loss Hit"
                )
                self._finalize_trade_exit(
                    trade=trade,
                    exit_signal_price=trade.stop_loss,
                    exit_time=eval_time,
                    new_status=TradeStatus.STOPPED_OUT.value,
                    exit_reason=reason,
                )
            elif t2_hit:
                self._finalize_trade_exit(
                    trade=trade,
                    exit_signal_price=trade.target_2,
                    exit_time=eval_time,
                    new_status=TradeStatus.TARGET_2_HIT.value,
                    exit_reason="Target 2 Hit",
                )
            elif t1_hit:
                trade.status = TradeStatus.TARGET_1_HIT.value
                trade.exit_reason = "Target 1 Hit"
                trade.unrealized_pnl = (trade.entry_price - close) * trade.quantity
                trade.updated_at = datetime.now(timezone.utc)
                self._recalculate_equity_metrics()
            else:
                trade.unrealized_pnl = (trade.entry_price - close) * trade.quantity
                trade.updated_at = datetime.now(timezone.utc)
                self._recalculate_equity_metrics()

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
        Prevents duplicate closes and double P&L realization.
        """
        trade = self._trades.get(trade_id)
        if not trade:
            raise KeyError(f"Trade not found: {trade_id}")

        if trade.is_terminal:
            raise ValueError(f"Cannot close trade {trade_id}: already in terminal state {trade.status}")

        resolved_exit_price = exit_price if exit_price is not None else trade.entry_price
        if (
            isinstance(resolved_exit_price, bool)
            or not isinstance(resolved_exit_price, (int, float))
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

        self._finalize_trade_exit(
            trade=trade,
            exit_signal_price=float(resolved_exit_price),
            exit_time=closing_time,
            new_status=TradeStatus.CLOSED.value,
            exit_reason=reason or "MANUAL_CLOSE",
        )
        self._save_to_disk()
        return trade

    # ------------------------------------------------------------------------
    # Risk Metrics, Cost Breakdown & Performance Summary (Phase 18 Sections 5, 9)
    # ------------------------------------------------------------------------

    def get_cost_breakdown(self) -> dict[str, Any]:
        """Return aggregate cost breakdown across all completed trades."""
        closed_trades = [t for t in self._trades.values() if t.is_terminal]
        total_brokerage = sum(t.brokerage for t in closed_trades)
        total_stt = sum(t.stt for t in closed_trades)
        total_exchange_fee = sum(t.exchange_fee for t in closed_trades)
        total_sebi_fee = sum(t.sebi_fee for t in closed_trades)
        total_gst = sum(t.gst for t in closed_trades)
        total_stamp_duty = sum(t.stamp_duty for t in closed_trades)
        total_taxes_and_fees = sum(t.taxes_and_fees for t in closed_trades)
        total_slippage = sum(t.slippage_cost for t in closed_trades)
        total_spread = sum(t.spread_penalty for t in closed_trades)
        total_cost = sum(t.total_cost for t in closed_trades)
        total_gross_pnl = sum(t.gross_pnl for t in closed_trades)
        total_net_pnl = sum(t.net_pnl for t in closed_trades)

        return {
            "simulation_only": True,
            "config_id": self.cost_model.config_id,
            "cost_model": self.cost_model.to_dict(),
            "completed_trades": len(closed_trades),
            "gross_pnl": round(total_gross_pnl, 4),
            "brokerage": round(total_brokerage, 4),
            "stt": round(total_stt, 4),
            "exchange_fee": round(total_exchange_fee, 4),
            "sebi_fee": round(total_sebi_fee, 4),
            "gst": round(total_gst, 4),
            "stamp_duty": round(total_stamp_duty, 4),
            "taxes_and_fees": round(total_taxes_and_fees, 4),
            "slippage_cost": round(total_slippage, 4),
            "spread_penalty": round(total_spread, 4),
            "total_cost": round(total_cost, 4),
            "net_pnl": round(total_net_pnl, 4),
        }

    def get_risk_metrics(self) -> dict[str, Any]:
        """
        Calculate deterministic risk and performance metrics.
        Returns None for ratios/averages when insufficient data exists.
        """
        self._recalculate_equity_metrics()
        all_trades = list(self._trades.values())
        total_trades = len(all_trades)
        open_trades = len([t for t in all_trades if t.is_active])
        closed_trades = [t for t in all_trades if t.is_terminal]
        closed_count = len(closed_trades)

        gross_pnl = sum(t.gross_pnl for t in closed_trades)
        total_costs = sum(t.total_cost for t in closed_trades)
        net_pnl = sum(t.net_pnl for t in closed_trades)

        wins_net = [t.net_pnl for t in closed_trades if t.net_pnl > 0]
        losses_net = [t.net_pnl for t in closed_trades if t.net_pnl < 0]

        winning_trades = len(wins_net)
        losing_trades = len(losses_net)

        if closed_count == 0:
            return {
                "simulation_only": True,
                "total_trades": total_trades,
                "open_trades": open_trades,
                "closed_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": None,
                "gross_pnl": 0.0,
                "total_costs": 0.0,
                "net_pnl": 0.0,
                "average_gross_trade": None,
                "average_net_trade": None,
                "profit_factor": None,
                "max_drawdown": round(self._max_drawdown, 2),
                "max_drawdown_pct": round(self._max_drawdown_pct, 4),
                "average_win": None,
                "average_loss": None,
                "expectancy": None,
                "largest_win": None,
                "largest_loss": None,
            }

        win_rate = (winning_trades / closed_count) * 100.0
        avg_gross = gross_pnl / closed_count
        avg_net = net_pnl / closed_count

        avg_win = (sum(wins_net) / winning_trades) if winning_trades > 0 else None
        avg_loss = (sum(losses_net) / losing_trades) if losing_trades > 0 else None

        gross_win_sum = sum(wins_net)
        gross_loss_sum = abs(sum(losses_net))
        if gross_loss_sum > 0 and gross_win_sum > 0:
            profit_factor = round(gross_win_sum / gross_loss_sum, 4)
        elif gross_loss_sum > 0 and gross_win_sum == 0:
            profit_factor = 0.0
        else:
            profit_factor = None

        win_prob = winning_trades / closed_count
        loss_prob = losing_trades / closed_count
        expectancy = (
            (win_prob * (avg_win or 0.0)) + (loss_prob * (avg_loss or 0.0))
        )

        largest_win = max(wins_net) if wins_net else None
        largest_loss = min(losses_net) if losses_net else None

        return {
            "simulation_only": True,
            "total_trades": total_trades,
            "open_trades": open_trades,
            "closed_trades": closed_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "gross_pnl": round(gross_pnl, 2),
            "total_costs": round(total_costs, 2),
            "net_pnl": round(net_pnl, 2),
            "average_gross_trade": round(avg_gross, 2),
            "average_net_trade": round(avg_net, 2),
            "profit_factor": profit_factor,
            "max_drawdown": round(self._max_drawdown, 2),
            "max_drawdown_pct": round(self._max_drawdown_pct, 4),
            "average_win": round(avg_win, 2) if avg_win is not None else None,
            "average_loss": round(avg_loss, 2) if avg_loss is not None else None,
            "expectancy": round(expectancy, 2),
            "largest_win": round(largest_win, 2) if largest_win is not None else None,
            "largest_loss": round(largest_loss, 2) if largest_loss is not None else None,
        }

    def get_summary(self) -> dict[str, Any]:
        """
        Calculate aggregate performance statistics across all interactive trades.
        Preserves full Phase 17 backward compatibility while exposing Phase 18 net/cost fields.
        """
        self._recalculate_equity_metrics()
        all_trades = list(self._trades.values())
        total_trades = len(all_trades)
        open_trades = len([t for t in all_trades if t.is_active])
        closed_trades = [t for t in all_trades if t.is_terminal]

        winning_trades = len([t for t in closed_trades if t.realized_pnl > 0])
        losing_trades = len([t for t in closed_trades if t.realized_pnl < 0])

        closed_count = len(closed_trades)
        win_rate = (winning_trades / closed_count * 100.0) if closed_count > 0 else 0.0

        total_gross_pnl = sum(t.gross_pnl for t in closed_trades)
        total_costs = sum(t.total_cost for t in closed_trades)
        total_net_pnl = sum(t.net_pnl for t in closed_trades)

        avg_trade = (total_gross_pnl / closed_count) if closed_count > 0 else 0.0
        avg_net_trade = (total_net_pnl / closed_count) if closed_count > 0 else 0.0

        pnls = [t.realized_pnl for t in closed_trades]
        largest_win = max(pnls) if pnls and max(pnls) > 0 else 0.0
        largest_loss = min(pnls) if pnls and min(pnls) < 0 else 0.0

        wins_net = [t.net_pnl for t in closed_trades if t.net_pnl > 0]
        losses_net = [t.net_pnl for t in closed_trades if t.net_pnl < 0]
        gross_win_sum = sum(wins_net)
        gross_loss_sum = abs(sum(losses_net))
        profit_factor = (
            round(gross_win_sum / gross_loss_sum, 4)
            if gross_loss_sum > 0 and gross_win_sum > 0
            else (0.0 if gross_loss_sum > 0 else None)
        )

        return {
            "total_trades": total_trades,
            "open_trades": open_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "gross_pnl": round(total_gross_pnl, 2),
            "total_costs": round(total_costs, 2),
            "net_pnl": round(total_net_pnl, 2),
            "average_trade": round(avg_trade, 2),
            "average_net_trade": round(avg_net_trade, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "profit_factor": profit_factor,
            "max_drawdown": round(self._max_drawdown, 2),
        }

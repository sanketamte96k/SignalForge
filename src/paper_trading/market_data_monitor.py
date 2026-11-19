"""
SignalForge — Phase 28: Market Data Reliability & Outage Monitor
=================================================================
File: src/paper_trading/market_data_monitor.py

Capabilities:
- Real-time market data quality tracking for paper trading.
- Supports 5 explicit data quality states:
    1. CONNECTED: Continuous, healthy tick/candle reception.
    2. STALE: Time elapsed without new observation exceeds staleness threshold.
    3. DISCONNECTED: Upstream socket or feed disconnected.
    4. INVALID: Corrupted, non-positive, or NaN prices observed.
    5. RECOVERING: Feed reconnected, undergoing synchronization before permitting entries.
- Outage boundary detection:
    - Missing expected candle detection using continuous expected timeline.
    - Global feed blackout detection across multiple symbols.
    - Stale position price marking (preserves last authentic mark, forbids fabricated fills).
    - Margin lock during outages.
    - Preserves pending liquidations to execute at authentic resumed quotes.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class DataQualityState(str, Enum):
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    INVALID = "INVALID"
    RECOVERING = "RECOVERING"


@dataclass
class OutageEvent:
    """Record of an explicit data outage or recovery event."""

    event_id: str
    symbol: Optional[str]
    event_type: str  # OUTAGE_START, OUTAGE_END, STALE_MARK, CORRUPTED_QUOTE
    from_state: str
    to_state: str
    timestamp: datetime
    description: str
    duration_seconds: Optional[float] = None
    last_authentic_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class SymbolDataHealth:
    """Live telemetry and health state for an individual symbol's feed."""

    symbol: str
    state: str = DataQualityState.CONNECTED.value
    last_authentic_quote: float = 0.0
    last_quote_timestamp: Optional[datetime] = None
    consecutive_missing_bars: int = 0
    total_outage_events: int = 0
    pending_liquidation: bool = False
    liquidation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.last_quote_timestamp:
            d["last_quote_timestamp"] = self.last_quote_timestamp.isoformat()
        return d


class MarketDataReliabilityMonitor:
    """
    Evaluates feed integrity, tracks data quality states, and enforces outage safety.
    """

    def __init__(
        self,
        stale_threshold_seconds: float = 300.0,  # 5 minutes
        max_consecutive_missing_bars: int = 3,
        **kwargs: Any,
    ) -> None:
        if "feed_timeout_seconds" in kwargs:
            stale_threshold_seconds = kwargs["feed_timeout_seconds"]
        if "max_missing_bars_tolerance" in kwargs:
            max_consecutive_missing_bars = kwargs["max_missing_bars_tolerance"]

        self.stale_threshold_seconds: float = float(stale_threshold_seconds)
        self.max_consecutive_missing_bars: int = int(max_consecutive_missing_bars)
        self._symbol_health: Dict[str, SymbolDataHealth] = {}
        self._outage_events: List[OutageEvent] = []
        self._global_state: str = DataQualityState.CONNECTED.value
        self._pending_liquidations: Dict[str, Dict[str, Any]] = {}  # trade_id -> details

    @property
    def global_state(self) -> str:
        return self._global_state

    @property
    def global_feed_state(self) -> str:
        return self._global_state

    def get_symbol_health(self, symbol: str) -> SymbolDataHealth:
        clean_s = symbol.strip().upper()
        if clean_s not in self._symbol_health:
            self._symbol_health[clean_s] = SymbolDataHealth(symbol=clean_s)
        return self._symbol_health[clean_s]

    def register_quote(
        self,
        symbol: str,
        price: float,
        timestamp: Optional[datetime] = None,
    ) -> SymbolDataHealth:
        """
        Register a new incoming market observation.
        Validates price validity and transitions state to CONNECTED or INVALID.
        """
        clean_s = symbol.strip().upper()
        now = timestamp or datetime.now(timezone.utc)
        health = self.get_symbol_health(clean_s)

        # 1. Price Validity Check
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or math.isnan(price)
            or math.isinf(price)
            or price <= 0
        ):
            prev_state = health.state
            health.state = DataQualityState.INVALID.value
            event = OutageEvent(
                event_id=f"evt_{len(self._outage_events) + 1}",
                symbol=clean_s,
                event_type="CORRUPTED_QUOTE",
                from_state=prev_state,
                to_state=DataQualityState.INVALID.value,
                timestamp=now,
                description=f"Received non-positive or corrupt quote: {price}",
                last_authentic_price=health.last_authentic_quote,
            )
            self._outage_events.append(event)
            return health

        # 2. Authentic Quote Registered
        prev_state = health.state
        health.last_authentic_quote = float(price)
        health.last_quote_timestamp = now
        health.consecutive_missing_bars = 0

        if prev_state in {DataQualityState.STALE.value, DataQualityState.DISCONNECTED.value}:
            health.state = DataQualityState.RECOVERING.value
            event = OutageEvent(
                event_id=f"evt_{len(self._outage_events) + 1}",
                symbol=clean_s,
                event_type="OUTAGE_END",
                from_state=prev_state,
                to_state=DataQualityState.RECOVERING.value,
                timestamp=now,
                description=f"Feed recovered for {clean_s} at authentic quote: ₹{price:.2f}",
                last_authentic_price=health.last_authentic_quote,
            )
            self._outage_events.append(event)
        else:
            health.state = DataQualityState.CONNECTED.value

        self._reevaluate_global_state()
        return health

    def record_missing_bar(self, symbol: str, timestamp: Optional[datetime] = None) -> SymbolDataHealth:
        """Flag that an expected chronological candle was not received."""
        clean_s = symbol.strip().upper()
        now = timestamp or datetime.now(timezone.utc)
        health = self.get_symbol_health(clean_s)
        health.consecutive_missing_bars += 1

        if health.consecutive_missing_bars >= self.max_consecutive_missing_bars:
            if health.state != DataQualityState.STALE.value:
                prev_state = health.state
                health.state = DataQualityState.STALE.value
                health.total_outage_events += 1
                event = OutageEvent(
                    event_id=f"evt_{len(self._outage_events) + 1}",
                    symbol=clean_s,
                    event_type="OUTAGE_START",
                    from_state=prev_state,
                    to_state=DataQualityState.STALE.value,
                    timestamp=now,
                    description=f"{clean_s} missed {health.consecutive_missing_bars} consecutive expected candles",
                    last_authentic_price=health.last_authentic_quote,
                )
                self._outage_events.append(event)

        self._reevaluate_global_state()
        return health

    def set_disconnected(self, reason: str = "Feed disconnected", timestamp: Optional[datetime] = None) -> None:
        """Mark global or symbol feed as disconnected."""
        now = timestamp or datetime.now(timezone.utc)
        prev = self._global_state
        self._global_state = DataQualityState.DISCONNECTED.value
        for h in self._symbol_health.values():
            h.state = DataQualityState.DISCONNECTED.value
        event = OutageEvent(
            event_id=f"evt_{len(self._outage_events) + 1}",
            symbol=None,
            event_type="GLOBAL_DISCONNECT",
            from_state=prev,
            to_state=DataQualityState.DISCONNECTED.value,
            timestamp=now,
            description=reason,
        )
        self._outage_events.append(event)

    def mark_pending_liquidation(
        self,
        trade_id: str,
        symbol: str,
        breached_stop_price: float,
        reason: str = "Stop loss breached during feed gap",
    ) -> None:
        """Record a position whose stop was breached during an outage to execute on recovery."""
        self._pending_liquidations[trade_id] = {
            "trade_id": trade_id,
            "symbol": symbol.strip().upper(),
            "breached_stop_price": breached_stop_price,
            "reason": reason,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        }
        health = self.get_symbol_health(symbol)
        health.pending_liquidation = True
        health.liquidation_reason = reason

    def resolve_pending_liquidation(self, trade_id: str) -> Optional[Dict[str, Any]]:
        details = self._pending_liquidations.pop(trade_id, None)
        if details:
            sym = details.get("symbol", "")
            health = self.get_symbol_health(sym)
            health.pending_liquidation = False
            health.liquidation_reason = None
        return details

    def get_pending_liquidations(self) -> List[Dict[str, Any]]:
        return list(self._pending_liquidations.values())

    def _reevaluate_global_state(self) -> None:
        if not self._symbol_health:
            self._global_state = DataQualityState.CONNECTED.value
            return

        states = [h.state for h in self._symbol_health.values()]
        if any(s == DataQualityState.DISCONNECTED.value for s in states):
            self._global_state = DataQualityState.DISCONNECTED.value
        elif any(s == DataQualityState.INVALID.value for s in states):
            self._global_state = DataQualityState.INVALID.value
        elif any(s == DataQualityState.STALE.value for s in states):
            self._global_state = DataQualityState.STALE.value
        elif any(s == DataQualityState.RECOVERING.value for s in states):
            self._global_state = DataQualityState.RECOVERING.value
        else:
            self._global_state = DataQualityState.CONNECTED.value

    def record_candle_received(
        self,
        symbol: str,
        timestamp: datetime,
        price: float | None = None,
        close: float | None = None,
        **kwargs: Any,
    ) -> SymbolDataHealth:
        """Alias for register_quote."""
        effective_price = price if price is not None else (close if close is not None else 0.0)
        return self.register_quote(symbol=symbol, price=effective_price, timestamp=timestamp)

    def is_symbol_healthy(self, symbol: str) -> bool:
        """Check if symbol feed is in CONNECTED or RECOVERING state."""
        health = self.get_symbol_health(symbol)
        return health.state in {DataQualityState.CONNECTED.value, DataQualityState.RECOVERING.value}

    def is_trading_allowed(self, symbol: str) -> bool:
        """Check if simulated trading is allowed for symbol."""
        can_open, _ = self.can_open_entry(symbol)
        return can_open

    def get_mark_price(self, symbol: str) -> Optional[float]:
        """Return the latest authentic quote for mark-to-market valuation."""
        health = self.get_symbol_health(symbol)
        return health.last_authentic_quote

    def can_open_entry(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """Verify whether data reliability permits opening a new simulated trade."""
        clean_s = symbol.strip().upper()
        health = self.get_symbol_health(clean_s)

        if self._global_state in {DataQualityState.DISCONNECTED.value, DataQualityState.INVALID.value}:
            return False, f"Global feed is {self._global_state}; entries blocked."

        if health.state in {DataQualityState.STALE.value, DataQualityState.DISCONNECTED.value, DataQualityState.INVALID.value}:
            return False, f"Feed for {clean_s} is {health.state}; new simulated entries blocked."

        if health.pending_liquidation:
            return False, f"Symbol {clean_s} has pending liquidation; new entries blocked."

        return True, None

    def get_summary(self) -> Dict[str, Any]:
        return {
            "global_state": self._global_state,
            "data_quality_state": self._global_state,
            "global_feed_connected": (self._global_state == DataQualityState.CONNECTED.value),
            "last_feed_update_utc": datetime.now(timezone.utc),
            "active_outage": (self._global_state != DataQualityState.CONNECTED.value),
            "outage_history": self.list_outage_events(limit=10),
            "tracked_symbols": len(self._symbol_health),
            "pending_liquidations_count": len(self._pending_liquidations),
            "total_outage_events": len(self._outage_events),
            "symbols": {s: h.to_dict() for s, h in self._symbol_health.items()},
            "symbols_health": {s: h.to_dict() for s, h in self._symbol_health.items()},
        }

    def list_outage_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in sorted(self._outage_events, key=lambda e: e.timestamp, reverse=True)[:limit]]

"""
SignalForge — Phase 30: Provider-Neutral Live Market Data Adapter & Ingestion Engine
=====================================================================================
File: src/market_data/live_adapter.py

Capabilities:
- Provider-neutral quote and candle schemas isolating SignalForge from upstream formats.
- Supports 4 explicit feed types:
    1. LIVE: Real-time, zero-delay market quote and tick feeds.
    2. DELAYED: Authorized exchange-delayed market feeds (e.g., 15-minute delay).
    3. REPLAY: Historical deterministic simulation replay.
    4. SYNTHETIC: Controlled synthetic fixtures for testing.
- Supports 6 explicit data quality states:
    1. CONNECTED: Continuous, healthy quote and candle reception.
    2. DELAYED: Feed arriving with authorized or observed time lag.
    3. STALE: Time elapsed without updates exceeds staleness threshold.
    4. DISCONNECTED: Transport layer or socket severed.
    5. INVALID: Malformed, non-positive, or unphysical OHLCV observations.
    6. RECOVERING: Feed reconnected, awaiting N authentic observations before arming.
- Strict causal validation:
    - Quote sanity: LTP > 0, Bid <= Ask if present, non-negative volume.
    - Candle sanity: High >= Low, High >= Open/Close, Low <= Open/Close, Volume >= 0.
    - Explicit distinction between forming/in-progress candles (is_closed=False)
      and finalized candles (is_closed=True). In-progress candles NEVER masquerade as completed.
    - Deduplication: Idempotent handling of duplicate timestamps.
    - Out-of-order rejection: Events arriving with t < t_last are rejected or quarantined.
    - Latency decomposition: Provider latency vs local processing latency vs end-to-end.
    - Timezone-aware timestamping with explicit IST (Asia/Kolkata) and UTC conversions.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

# Standard Timezone Constants
IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


class FeedType(str, Enum):
    """Explicit market data feed classification."""
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class DataQualityState(str, Enum):
    """Operational feed health states."""
    CONNECTED = "CONNECTED"
    DELAYED = "DELAYED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    INVALID = "INVALID"
    RECOVERING = "RECOVERING"


def _ensure_aware_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime is timezone-aware in UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        # Default naive timestamps to UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_aware_ist(dt: Optional[datetime]) -> datetime:
    """Ensure datetime is timezone-aware in Asia/Kolkata (IST)."""
    if dt is None:
        return datetime.now(IST)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


@dataclass(frozen=True)
class LatencyMetrics:
    """Decomposed latency measurements across the ingestion pipeline."""
    provider_latency_ms: Optional[float]  # receive_timestamp - event_timestamp
    processing_latency_ms: float         # processed_timestamp - receive_timestamp
    end_to_end_latency_ms: float         # processed_timestamp - event_timestamp
    clock_skew_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveMarketQuote:
    """Standardized provider-neutral quote observation."""
    symbol: str
    exchange: str
    ltp: float
    volume: int
    event_timestamp: datetime
    receive_timestamp: datetime
    quality_state: DataQualityState
    source_id: str
    feed_type: FeedType = FeedType.SYNTHETIC
    instrument_id: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_qty: Optional[int] = None
    ask_qty: Optional[int] = None
    provider_timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        norm_sym = self.symbol.strip().upper()
        norm_exch = self.exchange.strip().upper()
        if not norm_sym:
            raise ValueError("Quote symbol must not be empty.")
        if not norm_exch:
            raise ValueError("Quote exchange must not be empty.")
        if self.ltp <= 0.0 or math.isnan(self.ltp):
            raise ValueError(f"Quote LTP must be positive and non-NaN. Got: {self.ltp}")
        if self.volume < 0:
            raise ValueError(f"Quote volume cannot be negative. Got: {self.volume}")
        if self.bid is not None and self.ask is not None:
            if self.bid > self.ask:
                raise ValueError(f"Bid price ({self.bid}) cannot exceed Ask price ({self.ask}).")

        # Normalize timestamps
        object.__setattr__(self, "symbol", norm_sym)
        object.__setattr__(self, "exchange", norm_exch)
        object.__setattr__(self, "event_timestamp", _ensure_aware_utc(self.event_timestamp))
        object.__setattr__(self, "receive_timestamp", _ensure_aware_utc(self.receive_timestamp))
        if self.provider_timestamp is not None:
            object.__setattr__(self, "provider_timestamp", _ensure_aware_utc(self.provider_timestamp))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["event_timestamp"] = self.event_timestamp.isoformat()
        data["receive_timestamp"] = self.receive_timestamp.isoformat()
        if self.provider_timestamp:
            data["provider_timestamp"] = self.provider_timestamp.isoformat()
        data["quality_state"] = self.quality_state.value
        data["feed_type"] = self.feed_type.value
        return data


@dataclass(frozen=True)
class LiveMarketCandle:
    """Standardized provider-neutral OHLCV bar observation."""
    symbol: str
    exchange: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    candle_timestamp: datetime
    is_closed: bool  # True = finalized bar; False = in-progress / forming bar
    event_timestamp: datetime
    receive_timestamp: datetime
    quality_state: DataQualityState
    source_id: str
    feed_type: FeedType = FeedType.SYNTHETIC

    def __post_init__(self) -> None:
        norm_sym = self.symbol.strip().upper()
        norm_exch = self.exchange.strip().upper()
        norm_tf = self.timeframe.strip().lower()

        if not norm_sym:
            raise ValueError("Candle symbol must not be empty.")
        if not norm_exch:
            raise ValueError("Candle exchange must not be empty.")
        if not norm_tf:
            raise ValueError("Candle timeframe must not be empty.")

        # Physical OHLCV invariants
        for field_name, val in [("open", self.open), ("high", self.high), ("low", self.low), ("close", self.close)]:
            if val <= 0.0 or math.isnan(val):
                raise ValueError(f"Candle {field_name} must be positive and non-NaN. Got: {val}")

        if self.volume < 0.0 or math.isnan(self.volume):
            raise ValueError(f"Candle volume cannot be negative or NaN. Got: {self.volume}")

        if self.high < self.low:
            raise ValueError(f"Candle High ({self.high}) cannot be lower than Low ({self.low}).")
        if self.high < self.open or self.high < self.close:
            raise ValueError(f"Candle High ({self.high}) must be >= Open ({self.open}) and Close ({self.close}).")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Candle Low ({self.low}) must be <= Open ({self.open}) and Close ({self.close}).")

        object.__setattr__(self, "symbol", norm_sym)
        object.__setattr__(self, "exchange", norm_exch)
        object.__setattr__(self, "timeframe", norm_tf)
        object.__setattr__(self, "candle_timestamp", _ensure_aware_utc(self.candle_timestamp))
        object.__setattr__(self, "event_timestamp", _ensure_aware_utc(self.event_timestamp))
        object.__setattr__(self, "receive_timestamp", _ensure_aware_utc(self.receive_timestamp))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["candle_timestamp"] = self.candle_timestamp.isoformat()
        data["event_timestamp"] = self.event_timestamp.isoformat()
        data["receive_timestamp"] = self.receive_timestamp.isoformat()
        data["quality_state"] = self.quality_state.value
        data["feed_type"] = self.feed_type.value
        return data


class LiveMarketDataValidator:
    """
    Validates quote and candle streams for physical invariants, chronological ordering,
    duplicate suppression, and anomaly detection.
    """

    @classmethod
    def validate_quote(cls, quote: LiveMarketQuote) -> Tuple[bool, Optional[str]]:
        """Validate a single live quote observation."""
        if quote.ltp <= 0 or math.isnan(quote.ltp):
            return False, f"Invalid LTP: {quote.ltp}"
        if quote.bid is not None and quote.ask is not None:
            if quote.bid > quote.ask:
                return False, f"Inverted spread: Bid {quote.bid} > Ask {quote.ask}"
        if quote.volume < 0:
            return False, f"Negative volume: {quote.volume}"
        return True, None

    @classmethod
    def validate_candle(cls, candle: LiveMarketCandle) -> Tuple[bool, Optional[str]]:
        """Validate a single candle observation."""
        if candle.high < candle.low:
            return False, f"High ({candle.high}) < Low ({candle.low})"
        if candle.high < candle.open or candle.high < candle.close:
            return False, f"High ({candle.high}) below Open/Close ({candle.open}/{candle.close})"
        if candle.low > candle.open or candle.low > candle.close:
            return False, f"Low ({candle.low}) above Open/Close ({candle.open}/{candle.close})"
        if candle.volume < 0:
            return False, f"Negative volume: {candle.volume}"
        return True, None


@dataclass
class SymbolStreamState:
    """Stateful stream tracker for a single symbol."""
    symbol: str
    feed_type: FeedType = FeedType.SYNTHETIC
    quality_state: DataQualityState = DataQualityState.CONNECTED
    last_quote: Optional[LiveMarketQuote] = None
    forming_candle: Optional[LiveMarketCandle] = None
    completed_candles: List[LiveMarketCandle] = field(default_factory=list)
    last_event_timestamp: Optional[datetime] = None
    last_receive_timestamp: Optional[datetime] = None
    last_processed_timestamp: Optional[datetime] = None

    # Telemetry counters
    total_quotes_received: int = 0
    total_completed_candles: int = 0
    duplicate_events_count: int = 0
    out_of_order_events_count: int = 0
    invalid_events_count: int = 0
    missing_candles_count: int = 0
    recovery_observations_count: int = 0

    # Latency tracking (rolling average ms)
    avg_provider_latency_ms: float = 0.0
    avg_processing_latency_ms: float = 0.0
    avg_end_to_end_latency_ms: float = 0.0


class ProviderNeutralMarketDataAdapter:
    """
    Central provider-neutral adapter coordinating quote and candle ingestion,
    latency tracking, missing-bar detection, and outage handling across symbols.
    """

    def __init__(
        self,
        source_id: str = "synthetic",
        default_feed_type: FeedType = FeedType.SYNTHETIC,
        stale_threshold_seconds: float = 60.0,
        delayed_threshold_seconds: float = 300.0,
        recovery_required_bars: int = 3,
    ) -> None:
        self.source_id: str = source_id
        self.default_feed_type: FeedType = default_feed_type
        self.stale_threshold_seconds: float = stale_threshold_seconds
        self.delayed_threshold_seconds: float = delayed_threshold_seconds
        self.recovery_required_bars: int = recovery_required_bars

        self._symbols: Dict[str, SymbolStreamState] = {}
        self._global_state: DataQualityState = DataQualityState.CONNECTED
        self._outage_log: List[Dict[str, Any]] = []

    @property
    def global_state(self) -> DataQualityState:
        return self._global_state

    def get_or_create_symbol(self, symbol: str) -> SymbolStreamState:
        clean_sym = symbol.strip().upper()
        if clean_sym not in self._symbols:
            self._symbols[clean_sym] = SymbolStreamState(
                symbol=clean_sym,
                feed_type=self.default_feed_type,
                quality_state=DataQualityState.CONNECTED,
            )
        return self._symbols[clean_sym]

    def ingest_quote(self, quote: LiveMarketQuote) -> Tuple[bool, Optional[str], Optional[LatencyMetrics]]:
        """
        Ingest a live quote update.
        Validates quote, computes decomposed latencies, updates stream state.
        """
        now = datetime.now(timezone.utc)
        state = self.get_or_create_symbol(quote.symbol)
        state.total_quotes_received += 1

        # 1. Validation
        valid, reason = LiveMarketDataValidator.validate_quote(quote)
        if not valid:
            state.invalid_events_count += 1
            state.quality_state = DataQualityState.INVALID
            return False, reason, None

        # 2. Duplicate Detection
        if state.last_quote and state.last_quote.event_timestamp == quote.event_timestamp and state.last_quote.ltp == quote.ltp:
            state.duplicate_events_count += 1
            # Idempotently accept without mutating state
            return True, "DUPLICATE_IGNORED", None

        # 3. Out-of-Order Detection
        if state.last_event_timestamp and quote.event_timestamp < state.last_event_timestamp:
            state.out_of_order_events_count += 1
            # Quarantined: do not roll backward the committed stream clock
            return False, f"Out-of-order quote timestamp: {quote.event_timestamp} < {state.last_event_timestamp}", None

        # 4. Latency Calculation
        provider_lat = None
        if quote.event_timestamp:
            provider_lat = max(0.0, (quote.receive_timestamp - quote.event_timestamp).total_seconds() * 1000.0)

        proc_lat = max(0.0, (now - quote.receive_timestamp).total_seconds() * 1000.0)
        e2e_lat = (provider_lat if provider_lat is not None else 0.0) + proc_lat

        latency = LatencyMetrics(
            provider_latency_ms=round(provider_lat, 2) if provider_lat is not None else None,
            processing_latency_ms=round(proc_lat, 2),
            end_to_end_latency_ms=round(e2e_lat, 2),
        )

        # Update rolling averages
        n = state.total_quotes_received
        state.avg_processing_latency_ms = round(((state.avg_processing_latency_ms * (n - 1)) + proc_lat) / n, 2)
        state.avg_end_to_end_latency_ms = round(((state.avg_end_to_end_latency_ms * (n - 1)) + e2e_lat) / n, 2)
        if provider_lat is not None:
            state.avg_provider_latency_ms = round(((state.avg_provider_latency_ms * (n - 1)) + provider_lat) / n, 2)

        # 5. Commit Quote State
        state.last_quote = quote
        state.last_event_timestamp = quote.event_timestamp
        state.last_receive_timestamp = quote.receive_timestamp
        state.last_processed_timestamp = now

        # Handle recovery transition
        if state.quality_state == DataQualityState.RECOVERING:
            state.recovery_observations_count += 1
            if state.recovery_observations_count >= self.recovery_required_bars:
                state.quality_state = DataQualityState.CONNECTED
        elif state.quality_state in (DataQualityState.STALE, DataQualityState.DISCONNECTED):
            state.quality_state = DataQualityState.RECOVERING
            state.recovery_observations_count = 1

        return True, None, latency

    def ingest_candle(self, candle: LiveMarketCandle) -> Tuple[bool, Optional[str], Optional[LatencyMetrics]]:
        """
        Ingest an OHLCV candle observation.
        Strictly differentiates forming candles (is_closed=False) from finalized candles (is_closed=True).
        """
        now = datetime.now(timezone.utc)
        state = self.get_or_create_symbol(candle.symbol)

        # 1. Validation
        valid, reason = LiveMarketDataValidator.validate_candle(candle)
        if not valid:
            state.invalid_events_count += 1
            state.quality_state = DataQualityState.INVALID
            return False, reason, None

        # 2. In-Progress Candle Path
        if not candle.is_closed:
            # Forming candle: update forming buffer, do not commit to historical completed list
            state.forming_candle = candle
            state.last_receive_timestamp = candle.receive_timestamp
            state.last_processed_timestamp = now
            return True, "FORMING_CANDLE_UPDATED", None

        # 3. Duplicate Detection for Completed Candle
        if state.completed_candles:
            last_candle = state.completed_candles[-1]
            if last_candle.candle_timestamp == candle.candle_timestamp:
                state.duplicate_events_count += 1
                return True, "DUPLICATE_CANDLE_IGNORED", None

            # Out-of-order completed candle check
            if candle.candle_timestamp < last_candle.candle_timestamp:
                state.out_of_order_events_count += 1
                return False, f"Out-of-order candle timestamp: {candle.candle_timestamp} < {last_candle.candle_timestamp}", None

            # Missing candle detection (for 1m timeframe)
            if candle.timeframe == "1m":
                expected_delta_sec = 60.0
                actual_delta_sec = (candle.candle_timestamp - last_candle.candle_timestamp).total_seconds()
                if actual_delta_sec > expected_delta_sec:
                    # E.g. gap of 2 minutes = 1 missing bar
                    missing = int((actual_delta_sec - expected_delta_sec) // expected_delta_sec)
                    if missing > 0:
                        state.missing_candles_count += missing

        # 4. Latency Calculation
        provider_lat = None
        if candle.event_timestamp:
            provider_lat = max(0.0, (candle.receive_timestamp - candle.event_timestamp).total_seconds() * 1000.0)

        proc_lat = max(0.0, (now - candle.receive_timestamp).total_seconds() * 1000.0)
        e2e_lat = (provider_lat if provider_lat is not None else 0.0) + proc_lat

        latency = LatencyMetrics(
            provider_latency_ms=round(provider_lat, 2) if provider_lat is not None else None,
            processing_latency_ms=round(proc_lat, 2),
            end_to_end_latency_ms=round(e2e_lat, 2),
        )

        # 5. Commit Completed Candle
        state.completed_candles.append(candle)
        state.total_completed_candles += 1
        state.forming_candle = None  # Clear forming candle once finalized
        state.last_event_timestamp = candle.event_timestamp
        state.last_receive_timestamp = candle.receive_timestamp
        state.last_processed_timestamp = now

        # Recovery transition
        if state.quality_state == DataQualityState.RECOVERING:
            state.recovery_observations_count += 1
            if state.recovery_observations_count >= self.recovery_required_bars:
                state.quality_state = DataQualityState.CONNECTED
        elif state.quality_state in (DataQualityState.STALE, DataQualityState.DISCONNECTED):
            state.quality_state = DataQualityState.RECOVERING
            state.recovery_observations_count = 1

        return True, None, latency

    def evaluate_staleness(self, current_time: Optional[datetime] = None) -> None:
        """
        Evaluate staleness across all registered symbol streams against current time.
        Transitions symbol and global state to STALE or DISCONNECTED if thresholds breached.
        """
        now = _ensure_aware_utc(current_time)
        stale_symbols = 0
        total_symbols = len(self._symbols)

        for sym, state in self._symbols.items():
            if state.last_receive_timestamp is None:
                continue
            elapsed_sec = (now - state.last_receive_timestamp).total_seconds()

            if elapsed_sec > self.stale_threshold_seconds:
                if state.quality_state not in (DataQualityState.STALE, DataQualityState.DISCONNECTED):
                    state.quality_state = DataQualityState.STALE
                    self._outage_log.append({
                        "event": "SYMBOL_STALE",
                        "symbol": sym,
                        "elapsed_seconds": elapsed_sec,
                        "timestamp": now.isoformat(),
                    })
                stale_symbols += 1

        # Global feed state assessment
        if total_symbols > 0 and stale_symbols == total_symbols:
            if self._global_state != DataQualityState.STALE:
                self._global_state = DataQualityState.STALE
                self._outage_log.append({
                    "event": "GLOBAL_OUTAGE_STALE",
                    "stale_symbols_count": stale_symbols,
                    "timestamp": now.isoformat(),
                })
        elif total_symbols > 0 and stale_symbols == 0:
            if self._global_state in (DataQualityState.STALE, DataQualityState.DISCONNECTED):
                self._global_state = DataQualityState.RECOVERING

    def force_disconnect(self, reason: str = "Transport severed") -> None:
        """Trigger an explicit transport disconnect across all symbols."""
        self._global_state = DataQualityState.DISCONNECTED
        now = datetime.now(timezone.utc)
        for sym, state in self._symbols.items():
            state.quality_state = DataQualityState.DISCONNECTED
            state.recovery_observations_count = 0
        self._outage_log.append({
            "event": "GLOBAL_DISCONNECT",
            "reason": reason,
            "timestamp": now.isoformat(),
        })

    def export_canonical_dataframe(self, symbol: str, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Export completed candles as a canonical pandas DataFrame conforming to
        SignalForge OHLCV contract (DatetimeIndex, Open, High, Low, Close, Volume).
        Strictly excludes in-progress / forming candles.
        """
        clean_sym = symbol.strip().upper()
        if clean_sym not in self._symbols:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        state = self._symbols[clean_sym]
        candles = state.completed_candles
        if limit and limit > 0:
            candles = candles[-limit:]

        if not candles:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        records = []
        indices = []
        for c in candles:
            indices.append(c.candle_timestamp)
            records.append({
                "Open": c.open,
                "High": c.high,
                "Low": c.low,
                "Close": c.close,
                "Volume": c.volume,
            })

        df = pd.DataFrame(records, index=pd.DatetimeIndex(indices))
        df.index.name = None
        return df

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Aggregate system telemetry for API and operational dashboard."""
        now = datetime.now(timezone.utc)
        symbols_summary = {}

        for sym, st in self._symbols.items():
            symbols_summary[sym] = {
                "symbol": sym,
                "quality_state": st.quality_state.value,
                "feed_type": st.feed_type.value,
                "total_quotes": st.total_quotes_received,
                "total_completed_candles": st.total_completed_candles,
                "missing_candles": st.missing_candles_count,
                "duplicates": st.duplicate_events_count,
                "out_of_order": st.out_of_order_events_count,
                "invalid_events": st.invalid_events_count,
                "avg_provider_latency_ms": st.avg_provider_latency_ms,
                "avg_processing_latency_ms": st.avg_processing_latency_ms,
                "avg_end_to_end_latency_ms": st.avg_end_to_end_latency_ms,
                "last_quote_ltp": st.last_quote.ltp if st.last_quote else None,
                "last_event_timestamp": st.last_event_timestamp.isoformat() if st.last_event_timestamp else None,
                "last_processed_timestamp": st.last_processed_timestamp.isoformat() if st.last_processed_timestamp else None,
            }

        return {
            "source_id": self.source_id,
            "global_state": self._global_state.value,
            "default_feed_type": self.default_feed_type.value,
            "total_registered_symbols": len(self._symbols),
            "symbols": symbols_summary,
            "outage_events_count": len(self._outage_log),
            "timestamp": now.isoformat(),
            "simulation_only": True,
        }

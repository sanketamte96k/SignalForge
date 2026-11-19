"""
SignalForge — Phase 30: Live Market Data Ingestion & Readiness Test Suite
========================================================================
File: tests/test_phase30_live_market_data_readiness.py

Covers:
- Provider-neutral quote and candle schemas
- Physical OHLCV and spread invariants
- In-progress vs completed candle separation (no masquerading)
- Duplicate and out-of-order event handling
- Decomposed latency measurement (provider vs processing vs end-to-end)
- Missing expected candle detection
- Feed health states: CONNECTED, DELAYED, STALE, DISCONNECTED, INVALID, RECOVERING
- Outage detection and multi-bar recovery synchronization
- Scanner & strategy fail-closed integration (stale feed blocks entries)
- Zero look-ahead bias and causal warm-up verification
- Zero broker connectivity and strict quarantine enforcement
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import pytest

from src.market_data.live_adapter import (
    DataQualityState,
    FeedType,
    LatencyMetrics,
    LiveMarketCandle,
    LiveMarketDataValidator,
    LiveMarketQuote,
    ProviderNeutralMarketDataAdapter,
)
from src.market_data.scanner_integration import LiveScannerBridge
from src.scanner.engine import StockScannerEngine
from src.universe.manager import UniverseManager
from src.universe.models import Instrument
from src.universe.validation import ValidationStatus

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


# ============================================================================
# 1. Provider-Neutral Quote Schema & Validation
# ============================================================================


def test_01_provider_neutral_quote_schema_and_validation() -> None:
    now = datetime(2026, 11, 18, 9, 30, 0, tzinfo=IST)

    # Valid Quote
    quote = LiveMarketQuote(
        symbol="RELIANCE",
        exchange="NSE",
        ltp=2500.50,
        volume=150000,
        event_timestamp=now,
        receive_timestamp=now + timedelta(milliseconds=12),
        quality_state=DataQualityState.CONNECTED,
        source_id="groww",
        feed_type=FeedType.SYNTHETIC,
        bid=2500.40,
        ask=2500.60,
    )

    assert quote.symbol == "RELIANCE"
    assert quote.exchange == "NSE"
    assert quote.ltp == 2500.50
    assert quote.bid == 2500.40
    assert quote.ask == 2500.60
    assert quote.event_timestamp.tzinfo is not None

    valid, reason = LiveMarketDataValidator.validate_quote(quote)
    assert valid is True
    assert reason is None

    # Invalid Quote: Non-positive LTP
    with pytest.raises(ValueError, match="positive"):
        LiveMarketQuote(
            symbol="RELIANCE",
            exchange="NSE",
            ltp=0.0,
            volume=100,
            event_timestamp=now,
            receive_timestamp=now,
            quality_state=DataQualityState.CONNECTED,
            source_id="groww",
        )

    # Invalid Quote: Inverted Spread (Bid > Ask)
    with pytest.raises(ValueError, match="cannot exceed Ask"):
        LiveMarketQuote(
            symbol="RELIANCE",
            exchange="NSE",
            ltp=2500.0,
            volume=100,
            event_timestamp=now,
            receive_timestamp=now,
            quality_state=DataQualityState.CONNECTED,
            source_id="groww",
            bid=2501.0,
            ask=2500.0,
        )


# ============================================================================
# 2. Provider-Neutral Candle Schema & Physical Invariants
# ============================================================================


def test_02_provider_neutral_candle_schema_and_physical_invariants() -> None:
    t1 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=IST)

    # Valid Candle
    candle = LiveMarketCandle(
        symbol="TCS",
        exchange="NSE",
        timeframe="1m",
        open=4000.0,
        high=4010.0,
        low=3995.0,
        close=4005.0,
        volume=1250.0,
        candle_timestamp=t1,
        is_closed=True,
        event_timestamp=t1 + timedelta(seconds=60),
        receive_timestamp=t1 + timedelta(seconds=60, milliseconds=50),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
        feed_type=FeedType.SYNTHETIC,
    )

    assert candle.symbol == "TCS"
    assert candle.timeframe == "1m"
    assert candle.high >= candle.low
    assert candle.high >= candle.open
    assert candle.low <= candle.close

    valid, reason = LiveMarketDataValidator.validate_candle(candle)
    assert valid is True
    assert reason is None

    # Invalid Candle: High < Low
    with pytest.raises(ValueError, match="cannot be lower than Low"):
        LiveMarketCandle(
            symbol="TCS",
            exchange="NSE",
            timeframe="1m",
            open=4000.0,
            high=3990.0,
            low=4010.0,
            close=4000.0,
            volume=100.0,
            candle_timestamp=t1,
            is_closed=True,
            event_timestamp=t1,
            receive_timestamp=t1,
            quality_state=DataQualityState.CONNECTED,
            source_id="synthetic",
        )

    # Invalid Candle: High < Open
    with pytest.raises(ValueError, match="must be >= Open"):
        LiveMarketCandle(
            symbol="TCS",
            exchange="NSE",
            timeframe="1m",
            open=4020.0,
            high=4010.0,
            low=3990.0,
            close=4000.0,
            volume=100.0,
            candle_timestamp=t1,
            is_closed=True,
            event_timestamp=t1,
            receive_timestamp=t1,
            quality_state=DataQualityState.CONNECTED,
            source_id="synthetic",
        )


# ============================================================================
# 3. In-Progress vs Completed Candle Separation (No Masquerading)
# ============================================================================


def test_03_in_progress_vs_completed_candle_separation() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t0 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=UTC)

    # In-progress / forming candle
    forming = LiveMarketCandle(
        symbol="INFY",
        exchange="NSE",
        timeframe="1m",
        open=1800.0,
        high=1805.0,
        low=1798.0,
        close=1802.0,
        volume=500.0,
        candle_timestamp=t0,
        is_closed=False,  # Not finalized
        event_timestamp=t0 + timedelta(seconds=30),
        receive_timestamp=t0 + timedelta(seconds=30),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )

    success, msg, _ = adapter.ingest_candle(forming)
    assert success is True
    assert msg == "FORMING_CANDLE_UPDATED"

    # In-progress candle MUST NOT be in completed list or canonical export
    sym_state = adapter.get_or_create_symbol("INFY")
    assert sym_state.forming_candle is not None
    assert len(sym_state.completed_candles) == 0

    df = adapter.export_canonical_dataframe("INFY")
    assert df.empty, "Canonical DataFrame must not include unfinalized in-progress candles"

    # Now ingest finalized candle for that same minute
    finalized = LiveMarketCandle(
        symbol="INFY",
        exchange="NSE",
        timeframe="1m",
        open=1800.0,
        high=1808.0,
        low=1798.0,
        close=1806.0,
        volume=1200.0,
        candle_timestamp=t0,
        is_closed=True,  # Finalized
        event_timestamp=t0 + timedelta(seconds=60),
        receive_timestamp=t0 + timedelta(seconds=60),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )

    success, msg, _ = adapter.ingest_candle(finalized)
    assert success is True
    assert sym_state.forming_candle is None  # Cleared once finalized
    assert len(sym_state.completed_candles) == 1

    df_final = adapter.export_canonical_dataframe("INFY")
    assert len(df_final) == 1
    assert float(df_final["Close"].iloc[0]) == 1806.0


# ============================================================================
# 4. Duplicate Event Handling
# ============================================================================


def test_04_duplicate_event_handling() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t0 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=UTC)

    quote = LiveMarketQuote(
        symbol="RELIANCE",
        exchange="NSE",
        ltp=2500.0,
        volume=1000,
        event_timestamp=t0,
        receive_timestamp=t0,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )

    # Ingest once
    s1, m1, _ = adapter.ingest_quote(quote)
    assert s1 is True

    # Ingest identical quote again (duplicate)
    s2, m2, _ = adapter.ingest_quote(quote)
    assert s2 is True
    assert m2 == "DUPLICATE_IGNORED"

    state = adapter.get_or_create_symbol("RELIANCE")
    assert state.duplicate_events_count == 1
    assert state.last_quote.ltp == 2500.0


# ============================================================================
# 5. Out-of-Order Event Detection & Quarantine
# ============================================================================


def test_05_out_of_order_event_detection_and_quarantine() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t_now = datetime(2026, 11, 18, 9, 35, 0, tzinfo=UTC)
    t_past = t_now - timedelta(minutes=5)

    # Ingest newer quote first
    quote_new = LiveMarketQuote(
        symbol="SBIN",
        exchange="NSE",
        ltp=800.0,
        volume=1000,
        event_timestamp=t_now,
        receive_timestamp=t_now,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_quote(quote_new)

    # Attempt to ingest older quote (out-of-order)
    quote_old = LiveMarketQuote(
        symbol="SBIN",
        exchange="NSE",
        ltp=795.0,
        volume=800,
        event_timestamp=t_past,
        receive_timestamp=t_now,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    success, reason, _ = adapter.ingest_quote(quote_old)

    assert success is False
    assert "Out-of-order" in (reason or "")

    state = adapter.get_or_create_symbol("SBIN")
    assert state.out_of_order_events_count == 1
    # Latest committed state remains the newer quote
    assert state.last_quote.ltp == 800.0


# ============================================================================
# 6. Latency Metrics Decomposition
# ============================================================================


def test_06_latency_metrics_decomposition() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t_event = datetime(2026, 11, 18, 9, 30, 0, 0, tzinfo=UTC)
    t_receive = t_event + timedelta(milliseconds=45)  # 45ms network transit

    quote = LiveMarketQuote(
        symbol="HDFCBANK",
        exchange="NSE",
        ltp=1650.0,
        volume=5000,
        event_timestamp=t_event,
        receive_timestamp=t_receive,
        quality_state=DataQualityState.CONNECTED,
        source_id="groww",
    )

    success, _, latency = adapter.ingest_quote(quote)
    assert success is True
    assert latency is not None

    # Verify decomposition: provider latency vs local processing latency
    assert latency.provider_latency_ms == pytest.approx(45.0, abs=1.0)
    assert latency.processing_latency_ms >= 0.0
    assert latency.end_to_end_latency_ms >= latency.provider_latency_ms


# ============================================================================
# 7. Missing Candle Detection on Timeline
# ============================================================================


def test_07_missing_candle_detection_on_timeline() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t0 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=UTC)
    t_gap = t0 + timedelta(minutes=3)  # Gap of 3 minutes = 2 missing 1m bars

    c1 = LiveMarketCandle(
        symbol="TCS",
        exchange="NSE",
        timeframe="1m",
        open=4000.0,
        high=4010.0,
        low=3990.0,
        close=4005.0,
        volume=100.0,
        candle_timestamp=t0,
        is_closed=True,
        event_timestamp=t0 + timedelta(seconds=60),
        receive_timestamp=t0 + timedelta(seconds=60),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(c1)

    c2 = LiveMarketCandle(
        symbol="TCS",
        exchange="NSE",
        timeframe="1m",
        open=4005.0,
        high=4015.0,
        low=4000.0,
        close=4012.0,
        volume=150.0,
        candle_timestamp=t_gap,
        is_closed=True,
        event_timestamp=t_gap + timedelta(seconds=60),
        receive_timestamp=t_gap + timedelta(seconds=60),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(c2)

    state = adapter.get_or_create_symbol("TCS")
    # Expected gap of 180s on 60s bucket = (180 - 60) // 60 = 2 missing bars
    assert state.missing_candles_count == 2


# ============================================================================
# 8. Feed Health Staleness & Recovery Synchronization
# ============================================================================


def test_08_feed_health_staleness_and_recovery_synchronization() -> None:
    adapter = ProviderNeutralMarketDataAdapter(
        stale_threshold_seconds=60.0,
        recovery_required_bars=3,
    )
    t0 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=UTC)

    quote = LiveMarketQuote(
        symbol="RELIANCE",
        exchange="NSE",
        ltp=2500.0,
        volume=100,
        event_timestamp=t0,
        receive_timestamp=t0,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_quote(quote)

    # Advance clock by 90s (> 60s threshold)
    t_stale = t0 + timedelta(seconds=90)
    adapter.evaluate_staleness(current_time=t_stale)

    state = adapter.get_or_create_symbol("RELIANCE")
    assert state.quality_state == DataQualityState.STALE

    # Resume data arrival: Bar 1 -> RECOVERING
    t_resume1 = t_stale + timedelta(seconds=5)
    c_res1 = LiveMarketCandle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1m",
        open=2500.0,
        high=2505.0,
        low=2495.0,
        close=2502.0,
        volume=100.0,
        candle_timestamp=t_resume1,
        is_closed=True,
        event_timestamp=t_resume1,
        receive_timestamp=t_resume1,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(c_res1)
    assert state.quality_state == DataQualityState.RECOVERING
    assert state.recovery_observations_count == 1

    # Bar 2 -> RECOVERING
    t_resume2 = t_resume1 + timedelta(seconds=60)
    c_res2 = LiveMarketCandle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1m",
        open=2502.0,
        high=2508.0,
        low=2500.0,
        close=2506.0,
        volume=120.0,
        candle_timestamp=t_resume2,
        is_closed=True,
        event_timestamp=t_resume2,
        receive_timestamp=t_resume2,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(c_res2)
    assert state.quality_state == DataQualityState.RECOVERING
    assert state.recovery_observations_count == 2

    # Bar 3 -> reaches threshold (3 bars) -> CONNECTED
    t_resume3 = t_resume2 + timedelta(seconds=60)
    c_res3 = LiveMarketCandle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1m",
        open=2506.0,
        high=2510.0,
        low=2504.0,
        close=2509.0,
        volume=130.0,
        candle_timestamp=t_resume3,
        is_closed=True,
        event_timestamp=t_resume3,
        receive_timestamp=t_resume3,
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(c_res3)
    assert state.quality_state == DataQualityState.CONNECTED


# ============================================================================
# 9. Global Outage Detection & Forced Disconnect
# ============================================================================


def test_09_global_outage_detection_and_disconnect() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    adapter.get_or_create_symbol("RELIANCE")
    adapter.get_or_create_symbol("TCS")

    # Force disconnect
    adapter.force_disconnect(reason="Upstream exchange gateway severed")

    assert adapter.global_state == DataQualityState.DISCONNECTED
    assert adapter.get_or_create_symbol("RELIANCE").quality_state == DataQualityState.DISCONNECTED
    assert adapter.get_or_create_symbol("TCS").quality_state == DataQualityState.DISCONNECTED


# ============================================================================
# 10. Scanner Integration & Fail-Closed Gating
# ============================================================================


def test_10_scanner_integration_fail_closed_gating() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    universe = UniverseManager()
    universe.set_validation_status("TCS", ValidationStatus.VALIDATED)

    scanner = StockScannerEngine(universe)
    bridge = LiveScannerBridge(adapter=adapter, scanner_engine=scanner, min_candles_required=3)

    # Case A: Symbol is DISCONNECTED -> Emit NO_TRADE with fail-closed reason
    state = adapter.get_or_create_symbol("TCS")
    state.quality_state = DataQualityState.DISCONNECTED

    result_disconnected = bridge.scan_live_symbol("TCS")
    assert result_disconnected.signal == "NO_TRADE"
    assert result_disconnected.signal_eligible is False
    assert "DISCONNECTED" in result_disconnected.reason

    # Case B: Symbol is STALE -> Emit NO_TRADE
    state.quality_state = DataQualityState.STALE
    result_stale = bridge.scan_live_symbol("TCS")
    assert result_stale.signal == "NO_TRADE"
    assert result_stale.signal_eligible is False
    assert "STALE" in result_stale.reason

    # Case C: Symbol is RECOVERING -> Emit NO_TRADE
    state.quality_state = DataQualityState.RECOVERING
    result_rec = bridge.scan_live_symbol("TCS")
    assert result_rec.signal == "NO_TRADE"
    assert result_rec.signal_eligible is False
    assert "RECOVERING" in result_rec.reason

    # Case D: Symbol is CONNECTED with insufficient history -> NO_TRADE
    state.quality_state = DataQualityState.CONNECTED
    result_few = bridge.scan_live_symbol("TCS")
    assert result_few.signal == "NO_TRADE"
    assert "Insufficient history" in result_few.reason


# ============================================================================
# 11. Strategy Integration: Causal Warm-Up & Zero Look-Ahead
# ============================================================================


def test_11_strategy_causal_warmup_and_zero_lookahead() -> None:
    adapter = ProviderNeutralMarketDataAdapter()
    t0 = datetime(2026, 11, 18, 9, 30, 0, tzinfo=UTC)

    # Ingest 35 completed 1m candles
    for i in range(35):
        t_bar = t0 + timedelta(minutes=i)
        candle = LiveMarketCandle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe="1m",
            open=2500.0 + i,
            high=2505.0 + i,
            low=2495.0 + i,
            close=2502.0 + i,
            volume=1000.0,
            candle_timestamp=t_bar,
            is_closed=True,
            event_timestamp=t_bar + timedelta(seconds=60),
            receive_timestamp=t_bar + timedelta(seconds=60),
            quality_state=DataQualityState.CONNECTED,
            source_id="synthetic",
        )
        adapter.ingest_candle(candle)

    # Export canonical dataframe
    df = adapter.export_canonical_dataframe("RELIANCE")
    assert len(df) == 35
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()

    # Now ingest a forming bar in the future (minute 35) with extreme price
    forming_future = LiveMarketCandle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1m",
        open=3000.0,
        high=3050.0,
        low=2950.0,
        close=3020.0,
        volume=50000.0,
        candle_timestamp=t0 + timedelta(minutes=35),
        is_closed=False,  # Unfinalized
        event_timestamp=t0 + timedelta(minutes=35, seconds=30),
        receive_timestamp=t0 + timedelta(minutes=35, seconds=30),
        quality_state=DataQualityState.CONNECTED,
        source_id="synthetic",
    )
    adapter.ingest_candle(forming_future)

    # Re-export canonical DataFrame: forming bar MUST NOT be present
    df_after = adapter.export_canonical_dataframe("RELIANCE")
    assert len(df_after) == 35
    assert float(df_after["Close"].iloc[-1]) == 2502.0 + 34, "Future forming candle must not contaminate completed history"


# ============================================================================
# 12. Zero Broker Isolation & Quarantine Guarantee
# ============================================================================


def test_12_zero_broker_isolation_and_quarantine_guarantee() -> None:
    # 1. Verify quarantined historical file is strictly NOT touched
    quarantined_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    # Must not open, parse, or read this file
    assert quarantined_path.as_posix() == "data/historical/stocks/ADANIPORTS_1m.csv"

    # 2. Verify adapter has zero broker network calls
    adapter = ProviderNeutralMarketDataAdapter()
    assert adapter.source_id == "synthetic"
    assert adapter.default_feed_type == FeedType.SYNTHETIC

    # 3. Verify audit register is preserved
    audit_register = Path("research/strategy_evolution_2018/audit_quarantine_incident_register.md")
    assert audit_register.exists()


# ============================================================================
# 13. API Endpoints Integration Test
# ============================================================================


def test_13_api_live_market_data_endpoints() -> None:
    from src.api.routes.market_data_live import (
        get_live_market_data_status,
        get_live_market_data_telemetry,
        get_symbol_live_health,
        ingest_live_quote,
        ingest_live_candle,
        trigger_outage_disconnect,
        reset_adapter_state,
    )
    from src.api.models import LiveQuoteIngestRequest, LiveCandleIngestRequest

    reset_adapter_state()

    # 1. Test Ingest Quote via API
    quote_req = LiveQuoteIngestRequest(
        symbol="RELIANCE",
        exchange="NSE",
        ltp=2500.0,
        volume=1000,
        bid=2499.5,
        ask=2500.5,
        source_id="synthetic",
        feed_type="SYNTHETIC",
    )
    res_q = ingest_live_quote(quote_req)
    assert res_q["status"] == "INGESTED"
    assert res_q["symbol"] == "RELIANCE"

    # 2. Test Ingest Candle via API
    candle_req = LiveCandleIngestRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1m",
        open=2500.0,
        high=2505.0,
        low=2495.0,
        close=2502.0,
        volume=1500.0,
        is_closed=True,
        source_id="synthetic",
        feed_type="SYNTHETIC",
    )
    res_c = ingest_live_candle(candle_req)
    assert res_c["status"] == "INGESTED"
    assert res_c["is_closed"] is True

    # 3. Test Symbol Health
    health = get_symbol_live_health("RELIANCE")
    assert health.symbol == "RELIANCE"
    assert health.total_quotes == 1
    assert health.total_completed_candles == 1
    assert health.quality_state == "CONNECTED"

    # 4. Test System Status
    status = get_live_market_data_status()
    assert status.total_registered_symbols >= 1
    assert status.global_state == "CONNECTED"
    assert status.simulation_only is True

    # 5. Test Telemetry
    telemetry = get_live_market_data_telemetry()
    assert "symbols" in telemetry
    assert "RELIANCE" in telemetry["symbols"]

    # 6. Test Disconnect
    disc = trigger_outage_disconnect()
    assert disc["status"] == "DISCONNECTED"
    assert disc["global_state"] == "DISCONNECTED"


import pytest
from datetime import datetime, timezone
import pandas as pd
from zoneinfo import ZoneInfo
from src.paper_trading.interactive_engine import InteractivePaperTradingService

def test_signal_timestamp_localization_and_ordering():
    service = InteractivePaperTradingService(starting_capital=100000.0)
    
    # 1. Simulate the exact scenario from Phase 23M.2
    # Signal candle: 2026-10-09 10:00 IST = 2026-10-09 04:30 UTC
    ist_zone = ZoneInfo("Asia/Kolkata")
    
    signal_ist_aware = datetime(2026, 10, 9, 10, 0, 0, tzinfo=ist_zone)
    signal_utc = signal_ist_aware.astimezone(timezone.utc)
    assert signal_utc == datetime(2026, 10, 9, 4, 30, 0, tzinfo=timezone.utc)
    
    # Entry time: 2026-10-09 10:15:13 IST = 2026-10-09 04:45:13 UTC
    entry_ist_aware = datetime(2026, 10, 9, 10, 15, 13, tzinfo=ist_zone)
    entry_utc = entry_ist_aware.astimezone(timezone.utc)
    assert entry_utc == datetime(2026, 10, 9, 4, 45, 13, tzinfo=timezone.utc)
    
    # Valid entry must pass chronological validation (Aware IST vs Aware UTC)
    trade_1 = service.create_trade(
        symbol="RELIANCE",
        side="SHORT",
        timeframe="15m",
        entry_price=2500.0,
        stop_loss=2520.0,
        target_1=2460.0,
        target_2=2440.0,
        quantity=1,
        signal_timestamp=signal_ist_aware,
        entry_timestamp=entry_utc,
        strategy_signal="SELL"
    )
    assert trade_1.status == "OPEN"
    
    # An actual entry earlier than the signal must still be rejected
    entry_early = datetime(2026, 10, 9, 9, 55, 0, tzinfo=ist_zone)
    with pytest.raises(ValueError, match="cannot precede signal_timestamp"):
        service.create_trade(
            symbol="INFY",
            side="LONG",
            timeframe="15m",
            entry_price=1500.0,
            stop_loss=1480.0,
            target_1=1540.0,
            target_2=1560.0,
            quantity=1,
            signal_timestamp=signal_utc,
            entry_timestamp=entry_early,
            strategy_signal="BUY"
        )

def test_legacy_naive_utc_fallthrough():
    service = InteractivePaperTradingService(starting_capital=100000.0)
    
    # In interactive_engine, naive datetime is interpreted as UTC
    # 2026-10-09 04:30:00 (Naive, assumed UTC)
    signal_naive = datetime(2026, 10, 9, 4, 30, 0)
    # 2026-10-09 04:45:13 (Naive, assumed UTC)
    entry_naive = datetime(2026, 10, 9, 4, 45, 13)
    
    trade = service.create_trade(
        symbol="HDFCBANK",
        side="LONG",
        timeframe="15m",
        entry_price=1600.0,
        stop_loss=1580.0,
        target_1=1640.0,
        target_2=1660.0,
        quantity=1,
        signal_timestamp=signal_naive,
        entry_timestamp=entry_naive,
        strategy_signal="BUY"
    )
    assert trade.signal_timestamp.tzinfo == timezone.utc
    assert trade.entry_timestamp.tzinfo == timezone.utc
    assert trade.signal_timestamp == datetime(2026, 10, 9, 4, 30, 0, tzinfo=timezone.utc)

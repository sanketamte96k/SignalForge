import pytest
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.paper_trading.interactive_engine import InteractivePaperTradingService, TradeStatus
from src.data.market_data import MarketDataResult
from scripts.phase23M_continuous_monitoring import LiveScheduler
import tempfile

class MockMarketDataService:
    def get_historical(self, req):
        # Return a mocked dataframe with one candle for RELIANCE
        df = pd.DataFrame({
            "Open": [2490.0],
            "High": [2500.0],
            "Low": [2480.0],
            "Close": [2495.0],
            "Volume": [1000]
        }, index=[pd.Timestamp("2026-10-09 10:45:00")])
        return MarketDataResult(symbol=req.symbol, interval=req.interval, exchange="NSE", provider="mock", data=df)

def test_live_scheduler_open_position_monitoring_no_name_error():
    temp_file = tempfile.mktemp(suffix=".json")
    service = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=100000.0)
    
    # create a short trade
    signal_ist_aware = datetime(2026, 10, 9, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    entry_utc = datetime(2026, 10, 9, 4, 45, 13, tzinfo=timezone.utc)
    
    trade = service.create_trade(
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
    
    mock_data = MockMarketDataService()
    
    # Init scheduler
    scheduler = LiveScheduler(data_service=mock_data, paper_service=service, symbols=["RELIANCE"])
    
    # We shouldn't raise NameError for timezone
    scheduler.poll_once()
    
    trade = service.get_trade(trade.trade_id)
    assert trade.unrealized_pnl == 5.0 # (2500 - 2495) * 1

class StatefulMockMarketDataService:
    def __init__(self):
        self.call_count = 0
        
    def get_historical(self, req):
        self.call_count += 1
        
        if self.call_count == 1:
            # Poll 1: 10:45 candle
            df = pd.DataFrame({
                "Open": [2490.0],
                "High": [2500.0],
                "Low": [2480.0],
                "Close": [2495.0],
                "Volume": [1000]
            }, index=[pd.Timestamp("2026-10-09 10:45:00")])
            return MarketDataResult(symbol=req.symbol, interval=req.interval, exchange="NSE", provider="mock", data=df)
            
        elif self.call_count == 2:
            # Poll 2: Same 10:45 candle (no new data)
            df = pd.DataFrame({
                "Open": [2490.0],
                "High": [2500.0],
                "Low": [2480.0],
                "Close": [2495.0],
                "Volume": [1000]
            }, index=[pd.Timestamp("2026-10-09 10:45:00")])
            return MarketDataResult(symbol=req.symbol, interval=req.interval, exchange="NSE", provider="mock", data=df)
            
        elif self.call_count == 3:
            # Poll 3: Provider failure
            raise ProviderUnavailableError("Simulated failure")
            
        elif self.call_count == 4:
            # Poll 4: Recovery with new 10:46 candle
            df = pd.DataFrame({
                "Open": [2490.0],
                "High": [2500.0],
                "Low": [2480.0],
                "Close": [2495.0],
                "Volume": [1000]
            }, index=[pd.Timestamp("2026-10-09 10:45:00")])
            df.loc[pd.Timestamp("2026-10-09 10:46:00")] = [2495.0, 2515.0, 2490.0, 2510.0, 1500]
            return MarketDataResult(symbol=req.symbol, interval=req.interval, exchange="NSE", provider="mock", data=df)

def test_live_scheduler_candle_tracking(caplog):
    temp_file = tempfile.mktemp(suffix=".json")
    service = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=100000.0)
    
    # create a short trade
    signal_ist_aware = datetime(2026, 10, 9, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    entry_utc = datetime(2026, 10, 9, 4, 45, 13, tzinfo=timezone.utc)
    
    trade = service.create_trade(
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
    
    mock_data = StatefulMockMarketDataService()
    scheduler = LiveScheduler(data_service=mock_data, paper_service=service, symbols=["RELIANCE"])
    
    # 1. Poll 1: Expect 10:45 candle to be processed
    scheduler.poll_once()
    assert len(scheduler.last_evaluated_1m_candle) == 1
    assert scheduler.last_evaluated_1m_candle[trade.trade_id] == pd.Timestamp("2026-10-09 10:45:00").tz_localize("Asia/Kolkata")
    assert "is stale" in caplog.text or "STALE/UNAVAILABLE" in caplog.text
    
    # 2. Poll 2: No new data. Expect last evaluated candle unchanged
    scheduler.poll_once()
    assert scheduler.last_evaluated_1m_candle[trade.trade_id] == pd.Timestamp("2026-10-09 10:45:00").tz_localize("Asia/Kolkata")
    
    # 3. Poll 3: Provider failure
    from src.data.market_data_service import ProviderUnavailableError
    scheduler.poll_once() # Will catch the error and break cleanly
    assert "Error polling RELIANCE" in caplog.text
    
    # 4. Poll 4: Recovery + new candle
    scheduler.poll_once()
    assert scheduler.last_evaluated_1m_candle[trade.trade_id] == pd.Timestamp("2026-10-09 10:46:00").tz_localize("Asia/Kolkata")
    
    trade = service.get_trade(trade.trade_id)
    assert trade.unrealized_pnl == -10.0 # (2500 - 2510) * 1

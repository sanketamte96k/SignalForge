import pytest
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

from src.paper_trading.interactive_engine import InteractivePaperTradingService, TradeStatus

import tempfile

def setup_service():
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
    return service, trade.trade_id

def test_unrealized_pnl_calculation():
    service, trade_id = setup_service()
    trade = service.get_trade(trade_id)
    
    # Mark down: favorable for short
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    updated_trade = service.update_trade(
        trade_id=trade_id, 
        current_price=2490.0, 
        timestamp=eval_time
    )
    
    assert updated_trade.status == TradeStatus.OPEN.value
    assert updated_trade.unrealized_pnl == 10.0  # (2500 - 2490) * 1
    
    # Mark up: unfavorable for short
    eval_time = datetime(2026, 10, 9, 4, 51, 0, tzinfo=timezone.utc)
    updated_trade = service.update_trade(
        trade_id=trade_id, 
        current_price=2510.0, 
        timestamp=eval_time
    )
    
    assert updated_trade.unrealized_pnl == -10.0  # (2500 - 2510) * 1

def test_stop_loss_exit():
    service, trade_id = setup_service()
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    
    trade = service.update_trade(
        trade_id=trade_id,
        candle_open=2500.0,
        candle_high=2525.0, # hits SL 2520
        candle_low=2490.0,
        candle_close=2510.0,
        timestamp=eval_time
    )
    
    assert trade.status == TradeStatus.STOPPED_OUT.value
    assert trade.exit_price == 2520.0
    assert trade.is_terminal is True
    assert trade.unrealized_pnl == 0.0
    assert trade.total_cost > 0.0 # costs applied exactly once
    assert "Stop Loss Hit" in trade.exit_reason

def test_target_2_exit():
    service, trade_id = setup_service()
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    
    trade = service.update_trade(
        trade_id=trade_id,
        candle_open=2490.0,
        candle_high=2495.0, 
        candle_low=2430.0, # hits T2 2440
        candle_close=2435.0,
        timestamp=eval_time
    )
    
    assert trade.status == TradeStatus.TARGET_2_HIT.value
    assert trade.exit_price == 2440.0
    assert trade.unrealized_pnl == 0.0
    assert "Target 2 Hit" in trade.exit_reason

def test_conservative_ambiguity_handling():
    service, trade_id = setup_service()
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    
    # Candle touches BOTH SL (2520) and T2 (2440)
    trade = service.update_trade(
        trade_id=trade_id,
        candle_open=2490.0,
        candle_high=2530.0, 
        candle_low=2430.0, 
        candle_close=2500.0,
        timestamp=eval_time
    )
    
    assert trade.status == TradeStatus.STOPPED_OUT.value
    assert trade.exit_price == 2520.0
    assert "Conservative Resolution" in trade.exit_reason

def test_invalid_data_rejection():
    service, trade_id = setup_service()
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    
    with pytest.raises(ValueError, match="positive finite numbers"):
        service.update_trade(
            trade_id=trade_id,
            candle_open=2490.0,
            candle_high=math.nan, 
            candle_low=2430.0, 
            candle_close=2500.0,
            timestamp=eval_time
        )
        
    with pytest.raises(ValueError, match="Malformed candle: high"):
        service.update_trade(
            trade_id=trade_id,
            candle_open=2490.0,
            candle_high=2400.0, 
            candle_low=2430.0, 
            candle_close=2500.0,
            timestamp=eval_time
        )

def test_repeated_polls_cannot_close_twice():
    service, trade_id = setup_service()
    eval_time = datetime(2026, 10, 9, 4, 50, 0, tzinfo=timezone.utc)
    
    trade = service.update_trade(
        trade_id=trade_id,
        candle_open=2490.0,
        candle_high=2530.0, 
        candle_low=2480.0, 
        candle_close=2500.0,
        timestamp=eval_time
    )
    
    assert trade.status == TradeStatus.STOPPED_OUT.value
    
    # Try updating again
    eval_time_2 = datetime(2026, 10, 9, 4, 51, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="trade is already in terminal state"):
        service.update_trade(
            trade_id=trade_id,
            current_price=2500.0,
            timestamp=eval_time_2
        )

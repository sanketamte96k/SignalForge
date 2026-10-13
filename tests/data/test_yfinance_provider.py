import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from src.data.market_data import MarketDataRequest, MarketDataProvider
from src.data.providers.yfinance_provider import (
    YFinanceProvider,
    YFinanceError,
    YFinanceRateLimitError,
    YFinanceDataFormatError,
)

@pytest.fixture
def provider():
    return YFinanceProvider()

def test_conforms_to_interface(provider):
    assert isinstance(provider, MarketDataProvider)
    assert provider.provider_name == "yfinance"
    assert provider.is_available() is True

def test_symbol_mapping(provider):
    assert provider.resolve_yf_symbol("RELIANCE") == "RELIANCE.NS"
    assert provider.resolve_yf_symbol("HDFCBANK") == "HDFCBANK.NS"
    assert provider.resolve_yf_symbol("ICICIBANK") == "ICICIBANK.NS"
    assert provider.resolve_yf_symbol("INFY") == "INFY.NS"
    assert provider.resolve_yf_symbol("RANDOM", "BSE") == "RANDOM.BO"

@patch("src.data.providers.yfinance_provider.yf.Ticker")
@patch("src.data.providers.yfinance_provider.pd.Timestamp.now")
def test_valid_historical_request(mock_now, mock_ticker, provider):
    mock_now.return_value = pd.Timestamp("2026-10-09 10:15:00", tz="Asia/Kolkata")
    
    mock_df = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [102.0, 102.5],
        "Low": [99.0, 100.5],
        "Close": [101.5, 102.0],
        "Volume": [1000, 2000]
    }, index=pd.to_datetime(["2026-10-09 09:15:00", "2026-10-09 09:30:00"]).tz_localize("Asia/Kolkata"))
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    result = provider.get_historical(req)
    
    assert result.symbol == "RELIANCE"
    assert result.interval == "15m"
    assert len(result.data) == 2
    assert result.metadata["yf_symbol"] == "RELIANCE.NS"
    assert result.data.index.tz is None  # Normalized to naive IST

@patch("src.data.providers.yfinance_provider.yf.Ticker")
def test_drop_forming_candle(mock_ticker):
    mock_df = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [102.0, 102.5],
        "Low": [99.0, 100.5],
        "Close": [101.5, 102.0],
        "Volume": [1000, 2000]
    }, index=pd.to_datetime(["2026-10-09 09:30:00", "2026-10-09 09:45:00"]).tz_localize("Asia/Kolkata"))
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    
    # Test at 09:44:59 (Before 09:45 candle even starts, though our test mock returns it. If returned, 09:44:59 < 10:00:00 so it drops it)
    provider_1 = YFinanceProvider(clock=lambda: pd.Timestamp("2026-10-09 09:44:59", tz="Asia/Kolkata"))
    result_1 = provider_1.get_historical(req)
    assert len(result_1.data) == 1
    assert result_1.data.index[0] == pd.Timestamp("2026-10-09 09:30:00")

    # Test at 09:45:00 (Candle just started forming, should be dropped)
    provider_2 = YFinanceProvider(clock=lambda: pd.Timestamp("2026-10-09 09:45:00", tz="Asia/Kolkata"))
    result_2 = provider_2.get_historical(req)
    assert len(result_2.data) == 1

    # Test at 09:59:59 (Candle is still forming, should be dropped)
    provider_3 = YFinanceProvider(clock=lambda: pd.Timestamp("2026-10-09 09:59:59", tz="Asia/Kolkata"))
    result_3 = provider_3.get_historical(req)
    assert len(result_3.data) == 1

    # Test at 10:00:00 (Candle has closed, should NOT be dropped)
    provider_4 = YFinanceProvider(clock=lambda: pd.Timestamp("2026-10-09 10:00:00", tz="Asia/Kolkata"))
    result_4 = provider_4.get_historical(req)
    assert len(result_4.data) == 2
    assert result_4.data.index[-1] == pd.Timestamp("2026-10-09 09:45:00")

    # Test at 10:00:01 (Candle safely closed)
    provider_5 = YFinanceProvider(clock=lambda: pd.Timestamp("2026-10-09 10:00:01", tz="Asia/Kolkata"))
    result_5 = provider_5.get_historical(req)
    assert len(result_5.data) == 2

@patch("src.data.providers.yfinance_provider.yf.Ticker")
@patch("src.data.providers.yfinance_provider.pd.Timestamp.now")
def test_naive_timestamp_handling(mock_now, mock_ticker, provider):
    # Ensure provider converts naive index to IST
    mock_now.return_value = pd.Timestamp("2026-10-09 10:15:00", tz="Asia/Kolkata")
    
    mock_df = pd.DataFrame({
        "Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.5], "Volume": [1000]
    }, index=pd.to_datetime(["2026-10-09 09:15:00"]))  # Naive
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="INFY", interval="15m")
    result = provider.get_historical(req)
    
    assert len(result.data) == 1
    assert result.data.index[0] == pd.Timestamp("2026-10-09 09:15:00")
    
@patch("src.data.providers.yfinance_provider.yf.Ticker")
def test_empty_response(mock_ticker, provider):
    instance = mock_ticker.return_value
    instance.history.return_value = pd.DataFrame()
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    with pytest.raises(ValueError, match="No market data returned"):
        provider.get_historical(req)

@patch("src.data.providers.yfinance_provider.yf.Ticker")
def test_missing_ohlc_values_quarantined(mock_ticker, provider):
    mock_df = pd.DataFrame({
        "Open": [100.0, None],
        "High": [102.0, 103.0],
        "Low": [99.0, 100.0],
        "Close": [101.5, 102.0],
        "Volume": [1000, 2000]
    }, index=pd.to_datetime(["2026-10-09 09:15:00", "2026-10-09 09:30:00"]).tz_localize("Asia/Kolkata"))
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    result = provider.get_historical(req)
    
    # 09:30 candle had None for Open, it must be dropped entirely
    assert len(result.data) == 1
    assert result.data.index[0] == pd.Timestamp("2026-10-09 09:15:00")
    assert "2026-10-09T09:30:00+05:30" in result.metadata["dropped_invalid_ohlc_timestamps"]

@patch("src.data.providers.yfinance_provider.yf.Ticker")
def test_missing_volume_normalized(mock_ticker, provider):
    mock_df = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [102.0, 102.5],
        "Low": [99.0, 100.5],
        "Close": [101.5, 102.0],
        "Volume": [1000, None]
    }, index=pd.to_datetime(["2026-10-09 09:15:00", "2026-10-09 09:30:00"]).tz_localize("Asia/Kolkata"))
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    result = provider.get_historical(req)
    
    assert len(result.data) == 2
    assert result.data.iloc[1]["Volume"] == 0
    assert "2026-10-09T09:30:00+05:30" in result.metadata["missing_volume_timestamps"]

@patch("src.data.providers.yfinance_provider.yf.Ticker")
@patch("src.data.providers.yfinance_provider.pd.Timestamp.now")
def test_duplicate_and_out_of_order_timestamps(mock_now, mock_ticker, provider):
    mock_now.return_value = pd.Timestamp("2026-10-09 12:00:00", tz="Asia/Kolkata")
    
    mock_df = pd.DataFrame({
        "Open": [1.0, 2.0, 3.0],
        "High": [1.1, 2.1, 3.1],
        "Low": [0.9, 1.9, 2.9],
        "Close": [1.05, 2.05, 3.05],
        "Volume": [100, 200, 300]
    }, index=pd.to_datetime([
        "2026-10-09 09:30:00", 
        "2026-10-09 09:15:00", 
        "2026-10-09 09:30:00"
    ]).tz_localize("Asia/Kolkata"))
    
    instance = mock_ticker.return_value
    instance.history.return_value = mock_df
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    result = provider.get_historical(req)
    
    assert len(result.data) == 2
    assert result.data.index[0] == pd.Timestamp("2026-10-09 09:15:00")
    assert result.data.index[1] == pd.Timestamp("2026-10-09 09:30:00")
    assert result.data.iloc[1]["Open"] == 3.0  # Kept last duplicate

@patch("src.data.providers.yfinance_provider.yf.Ticker")
def test_provider_exceptions(mock_ticker, provider):
    instance = mock_ticker.return_value
    instance.history.side_effect = Exception("Rate limited")
    
    req = MarketDataRequest(symbol="RELIANCE", interval="15m")
    with pytest.raises(YFinanceRateLimitError):
        provider.get_historical(req)

    instance.history.side_effect = Exception("Some network error")
    with pytest.raises(YFinanceError):
        provider.get_historical(req)

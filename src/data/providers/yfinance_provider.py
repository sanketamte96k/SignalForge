"""YFinance Market Data Provider for SignalForge.

Implements the MarketDataProvider interface for yfinance.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from src.data.market_data import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    validate_normalized_ohlcv,
    normalize_ohlcv_columns,
)

logger = logging.getLogger(__name__)

SUPPORTED_YF_INTERVALS = {
    "1m": "1m",
    "2m": "2m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
    "90m": "90m",
    "1h": "1h",
    "1d": "1d",
    "5d": "5d",
    "1wk": "1wk",
    "1mo": "1mo",
    "3mo": "3mo",
}

DEFAULT_YF_SYMBOL_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "SBIN": "SBIN.NS",
    "ICICIBANK": "ICICIBANK.NS",
}


class YFinanceError(Exception):
    """Base exception for yfinance provider."""


class YFinanceRateLimitError(YFinanceError):
    """Rate limit exceeded."""


class YFinanceDataFormatError(YFinanceError):
    """Data format is invalid."""


class YFinanceProvider(MarketDataProvider):
    """yfinance market-data adapter conforming to MarketDataProvider."""

    def __init__(
        self, 
        symbol_map: dict[str, str] | None = None, 
        drop_forming_candle: bool = True,
        clock: Any | None = None,
    ) -> None:
        self._symbol_map = dict(DEFAULT_YF_SYMBOL_MAP)
        if symbol_map:
            self._symbol_map.update(symbol_map)
        self.drop_forming_candle = drop_forming_candle
        self._clock = clock

    @property
    def provider_name(self) -> str:
        return "yfinance"

    def _get_current_time(self) -> pd.Timestamp:
        """Return the current time in IST, tz-naive to match data processing."""
        if self._clock:
            now = self._clock()
            if now.tz is None:
                return now
            return now.tz_convert("Asia/Kolkata").tz_localize(None)
        return pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)

    def is_available(self) -> bool:
        """yfinance is always available without credentials."""
        return True

    def resolve_yf_symbol(self, symbol: str, exchange: str = "NSE") -> str:
        """Map SignalForge ticker to Yahoo Finance ticker."""
        clean_symbol = symbol.strip().upper()
        if clean_symbol in self._symbol_map:
            return self._symbol_map[clean_symbol]

        if exchange.strip().upper() == "NSE":
            return f"{clean_symbol}.NS"
        elif exchange.strip().upper() == "BSE":
            return f"{clean_symbol}.BO"
        
        return clean_symbol

    def get_historical(self, request: MarketDataRequest) -> MarketDataResult:
        interval_key = request.interval.lower()
        if interval_key not in SUPPORTED_YF_INTERVALS:
            raise ValueError(
                f"Interval '{request.interval}' is not supported by yfinance. "
                f"Supported intervals: {sorted(SUPPORTED_YF_INTERVALS.keys())}"
            )

        yf_interval = SUPPORTED_YF_INTERVALS[interval_key]
        yf_symbol = self.resolve_yf_symbol(request.symbol, request.exchange)

        ticker = yf.Ticker(yf_symbol)
        
        # Start and end
        start_date = None
        end_date = None
        
        if request.start is not None:
            # yfinance expects date strings or datetime for start/end
            start_date = pd.Timestamp(request.start).tz_localize(None).strftime("%Y-%m-%d")
            
        if request.end is not None:
            end_date = pd.Timestamp(request.end).tz_localize(None).strftime("%Y-%m-%d")

        try:
            if start_date and end_date:
                df = ticker.history(start=start_date, end=end_date, interval=yf_interval, auto_adjust=request.adjusted)
            elif start_date:
                df = ticker.history(start=start_date, interval=yf_interval, auto_adjust=request.adjusted)
            else:
                # Default to a reasonable period if no start/end provided
                df = ticker.history(period="1mo", interval=yf_interval, auto_adjust=request.adjusted)
        except Exception as e:
            if "Rate limited" in str(e):
                raise YFinanceRateLimitError(f"Rate limited by Yahoo Finance: {e}") from e
            raise YFinanceError(f"Error fetching data from yfinance: {e}") from e

        if df is None or df.empty:
            raise ValueError(
                f"No market data returned by yfinance for symbol '{request.symbol}' "
                f"in requested range."
            )

        df = normalize_ohlcv_columns(df)
        
        # Keep only canonical columns if they exist, plus index
        cols_to_keep = [c for c in CANONICAL_OHLCV_COLUMNS if c in df.columns]
        df = df[cols_to_keep].copy()
        
        if len(cols_to_keep) != len(CANONICAL_OHLCV_COLUMNS):
            missing = set(CANONICAL_OHLCV_COLUMNS) - set(cols_to_keep)
            raise YFinanceDataFormatError(f"yfinance data missing required columns: {missing}")

        # Quarantine rows with missing OHLC values instead of forward-filling
        invalid_mask = df[["Open", "High", "Low", "Close"]].isna().any(axis=1)
        invalid_timestamps = df.index[invalid_mask].tolist()
        df = df[~invalid_mask].copy()

        if df.empty:
            raise ValueError("Data became empty after dropping invalid/NaN OHLC values.")

        # Preserve a diagnostic distinction for missing volume
        missing_volume_mask = df["Volume"].isna()
        missing_volume_timestamps = df.index[missing_volume_mask].tolist()
        df.loc[missing_volume_mask, "Volume"] = 0


        # Ensure index is Asia/Kolkata
        if df.index.tz is None:
            df.index = df.index.tz_localize("Asia/Kolkata")
        elif str(df.index.tz) != "Asia/Kolkata":
            df.index = df.index.tz_convert("Asia/Kolkata")
            
        df.index = df.index.tz_localize(None) # Remove tz for canonical consistency

        # Handle forming candle
        if self.drop_forming_candle and not df.empty:
            now_ist = self._get_current_time()
            latest_ts = df.index[-1]
            
            # For a 15m candle starting at 09:45, it forms until 10:00
            # Convert interval to minutes
            interval_mins_map = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "1h": 60}
            if interval_key in interval_mins_map:
                interval_td = pd.Timedelta(minutes=interval_mins_map[interval_key])
                candle_close_time = latest_ts + interval_td
                
                # If current time is strictly less than candle close time, it is forming
                if now_ist < candle_close_time:
                    df = df.iloc[:-1]

        if df.empty:
            raise ValueError("Filtered market data is empty.")

        # Sort index and drop duplicates
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        # Validate
        validate_normalized_ohlcv(df)
        
        # Strict low check
        if (df["Low"] <= 0).any():
            raise ValueError("Market data contains non-positive Low values (Low <= 0).")

        metadata = {
            "source": "yfinance",
            "yf_symbol": yf_symbol,
            "interval": yf_interval,
            "row_count": len(df),
            "dropped_invalid_ohlc_timestamps": [ts.isoformat() for ts in invalid_timestamps],
            "missing_volume_timestamps": [ts.isoformat() for ts in missing_volume_timestamps],
        }

        return MarketDataResult(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            data=df,
            provider=self.provider_name,
            requested_start=request.start,
            requested_end=request.end,
            metadata=metadata,
        )

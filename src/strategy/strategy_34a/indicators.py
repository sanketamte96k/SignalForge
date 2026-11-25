"""
SignalForge — Phase 34A: Multi-Timeframe Technical Indicators Engine
===================================================================
File: src/strategy/strategy_34a/indicators.py

Computes strictly lookahead-free technical indicators:
  - Weekly completed candles and Weekly EMA (10, 20, 30)
  - Daily EMA (20, 50)
  - Wilder's RSI (14)
  - Wilder's ATR (14)
  - Daily Volume SMA (20)
  - Relative Strength vs Nifty 50 over 20, 40, and 60 sessions
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def validate_ohlcv(df: pd.DataFrame, symbol: str) -> None:
    """Validates basic OHLCV structural integrity and monotonicity."""
    if df.empty:
        raise ValueError(f"Empty dataframe for symbol {symbol}")
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Symbol {symbol} missing columns: {missing}")

    if (df["open"] <= 0).any() or (df["high"] <= 0).any() or (df["low"] <= 0).any() or (df["close"] <= 0).any():
        raise ValueError(f"Symbol {symbol} contains non-positive price records")
    if (df["volume"] < 0).any():
        raise ValueError(f"Symbol {symbol} contains negative volume records")
    if (df["high"] < df["low"]).any():
        raise ValueError(f"Symbol {symbol} contains high < low violations")


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average with alpha = 2 / (period + 1)."""
    if len(series) == 0:
        return pd.Series(dtype=float, index=series.index)
    if period <= 0:
        raise ValueError(f"EMA period must be positive: {period}")
    return series.ewm(span=period, adjust=False).mean()


def calculate_tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculates True Range (TR) across high, low, and prior close."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR) using Wilder's exponential smoothing."""
    tr = calculate_tr(high, low, close)
    if len(tr) == 0:
        return pd.Series(dtype=float, index=high.index)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI) using Wilder's smoothing."""
    if len(close) < period + 1:
        return pd.Series(np.nan, index=close.index, dtype=float)

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's smoothing: alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Clean corner cases where loss == 0 or gain == 0
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(avg_gain != 0.0, 0.0)
    rsi = rsi.where(~(avg_loss.isna() & avg_gain.isna()), np.nan)
    return rsi


def build_completed_weekly_bars(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs completed weekly OHLCV bars from daily data.
    Each week is identified by ISO (year, week).
    The completion date of each week is the date of its last trading day.
    Computes weekly EMAs (10, 20, 30) deterministically.
    """
    df = daily_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    iso_cal = df.index.isocalendar()
    df["iso_year"] = iso_cal.year.values
    df["iso_week"] = iso_cal.week.values
    df["year_week"] = df["iso_year"] * 100 + df["iso_week"]

    # Group daily bars into completed weekly bars
    weekly_bars = df.groupby("year_week").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })

    # The completion date is the last daily session in that week
    completion_dates = df.reset_index().groupby("year_week")["index"].last()
    weekly_bars["completion_date"] = pd.to_datetime(completion_dates.values)
    weekly_bars = weekly_bars.set_index("completion_date").sort_index()

    # Calculate Weekly EMAs
    weekly_bars["wema10"] = calculate_ema(weekly_bars["close"], 10)
    weekly_bars["wema20"] = calculate_ema(weekly_bars["close"], 20)
    weekly_bars["wema30"] = calculate_ema(weekly_bars["close"], 30)
    weekly_bars["weekly_close"] = weekly_bars["close"]

    return weekly_bars


def calculate_nifty_relative_strength(
    stock_close: pd.Series,
    nifty_close: pd.Series,
    lookback: int,
) -> pd.Series:
    """
    Calculates stock relative performance vs Nifty 50 over N trading sessions:
      R_stock = (Close_stock(t) / Close_stock(t-N)) - 1.0
      R_nifty = (Close_nifty(t) / Close_nifty(t-N)) - 1.0
      RS = R_stock - R_nifty
    """
    stock_ret = (stock_close - stock_close.shift(lookback)) / stock_close.shift(lookback)
    nifty_ret = (nifty_close - nifty_close.shift(lookback)) / nifty_close.shift(lookback)
    rs = stock_ret - nifty_ret
    return rs


def attach_multi_timeframe_indicators(
    daily_df: pd.DataFrame,
    nifty_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attaches all Phase 34A multi-timeframe indicators onto daily dataframe lookahead-free:
      - Completed Weekly EMA 10, 20, 30 and Weekly Close
      - Daily EMA 20, EMA 50
      - Daily RSI 14
      - Daily ATR 14
      - Daily Volume SMA 20 and Volume Ratio
      - Relative Strength vs Nifty 50 (20, 40, 60 sessions)
    """
    df = daily_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # 1. Daily Trend & Momentum Indicators
    df["dema20"] = calculate_ema(df["close"], 20)
    df["dema50"] = calculate_ema(df["close"], 50)
    df["rsi14"] = calculate_rsi(df["close"], 14)
    df["atr14"] = calculate_atr(df["high"], df["low"], df["close"], 14)

    # 2. Volume Confirmation
    df["vol_sma20"] = df["volume"].rolling(window=20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma20"].replace(0.0, np.nan)

    # 3. Weekly Completed Indicators (Lookahead-free alignment via merge_asof backward)
    weekly_bars = build_completed_weekly_bars(df)
    weekly_cols = ["weekly_close", "wema10", "wema20", "wema30"]
    weekly_subset = weekly_bars[weekly_cols].sort_index()

    # Align backwards: at date t, takes the latest weekly candle with completion_date <= t
    df_aligned = pd.merge_asof(
        df,
        weekly_subset,
        left_index=True,
        right_index=True,
        direction="backward",
    )

    # 4. Relative Strength vs Nifty 50
    # Ensure Nifty is aligned to the same daily dates
    if not isinstance(nifty_df.index, pd.DatetimeIndex):
        nifty_df = nifty_df.copy()
        nifty_df.index = pd.to_datetime(nifty_df.index)

    # Reindex nifty_df to match df dates
    nifty_aligned_close = nifty_df["close"].reindex(df_aligned.index).ffill()

    df_aligned["rs_20"] = calculate_nifty_relative_strength(df_aligned["close"], nifty_aligned_close, 20)
    df_aligned["rs_40"] = calculate_nifty_relative_strength(df_aligned["close"], nifty_aligned_close, 40)
    df_aligned["rs_60"] = calculate_nifty_relative_strength(df_aligned["close"], nifty_aligned_close, 60)

    return df_aligned

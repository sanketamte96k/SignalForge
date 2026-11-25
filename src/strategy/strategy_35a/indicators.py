"""
SignalForge — Phase 35A: Technical Indicators Engine
===================================================
File: src/strategy/strategy_35a/indicators.py

Computes deterministic, lookahead-free indicators for Phase 35A:
  - SMA (50, 200) for stock and SMA (100) for Nifty 50
  - EMA (20, 50) and EMA 50 slope
  - Wilder's RSI (2, 5, 14)
  - Wilder's ATR (14)
  - Bollinger Bands (20-day, 2.0 std)
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


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average over rolling period."""
    if len(series) == 0:
        return pd.Series(dtype=float, index=series.index)
    if period <= 0:
        raise ValueError(f"SMA period must be positive: {period}")
    return series.rolling(window=period).mean()


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


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
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

    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(avg_gain != 0.0, 0.0)
    rsi = rsi.where(~(avg_loss.isna() & avg_gain.isna()), np.nan)
    return rsi


def calculate_bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Bollinger Bands: (Middle Band, Upper Band, Lower Band)."""
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    return middle, upper, lower


def attach_35a_indicators(daily_df: pd.DataFrame, nifty_df: pd.DataFrame) -> pd.DataFrame:
    """
    Attaches all Phase 35A regime and mean-reversion indicators onto daily dataframe lookahead-free:
      - Stock Trend & Regime: SMA 50, SMA 200, EMA 20, EMA 50, EMA 50 slope
      - Nifty Regime: Nifty Close, Nifty SMA 100
      - Mean Reversion: RSI 2, RSI 5, RSI 14
      - Bands: Bollinger Middle (SMA20), Upper (2.0 std), Lower (2.0 std)
      - Volatility: ATR 14
    """
    df = daily_df.copy()

    # 1. Stock Moving Averages
    df["sma50"] = calculate_sma(df["close"], 50)
    df["sma200"] = calculate_sma(df["close"], 200)
    df["ema20"] = calculate_ema(df["close"], 20)
    df["ema50"] = calculate_ema(df["close"], 50)
    df["ema50_slope"] = df["ema50"] - df["ema50"].shift(1)

    # 2. Mean Reversion Oscillators
    df["rsi2"] = calculate_rsi(df["close"], 2)
    df["rsi5"] = calculate_rsi(df["close"], 5)
    df["rsi14"] = calculate_rsi(df["close"], 14)

    # 3. Bollinger Bands & Volatility
    bb_mid, bb_upp, bb_low = calculate_bollinger_bands(df["close"], 20, 2.0)
    df["bb_middle"] = bb_mid
    df["bb_upper"] = bb_upp
    df["bb_lower"] = bb_low
    df["atr14"] = calculate_atr(df["high"], df["low"], df["close"], 14)

    # 4. Nifty 50 Benchmark Alignment
    # Map nifty close and sma100 to stock dates
    nifty_close = nifty_df["close"].reindex(df.index).ffill()
    nifty_sma100 = nifty_df["sma100"].reindex(df.index).ffill() if "sma100" in nifty_df.columns else calculate_sma(nifty_close, 100)

    df["nifty_close"] = nifty_close
    df["nifty_sma100"] = nifty_sma100

    return df

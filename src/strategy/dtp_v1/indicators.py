"""
SignalForge — Phase 32C.5: DTP-V1 Causal Indicators
===================================================
File: src/strategy/dtp_v1/indicators.py

Computes deterministic, strictly causal daily technical indicators for DTP-V1:
  - 20-day and 50-day Exponential Moving Averages (EMA)
  - 200-day Simple Moving Average (SMA)
  - 14-day Average True Range (ATR) with Wilder's smoothing
  - 14-day Relative Strength Index (RSI) with Wilder's smoothing
  - 14-day Average Directional Index (ADX, +DI, -DI)
  - 20-day Volume SMA and Relative Volume (RVOL)
  - 20-day / 2.5-std Bollinger Bands
  - 20-day Relative Strength versus benchmark
  - 20-day Rolling Swing Highs and Lows

All calculations operate strictly on completed historical bars without look-ahead.
"""

from __future__ import annotations

from typing import Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.dtp_v1.config import DTPV1Config


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average with alpha = 2 / (period + 1)."""
    if len(series) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"EMA period must be positive: {period}")
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average over rolling period."""
    if len(series) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"SMA period must be positive: {period}")
    return series.rolling(window=period).mean()


def calculate_tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculates True Range (TR) across high, low, and prior close."""
    if len(close) == 0:
        return pd.Series(dtype=float)
    prev_close = close.shift(1)
    hl = high - low
    hc = (high - prev_close).abs()
    lc = (low - prev_close).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """
    Calculates Average True Range (ATR) using Wilder's smoothing (alpha = 1 / period).
    """
    if len(close) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"ATR period must be positive: {period}")
    tr = calculate_tr(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates Relative Strength Index (RSI) using Wilder's smoothing.
    """
    if len(close) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"RSI period must be positive: {period}")

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Boundary cleanups
    rsi = rsi.fillna(100.0)
    rsi.loc[(avg_gain == 0.0) & (avg_loss == 0.0)] = 50.0
    rsi.loc[(avg_gain == 0.0) & (avg_loss > 0.0)] = 0.0
    return rsi


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculates ADX, +DI, and -DI using Wilder's smoothing.
    Returns: (adx, plus_di, minus_di)
    """
    if len(close) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty
    if period <= 0:
        raise ValueError(f"ADX period must be positive: {period}")

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0), index=low.index)

    tr = calculate_tr(high, low, close)
    smooth_tr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_plus_dm = plus_dm.ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_minus_dm = minus_dm.ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * (smooth_plus_dm / smooth_tr.replace(0.0, np.nan)).fillna(0.0)
    minus_di = 100.0 * (smooth_minus_dm / smooth_tr.replace(0.0, np.nan)).fillna(0.0)

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100.0 * (di_diff / di_sum.replace(0.0, np.nan)).fillna(0.0)

    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def calculate_bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.5
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculates Bollinger Bands: (upper, middle, lower).
    """
    if len(close) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = mid + (num_std * std)
    lower = mid - (num_std * std)
    return upper, mid, lower


def calculate_relative_strength(
    stock_close: pd.Series,
    benchmark_close: Optional[pd.Series] = None,
    window: int = 20,
) -> pd.Series:
    """
    Calculates Relative Strength over a rolling window.
    If benchmark is provided, returns: stock_return - benchmark_return.
    If benchmark is None, returns the stock's own rolling return (absolute momentum).
    """
    if len(stock_close) == 0:
        return pd.Series(dtype=float)
    stock_ret = (stock_close - stock_close.shift(window)) / stock_close.shift(window).replace(0.0, np.nan)
    if benchmark_close is not None and len(benchmark_close) == len(stock_close):
        bench_ret = (benchmark_close - benchmark_close.shift(window)) / benchmark_close.shift(window).replace(0.0, np.nan)
        return stock_ret - bench_ret
    return stock_ret


def calculate_dtp_indicators(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    config: Optional[DTPV1Config] = None,
) -> pd.DataFrame:
    """
    Calculates the complete suite of technical indicators required for DTP-V1.
    Expects df with columns: ['open', 'high', 'low', 'close', 'volume'].
    Returns a copy of df augmented with:
      - ema_fast, ema_slow, sma_trend
      - atr, rsi, adx, plus_di, minus_di
      - volume_sma, rvol
      - bb_upper, bb_mid, bb_lower
      - relative_strength
      - swing_high_20, swing_low_20
    """
    if config is None:
        config = DTPV1Config()

    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(c.lower() for c in df.columns)
    if missing:
        raise ValueError(f"Input DataFrame missing required OHLCV columns: {missing}")

    res = df.copy()
    # Normalize column names to lowercase
    res.columns = [c.lower() for c in res.columns]

    close = res["close"]
    high = res["high"]
    low = res["low"]
    volume = res["volume"]

    # Moving Averages
    res["ema_fast"] = calculate_ema(close, config.ema_fast_period)
    res["ema_slow"] = calculate_ema(close, config.ema_slow_period)
    res["sma_trend"] = calculate_sma(close, config.sma_trend_period)

    # Volatility & Momentum
    res["atr"] = calculate_atr(high, low, close, config.atr_period)
    res["rsi"] = calculate_rsi(close, config.rsi_period)
    adx, plus_di, minus_di = calculate_adx(high, low, close, config.adx_period)
    res["adx"] = adx
    res["plus_di"] = plus_di
    res["minus_di"] = minus_di

    # Volume & RVOL
    res["volume_sma"] = calculate_sma(volume, config.volume_sma_period)
    prev_vol_sma = res["volume_sma"].shift(1)
    res["rvol"] = volume / prev_vol_sma.replace(0.0, np.nan)

    # Bollinger Bands
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close, config.bb_period, config.bb_std_mult)
    res["bb_upper"] = bb_upper
    res["bb_mid"] = bb_mid
    res["bb_lower"] = bb_lower

    # Relative Strength
    bench_close = benchmark_df["close"] if benchmark_df is not None and "close" in benchmark_df.columns else None
    res["relative_strength"] = calculate_relative_strength(close, bench_close, config.relative_strength_window)

    # 20-day Swing High / Low (causal shift(1) so current day is excluded from historical swing)
    res["swing_high_20"] = high.shift(1).rolling(window=20).max()
    res["swing_low_20"] = low.shift(1).rolling(window=20).min()

    return res

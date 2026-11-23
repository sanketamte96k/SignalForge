"""
SignalForge — Phase 32I: DTP-V3 Causal Indicators
===================================================
File: src/strategy/dtp_v3/indicators.py

Computes deterministic, strictly causal daily technical indicators for DTP-V3:
  - 20-day and 50-day Exponential Moving Averages (EMA)
  - 200-day Simple Moving Average (SMA)
  - 14-day Average True Range (ATR) with Wilder's smoothing
  - 14-day Relative Strength Index (RSI) with Wilder's smoothing
  - 14-day Average Directional Index (ADX, +DI, -DI) with Wilder's smoothing
  - 20-day Volume SMA and Relative Volume (RVOL)
  - 20-day / 2.5-std Bollinger Bands
  - 20-day Relative Strength versus benchmark
  - 20-day Rolling Swing Highs and Lows
  - 14-day Choppiness Index (CI) for sideways/whipsaw regime identification

All calculations operate strictly on completed historical bars without look-ahead.
"""

from __future__ import annotations

from typing import Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.dtp_v3.config import DTPV3Config


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
    """Calculates Average True Range (ATR) using Wilder's smoothing (alpha = 1 / period)."""
    if len(close) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"ATR period must be positive: {period}")
    tr = calculate_tr(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI) using Wilder's smoothing."""
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

    rsi = rsi.fillna(100.0)
    rsi.loc[(avg_gain == 0.0) & (avg_loss == 0.0)] = 50.0
    rsi.loc[(avg_gain == 0.0) & (avg_loss > 0.0)] = 0.0
    return rsi


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Directional Movement Index (+DI, -DI) and ADX using Wilder's smoothing."""
    if len(close) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty

    atr = calculate_atr(high, low, close, period=period)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)

    p_dm_series = pd.Series(plus_dm, index=high.index)
    m_dm_series = pd.Series(minus_dm, index=high.index)

    smoothed_p_dm = p_dm_series.ewm(alpha=1.0 / period, adjust=False).mean()
    smoothed_m_dm = m_dm_series.ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * (smoothed_p_dm / atr.replace(0.0, np.nan))
    minus_di = 100.0 * (smoothed_m_dm / atr.replace(0.0, np.nan))

    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * ((plus_di - minus_di).abs() / di_sum)
    dx = dx.fillna(0.0)

    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx, plus_di.fillna(0.0), minus_di.fillna(0.0)


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.5
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Bollinger Bands: (Middle, Upper, Lower)."""
    if len(series) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    return middle, upper, lower


def calculate_choppiness_index(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """
    Calculates Choppiness Index (CI) using standard definition:
      CI = 100 * LOG10( SUM(TrueRange, period) / (MaxHigh(period) - MinLow(period)) ) / LOG10(period)
    Values:
      > 61.8 (or > 60.0): Market is consolidating / sideways chop.
      < 38.2: Market is trending.
    """
    if len(close) == 0:
        return pd.Series(dtype=float)
    if period <= 1:
        raise ValueError("Choppiness period must be > 1")

    tr = calculate_tr(high, low, close)
    sum_tr = tr.rolling(window=period).sum()
    max_hi = high.rolling(window=period).max()
    min_lo = low.rolling(window=period).min()
    range_hl = (max_hi - min_lo).replace(0.0, np.nan)

    ci = 100.0 * np.log10(sum_tr / range_hl) / np.log10(period)
    return ci.fillna(50.0)


def calculate_dtp_indicators(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    config: Optional[DTPV3Config] = None,
) -> pd.DataFrame:
    """
    Computes all causal indicators for DTP-V3 and attaches them as columns:
      - ema_fast, ema_slow, sma_trend
      - tr, atr, rsi, adx, plus_di, minus_di
      - volume_sma, rvol
      - bb_middle, bb_upper, bb_lower
      - relative_strength
      - swing_high_20, swing_low_20
      - chop_index
    """
    if config is None:
        config = DTPV3Config()

    df_out = df.copy()
    c = df_out["close"]
    h = df_out["high"]
    l = df_out["low"]
    v = df_out["volume"]

    df_out["ema_fast"] = calculate_ema(c, config.ema_fast_period)
    df_out["ema_slow"] = calculate_ema(c, config.ema_slow_period)
    df_out["sma_trend"] = calculate_sma(c, config.sma_trend_period)

    df_out["tr"] = calculate_tr(h, l, c)
    df_out["atr"] = calculate_atr(h, l, c, config.atr_period)

    df_out["rsi"] = calculate_rsi(c, config.rsi_period)

    adx, p_di, m_di = calculate_adx(h, l, c, config.adx_period)
    df_out["adx"] = adx
    df_out["plus_di"] = p_di
    df_out["minus_di"] = m_di

    df_out["volume_sma"] = calculate_sma(v, config.volume_sma_period)
    vol_sma_safe = df_out["volume_sma"].replace(0.0, np.nan)
    df_out["rvol"] = (v / vol_sma_safe).fillna(1.0)

    bb_mid, bb_hi, bb_lo = calculate_bollinger_bands(
        c, period=config.bb_period, num_std=config.bb_std_mult
    )
    df_out["bb_middle"] = bb_mid
    df_out["bb_upper"] = bb_hi
    df_out["bb_lower"] = bb_lo

    df_out["swing_high_20"] = h.rolling(window=20).max()
    df_out["swing_low_20"] = l.rolling(window=20).min()

    # Choppiness Index
    df_out["chop_index"] = calculate_choppiness_index(h, l, c, period=config.choppiness_period)

    # Relative strength vs benchmark or rolling return
    if benchmark_df is not None and "close" in benchmark_df.columns:
        stock_ret = c.pct_change(periods=config.relative_strength_window).fillna(0.0)
        bm_ret = benchmark_df["close"].pct_change(periods=config.relative_strength_window).fillna(0.0)
        df_out["relative_strength"] = stock_ret - bm_ret
    else:
        df_out["relative_strength"] = c.pct_change(periods=config.relative_strength_window).fillna(0.0)

    return df_out

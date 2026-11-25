"""
SignalForge — Phase 33A: Technical Indicators & Data Validation
===============================================================
File: src/strategy/strategy_research_lab/indicators.py

Computes deterministic, strictly lookahead-free technical indicators:
  - SMA (20, 50, 100, 200)
  - EMA (20, 50)
  - ATR (14) with Wilder's smoothing
  - RSI (14) with Wilder's smoothing
  - Bollinger Bands (20, 2.0 std) and Bollinger Band Width percentile (120 lookback)
  - Donchian Channels (20-day high, 10-day low)
  - Trailing 20-day Volume SMA
  - Trailing 60-day Returns and Cross-Sectional Percentile Ranking across the 91-stock universe
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def validate_ohlc_invariants(df: pd.DataFrame, symbol: str) -> None:
    """Validates basic OHLCV structural integrity."""
    if df.empty:
        raise ValueError(f"Empty dataframe for symbol {symbol}")
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Symbol {symbol} missing columns: {missing}")

    # Check non-negative prices and volume
    if (df["open"] <= 0).any() or (df["high"] <= 0).any() or (df["low"] <= 0).any() or (df["close"] <= 0).any():
        raise ValueError(f"Symbol {symbol} contains non-positive price records")
    if (df["volume"] < 0).any():
        raise ValueError(f"Symbol {symbol} contains negative volume records")

    # Invariants: High >= Open, High >= Close, High >= Low, Low <= Open, Low <= Close
    invalid_high = (df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])
    if invalid_high.any():
        raise ValueError(f"Symbol {symbol} has {invalid_high.sum()} invalid High price bars")

    invalid_low = (df["low"] > df["open"]) | (df["low"] > df["close"])
    if invalid_low.any():
        raise ValueError(f"Symbol {symbol} has {invalid_low.sum()} invalid Low price bars")


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average over rolling period."""
    if len(series) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"SMA period must be positive: {period}")
    return series.rolling(window=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average with alpha = 2 / (period + 1)."""
    if len(series) == 0:
        return pd.Series(dtype=float)
    if period <= 0:
        raise ValueError(f"EMA period must be positive: {period}")
    return series.ewm(span=period, adjust=False).mean()


def calculate_tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculates True Range (TR) across high, low, and prior close."""
    if len(close) == 0:
        return pd.Series(dtype=float)
    prev_close = close.shift(1)
    hl = high - low
    hc = (high - prev_close).abs()
    lc = (low - prev_close).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


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
    return rsi.fillna(50.0)


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculates Bollinger Bands: (Middle, Upper, Lower, Bandwidth).
    Bandwidth = (Upper - Lower) / Middle
    """
    if len(series) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    bandwidth = (upper - lower) / middle.replace(0.0, np.nan)
    return middle, upper, lower, bandwidth


def calculate_rolling_percentile_rank(series: pd.Series, window: int = 120) -> pd.Series:
    """
    Causal rolling percentile rank of current bar's value relative to trailing window.
    Returns value in [0.0, 1.0].
    """
    vals = series.values
    n = len(vals)
    ranks = np.full(n, np.nan)
    for i in range(window - 1, n):
        win = vals[i - window + 1 : i + 1]
        valid = win[~np.isnan(win)]
        if len(valid) > 0:
            current = vals[i]
            if not np.isnan(current):
                ranks[i] = float(np.mean(valid <= current))
    return pd.Series(ranks, index=series.index)


def calculate_donchian_channels(
    high: pd.Series, low: pd.Series, high_period: int = 20, low_period: int = 10
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculates lookahead-free Donchian channel breakout and trailing levels:
      - donchian_high_20: max High of previous 20 sessions (shift 1).
      - donchian_low_10: min Low of previous 10 sessions (shift 1).
    """
    donchian_high = high.shift(1).rolling(window=high_period).max()
    donchian_low = low.shift(1).rolling(window=low_period).min()
    return donchian_high, donchian_low


def calculate_momentum_return(close: pd.Series, period: int = 60) -> pd.Series:
    """Calculates trailing n-session percentage return: Close[t] / Close[t - period] - 1.0."""
    return close / close.shift(period) - 1.0


def compute_cross_sectional_ranks(
    universe: Dict[str, pd.DataFrame], lookback: int = 60
) -> pd.DataFrame:
    """
    Computes daily cross-sectional percentile rankings across all symbols in the universe
    based strictly on trailing `lookback` return.
    Returns DataFrame indexed by date with symbols as columns, values in [0.0, 1.0].
    """
    returns_dict: Dict[str, pd.Series] = {}
    for sym, df in universe.items():
        ret = calculate_momentum_return(df["close"], period=lookback)
        returns_dict[sym] = ret

    df_returns = pd.DataFrame(returns_dict)
    # Cross-sectional percentile rank across columns for each row
    cs_ranks = df_returns.rank(axis=1, pct=True, ascending=True)
    return cs_ranks


def attach_all_indicators(
    df: pd.DataFrame,
    symbol: str,
    cs_rank_series: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Attaches all indicators required for Strategies 1 through 5 to a single stock's daily DataFrame.
    """
    validate_ohlc_invariants(df, symbol)
    out = df.copy()

    # Trend moving averages
    out["sma_200"] = calculate_sma(out["close"], 200)
    out["sma_50"] = calculate_sma(out["close"], 50)
    out["sma_20"] = calculate_sma(out["close"], 20)
    out["ema_20"] = calculate_ema(out["close"], 20)
    out["ema_50"] = calculate_ema(out["close"], 50)

    # Volatility and range
    out["tr"] = calculate_tr(out["high"], out["low"], out["close"])
    out["atr_14"] = calculate_atr(out["high"], out["low"], out["close"], period=14)

    # Momentum
    out["rsi_14"] = calculate_rsi(out["close"], period=14)

    # Bollinger Bands
    bb_mid, bb_up, bb_lo, bb_width = calculate_bollinger_bands(out["close"], period=20, num_std=2.0)
    out["bb_middle"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_lo
    out["bb_width"] = bb_width
    out["bb_width_pct_120"] = calculate_rolling_percentile_rank(out["bb_width"], window=120)

    # Donchian Breakout and Trailing Low
    dh_20, dl_10 = calculate_donchian_channels(out["high"], out["low"], high_period=20, low_period=10)
    out["donchian_high_20"] = dh_20
    out["donchian_low_10"] = dl_10

    # Volume SMA20
    out["volume_sma_20"] = out["volume"].shift(1).rolling(window=20).mean()

    # 60-day return
    out["return_60"] = calculate_momentum_return(out["close"], period=60)

    # Cross-sectional rank if provided
    if cs_rank_series is not None:
        out["cs_rank_percentile"] = cs_rank_series
    else:
        out["cs_rank_percentile"] = np.nan

    return out

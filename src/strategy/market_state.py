"""
SignalForge — Phase 6: Market State Engine
===========================================
File: src/strategy/market_state.py

Causal Market State classification engine evaluating every 1-minute candle
using strictly past and current information (no look-ahead).

States Classified:
1. TRENDING_UP: Strong bullish directional momentum and positive EMA structure.
2. TRENDING_DOWN: Strong bearish directional momentum and negative EMA structure.
3. RANGE: Low directional momentum and horizontal price action within boundaries.
4. HIGH_VOLATILITY: ATR in upper distribution (> 70th percentile).
5. LOW_VOLATILITY: ATR in lower distribution (< 30th percentile).
6. VOLATILITY_EXPANSION: Increasing ATR relative to baseline.
7. VOLATILITY_CONTRACTION: Contracting ATR relative to baseline.
"""

from __future__ import annotations

from typing import Dict, Any
import numpy as np
import pandas as pd


def compute_market_state_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all causal features needed for market state and setup detection.
    Preserves input index and column structure.
    """
    out = df.copy()

    close = out["Close"].to_numpy()
    high = out["High"].to_numpy()
    low = out["Low"].to_numpy()

    # 1. EMAs (9 and 21)
    out["ema9"] = out["Close"].ewm(span=9, adjust=False).mean()
    out["ema21"] = out["Close"].ewm(span=21, adjust=False).mean()
    out["ema50"] = out["Close"].ewm(span=50, adjust=False).mean()

    # EMA slopes & separation
    out["ema9_slope"] = out["ema9"].diff(5) / 5.0
    out["ema_spread"] = (out["ema9"] - out["ema21"]) / out["Close"]

    # 2. True Range & ATR(14)
    prev_close = out["Close"].shift(1).bfill()
    tr1 = out["High"] - out["Low"]
    tr2 = (out["High"] - prev_close).abs()
    tr3 = (out["Low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["tr"] = tr
    out["atr14"] = tr.ewm(span=14, adjust=False).mean()
    out["atr_sma50"] = out["atr14"].rolling(50, min_periods=10).mean().bfill()
    out["atr_ratio"] = out["atr14"] / out["atr_sma50"]

    # Rolling ATR percentile (100 candles)
    def rolling_pctile(series: pd.Series, window: int = 100) -> pd.Series:
        return series.rolling(window, min_periods=20).apply(
            lambda x: (pd.Series(x).rank(pct=True).iloc[-1] * 100.0) if len(x) > 0 else 50.0,
            raw=False
        ).bfill()

    out["atr_pctile"] = rolling_pctile(out["atr14"], window=100)

    # 3. Directional Movement Index (ADX 14)
    up_move = out["High"] - out["High"].shift(1)
    down_move = out["Low"].shift(1) - out["Low"]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_series = pd.Series(plus_dm, index=out.index)
    minus_dm_series = pd.Series(minus_dm, index=out.index)

    alpha = 1.0 / 14.0
    smooth_plus_dm = plus_dm_series.ewm(alpha=alpha, adjust=False).mean()
    smooth_minus_dm = minus_dm_series.ewm(alpha=alpha, adjust=False).mean()
    atr_smooth = tr.ewm(alpha=alpha, adjust=False).mean().replace(0, np.nan)

    plus_di = (smooth_plus_dm / atr_smooth) * 100.0
    minus_di = (smooth_minus_dm / atr_smooth) * 100.0
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / di_sum) * 100.0
    out["adx14"] = dx.ewm(alpha=alpha, adjust=False).mean().bfill().fillna(20.0)
    out["plus_di"] = plus_di.bfill().fillna(20.0)
    out["minus_di"] = minus_di.bfill().fillna(20.0)

    # 4. Rolling Range & Compression
    out["rolling_high_20"] = out["High"].rolling(20, min_periods=5).max()
    out["rolling_low_20"] = out["Low"].rolling(20, min_periods=5).min()
    out["rolling_range_20"] = out["rolling_high_20"] - out["rolling_low_20"]
    # Compression: rolling range relative to expected 20-candle ATR
    out["range_compression"] = out["rolling_range_20"] / (out["atr14"] * np.sqrt(20.0)).replace(0, np.nan)
    out["range_compression"] = out["range_compression"].bfill().fillna(1.0)

    # Price location in range: 0.0 (at low) to 1.0 (at high)
    range_span = out["rolling_range_20"].replace(0, np.nan)
    out["range_position"] = ((out["Close"] - out["rolling_low_20"]) / range_span).bfill().fillna(0.5)

    # Candle body / range
    candle_range = (out["High"] - out["Low"]).replace(0, np.nan)
    out["candle_body_ratio"] = (out["Close"] - out["Open"]).abs() / candle_range
    out["candle_body_ratio"] = out["candle_body_ratio"].bfill().fillna(0.5)

    return out


def classify_market_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifies the primary market state for each timestamp into:
    - TRENDING_UP
    - TRENDING_DOWN
    - RANGE
    - HIGH_VOLATILITY
    - LOW_VOLATILITY
    - VOLATILITY_EXPANSION
    - VOLATILITY_CONTRACTION
    """
    df_feat = compute_market_state_features(df)

    # Primary directional & structural state
    conditions_primary = [
        (df_feat["adx14"] >= 20.0) & (df_feat["ema9"] > df_feat["ema21"]) & (df_feat["ema9_slope"] > 0),
        (df_feat["adx14"] >= 20.0) & (df_feat["ema9"] < df_feat["ema21"]) & (df_feat["ema9_slope"] < 0),
        (df_feat["adx14"] < 20.0) & (df_feat["range_compression"] < 1.1),
        (df_feat["atr_pctile"] >= 70.0),
        (df_feat["atr_pctile"] <= 30.0),
        (df_feat["atr_ratio"] > 1.2) & (df_feat["atr14"] > df_feat["atr14"].shift(1)),
        (df_feat["atr_ratio"] < 0.8) & (df_feat["atr14"] < df_feat["atr14"].shift(1)),
    ]

    choices_primary = [
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "VOLATILITY_EXPANSION",
        "VOLATILITY_CONTRACTION",
    ]

    df_feat["market_state"] = np.select(conditions_primary, choices_primary, default="RANGE")

    # Flag secondary volatility states for multi-dimensional filtering
    df_feat["is_trending_up"] = (df_feat["ema9"] > df_feat["ema21"]) & (df_feat["ema9_slope"] > 0)
    df_feat["is_trending_down"] = (df_feat["ema9"] < df_feat["ema21"]) & (df_feat["ema9_slope"] < 0)
    df_feat["is_range"] = (df_feat["adx14"] < 22.0)
    df_feat["is_high_vol"] = (df_feat["atr_pctile"] >= 70.0)
    df_feat["is_low_vol"] = (df_feat["atr_pctile"] <= 30.0)
    df_feat["is_vol_expansion"] = (df_feat["atr_ratio"] > 1.1)
    df_feat["is_vol_contraction"] = (df_feat["atr_ratio"] < 0.9)

    return df_feat

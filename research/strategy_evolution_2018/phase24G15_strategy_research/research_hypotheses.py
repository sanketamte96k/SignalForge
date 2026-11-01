"""
SignalForge — Phase 24G.15: Quantitative Strategy Research & Signal Engine
==========================================================================
Implements causal, multi-timeframe indicator computation and four distinct
alternative strategy hypotheses:
  - Hypothesis A: Trend Pullback & Continuation (Anti-Chasing)
  - Hypothesis B: Volatility Compression & Breakout (Squeeze Expansion)
  - Hypothesis C: Regime-Filtered Mean Reversion
  - Hypothesis D: Regime-Adaptive Multi-Strategy (Trend vs Range Dispatch)

All signals use completed candles only and are executed at causal next_open.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dtime, timedelta
from enum import Enum
import math
from typing import Optional, Union

import numpy as np
import pandas as pd

from src.backtest.risk_engine_v2 import PositionSide
from src.data.resampler import resample_ohlcv


# ============================================================================
# 1. Technical Indicators (Vectorized & Causal)
# ============================================================================

def calc_ema(series: pd.Series, span: int) -> pd.Series:
    """Calculate exponential moving average."""
    return series.ewm(span=span, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def calc_rvol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Relative Volume (RVOL) against rolling average."""
    vol = df["volume"].astype(float)
    avg_vol = vol.rolling(window=period, min_periods=1).mean()
    rvol = vol / avg_vol.replace(0, np.nan)
    return rvol.fillna(1.0)


def calc_adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Welles Wilder's Directional Movement Index (ADX, +DI, -DI)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    plus_dm = high - prev_high
    minus_dm = prev_low - low

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_plus_dm = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_minus_dm = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * (smooth_plus_dm / atr.replace(0, np.nan))
    minus_di = 100.0 * (smooth_minus_dm / atr.replace(0, np.nan))

    di_diff = (plus_di - minus_di).abs()
    di_sum = plus_di + minus_di
    dx = 100.0 * (di_diff / di_sum.replace(0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


# ============================================================================
# 2. Multi-Timeframe Feature Matrix Builder
# ============================================================================

def build_multi_timeframe_features(df_1m: pd.DataFrame) -> dict:
    """
    Build complete set of higher timeframe causal features and synchronizers.
    All features on higher timeframes are computed on completed candles only.
    """
    df_raw = df_1m.copy()
    df_raw.columns = [c.lower() for c in df_raw.columns]

    # Resample to 5m, 15m, 30m
    tf_5m = resample_ohlcv(df_raw, "5m")
    tf_15m = resample_ohlcv(df_raw, "15m")
    tf_30m = resample_ohlcv(df_raw, "30m")

    # 1. 5m Features
    tf_5m["ema20"] = calc_ema(tf_5m["close"], 20)
    tf_5m["ema50"] = calc_ema(tf_5m["close"], 50)
    tf_5m["rsi"] = calc_rsi(tf_5m["close"], 14)
    tf_5m["atr"] = calc_atr(tf_5m, 14)
    tf_5m["rvol"] = calc_rvol(tf_5m, 20)

    # 20-bar Donchian channel
    tf_5m["donchian_high_20"] = tf_5m["high"].rolling(20).max()
    tf_5m["donchian_low_20"] = tf_5m["low"].rolling(20).min()

    # Bollinger Bands (20, 2.0 std)
    roll_mean = tf_5m["close"].rolling(20).mean()
    roll_std = tf_5m["close"].rolling(20).std()
    tf_5m["bb_upper"] = roll_mean + (2.0 * roll_std)
    tf_5m["bb_lower"] = roll_mean - (2.0 * roll_std)
    tf_5m["bb_width"] = (tf_5m["bb_upper"] - tf_5m["bb_lower"]) / roll_mean.replace(0, np.nan)

    # Keltner Channel (20, 1.5 ATR)
    tf_5m["kc_upper"] = tf_5m["ema20"] + (1.5 * tf_5m["atr"])
    tf_5m["kc_lower"] = tf_5m["ema20"] - (1.5 * tf_5m["atr"])

    # Squeeze: Bollinger Bands inside Keltner Channel
    tf_5m["in_squeeze"] = (tf_5m["bb_upper"] < tf_5m["kc_upper"]) & (tf_5m["bb_lower"] > tf_5m["kc_lower"])

    # ADX on 5m
    adx_5m, pdi_5m, mdi_5m = calc_adx(tf_5m, 14)
    tf_5m["adx"] = adx_5m
    tf_5m["pdi"] = pdi_5m
    tf_5m["mdi"] = mdi_5m

    # 2. 15m Features
    tf_15m["ema20"] = calc_ema(tf_15m["close"], 20)
    tf_15m["ema50"] = calc_ema(tf_15m["close"], 50)
    tf_15m["trend"] = np.where(tf_15m["ema20"] > tf_15m["ema50"], 1, np.where(tf_15m["ema20"] < tf_15m["ema50"], -1, 0))
    adx_15m, _, _ = calc_adx(tf_15m, 14)
    tf_15m["adx"] = adx_15m

    # 3. 30m Features
    tf_30m["ema20"] = calc_ema(tf_30m["close"], 20)
    tf_30m["ema50"] = calc_ema(tf_30m["close"], 50)
    tf_30m["trend"] = np.where(tf_30m["ema20"] > tf_30m["ema50"], 1, np.where(tf_30m["ema20"] < tf_30m["ema50"], -1, 0))
    adx_30m, _, _ = calc_adx(tf_30m, 14)
    tf_30m["adx"] = adx_30m
    tf_30m["ema_spread_pct"] = (tf_30m["ema20"] - tf_30m["ema50"]).abs() / tf_30m["close"] * 100.0

    return {
        "1m": df_raw,
        "5m": tf_5m,
        "15m": tf_15m,
        "30m": tf_30m,
    }


# ============================================================================
# 3. Alternative Strategy Hypotheses
# ============================================================================

class MarketRegime(str, Enum):
    STRONG_TREND = "STRONG_TREND"
    RANGING_COMPRESSION = "RANGING_COMPRESSION"
    VOLATILE_CHAOS = "VOLATILE_CHAOS"
    NEUTRAL = "NEUTRAL"


def classify_market_regime(
    ts: pd.Timestamp,
    s5: pd.Series,
    s15: pd.Series,
    s30: pd.Series,
) -> MarketRegime:
    """Classify current intraday market condition into one of 4 discrete regimes."""
    t = ts.time()
    # 1. Opening Chaos Window (09:15 to 09:35)
    if t < dtime(9, 35):
        return MarketRegime.VOLATILE_CHAOS

    # 2. Strong Trend Regime: 30m ADX > 25 and 15m/30m trends aligned with significant EMA spread
    if s30["adx"] >= 25.0 and s15["trend"] == s30["trend"] and s30["trend"] != 0 and s30["ema_spread_pct"] >= 0.15:
        return MarketRegime.STRONG_TREND

    # 3. Ranging / Compression Regime: 30m ADX < 20 and 5m in squeeze or low BB width
    if s30["adx"] <= 20.0 and (s5.get("in_squeeze", False) or s5["bb_width"] < 0.008):
        return MarketRegime.RANGING_COMPRESSION

    return MarketRegime.NEUTRAL


def generate_hypothesis_signals(
    features: dict,
    hypothesis: str,
) -> pd.Series:
    """
    Generate causal 1-minute signals vector for a specific research hypothesis.
    Completed candle at timestamp t gives signal for next bar execution.
    """
    df_1m = features["1m"]
    tf_5m = features["5m"]
    tf_15m = features["15m"]
    tf_30m = features["30m"]

    # Align higher timeframe completed bars to 1m index causally
    # A 5m candle ending at 09:20 is completed at 09:20:00 (available at 09:20:00 for 09:21:00 next open fill)
    idx_5m = tf_5m.index
    idx_15m = tf_15m.index
    idx_30m = tf_30m.index

    # Pre-index for causal lookup
    s5_df = tf_5m.reindex(df_1m.index, method="ffill")
    s15_df = tf_15m.reindex(df_1m.index, method="ffill")
    s30_df = tf_30m.reindex(df_1m.index, method="ffill")

    signals: list[Optional[PositionSide]] = []
    last_exit_bar = -9999

    n_bars = len(df_1m)
    datetimes = df_1m.index

    for i in range(n_bars):
        cur_ts = datetimes[i]
        t = cur_ts.time()

        # No trading in final 15 minutes of day
        if t >= dtime(15, 15):
            signals.append(None)
            continue

        s5 = s5_df.iloc[i]
        s15 = s15_df.iloc[i]
        s30 = s30_df.iloc[i]

        # Ensure warm-up data exists
        if pd.isna(s5["ema50"]) or pd.isna(s15["ema50"]) or pd.isna(s30["ema50"]):
            signals.append(None)
            continue

        # Signal evaluation can only occur on 5-minute bar boundaries (when a 5m bar just closed)
        # 5m bar completes at minute % 5 == 0
        if cur_ts.minute % 5 != 0:
            signals.append(None)
            continue

        sig: Optional[PositionSide] = None

        # --------------------------------------------------------------------
        # HYPOTHESIS A: Trend Pullback & Continuation (Anti-Chasing)
        # --------------------------------------------------------------------
        if hypothesis == "HYPOTHESIS_A_TREND_PULLBACK":
            # Macro trend: 15m and 30m EMAs in bullish alignment
            macro_bull = (s15["trend"] == 1) and (s30["trend"] == 1)
            macro_bear = (s15["trend"] == -1) and (s30["trend"] == -1)

            # 5m Pullback into value zone:
            # For LONG: Close pulled back near EMA20, RSI reset to 42–58 (not overbought!), green candle close
            c5 = s5["close"]
            o5 = s5["open"]
            ema20 = s5["ema20"]
            ema50 = s5["ema50"]
            atr5 = s5["atr"]
            rsi5 = s5["rsi"]

            dist_ema = abs(c5 - ema20)

            if macro_bull:
                # Price is above EMA50, pulled back near EMA20, RSI in healthy pullback zone (42–56), candle is bullish
                if (c5 >= ema20 * 0.998) and (c5 <= ema20 + (0.5 * atr5)) and (42.0 <= rsi5 <= 56.0) and (c5 > o5):
                    sig = PositionSide.LONG
            elif macro_bear:
                if (c5 <= ema20 * 1.002) and (c5 >= ema20 - (0.5 * atr5)) and (44.0 <= rsi5 <= 58.0) and (c5 < o5):
                    sig = PositionSide.SHORT

        # --------------------------------------------------------------------
        # HYPOTHESIS B: Volatility Compression & Breakout (Squeeze Expansion)
        # --------------------------------------------------------------------
        elif hypothesis == "HYPOTHESIS_B_VOLATILITY_BREAKOUT":
            # Require compression on 5m (Bollinger Band squeeze or low bandwidth)
            is_compressed = s5["in_squeeze"] or (s5["bb_width"] < 0.009)
            rvol5 = s5["rvol"]
            c5 = s5["close"]
            dh = s5["donchian_high_20"]
            dl = s5["donchian_low_20"]
            atr5 = s5["atr"]

            # Breakout with volume confirmation and macro trend alignment
            if is_compressed and rvol5 >= 1.5:
                # Long breakout above 20-bar Donchian high
                if (c5 >= dh) and (s30["trend"] >= 0) and (c5 - s5["open"] <= 2.0 * atr5):
                    sig = PositionSide.LONG
                # Short breakout below 20-bar Donchian low
                elif (c5 <= dl) and (s30["trend"] <= 0) and (s5["open"] - c5 <= 2.0 * atr5):
                    sig = PositionSide.SHORT

        # --------------------------------------------------------------------
        # HYPOTHESIS C: Regime-Filtered Mean Reversion
        # --------------------------------------------------------------------
        elif hypothesis == "HYPOTHESIS_C_MEAN_REVERSION":
            # Only trade when macro market is RANGING (30m ADX < 20 and low EMA separation)
            macro_ranging = (s30["adx"] <= 20.0) and (s30["ema_spread_pct"] <= 0.12)
            c5 = s5["close"]
            o5 = s5["open"]
            bbu = s5["bb_upper"]
            bbl = s5["bb_lower"]
            rsi5 = s5["rsi"]

            if macro_ranging:
                # Oversold bounce: pierced lower band, closed back up with green candle, RSI < 32
                if (s5["low"] <= bbl) and (c5 > o5) and (rsi5 <= 35.0):
                    sig = PositionSide.LONG
                # Overbought rejection: pierced upper band, closed back down with red candle, RSI > 68
                elif (s5["high"] >= bbu) and (c5 < o5) and (rsi5 >= 65.0):
                    sig = PositionSide.SHORT

        # --------------------------------------------------------------------
        # HYPOTHESIS D: Regime-Adaptive Multi-Strategy
        # --------------------------------------------------------------------
        elif hypothesis == "HYPOTHESIS_D_REGIME_ADAPTIVE":
            regime = classify_market_regime(cur_ts, s5, s15, s30)

            # In Strong Trend: Execute Trend Pullback ONLY
            if regime == MarketRegime.STRONG_TREND:
                c5 = s5["close"]
                o5 = s5["open"]
                ema20 = s5["ema20"]
                atr5 = s5["atr"]
                rsi5 = s5["rsi"]
                macro_bull = s30["trend"] == 1
                macro_bear = s30["trend"] == -1

                if macro_bull and (c5 >= ema20 * 0.998) and (c5 <= ema20 + (0.5 * atr5)) and (42.0 <= rsi5 <= 58.0) and (c5 > o5):
                    sig = PositionSide.LONG
                elif macro_bear and (c5 <= ema20 * 1.002) and (c5 >= ema20 - (0.5 * atr5)) and (42.0 <= rsi5 <= 58.0) and (c5 < o5):
                    sig = PositionSide.SHORT

            # In Ranging / Compression: Execute Mean Reversion ONLY
            elif regime == MarketRegime.RANGING_COMPRESSION:
                c5 = s5["close"]
                o5 = s5["open"]
                bbu = s5["bb_upper"]
                bbl = s5["bb_lower"]
                rsi5 = s5["rsi"]

                if (s5["low"] <= bbl) and (c5 > o5) and (rsi5 <= 35.0):
                    sig = PositionSide.LONG
                elif (s5["high"] >= bbu) and (c5 < o5) and (rsi5 >= 65.0):
                    sig = PositionSide.SHORT

            # In Volatile Chaos / Opening Window: Stand completely aside (sig remains None)

        signals.append(sig)

    return pd.Series(signals, index=df_1m.index)


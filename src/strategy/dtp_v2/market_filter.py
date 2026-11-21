"""
SignalForge — Phase 32E.1: DTP-V2 Market Regime Filter
======================================================
File: src/strategy/dtp_v2/market_filter.py

Implements broader market regime assessment for DTP-V2 delivery swing trading:
  1. Primary Market Filter: NIFTY 50 daily trend confirmation (EMA50 slope and SMA200 alignment).
  2. Standalone Fallback: Universe Breadth Index (UBI) computed across approved universe stocks.
  3. Failsafe handling for missing or unverified market data.

Preserves exact parity with DTP-V1.
All regime evaluations use strictly causal, completed daily bars.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v2.config import DTPRegimeState, DTPV2Config


def evaluate_nifty_regime(
    nifty_df: pd.DataFrame,
    config: Optional[DTPV2Config] = None,
    bar_idx: int = -1,
) -> Tuple[DTPRegimeState, str]:
    """
    Evaluates the broader market regime using NIFTY 50 daily OHLCV dataframe.
    Expects nifty_df with columns ['close', 'ema_fast', 'ema_slow', 'sma_trend'] or computes them.

    Rules:
      - BULLISH: Close > EMA50 AND EMA50 > EMA50[5 days ago]
      - NEUTRAL: Close <= EMA50 AND Close > SMA200 (or EMA20 > EMA50)
      - BEARISH: Close < SMA200 OR (EMA20 < EMA50 < SMA200)
    """
    if config is None:
        config = DTPV2Config()

    if nifty_df is None or len(nifty_df) < config.ema_slow_period:
        return DTPRegimeState.UNKNOWN, "Insufficient NIFTY 50 history (<50 bars)"

    df = nifty_df.copy()
    if "ema_slow" not in df.columns:
        df["ema_slow"] = df["close"].ewm(span=config.ema_slow_period, adjust=False).mean()
    if "ema_fast" not in df.columns:
        df["ema_fast"] = df["close"].ewm(span=config.ema_fast_period, adjust=False).mean()
    if "sma_trend" not in df.columns:
        df["sma_trend"] = df["close"].rolling(window=config.sma_trend_period).mean()

    n_rows = len(df)
    target_idx = bar_idx if bar_idx >= 0 else n_rows + bar_idx
    if target_idx < 0 or target_idx >= n_rows:
        return DTPRegimeState.UNKNOWN, f"Bar index {bar_idx} out of range [0, {n_rows})"

    c = df["close"].iloc[target_idx]
    ema50 = df["ema_slow"].iloc[target_idx]
    ema20 = df["ema_fast"].iloc[target_idx]
    sma200 = df["sma_trend"].iloc[target_idx]

    slope_idx = max(0, target_idx - 5)
    ema50_5d_ago = df["ema_slow"].iloc[slope_idx]
    ema50_sloping_up = ema50 > ema50_5d_ago

    # Check BEARISH regime first
    if pd.notna(sma200):
        if c < sma200 or (ema20 < ema50 and ema50 < sma200):
            return DTPRegimeState.BEARISH, f"NIFTY below SMA200 (Close={c:.2f}, SMA200={sma200:.2f})"
    else:
        if c < ema50 and ema20 < ema50 and not ema50_sloping_up:
            return DTPRegimeState.BEARISH, f"NIFTY in severe intermediate downtrend (Close={c:.2f} < EMA50={ema50:.2f})"

    # Check BULLISH regime
    if c > ema50 and ema50_sloping_up:
        return DTPRegimeState.BULLISH, f"NIFTY in confirmed uptrend (Close={c:.2f} > EMA50={ema50:.2f}, rising)"

    # NEUTRAL regime
    return DTPRegimeState.NEUTRAL, f"NIFTY consolidating (Close={c:.2f}, EMA50={ema50:.2f})"


def evaluate_breadth_regime(
    universe_dfs: Dict[str, pd.DataFrame],
    config: Optional[DTPV2Config] = None,
    bar_idx: int = -1,
) -> Tuple[DTPRegimeState, str]:
    """
    Evaluates broader market regime using the Universe Breadth Index (UBI).
    Computes the fraction of approved universe stocks trading above their 50-day EMA.

    Rules:
      - BULLISH: Breadth ratio >= 2/3 (at least 66.7% of stocks above EMA50)
      - BEARISH: Breadth ratio <= 1/3 (at most 33.3% of stocks above EMA50)
      - NEUTRAL: 1/3 < Breadth ratio < 2/3
    """
    if config is None:
        config = DTPV2Config()

    if not universe_dfs:
        return DTPRegimeState.UNKNOWN, "Empty universe data dictionary"

    above_count = 0
    valid_count = 0

    for symbol, df in universe_dfs.items():
        if df is None or len(df) < config.ema_slow_period:
            continue

        n_rows = len(df)
        target_idx = bar_idx if bar_idx >= 0 else n_rows + bar_idx
        if target_idx < 0 or target_idx >= n_rows:
            continue

        c = df["close"].iloc[target_idx]
        if "ema_slow" in df.columns:
            ema50 = df["ema_slow"].iloc[target_idx]
        else:
            ema50 = df["close"].ewm(span=config.ema_slow_period, adjust=False).mean().iloc[target_idx]

        valid_count += 1
        if c > ema50:
            above_count += 1

    if valid_count == 0:
        return DTPRegimeState.UNKNOWN, "No valid universe symbols with sufficient history"

    breadth_ratio = above_count / valid_count

    if breadth_ratio >= (2.0 / 3.0):
        return DTPRegimeState.BULLISH, f"Universe Breadth Bullish ({above_count}/{valid_count} = {breadth_ratio:.1%})"
    elif breadth_ratio <= (1.0 / 3.0):
        return DTPRegimeState.BEARISH, f"Universe Breadth Bearish ({above_count}/{valid_count} = {breadth_ratio:.1%})"
    else:
        return DTPRegimeState.NEUTRAL, f"Universe Breadth Neutral ({above_count}/{valid_count} = {breadth_ratio:.1%})"


def get_market_regime(
    nifty_df: Optional[pd.DataFrame] = None,
    universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
    config: Optional[DTPV2Config] = None,
    bar_idx: int = -1,
) -> Tuple[DTPRegimeState, str]:
    """
    Hierarchical market regime resolver:
      1. Tries primary NIFTY 50 trend confirmation.
      2. If NIFTY is unavailable, falls back cleanly to Universe Breadth Index.
      3. If neither is available, fails safely to UNKNOWN.
    """
    if config is None:
        config = DTPV2Config()

    if nifty_df is not None and len(nifty_df) >= config.ema_slow_period:
        state, reason = evaluate_nifty_regime(nifty_df, config, bar_idx)
        if state != DTPRegimeState.UNKNOWN:
            return state, f"Primary NIFTY 50: {reason}"

    if universe_dfs is not None and len(universe_dfs) > 0:
        state, reason = evaluate_breadth_regime(universe_dfs, config, bar_idx)
        return state, f"Fallback Breadth: {reason}"

    return DTPRegimeState.UNKNOWN, "No market data or universe data available for regime evaluation"

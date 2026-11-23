"""
SignalForge — Phase 32I: DTP-V3 Market Breadth & Regime Filter
==============================================================
File: src/strategy/dtp_v3/market_filter.py

Classifies broader market environment into BULLISH, NEUTRAL, or BEARISH
based on universe breadth (percentage of stocks above 50-day EMA and 200-day SMA).
"""

from __future__ import annotations

from typing import Dict, Optional
import pandas as pd

from src.strategy.dtp_v3.config import DTPRegimeState, DTPV3Config


def evaluate_breadth_regime(
    universe_dict: Dict[str, pd.DataFrame],
    bar_idx: int = -1,
    config: Optional[DTPV3Config] = None,
) -> DTPRegimeState:
    """
    Evaluates market regime across the approved universe at Bar T:
      - BULLISH: >= 60% of stocks above 50-day EMA and >= 50% above 200-day SMA.
      - BEARISH: < 40% of stocks above 50-day EMA.
      - NEUTRAL: All other intermediate conditions.
    """
    if config is None:
        config = DTPV3Config()

    if not universe_dict:
        return DTPRegimeState.UNKNOWN

    above_ema50_count = 0
    above_sma200_count = 0
    total_valid = 0

    for sym, df in universe_dict.items():
        if df.empty:
            continue
        n_rows = len(df)
        idx = bar_idx if bar_idx >= 0 else n_rows + bar_idx
        if idx < 0 or idx >= n_rows:
            continue

        row = df.iloc[idx]
        close = row["close"]
        ema50 = row.get("ema_slow", None)
        sma200 = row.get("sma_trend", None)

        if pd.notna(close) and pd.notna(ema50):
            total_valid += 1
            if close > ema50:
                above_ema50_count += 1
            if pd.notna(sma200) and close > sma200:
                above_sma200_count += 1

    if total_valid == 0:
        return DTPRegimeState.UNKNOWN

    pct_above_ema50 = above_ema50_count / total_valid
    pct_above_sma200 = above_sma200_count / total_valid

    if pct_above_ema50 >= 0.60 and pct_above_sma200 >= 0.50:
        return DTPRegimeState.BULLISH
    elif pct_above_ema50 < 0.40:
        return DTPRegimeState.BEARISH
    else:
        return DTPRegimeState.NEUTRAL

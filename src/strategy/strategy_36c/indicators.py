"""
SignalForge — Phase 36C: Quantitative Indicators & Regime Engine
================================================================
File: src/strategy/strategy_36c/indicators.py

Computes causal Nifty 50 macro regime metrics (SMA50, SMA200) and stock-level
ATR(14) indicators with strict zero lookahead bias.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd

from src.strategy.dtp_v3.indicators import calculate_atr


def load_nifty_regime_series(
    research_nifty_path: str = "data/historical/nifty50_1m_research.csv",
    canonical_nifty_path: str = "temp_nse_data/NSE Minute Data/NSE_Index_Data/NIFTY_50__EQ__INDICES__NSE__MINUTE.csv",
    start_date: date = date(2017, 1, 2),
    end_date: date = date(2019, 12, 31),
) -> pd.DataFrame:
    """
    Loads continuous daily Nifty 50 series with pre-2017 warmup to ensure
    unbroken, point-in-time SMA50 and SMA200 across 2017-2019.
    """
    p_res = Path(research_nifty_path)
    p_can = Path(canonical_nifty_path)

    if not p_res.exists():
        raise FileNotFoundError(f"Missing historical Nifty research file: {p_res}")
    if not p_can.exists():
        raise FileNotFoundError(f"Missing canonical Nifty file: {p_can}")

    # 1. Pre-2017 warmup
    df_res = pd.read_csv(p_res)
    df_res["dt"] = pd.to_datetime(df_res["timestamp"])
    df_res["date"] = df_res["dt"].dt.date
    daily_pre = (
        df_res[df_res["date"] < start_date]
        .groupby("date")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    )
    daily_pre.columns = ["open", "high", "low", "close"]

    # 2. Study period (2017-2019)
    df_idx = pd.read_csv(p_can)
    df_idx["dt"] = pd.to_datetime(df_idx["timestamp"])
    df_idx["date"] = df_idx["dt"].dt.date
    daily_main = (
        df_idx[(df_idx["date"] >= start_date) & (df_idx["date"] <= end_date)]
        .groupby("date")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    )

    combined = pd.concat([daily_pre, daily_main]).sort_index()

    # Causal SMAs
    combined["sma50"] = combined["close"].rolling(window=50).mean()
    combined["sma200"] = combined["close"].rolling(window=200).mean()

    # Bull regime: close > sma200 AND sma50 > sma200
    combined["is_bull_regime"] = (
        (combined["close"] > combined["sma200"]) &
        (combined["sma50"] > combined["sma200"])
    )

    # Return only study period (2017-2019)
    study_nifty = combined.loc[daily_main.index].copy()
    return study_nifty


def compute_stock_atr_dict(
    universe: Dict[str, pd.DataFrame],
    period: int = 14,
) -> Dict[str, pd.Series]:
    """
    Computes Wilder's ATR(14) series for each stock in the universe.
    """
    atr_dict: Dict[str, pd.Series] = {}
    for sym, df in universe.items():
        atr_series = calculate_atr(df["high"], df["low"], df["close"], period=period)
        atr_dict[sym] = atr_series
    return atr_dict

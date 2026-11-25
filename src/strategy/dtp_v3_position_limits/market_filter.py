"""
SignalForge — Phase 32J.5: Nifty Proximity & Dynamic Limit Engine
=================================================================
File: src/strategy/dtp_v3_position_limits/market_filter.py

Evaluates Nifty 50 proximity to 100-day SMA and calculates dynamic position limits:
  - Zones:
      * NORMAL: Nifty > 2% above 100-day SMA (dist > 0.02)
      * CAUTION: Nifty between 0% and 2% above 100-day SMA (0.0 <= dist <= 0.02)
      * WEAK: Nifty below 100-day SMA (dist < 0.0)
  - Dynamic Position Limits:
      * B1: Normal -> 3, Caution -> 2, Weak -> 1
      * B2: Normal -> 3, Caution -> 1, Weak -> 1
      * B3: Normal -> 3, Caution -> 2, Weak -> 0
  - Causal execution: zero look-ahead, historical warm-up from 2015-2016.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3_position_limits.config import (
    DynamicLimitMode,
    FixedLimitMode,
    MarketZone,
)


class NiftyPositionLimitsFilter:
    """
    Evaluates Nifty 50 trend, proximity to 100-day SMA, and determines
    active concurrent position limits and risk discounts.
    """

    def __init__(
        self,
        research_nifty_path: str = "data/historical/nifty50_1m_research.csv",
        canonical_nifty_path: str = "temp_nse_data/NSE Minute Data/NSE_Index_Data/NIFTY_50__EQ__INDICES__NSE__MINUTE.csv",
    ) -> None:
        self.research_nifty_path = Path(research_nifty_path)
        self.canonical_nifty_path = Path(canonical_nifty_path)
        self._daily_nifty: Optional[pd.DataFrame] = None
        self._load_and_compute()

    def _load_and_compute(self) -> None:
        """Loads and builds continuous daily Nifty 50 dataframe."""
        if not self.research_nifty_path.exists():
            raise FileNotFoundError(f"Missing historical Nifty research file: {self.research_nifty_path}")
        df_res = pd.read_csv(self.research_nifty_path)
        df_res["dt"] = pd.to_datetime(df_res["timestamp"])
        df_res["date"] = df_res["dt"].dt.date
        daily_pre = df_res[df_res["date"] < date(2017, 1, 2)].groupby("date").agg({"Close": "last"})
        daily_pre.columns = ["close"]

        if not self.canonical_nifty_path.exists():
            raise FileNotFoundError(f"Missing canonical Nifty file: {self.canonical_nifty_path}")
        df_idx = pd.read_csv(self.canonical_nifty_path)
        df_idx["dt"] = pd.to_datetime(df_idx["timestamp"])
        df_idx["date"] = df_idx["dt"].dt.date
        daily_main = (
            df_idx[(df_idx["date"] >= date(2017, 1, 2)) & (df_idx["date"] <= date(2019, 12, 31))]
            .groupby("date")
            .agg({"close": "last"})
        )

        combined = pd.concat([daily_pre, daily_main]).sort_index()
        combined["sma100"] = combined["close"].rolling(window=100).mean()
        self._daily_nifty = combined.loc[daily_main.index].copy()

    def evaluate_market_zone(self, decision_date: date) -> Tuple[MarketZone, float, float, float]:
        """
        Determines the market zone: (zone, close, sma100, dist_pct).
        dist_pct = (close - sma100) / sma100.
        """
        if self._daily_nifty is None:
            raise RuntimeError("NiftyPositionLimitsFilter data not initialized.")

        if decision_date not in self._daily_nifty.index:
            raise KeyError(f"Date {decision_date} not in Nifty 50 calendar")

        row = self._daily_nifty.loc[decision_date]
        close = float(row["close"])
        sma100 = float(row["sma100"])
        dist_pct = (close - sma100) / sma100

        if dist_pct > 0.02:
            zone = MarketZone.NORMAL
        elif dist_pct >= 0.0:
            zone = MarketZone.CAUTION
        else:
            zone = MarketZone.WEAK

        return zone, close, sma100, dist_pct

    def get_active_position_limit(
        self,
        decision_date: date,
        dynamic_mode: DynamicLimitMode = DynamicLimitMode.NONE,
        fixed_limit: FixedLimitMode = FixedLimitMode.A1_MAX_3,
    ) -> Tuple[int, MarketZone, float, str]:
        """
        Calculates active concurrent position limit for new entries:
          - If dynamic_mode == NONE: returns fixed_limit (3, 2, or 1).
          - If dynamic_mode in [B1, B2, B3]: returns dynamic limit based on market zone.
        Returns: (position_limit, zone, dist_pct, audit_msg).
        """
        zone, close, sma100, dist_pct = self.evaluate_market_zone(decision_date)

        if dynamic_mode == DynamicLimitMode.NONE:
            limit = int(fixed_limit.value)
            msg = f"Fixed Limit: max {limit} positions (Zone: {zone.value}, dist: {dist_pct*100:.2f}%)"
            return limit, zone, dist_pct, msg

        elif dynamic_mode == DynamicLimitMode.B1:
            if zone == MarketZone.NORMAL:
                limit = 3
            elif zone == MarketZone.CAUTION:
                limit = 2
            else:  # WEAK
                limit = 1
            msg = f"Dynamic B1: Zone {zone.value} (dist: {dist_pct*100:.2f}%) -> max {limit} positions"
            return limit, zone, dist_pct, msg

        elif dynamic_mode == DynamicLimitMode.B2:
            if zone == MarketZone.NORMAL:
                limit = 3
            elif zone == MarketZone.CAUTION:
                limit = 1
            else:  # WEAK
                limit = 1
            msg = f"Dynamic B2: Zone {zone.value} (dist: {dist_pct*100:.2f}%) -> max {limit} positions"
            return limit, zone, dist_pct, msg

        elif dynamic_mode == DynamicLimitMode.B3:
            if zone == MarketZone.NORMAL:
                limit = 3
            elif zone == MarketZone.CAUTION:
                limit = 2
            else:  # WEAK
                limit = 0
            msg = f"Dynamic B3: Zone {zone.value} (dist: {dist_pct*100:.2f}%) -> max {limit} positions"
            return limit, zone, dist_pct, msg

        else:
            raise ValueError(f"Unknown DynamicLimitMode: {dynamic_mode}")

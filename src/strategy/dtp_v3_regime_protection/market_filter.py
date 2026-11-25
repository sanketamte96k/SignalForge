"""
SignalForge — Phase 32J.7: Nifty Market Regime Protection Engine
================================================================
File: src/strategy/dtp_v3_regime_protection/market_filter.py

Implements causal Nifty 50 market regime protection filters:
  - Baseline: Nifty 50 Close > 100-day SMA
  - Experiment A: Market Trend Strength Filters (A1, A2, A3, A4)
  - Experiment B: Market Volatility Filters (B1, B2, B3)
  - Experiment C: Sideways Market Filters (C1, C2, C3, C4)
  - Experiment D: Two-Filter Combination

Strictly causal:
  - 480 pre-2017 warmup sessions ensure unbroken SMA100, ADX14, and 60-day percentiles on 2017-01-02.
  - Zero future look-ahead.
  - Evaluated exclusively for new trade entries; open positions are never forcibly liquidated.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.dtp_v3.indicators import calculate_adx, calculate_atr
from src.strategy.dtp_v3_regime_protection.config import RegimeProtectionFilterMode


class NiftyRegimeProtectionFilter:
    """
    Causal Nifty 50 Market Regime Protection indicator engine and entry permission evaluator.
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
        """Loads and builds continuous daily Nifty 50 dataframe across 2015-2019."""
        if not self.research_nifty_path.exists():
            raise FileNotFoundError(f"Missing historical Nifty research file: {self.research_nifty_path}")
        df_res = pd.read_csv(self.research_nifty_path)
        df_res["dt"] = pd.to_datetime(df_res["timestamp"])
        df_res["date"] = df_res["dt"].dt.date
        daily_pre = df_res[df_res["date"] < date(2017, 1, 2)].groupby("date").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        })
        daily_pre.columns = ["open", "high", "low", "close"]

        if not self.canonical_nifty_path.exists():
            raise FileNotFoundError(f"Missing canonical Nifty file: {self.canonical_nifty_path}")
        df_idx = pd.read_csv(self.canonical_nifty_path)
        df_idx["dt"] = pd.to_datetime(df_idx["timestamp"])
        df_idx["date"] = df_idx["dt"].dt.date
        daily_main = (
            df_idx[(df_idx["date"] >= date(2017, 1, 2)) & (df_idx["date"] <= date(2019, 12, 31))]
            .groupby("date")
            .agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
            })
        )

        combined = pd.concat([daily_pre, daily_main]).sort_index()

        # SMA100 & Trend Metrics
        combined["sma100"] = combined["close"].rolling(window=100).mean()
        combined["sma100_slope"] = combined["sma100"] - combined["sma100"].shift(1)
        combined["dist_sma100"] = (combined["close"] - combined["sma100"]) / combined["sma100"]

        # ADX(14)
        adx, p_di, m_di = calculate_adx(combined["high"], combined["low"], combined["close"], period=14)
        combined["adx14"] = adx

        # ATR(14) & Normalized Volatility Percentiles
        atr = calculate_atr(combined["high"], combined["low"], combined["close"], period=14)
        combined["atr14"] = atr
        combined["natr"] = combined["atr14"] / combined["close"]
        combined["natr_p75"] = combined["natr"].shift(1).rolling(window=60).quantile(0.75)
        combined["natr_p90"] = combined["natr"].shift(1).rolling(window=60).quantile(0.90)

        # Daily Return & Absolute Return Percentiles
        combined["abs_ret"] = ((combined["close"] - combined["close"].shift(1)) / combined["close"].shift(1)).abs()
        combined["abs_ret_p90"] = combined["abs_ret"].shift(1).rolling(window=60).quantile(0.90)

        # Retain study period
        self._daily_nifty = combined.loc[daily_main.index].copy()

    def get_indicators(self, decision_date: date) -> Dict[str, Any]:
        """Returns Nifty indicators on decision_date."""
        if self._daily_nifty is None:
            raise RuntimeError("NiftyRegimeProtectionFilter data not initialized.")
        if decision_date not in self._daily_nifty.index:
            raise KeyError(f"Date {decision_date} not in Nifty 50 calendar")

        row = self._daily_nifty.loc[decision_date]
        return {
            "date": decision_date.isoformat(),
            "close": float(row["close"]),
            "sma100": float(row["sma100"]),
            "sma100_slope": float(row["sma100_slope"]),
            "dist_sma100": float(row["dist_sma100"]),
            "adx14": float(row["adx14"]),
            "atr14": float(row["atr14"]),
            "natr": float(row["natr"]),
            "natr_p75": float(row["natr_p75"]),
            "natr_p90": float(row["natr_p90"]),
            "abs_ret": float(row["abs_ret"]),
            "abs_ret_p90": float(row["abs_ret_p90"]),
        }

    def is_entry_permitted(
        self,
        decision_date: date,
        mode: RegimeProtectionFilterMode,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates whether new entry is permitted under the specified regime filter mode.
        Returns: (is_permitted, reason_msg, metadata).
        """
        ind = self.get_indicators(decision_date)
        close = ind["close"]
        sma100 = ind["sma100"]
        slope = ind["sma100_slope"]
        dist = ind["dist_sma100"]
        adx = ind["adx14"]
        natr = ind["natr"]
        natr_p75 = ind["natr_p75"]
        natr_p90 = ind["natr_p90"]
        abs_ret = ind["abs_ret"]
        abs_ret_p90 = ind["abs_ret_p90"]

        # Baseline: NIFTY_SMA100 (Close > SMA100)
        if mode == RegimeProtectionFilterMode.BASELINE_SMA100:
            permitted = (close > sma100)
            msg = "Permitted: Close > SMA100" if permitted else f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            return permitted, msg, ind

        # Experiment A: Trend Strength
        elif mode == RegimeProtectionFilterMode.A1_ADX20:
            permitted = (adx >= 20.0)
            msg = f"Permitted: ADX(14) {adx:.2f} >= 20" if permitted else f"Blocked: ADX(14) {adx:.2f} < 20"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.A2_ADX25:
            permitted = (adx >= 25.0)
            msg = f"Permitted: ADX(14) {adx:.2f} >= 25" if permitted else f"Blocked: ADX(14) {adx:.2f} < 25"
            return permitted, msg, ind

        elif mode in [RegimeProtectionFilterMode.A3_RISING_SMA100, RegimeProtectionFilterMode.C1_SMA100_RISING]:
            permitted = (close > sma100) and (slope > 0.0)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif slope <= 0.0:
                msg = f"Blocked: SMA100 slope {slope:.2f} <= 0"
            else:
                msg = "Permitted: Close > rising SMA100"
            return permitted, msg, ind

        elif mode in [RegimeProtectionFilterMode.A4_SMA100_ADX20, RegimeProtectionFilterMode.C2_SMA100_ADX20]:
            permitted = (close > sma100) and (adx >= 20.0)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif adx < 20.0:
                msg = f"Blocked: ADX(14) {adx:.2f} < 20"
            else:
                msg = f"Permitted: Close > SMA100 and ADX(14) {adx:.2f} >= 20"
            return permitted, msg, ind

        # Experiment B: Volatility Filter Overlays (Baseline SMA100 + Volatility threshold)
        elif mode == RegimeProtectionFilterMode.B1_NATR_P75:
            permitted = (close > sma100) and (natr < natr_p75)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif natr >= natr_p75:
                msg = f"Blocked: NATR {natr:.4f} >= 75th percentile {natr_p75:.4f}"
            else:
                msg = f"Permitted: Close > SMA100 and NATR {natr:.4f} < P75 {natr_p75:.4f}"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.B2_NATR_P90:
            permitted = (close > sma100) and (natr < natr_p90)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif natr >= natr_p90:
                msg = f"Blocked: NATR {natr:.4f} >= 90th percentile {natr_p90:.4f}"
            else:
                msg = f"Permitted: Close > SMA100 and NATR {natr:.4f} < P90 {natr_p90:.4f}"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.B3_ABS_RET_P90:
            permitted = (close > sma100) and (abs_ret < abs_ret_p90)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif abs_ret >= abs_ret_p90:
                msg = f"Blocked: Daily |Return| {abs_ret:.4f} >= 90th percentile {abs_ret_p90:.4f}"
            else:
                msg = f"Permitted: Close > SMA100 and |Return| {abs_ret:.4f} < P90 {abs_ret_p90:.4f}"
            return permitted, msg, ind

        # Experiment B: Standalone Volatility Filters
        elif mode == RegimeProtectionFilterMode.B1_ALONE:
            permitted = (natr < natr_p75)
            msg = f"Permitted: NATR {natr:.4f} < P75" if permitted else f"Blocked: NATR {natr:.4f} >= P75"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.B2_ALONE:
            permitted = (natr < natr_p90)
            msg = f"Permitted: NATR {natr:.4f} < P90" if permitted else f"Blocked: NATR {natr:.4f} >= P90"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.B3_ALONE:
            permitted = (abs_ret < abs_ret_p90)
            msg = f"Permitted: |Return| {abs_ret:.4f} < P90" if permitted else f"Blocked: |Return| {abs_ret:.4f} >= P90"
            return permitted, msg, ind

        # Experiment C: Sideways Market Filters
        elif mode == RegimeProtectionFilterMode.C3_SMA100_DIST1PCT:
            permitted = (close > sma100) and (dist > 0.01)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif dist <= 0.01:
                msg = f"Blocked: Distance to SMA100 {dist*100:.2f}% <= 1.0%"
            else:
                msg = f"Permitted: Close > SMA100 and Distance {dist*100:.2f}% > 1.0%"
            return permitted, msg, ind

        elif mode == RegimeProtectionFilterMode.C4_SMA100_ADX20_RISING:
            permitted = (close > sma100) and (adx >= 20.0) and (slope > 0.0)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif adx < 20.0:
                msg = f"Blocked: ADX(14) {adx:.2f} < 20"
            elif slope <= 0.0:
                msg = f"Blocked: SMA100 slope {slope:.2f} <= 0"
            else:
                msg = f"Permitted: Close > rising SMA100 with ADX(14) {adx:.2f} >= 20"
            return permitted, msg, ind

        # Experiment D: Combination (Best Trend + Best Volatility)
        # Specifically: Close > rising SMA100 AND NATR < P90
        elif mode == RegimeProtectionFilterMode.D_COMBINATION:
            permitted = (close > sma100) and (slope > 0.0) and (natr < natr_p90)
            if not (close > sma100):
                msg = f"Blocked: Close {close:.1f} <= SMA100 {sma100:.1f}"
            elif slope <= 0.0:
                msg = f"Blocked: SMA100 slope {slope:.2f} <= 0"
            elif natr >= natr_p90:
                msg = f"Blocked: NATR {natr:.4f} >= P90 {natr_p90:.4f}"
            else:
                msg = "Permitted: Combination (Rising SMA100 + Volatility < P90)"
            return permitted, msg, ind

        else:
            raise ValueError(f"Unknown RegimeProtectionFilterMode: {mode}")

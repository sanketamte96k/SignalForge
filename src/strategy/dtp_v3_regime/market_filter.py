"""
SignalForge — Phase 32J.3.1: DTP-V3 Market Regime Filter Engine
=================================================================
File: src/strategy/dtp_v3_regime/market_filter.py

Implements causal Nifty 50 market trend regime filtering:
  - Variation A: NONE (Always permitted)
  - Variation B: NIFTY_SMA200 (Close > 200-day SMA)
  - Variation C: NIFTY_SMA100 (Close > 100-day SMA)
  - Variation D: NIFTY_SMA200_TREND (Close > 200-day SMA and SMA200[t] > SMA200[t-1])

Strictly causal:
  - Uses 2015-2016 daily closes as warm-up so 2017-01-02 has 200 full historical bars.
  - Zero look-ahead bias: evaluations on day T utilize closes up to and including day T.
  - Only blocks new entries; does NOT forcibly exit existing positions.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v3_regime.config import RegimeFilterMode


class NiftyMarketFilter:
    """
    Causal Nifty 50 trend regime filter provider.
    Maintains continuous daily history from 2015 through 2019 to provide
    unbroken 100-day and 200-day simple moving averages across 2017-2019.
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
        """Loads and builds the continuous daily Nifty 50 dataframe."""
        # 1. Load Pre-2017 research data for warm-up
        if not self.research_nifty_path.exists():
            raise FileNotFoundError(f"Missing historical Nifty research file: {self.research_nifty_path}")
        df_res = pd.read_csv(self.research_nifty_path)
        df_res["dt"] = pd.to_datetime(df_res["timestamp"])
        df_res["date"] = df_res["dt"].dt.date
        daily_pre = df_res[df_res["date"] < date(2017, 1, 2)].groupby("date").agg({"Close": "last"})
        daily_pre.columns = ["close"]

        # 2. Load Canonical 2017-2019 minute data
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

        # 3. Concatenate and compute causal moving averages
        combined = pd.concat([daily_pre, daily_main]).sort_index()
        combined["sma100"] = combined["close"].rolling(window=100).mean()
        combined["sma200"] = combined["close"].rolling(window=200).mean()
        combined["sma200_prev"] = combined["sma200"].shift(1)
        combined["sma200_rising"] = combined["sma200"] > combined["sma200_prev"]

        # Restrict lookup table to the active study window
        self._daily_nifty = combined.loc[daily_main.index].copy()

    def is_entry_permitted(
        self,
        decision_date: date,
        mode: RegimeFilterMode,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates whether a new long position entry is permitted under the chosen regime filter.
        Returns (is_permitted, reason_message, metadata_dict).
        """
        if mode == RegimeFilterMode.NONE:
            return True, "Filter A: NONE - All market regimes permitted", {"mode": mode.value}

        if self._daily_nifty is None:
            raise RuntimeError("NiftyMarketFilter data not initialized.")

        if decision_date not in self._daily_nifty.index:
            return False, f"Date {decision_date} not found in Nifty 50 calendar", {"mode": mode.value}

        row = self._daily_nifty.loc[decision_date]
        close = float(row["close"])
        sma100 = float(row["sma100"])
        sma200 = float(row["sma200"])
        sma200_rising = bool(row["sma200_rising"])

        meta = {
            "mode": mode.value,
            "decision_date": decision_date.isoformat(),
            "nifty_close": round(close, 2),
            "sma100": round(sma100, 2),
            "sma200": round(sma200, 2),
            "sma200_rising": sma200_rising,
        }

        if mode == RegimeFilterMode.NIFTY_SMA200:
            permitted = close > sma200
            status_str = "ABOVE" if permitted else "BELOW_OR_EQUAL"
            msg = f"Nifty Close ({close:.2f}) is {status_str} SMA200 ({sma200:.2f})"
            return permitted, msg, meta

        elif mode == RegimeFilterMode.NIFTY_SMA100:
            permitted = close > sma100
            status_str = "ABOVE" if permitted else "BELOW_OR_EQUAL"
            msg = f"Nifty Close ({close:.2f}) is {status_str} SMA100 ({sma100:.2f})"
            return permitted, msg, meta

        elif mode == RegimeFilterMode.NIFTY_SMA200_TREND:
            above_sma = close > sma200
            permitted = above_sma and sma200_rising
            if not above_sma:
                msg = f"Nifty Close ({close:.2f}) is BELOW_OR_EQUAL SMA200 ({sma200:.2f})"
            elif not sma200_rising:
                msg = f"Nifty Close ({close:.2f}) > SMA200 ({sma200:.2f}) but SMA200 is FLAT/FALLING"
            else:
                msg = f"Nifty Close ({close:.2f}) > SMA200 ({sma200:.2f}) AND SMA200 is RISING"
            return permitted, msg, meta

        else:
            raise ValueError(f"Unknown RegimeFilterMode: {mode}")

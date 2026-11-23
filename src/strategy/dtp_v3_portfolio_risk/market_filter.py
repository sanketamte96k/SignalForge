"""
SignalForge — Phase 32J.4: Nifty Market Weakness Exposure Engine
================================================================
File: src/strategy/dtp_v3_portfolio_risk/market_filter.py

Implements causal Nifty 50 market trend and proximity evaluation:
  - Baseline filter: Nifty 50 Close > 100-day SMA (blocks trades when False).
  - Weakness overlay (Experiment A):
      * A1_NONE: No risk reduction.
      * A2_WITHIN_2PCT: If Close > SMA100 and (Close - SMA100)/SMA100 <= 0.02, 50% risk discount.
      * A3_WITHIN_3PCT: If Close > SMA100 and (Close - SMA100)/SMA100 <= 0.03, 50% risk discount.

Strictly causal:
  - Uses historical 2015-2016 daily closes for warm-up.
  - Zero look-ahead: calculations use daily closes strictly up to decision date T.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3_portfolio_risk.config import NiftyWeaknessMode


class NiftyPortfolioRiskFilter:
    """
    Evaluates Nifty 50 trend regime and proximity to 100-day SMA for exposure scaling.
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
        combined["sma200"] = combined["close"].rolling(window=200).mean()

        self._daily_nifty = combined.loc[daily_main.index].copy()

    def evaluate_entry_exposure(
        self,
        decision_date: date,
        weakness_mode: NiftyWeaknessMode = NiftyWeaknessMode.A1_NONE,
        reduction_factor: float = 0.50,
    ) -> Tuple[bool, float, str, Dict[str, Any]]:
        """
        Evaluates whether an entry is permitted (Nifty > SMA100) and returns the risk multiplier:
          - If Nifty <= SMA100: returns (False, 0.0, "Blocked: Nifty <= SMA100", meta)
          - If permitted:
              returns (True, risk_multiplier, audit_reason, meta)
              where risk_multiplier is 1.0 (full risk) or 0.50 (reduced risk if within proximity band).
        """
        if self._daily_nifty is None:
            raise RuntimeError("NiftyPortfolioRiskFilter data not initialized.")

        if decision_date not in self._daily_nifty.index:
            return False, 0.0, f"Date {decision_date} not in Nifty calendar", {"decision_date": decision_date.isoformat()}

        row = self._daily_nifty.loc[decision_date]
        close = float(row["close"])
        sma100 = float(row["sma100"])

        # Baseline check: Nifty must be above 100-day SMA
        if close <= sma100:
            return (
                False,
                0.0,
                f"Blocked: Nifty Close ({close:.2f}) <= SMA100 ({sma100:.2f})",
                {
                    "decision_date": decision_date.isoformat(),
                    "nifty_close": round(close, 2),
                    "sma100": round(sma100, 2),
                    "dist_pct": round((close - sma100) / sma100 * 100, 2),
                },
            )

        dist_pct = (close - sma100) / sma100

        meta = {
            "decision_date": decision_date.isoformat(),
            "nifty_close": round(close, 2),
            "sma100": round(sma100, 2),
            "dist_pct": round(dist_pct * 100, 2),
            "weakness_mode": weakness_mode.value,
        }

        if weakness_mode == NiftyWeaknessMode.A1_NONE:
            return True, 1.0, f"Nifty Close ({close:.2f}) > SMA100 ({sma100:.2f}) - Full Risk", meta

        elif weakness_mode == NiftyWeaknessMode.A2_WITHIN_2PCT:
            if dist_pct <= 0.02:
                multiplier = 1.0 - reduction_factor
                msg = f"Nifty Close ({close:.2f}) within 2.0% of SMA100 ({dist_pct*100:.2f}%) -> {multiplier:.0%} Risk Sizing"
                meta["risk_multiplier"] = multiplier
                return True, multiplier, msg, meta
            else:
                msg = f"Nifty Close ({close:.2f}) >2.0% above SMA100 ({dist_pct*100:.2f}%) -> Full Risk"
                meta["risk_multiplier"] = 1.0
                return True, 1.0, msg, meta

        elif weakness_mode == NiftyWeaknessMode.A3_WITHIN_3PCT:
            if dist_pct <= 0.03:
                multiplier = 1.0 - reduction_factor
                msg = f"Nifty Close ({close:.2f}) within 3.0% of SMA100 ({dist_pct*100:.2f}%) -> {multiplier:.0%} Risk Sizing"
                meta["risk_multiplier"] = multiplier
                return True, multiplier, msg, meta
            else:
                msg = f"Nifty Close ({close:.2f}) >3.0% above SMA100 ({dist_pct*100:.2f}%) -> Full Risk"
                meta["risk_multiplier"] = 1.0
                return True, 1.0, msg, meta

        else:
            raise ValueError(f"Unknown NiftyWeaknessMode: {weakness_mode}")

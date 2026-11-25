"""
SignalForge — Phase 32J.8: Market Breadth Participation Engine
==============================================================
File: src/strategy/dtp_v3_breadth_research/breadth_engine.py

Calculates causal market breadth indicators across the 91 approved NSE equities:
  - Indicator A: Percentage of stocks above 50 EMA
  - Indicator B: Percentage of stocks above 100 SMA
  - Indicator C: Percentage of stocks with rising 50 EMA
  - Indicator D: Percentage of stocks with positive 20-session return
  - Indicator E: Daily Advance-Decline Ratio (Advances / Declines)

Strictly causal:
  - Computed on completed daily close prices without look-ahead.
  - Coupled with Phase 32J.7 Rising SMA100 baseline:
    Entry requires: (Nifty Close > SMA100 AND SMA100[t] > SMA100[t-1]) AND Breadth Filter.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.dtp_v3_breadth_research.config import BreadthFilterMode
from src.strategy.dtp_v3_regime_protection.config import RegimeProtectionFilterMode
from src.strategy.dtp_v3_regime_protection.market_filter import NiftyRegimeProtectionFilter


class MarketBreadthEngine:
    """
    Computes daily universe-level market breadth participation across the 91 approved stocks
    and evaluates entry permissions.
    """

    def __init__(
        self,
        universe: Dict[str, pd.DataFrame],
        nifty_filter: Optional[NiftyRegimeProtectionFilter] = None,
    ) -> None:
        self.symbols = sorted(list(universe.keys()))
        self.trading_dates = sorted(list(universe[self.symbols[0]].index))
        self.nifty_filter = nifty_filter or NiftyRegimeProtectionFilter()

        self._breadth_df: Optional[pd.DataFrame] = None
        self._compute_daily_breadth(universe)

    def _compute_daily_breadth(self, universe: Dict[str, pd.DataFrame]) -> None:
        """Computes daily breadth time series for indicators A, B, C, D, E."""
        closes = pd.DataFrame({s: universe[s]["close"] for s in self.symbols}, index=self.trading_dates)

        # Indicator A: Above 50 EMA
        ema50 = closes.ewm(span=50, adjust=False).mean()
        is_above_ema50 = closes > ema50
        pct_above_ema50 = is_above_ema50.mean(axis=1) * 100.0

        # Indicator B: Above 100 SMA
        # min_periods=1 allows causal expanding mean during warmup so denominator is always valid
        sma100 = closes.rolling(window=100, min_periods=1).mean()
        is_above_sma100 = closes > sma100
        pct_above_sma100 = is_above_sma100.mean(axis=1) * 100.0

        # Strict 100-bar SMA for documentation
        sma100_strict = closes.rolling(window=100, min_periods=100).mean()
        valid_strict_stocks = sma100_strict.notnull().sum(axis=1)
        pct_above_sma100_strict = np.where(
            valid_strict_stocks > 0,
            (closes > sma100_strict).sum(axis=1) / valid_strict_stocks * 100.0,
            0.0,
        )

        # Indicator C: Rising 50 EMA
        ema50_slope = ema50 - ema50.shift(1)
        is_rising_ema50 = ema50_slope > 0.0
        pct_rising_ema50 = is_rising_ema50.mean(axis=1) * 100.0

        # Indicator D: Positive 20-session return
        ret20 = closes.pct_change(periods=20)
        is_pos_ret20 = ret20 > 0.0
        pct_pos_ret20 = is_pos_ret20.mean(axis=1) * 100.0

        # Indicator E: Advance-Decline Ratio
        daily_diff = closes - closes.shift(1)
        advances = (daily_diff > 0.0).sum(axis=1)
        declines = (daily_diff < 0.0).sum(axis=1)
        unchanged = (daily_diff == 0.0).sum(axis=1)

        # Avoid division by zero
        adr = np.where(
            declines > 0,
            advances / declines,
            np.where(advances > 0, 99.0, 1.0),
        )

        # Assemble full breadth DataFrame
        df_b = pd.DataFrame(index=self.trading_dates)
        df_b["date"] = [ts.date() for ts in self.trading_dates]
        df_b["universe_size"] = len(self.symbols)
        df_b["valid_denominator"] = len(self.symbols)
        df_b["pct_above_ema50"] = pct_above_ema50.round(2)
        df_b["pct_above_sma100"] = pct_above_sma100.round(2)
        df_b["pct_above_sma100_strict"] = pd.Series(pct_above_sma100_strict, index=self.trading_dates).round(2)
        df_b["valid_strict_denominator"] = valid_strict_stocks
        df_b["pct_rising_ema50"] = pct_rising_ema50.round(2)
        df_b["pct_pos_ret20"] = pct_pos_ret20.round(2)
        df_b["advances"] = advances
        df_b["declines"] = declines
        df_b["unchanged"] = unchanged
        df_b["adr"] = pd.Series(adr, index=self.trading_dates).round(2)

        self._breadth_df = df_b.copy()

    @property
    def breadth_history(self) -> pd.DataFrame:
        if self._breadth_df is None:
            raise RuntimeError("Breadth engine not initialized.")
        return self._breadth_df.copy()

    def get_breadth(self, decision_date: date) -> Dict[str, Any]:
        """Returns market breadth metrics for decision_date."""
        if self._breadth_df is None:
            raise RuntimeError("Breadth engine not initialized.")

        # Find row by date
        match = self._breadth_df[self._breadth_df["date"] == decision_date]
        if match.empty:
            raise KeyError(f"Date {decision_date} not in trading dates")

        row = match.iloc[0]
        return row.to_dict()

    def is_entry_permitted(
        self,
        decision_date: date,
        mode: BreadthFilterMode,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates whether new entry is permitted under the specified breadth filter mode.
        First enforces Phase 32J.7 Rising SMA100 baseline:
          Nifty Close > SMA100 AND SMA100[t] > SMA100[t-1]
        Then applies the pre-registered breadth participation filter.
        """
        # Step 1: Baseline Rising SMA100 check
        base_perm, base_msg, base_ind = self.nifty_filter.is_entry_permitted(
            decision_date=decision_date,
            mode=RegimeProtectionFilterMode.A3_RISING_SMA100,
        )

        b_metrics = self.get_breadth(decision_date)
        meta = {**b_metrics, **base_ind}

        if not base_perm:
            return False, f"Blocked by Baseline: {base_msg}", meta

        # Baseline mode has no further breadth filter
        if mode == BreadthFilterMode.BASELINE_RISING_SMA100:
            return True, "Permitted: Rising SMA100 Baseline", meta

        # Indicator A: Percentage of stocks above 50 EMA
        elif mode == BreadthFilterMode.A_EMA50_40:
            val = b_metrics["pct_above_ema50"]
            perm = val >= 40.0
            msg = f"Permitted: % > EMA50 is {val:.1f}% >= 40%" if perm else f"Blocked: % > EMA50 is {val:.1f}% < 40%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.A_EMA50_50:
            val = b_metrics["pct_above_ema50"]
            perm = val >= 50.0
            msg = f"Permitted: % > EMA50 is {val:.1f}% >= 50%" if perm else f"Blocked: % > EMA50 is {val:.1f}% < 50%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.A_EMA50_60:
            val = b_metrics["pct_above_ema50"]
            perm = val >= 60.0
            msg = f"Permitted: % > EMA50 is {val:.1f}% >= 60%" if perm else f"Blocked: % > EMA50 is {val:.1f}% < 60%"
            return perm, msg, meta

        # Indicator B: Percentage of stocks above 100 SMA
        elif mode == BreadthFilterMode.B_SMA100_40:
            val = b_metrics["pct_above_sma100"]
            perm = val >= 40.0
            msg = f"Permitted: % > SMA100 is {val:.1f}% >= 40%" if perm else f"Blocked: % > SMA100 is {val:.1f}% < 40%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.B_SMA100_50:
            val = b_metrics["pct_above_sma100"]
            perm = val >= 50.0
            msg = f"Permitted: % > SMA100 is {val:.1f}% >= 50%" if perm else f"Blocked: % > SMA100 is {val:.1f}% < 50%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.B_SMA100_60:
            val = b_metrics["pct_above_sma100"]
            perm = val >= 60.0
            msg = f"Permitted: % > SMA100 is {val:.1f}% >= 60%" if perm else f"Blocked: % > SMA100 is {val:.1f}% < 60%"
            return perm, msg, meta

        # Indicator C: Percentage of stocks with rising 50 EMA
        elif mode == BreadthFilterMode.C_RISE50_40:
            val = b_metrics["pct_rising_ema50"]
            perm = val >= 40.0
            msg = f"Permitted: % Rising EMA50 is {val:.1f}% >= 40%" if perm else f"Blocked: % Rising EMA50 is {val:.1f}% < 40%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.C_RISE50_50:
            val = b_metrics["pct_rising_ema50"]
            perm = val >= 50.0
            msg = f"Permitted: % Rising EMA50 is {val:.1f}% >= 50%" if perm else f"Blocked: % Rising EMA50 is {val:.1f}% < 50%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.C_RISE50_60:
            val = b_metrics["pct_rising_ema50"]
            perm = val >= 60.0
            msg = f"Permitted: % Rising EMA50 is {val:.1f}% >= 60%" if perm else f"Blocked: % Rising EMA50 is {val:.1f}% < 60%"
            return perm, msg, meta

        # Indicator D: Percentage of stocks with positive 20-session return
        elif mode == BreadthFilterMode.D_RET20_40:
            val = b_metrics["pct_pos_ret20"]
            perm = val >= 40.0
            msg = f"Permitted: % Pos Ret20 is {val:.1f}% >= 40%" if perm else f"Blocked: % Pos Ret20 is {val:.1f}% < 40%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.D_RET20_50:
            val = b_metrics["pct_pos_ret20"]
            perm = val >= 50.0
            msg = f"Permitted: % Pos Ret20 is {val:.1f}% >= 50%" if perm else f"Blocked: % Pos Ret20 is {val:.1f}% < 50%"
            return perm, msg, meta

        elif mode == BreadthFilterMode.D_RET20_60:
            val = b_metrics["pct_pos_ret20"]
            perm = val >= 60.0
            msg = f"Permitted: % Pos Ret20 is {val:.1f}% >= 60%" if perm else f"Blocked: % Pos Ret20 is {val:.1f}% < 60%"
            return perm, msg, meta

        # Indicator E: Advance-Decline Ratio
        elif mode == BreadthFilterMode.E_ADR_080:
            val = b_metrics["adr"]
            perm = val >= 0.80
            msg = f"Permitted: ADR is {val:.2f} >= 0.80" if perm else f"Blocked: ADR is {val:.2f} < 0.80"
            return perm, msg, meta

        elif mode == BreadthFilterMode.E_ADR_100:
            val = b_metrics["adr"]
            perm = val >= 1.00
            msg = f"Permitted: ADR is {val:.2f} >= 1.00" if perm else f"Blocked: ADR is {val:.2f} < 1.00"
            return perm, msg, meta

        elif mode == BreadthFilterMode.E_ADR_120:
            val = b_metrics["adr"]
            perm = val >= 1.20
            msg = f"Permitted: ADR is {val:.2f} >= 1.20" if perm else f"Blocked: ADR is {val:.2f} < 1.20"
            return perm, msg, meta

        # Best two breadth filters combined (evaluated after single filter ranking)
        elif mode == BreadthFilterMode.COMBO_BEST_TWO:
            # Combining % Above 50 EMA >= 50% AND % Rising 50 EMA >= 50%
            val_a = b_metrics["pct_above_ema50"]
            val_c = b_metrics["pct_rising_ema50"]
            perm = (val_a >= 50.0) and (val_c >= 50.0)
            msg = "Permitted: Dual Breadth (% > EMA50 >= 50% & % Rising EMA50 >= 50%)" if perm else f"Blocked: Dual Breadth (EMA50: {val_a:.1f}%, Rising: {val_c:.1f}%)"
            return perm, msg, meta

        else:
            raise ValueError(f"Unknown BreadthFilterMode: {mode}")

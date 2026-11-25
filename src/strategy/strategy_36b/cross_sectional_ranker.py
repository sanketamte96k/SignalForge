"""
SignalForge — Phase 36B: Cross-Sectional Relative Strength Ranker
=================================================================
File: src/strategy/strategy_36b/cross_sectional_ranker.py

Computes multi-timeframe trailing returns (20-, 40-, 60-session lookbacks),
cross-sectional percentile ranks, and the Composite Relative Strength Score (CRSS)
with strict adherence to zero lookahead bias.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.strategy_36b.config import Strategy36BConfig


@dataclass(frozen=True)
class StockRankEntry:
    """Represents relative strength ranking data for a single stock on a given date."""
    date: date
    symbol: str
    sector: str
    close_price: float
    ret_20: float
    ret_40: float
    ret_60: float
    rank_20_pct: float
    rank_40_pct: float
    rank_60_pct: float
    crss: float
    crss_percentile: float
    universe_rank: int  # 1 = highest CRSS, 2 = 2nd highest, ...


class CrossSectionalRanker:
    """
    Computes cross-sectional relative strength scores and rankings across the universe
    for each trading session date.
    """

    def __init__(
        self,
        universe: Dict[str, pd.DataFrame],
        sector_map: Dict[str, str],
        config: Strategy36BConfig,
    ) -> None:
        self.universe = universe
        self.sector_map = sector_map
        self.config = config

        # Pre-align price and volume matrices: dates x symbols
        self._symbols = sorted(universe.keys())
        self._aligned_closes: pd.DataFrame = pd.DataFrame()
        self._aligned_volumes: pd.DataFrame = pd.DataFrame()
        self._aligned_opens: pd.DataFrame = pd.DataFrame()
        self._trading_dates: List[date] = []
        self._build_aligned_matrices()

    def _build_aligned_matrices(self) -> None:
        """Constructs unified date-indexed matrices for close, open, and volume."""
        close_dict = {}
        volume_dict = {}
        open_dict = {}

        for sym in self._symbols:
            df = self.universe[sym]
            close_dict[sym] = df["close"]
            volume_dict[sym] = df["volume"]
            open_dict[sym] = df["open"]

        self._aligned_closes = pd.DataFrame(close_dict).sort_index()
        self._aligned_volumes = pd.DataFrame(volume_dict).sort_index()
        self._aligned_opens = pd.DataFrame(open_dict).sort_index()
        self._trading_dates = list(self._aligned_closes.index)

    @property
    def trading_dates(self) -> List[date]:
        return self._trading_dates

    def compute_ranks_for_date(self, target_date: date) -> List[StockRankEntry]:
        """
        Computes cross-sectional rankings for a specific trading session using ONLY
        data available at or before target_date.
        """
        if target_date not in self._aligned_closes.index:
            raise KeyError(f"Date {target_date} not found in trading dates.")

        idx = self._aligned_closes.index.get_loc(target_date)
        lookback_max = max(
            self.config.lookback_fast,
            self.config.lookback_mid,
            self.config.lookback_slow,
        )

        if idx < lookback_max:
            # Insufficient lookback history
            return []

        # Slice prices strictly up to index idx (inclusive)
        sub_closes = self._aligned_closes.iloc[idx - lookback_max : idx + 1]
        sub_volumes = self._aligned_volumes.iloc[idx - self.config.lookback_fast : idx + 1]

        current_closes = sub_closes.iloc[-1]
        p_fast = sub_closes.iloc[-1 - self.config.lookback_fast]
        p_mid = sub_closes.iloc[-1 - self.config.lookback_mid]
        p_slow = sub_closes.iloc[-1 - self.config.lookback_slow]

        ret_fast = (current_closes / p_fast) - 1.0
        ret_mid = (current_closes / p_mid) - 1.0
        ret_slow = (current_closes / p_slow) - 1.0
        vol_avg = sub_volumes.mean()

        # Build cross-sectional dataframe for eligible stocks (non-null returns)
        valid_mask = ret_fast.notna() & ret_mid.notna() & ret_slow.notna()
        valid_syms = [s for s in self._symbols if valid_mask[s]]

        if not valid_syms:
            return []

        df_rank = pd.DataFrame({
            "symbol": valid_syms,
            "sector": [self.sector_map.get(s, "Unknown") for s in valid_syms],
            "close": [current_closes[s] for s in valid_syms],
            "ret_fast": [ret_fast[s] for s in valid_syms],
            "ret_mid": [ret_mid[s] for s in valid_syms],
            "ret_slow": [ret_slow[s] for s in valid_syms],
            "vol_avg": [vol_avg[s] for s in valid_syms],
        })

        k_count = len(df_rank)

        # Cross-sectional percentile ranks: [1/K, 1.0] where 1.0 is highest return
        # method="average" handles any exact ties smoothly
        df_rank["rank_fast_pct"] = df_rank["ret_fast"].rank(ascending=True, pct=True)
        df_rank["rank_mid_pct"] = df_rank["ret_mid"].rank(ascending=True, pct=True)
        df_rank["rank_slow_pct"] = df_rank["ret_slow"].rank(ascending=True, pct=True)

        # Composite Relative Strength Score (CRSS)
        df_rank["crss"] = (
            self.config.weight_fast * df_rank["rank_fast_pct"]
            + self.config.weight_mid * df_rank["rank_mid_pct"]
            + self.config.weight_slow * df_rank["rank_slow_pct"]
        )

        # Cross-sectional percentile rank of CRSS itself across the universe
        # Higher CRSS = higher percentile (1.0 = top 100th percentile)
        df_rank["crss_percentile"] = df_rank["crss"].rank(ascending=True, pct=True)

        # Sort descending by CRSS, then tie-break by ret_slow, then vol_avg
        df_rank = df_rank.sort_values(
            by=["crss", "ret_slow", "vol_avg"],
            ascending=[False, False, False],
        ).reset_index(drop=True)

        # universe_rank: 1 = top stock, 2 = 2nd stock, ...
        df_rank["universe_rank"] = np.arange(1, k_count + 1)

        entries = []
        for _, row in df_rank.iterrows():
            entries.append(
                StockRankEntry(
                    date=target_date,
                    symbol=row["symbol"],
                    sector=row["sector"],
                    close_price=float(row["close"]),
                    ret_20=float(row["ret_fast"]),
                    ret_40=float(row["ret_mid"]),
                    ret_60=float(row["ret_slow"]),
                    rank_20_pct=float(row["rank_fast_pct"]),
                    rank_40_pct=float(row["rank_mid_pct"]),
                    rank_60_pct=float(row["rank_slow_pct"]),
                    crss=float(row["crss"]),
                    crss_percentile=float(row["crss_percentile"]),
                    universe_rank=int(row["universe_rank"]),
                )
            )

        return entries

    def get_open_price(self, symbol: str, target_date: date) -> float:
        """Returns the raw opening price of a stock on target_date."""
        return float(self._aligned_opens.loc[target_date, symbol])

    def get_close_price(self, symbol: str, target_date: date) -> float:
        """Returns the raw closing price of a stock on target_date."""
        return float(self._aligned_closes.loc[target_date, symbol])

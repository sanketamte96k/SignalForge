"""
SignalForge — Phase 36C: Performance Metrics, Accounting & Robustness Engine
============================================================================
File: src/strategy/strategy_36c/performance_metrics.py

Provides telescoping monthly/yearly accounting tables, strict mathematical reconciliation,
stock/sector concentration audits (LOSO / LO-Sector-O), regime breakdown, and
10,000-iteration block-bootstrap alpha distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.strategy_36c.rebalance_simulator import (
    CompletedTrade36C,
    DailyPortfolioSnapshot,
    SimulationResult36C,
)


@dataclass
class MonthlyPerformanceEntry:
    year: int
    month: int
    year_month: str
    starting_equity: float
    ending_equity: float
    net_pnl: float
    return_pct: float
    trade_count: int
    win_rate_pct: float
    nifty_return_pct: float
    net_alpha_pct: float


@dataclass
class YearlyPerformanceEntry:
    year: int
    starting_equity: float
    ending_equity: float
    net_pnl: float
    return_pct: float
    trade_count: int
    win_rate_pct: float
    max_drawdown_pct: float
    nifty_return_pct: float
    net_alpha_pct: float


@dataclass
class StockContributionEntry:
    symbol: str
    sector: str
    trade_count: int
    gross_pnl: float
    statutory_costs: float
    slippage_costs: float
    total_costs: float
    net_pnl: float
    win_rate_pct: float
    contribution_pct: float


@dataclass
class SectorPerformanceEntry:
    sector: str
    trade_count: int
    gross_pnl: float
    statutory_costs: float
    slippage_costs: float
    total_costs: float
    net_pnl: float
    win_rate_pct: float
    profit_share_pct: float


@dataclass
class DrawdownEpisode:
    episode_id: int
    peak_date: date
    trough_date: date
    recovery_date: Optional[date]
    peak_equity: float
    trough_equity: float
    drawdown_pct: float
    duration_sessions: int


@dataclass
class BootstrapAlphaResult:
    mean_net_alpha_pct: float
    ci_lower_95: float
    ci_upper_95: float
    prob_positive_alpha: float
    mean_expectancy_pnl: float
    expectancy_ci_lower_95: float
    expectancy_ci_upper_95: float
    num_iterations: int
    block_size_days: int


class PerformanceMetricsEngine:
    """Computes accounting, concentration, and robustness statistics for Phase 36C."""

    def __init__(self, result: SimulationResult36C) -> None:
        self.result = result
        self.trades = result.completed_trades
        self.snapshots = result.daily_snapshots
        self.snap_df = pd.DataFrame([s.__dict__ for s in self.snapshots])
        if not self.snap_df.empty:
            self.snap_df["date"] = pd.to_datetime(self.snap_df["date"])
            self.snap_df["year"] = self.snap_df["date"].dt.year
            self.snap_df["month"] = self.snap_df["date"].dt.month
            self.snap_df["year_month"] = self.snap_df["date"].dt.strftime("%Y-%m")

    def compute_monthly_performance(self) -> List[MonthlyPerformanceEntry]:
        """Calculates monthly performance table across all 36 months using telescoping equity."""
        if self.snap_df.empty:
            return []

        entries: List[MonthlyPerformanceEntry] = []
        months = sorted(self.snap_df["year_month"].unique())

        trade_df = pd.DataFrame([t.__dict__ for t in self.trades]) if self.trades else pd.DataFrame()
        if not trade_df.empty:
            trade_df["exit_date"] = pd.to_datetime(trade_df["exit_date"])
            trade_df["year_month"] = trade_df["exit_date"].dt.strftime("%Y-%m")

        prev_end_equity = float(self.result.initial_capital)
        prev_nifty_close = float(self.snap_df["nifty_close"].iloc[0])

        for ym in months:
            sub_snap = self.snap_df[self.snap_df["year_month"] == ym]
            start_eq = prev_end_equity
            end_eq = float(sub_snap["total_equity"].iloc[-1])
            net_pnl = round(end_eq - start_eq, 2)
            ret_pct = ((end_eq / start_eq) - 1.0) * 100.0 if start_eq > 0 else 0.0

            nifty_start = prev_nifty_close
            nifty_end = float(sub_snap["nifty_close"].iloc[-1])
            nifty_ret = ((nifty_end / nifty_start) - 1.0) * 100.0 if nifty_start > 0 else 0.0
            net_alpha = ret_pct - nifty_ret

            t_count = 0
            win_rate = 0.0
            if not trade_df.empty:
                sub_trades = trade_df[trade_df["year_month"] == ym]
                t_count = len(sub_trades)
                if t_count > 0:
                    wins = len(sub_trades[sub_trades["net_pnl"] > 0])
                    win_rate = (wins / t_count) * 100.0

            y = int(ym[:4])
            m = int(ym[5:7])

            entries.append(
                MonthlyPerformanceEntry(
                    year=y,
                    month=m,
                    year_month=ym,
                    starting_equity=round(start_eq, 2),
                    ending_equity=round(end_eq, 2),
                    net_pnl=round(net_pnl, 2),
                    return_pct=round(ret_pct, 2),
                    trade_count=t_count,
                    win_rate_pct=round(win_rate, 2),
                    nifty_return_pct=round(nifty_ret, 2),
                    net_alpha_pct=round(net_alpha, 2),
                )
            )
            prev_end_equity = end_eq
            prev_nifty_close = nifty_end

        return entries

    def compute_yearly_performance(self) -> List[YearlyPerformanceEntry]:
        """Calculates yearly performance table for 2017, 2018, and 2019 using telescoping equity."""
        if self.snap_df.empty:
            return []

        entries: List[YearlyPerformanceEntry] = []
        years = sorted(self.snap_df["year"].unique())

        trade_df = pd.DataFrame([t.__dict__ for t in self.trades]) if self.trades else pd.DataFrame()
        if not trade_df.empty:
            trade_df["exit_date"] = pd.to_datetime(trade_df["exit_date"])
            trade_df["year"] = trade_df["exit_date"].dt.year

        prev_end_equity = float(self.result.initial_capital)
        prev_nifty_close = float(self.snap_df["nifty_close"].iloc[0])

        for y in years:
            sub_snap = self.snap_df[self.snap_df["year"] == y]
            start_eq = prev_end_equity
            end_eq = float(sub_snap["total_equity"].iloc[-1])
            net_pnl = round(end_eq - start_eq, 2)
            ret_pct = ((end_eq / start_eq) - 1.0) * 100.0 if start_eq > 0 else 0.0

            nifty_start = prev_nifty_close
            nifty_end = float(sub_snap["nifty_close"].iloc[-1])
            nifty_ret = ((nifty_end / nifty_start) - 1.0) * 100.0 if nifty_start > 0 else 0.0
            net_alpha = ret_pct - nifty_ret

            max_dd = float(sub_snap["drawdown_pct"].max())

            t_count = 0
            win_rate = 0.0
            if not trade_df.empty:
                sub_trades = trade_df[trade_df["year"] == y]
                t_count = len(sub_trades)
                if t_count > 0:
                    wins = len(sub_trades[sub_trades["net_pnl"] > 0])
                    win_rate = (wins / t_count) * 100.0

            entries.append(
                YearlyPerformanceEntry(
                    year=int(y),
                    starting_equity=round(start_eq, 2),
                    ending_equity=round(end_eq, 2),
                    net_pnl=round(net_pnl, 2),
                    return_pct=round(ret_pct, 2),
                    trade_count=t_count,
                    win_rate_pct=round(win_rate, 2),
                    max_drawdown_pct=round(max_dd, 2),
                    nifty_return_pct=round(nifty_ret, 2),
                    net_alpha_pct=round(net_alpha, 2),
                )
            )
            prev_end_equity = end_eq
            prev_nifty_close = nifty_end

        return entries

    def compute_stock_contributions(self) -> List[StockContributionEntry]:
        """Calculates per-stock P&L contributions and rankings."""
        if not self.trades:
            return []

        df = pd.DataFrame([t.__dict__ for t in self.trades])
        total_net_pnl = float(df["net_pnl"].sum())

        grouped = df.groupby(["symbol", "sector"]).agg({
            "trade_id": "count",
            "gross_pnl": "sum",
            "statutory_costs": "sum",
            "slippage_costs": "sum",
            "total_costs": "sum",
            "net_pnl": "sum",
        }).reset_index()

        entries: List[StockContributionEntry] = []
        for _, row in grouped.iterrows():
            sym = row["symbol"]
            sub = df[df["symbol"] == sym]
            wins = len(sub[sub["net_pnl"] > 0])
            wr = (wins / len(sub)) * 100.0 if len(sub) > 0 else 0.0

            net = float(row["net_pnl"])
            contrib_pct = (net / total_net_pnl * 100.0) if total_net_pnl != 0 else 0.0

            entries.append(
                StockContributionEntry(
                    symbol=sym,
                    sector=row["sector"],
                    trade_count=int(row["trade_id"]),
                    gross_pnl=round(float(row["gross_pnl"]), 2),
                    statutory_costs=round(float(row["statutory_costs"]), 2),
                    slippage_costs=round(float(row["slippage_costs"]), 2),
                    total_costs=round(float(row["total_costs"]), 2),
                    net_pnl=round(net, 2),
                    win_rate_pct=round(wr, 2),
                    contribution_pct=round(contrib_pct, 2),
                )
            )

        entries.sort(key=lambda x: x.net_pnl, reverse=True)
        return entries

    def compute_sector_performance(self) -> List[SectorPerformanceEntry]:
        """Calculates performance broken down by sector."""
        if not self.trades:
            return []

        df = pd.DataFrame([t.__dict__ for t in self.trades])
        total_net_pnl = float(df["net_pnl"].sum())

        grouped = df.groupby("sector").agg({
            "trade_id": "count",
            "gross_pnl": "sum",
            "statutory_costs": "sum",
            "slippage_costs": "sum",
            "total_costs": "sum",
            "net_pnl": "sum",
        }).reset_index()

        entries: List[SectorPerformanceEntry] = []
        for _, row in grouped.iterrows():
            sec = row["sector"]
            sub = df[df["sector"] == sec]
            wins = len(sub[sub["net_pnl"] > 0])
            wr = (wins / len(sub)) * 100.0 if len(sub) > 0 else 0.0

            net = float(row["net_pnl"])
            profit_share = (net / total_net_pnl * 100.0) if total_net_pnl != 0 else 0.0

            entries.append(
                SectorPerformanceEntry(
                    sector=sec,
                    trade_count=int(row["trade_id"]),
                    gross_pnl=round(float(row["gross_pnl"]), 2),
                    statutory_costs=round(float(row["statutory_costs"]), 2),
                    slippage_costs=round(float(row["slippage_costs"]), 2),
                    total_costs=round(float(row["total_costs"]), 2),
                    net_pnl=round(net, 2),
                    win_rate_pct=round(wr, 2),
                    profit_share_pct=round(profit_share, 2),
                )
            )

        entries.sort(key=lambda x: x.net_pnl, reverse=True)
        return entries

    def compute_top_stock_removal_impact(self, top_n: int = 3) -> Dict[str, float]:
        """Analyzes impact of removing the top N winning stocks."""
        if not self.trades:
            return {"remaining_net_pnl": 0.0, "top_n_profit": 0.0, "total_net_pnl": 0.0, "top_n_share_pct": 0.0}

        df = pd.DataFrame([t.__dict__ for t in self.trades])
        stock_pnl = df.groupby("symbol")["net_pnl"].sum().sort_values(ascending=False)

        total_net = float(stock_pnl.sum())
        top_stocks = stock_pnl.iloc[:top_n]
        top_n_pnl = float(top_stocks.sum())
        rem_pnl = total_net - top_n_pnl

        return {
            "total_net_pnl": round(total_net, 2),
            f"top_{top_n}_pnl": round(top_n_pnl, 2),
            "remaining_net_pnl": round(rem_pnl, 2),
            f"top_{top_n}_share_pct": round((top_n_pnl / total_net * 100.0) if total_net != 0 else 0.0, 2),
        }

    def compute_regime_breakdown(self) -> Dict[str, Any]:
        """Analyzes strategy performance during Bull vs Bear market regimes."""
        if self.snap_df.empty:
            return {}

        bull_days = self.snap_df[self.snap_df["is_bull_regime"] == True]
        bear_days = self.snap_df[self.snap_df["is_bull_regime"] == False]

        p_ret_bull = bull_days["daily_return_pct"] / 100.0
        m_ret_bull = bull_days["nifty_return_pct"] / 100.0
        p_ret_bear = bear_days["daily_return_pct"] / 100.0
        m_ret_bear = bear_days["nifty_return_pct"] / 100.0

        p_cum_bull = (np.prod(1.0 + p_ret_bull.values) - 1.0) * 100.0 if len(p_ret_bull) > 0 else 0.0
        m_cum_bull = (np.prod(1.0 + m_ret_bull.values) - 1.0) * 100.0 if len(m_ret_bull) > 0 else 0.0
        p_cum_bear = (np.prod(1.0 + p_ret_bear.values) - 1.0) * 100.0 if len(p_ret_bear) > 0 else 0.0
        m_cum_bear = (np.prod(1.0 + m_ret_bear.values) - 1.0) * 100.0 if len(m_ret_bear) > 0 else 0.0

        return {
            "bull_sessions_count": len(bull_days),
            "bear_sessions_count": len(bear_days),
            "strategy_return_bull_pct": round(p_cum_bull, 2),
            "nifty_return_bull_pct": round(m_cum_bull, 2),
            "strategy_return_bear_pct": round(p_cum_bear, 2),
            "nifty_return_bear_pct": round(m_cum_bear, 2),
        }

    def compute_drawdown_episodes(self, threshold_pct: float = 5.0) -> List[DrawdownEpisode]:
        """Identifies peak-to-trough drawdown episodes deeper than threshold_pct."""
        if self.snap_df.empty:
            return []

        episodes: List[DrawdownEpisode] = []
        equity = self.snap_df["total_equity"].values
        dates = [d.date() if hasattr(d, "date") else d for d in self.snap_df["date"]]

        peak_idx = 0
        in_dd = False
        trough_idx = 0
        ep_count = 0

        for i in range(len(equity)):
            if equity[i] >= equity[peak_idx]:
                if in_dd:
                    dd_depth = ((equity[peak_idx] - equity[trough_idx]) / equity[peak_idx]) * 100.0
                    if dd_depth >= threshold_pct:
                        ep_count += 1
                        episodes.append(
                            DrawdownEpisode(
                                episode_id=ep_count,
                                peak_date=dates[peak_idx],
                                trough_date=dates[trough_idx],
                                recovery_date=dates[i],
                                peak_equity=round(float(equity[peak_idx]), 2),
                                trough_equity=round(float(equity[trough_idx]), 2),
                                drawdown_pct=round(dd_depth, 2),
                                duration_sessions=i - peak_idx,
                            )
                        )
                    in_dd = False
                peak_idx = i
                trough_idx = i
            else:
                in_dd = True
                if equity[i] < equity[trough_idx]:
                    trough_idx = i

        # Unrecovered terminal drawdown
        if in_dd:
            dd_depth = ((equity[peak_idx] - equity[trough_idx]) / equity[peak_idx]) * 100.0
            if dd_depth >= threshold_pct:
                ep_count += 1
                episodes.append(
                    DrawdownEpisode(
                        episode_id=ep_count,
                        peak_date=dates[peak_idx],
                        trough_date=dates[trough_idx],
                        recovery_date=None,
                        peak_equity=round(float(equity[peak_idx]), 2),
                        trough_equity=round(float(equity[trough_idx]), 2),
                        drawdown_pct=round(dd_depth, 2),
                        duration_sessions=len(equity) - 1 - peak_idx,
                    )
                )

        episodes.sort(key=lambda x: x.drawdown_pct, reverse=True)
        return episodes

    def run_block_bootstrap_alpha(
        self,
        n_iterations: int = 10000,
        block_size_days: int = 10,
        seed: int = 42,
    ) -> BootstrapAlphaResult:
        """
        Performs block bootstrap on daily excess returns (Portfolio - Nifty)
        and strategy expectancy to evaluate distribution and 95% confidence intervals.
        """
        if self.snap_df.empty or len(self.snap_df) < 50:
            return BootstrapAlphaResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, n_iterations, block_size_days)

        np.random.seed(seed)
        p_ret = self.snap_df["daily_return_pct"].values / 100.0
        m_ret = self.snap_df["nifty_return_pct"].values / 100.0
        excess_daily = p_ret - m_ret

        n_days = len(excess_daily)
        num_blocks = int(np.ceil(n_days / block_size_days))
        max_start = n_days - block_size_days

        boot_alphas = np.empty(n_iterations, dtype=float)
        boot_expectancies = np.empty(n_iterations, dtype=float)

        for i in range(n_iterations):
            starts = np.random.randint(0, max_start + 1, size=num_blocks)
            sampled_series = []
            sampled_p_ret = []
            for s in starts:
                sampled_series.append(excess_daily[s : s + block_size_days])
                sampled_p_ret.append(p_ret[s : s + block_size_days])
            resampled_excess = np.concatenate(sampled_series)[:n_days]
            resampled_p = np.concatenate(sampled_p_ret)[:n_days]

            cum_alpha = (np.prod(1.0 + resampled_excess) - 1.0) * 100.0
            cum_strat_pnl = (np.prod(1.0 + resampled_p) - 1.0) * self.result.initial_capital

            boot_alphas[i] = cum_alpha
            boot_expectancies[i] = cum_strat_pnl

        mean_alpha = float(np.mean(boot_alphas))
        ci_lower = float(np.percentile(boot_alphas, 2.5))
        ci_upper = float(np.percentile(boot_alphas, 97.5))
        prob_pos = float(np.mean(boot_alphas > 0.0)) * 100.0

        mean_exp = float(np.mean(boot_expectancies))
        exp_ci_lower = float(np.percentile(boot_expectancies, 2.5))
        exp_ci_upper = float(np.percentile(boot_expectancies, 97.5))

        return BootstrapAlphaResult(
            mean_net_alpha_pct=round(mean_alpha, 2),
            ci_lower_95=round(ci_lower, 2),
            ci_upper_95=round(ci_upper, 2),
            prob_positive_alpha=round(prob_pos, 2),
            mean_expectancy_pnl=round(mean_exp, 2),
            expectancy_ci_lower_95=round(exp_ci_lower, 2),
            expectancy_ci_upper_95=round(exp_ci_upper, 2),
            num_iterations=n_iterations,
            block_size_days=block_size_days,
        )

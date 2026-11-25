"""
SignalForge — Phase 36C: Quantitative Risk & Beta Measurement Engine
====================================================================
File: src/strategy/strategy_36c/risk_engine.py

Calculates rolling portfolio beta to Nifty 50, sector concentration (HHI),
tracking error, information ratio, and daily MTM drawdown dynamics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.strategy_36c.rebalance_simulator import DailyPortfolioSnapshot


@dataclass(frozen=True)
class RiskMetrics36C:
    """Comprehensive risk metrics for Phase 36C strategy."""
    mean_rolling_beta: float
    min_rolling_beta: float
    max_rolling_beta: float
    final_rolling_beta: float
    tracking_error_pct: float
    information_ratio: float
    annualized_portfolio_vol_pct: float
    annualized_nifty_vol_pct: float
    portfolio_sharpe: float
    nifty_sharpe: float
    max_drawdown_pct: float
    mean_cash_pct: float


class RiskEngine36C:
    """
    Computes portfolio risk and benchmark comparison metrics for Phase 36C.
    """

    def __init__(
        self,
        snapshots: List[DailyPortfolioSnapshot],
        annual_rf_rate: float = 0.062,
    ) -> None:
        self.snapshots = snapshots
        self.annual_rf_rate = annual_rf_rate
        self.df = pd.DataFrame([s.__dict__ for s in snapshots])
        if not self.df.empty:
            self.df["date"] = pd.to_datetime(self.df["date"])
            self.df.set_index("date", inplace=True)

    def compute_rolling_beta(self, window: int = 60) -> pd.Series:
        """Calculates rolling window OLS beta against Nifty 50."""
        if len(self.df) < window:
            return pd.Series(dtype=float)

        p_ret = self.df["daily_return_pct"] / 100.0
        m_ret = self.df["nifty_return_pct"] / 100.0

        cov = p_ret.rolling(window=window).cov(m_ret)
        var_m = m_ret.rolling(window=window).var()

        beta = cov / var_m
        return beta.dropna()

    def compute_all_metrics(self) -> RiskMetrics36C:
        """Computes comprehensive risk and benchmark statistics."""
        if self.df.empty or len(self.df) < 60:
            return RiskMetrics36C(
                mean_rolling_beta=0.0,
                min_rolling_beta=0.0,
                max_rolling_beta=0.0,
                final_rolling_beta=0.0,
                tracking_error_pct=0.0,
                information_ratio=0.0,
                annualized_portfolio_vol_pct=0.0,
                annualized_nifty_vol_pct=0.0,
                portfolio_sharpe=0.0,
                nifty_sharpe=0.0,
                max_drawdown_pct=0.0,
                mean_cash_pct=100.0,
            )

        p_ret = self.df["daily_return_pct"] / 100.0
        m_ret = self.df["nifty_return_pct"] / 100.0

        p_vol = float(p_ret.std() * np.sqrt(252) * 100.0)
        m_vol = float(m_ret.std() * np.sqrt(252) * 100.0)

        diff_ret = p_ret - m_ret
        te = float(diff_ret.std() * np.sqrt(252) * 100.0)

        total_sessions = len(self.df)
        p_total_ret = (self.df["total_equity"].iloc[-1] / self.df["total_equity"].iloc[0]) - 1.0
        m_total_ret = (self.df["nifty_close"].iloc[-1] / self.df["nifty_close"].iloc[0]) - 1.0

        ann_p_ret = ((1.0 + p_total_ret) ** (252.0 / total_sessions)) - 1.0
        ann_m_ret = ((1.0 + m_total_ret) ** (252.0 / total_sessions)) - 1.0

        ir = ((ann_p_ret - ann_m_ret) / (te / 100.0)) if te > 0 else 0.0

        p_sharpe = ((ann_p_ret - self.annual_rf_rate) / (p_vol / 100.0)) if p_vol > 0 else 0.0
        m_sharpe = ((ann_m_ret - self.annual_rf_rate) / (m_vol / 100.0)) if m_vol > 0 else 0.0

        rolling_beta = self.compute_rolling_beta(window=60)
        mean_b = float(rolling_beta.mean()) if not rolling_beta.empty else 0.0
        min_b = float(rolling_beta.min()) if not rolling_beta.empty else 0.0
        max_b = float(rolling_beta.max()) if not rolling_beta.empty else 0.0
        final_b = float(rolling_beta.iloc[-1]) if not rolling_beta.empty else 0.0

        max_dd = float(self.df["drawdown_pct"].max())
        mean_cash = float(((self.df["cash"] / self.df["total_equity"]) * 100.0).mean())

        return RiskMetrics36C(
            mean_rolling_beta=round(mean_b, 3),
            min_rolling_beta=round(min_b, 3),
            max_rolling_beta=round(max_b, 3),
            final_rolling_beta=round(final_b, 3),
            tracking_error_pct=round(te, 2),
            information_ratio=round(ir, 3),
            annualized_portfolio_vol_pct=round(p_vol, 2),
            annualized_nifty_vol_pct=round(m_vol, 2),
            portfolio_sharpe=round(p_sharpe, 2),
            nifty_sharpe=round(m_sharpe, 2),
            max_drawdown_pct=round(max_dd, 2),
            mean_cash_pct=round(mean_cash, 2),
        )

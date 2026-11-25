"""
SignalForge — Phase 33A: Strategy Research Lab Configurations
=============================================================
File: src/strategy/strategy_research_lab/config.py

Defines data classes, enums, and configurations for:
  - Five Strategy Candidates (S1-S5)
  - Exit Reasons
  - Risk Tiers (E1, E2, E3)
  - Portfolio Execution Constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StrategyID(str, Enum):
    """Identifier for the 5 independent research strategies."""
    STRATEGY_1_TREND_PULLBACK = "Strategy 1 — Trend Pullback"
    STRATEGY_2_DONCHIAN_BREAKOUT = "Strategy 2 — Donchian Breakout"
    STRATEGY_3_RELATIVE_STRENGTH = "Strategy 3 — Relative Strength Momentum"
    STRATEGY_4_MEAN_REVERSION = "Strategy 4 — Trend-Conditioned Mean Reversion"
    STRATEGY_5_VOLATILITY_CONTRACTION = "Strategy 5 — Volatility Contraction Breakout"


class ExitReason(str, Enum):
    """Categorized exit reason for research trades."""
    PROFIT_TARGET = "PROFIT_TARGET"
    TRAILING_STOP = "TRAILING_STOP"
    PROTECTIVE_STOP = "PROTECTIVE_STOP"
    TIME_STOP = "TIME_STOP"
    REBALANCE_EXIT = "REBALANCE_EXIT"
    END_OF_DATA_LIQUIDATION = "END_OF_DATA_LIQUIDATION"


class RiskTier(str, Enum):
    """Risk allocation tiers."""
    E1 = "E1 (1%)"
    E2 = "E2 (2%)"
    E3 = "E3 (3%)"

    @property
    def risk_fraction(self) -> float:
        if self == RiskTier.E1:
            return 0.01
        elif self == RiskTier.E2:
            return 0.02
        elif self == RiskTier.E3:
            return 0.03
        return 0.02


@dataclass(frozen=True)
class StrategyCandidateConfig:
    """Strategy specific parameters."""
    strategy_id: StrategyID
    description: str
    stop_atr_mult: float = 2.0
    max_hold_bars: int = 10
    
    # S1 specific
    s1_rsi_min: float = 40.0
    s1_rsi_max: float = 60.0
    s1_target_atr_mult: float = 3.0
    
    # S2 specific
    s2_breakout_bars: int = 20
    s2_volume_mult: float = 1.5
    s2_trailing_low_bars: int = 10
    
    # S3 specific
    s3_lookback_bars: int = 60
    s3_top_percentile: float = 0.80  # Top 20%
    s3_exit_percentile: float = 0.50  # Below 50%
    
    # S4 specific
    s4_rsi_oversold: float = 30.0
    s4_bb_period: int = 20
    s4_bb_std: float = 2.0
    s4_max_hold_bars: int = 5
    
    # S5 specific
    s5_bb_period: int = 20
    s5_bb_std: float = 2.0
    s5_bb_width_lookback: int = 120
    s5_bb_width_pct_thresh: float = 0.20  # Bottom 20%
    s5_breakout_bars: int = 20
    s5_trailing_low_bars: int = 10


@dataclass(frozen=True)
class StrategyLabConfig:
    """Master research lab execution configuration."""
    initial_capital: float = 100000.0
    max_concurrent_positions: int = 2
    execution_slippage_bps: float = 5.0  # 5 bps per execution leg
    execution_spread_bps: float = 0.0
    default_stop_loss_atr_mult: float = 2.0
    symbol_sector_map: Dict[str, str] = field(default_factory=dict)
    symbol_isin_map: Dict[str, str] = field(default_factory=dict)


DEFAULT_STRATEGY_CONFIGS: Dict[StrategyID, StrategyCandidateConfig] = {
    StrategyID.STRATEGY_1_TREND_PULLBACK: StrategyCandidateConfig(
        strategy_id=StrategyID.STRATEGY_1_TREND_PULLBACK,
        description="Buy strong stocks pulling back to EMA20 during uptrend, target 1.5R, max 10 sessions.",
        stop_atr_mult=2.0,
        max_hold_bars=10,
        s1_rsi_min=40.0,
        s1_rsi_max=60.0,
        s1_target_atr_mult=3.0,
    ),
    StrategyID.STRATEGY_2_DONCHIAN_BREAKOUT: StrategyCandidateConfig(
        strategy_id=StrategyID.STRATEGY_2_DONCHIAN_BREAKOUT,
        description="Donchian 20-session breakout with 1.5x volume expansion under positive Nifty trend, trailing 10-session low exit.",
        stop_atr_mult=2.0,
        max_hold_bars=10,
        s2_breakout_bars=20,
        s2_volume_mult=1.5,
        s2_trailing_low_bars=10,
    ),
    StrategyID.STRATEGY_3_RELATIVE_STRENGTH: StrategyCandidateConfig(
        strategy_id=StrategyID.STRATEGY_3_RELATIVE_STRENGTH,
        description="Relative strength momentum top 20% of 60-day returns with SMA50/200 filter, exit below 50th percentile rank.",
        stop_atr_mult=2.0,
        max_hold_bars=10,
        s3_lookback_bars=60,
        s3_top_percentile=0.80,
        s3_exit_percentile=0.50,
    ),
    StrategyID.STRATEGY_4_MEAN_REVERSION: StrategyCandidateConfig(
        strategy_id=StrategyID.STRATEGY_4_MEAN_REVERSION,
        description="Trend-conditioned mean reversion: Close>SMA200, RSI<30, Close<BB Lower with bullish confirmation, exit at BB Middle.",
        stop_atr_mult=2.0,
        max_hold_bars=5,
        s4_rsi_oversold=30.0,
        s4_bb_period=20,
        s4_bb_std=2.0,
        s4_max_hold_bars=5,
    ),
    StrategyID.STRATEGY_5_VOLATILITY_CONTRACTION: StrategyCandidateConfig(
        strategy_id=StrategyID.STRATEGY_5_VOLATILITY_CONTRACTION,
        description="Volatility contraction breakout: BB width in bottom 20% of trailing 120 sessions, 20-day high breakout with volume, trailing exit.",
        stop_atr_mult=2.0,
        max_hold_bars=10,
        s5_bb_period=20,
        s5_bb_std=2.0,
        s5_bb_width_lookback=120,
        s5_bb_width_pct_thresh=0.20,
        s5_breakout_bars=20,
        s5_trailing_low_bars=10,
    ),
}

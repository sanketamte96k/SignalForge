"""
SignalForge — Phase 34A: Strategy Configuration & Parameter Definitions
=======================================================================
File: src/strategy/strategy_34a/config.py

Defines configuration data structures, enums for Experiment components A-E,
risk tiers E1-E3, exit reasons, and portfolio execution parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class WeeklyTrendFilter(str, Enum):
    """Experiment A: Weekly Trend Direction Filters (using completed weekly bars)."""
    NONE = "none"
    A1_CLOSE_GT_WEMA10 = "a1_close_gt_wema10"
    A2_CLOSE_GT_WEMA20 = "a2_close_gt_wema20"
    A3_CLOSE_GT_WEMA30 = "a3_close_gt_wema30"
    A4_WEMA10_GT_WEMA20 = "a4_wema10_gt_wema20"


class DailyMomentumFilter(str, Enum):
    """Experiment B: Daily Momentum Confirmation Filters."""
    NONE = "none"
    B1_CLOSE_GT_EMA20_AND_EMA20_GT_EMA50 = "b1_close_gt_ema20_and_ema20_gt_ema50"
    B2_CLOSE_GT_EMA20_AND_RSI14_GT_50 = "b2_close_gt_ema20_and_rsi14_gt_50"
    B3_EMA20_GT_EMA50_AND_RSI_RANGE = "b3_ema20_gt_ema50_and_rsi_range"


class RSPeriod(int, Enum):
    """Experiment C: Relative Strength Lookback Sessions vs Nifty 50."""
    NONE = 0
    C1_RS20 = 20
    C2_RS40 = 40
    C3_RS60 = 60


class VolumeThreshold(float, Enum):
    """Experiment D: Relative Volume Multiplier vs 20-Day SMA Volume."""
    NONE = 0.0
    D1_VOL12 = 1.2
    D2_VOL15 = 1.5


class CombinedConfigID(str, Enum):
    """Experiment E: Pre-defined Combined Configurations."""
    CFG1_BALANCED = "CFG-1"
    CFG2_HIGH_MOMENTUM = "CFG-2"
    CFG3_FAST_REACTIVE = "CFG-3"
    CFG4_TREND_CONSERVATIVE = "CFG-4"


class RiskTier(float, Enum):
    """Position Risk Fraction Tiers."""
    E1 = 0.01  # 1% risk per trade
    E2 = 0.02  # 2% risk per trade
    E3 = 0.03  # 3% risk per trade


class ExitReason(str, Enum):
    """Exit classification reasons."""
    PROTECTIVE_STOP = "protective_stop"          # 2.0 ATR initial stop
    TREND_DETERIORATION = "trend_deterioration"  # Daily Close < EMA 20
    TIME_STOP = "time_stop"                      # Max 10 bars held
    END_OF_DATA_LIQUIDATION = "end_of_data"      # Backtest window EOD liquidation


@dataclass
class Strategy34AConfig:
    """Complete parameter specification for Phase 34A Multi-Timeframe Strategy."""
    # Portfolio capital & risk
    initial_capital: float = 100_000.0
    max_concurrent_positions: int = 2
    risk_per_trade: float = 0.02  # Default E2: 2%
    risk_tier: RiskTier = RiskTier.E2

    # Stop Loss & Holding Parameters
    atr_stop_multiplier: float = 2.0
    max_holding_bars: int = 10
    exit_on_ema20_break: bool = True  # Trend deterioration exit

    # Execution Friction
    execution_slippage_bps: float = 5.0
    use_stress_costs: bool = True  # ₹317/cr stress schedule vs ₹307/cr official

    # Multi-Timeframe Component Selection
    weekly_filter: WeeklyTrendFilter = WeeklyTrendFilter.A2_CLOSE_GT_WEMA20
    daily_filter: DailyMomentumFilter = DailyMomentumFilter.B2_CLOSE_GT_EMA20_AND_RSI14_GT_50
    rs_period: RSPeriod = RSPeriod.C1_RS20
    volume_threshold: VolumeThreshold = VolumeThreshold.D1_VOL12

    # Identification
    config_id: str = "CUSTOM"
    description: str = "Phase 34A Multi-Timeframe Momentum"

    # Symbol mappings
    symbol_sector_map: Dict[str, str] = field(default_factory=dict)
    symbol_isin_map: Dict[str, str] = field(default_factory=dict)


def get_combined_config(cfg_id: CombinedConfigID, risk_tier: RiskTier = RiskTier.E2, use_stress: bool = True) -> Strategy34AConfig:
    """Builds pre-defined Experiment E configurations."""
    if cfg_id == CombinedConfigID.CFG1_BALANCED:
        return Strategy34AConfig(
            config_id=cfg_id.value,
            description="CFG-1: Balanced (W-EMA20, Close>EMA20 & RSI>50, RS20, Vol1.2x)",
            weekly_filter=WeeklyTrendFilter.A2_CLOSE_GT_WEMA20,
            daily_filter=DailyMomentumFilter.B2_CLOSE_GT_EMA20_AND_RSI14_GT_50,
            rs_period=RSPeriod.C1_RS20,
            volume_threshold=VolumeThreshold.D1_VOL12,
            risk_per_trade=risk_tier.value,
            risk_tier=risk_tier,
            use_stress_costs=use_stress,
        )
    elif cfg_id == CombinedConfigID.CFG2_HIGH_MOMENTUM:
        return Strategy34AConfig(
            config_id=cfg_id.value,
            description="CFG-2: High Momentum (W-EMA10, Close>EMA20 & EMA20>EMA50, RS20, Vol1.5x)",
            weekly_filter=WeeklyTrendFilter.A1_CLOSE_GT_WEMA10,
            daily_filter=DailyMomentumFilter.B1_CLOSE_GT_EMA20_AND_EMA20_GT_EMA50,
            rs_period=RSPeriod.C1_RS20,
            volume_threshold=VolumeThreshold.D2_VOL15,
            risk_per_trade=risk_tier.value,
            risk_tier=risk_tier,
            use_stress_costs=use_stress,
        )
    elif cfg_id == CombinedConfigID.CFG3_FAST_REACTIVE:
        return Strategy34AConfig(
            config_id=cfg_id.value,
            description="CFG-3: Fast Reactive (W-EMA10>W-EMA20, Close>EMA20 & RSI>50, RS40, Vol1.2x)",
            weekly_filter=WeeklyTrendFilter.A4_WEMA10_GT_WEMA20,
            daily_filter=DailyMomentumFilter.B2_CLOSE_GT_EMA20_AND_RSI14_GT_50,
            rs_period=RSPeriod.C2_RS40,
            volume_threshold=VolumeThreshold.D1_VOL12,
            risk_per_trade=risk_tier.value,
            risk_tier=risk_tier,
            use_stress_costs=use_stress,
        )
    elif cfg_id == CombinedConfigID.CFG4_TREND_CONSERVATIVE:
        return Strategy34AConfig(
            config_id=cfg_id.value,
            description="CFG-4: Trend Conservative (W-EMA30, EMA20>EMA50 & 50<=RSI<=70, RS60, Vol1.5x)",
            weekly_filter=WeeklyTrendFilter.A3_CLOSE_GT_WEMA30,
            daily_filter=DailyMomentumFilter.B3_EMA20_GT_EMA50_AND_RSI_RANGE,
            rs_period=RSPeriod.C3_RS60,
            volume_threshold=VolumeThreshold.D2_VOL15,
            risk_per_trade=risk_tier.value,
            risk_tier=risk_tier,
            use_stress_costs=use_stress,
        )
    raise ValueError(f"Unknown config ID: {cfg_id}")

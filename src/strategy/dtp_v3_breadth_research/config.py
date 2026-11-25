"""
SignalForge — Phase 32J.8: Market Breadth Participation Configuration
======================================================================
File: src/strategy/dtp_v3_breadth_research/config.py

Defines configuration parameters and enums for Phase 32J.8 Market Breadth Research:
  - Baseline: Fixed Max 2 with Rising SMA100 (Phase 32J.7 top performer)
  - Pre-registered Breadth Indicators (A, B, C, D, E) and Fixed Thresholds
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.strategy.dtp_v3_position_limits.config import (
    DTPV3PositionLimitsConfig,
    FixedLimitMode,
    DynamicLimitMode,
)


class BreadthFilterMode(str, Enum):
    """Pre-registered market breadth filter variations tested in Phase 32J.8."""
    # Baseline: Phase 32J.7 Top Performer
    BASELINE_RISING_SMA100 = "BASELINE_RISING_SMA100"        # Nifty Close > SMA100 AND SMA100[t] > SMA100[t-1]

    # Indicator A: Percentage of stocks above 50 EMA
    A_EMA50_40 = "A_EMA50_40"                                # Breadth >= 40%
    A_EMA50_50 = "A_EMA50_50"                                # Breadth >= 50%
    A_EMA50_60 = "A_EMA50_60"                                # Breadth >= 60%

    # Indicator B: Percentage of stocks above 100 SMA
    B_SMA100_40 = "B_SMA100_40"                              # Breadth >= 40%
    B_SMA100_50 = "B_SMA100_50"                              # Breadth >= 50%
    B_SMA100_60 = "B_SMA100_60"                              # Breadth >= 60%

    # Indicator C: Percentage of stocks with rising 50 EMA
    C_RISE50_40 = "C_RISE50_40"                              # Breadth >= 40%
    C_RISE50_50 = "C_RISE50_50"                              # Breadth >= 50%
    C_RISE50_60 = "C_RISE50_60"                              # Breadth >= 60%

    # Indicator D: Percentage of stocks with positive 20-session returns
    D_RET20_40 = "D_RET20_40"                                # Breadth >= 40%
    D_RET20_50 = "D_RET20_50"                                # Breadth >= 50%
    D_RET20_60 = "D_RET20_60"                                # Breadth >= 60%

    # Indicator E: Advance-Decline Ratio
    E_ADR_080 = "E_ADR_080"                                  # ADR >= 0.80
    E_ADR_100 = "E_ADR_100"                                  # ADR >= 1.00
    E_ADR_120 = "E_ADR_120"                                  # ADR >= 1.20

    # Combinations
    COMBO_BEST_TWO = "COMBO_BEST_TWO"                        # Best two breadth filters combined


@dataclass(frozen=True)
class DTPV3BreadthResearchConfig(DTPV3PositionLimitsConfig):
    """
    Configuration container for DTP-V3 Market Breadth Research.
    Inherits frozen parameters from DTPV3PositionLimitsConfig with Fixed Max 2 default.
    """
    name: str = "DTP-V3-Breadth-Research"
    description: str = "DTP-V3 Fixed Max 2 with Market Breadth Participation Filters"

    # Breadth Filter Selection
    breadth_filter_mode: BreadthFilterMode = BreadthFilterMode.BASELINE_RISING_SMA100

    # Baseline limits
    fixed_limit_mode: FixedLimitMode = FixedLimitMode.A2_MAX_2
    dynamic_limit_mode: DynamicLimitMode = DynamicLimitMode.NONE
    apply_a2_risk_overlay: bool = False

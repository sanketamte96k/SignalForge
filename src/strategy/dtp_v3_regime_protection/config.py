"""
SignalForge — Phase 32J.7: Market Regime Protection Configuration
==================================================================
File: src/strategy/dtp_v3_regime_protection/config.py

Defines configuration containers and enums for Phase 32J.7 Market Regime Protection:
  - Baseline: Fixed Max 2 with NIFTY_SMA100
  - Experiment A: Market Trend Strength Filters (A1, A2, A3, A4)
  - Experiment B: Market Volatility Filters (B1, B2, B3)
  - Experiment C: Sideways Market Filters (C1, C2, C3, C4)
  - Experiment D: Two-Filter Combination
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.strategy.dtp_v3_position_limits.config import (
    DTPV3PositionLimitsConfig,
    FixedLimitMode,
    DynamicLimitMode,
    MarketZone,
)


class RegimeProtectionFilterMode(str, Enum):
    """Market regime filter variations tested in Phase 32J.7."""
    # Baseline
    BASELINE_SMA100 = "BASELINE_SMA100"                      # Fixed Max 2: Nifty Close > SMA100

    # Experiment A: Trend Strength Filters
    A1_ADX20 = "A1_ADX20"                                    # Nifty 50 ADX(14) >= 20
    A2_ADX25 = "A2_ADX25"                                    # Nifty 50 ADX(14) >= 25
    A3_RISING_SMA100 = "A3_RISING_SMA100"                    # Nifty 50 Close > rising SMA100
    A4_SMA100_ADX20 = "A4_SMA100_ADX20"                      # Nifty 50 Close > SMA100 AND ADX(14) >= 20

    # Experiment B: Volatility Filters (Evaluated as overlays on Fixed Max 2 SMA100 baseline)
    B1_NATR_P75 = "B1_NATR_P75"                              # ATR(14)/Close < trailing 60-session 75th percentile
    B2_NATR_P90 = "B2_NATR_P90"                              # ATR(14)/Close < trailing 60-session 90th percentile
    B3_ABS_RET_P90 = "B3_ABS_RET_P90"                        # Daily |Return| < trailing 60-session 90th percentile

    # Experiment B (Standalone Variants - Without SMA100)
    B1_ALONE = "B1_ALONE"                                    # NATR < P75 alone
    B2_ALONE = "B2_ALONE"                                    # NATR < P90 alone
    B3_ALONE = "B3_ALONE"                                    # Daily |Return| < P90 alone

    # Experiment C: Sideways Market Filters
    C1_SMA100_RISING = "C1_SMA100_RISING"                    # Nifty Close > SMA100 AND SMA100 slope > 0
    C2_SMA100_ADX20 = "C2_SMA100_ADX20"                      # Nifty Close > SMA100 AND ADX(14) >= 20
    C3_SMA100_DIST1PCT = "C3_SMA100_DIST1PCT"                # Nifty Close > SMA100 AND dist > 1%
    C4_SMA100_ADX20_RISING = "C4_SMA100_ADX20_RISING"        # Nifty Close > SMA100 AND ADX(14) >= 20 AND slope > 0

    # Experiment D: Combinations
    D_COMBINATION = "D_COMBINATION"                          # Best trend + best volatility filter


@dataclass(frozen=True)
class DTPV3RegimeProtectionConfig(DTPV3PositionLimitsConfig):
    """
    Configuration container for DTP-V3 Market Regime Protection Research.
    Inherits frozen parameters from DTPV3PositionLimitsConfig with Fixed Max 2 default.
    """
    name: str = "DTP-V3-Regime-Protection"
    description: str = "DTP-V3 Fixed Max 2 with Market Regime Protection Filters"

    # Regime Protection Filter Selection
    regime_protection_mode: RegimeProtectionFilterMode = RegimeProtectionFilterMode.BASELINE_SMA100

    # Fixed Limit Mode is strictly Fixed Max 2
    fixed_limit_mode: FixedLimitMode = FixedLimitMode.A2_MAX_2
    dynamic_limit_mode: DynamicLimitMode = DynamicLimitMode.NONE
    apply_a2_risk_overlay: bool = False

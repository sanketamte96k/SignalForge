"""
SignalForge — Phase 32J.5: Dynamic Concurrent Position Limit Configuration
==========================================================================
File: src/strategy/dtp_v3_position_limits/config.py

Defines configuration parameters, enums, and data models for DTP-V3 with
Dynamic Concurrent Position Limits:
  - Experiment A: Fixed Position Limits (A1: 3 positions, A2: 2 positions, A3: 1 position)
  - Experiment B: Dynamic Position Limits based on Nifty 50 100-day SMA:
      * B1: Normal (>2%) -> 3, Caution (0-2%) -> 2, Weak (<0%) -> 1
      * B2: Normal (>2%) -> 3, Caution (0-2%) -> 1, Weak (<0%) -> 1
      * B3: Normal (>2%) -> 3, Caution (0-2%) -> 2, Weak (<0%) -> 0
  - Experiment C: A2 Risk Overlay (50% risk discount in Caution zone) combined with position limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)


class FixedLimitMode(int, Enum):
    """Fixed concurrent position limit variations (Experiment A)."""
    A1_MAX_3 = 3     # Baseline: Maximum 3 positions
    A2_MAX_2 = 2     # Maximum 2 positions
    A3_MAX_1 = 1     # Maximum 1 position


class DynamicLimitMode(str, Enum):
    """Dynamic position limit modes based on Nifty 50 100-day SMA (Experiment B)."""
    NONE = "NONE"    # Uses fixed limit
    B1 = "B1"        # Normal (>2%): 3, Caution (0-2%): 2, Weak (<0%): 1
    B2 = "B2"        # Normal (>2%): 3, Caution (0-2%): 1, Weak (<0%): 1
    B3 = "B3"        # Normal (>2%): 3, Caution (0-2%): 2, Weak (<0%): 0


class MarketZone(str, Enum):
    """Nifty 50 proximity zone relative to 100-day SMA."""
    NORMAL = "NORMAL"    # Nifty > 2% above 100-day SMA
    CAUTION = "CAUTION"  # Nifty between 0% and 2% above 100-day SMA
    WEAK = "WEAK"        # Nifty below 100-day SMA


@dataclass(frozen=True)
class DTPV3PositionLimitsConfig(DTPV3Config):
    """
    Configuration container for DTP-V3 with Dynamic Position Limits.
    Inherits all frozen parameters from DTPV3Config and adds limit control settings.
    """
    name: str = "DTP-V3-PositionLimits"
    description: str = "DTP-V3 with Dynamic Concurrent Position Limits (Phase 32J.5)"

    # Experiment A: Fixed Position Limits
    fixed_limit_mode: FixedLimitMode = FixedLimitMode.A1_MAX_3

    # Experiment B: Dynamic Position Limits
    dynamic_limit_mode: DynamicLimitMode = DynamicLimitMode.NONE

    # Experiment C: Phase 32J.4 A2 Risk Overlay (50% risk discount when in Caution zone)
    apply_a2_risk_overlay: bool = False
    caution_risk_reduction_pct: float = 0.50

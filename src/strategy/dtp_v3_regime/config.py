"""
SignalForge — Phase 32J.3.1: DTP-V3 Market Regime Filter Configuration
========================================================================
File: src/strategy/dtp_v3_regime/config.py

Defines configuration parameters, enums, and data models for DTP-V3 with
Market Regime Trend Filters:
  - Variation A: NONE (Original DTP-V3 baseline)
  - Variation B: NIFTY_SMA200 (Nifty 50 Close > 200-day SMA)
  - Variation C: NIFTY_SMA100 (Nifty 50 Close > 100-day SMA)
  - Variation D: NIFTY_SMA200_TREND (Nifty 50 Close > 200-day SMA & 200-day SMA rising)

Completely isolated from DTP-V1, DTP-V2, and frozen DTP-V3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)


class RegimeFilterMode(str, Enum):
    """Market regime filter variations tested in Phase 32J.3.1."""
    NONE = "NONE"                                    # Variation A: Original DTP-V3 (No filter)
    NIFTY_SMA200 = "NIFTY_SMA200"                    # Variation B: Nifty 50 Close > 200-day SMA
    NIFTY_SMA100 = "NIFTY_SMA100"                    # Variation C: Nifty 50 Close > 100-day SMA
    NIFTY_SMA200_TREND = "NIFTY_SMA200_TREND"        # Variation D: Nifty 50 Close > 200-day SMA & SMA200 rising


@dataclass(frozen=True)
class DTPV3RegimeConfig(DTPV3Config):
    """
    Configuration container for DTP-V3 with Market Regime Filter.
    Inherits all frozen parameters from DTPV3Config and adds the regime filter mode.
    """
    name: str = "DTP-V3-Regime"
    description: str = "DTP-V3 with Nifty 50 Trend Regime Filter"

    # Market Regime Filter Selection
    regime_filter_mode: RegimeFilterMode = RegimeFilterMode.NONE

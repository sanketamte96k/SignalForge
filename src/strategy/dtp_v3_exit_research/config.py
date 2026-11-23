"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Configuration
================================================================
File: src/strategy/dtp_v3_exit_research/config.py

Defines configuration and enums for Phase 32J.3.2 Trailing Exit & Profit Protection:
  - Method A: EXISTING_EXIT (Current DTP-V3 exit)
  - Method B: BREAKEVEN_ONLY (Move stop to entry price at +1.0R, no trailing ATR)
  - Method C: ATR_TRAILING (At +1.0R, activate 2x ATR trailing stop from close)
  - Method D: CHANDELIER_HIGHEST_CLOSE (At +1.0R, trail at Highest Close - 2x ATR)
  - Method E: PARTIAL_PROFIT_BOOKING (At +1.5R, exit 50% shares, trail remainder with existing stop)

Completely isolated from DTP-V1, DTP-V2, and frozen DTP-V3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    OrderAction,
)
from src.strategy.dtp_v3_regime.config import DTPV3RegimeConfig, RegimeFilterMode


class ExitResearchMethod(str, Enum):
    """Exit methods evaluated in Phase 32J.3.2."""
    EXISTING_EXIT = "EXISTING_EXIT"                       # Method A: Current DTP-V3 exit
    BREAKEVEN_ONLY = "BREAKEVEN_ONLY"                     # Method B: Stop to entry price at +1R
    ATR_TRAILING = "ATR_TRAILING"                         # Method C: 2x ATR trailing from close at +1R
    CHANDELIER_HIGHEST_CLOSE = "CHANDELIER_HIGHEST_CLOSE" # Method D: Highest close - 2x ATR at +1R
    PARTIAL_PROFIT_BOOKING = "PARTIAL_PROFIT_BOOKING"     # Method E: 50% exit at +1.5R, trail rest


@dataclass(frozen=True)
class DTPV3ExitResearchConfig(DTPV3RegimeConfig):
    """
    Configuration container for DTP-V3 Exit Research.
    Inherits all frozen parameters and NIFTY_SMA100 filter mode from DTPV3RegimeConfig.
    """
    name: str = "DTP-V3-Exit-Research"
    description: str = "DTP-V3 with NIFTY_SMA100 Filter and Alternative Exit Methods"

    # Default to NIFTY_SMA100 as mandated by Phase 32J.3.2 protocol
    regime_filter_mode: RegimeFilterMode = RegimeFilterMode.NIFTY_SMA100

    # Exit Research Method
    exit_method: ExitResearchMethod = ExitResearchMethod.EXISTING_EXIT

    # Exit Parameter Details
    breakeven_r_mult: float = 1.0
    trailing_activation_r_mult: float = 1.0
    trailing_atr_mult: float = 2.0
    partial_profit_r_mult: float = 1.5
    partial_profit_pct: float = 0.50

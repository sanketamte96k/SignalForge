"""
SignalForge — Phase 32J.4: Smart Portfolio Risk Management Configuration
========================================================================
File: src/strategy/dtp_v3_portfolio_risk/config.py

Defines configuration parameters, enums, and data models for DTP-V3 with
Smart Portfolio Risk Management Overlays:
  - Experiment A: Nifty Market Weakness Exposure Control (A1: None, A2: <=2%, A3: <=3%)
  - Experiment B: Sector Concentration Limits (B1: 40%, B2: 30%, B3: 25%)
  - Experiment C: India VIX Volatility Control (C1: None, C2: >80th percentile, C3: >90th percentile)
  - Combined Experiments: Best of A + Best of B

Completely isolated from DTP-V1, DTP-V2, DTP-V3, and earlier research tracks.
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


class NiftyWeaknessMode(str, Enum):
    """Nifty 50 weakness exposure control variations (Experiment A)."""
    A1_NONE = "A1_NONE"                    # Baseline: No additional exposure control
    A2_WITHIN_2PCT = "A2_WITHIN_2PCT"      # When Nifty > SMA100 but <= 2% above: 50% risk reduction
    A3_WITHIN_3PCT = "A3_WITHIN_3PCT"      # When Nifty > SMA100 but <= 3% above: 50% risk reduction


class SectorLimitMode(str, Enum):
    """Portfolio equity sector concentration limits (Experiment B)."""
    B1_NONE_40PCT = "B1_NONE_40PCT"        # Baseline: 40% sector allocation cap
    B2_CAP_30PCT = "B2_CAP_30PCT"          # Max 30% of portfolio equity in one sector
    B3_CAP_25PCT = "B3_CAP_25PCT"          # Max 25% of portfolio equity in one sector


class VixControlMode(str, Enum):
    """India VIX volatility-based position sizing (Experiment C)."""
    C1_NONE = "C1_NONE"                    # Baseline: No additional volatility control
    C2_P80_TRAILING_252 = "C2_P80"         # VIX > 252-session 80th percentile: 50% risk reduction
    C3_P90_TRAILING_252 = "C3_P90"         # VIX > 252-session 90th percentile: 50% risk reduction


@dataclass(frozen=True)
class DTPV3PortfolioRiskConfig(DTPV3Config):
    """
    Configuration container for DTP-V3 with Smart Portfolio Risk Overlays.
    Inherits all frozen parameters from DTPV3Config and adds overlay control modes.
    """
    name: str = "DTP-V3-PortfolioRisk"
    description: str = "DTP-V3 with Smart Portfolio Risk Overlays (Phase 32J.4)"

    # Experiment A: Nifty Market Weakness Exposure Control
    nifty_weakness_mode: NiftyWeaknessMode = NiftyWeaknessMode.A1_NONE
    weakness_risk_reduction_pct: float = 0.50  # 50% risk reduction (multiplier = 0.50)

    # Experiment B: Sector Concentration Limits
    sector_limit_mode: SectorLimitMode = SectorLimitMode.B1_NONE_40PCT
    sector_cap_pct: float = 0.40               # 0.40 (B1), 0.30 (B2), 0.25 (B3)

    # Experiment C: India VIX Volatility Control
    vix_control_mode: VixControlMode = VixControlMode.C1_NONE
    vix_risk_reduction_pct: float = 0.50       # 50% risk reduction when threshold breached

    def get_effective_sector_cap(self) -> float:
        """Returns the active sector exposure ceiling."""
        if self.sector_limit_mode == SectorLimitMode.B2_CAP_30PCT:
            return 0.30
        elif self.sector_limit_mode == SectorLimitMode.B3_CAP_25PCT:
            return 0.25
        return 0.40

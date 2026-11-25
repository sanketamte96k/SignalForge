"""
SignalForge — Phase 32J.7: Market Regime Protection Research Module
===================================================================
File: src/strategy/dtp_v3_regime_protection/__init__.py

Independent research module testing market regime filters on Fixed Max 2 DTP-V3.
"""

from src.strategy.dtp_v3_regime_protection.config import (
    DTPV3RegimeProtectionConfig,
    RegimeProtectionFilterMode,
)
from src.strategy.dtp_v3_regime_protection.market_filter import (
    NiftyRegimeProtectionFilter,
)

__all__ = [
    "DTPV3RegimeProtectionConfig",
    "RegimeProtectionFilterMode",
    "NiftyRegimeProtectionFilter",
]

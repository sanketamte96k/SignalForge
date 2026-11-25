"""
SignalForge — Phase 32J.8: Market Breadth Participation Research Module
======================================================================
File: src/strategy/dtp_v3_breadth_research/__init__.py

Independent research module testing market breadth participation filters
on Fixed Max 2 DTP-V3 with Rising SMA100 baseline.
"""

from src.strategy.dtp_v3_breadth_research.config import (
    BreadthFilterMode,
    DTPV3BreadthResearchConfig,
)
from src.strategy.dtp_v3_breadth_research.breadth_engine import (
    MarketBreadthEngine,
)

__all__ = [
    "BreadthFilterMode",
    "DTPV3BreadthResearchConfig",
    "MarketBreadthEngine",
]

"""
SignalForge — Phase 33B: S5 Forensic Research Module
====================================================
Package: src/strategy/s5_forensic_research
"""

from src.strategy.s5_forensic_research.config import (
    FORENSIC_HYPOTHESIS_CONFIGS,
    S5ForensicConfig,
    S5HypothesisID,
)
from src.strategy.s5_forensic_research.forensic_simulator import (
    run_s5_forensic_simulation,
)

__all__ = [
    "S5HypothesisID",
    "S5ForensicConfig",
    "FORENSIC_HYPOTHESIS_CONFIGS",
    "run_s5_forensic_simulation",
]

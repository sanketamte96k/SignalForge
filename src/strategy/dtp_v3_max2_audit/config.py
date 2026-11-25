"""
SignalForge — Phase 32J.6: Fixed Max 2 Independent Robustness Audit Package
===========================================================================
Package: src/strategy/dtp_v3_max2_audit
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from src.strategy.dtp_v3_position_limits.config import (
    DTPV3PositionLimitsConfig,
    FixedLimitMode,
    DynamicLimitMode,
    MarketZone,
    OrderAction,
    DTPExitReason,
)


class EntryPriorityMode(str, Enum):
    """
    Deterministic Entry Priority Modes for Section 7 Audit:
      - ORIGINAL: Historical default deterministic priority (signal priority score + alphabetical tie-break).
      - CHOP_STRENGTH: Strongest trend first (lowest Choppiness Index at entry).
      - REVERSE_ALPHA: Reverse alphabetical symbol tie-breaker (neutral tie-break).
    """
    ORIGINAL = "ORIGINAL"
    CHOP_STRENGTH = "CHOP_STRENGTH"
    REVERSE_ALPHA = "REVERSE_ALPHA"


@dataclass(frozen=True)
class DTPMax2AuditConfig(DTPV3PositionLimitsConfig):
    """
    Configuration extension for Phase 32J.6 Robustness Audit.
    Maintains all frozen DTP-V3 / Phase 32J.5 parameters.
    """
    entry_priority_mode: EntryPriorityMode = EntryPriorityMode.ORIGINAL
    excluded_symbols: Tuple[str, ...] = field(default_factory=tuple)
    excluded_sectors: Tuple[str, ...] = field(default_factory=tuple)

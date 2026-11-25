"""
SignalForge — Phase 32J.6: Fixed Max 2 Independent Robustness Audit Tests
=========================================================================
"""

import pytest
from src.strategy.dtp_v3_max2_audit.config import DTPMax2AuditConfig, EntryPriorityMode
from src.strategy.dtp_v3_position_limits.config import FixedLimitMode, DynamicLimitMode


def test_audit_config_defaults():
    cfg = DTPMax2AuditConfig()
    assert cfg.entry_priority_mode == EntryPriorityMode.ORIGINAL
    assert cfg.excluded_symbols == ()
    assert cfg.excluded_sectors == ()
    assert cfg.max_concurrent_positions == 3
    assert cfg.risk_fraction_per_trade == 0.01


def test_entry_priority_modes():
    assert EntryPriorityMode.ORIGINAL.value == "ORIGINAL"
    assert EntryPriorityMode.CHOP_STRENGTH.value == "CHOP_STRENGTH"
    assert EntryPriorityMode.REVERSE_ALPHA.value == "REVERSE_ALPHA"

    cfg = DTPMax2AuditConfig(entry_priority_mode=EntryPriorityMode.CHOP_STRENGTH)
    assert cfg.entry_priority_mode == EntryPriorityMode.CHOP_STRENGTH


def test_immutability_of_prior_phases():
    from src.strategy.dtp_v3.config import DTPV3Config
    from src.strategy.dtp_v3_position_limits.config import DTPV3PositionLimitsConfig

    v3_cfg = DTPV3Config()
    v3_lim_cfg = DTPV3PositionLimitsConfig()
    assert v3_cfg.initial_stop_atr_mult == 2.0
    assert v3_lim_cfg.max_allowable_drawdown_pct == 0.15

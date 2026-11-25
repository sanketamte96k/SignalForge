"""
Unit Tests for DTP-V3 Market Regime Protection Module
=====================================================
File: tests/test_strategy_dtp_v3_regime_protection.py
"""

from datetime import date
import pytest

from src.strategy.dtp_v3_position_limits.config import FixedLimitMode
from src.strategy.dtp_v3_regime_protection.config import (
    DTPV3RegimeProtectionConfig,
    RegimeProtectionFilterMode,
)
from src.strategy.dtp_v3_regime_protection.market_filter import (
    NiftyRegimeProtectionFilter,
)


def test_regime_protection_config_defaults():
    cfg = DTPV3RegimeProtectionConfig()
    assert cfg.name == "DTP-V3-Regime-Protection"
    assert cfg.regime_protection_mode == RegimeProtectionFilterMode.BASELINE_SMA100
    assert cfg.fixed_limit_mode == FixedLimitMode.A2_MAX_2
    assert cfg.risk_fraction_per_trade == 0.01


def test_nifty_regime_protection_filter_initialization():
    nifty_filter = NiftyRegimeProtectionFilter()
    assert nifty_filter._daily_nifty is not None
    assert len(nifty_filter._daily_nifty) == 739

    # Check indicators on a known date: 2017-01-02
    ind = nifty_filter.get_indicators(date(2017, 1, 2))
    assert "close" in ind
    assert "sma100" in ind
    assert "adx14" in ind
    assert "natr" in ind
    assert "natr_p75" in ind
    assert "abs_ret_p90" in ind
    assert not any(v is None for v in ind.values())


def test_regime_filter_modes_causality():
    nifty_filter = NiftyRegimeProtectionFilter()

    # 2017-01-02: Nifty close was 8179.20, SMA100 was 8474.26 (Close < SMA100)
    perm_base, msg_base, _ = nifty_filter.is_entry_permitted(date(2017, 1, 2), RegimeProtectionFilterMode.BASELINE_SMA100)
    assert perm_base is False
    assert "Blocked" in msg_base

    # 2017-03-01: Bull market, Nifty > SMA100
    perm_bull, msg_bull, ind = nifty_filter.is_entry_permitted(date(2017, 3, 1), RegimeProtectionFilterMode.BASELINE_SMA100)
    assert perm_bull is True
    assert "Permitted" in msg_bull

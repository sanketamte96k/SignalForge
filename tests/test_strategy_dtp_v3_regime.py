"""
Unit tests for DTP-V3 Market Regime Filter Package (Phase 32J.3.1).
"""

from datetime import date
import pytest

from src.strategy.dtp_v3_regime.config import DTPV3RegimeConfig, RegimeFilterMode
from src.strategy.dtp_v3_regime.market_filter import NiftyMarketFilter


def test_dtp_v3_regime_config():
    cfg = DTPV3RegimeConfig(regime_filter_mode=RegimeFilterMode.NIFTY_SMA200)
    assert cfg.name == "DTP-V3-Regime"
    assert cfg.regime_filter_mode == RegimeFilterMode.NIFTY_SMA200
    assert cfg.use_chop_filter is True
    assert cfg.require_upper_half_close is True


def test_nifty_market_filter_none():
    nmf = NiftyMarketFilter()
    d = date(2017, 1, 2)
    permitted, msg, meta = nmf.is_entry_permitted(d, RegimeFilterMode.NONE)
    assert permitted is True
    assert meta["mode"] == "NONE"


def test_nifty_market_filter_causal_warmup():
    nmf = NiftyMarketFilter()
    d = date(2017, 1, 2)
    # Check that day 1 of 2017 has valid non-NaN moving averages
    permitted, msg, meta = nmf.is_entry_permitted(d, RegimeFilterMode.NIFTY_SMA200)
    assert meta["sma200"] > 0
    assert meta["sma100"] > 0
    assert "nifty_close" in meta


def test_nifty_market_filter_modes():
    nmf = NiftyMarketFilter()
    # Test on a known date in 2017 bull market: e.g. 2017-06-01
    d_bull = date(2017, 6, 1)
    p_b, msg_b, _ = nmf.is_entry_permitted(d_bull, RegimeFilterMode.NIFTY_SMA200)
    p_c, msg_c, _ = nmf.is_entry_permitted(d_bull, RegimeFilterMode.NIFTY_SMA100)
    p_d, msg_d, _ = nmf.is_entry_permitted(d_bull, RegimeFilterMode.NIFTY_SMA200_TREND)
    assert p_b is True
    assert p_c is True
    assert p_d is True

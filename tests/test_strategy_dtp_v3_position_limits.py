"""
Unit tests for DTP-V3 Dynamic Concurrent Position Limits (Phase 32J.5)
=====================================================================
File: tests/test_strategy_dtp_v3_position_limits.py
"""

from datetime import date
import pytest

from src.strategy.dtp_v3_position_limits.config import (
    DTPV3PositionLimitsConfig,
    DynamicLimitMode,
    FixedLimitMode,
    MarketZone,
)
from src.strategy.dtp_v3_position_limits.market_filter import NiftyPositionLimitsFilter
from src.strategy.dtp_v3_position_limits.portfolio_rules import DTPPositionLimitsTracker
from src.strategy.dtp_v3_position_limits.risk_manager import calculate_position_limit_sizing


def test_position_limits_config():
    cfg = DTPV3PositionLimitsConfig(
        fixed_limit_mode=FixedLimitMode.A2_MAX_2,
        dynamic_limit_mode=DynamicLimitMode.B1,
        apply_a2_risk_overlay=True,
    )
    assert cfg.fixed_limit_mode == FixedLimitMode.A2_MAX_2
    assert cfg.dynamic_limit_mode == DynamicLimitMode.B1
    assert cfg.apply_a2_risk_overlay is True


def test_nifty_filter_zone_and_dynamic_limits():
    """Verify zone classification and dynamic limits."""
    nifty_filter = NiftyPositionLimitsFilter()

    # Test date 2017-01-02 (early 2017)
    d = date(2017, 1, 2)
    zone, close, sma100, dist = nifty_filter.evaluate_market_zone(d)
    assert zone in [MarketZone.NORMAL, MarketZone.CAUTION, MarketZone.WEAK]

    # Verify B1 limits
    lim_b1, z_b1, _, _ = nifty_filter.get_active_position_limit(d, DynamicLimitMode.B1)
    if z_b1 == MarketZone.NORMAL:
        assert lim_b1 == 3
    elif z_b1 == MarketZone.CAUTION:
        assert lim_b1 == 2
    else:
        assert lim_b1 == 1

    # Verify B2 limits
    lim_b2, z_b2, _, _ = nifty_filter.get_active_position_limit(d, DynamicLimitMode.B2)
    if z_b2 == MarketZone.NORMAL:
        assert lim_b2 == 3
    elif z_b2 == MarketZone.CAUTION:
        assert lim_b2 == 1
    else:
        assert lim_b2 == 1

    # Verify B3 limits
    lim_b3, z_b3, _, _ = nifty_filter.get_active_position_limit(d, DynamicLimitMode.B3)
    if z_b3 == MarketZone.NORMAL:
        assert lim_b3 == 3
    elif z_b3 == MarketZone.CAUTION:
        assert lim_b3 == 2
    else:
        assert lim_b3 == 0


def test_portfolio_limits_tracker_enforces_limits():
    """Verify that tracker rejects entries when active_position_limit is reached."""
    tracker = DTPPositionLimitsTracker(initial_capital=100000.0)

    # Limit = 2
    tracker.open_position(
        symbol="INFY",
        entry_price=100.0,
        shares=100,
        stop_price=95.0,
        r_distance=5.0,
        entry_date=date(2017, 1, 2),
        order_id="ORD_1",
    )
    assert tracker.position_count == 1

    # Second trade permitted under limit = 2
    can_open, _ = tracker.can_open_position(
        symbol="TCS",
        entry_price=100.0,
        proposed_shares=100,
        active_position_limit=2,
    )
    assert can_open is True

    tracker.open_position(
        symbol="TCS",
        entry_price=100.0,
        shares=100,
        stop_price=95.0,
        r_distance=5.0,
        entry_date=date(2017, 1, 2),
        order_id="ORD_2",
    )
    assert tracker.position_count == 2

    # Third trade rejected under limit = 2
    can_open_3, reason_3 = tracker.can_open_position(
        symbol="WIPRO",
        entry_price=100.0,
        proposed_shares=100,
        active_position_limit=2,
    )
    assert can_open_3 is False
    assert "Position limit reached (2/2)" in reason_3

    # But permitted under limit = 3
    can_open_3_with_limit_3, _ = tracker.can_open_position(
        symbol="WIPRO",
        entry_price=100.0,
        proposed_shares=100,
        active_position_limit=3,
    )
    assert can_open_3_with_limit_3 is True


def test_a2_risk_overlay_sizing():
    """Verify that risk multiplier reduces shares correctly."""
    equity = 100000.0
    cash = 100000.0
    entry_price = 100.0
    stop_price = 95.0  # Stop distance = 5.0

    cfg = DTPV3PositionLimitsConfig(risk_fraction_per_trade=0.02)

    # Full risk
    shares_full, _ = calculate_position_limit_sizing(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        risk_multiplier=1.0,
        config=cfg,
    )

    # 50% discount
    shares_discount, _ = calculate_position_limit_sizing(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        risk_multiplier=0.50,
        config=cfg,
    )

    assert shares_full == 331  # Capped by 33.3% position allocation cap
    assert shares_discount == 200  # ₹1,000 budget / 5 = 200
    assert shares_discount < shares_full

"""
Unit tests for DTP-V3 Smart Portfolio Risk Management (Phase 32J.4)
==================================================================
File: tests/test_strategy_dtp_v3_portfolio_risk.py
"""

from datetime import date
import pytest

from src.strategy.dtp_v3_portfolio_risk.config import (
    DTPV3PortfolioRiskConfig,
    NiftyWeaknessMode,
    SectorLimitMode,
    VixControlMode,
)
from src.strategy.dtp_v3_portfolio_risk.portfolio_rules import DTPPortfolioRiskTracker
from src.strategy.dtp_v3_portfolio_risk.risk_manager import calculate_portfolio_risk_position_size


def test_portfolio_risk_config():
    cfg = DTPV3PortfolioRiskConfig(
        nifty_weakness_mode=NiftyWeaknessMode.A2_WITHIN_2PCT,
        sector_limit_mode=SectorLimitMode.B2_CAP_30PCT,
        vix_control_mode=VixControlMode.C1_NONE,
    )
    assert cfg.nifty_weakness_mode == NiftyWeaknessMode.A2_WITHIN_2PCT
    assert cfg.sector_limit_mode == SectorLimitMode.B2_CAP_30PCT
    assert cfg.get_effective_sector_cap() == 0.30
    assert cfg.vix_control_mode == VixControlMode.C1_NONE


def test_nifty_weakness_risk_multiplier_sizing():
    """Verify that a 50% risk discount correctly reduces approved shares."""
    equity = 100000.0
    cash = 100000.0
    entry_price = 100.0
    stop_price = 95.0  # Stop distance = 5.0

    # Base risk = 2% (₹2,000 budget / 5 = 400 shares)
    # Full risk (multiplier = 1.0)
    cfg = DTPV3PortfolioRiskConfig(risk_fraction_per_trade=0.02)
    shares_full, _ = calculate_portfolio_risk_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        risk_multiplier=1.0,
        config=cfg,
    )

    # Discounted risk (multiplier = 0.50 -> effective risk = 1.0%, budget = ₹1,000 / 5 = 200 shares)
    shares_discount, _ = calculate_portfolio_risk_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        risk_multiplier=0.50,
        config=cfg,
    )

    assert shares_full == 331  # Capped by 33.3% position allocation cap: floor(33333 / 100.5) = 331
    # For discounted: 200 shares * 100 = ₹20,000 (well within 33.3% cap)
    assert shares_discount == 200
    assert shares_discount < shares_full


def test_sector_concentration_sizing_reduction_and_rejection():
    """Verify sector caps at 40%, 30%, and 25% correctly constrain position sizes."""
    equity = 100000.0
    cash = 100000.0
    entry_price = 500.0
    stop_price = 490.0  # Stop distance = 10.0 (risk budget = ₹3,000 -> 300 shares)

    cfg = DTPV3PortfolioRiskConfig(risk_fraction_per_trade=0.03)

    # 1. Existing sector exposure = ₹20,000
    # Under B1 (40% cap = ₹40,000): remaining budget = ₹20,000 -> shares = floor(20000 / 502.5) = 39 shares
    shares_b1, reason_b1 = calculate_portfolio_risk_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        sector="Banking",
        current_sector_exposure=20000.0,
        sector_cap_pct=0.40,
        config=cfg,
    )
    assert shares_b1 == 39

    # Under B2 (30% cap = ₹30,000): remaining budget = ₹10,000 -> shares = floor(10000 / 502.5) = 19 shares
    shares_b2, reason_b2 = calculate_portfolio_risk_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        sector="Banking",
        current_sector_exposure=20000.0,
        sector_cap_pct=0.30,
        config=cfg,
    )
    assert shares_b2 == 19
    assert shares_b2 < shares_b1

    # Under B3 (25% cap = ₹25,000): remaining budget = ₹5,000 -> shares = floor(5000 / 502.5) = 9 shares
    # 9 shares * ₹500 = ₹4,500 < ₹5,000 min notional floor -> REJECTED!
    shares_b3, reason_b3 = calculate_portfolio_risk_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_price,
        stop_price=stop_price,
        sector="Banking",
        current_sector_exposure=20000.0,
        sector_cap_pct=0.25,
        config=cfg,
    )
    assert shares_b3 == 0
    assert "floor" in reason_b3.lower() or "rejected" in reason_b3.lower()


def test_portfolio_risk_tracker_sector_rejection():
    """Verify DTPPortfolioRiskTracker enforces sector constraints."""
    tracker = DTPPortfolioRiskTracker(initial_capital=100000.0, sector_cap_pct=0.25)

    # Open a position in IT of ₹20,000
    tracker.open_position(
        symbol="INFY",
        entry_price=1000.0,
        shares=20,
        stop_price=950.0,
        r_distance=50.0,
        entry_date=date(2017, 1, 2),
        order_id="ORD_1",
        sector="IT",
    )

    # Try to open another IT position of ₹10,000 (total = ₹30,000 > 25% of ₹100,000)
    can_open, reason = tracker.can_open_position(
        symbol="TCS",
        entry_price=1000.0,
        proposed_shares=10,
        sector="IT",
    )
    assert not can_open
    assert "Sector exposure for IT would exceed 25%" in reason

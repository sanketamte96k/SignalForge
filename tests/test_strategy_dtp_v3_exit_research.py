"""
Unit tests for DTP-V3 Exit Research Package (Phase 32J.3.2).
"""

from datetime import date
import pytest

from src.strategy.dtp_v3.config import DTPExitReason
from src.strategy.dtp_v3_exit_research.config import (
    DTPV3ExitResearchConfig,
    ExitResearchMethod,
    RegimeFilterMode,
)
from src.strategy.dtp_v3_exit_research.signal_engine import (
    DTPExitPositionState,
    evaluate_research_exit_conditions,
)


def test_exit_research_config():
    cfg = DTPV3ExitResearchConfig(exit_method=ExitResearchMethod.BREAKEVEN_ONLY)
    assert cfg.name == "DTP-V3-Exit-Research"
    assert cfg.exit_method == ExitResearchMethod.BREAKEVEN_ONLY
    assert cfg.regime_filter_mode == RegimeFilterMode.NIFTY_SMA100


def test_breakeven_only_exit_logic():
    cfg = DTPV3ExitResearchConfig(exit_method=ExitResearchMethod.BREAKEVEN_ONLY)
    pos = DTPExitPositionState(
        symbol="TEST",
        entry_date=date(2017, 1, 2),
        entry_price=100.0,
        quantity=100,
        initial_quantity=100,
        initial_stop_price=90.0,
        current_stop_price=90.0,
        r_distance=10.0,
    )
    # Day 1: high reaches 110 (+1.0R)
    reason, exit_px, msg, partial = evaluate_research_exit_conditions(
        pos=pos,
        current_high=110.5,
        current_low=99.0,
        current_close=105.0,
        current_open=100.0,
        current_atr=2.0,
        current_ema50=95.0,
        current_rsi=55.0,
        current_bb_upper=120.0,
        config=cfg,
    )
    assert reason is None
    assert pos.is_breakeven_activated is True
    assert pos.current_stop_price == 100.0  # Stop moved to exact entry price


def test_chandelier_highest_close_logic():
    cfg = DTPV3ExitResearchConfig(exit_method=ExitResearchMethod.CHANDELIER_HIGHEST_CLOSE)
    pos = DTPExitPositionState(
        symbol="TEST",
        entry_date=date(2017, 1, 2),
        entry_price=100.0,
        quantity=100,
        initial_quantity=100,
        initial_stop_price=90.0,
        current_stop_price=90.0,
        r_distance=10.0,
    )
    # Day 1: high reaches 110 (+1.0R), close is 108, atr is 2.0
    reason, exit_px, msg, partial = evaluate_research_exit_conditions(
        pos=pos,
        current_high=110.0,
        current_low=99.0,
        current_close=108.0,
        current_open=101.0,
        current_atr=2.0,
        current_ema50=95.0,
        current_rsi=55.0,
        current_bb_upper=120.0,
        config=cfg,
    )
    assert reason is None
    assert pos.is_trailing_activated is True
    # Chandelier stop = highest close (108) - 2 * 2.0 = 104.0
    assert pos.current_stop_price == 104.0


def test_partial_profit_booking_logic():
    cfg = DTPV3ExitResearchConfig(exit_method=ExitResearchMethod.PARTIAL_PROFIT_BOOKING)
    pos = DTPExitPositionState(
        symbol="TEST",
        entry_date=date(2017, 1, 2),
        entry_price=100.0,
        quantity=100,
        initial_quantity=100,
        initial_stop_price=90.0,
        current_stop_price=90.0,
        r_distance=10.0,
    )
    # Day 1: high reaches 116.0 (+1.6R, triggers +1.5R partial profit)
    reason, exit_px, msg, partial = evaluate_research_exit_conditions(
        pos=pos,
        current_high=116.0,
        current_low=99.0,
        current_close=114.0,
        current_open=101.0,
        current_atr=2.0,
        current_ema50=95.0,
        current_rsi=55.0,
        current_bb_upper=125.0,
        config=cfg,
    )
    assert reason is None
    assert partial is not None
    assert partial["partial_shares"] == 50
    assert partial["partial_reason"] == "PARTIAL_PROFIT_1.5R"
    assert pos.is_partial_taken is True

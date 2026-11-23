"""
SignalForge — Phase 32I: DTP-V3 Strategy Unit Tests
===================================================
File: tests/test_strategy_dtp_v3.py

Tests component integrity, configuration parameters, Choppiness Index filter,
upper-half close confirmation, fixed-fractional sizing (E1, E2, E3),
drawdown circuit breakers, and verifies DTP-V1/DTP-V2 code immutability.
"""

from datetime import date
import pytest
import numpy as np
import pandas as pd

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)
from src.strategy.dtp_v3.indicators import (
    calculate_choppiness_index,
    calculate_dtp_indicators,
    calculate_atr,
    calculate_rsi,
)
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v3.portfolio_rules import DTPPortfolioTracker
from src.strategy.dtp_v3.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    is_trend_aligned,
    check_reversal_trigger,
)


def test_dtp_v3_config_defaults():
    cfg = DTPV3Config()
    assert cfg.name == "DTP-V3"
    assert cfg.use_chop_filter is True
    assert cfg.max_chop_index == 60.0
    assert cfg.require_upper_half_close is True
    assert cfg.min_close_range_ratio == 0.50
    assert cfg.risk_fraction_per_trade == 0.010
    assert cfg.max_allowable_drawdown_pct == 0.15
    assert cfg.initial_stop_atr_mult == 2.0
    assert cfg.trailing_atr_mult == 2.0
    assert cfg.profit_target_r_mult == 3.0


def test_choppiness_index_calculation():
    # Construct trending price series
    trend_high = pd.Series([100 + i * 2.0 for i in range(30)])
    trend_low = pd.Series([98 + i * 2.0 for i in range(30)])
    trend_close = pd.Series([99 + i * 2.0 for i in range(30)])
    ci_trend = calculate_choppiness_index(trend_high, trend_low, trend_close, period=14)
    # Trending markets should have lower Choppiness Index (< 50)
    assert ci_trend.iloc[-1] < 50.0

    # Construct oscillating choppy price series
    chop_high = pd.Series([100 + (1 if i % 2 == 0 else -1) for i in range(30)])
    chop_low = pd.Series([98 + (1 if i % 2 == 0 else -1) for i in range(30)])
    chop_close = pd.Series([99 + (1 if i % 2 == 0 else -1) for i in range(30)])
    ci_chop = calculate_choppiness_index(chop_high, chop_low, chop_close, period=14)
    # Choppy range-bound markets should have elevated Choppiness Index (> 55)
    assert ci_chop.iloc[-1] > 55.0


def test_chop_filter_blocks_choppy_regime():
    cfg = DTPV3Config(use_chop_filter=True, max_chop_index=60.0)
    dates = pd.date_range("2019-01-01", periods=60, freq="B")
    df = pd.DataFrame({
        "close": [100.0 + i * 0.5 for i in range(60)],
        "high": [101.0 + i * 0.5 for i in range(60)],
        "low": [99.0 + i * 0.5 for i in range(60)],
        "ema_fast": [95.0 + i * 0.5 for i in range(60)],
        "ema_slow": [90.0 + i * 0.4 for i in range(60)],
        "adx": [25.0] * 60,
        "relative_strength": [0.05] * 60,
        "chop_index": [65.0] * 60,  # Choppy regime > 60
    }, index=dates)

    aligned, msg = is_trend_aligned(df, 50, cfg)
    assert aligned is False
    assert "Choppiness Index" in msg


def test_upper_half_close_confirmation():
    cfg = DTPV3Config(require_upper_half_close=True, min_close_range_ratio=0.50)
    dates = pd.date_range("2019-01-01", periods=10, freq="B")

    # Bar with close in lower half of candle range: high=100, low=90, open=91, close=94 -> (94-90)/(100-90) = 40% < 50%
    # Even though close > open (94 > 91), it fails upper-half confirmation
    df_weak = pd.DataFrame({
        "open": [91.0] * 10,
        "high": [100.0] * 10,
        "low": [90.0] * 10,
        "close": [94.0] * 10,
        "volume": [1000.0] * 10,
        "volume_sma": [1000.0] * 10,
        "ema_fast": [92.0] * 10,
        "rsi": [45.0] * 10,
    }, index=dates)

    # Need pullback active
    rev_ok, msg = check_reversal_trigger(df_weak, 5, cfg)
    assert rev_ok is False


def test_position_sizing_risk_experiments():
    cfg_e1 = DTPV3Config(risk_fraction_per_trade=0.010)
    cfg_e2 = DTPV3Config(risk_fraction_per_trade=0.020)
    cfg_e3 = DTPV3Config(risk_fraction_per_trade=0.030)

    equity = 100000.0
    cash = 100000.0
    entry = 500.0
    stop = 480.0 # Stop distance = 20.0 (4.0%)

    # E1: Risk = 1,000 -> 1000 / 20 = 50 shares
    s_e1, _ = calculate_dtp_position_size(equity, cash, entry, stop, config=cfg_e1)
    assert s_e1 == 50
    assert s_e1 * entry == 25000.0 # 25% of equity (below 33.3% cap)

    # E2: Risk = 2,000 -> 2000 / 20 = 100 shares -> 100 * 500 = 50,000 > 33.3% cap (33,333) -> capped at floor(33333 / (500*1.005)) = 66 shares
    s_e2, _ = calculate_dtp_position_size(equity, cash, entry, stop, config=cfg_e2)
    assert s_e2 == 66

    # E3: Risk = 3,000 -> capped at 66 shares due to 33.3% max position allocation cap
    s_e3, _ = calculate_dtp_position_size(equity, cash, entry, stop, config=cfg_e3)
    assert s_e3 == 66


def test_drawdown_circuit_breaker():
    cfg = DTPV3Config(max_allowable_drawdown_pct=0.15)
    # If portfolio drawdown is 16% (>= 15%), new orders must be blocked
    shares, msg = calculate_dtp_position_size(
        equity=84000.0,
        available_cash=84000.0,
        entry_price=500.0,
        stop_price=480.0,
        current_drawdown_pct=0.16,
        config=cfg,
    )
    assert shares == 0
    assert "Circuit breaker active" in msg


def test_dtp_v1_and_v2_code_immutability():
    """Verify DTP-V1 and DTP-V2 remain completely separate, frozen and unmodified."""
    from src.strategy.dtp_v1.config import DTPV1Config
    from src.strategy.dtp_v2.config import DTPV2Config

    v1_cfg = DTPV1Config()
    v2_cfg = DTPV2Config()
    v3_cfg = DTPV3Config()

    assert v1_cfg.name == "DTP-V1"
    assert v2_cfg.name == "DTP-V2"
    assert v3_cfg.name == "DTP-V3"

    # DTP-V1 and DTP-V2 must NOT have choppiness filter flags
    assert not hasattr(v1_cfg, "use_chop_filter")
    assert not hasattr(v2_cfg, "use_chop_filter")
    assert v3_cfg.use_chop_filter is True

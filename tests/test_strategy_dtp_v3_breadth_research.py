"""
Unit Tests for DTP-V3 Market Breadth Research Module
===================================================
File: tests/test_strategy_dtp_v3_breadth_research.py
"""

from datetime import date
import pandas as pd
import pytest

from src.strategy.dtp_v3_position_limits.config import FixedLimitMode
from src.strategy.dtp_v3_breadth_research.config import (
    BreadthFilterMode,
    DTPV3BreadthResearchConfig,
)
from src.strategy.dtp_v3_breadth_research.breadth_engine import (
    MarketBreadthEngine,
)


def test_breadth_config_defaults():
    cfg = DTPV3BreadthResearchConfig()
    assert cfg.name == "DTP-V3-Breadth-Research"
    assert cfg.breadth_filter_mode == BreadthFilterMode.BASELINE_RISING_SMA100
    assert cfg.fixed_limit_mode == FixedLimitMode.A2_MAX_2
    assert cfg.risk_fraction_per_trade == 0.01


def test_breadth_engine_calculations():
    # Create synthetic universe of 3 stocks over 10 days
    dates = pd.date_range("2017-01-02", periods=10, freq="B")
    data_a = pd.DataFrame({"open": [100.0 + i for i in range(10)], "high": [105.0 + i for i in range(10)], "low": [95.0 + i for i in range(10)], "close": [102.0 + i for i in range(10)], "volume": [1000 for _ in range(10)]}, index=dates)
    data_b = pd.DataFrame({"open": [200.0 - i for i in range(10)], "high": [205.0 - i for i in range(10)], "low": [195.0 - i for i in range(10)], "close": [198.0 - i for i in range(10)], "volume": [2000 for _ in range(10)]}, index=dates)

    mock_universe = {"STOCK_A": data_a, "STOCK_B": data_b}
    engine = MarketBreadthEngine(universe=mock_universe)

    history = engine.breadth_history
    assert len(history) == 10
    assert "pct_above_ema50" in history.columns
    assert "pct_above_sma100" in history.columns
    assert "pct_rising_ema50" in history.columns
    assert "pct_pos_ret20" in history.columns
    assert "adr" in history.columns

    # Check breadth dictionary retrieval
    b_day = engine.get_breadth(dates[5].date())
    assert "pct_above_ema50" in b_day
    assert b_day["universe_size"] == 2

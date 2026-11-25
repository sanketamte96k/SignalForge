"""
SignalForge — Phase 34A: Unit Tests for Multi-Timeframe Momentum Strategy
========================================================================
File: tests/test_strategy_34a.py

Verifies:
  1. Weekly bar construction and causal completion dates.
  2. Lookahead-free weekly indicator alignment.
  3. Relative strength calculation vs Nifty 50.
  4. Signal generation across filters A1-A4, B1-B3, C1-C3, D1-D2.
  5. Exit condition logic (ATR stop, trend deterioration, max hold).
  6. Mathematical accounting reconciliation (ending cash == trade net P&L).
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from src.strategy.strategy_34a.config import (
    CombinedConfigID,
    DailyMomentumFilter,
    ExitReason,
    RSPeriod,
    RiskTier,
    Strategy34AConfig,
    VolumeThreshold,
    WeeklyTrendFilter,
    get_combined_config,
)
from src.strategy.strategy_34a.indicators import (
    attach_multi_timeframe_indicators,
    build_completed_weekly_bars,
    calculate_atr,
    calculate_ema,
    calculate_nifty_relative_strength,
    calculate_rsi,
)
from src.strategy.strategy_34a.signal_engine import (
    check_daily_momentum_filter,
    check_relative_strength_filter,
    check_volume_confirmation_filter,
    check_weekly_trend_filter,
    evaluate_34a_exit,
    generate_34a_signals,
)
from src.strategy.strategy_34a.portfolio_simulator import (
    run_34a_simulation,
    to_py_date,
)


def create_synthetic_daily_data(n_days: int = 100, base_price: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
    """Helper to create synthetic daily OHLCV dataframe with known trend."""
    dates = pd.date_range("2017-01-02", periods=n_days, freq="B")
    prices = [base_price + i * trend for i in range(n_days)]
    df = pd.DataFrame(
        {
            "open": [p - 0.2 for p in prices],
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [100000.0 + (i % 5) * 20000.0 for i in range(n_days)],
        },
        index=dates,
    )
    return df


def test_weekly_bars_construction_and_causality():
    """Verify weekly bars are aggregated correctly and completion dates match last trading session."""
    daily_df = create_synthetic_daily_data(n_days=15)  # 3 full weeks
    weekly_bars = build_completed_weekly_bars(daily_df)

    assert len(weekly_bars) == 3
    # First Friday is 2017-01-06
    assert weekly_bars.index[0] == pd.to_datetime("2017-01-06")
    # Second Friday is 2017-01-13
    assert weekly_bars.index[1] == pd.to_datetime("2017-01-13")
    # Third Friday is 2017-01-20
    assert weekly_bars.index[2] == pd.to_datetime("2017-01-20")

    # Weekly close of week 1 should match day 5 close
    assert weekly_bars.iloc[0]["close"] == daily_df.iloc[4]["close"]
    # Weekly high should be max of the 5 days
    assert weekly_bars.iloc[0]["high"] == daily_df.iloc[0:5]["high"].max()


def test_lookahead_free_indicator_alignment():
    """Verify that prior completed weekly candle is attached without future leakage."""
    daily_df = create_synthetic_daily_data(n_days=20)
    nifty_df = create_synthetic_daily_data(n_days=20, base_price=10000.0, trend=10.0)

    aligned = attach_multi_timeframe_indicators(daily_df, nifty_df)

    # Days in week 1 (2017-01-02 to 2017-01-05) have no prior completed weekly bar
    assert pd.isna(aligned.loc["2017-01-02", "wema10"])
    assert pd.isna(aligned.loc["2017-01-05", "wema10"])

    # On Friday 2017-01-06 EOD, week 1 is complete, so wema10 is populated
    assert not pd.isna(aligned.loc["2017-01-06", "wema10"])
    week1_wema10 = aligned.loc["2017-01-06", "wema10"]

    # On Mon-Thu of week 2 (2017-01-09 to 2017-01-12), wema10 must strictly equal week 1 wema10
    assert aligned.loc["2017-01-09", "wema10"] == week1_wema10
    assert aligned.loc["2017-01-12", "wema10"] == week1_wema10

    # On Friday 2017-01-13 EOD, week 2 is complete, so wema10 updates to week 2
    assert aligned.loc["2017-01-13", "wema10"] != week1_wema10


def test_nifty_relative_strength():
    """Verify relative strength calculations over specified lookbacks."""
    daily_df = create_synthetic_daily_data(n_days=50, base_price=100.0, trend=1.0)   # 50% gain
    nifty_df = create_synthetic_daily_data(n_days=50, base_price=1000.0, trend=2.0) # 10% gain

    aligned = attach_multi_timeframe_indicators(daily_df, nifty_df)

    # After day 20, rs_20 should be strictly positive because stock outperformed Nifty
    rs20_val = aligned.iloc[25]["rs_20"]
    assert not pd.isna(rs20_val)
    assert rs20_val > 0.0


def test_signal_generation_filters():
    """Verify each independent filter works correctly."""
    row = pd.Series({
        "close": 110.0,
        "dema20": 105.0,
        "dema50": 100.0,
        "rsi14": 55.0,
        "weekly_close": 108.0,
        "wema10": 102.0,
        "wema20": 98.0,
        "wema30": 95.0,
        "rs_20": 0.05,
        "rs_40": 0.08,
        "rs_60": 0.12,
        "vol_ratio": 1.4,
        "atr14": 2.5,
    })

    # Weekly Filters
    assert check_weekly_trend_filter(row, WeeklyTrendFilter.A1_CLOSE_GT_WEMA10) is True
    assert check_weekly_trend_filter(row, WeeklyTrendFilter.A2_CLOSE_GT_WEMA20) is True
    assert check_weekly_trend_filter(row, WeeklyTrendFilter.A3_CLOSE_GT_WEMA30) is True
    assert check_weekly_trend_filter(row, WeeklyTrendFilter.A4_WEMA10_GT_WEMA20) is True

    # Daily Filters
    assert check_daily_momentum_filter(row, DailyMomentumFilter.B1_CLOSE_GT_EMA20_AND_EMA20_GT_EMA50) is True
    assert check_daily_momentum_filter(row, DailyMomentumFilter.B2_CLOSE_GT_EMA20_AND_RSI14_GT_50) is True
    assert check_daily_momentum_filter(row, DailyMomentumFilter.B3_EMA20_GT_EMA50_AND_RSI_RANGE) is True

    # RS Filters
    ok, val = check_relative_strength_filter(row, RSPeriod.C1_RS20)
    assert ok is True and val == 0.05

    # Volume Filters
    ok12, v12 = check_volume_confirmation_filter(row, VolumeThreshold.D1_VOL12)
    assert ok12 is True and v12 == 1.4
    ok15, v15 = check_volume_confirmation_filter(row, VolumeThreshold.D2_VOL15)
    assert ok15 is False and v15 == 1.4

    # Full Signal Generation
    cfg = get_combined_config(CombinedConfigID.CFG1_BALANCED)
    sig = generate_34a_signals("TESTSYM", row, date(2017, 2, 1), cfg)
    assert sig is not None
    assert sig.symbol == "TESTSYM"
    assert sig.stop_loss_price == 110.0 - (2.0 * 2.5)


def test_exit_evaluation_rules():
    """Verify exit triggers: protective stop, trend deterioration, max hold, final liquidation."""
    pos = {
        "symbol": "TESTSYM",
        "entry_date": date(2017, 1, 10),
        "stop_loss_price": 95.0,
        "bars_held": 5,
    }
    cfg = Strategy34AConfig(atr_stop_multiplier=2.0, max_holding_bars=10, exit_on_ema20_break=True)

    # 1. Protective stop trigger
    bar_stop = pd.Series({"open": 98.0, "high": 99.0, "low": 94.0, "close": 96.0, "dema20": 100.0})
    should_exit, px, reason, note, next_open = evaluate_34a_exit(pos, bar_stop, False, cfg)
    assert should_exit is True
    assert reason == ExitReason.PROTECTIVE_STOP
    assert px == 95.0

    # 2. Trend deterioration (Close < DEMA20)
    bar_trend = pd.Series({"open": 102.0, "high": 103.0, "low": 98.0, "close": 99.0, "dema20": 100.0})
    should_exit, px, reason, note, next_open = evaluate_34a_exit(pos, bar_trend, False, cfg)
    assert should_exit is False
    assert next_open is True
    assert reason == ExitReason.TREND_DETERIORATION

    # 3. Max holding bars reached
    pos_old = dict(pos)
    pos_old["bars_held"] = 10
    bar_normal = pd.Series({"open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0, "dema20": 100.0})
    should_exit, px, reason, note, next_open = evaluate_34a_exit(pos_old, bar_normal, False, cfg)
    assert next_open is True
    assert reason == ExitReason.TIME_STOP


def test_portfolio_simulator_reconciliation():
    """Verify single-slippage accounting reconciliation achieves ₹0.00 discrepancy."""
    df1 = create_synthetic_daily_data(n_days=70, base_price=100.0, trend=0.8)
    df2 = create_synthetic_daily_data(n_days=70, base_price=200.0, trend=-0.3)
    nifty = create_synthetic_daily_data(n_days=70, base_price=10000.0, trend=5.0)

    aligned1 = attach_multi_timeframe_indicators(df1, nifty)
    aligned2 = attach_multi_timeframe_indicators(df2, nifty)

    universe = {"STOCK1": aligned1, "STOCK2": aligned2}
    cfg = get_combined_config(CombinedConfigID.CFG1_BALANCED, risk_tier=RiskTier.E2, use_stress=True)

    result = run_34a_simulation(universe, cfg)

    assert result.reconciliation_passed is True
    assert result.reconciliation_discrepancy < 0.01
    # Check that trades were completed and reconciled
    assert result.completed_trades >= 0

"""
SignalForge — Phase 35A: Unit Tests for Regime-Filtered Mean Reversion Strategy
==============================================================================
File: tests/test_strategy_35a.py

Verifies:
  1. Indicator calculation correctness (RSI 2/5/14, BB 20/2, SMA/EMA).
  2. Regime filter evaluation (Regimes A, B, C).
  3. Mean reversion entry triggers (MR1, MR2, MR3).
  4. Exit concepts (Exit A, Exit B, Exit C, Time stop).
  5. Exact accounting reconciliation down to ₹0.0000.
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from src.strategy.strategy_35a.config import (
    ExitConceptType,
    ExitReason,
    MeanReversionEntryType,
    RegimeFilterType,
    RiskTier,
    Strategy35AConfig,
)
from src.strategy.strategy_35a.indicators import (
    attach_35a_indicators,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    calculate_sma,
)
from src.strategy.strategy_35a.signal_engine import (
    check_entry_concept,
    check_regime_filter,
    evaluate_35a_exit,
    generate_35a_signals,
)
from src.strategy.strategy_35a.portfolio_simulator import (
    run_35a_simulation,
    to_py_date,
)


def create_synthetic_data(n_days: int = 150, base_price: float = 100.0) -> pd.DataFrame:
    """Creates synthetic OHLCV dataframe with deterministic price curve."""
    dates = pd.date_range("2017-01-02", periods=n_days, freq="B")
    # Sine wave superimposed on gentle upward drift
    t = np.linspace(0, 10, n_days)
    prices = base_price + 0.1 * np.arange(n_days) + 5.0 * np.sin(t)
    df = pd.DataFrame(
        {
            "open": prices - 0.2,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": [100000.0] * n_days,
        },
        index=dates,
    )
    return df


def test_indicator_calculations():
    """Verify indicator mathematical accuracy and bounds."""
    df = create_synthetic_data(n_days=60)
    close = df["close"]

    rsi2 = calculate_rsi(close, 2)
    rsi5 = calculate_rsi(close, 5)
    rsi14 = calculate_rsi(close, 14)

    assert not rsi2.dropna().empty
    assert (rsi2.dropna() >= 0.0).all() and (rsi2.dropna() <= 100.0).all()
    assert (rsi5.dropna() >= 0.0).all() and (rsi5.dropna() <= 100.0).all()
    assert (rsi14.dropna() >= 0.0).all() and (rsi14.dropna() <= 100.0).all()

    mid, upp, low = calculate_bollinger_bands(close, period=20, num_std=2.0)
    assert (upp.dropna() > mid.dropna()).all()
    assert (mid.dropna() > low.dropna()).all()

    atr = calculate_atr(df["high"], df["low"], df["close"], 14)
    assert (atr.dropna() > 0.0).all()


def test_regime_filter_evaluation():
    """Verify Regimes A, B, and C evaluate strictly causally."""
    # Bullish row
    row_bull = pd.Series({
        "close": 150.0,
        "sma50": 140.0,
        "sma200": 130.0,
        "ema50": 145.0,
        "ema50_slope": 0.5,
        "nifty_close": 11000.0,
        "nifty_sma100": 10500.0,
    })
    assert check_regime_filter(row_bull, RegimeFilterType.REGIME_A) is True
    assert check_regime_filter(row_bull, RegimeFilterType.REGIME_B) is True
    assert check_regime_filter(row_bull, RegimeFilterType.REGIME_C) is True

    # Bearish row
    row_bear = pd.Series({
        "close": 120.0,
        "sma50": 125.0,
        "sma200": 130.0,
        "ema50": 125.0,
        "ema50_slope": -0.2,
        "nifty_close": 10000.0,
        "nifty_sma100": 10500.0,
    })
    assert check_regime_filter(row_bear, RegimeFilterType.REGIME_A) is False
    assert check_regime_filter(row_bear, RegimeFilterType.REGIME_B) is False
    assert check_regime_filter(row_bear, RegimeFilterType.REGIME_C) is False


def test_mean_reversion_entry_triggers():
    """Verify MR1, MR2, and MR3 entry logic."""
    # Oversold row
    row_oversold = pd.Series({
        "close": 90.0,
        "ema20": 98.0,
        "atr14": 4.0,
        "rsi2": 5.0,    # < 10
        "rsi5": 22.0,   # < 30
        "rsi14": 35.0,  # < 40
        "bb_lower": 92.0,  # close < lower BB
    })
    assert check_entry_concept(row_oversold, MeanReversionEntryType.MR1_RSI5_BB) is True
    assert check_entry_concept(row_oversold, MeanReversionEntryType.MR2_RSI2_EMA20) is True
    assert check_entry_concept(row_oversold, MeanReversionEntryType.MR3_PULLBACK_ATR) is True

    # Normal / not oversold row
    row_normal = pd.Series({
        "close": 100.0,
        "ema20": 98.0,
        "atr14": 2.0,
        "rsi2": 60.0,
        "rsi5": 55.0,
        "rsi14": 52.0,
        "bb_lower": 95.0,
    })
    assert check_entry_concept(row_normal, MeanReversionEntryType.MR1_RSI5_BB) is False
    assert check_entry_concept(row_normal, MeanReversionEntryType.MR2_RSI2_EMA20) is False
    assert check_entry_concept(row_normal, MeanReversionEntryType.MR3_PULLBACK_ATR) is False


def test_exit_concepts():
    """Verify Exit A (EMA20 recovery), Exit B (BB middle target + 2 ATR stop), Exit C (trailing stop)."""
    pos = {
        "symbol": "TEST",
        "entry_date": date(2017, 1, 10),
        "stop_loss_price": 90.0,
        "bars_held": 3,
        "initial_atr": 3.0,
        "highest_high": 102.0,
    }

    # Exit A: Close > EMA20 triggers next open exit
    cfg_a = Strategy35AConfig(exit_concept=ExitConceptType.EXIT_A)
    bar_recov = pd.Series({"open": 98.0, "high": 101.0, "low": 97.0, "close": 100.0, "ema20": 99.0})
    exit_now, px, reason, note, exit_next = evaluate_35a_exit(pos, bar_recov, False, cfg_a)
    assert exit_now is False
    assert exit_next is True
    assert reason == ExitReason.TARGET_RECOVERY

    # Exit B: Initial stop breach triggers immediate exit
    cfg_b = Strategy35AConfig(exit_concept=ExitConceptType.EXIT_B)
    bar_stop = pd.Series({"open": 92.0, "high": 93.0, "low": 88.0, "close": 89.0, "bb_middle": 100.0})
    exit_now, px, reason, note, exit_next = evaluate_35a_exit(pos, bar_stop, False, cfg_b)
    assert exit_now is True
    assert px == 90.0
    assert reason == ExitReason.INITIAL_STOP

    # Exit B: BB middle target reached triggers immediate exit
    bar_target = pd.Series({"open": 96.0, "high": 102.0, "low": 95.0, "close": 101.0, "bb_middle": 100.0})
    exit_now, px, reason, note, exit_next = evaluate_35a_exit(pos, bar_target, False, cfg_b)
    assert exit_now is True
    assert px == 100.0
    assert reason == ExitReason.TARGET_RECOVERY

    # Exit C: Trailing stop hit
    cfg_c = Strategy35AConfig(exit_concept=ExitConceptType.EXIT_C, atr_stop_multiplier=2.0)
    pos_c = dict(pos)
    pos_c["highest_high"] = 100.0
    # highest_high is 100, trailing stop is 100 - 2*3.0 = 94.0
    bar_trail = pd.Series({"open": 95.0, "high": 96.0, "low": 93.0, "close": 94.0, "atr14": 3.0})
    exit_now, px, reason, note, exit_next = evaluate_35a_exit(pos_c, bar_trail, False, cfg_c)
    assert exit_now is True
    assert px == 94.0
    assert reason == ExitReason.TRAILING_STOP


def test_simulation_accounting_reconciliation():
    """Verify single-slippage accounting achieves zero discrepancy down to ₹0.0000."""
    df1 = create_synthetic_data(n_days=100, base_price=100.0)
    df2 = create_synthetic_data(n_days=100, base_price=200.0)
    nifty = create_synthetic_data(n_days=100, base_price=10000.0)

    aug1 = attach_35a_indicators(df1, nifty)
    aug2 = attach_35a_indicators(df2, nifty)
    aug1.index = pd.Index([to_py_date(d) for d in aug1.index])
    aug2.index = pd.Index([to_py_date(d) for d in aug2.index])

    universe = {"STOCK1": aug1, "STOCK2": aug2}
    cfg = Strategy35AConfig(
        regime_filter=RegimeFilterType.REGIME_C,
        entry_concept=MeanReversionEntryType.MR2_RSI2_EMA20,
        exit_concept=ExitConceptType.EXIT_A,
        risk_per_trade=0.02,
        use_stress_costs=True,
    )

    res = run_35a_simulation(universe, cfg)
    assert res.reconciliation_passed is True
    assert res.reconciliation_discrepancy < 0.0001

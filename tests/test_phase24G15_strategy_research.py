"""
SignalForge Phase 24G.15 — Quantitative Strategy Research Test Suite
====================================================================
Validates indicator calculation fidelity, squeeze detection, multi-timeframe
causal synchronization, and signal generation mechanics for the alternative
strategy hypotheses (Hypotheses A, B, C, and D).
"""

import pytest
import numpy as np
import pandas as pd
from datetime import time as dtime

from research.strategy_evolution_2018.phase24G15_strategy_research.research_hypotheses import (
    calc_ema,
    calc_rsi,
    calc_atr,
    calc_rvol,
    calc_adx,
    build_multi_timeframe_features,
    generate_hypothesis_signals,
    classify_market_regime,
    MarketRegime,
)
from src.backtest.risk_engine_v2 import PositionSide


@pytest.fixture
def sample_ohlcv_1m():
    """Generate 200 synthetic 1-minute OHLCV candles with realistic intraday pattern."""
    dates = pd.date_range("2020-01-02 09:15:00", periods=200, freq="1min")
    np.random.seed(42)
    returns = np.random.normal(0.0001, 0.001, size=len(dates))
    price = 300.0 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame(
        {
            "open": price * (1 + np.random.uniform(-0.0005, 0.0005, size=len(dates))),
            "high": price * (1 + np.random.uniform(0.0005, 0.0015, size=len(dates))),
            "low": price * (1 - np.random.uniform(0.0005, 0.0015, size=len(dates))),
            "close": price,
            "volume": np.random.randint(1000, 10000, size=len(dates)),
        },
        index=dates,
    )
    # Ensure High is highest and Low is lowest
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_indicator_calculations(sample_ohlcv_1m):
    """Verify standard indicator calculation properties."""
    close = sample_ohlcv_1m["close"]
    ema20 = calc_ema(close, 20)
    assert len(ema20) == len(close)
    assert not ema20.isna().all()

    rsi14 = calc_rsi(close, 14)
    assert (rsi14 >= 0.0).all() and (rsi14 <= 100.0).all()

    atr14 = calc_atr(sample_ohlcv_1m, 14)
    assert (atr14 > 0.0).all()

    rvol20 = calc_rvol(sample_ohlcv_1m, 20)
    assert (rvol20 > 0.0).all()

    adx, pdi, mdi = calc_adx(sample_ohlcv_1m, 14)
    assert (adx >= 0.0).all() and (adx <= 100.0).all()
    assert (pdi >= 0.0).all()
    assert (mdi >= 0.0).all()


def test_squeeze_condition_logic():
    """Verify Bollinger Band inside Keltner Channel squeeze detection."""
    # Synthetic flat price creates a squeeze
    dates = pd.date_range("2020-01-02 09:15:00", periods=50, freq="5min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 50,
            "high": [100.2] * 50,
            "low": [99.8] * 50,
            "close": [100.0] * 50,
            "volume": [1000] * 50,
        },
        index=dates,
    )
    # Roll std is 0, so BB upper/lower will be close to 100.0
    # KC upper/lower will be 100 +/- 1.5 * ATR (0.4) = 100.6 and 99.4
    # BB (100, 100) is strictly inside KC (99.4, 100.6) -> Squeeze is True
    roll_mean = df["close"].rolling(20).mean()
    roll_std = df["close"].rolling(20).std().fillna(0.0)
    bb_upper = roll_mean + (2.0 * roll_std)
    bb_lower = roll_mean - (2.0 * roll_std)

    atr = calc_atr(df, 14)
    kc_upper = roll_mean + (1.5 * atr)
    kc_lower = roll_mean - (1.5 * atr)

    in_squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    assert in_squeeze.iloc[-1] is True or in_squeeze.iloc[-1] == 1


def test_multi_timeframe_feature_builder(sample_ohlcv_1m):
    """Verify feature builder outputs all required timeframes."""
    features = build_multi_timeframe_features(sample_ohlcv_1m)
    assert "1m" in features
    assert "5m" in features
    assert "15m" in features
    assert "30m" in features

    assert "ema20" in features["5m"].columns
    assert "in_squeeze" in features["5m"].columns
    assert "trend" in features["15m"].columns
    assert "trend" in features["30m"].columns


def test_hypothesis_signal_invariants(sample_ohlcv_1m):
    """Verify that signal streams conform to structural timing invariants."""
    features = build_multi_timeframe_features(sample_ohlcv_1m)

    for hyp in [
        "HYPOTHESIS_A_TREND_PULLBACK",
        "HYPOTHESIS_B_VOLATILITY_BREAKOUT",
        "HYPOTHESIS_C_MEAN_REVERSION",
        "HYPOTHESIS_D_REGIME_ADAPTIVE",
    ]:
        sig_series = generate_hypothesis_signals(features, hyp)
        assert len(sig_series) == len(sample_ohlcv_1m)
        assert sig_series.index.equals(sample_ohlcv_1m.index)

        # Signals should only be emitted on 5-minute boundaries
        non_null = sig_series.dropna()
        for ts in non_null.index:
            assert ts.minute % 5 == 0, f"Signal emitted off 5m boundary: {ts}"
            assert ts.time() < dtime(15, 15), f"Signal emitted after 15:15: {ts}"
            val = non_null.loc[ts]
            assert val in (PositionSide.LONG, PositionSide.SHORT)

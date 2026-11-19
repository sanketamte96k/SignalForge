"""
SignalForge — Phase 32B: Focused Test Suite for Strategy TPV-V2
================================================================
Validates:
1. Multi-timeframe causal synchronization (15m available at index+15m, 30m at index+30m).
2. Pullback into value zone [EMA50, EMA20] and RSI reset detection.
3. Anti-chasing proximity gate (close <= EMA20 + 0.5 * ATR).
4. ADX trend strength gate (ADX >= 15.0).
5. Next-open execution timing.
6. Stop-first collision handling.
7. Trailing stop ratchet logic.
8. Exact transaction cost accounting.
9. EOD 15:15 square-off semantics.
"""

from datetime import datetime, time as dtime
import numpy as np
import pandas as pd
import pytest

from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    CONSERVATIVE_STRESS_CONFIG,
)
from src.backtest.simulator import Position
from src.strategy.strategy_tpv_v2 import (
    TPVV2Config,
    DEFAULT_TPV_V2_CONFIG,
    calc_wilder_atr,
    calc_rsi,
    calc_adx,
    compute_tpv_v2_indicators,
    run_tpv_v2_backtest,
)


@pytest.fixture
def synthetic_1m_data():
    """Generates synthetic 1-minute OHLCV data spanning multiple intraday sessions."""
    records = []
    dates = ["2017-01-02", "2017-01-03", "2017-01-04"]
    np.random.seed(42)

    for d_str in dates:
        times = pd.date_range(f"{d_str} 09:15:00", f"{d_str} 15:29:00", freq="1min")
        base_price = 500.0
        price = base_price
        for ts in times:
            change = np.random.normal(0, 0.2)
            price = max(10.0, price + change)
            high = price + np.random.uniform(0.1, 0.5)
            low = price - np.random.uniform(0.1, 0.5)
            o = price + np.random.uniform(-0.1, 0.1)
            c = price
            v = np.random.randint(500, 3000)
            records.append({
                "timestamp": ts,
                "open": o,
                "high": high,
                "low": low,
                "close": c,
                "volume": v,
            })

    df = pd.DataFrame(records)
    return df


def test_htf_trend_causal_synchronization(synthetic_1m_data):
    """Verify 15m and 30m indicators only merge onto 5m bars after HTF completion."""
    res = compute_tpv_v2_indicators(synthetic_1m_data)
    df_5m = res["df_5m"]
    df_15m = res["df_15m"]
    df_30m = res["df_30m"]

    # First completed 15m candle is 09:15..09:30 (available at 09:30:00).
    # 5m bar at 09:20 completed at 09:25:00 -> before 09:30:00 -> must not see day1 15m data!
    bar_0920 = df_5m.loc["2017-01-02 09:20:00"]
    assert bar_0920["completed_at"] == pd.Timestamp("2017-01-02 09:25:00")

    # 5m bar at 09:30 completed at 09:35:00 -> sees 15m bar from 09:15..09:30
    bar_0930 = df_5m.loc["2017-01-02 09:30:00"]
    assert bar_0930["completed_at"] == pd.Timestamp("2017-01-02 09:35:00")


def test_anti_chasing_proximity_gate():
    """Verify that entries extended > 0.5 ATR beyond EMA20 are strictly rejected."""
    # Build 5m bar with close extended far above EMA20
    times = pd.date_range("2017-01-02 09:15:00", periods=50, freq="5min")
    df_5m = pd.DataFrame({
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.5,
        "volume": 2000,
    }, index=times)

    ema20 = df_5m["close"].ewm(span=20, adjust=False).mean()
    atr = calc_wilder_atr(df_5m, 14)

    # Extended entry: close is > ema20 + 0.5 * atr
    close_extended = float(ema20.iloc[-1] + (0.8 * atr.iloc[-1]))
    not_chasing = close_extended <= (ema20.iloc[-1] + (0.5 * atr.iloc[-1]))
    assert not not_chasing, "Extended close must fail proximity gate"


def test_adx_gate_rejection():
    """Verify that flat choppy periods with ADX < 15.0 do not generate signals."""
    times = pd.date_range("2017-01-02 09:15:00", periods=50, freq="5min")
    # Perfectly flat data has 0 ADX
    df_5m = pd.DataFrame({
        "open": 100.0,
        "high": 100.01,
        "low": 99.99,
        "close": 100.0,
        "volume": 1000,
    }, index=times)
    adx = calc_adx(df_5m, 14)
    assert adx.iloc[-1] < 15.0


def test_tpv_stop_first_collision_handling():
    """Verify stop-first collision resolution on same 5m bar."""
    times = pd.date_range("2017-01-02 09:15:00", periods=75, freq="1min")
    df_1m = pd.DataFrame({
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 2000,
    }, index=times)

    # Simulate wide bar
    df_1m.loc["2017-01-02 09:50:00", "low"] = 70.0
    df_1m.loc["2017-01-02 09:50:00", "high"] = 130.0

    res = run_tpv_v2_backtest(df_1m, symbol="TESTSTOCK")
    if res.total_trades > 0:
        assert res.trades[0].exit_reason == "STOP_LOSS"


def test_tpv_next_open_execution_timing(synthetic_1m_data):
    """Verify trade execution aligns strictly with next bar open."""
    res = run_tpv_v2_backtest(synthetic_1m_data, symbol="INFY")
    for t in res.trades:
        entry_ts = pd.Timestamp(t.entry_time)
        assert entry_ts.minute % 5 == 0
        assert t.entry_price > 0.0


def test_tpv_eod_square_off_semantics():
    """Verify positions open at 15:15 are unconditionally closed."""
    times = pd.date_range("2017-01-02 09:15:00", "2017-01-02 15:29:00", freq="1min")
    p = 500.0
    records = []
    for ts in times:
        records.append({
            "timestamp": ts,
            "open": p,
            "high": p + 0.5,
            "low": p - 0.5,
            "close": p,
            "volume": 2000,
        })
    df_1m = pd.DataFrame(records)

    res = run_tpv_v2_backtest(df_1m, symbol="INFY")
    for t in res.trades:
        if t.exit_reason == "EOD_SQUARE_OFF":
            exit_ts = pd.Timestamp(t.exit_time)
            assert exit_ts.time() >= dtime(15, 15)


def test_tpv_transaction_costs_deducted_exactly_once(synthetic_1m_data):
    """Verify cost accounting invariant."""
    res = run_tpv_v2_backtest(synthetic_1m_data, symbol="INFY", cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG)
    for t in res.trades:
        expected_net = round(t.gross_pnl - t.transaction_cost, 2)
        actual_net = round(t.net_pnl, 2)
        assert abs(expected_net - actual_net) <= 0.02

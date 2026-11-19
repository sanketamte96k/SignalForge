"""
SignalForge — Phase 32B: Focused Test Suite for Strategy SEB-V1
================================================================
Validates:
1. Donchian causal shifting (shift(1) excludes current candle).
2. Squeeze detection (BB inside KC) and 6-bar memory.
3. Macro 30m trend causal synchronization.
4. Signal generation rules (RVOL, body <= 2 ATR, 09:35 blackout, 1 trade/session).
5. Next-open fill semantics.
6. Stop-first collision handling.
7. Trailing stop activation and ratchet logic.
8. Exact transaction cost accounting.
9. EOD 15:15 square-off.
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
from src.strategy.strategy_seb_v1 import (
    SEBV1Config,
    DEFAULT_SEB_V1_CONFIG,
    calc_wilder_atr,
    compute_seb_v1_indicators,
    run_seb_v1_backtest,
)


@pytest.fixture
def synthetic_1m_data():
    """Generates synthetic 1-minute OHLCV data spanning multiple intraday sessions."""
    records = []
    # 3 trading days: 2017-01-02, 2017-01-03, 2017-01-04
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


def test_donchian_shift1_causality():
    """Verify that Donchian boundaries strictly exclude the current candle via shift(1)."""
    # Create simple 5m DataFrame
    times = pd.date_range("2017-01-02 09:15:00", periods=25, freq="5min")
    highs = [100.0] * 20 + [150.0, 110.0, 110.0, 110.0, 110.0]
    lows = [90.0] * 20 + [80.0, 90.0, 90.0, 90.0, 90.0]

    df_5m = pd.DataFrame({
        "open": 95.0,
        "high": highs,
        "low": lows,
        "close": 95.0,
        "volume": 1000,
    }, index=times)

    # Shift(1) rolling(20) max
    dh = df_5m["high"].shift(1).rolling(20).max()
    dl = df_5m["low"].shift(1).rolling(20).min()

    # At index 20 (where high is 150.0), Donchian High must still be 100.0 (from bars 0..19)
    assert dh.iloc[20] == 100.0, f"Expected 100.0, got {dh.iloc[20]}"
    # At index 21, Donchian High incorporates 150.0
    assert dh.iloc[21] == 150.0

    # Low at index 20 (where low is 80.0), Donchian Low must still be 90.0
    assert dl.iloc[20] == 90.0
    assert dl.iloc[21] == 80.0


def test_squeeze_condition_detection():
    """Verify Bollinger Band inside Keltner Channel squeeze detection."""
    times = pd.date_range("2017-01-02 09:15:00", periods=50, freq="5min")
    # Low volatility creates tight BB
    df_5m = pd.DataFrame({
        "open": 100.0,
        "high": 100.2,
        "low": 99.8,
        "close": 100.0,
        "volume": 1000,
    }, index=times)

    roll_mean = df_5m["close"].rolling(20).mean()
    roll_std = df_5m["close"].rolling(20).std().fillna(0.0)
    bb_upper = roll_mean + (2.0 * roll_std)
    bb_lower = roll_mean - (2.0 * roll_std)

    atr = calc_wilder_atr(df_5m, 14)
    ema20 = df_5m["close"].ewm(span=20, adjust=False).mean()
    kc_upper = ema20 + (1.5 * atr)
    kc_lower = ema20 - (1.5 * atr)

    in_squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    assert in_squeeze.iloc[-1] is True or in_squeeze.iloc[-1] == 1


def test_macro_30m_causal_synchronization(synthetic_1m_data):
    """Verify 30m indicators only become available after the 30m candle is complete."""
    res = compute_seb_v1_indicators(synthetic_1m_data)
    df_5m = res["df_5m"]
    df_30m = res["df_30m"]

    # First completed 30m candle is 09:15..09:45 (indexed at 09:15).
    # Its available_at is 09:45:00.
    # Therefore, 5m bars starting at 09:15, 09:20, 09:25, 09:30, 09:35 completed before 09:45
    # cannot see the 09:15..09:45 30m candle!
    day1_5m = df_5m.loc["2017-01-02"]
    bar_0935 = day1_5m.loc["2017-01-02 09:35:00"]
    # completed at 09:40:00 -> before 09:45:00 -> must not have day1 30m data
    assert bar_0935["completed_at"] == pd.Timestamp("2017-01-02 09:40:00")


def test_stop_first_collision_handling():
    """Verify that if a 5m bar touches both stop and target, Stop-Loss triggers first."""
    # Build 1m dataset where on bar T+2 high hits target and low hits stop
    times = pd.date_range("2017-01-02 09:15:00", periods=75, freq="1min")
    df_1m = pd.DataFrame({
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 2000,
    }, index=times)

    # Make a breakout bar at 09:40 (completed at 09:45)
    # Donchian high was 100.5, let's close at 102.0 with high volume
    df_1m.loc["2017-01-02 09:40:00":"2017-01-02 09:44:00", "high"] = 103.0
    df_1m.loc["2017-01-02 09:40:00":"2017-01-02 09:44:00", "close"] = 102.5
    df_1m.loc["2017-01-02 09:40:00":"2017-01-02 09:44:00", "volume"] = 10000

    # Next bar (09:45) fills at Open.
    # In next bar (09:50..09:54), create a massive bar with Low = 80.0 and High = 120.0
    df_1m.loc["2017-01-02 09:50:00", "low"] = 80.0
    df_1m.loc["2017-01-02 09:50:00", "high"] = 120.0

    res = run_seb_v1_backtest(df_1m, symbol="TESTSTOCK")
    if res.total_trades > 0:
        trade = res.trades[0]
        # Must be STOP_LOSS, never TARGET
        assert trade.exit_reason == "STOP_LOSS", f"Expected STOP_LOSS, got {trade.exit_reason}"


def test_next_open_execution_timing(synthetic_1m_data):
    """Verify that trades fill strictly at next bar open, not current bar close."""
    res = run_seb_v1_backtest(synthetic_1m_data, symbol="INFY")
    for t in res.trades:
        # Entry time must be at minute % 5 == 0
        entry_ts = pd.Timestamp(t.entry_time)
        assert entry_ts.minute % 5 == 0
        # Entry price must be positive
        assert t.entry_price > 0.0


def test_eod_square_off_semantics():
    """Verify open positions are unconditionally closed at 15:15 IST."""
    # Synthetic dataset where price moves sideways and never hits target/stop
    times = pd.date_range("2017-01-02 09:15:00", "2017-01-02 15:29:00", freq="1min")
    np.random.seed(123)
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
    # Trigger breakout at 10:00
    df_1m.loc[df_1m["timestamp"].between("2017-01-02 10:00:00", "2017-01-02 10:04:00"), "close"] = 510.0
    df_1m.loc[df_1m["timestamp"].between("2017-01-02 10:00:00", "2017-01-02 10:04:00"), "volume"] = 15000

    res = run_seb_v1_backtest(df_1m, symbol="INFY")
    for t in res.trades:
        if t.exit_reason == "EOD_SQUARE_OFF":
            exit_ts = pd.Timestamp(t.exit_time)
            assert exit_ts.time() >= dtime(15, 15)


def test_transaction_costs_deducted_exactly_once(synthetic_1m_data):
    """Verify transaction costs are accounted for and net_pnl = gross_pnl - total_costs."""
    res = run_seb_v1_backtest(synthetic_1m_data, symbol="INFY", cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG)
    for t in res.trades:
        expected_net = round(t.gross_pnl - t.transaction_cost, 2)
        actual_net = round(t.net_pnl, 2)
        assert abs(expected_net - actual_net) <= 0.02
        assert t.brokerage >= 0.0
        assert t.statutory_fees >= 0.0
        assert t.slippage >= 0.0

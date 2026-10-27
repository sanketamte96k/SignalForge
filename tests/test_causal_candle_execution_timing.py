"""
Tests for Phase 24G.6: Causal Candle Alignment and Execution-Timing Contracts.

Validates:
1. Multi-timeframe causal completion boundaries (5m, 10m, 15m, 30m).
2. Look-ahead immunity (future candle manipulation does not leak into unfinished bars).
3. Session boundary isolation (no cross-day feature leakage).
4. Missing-minute gap rejection (no stale feature leakage across gaps).
5. Parity between _TimeframeCursor and _completed_state.
6. Next-open vs. same-close execution timing contract in run_backtest.
7. Next-open vs. same-close execution timing contract in run_intraday_backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import (
    IntradayEngineConfig,
    Position,
    run_backtest,
    run_intraday_backtest,
)
from src.data.resampler import resample_ohlcv
from src.strategy.backtest_strategy import (
    StrategyConfig,
    TimeframeState,
    _completed_state,
    _make_cursors,
    calculate_timeframe_indicators,
    create_signal_function,
)


def _make_populated_htf_frame(
    freq: str = "5min",
    start: str = "2024-01-02 09:15:00",
    periods: int = 20,
) -> pd.DataFrame:
    """Create a higher-timeframe DataFrame with pre-populated non-NaN indicator columns."""
    idx = pd.date_range(start, periods=periods, freq=freq)
    closes = [100.0 + i * 2.0 for i in range(periods)]
    return pd.DataFrame(
        {
            "open": [c - 1.0 for c in closes],
            "high": [c + 2.0 for c in closes],
            "low": [c - 2.0 for c in closes],
            "close": closes,
            "volume": [1000.0] * periods,
            "ema20": closes,
            "ema50": [c - 1.0 for c in closes],
            "rsi": [55.0] * periods,
            "atr": [2.0] * periods,
            "rvol": [1.5] * periods,
        },
        index=idx,
    )


# ===========================================================================
# 1. Higher-Timeframe Completion Boundary Tests
# ===========================================================================

@pytest.mark.parametrize(
    "tf, freq, dur_min, pre_ts, at_ts, post_ts",
    [
        ("5m", "5min", 5, "09:19", "09:20", "09:21"),
        ("10m", "10min", 10, "09:24", "09:25", "09:26"),
        ("15m", "15min", 15, "09:29", "09:30", "09:31"),
        ("30m", "30min", 30, "09:44", "09:45", "09:46"),
    ],
)
def test_htf_candle_causal_availability_boundaries(
    tf: str,
    freq: str,
    dur_min: int,
    pre_ts: str,
    at_ts: str,
    post_ts: str,
):
    """
    Higher-timeframe candles are left-labelled (stamped at candle open).
    Therefore, candle [09:15, 09:15+dur) is NOT complete until 09:15+dur.
    - Pre-completion: must return None (no look-ahead).
    - At-completion: must return candle 0.
    - Post-completion: must continue returning candle 0 until next completion.
    """
    frame = _make_populated_htf_frame(freq=freq, periods=10)

    t_pre = pd.Timestamp(f"2024-01-02 {pre_ts}:00")
    t_at = pd.Timestamp(f"2024-01-02 {at_ts}:00")
    t_post = pd.Timestamp(f"2024-01-02 {post_ts}:00")

    # Before completion: must NOT be available
    state_pre = _completed_state(frame, t_pre, use_rvol=False, timeframe=tf)
    assert state_pre is None, f"{tf} candle was accessible at {pre_ts} before completion!"

    # At completion: becomes available
    state_at = _completed_state(frame, t_at, use_rvol=False, timeframe=tf)
    assert state_at is not None, f"{tf} candle should be complete at {at_ts}!"
    expected_c0_close = frame.iloc[0]["close"]
    assert state_at.close == expected_c0_close

    # Post completion: remains candle 0
    state_post = _completed_state(frame, t_post, use_rvol=False, timeframe=tf)
    assert state_post is not None
    assert state_post.close == expected_c0_close


# ===========================================================================
# 2. Look-Ahead Immunity Test
# ===========================================================================

def test_future_candle_mutation_does_not_leak_into_unfinished_state():
    """
    Mutating data in a future bar must NOT change the state evaluated at an earlier bar.
    At 09:18, candle 0 [09:15, 09:20) is not yet complete.
    Mutating candle 0 must have zero effect on state evaluated at 09:18 (which must be None).
    """
    frame_clean = _make_populated_htf_frame(freq="5min", periods=5)
    frame_mutated = frame_clean.copy()
    frame_mutated.iloc[0, frame_mutated.columns.get_loc("close")] = 999999.0

    t_obs = pd.Timestamp("2024-01-02 09:18:00")

    # At 09:18, no 5m candle should be completed in either
    assert _completed_state(frame_clean, t_obs, use_rvol=False, timeframe="5m") is None
    assert _completed_state(frame_mutated, t_obs, use_rvol=False, timeframe="5m") is None

    # At 09:20, the 5m candle IS completed, and the mutated one must reflect the mutation causally
    t_comp = pd.Timestamp("2024-01-02 09:20:00")
    st_clean = _completed_state(frame_clean, t_comp, use_rvol=False, timeframe="5m")
    st_mutated = _completed_state(frame_mutated, t_comp, use_rvol=False, timeframe="5m")

    assert st_clean is not None and st_mutated is not None
    assert st_clean.close != st_mutated.close
    assert st_mutated.close == 999999.0


# ===========================================================================
# 3. Session Boundary and Gap Rejection Tests
# ===========================================================================

def test_session_boundary_prevents_stale_overnight_candles():
    """Yesterday's last candle must never be used in today's session."""
    idx1 = pd.date_range("2024-01-02 09:15", "2024-01-02 15:30", freq="5min")
    idx2 = pd.date_range("2024-01-03 09:15", "2024-01-03 15:30", freq="5min")
    all_idx = idx1.append(idx2)

    frame = pd.DataFrame(
        {
            "close": range(len(all_idx)),
            "ema20": range(len(all_idx)),
            "ema50": range(len(all_idx)),
            "rsi": [50.0] * len(all_idx),
            "atr": [1.0] * len(all_idx),
            "rvol": [1.0] * len(all_idx),
        },
        index=all_idx,
    )

    # Day 2 morning at 09:16: no day 2 candle is completed yet.
    # Must NOT return day 1's 15:00-15:30 candle.
    t_day2_morning = pd.Timestamp("2024-01-03 09:16:00")
    state = _completed_state(
        frame,
        t_day2_morning,
        use_rvol=False,
        timeframe="5m",
    )
    assert state is None, "Leaked yesterday's candle into today morning!"


def test_missing_minute_gap_rejects_stale_candle():
    """If a gap exceeds timeframe duration, the stale candle must be rejected."""
    # Candle 0: 09:15 (ends at 09:20)
    # Candle 1: 09:40 (ends at 09:45) - 20 minute gap
    idx = pd.to_datetime(["2024-01-02 09:15:00", "2024-01-02 09:40:00"])
    frame = pd.DataFrame(
        {
            "close": [100.0, 105.0],
            "ema20": [100.0, 105.0],
            "ema50": [99.0, 104.0],
            "rsi": [50.0, 50.0],
            "atr": [1.0, 1.0],
            "rvol": [1.0, 1.0],
        },
        index=idx,
    )

    # At 09:35, candle 0 [09:15, 09:20) is 15 minutes old (stale for a 5m timeframe).
    # Since 09:35 - 09:20 = 15 min >= 5 min duration, it must be rejected as stale.
    t_in_gap = pd.Timestamp("2024-01-02 09:35:00")
    state = _completed_state(
        frame,
        t_in_gap,
        use_rvol=False,
        timeframe="5m",
    )
    assert state is None, "Stale candle was used across a missing-minute gap!"


def test_cursor_and_completed_state_exact_parity():
    """_TimeframeCursor and _completed_state must produce identical results on all bars."""
    idx = pd.date_range("2024-01-02 09:15", "2024-01-02 11:15", freq="5min")
    # Drop 10:00 to 10:20 as a gap
    idx = idx[~((idx >= "2024-01-02 10:00") & (idx < "2024-01-02 10:20"))]

    frame = pd.DataFrame(
        {
            "close": np.linspace(100, 150, len(idx)),
            "ema20": np.linspace(100, 150, len(idx)),
            "ema50": np.linspace(99, 149, len(idx)),
            "rsi": [55.0] * len(idx),
            "atr": [2.0] * len(idx),
            "rvol": [1.5] * len(idx),
        },
        index=idx,
    )

    tf_dict = {"5m": frame, "10m": frame, "15m": frame, "30m": frame}
    cursors = _make_cursors(tf_dict, use_rvol=False)
    cursor = cursors["5m"]

    # Test every 1-minute step from 09:15 to 11:30
    eval_timestamps = pd.date_range("2024-01-02 09:15", "2024-01-02 11:30", freq="1min")
    for ts in eval_timestamps:
        direct = _completed_state(frame, ts, use_rvol=False, timeframe="5m")
        from_cursor = cursor.update(ts)
        assert direct == from_cursor, f"Discrepancy at {ts}: direct={direct}, cursor={from_cursor}"


# ===========================================================================
# 4. Execution Timing Contracts (run_backtest)
# ===========================================================================

def test_run_backtest_same_close_vs_next_open_timing():
    """
    Demonstrate the contract difference between same_close and next_open.
    Bar 1 generates LONG signal at close.
    - same_close: entry_price == Bar 1 close
    - next_open: entry_price == Bar 2 open
    """
    idx = pd.date_range("2024-01-02 09:15", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0, 102.0, 105.0, 108.0, 110.0],
            "high": [101.0, 104.0, 107.0, 110.0, 112.0],
            "low": [99.0, 101.0, 104.0, 107.0, 109.0],
            "close": [101.0, 103.0, 106.0, 109.0, 111.0],
        },
        index=idx,
    )

    def sig_func(row, prev_row):
        if row.name == pd.Timestamp("2024-01-02 09:16:00"):
            return Position.LONG
        return None

    # Legacy same_close
    res_close = run_backtest(df, sig_func, initial_capital=10000.0, execution_model="same_close")
    assert len(res_close.trades) == 1
    assert res_close.trades[0].entry_time == pd.Timestamp("2024-01-02 09:16:00")
    assert res_close.trades[0].entry_price == 103.0

    # Causal next_open
    res_open = run_backtest(df, sig_func, initial_capital=10000.0, execution_model="next_open")
    assert len(res_open.trades) == 1
    assert res_open.trades[0].entry_time == pd.Timestamp("2024-01-02 09:17:00")
    assert res_open.trades[0].entry_price == 105.0


def test_run_backtest_next_open_does_not_execute_last_bar_signal():
    """A signal on the final candle cannot execute because no t+1 bar exists."""
    idx = pd.date_range("2024-01-02 09:15", periods=3, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0, 102.0, 104.0],
            "high": [101.0, 103.0, 105.0],
            "low": [99.0, 101.0, 103.0],
            "close": [100.5, 102.5, 104.5],
        },
        index=idx,
    )

    def sig_func(row, prev_row):
        if row.name == pd.Timestamp("2024-01-02 09:17:00"):
            return Position.LONG
        return None

    res = run_backtest(df, sig_func, initial_capital=10000.0, execution_model="next_open")
    assert len(res.trades) == 0


def test_run_backtest_invalid_execution_model_raises_value_error():
    idx = pd.date_range("2024-01-02 09:15", periods=5, freq="1min")
    df = pd.DataFrame({"close": range(5)}, index=idx)
    with pytest.raises(ValueError, match="Unsupported execution_model"):
        run_backtest(df, lambda r, p: None, initial_capital=10000.0, execution_model="invalid_model")


# ===========================================================================
# 5. Execution Timing Contracts (run_intraday_backtest)
# ===========================================================================

def test_run_intraday_backtest_same_close_vs_next_open_timing():
    """
    Verify run_intraday_backtest execution timing:
    - same_close enters at signal bar close.
    - next_open enters at signal bar + 1 open.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    df = pd.DataFrame(
        {
            "open": [100.0, 102.0, 105.0, 108.0, 110.0],
            "high": [101.0, 103.0, 106.0, 109.0, 111.0],
            "low": [99.0, 101.0, 104.0, 107.0, 109.0],
            "close": [100.5, 102.5, 105.5, 108.5, 110.5],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )

    signals = [None, Position.LONG, None, None, None]

    # 1. same_close: entry at Bar 1 close (102.5)
    cfg_close = IntradayEngineConfig(execution_model="same_close")
    res_close = run_intraday_backtest(df, signals, cfg_close)
    assert len(res_close.trades) == 1
    assert res_close.trades[0].entry_time == pd.Timestamp("2024-01-02 09:16:00")
    assert res_close.trades[0].entry_price == 102.5

    # 2. next_open: entry at Bar 2 (09:17) open (105.0)
    cfg_open = IntradayEngineConfig(execution_model="next_open")
    res_open = run_intraday_backtest(df, signals, cfg_open)
    assert len(res_open.trades) == 1
    assert res_open.trades[0].entry_time == pd.Timestamp("2024-01-02 09:17:00")
    assert res_open.trades[0].entry_price == 105.0


def test_run_intraday_backtest_next_open_overnight_cleared():
    """A signal at the last bar of Day 1 must NOT execute on Day 2 morning."""
    idx1 = pd.date_range("2024-01-02 15:25", periods=5, freq="1min")
    idx2 = pd.date_range("2024-01-03 09:15", periods=5, freq="1min")
    all_idx = idx1.append(idx2)

    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "atr": 2.0,
        },
        index=all_idx,
    )

    signals = [None] * len(all_idx)
    signals[4] = Position.LONG

    cfg = IntradayEngineConfig(execution_model="next_open")
    res = run_intraday_backtest(df, signals, cfg)
    assert len(res.trades) == 0


def test_run_intraday_backtest_invalid_execution_model_raises_value_error():
    idx = pd.date_range("2024-01-02 09:15", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "atr": 2.0,
        },
        index=idx,
    )
    cfg = IntradayEngineConfig(execution_model="unsupported")
    with pytest.raises(ValueError, match="Unsupported execution_model"):
        run_intraday_backtest(df, [None] * 5, cfg)

"""
Unit, Acceptance, and Regression Tests for SignalForge Risk and Exit Engine (V2 Architecture).
=============================================================================================
Document Reference: SF-TEST-RISK-2026-V2
Parent Specification: SF-SPEC-RISK-2026-V2 (research/strategy_evolution_2018/phase24G10_risk_engine_spec/risk_and_exit_engine_specification.md)
Acceptance Matrix: research/strategy_evolution_2018/phase24G10_risk_engine_spec/acceptance_test_matrix.md
Unresolved Decisions: research/strategy_evolution_2018/phase24G10_risk_engine_spec/unresolved_decisions_register.md

Validates:
  - Acceptance Test Matrix (TC-RISK-01 through TC-RISK-15)
  - Short-side symmetry (TC-SHORT-01 through TC-SHORT-05)
  - Monotonic trailing stop ratchet across complex multi-wave swings
  - Sizing floors, leverage limits, and insufficient capital rejections
  - Gap-through-stop losses exceeding 1R
  - EOD edge cases and partition boundary purges
  - Causal reversals and gate failure handling
  - Data corruption and invalid price rejection
  - Transaction friction model comparisons
  - Bit-for-bit deterministic replay consistency (SHA-256 agreement)
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from src.backtest.risk_engine_v2 import (
    CostBreakdown,
    CostModelType,
    ExitReason,
    PositionSide,
    RejectionReason,
    RiskEngineConfigV2,
    RiskEngineV2,
    RiskEngineV2Result,
    TrailingStopRatchet,
    V2Trade,
    calculate_clamped_stop_distance,
    calculate_position_size,
    calculate_transaction_costs,
)


# ============================================================================
# Helper Functions
# ============================================================================

def make_candles(records: list[dict]) -> pd.DataFrame:
    """Build a standard 1-minute OHLCV DataFrame with DatetimeIndex and ATR."""
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["time"])
    df = df.set_index("timestamp").sort_index()
    if "open" not in df.columns and "Open" in df.columns:
        df["open"] = df["Open"]
    if "high" not in df.columns and "High" in df.columns:
        df["high"] = df["High"]
    if "low" not in df.columns and "Low" in df.columns:
        df["low"] = df["Low"]
    if "close" not in df.columns and "Close" in df.columns:
        df["close"] = df["Close"]
    if "volume" not in df.columns:
        df["volume"] = 1000.0
    if "atr" not in df.columns:
        df["atr"] = 4.0
    return df


# ============================================================================
# 1. Standalone Mathematical Formula Tests (Specification Section 2.1 - 2.5)
# ============================================================================

def test_position_sizing_respects_risk_budget():
    """Verify that monetary risk never exceeds the allocated risk budget."""
    capital = 100000.0
    risk_pct = 0.01  # 1% = Rs 1000
    entry_price = 300.0
    stop_distance = 6.0  # 1.5 * ATR(4.0)

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance)
    assert qty == 166

    monetary_risk = qty * stop_distance
    assert monetary_risk <= 1000.0
    assert monetary_risk == 996.0


def test_position_sizing_respects_leverage_cap():
    """Verify that notional exposure never exceeds capital * max_leverage."""
    capital = 10000.0
    risk_pct = 0.01  # Rs 100 budget
    entry_price = 1000.0
    stop_distance = 0.50  # Very tight stop -> q_risk would be 200 units (Rs 200k notional = 20x)
    max_leverage = 5.0    # Capped at Rs 50,000 notional -> max 50 units

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance, max_leverage)
    assert qty == 50

    notional_exposure = qty * entry_price
    assert notional_exposure <= capital * max_leverage
    assert notional_exposure == 50000.0


def test_position_sizing_rejects_insufficient_capital():
    """Verify that if capital cannot afford even 1 unit within risk bounds, size is 0."""
    capital = 100.0
    risk_pct = 0.01  # Rs 1.00 budget
    entry_price = 500.0
    stop_distance = 10.0  # q_risk = floor(1 / 10) = 0

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance)
    assert qty == 0


def test_stop_distance_clamping():
    """Verify that stop distance is clamped to at least 1 tick or 0.20% of entry price."""
    # Case 1: Compressed ATR where raw ATR is 0.01
    dist = calculate_clamped_stop_distance(entry_price=300.0, atr=0.01, k_stop=1.5, tick_size=0.05, min_stop_pct=0.0020)
    # Min distance = max(0.05, 300 * 0.0020 = 0.60) = 0.60
    assert dist == 0.60

    # Case 2: Normal ATR 4.0, k_stop 1.5 -> 6.0 (which is > 0.60)
    dist2 = calculate_clamped_stop_distance(entry_price=300.0, atr=4.0, k_stop=1.5, tick_size=0.05, min_stop_pct=0.0020)
    assert dist2 == 6.0


# ============================================================================
# 2. Phase 24G.10 Acceptance Test Cases (TC-RISK-01 through TC-RISK-15)
# ============================================================================

def test_tc_risk_01_causal_next_open_fill():
    """TC-RISK-01: Order queues at t close; executes at t+1 open."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 301.0, "low": 299.0, "close": 300.5, "atr": 4.0},  # BUY signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 302.0, "low": 299.5, "close": 301.0, "atr": 4.0},  # Fills here
        {"time": "2020-01-02 10:17:00", "open": 301.0, "high": 303.0, "low": 300.5, "close": 302.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.entry_time == pd.Timestamp("2020-01-02 10:16:00")
    assert trade.entry_price == 300.00
    assert trade.side == PositionSide.LONG


def test_tc_risk_02_normal_intrabar_stop_loss():
    """TC-RISK-02: Normal Intrabar Stop Loss triggered at Low <= P_stop."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 300.5, "low": 299.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 298.0, "close": 299.0, "atr": 4.0},  # Filled @ 300.0, stop=294.0
        {"time": "2020-01-02 10:17:00", "open": 297.0, "high": 298.0, "low": 293.5, "close": 295.0, "atr": 4.0},  # Low 293.5 <= 294.0
        {"time": "2020-01-02 10:18:00", "open": 295.0, "high": 296.0, "low": 294.0, "close": 295.5, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    # Capital 60,000, risk 1% = 600, stop dist = 6.0 -> Q = 100
    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.quantity == 100
    assert t.exit_price == 294.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -600.0
    assert t.net_pnl == pytest.approx(-600.0 - t.transaction_cost, abs=1e-4)


def test_tc_risk_03_gap_through_stop_loss():
    """TC-RISK-03: Gap-Through Stop Loss fills at Open - Slippage, NOT nominal stop."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 300.5, "low": 299.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 298.0, "close": 299.0, "atr": 4.0},  # Filled @ 300.0, stop=294.0
        {"time": "2020-01-02 10:17:00", "open": 289.0, "high": 291.0, "low": 287.0, "close": 290.0, "atr": 4.0},  # Gaps down to 289.0
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    # Case A: 0 slippage
    cfg_no_slip = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res_no_slip = RiskEngineV2(cfg_no_slip).run(df, sig_fn)
    t = res_no_slip.trades[0]
    assert t.exit_price == 289.00
    assert t.exit_price < 294.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -1100.0  # (289 - 300) * 100

    # Case B: 1-tick slippage (0.05)
    cfg_slip = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.05)
    res_slip = RiskEngineV2(cfg_slip).run(df, sig_fn)
    t_slip = res_slip.trades[0]
    assert t_slip.exit_price == pytest.approx(288.95, abs=1e-4)
    assert t_slip.exit_price < 294.00


def test_tc_risk_04_same_candle_stop_target_conflict():
    """TC-RISK-04: Conservative rule triggers stop loss first when bar touches both Stop and Target."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 300.5, "low": 299.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.5, "atr": 4.0},  # Entry 300.0, stop=294, target=312
        {"time": "2020-01-02 10:17:00", "open": 302.0, "high": 315.0, "low": 292.0, "close": 305.0, "atr": 4.0},  # High 315 >= 312 AND Low 292 <= 294
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, k_stop=1.5, k_target=3.0, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 294.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -600.0


def test_tc_risk_05_trailing_stop_ratchet_monotonicity():
    """TC-RISK-05: Trailing stop ratchets up and never loosens on pullbacks."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 300.5, "low": 299.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Entry 300, stop 294
        {"time": "2020-01-02 10:17:00", "open": 301.0, "high": 310.0, "low": 305.0, "close": 308.0, "atr": 4.0},  # Candle 1: High 310 -> stop 304
        {"time": "2020-01-02 10:18:00", "open": 308.0, "high": 305.0, "low": 304.5, "close": 304.8, "atr": 4.0},  # Candle 2: Pullback -> stop stays 304
        {"time": "2020-01-02 10:19:00", "open": 304.5, "high": 304.8, "low": 298.0, "close": 299.0, "atr": 4.0},  # Candle 3: Stop hit at 304
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=60000.0,
        k_stop=1.5,
        k_target=None,
        k_trail=1.5,
        trail_activation_r=1.0,
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.final_stop == 304.00
    assert t.exit_price == 304.00
    assert t.exit_reason == ExitReason.TRAILING_STOP.value
    assert t.gross_pnl > 0


def test_tc_risk_06_max_holding_time_expiration():
    """TC-RISK-06: Time-based exit triggered at open of bar t_entry + M_max + 1."""
    times = pd.date_range("2020-01-02 09:59:00", "2020-01-02 11:05:00", freq="1min")
    records = []
    for t in times:
        records.append({
            "time": str(t),
            "open": 300.0,
            "high": 301.0,
            "low": 299.0,
            "close": 300.0,
            "atr": 4.0,
        })
    df = make_candles(records)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 09:59:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=60000.0,
        k_stop=2.0,
        k_target=4.0,
        max_holding_bars=60,
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.entry_time == pd.Timestamp("2020-01-02 10:00:00")
    assert t.exit_time == pd.Timestamp("2020-01-02 11:01:00")
    assert t.exit_reason == ExitReason.MAX_TIME.value


def test_tc_risk_07_mandatory_1529_eod_liquidation():
    """TC-RISK-07: Mandatory square-off executed at 15:29:00 close with zero overnight carry."""
    times = pd.date_range("2020-01-02 15:25:00", "2020-01-02 15:30:00", freq="1min")
    records = []
    for t in times:
        records.append({
            "time": str(t),
            "open": 300.0,
            "high": 301.0,
            "low": 299.0,
            "close": 300.0,
            "atr": 4.0,
        })
    df = make_candles(records)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 15:25:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=60000.0,
        session_end_time="15:29:00",
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.entry_time == pd.Timestamp("2020-01-02 15:26:00")
    assert t.exit_time == pd.Timestamp("2020-01-02 15:29:00")
    assert t.exit_reason == ExitReason.EOD.value


def test_tc_risk_08_pending_order_cancellation_at_day_rollover():
    """TC-RISK-08: Pending orders at 15:29:00 are cancelled at session rollover; zero fill at 09:15 next day."""
    candles = [
        {"time": "2020-01-02 15:28:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 15:29:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Signal queued
        {"time": "2020-01-03 09:15:00", "open": 305.0, "high": 306.0, "low": 304.0, "close": 305.5, "atr": 4.0},  # New day
        {"time": "2020-01-03 09:16:00", "open": 305.5, "high": 307.0, "low": 305.0, "close": 306.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 15:29:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(session_end_time="15:29:00", execution_model="next_open")
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 0
    rollover_rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.DAY_ROLLOVER_CANCELLED.value]
    assert len(rollover_rejections) == 1


def test_tc_risk_09_partition_boundary_purge():
    """TC-RISK-09: Partition boundary purges all open positions and starts next partition completely flat."""
    part1_candles = [
        {"time": "2018-12-31 15:25:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2018-12-31 15:26:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Enters Long
        {"time": "2018-12-31 15:29:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Final bar of 2018
    ]
    part2_candles = [
        {"time": "2019-01-01 09:15:00", "open": 305.0, "high": 306.0, "low": 304.0, "close": 305.0, "atr": 4.0},
        {"time": "2019-01-01 09:16:00", "open": 305.0, "high": 306.0, "low": 304.0, "close": 305.0, "atr": 4.0},
    ]
    df1 = make_candles(part1_candles)
    df2 = make_candles(part2_candles)

    def sig_fn1(row, prev_row):
        if row.name == pd.Timestamp("2018-12-31 15:25:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(execution_model="next_open")
    res1 = RiskEngineV2(cfg).run(df1, sig_fn1)
    assert len(res1.trades) == 1
    assert res1.trades[0].exit_reason == ExitReason.EOD.value

    # Partition 2 runs completely flat
    res2 = RiskEngineV2(cfg).run(df2, lambda r, p: None)
    assert len(res2.trades) == 0


def test_tc_risk_10_daily_loss_circuit_breaker():
    """TC-RISK-10: Daily loss circuit breaker trips after exceeding theta_day (2.0%); subsequent signals rejected."""
    candles = [
        # Setup Trade 1: loses ~1100
        {"time": "2020-01-02 09:20:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 09:21:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 09:25:00", "open": 294.0, "high": 295.0, "low": 293.0, "close": 293.5, "atr": 4.0},  # Stop hit
        # Setup Trade 2: loses ~1000
        {"time": "2020-01-02 09:30:00", "open": 295.0, "high": 296.0, "low": 294.0, "close": 295.0, "atr": 4.0},
        {"time": "2020-01-02 09:31:00", "open": 295.0, "high": 296.0, "low": 294.0, "close": 295.0, "atr": 4.0},
        {"time": "2020-01-02 09:35:00", "open": 289.0, "high": 290.0, "low": 288.0, "close": 288.5, "atr": 4.0},  # Stop hit -> total loss > 2000
        # Subsequent signal on same day
        {"time": "2020-01-02 10:00:00", "open": 290.0, "high": 291.0, "low": 289.0, "close": 290.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 290.0, "high": 291.0, "low": 289.0, "close": 290.0, "atr": 4.0},
        # Next Day auto-reset
        {"time": "2020-01-03 09:20:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-03 09:21:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        ts = row.name
        if ts in (
            pd.Timestamp("2020-01-02 09:20:00"),
            pd.Timestamp("2020-01-02 09:30:00"),
            pd.Timestamp("2020-01-02 10:00:00"),
            pd.Timestamp("2020-01-03 09:20:00"),
        ):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=100000.0,
        daily_loss_limit_pct=0.02,
        risk_per_trade=0.011,
        k_stop=1.5,
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert res.circuit_breaker_tripped is True
    rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.DAILY_LOSS_LIMIT.value]
    assert len(rejections) >= 1
    # Check that day 2 entered normally
    assert any(t.entry_time == pd.Timestamp("2020-01-03 09:21:00") for t in res.trades)


def test_tc_risk_11_consecutive_loss_cooldown():
    """TC-RISK-11: 3 consecutive losses activate a 60-min cooling-off pause."""
    candles = [
        # Loss 1
        {"time": "2020-01-02 09:20:00", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "atr": 2.0},
        {"time": "2020-01-02 09:21:00", "open": 100.0, "high": 101.0, "low": 96.0, "close": 96.5, "atr": 2.0},  # Stop hit
        # Loss 2
        {"time": "2020-01-02 09:25:00", "open": 96.0, "high": 97.0, "low": 95.0, "close": 96.0, "atr": 2.0},
        {"time": "2020-01-02 09:26:00", "open": 96.0, "high": 97.0, "low": 92.0, "close": 92.5, "atr": 2.0},  # Stop hit
        # Loss 3
        {"time": "2020-01-02 09:30:00", "open": 92.0, "high": 93.0, "low": 91.0, "close": 92.0, "atr": 2.0},
        {"time": "2020-01-02 09:31:00", "open": 92.0, "high": 93.0, "low": 88.0, "close": 88.5, "atr": 2.0},  # Stop hit at 09:31 -> Cooldown until 10:31
        # Signal during cooldown window at 10:00:00
        {"time": "2020-01-02 10:00:00", "open": 88.0, "high": 89.0, "low": 87.0, "close": 88.0, "atr": 2.0},
        {"time": "2020-01-02 10:01:00", "open": 88.0, "high": 89.0, "low": 87.0, "close": 88.0, "atr": 2.0},
        # Signal after cooldown window at 10:35:00
        {"time": "2020-01-02 10:35:00", "open": 88.0, "high": 89.0, "low": 87.0, "close": 88.0, "atr": 2.0},
        {"time": "2020-01-02 10:36:00", "open": 88.0, "high": 89.0, "low": 87.0, "close": 88.0, "atr": 2.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        ts = row.name
        if ts in (
            pd.Timestamp("2020-01-02 09:20:00"),
            pd.Timestamp("2020-01-02 09:25:00"),
            pd.Timestamp("2020-01-02 09:30:00"),
            pd.Timestamp("2020-01-02 10:00:00"),
            pd.Timestamp("2020-01-02 10:35:00"),
        ):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=500000.0,
        daily_loss_limit_pct=0.10,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        k_stop=1.5,
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    cooldown_rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value]
    assert len(cooldown_rejections) >= 1
    # Check that trade entered after 10:31
    assert any(t.entry_time == pd.Timestamp("2020-01-02 10:36:00") for t in res.trades)


def test_tc_risk_12_risk_budget_leverage_clamping():
    """TC-RISK-12: Quantity is clamped by regulatory/broker leverage cap (5.0x)."""
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 1000.0, "high": 1001.0, "low": 999.0, "close": 1000.0, "atr": 0.5},
        {"time": "2020-01-02 10:01:00", "open": 1000.0, "high": 1001.0, "low": 999.0, "close": 1000.0, "atr": 0.5},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:00:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=2.0,
        min_stop_pct=0.001,
        execution_model="next_open",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    assert res.trades[0].quantity == 50  # (10000 * 5) / 1000


def test_tc_risk_13_missing_minute_gap_rejection():
    """TC-RISK-13: Pending order cancelled when a missing data gap (>1m) occurs."""
    candles = [
        {"time": "2020-01-02 09:59:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Queues order
        {"time": "2020-01-02 10:05:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # 4-minute gap!
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:00:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(execution_model="next_open")
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 0
    gap_rej = [r for r in res.audit_rejections if r["reason"] == RejectionReason.MISSING_DATA_GAP.value]
    assert len(gap_rej) == 1


def test_tc_risk_14_zero_capital_bankruptcy_protection():
    """TC-RISK-14: Catastrophic loss drops capital <= 0; trading halts permanently with explicit bankruptcy reason."""
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0, "atr": 0.1},
        {"time": "2020-01-02 10:01:00", "open": 100.0, "high": 100.1, "low": 99.95, "close": 100.0, "atr": 0.1},
        {"time": "2020-01-02 10:02:00", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "atr": 0.1},  # Severe gap down (-90 pts)
        {"time": "2020-01-02 10:03:00", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "atr": 0.1},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:00:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=500.0, risk_per_trade=0.02, max_leverage=5.0, k_target=None, min_stop_pct=0.001, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert res.bankruptcy_reason is not None
    assert "BANKRUPTCY" in res.bankruptcy_reason
    assert res.final_capital <= 0.0


def test_tc_risk_15_deterministic_replay_agreement():
    """TC-RISK-15: Two independent simulator runs on identical inputs yield exact SHA-256 trade log agreement."""
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 302.0, "low": 299.0, "close": 301.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 301.0, "high": 308.0, "low": 300.0, "close": 307.0, "atr": 4.0},
        {"time": "2020-01-02 10:02:00", "open": 307.0, "high": 309.0, "low": 302.0, "close": 304.0, "atr": 4.0},
        {"time": "2020-01-02 10:03:00", "open": 304.0, "high": 305.0, "low": 290.0, "close": 292.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:00:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=50000.0, execution_model="next_open")
    res1 = RiskEngineV2(cfg).run(df, sig_fn)
    res2 = RiskEngineV2(cfg).run(df, sig_fn)

    assert res1.trade_log_hash == res2.trade_log_hash
    assert res1.net_pnl == res2.net_pnl
    assert res1.total_trades == res2.total_trades
    assert res1.win_rate_pct == res2.win_rate_pct
    assert res1.max_drawdown_amount == res2.max_drawdown_amount


# ============================================================================
# 3. Short-Side Symmetry Tests
# ============================================================================

def test_short_side_causal_next_open_fill():
    """Verify that SHORT order executes at t+1 open following signal at t close."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 301.0, "high": 302.0, "low": 300.0, "close": 301.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 301.5, "high": 302.0, "low": 299.5, "close": 300.0, "atr": 4.0},  # SELL signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 300.5, "low": 298.0, "close": 298.5, "atr": 4.0},  # Fills SHORT
        {"time": "2020-01-02 10:17:00", "open": 298.5, "high": 299.0, "low": 297.0, "close": 298.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.SHORT
        return None

    cfg = RiskEngineConfigV2.test_fixture(k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.entry_time == pd.Timestamp("2020-01-02 10:16:00")
    assert trade.entry_price == 300.00
    assert trade.side == PositionSide.SHORT
    assert trade.initial_stop == 306.00  # 300 + 1.5 * 4


def test_short_side_normal_intrabar_stop_loss():
    """Verify SHORT position exits at stop price when High >= P_stop."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 301.0, "high": 302.0, "low": 300.0, "close": 301.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 301.5, "high": 302.0, "low": 300.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Filled Short @ 300, stop 306
        {"time": "2020-01-02 10:17:00", "open": 302.0, "high": 306.5, "low": 301.0, "close": 305.0, "atr": 4.0},  # High 306.5 >= 306.0
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.SHORT
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 306.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -600.0  # (300 - 306) * 100


def test_short_side_gap_through_stop_loss():
    """Verify SHORT position fills at Open + Slippage when market gaps up past stop."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 301.0, "high": 302.0, "low": 300.0, "close": 301.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 301.5, "high": 302.0, "low": 300.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Entry Short @ 300, stop 306
        {"time": "2020-01-02 10:17:00", "open": 311.0, "high": 313.0, "low": 310.0, "close": 312.0, "atr": 4.0},  # Gaps up to 311.0 > 306.0
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.SHORT
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 311.00
    assert t.exit_price > 306.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -1100.0  # (300 - 311) * 100


def test_short_side_trailing_ratchet_monotonicity():
    """Verify that SHORT trailing stop ratchets down and never moves upward on adverse rallies."""
    trail = TrailingStopRatchet(
        side=PositionSide.SHORT,
        initial_stop=306.00,
        trail_distance=6.0,
        entry_price=300.0,
        stop_distance=6.0,
        activation_r=1.0,  # Activates below 300 - 6 = 294.0
    )

    # Bar 1: Market drops to 290.0 (Activates trail!)
    s1 = trail.update(candle_high=298.0, candle_low=290.0)
    assert s1 == 296.0  # 290 + 6

    # Bar 2: Market rallies to 295.0 (Low is 292.0)
    s2 = trail.update(candle_high=295.0, candle_low=292.0)
    assert s2 == 296.0  # CANNOT move up
    assert s2 <= s1

    # Bar 3: Market plunges to 280.0
    s3 = trail.update(candle_high=288.0, candle_low=280.0)
    assert s3 == 286.0  # 280 + 6
    assert s3 < s2


def test_short_side_same_candle_collision():
    """Verify conservative stop-first resolution for SHORT position when bar touches both Stop and Target."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 301.0, "high": 302.0, "low": 300.0, "close": 301.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 301.5, "high": 302.0, "low": 300.0, "close": 300.0, "atr": 4.0},  # Signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Entry Short @ 300, stop 306, target 288
        {"time": "2020-01-02 10:17:00", "open": 299.0, "high": 308.0, "low": 285.0, "close": 295.0, "atr": 4.0},  # High 308 >= 306 AND Low 285 <= 288
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.SHORT
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, k_stop=1.5, k_target=3.0, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 306.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl < 0


# ============================================================================
# 4. Monotonicity & Edge-Case Regressions
# ============================================================================

def test_complex_wave_long_monotonicity():
    """Verify that across a complex 10-wave price sequence, LONG stop never decreases."""
    trail = TrailingStopRatchet(
        side=PositionSide.LONG,
        initial_stop=100.0,
        trail_distance=5.0,
        entry_price=105.0,
        stop_distance=5.0,
        activation_r=0.0,  # Immediately active
    )

    highs = [110.0, 107.0, 115.0, 112.0, 118.0, 114.0, 125.0, 120.0, 122.0, 130.0]
    prev_stop = 100.0

    for h in highs:
        cur_stop = trail.update(candle_high=h, candle_low=h - 4.0)
        assert cur_stop >= prev_stop, f"Monotonicity violation: {cur_stop} < {prev_stop}"
        prev_stop = cur_stop

    assert prev_stop == 125.0  # 130 - 5


def test_complex_wave_short_monotonicity():
    """Verify that across a complex 10-wave price sequence, SHORT stop never increases."""
    trail = TrailingStopRatchet(
        side=PositionSide.SHORT,
        initial_stop=100.0,
        trail_distance=5.0,
        entry_price=95.0,
        stop_distance=5.0,
        activation_r=0.0,
    )

    lows = [90.0, 93.0, 85.0, 88.0, 82.0, 86.0, 75.0, 80.0, 78.0, 70.0]
    prev_stop = 100.0

    for l in lows:
        cur_stop = trail.update(candle_high=l + 4.0, candle_low=l)
        assert cur_stop <= prev_stop, f"Monotonicity violation: {cur_stop} > {prev_stop}"
        prev_stop = cur_stop

    assert prev_stop == 75.0  # 70 + 5


def test_gap_through_loss_exceeds_one_r():
    """Verify simulator records the true gap loss exceeding the nominal 1R risk budget."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 299.0, "high": 300.0, "low": 298.5, "close": 299.5, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 299.5, "high": 300.5, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # Entry 300, stop 294 (1R = 1000)
        {"time": "2020-01-02 10:17:00", "open": 282.0, "high": 283.0, "low": 280.0, "close": 281.0, "atr": 4.0},  # Catastrophic gap to 282 (18 pts loss)
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        if row.name == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=100000.0, risk_per_trade=0.01, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    t = res.trades[0]
    nominal_1r = t.quantity * t.stop_distance
    assert abs(t.gross_pnl) > nominal_1r
    assert abs(t.r_multiple) > 1.0
    assert abs(t.r_multiple) == pytest.approx(3.0, abs=0.1)  # 18 pts / 6 pts = 3R loss


def test_reversal_handling_flow():
    """Verify that an opposite signal closes the active position and opens the reversed position."""
    candles = [
        {"time": "2020-01-02 10:14:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:15:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},  # BUY signal
        {"time": "2020-01-02 10:16:00", "open": 300.0, "high": 302.0, "low": 299.5, "close": 301.0, "atr": 4.0},  # Fills Long
        {"time": "2020-01-02 10:17:00", "open": 301.0, "high": 302.0, "low": 300.0, "close": 300.5, "atr": 4.0},  # SELL signal (reversal)
        {"time": "2020-01-02 10:18:00", "open": 300.5, "high": 301.0, "low": 299.0, "close": 299.5, "atr": 4.0},  # Reversal executes
        {"time": "2020-01-02 10:19:00", "open": 299.5, "high": 300.0, "low": 298.0, "close": 298.5, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev_row):
        ts = row.name
        if ts == pd.Timestamp("2020-01-02 10:15:00"):
            return PositionSide.LONG
        elif ts == pd.Timestamp("2020-01-02 10:17:00"):
            return PositionSide.SHORT
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=100000.0, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert len(res.trades) >= 1
    first_trade = res.trades[0]
    assert first_trade.side == PositionSide.LONG
    assert first_trade.exit_reason == ExitReason.REVERSAL.value
    assert first_trade.exit_time == pd.Timestamp("2020-01-02 10:18:00")


def test_data_corruption_and_invalid_prices():
    """Verify that data containing High < Low or non-positive prices is immediately rejected."""
    # Invalid High < Low
    bad_candles_1 = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 290.0, "low": 295.0, "close": 292.0, "atr": 4.0},
    ]
    df_bad_1 = make_candles(bad_candles_1)
    cfg = RiskEngineConfigV2.test_fixture()
    with pytest.raises(ValueError, match="High < Low"):
        RiskEngineV2(cfg).run(df_bad_1, lambda r, p: None)

    # Invalid non-positive price
    bad_candles_2 = [
        {"time": "2020-01-02 10:00:00", "open": 0.0, "high": 10.0, "low": 0.0, "close": 5.0, "atr": 4.0},
    ]
    df_bad_2 = make_candles(bad_candles_2)
    with pytest.raises(ValueError, match="Non-positive price"):
        RiskEngineV2(cfg).run(df_bad_2, lambda r, p: None)


def test_transaction_cost_models_comparison():
    """Verify mathematical calculation of Historical Baseline vs Production Indian Equity Intraday Cost Model."""
    entry_p = 300.0
    exit_p = 306.0
    qty = 100
    entry_t = pd.Timestamp("2020-01-02 09:45:00")
    exit_t = pd.Timestamp("2020-01-02 10:15:00")

    # 1. Historical Baseline
    costs_hist = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        entry_time=entry_t,
        exit_time=exit_t,
        cost_model=CostModelType.HISTORICAL_BASELINE,
        slippage_per_share=0.0,
    )
    # Total turnover = (300 + 306) * 100 = 60,600. Flat 1 bps = 6.06
    assert costs_hist.turnover == 60600.0
    assert costs_hist.total_costs == 6.06

    # 2. Production Indian Equity Intraday Model
    costs_prod = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        entry_time=entry_t,
        exit_time=exit_t,
        cost_model=CostModelType.REALISTIC_INTRADAY,
        slippage_per_share=0.0,
    )
    assert costs_prod.turnover == 60600.0
    # Brokerage: min(20, 30000 * 0.0005 = 15) + min(20, 30600 * 0.0005 = 15.30) = 30.30
    assert costs_prod.brokerage == pytest.approx(30.30, abs=1e-2)
    # STT: 0.025% on sell leg (exit: 30,600 * 0.00025 = 7.65)
    assert costs_prod.stt == pytest.approx(7.65, abs=1e-2)
    # Stamp duty: 0.003% on buy leg (entry: 30,000 * 0.00003 = 0.90)
    assert costs_prod.stamp_duty == pytest.approx(0.90, abs=1e-2)
    assert costs_prod.total_costs > costs_hist.total_costs

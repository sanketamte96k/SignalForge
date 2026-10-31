"""
Phase 24G.12 — Adversarial Audit and Boundary Test Suite for RiskEngineV2
=========================================================================
Document Reference: SF-AUDIT-RISK-2026-V2
Parent Specification: SF-SPEC-RISK-2026-V2 (Phase 24G.10)
Implementation Under Audit: src/backtest/risk_engine_v2.py

This module contains adversarial unit, boundary, accounting, and failure-mode
tests for the V2 Risk and Exit Engine candidate. Each test explicitly documents:
  - Suspected failure mode / audit objective
  - Expected behavioral invariant under SF-SPEC-RISK-2026-V2
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


def make_candles(records: list[dict]) -> pd.DataFrame:
    """Construct a clean 1-minute OHLCV DataFrame with DatetimeIndex."""
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["time"])
    df = df.set_index("timestamp").sort_index()
    for col in ("open", "high", "low", "close"):
        if col not in df.columns and col.capitalize() in df.columns:
            df[col] = df[col.capitalize()]
    if "volume" not in df.columns:
        df["volume"] = 1000.0
    if "atr" not in df.columns:
        df["atr"] = 4.0
    return df


# ============================================================================
# 1. Position Sizing & Numerical Boundary Values
# ============================================================================

def test_position_sizing_boundary_zero_and_negative():
    """Verify position sizing safely returns 0 for zero or negative parameters."""
    # Zero or negative capital
    assert calculate_position_size(capital=0.0, risk_pct=0.01, entry_price=300.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=-10000.0, risk_pct=0.01, entry_price=300.0, stop_distance=6.0) == 0

    # Zero or negative risk_pct
    assert calculate_position_size(capital=100000.0, risk_pct=0.0, entry_price=300.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=-0.01, entry_price=300.0, stop_distance=6.0) == 0

    # Zero or negative entry_price
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=0.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=-300.0, stop_distance=6.0) == 0

    # Zero or negative stop_distance
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=0.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=-6.0) == 0

    # Zero or negative max_leverage
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=6.0, max_leverage=0.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=6.0, max_leverage=-5.0) == 0


def test_position_sizing_non_finite_inputs():
    """
    Suspected Failure Mode: math.floor(nan) raises ValueError; math.floor(inf) raises OverflowError.
    Expected Invariant: Sizing returns 0 for non-finite inputs without raising exceptions.
    """
    assert calculate_position_size(capital=float("nan"), risk_pct=0.01, entry_price=300.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=float("nan"), entry_price=300.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=float("nan"), stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=float("nan")) == 0
    assert calculate_position_size(capital=float("inf"), risk_pct=0.01, entry_price=300.0, stop_distance=6.0) == 0
    assert calculate_position_size(capital=100000.0, risk_pct=0.01, entry_price=300.0, stop_distance=float("inf")) == 0


def test_clamped_stop_distance_clamping_and_boundaries():
    """Verify stop distance clamping protects against compressed ATR, non-positive, and non-finite inputs."""
    # ATR <= 0 or k_stop <= 0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=0.0, k_stop=1.5) == 0.0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=-4.0, k_stop=1.5) == 0.0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=4.0, k_stop=0.0) == 0.0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=4.0, k_stop=-1.5) == 0.0
    assert calculate_clamped_stop_distance(entry_price=0.0, atr=4.0, k_stop=1.5) == 0.0

    # Non-finite inputs
    assert calculate_clamped_stop_distance(entry_price=float("nan"), atr=4.0, k_stop=1.5) == 0.0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=float("nan"), k_stop=1.5) == 0.0
    assert calculate_clamped_stop_distance(entry_price=300.0, atr=4.0, k_stop=float("nan")) == 0.0

    # Extremely compressed ATR (e.g. ATR = 0.001)
    # Price 300 * 0.0020 = 0.60 > tick_size (0.05) -> clamped to 0.60
    dist = calculate_clamped_stop_distance(entry_price=300.0, atr=0.001, k_stop=1.5, tick_size=0.05, min_stop_pct=0.0020)
    assert dist == 0.60

    # Low-priced penny stock (Price = 5.0): 5.0 * 0.0020 = 0.01 < tick_size (0.05) -> clamped to 0.05
    dist_penny = calculate_clamped_stop_distance(entry_price=5.0, atr=0.001, k_stop=1.5, tick_size=0.05, min_stop_pct=0.0020)
    assert dist_penny == 0.05


def test_stated_risk_budget_covers_gross_price_risk_not_friction():
    """
    Audit Invariant: Monetary risk calculation sizes strictly for gross price movement.
    Transaction costs and slippage are additive to realized loss upon stop trigger.
    """
    capital = 100_000.0
    risk_pct = 0.01  # Rs 1,000 risk budget
    entry_p = 300.0
    stop_dist = 6.0   # Q = floor(1000 / 6) = 166

    qty = calculate_position_size(capital, risk_pct, entry_p, stop_dist)
    assert qty == 166

    gross_stop_risk = qty * stop_dist  # 166 * 6.00 = 996.00
    assert gross_stop_risk <= 1000.0

    costs = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=entry_p,
        exit_price=entry_p - stop_dist,
        quantity=qty,
        cost_model=CostModelType.HISTORICAL_BASELINE,
    )
    # Total net loss = Gross loss (996.00) + Costs
    net_loss = gross_stop_risk + costs.total_costs
    assert net_loss > 1000.0, "Net loss exceeds nominal 1R due to additive transaction friction."


# ============================================================================
# 2. Intrabar Precedence & Trailing Stop Ratchet Invariants
# ============================================================================

def test_adversarial_intrabar_stop_breach_before_trailing_ratchet_long():
    """
    Suspected Failure Mode: When a single bar touches both the pre-existing stop and a new high,
    updating the trailing ratchet before checking the stop overwrites the initial stop and
    converts a losing stop-out into a winning trade.
    Expected Invariant: Under DEC-09 conservative precedence, the pre-existing stop must trigger
    first at 294.0 with ExitReason.STOP_LOSS and negative gross P&L (-Rs 600.00).
    """
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        # Enters Long @ 300.0; initial stop = 294.0.
        # Bar 10:02 has Low=290.0 (breaches 294) AND High=312.0 (reaches trail threshold).
        {"time": "2020-01-02 10:02:00", "open": 300.0, "high": 312.0, "low": 290.0, "close": 305.0, "atr": 4.0},
    ]
    df = make_candles(candles)
    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=60000.0,
        k_stop=1.5,
        k_target=None,
        k_trail=1.5,
        trail_activation_r=1.0,
        execution_model="same_close",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(
        df,
        lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:01:00") else None,
    )
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 294.00, "Position must exit at pre-existing stop, NOT trailing ratchet candidate."
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -600.0


def test_adversarial_intrabar_stop_breach_before_trailing_ratchet_short():
    """
    Suspected Failure Mode: SHORT position stop loss overwritten by downward trailing ratchet.
    Expected Invariant: SHORT position must stop out at initial stop 306.0 with STOP_LOSS.
    """
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        # Enters Short @ 300.0; initial stop = 306.0.
        # Bar 10:02 has High=310.0 (breaches 306) AND Low=288.0 (trail threshold).
        {"time": "2020-01-02 10:02:00", "open": 300.0, "high": 310.0, "low": 288.0, "close": 295.0, "atr": 4.0},
    ]
    df = make_candles(candles)
    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=60000.0,
        k_stop=1.5,
        k_target=None,
        k_trail=1.5,
        trail_activation_r=1.0,
        execution_model="same_close",
        slippage=0.0,
    )
    res = RiskEngineV2(cfg).run(
        df,
        lambda r, p: PositionSide.SHORT if r.name == pd.Timestamp("2020-01-02 10:01:00") else None,
    )
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_price == 306.00
    assert t.exit_reason == ExitReason.STOP_LOSS.value
    assert t.gross_pnl == -600.0


# ============================================================================
# 3. Slippage Accounting Reconciliation
# ============================================================================

def test_adversarial_slippage_accounting_no_double_deduction():
    """
    Suspected Failure Mode: When slippage > 0, fill prices are shifted by slippage,
    AND calculate_transaction_costs adds slippage to total_costs, deducting slippage TWICE.
    Expected Invariant: Net P&L = Gross P&L - Brokerage/Statutory Fees.
    Total friction on a 0-movement trade with 0.05 slippage on 100 shares must be exactly:
      Execution Spread Slippage: 2 * 0.05 * 100 = Rs 10.00
      Historical Fee (1 bps on turnover ~60,000): Rs 6.00
      Total Loss: Rs 16.00 (NOT Rs 26.00).
    """
    records = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 15:29:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
    ]
    df = make_candles(records)
    cfg = RiskEngineConfigV2.test_fixture(initial_capital=60000.0, slippage=0.05, cost_model="historical_baseline")
    res = RiskEngineV2(cfg).run(
        df,
        lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:00:00") else None,
    )
    assert len(res.trades) == 1
    t = res.trades[0]

    assert t.entry_price == 300.05
    assert t.exit_price == 299.95
    assert t.gross_pnl == -10.0  # Slippage embedded in price spread
    # Net P&L must be -16.00 (gross -10.00 - fees 6.00)
    assert t.net_pnl == pytest.approx(-16.00, abs=0.05)
    assert t.net_pnl == pytest.approx(t.gross_pnl - t.transaction_cost, abs=1e-4)


# ============================================================================
# 4. Risk Limits & Circuit Breakers
# ============================================================================

def test_circuit_breaker_exact_threshold_boundary():
    """
    Verify circuit breaker behavior below and above theta_day (2.0%).
    Day start capital = Rs 100,000. Max allowed loss = Rs 2,000.
    """
    # Case 1: Below threshold (loss = -950) -> Not tripped
    candles_sub = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:05:00", "open": 292.4, "high": 293.0, "low": 291.5, "close": 292.0, "atr": 4.0},
        {"time": "2020-01-02 10:10:00", "open": 292.0, "high": 293.0, "low": 291.5, "close": 292.0, "atr": 4.0},
    ]
    df_sub = make_candles(candles_sub)
    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=100000.0,
        daily_loss_limit_pct=0.02,
        k_stop=2.0,
        k_target=4.0,
        execution_model="next_open",
        slippage=0.0,
    )
    res_sub = RiskEngineV2(cfg).run(
        df_sub,
        lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:00:00") else None,
    )
    assert res_sub.circuit_breaker_tripped is False

    # Case 2: Above threshold (loss = -2375 > 2000) -> Tripped
    candles_above = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:05:00", "open": 281.0, "high": 282.0, "low": 280.0, "close": 281.0, "atr": 4.0},
        {"time": "2020-01-02 10:10:00", "open": 281.0, "high": 282.0, "low": 280.0, "close": 281.0, "atr": 4.0},
    ]
    df_above = make_candles(candles_above)
    res_above = RiskEngineV2(cfg).run(
        df_above,
        lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:00:00") else None,
    )
    assert res_above.circuit_breaker_tripped is True


def test_circuit_breaker_remains_active_for_entire_session():
    """Verify that once tripped, circuit breaker rejects ALL subsequent signals for that session."""
    candles = [
        {"time": "2020-01-02 09:20:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 09:21:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 09:25:00", "open": 270.0, "high": 271.0, "low": 269.0, "close": 270.0, "atr": 4.0},
        {"time": "2020-01-02 11:00:00", "open": 270.0, "high": 271.0, "low": 269.0, "close": 270.0, "atr": 4.0},
        {"time": "2020-01-02 13:00:00", "open": 270.0, "high": 271.0, "low": 269.0, "close": 270.0, "atr": 4.0},
        {"time": "2020-01-02 15:00:00", "open": 270.0, "high": 271.0, "low": 269.0, "close": 270.0, "atr": 4.0},
    ]
    df = make_candles(candles)

    def sig_fn(row, prev):
        if row.name in (
            pd.Timestamp("2020-01-02 09:20:00"),
            pd.Timestamp("2020-01-02 11:00:00"),
            pd.Timestamp("2020-01-02 13:00:00"),
            pd.Timestamp("2020-01-02 15:00:00"),
        ):
            return PositionSide.LONG
        return None

    cfg = RiskEngineConfigV2.test_fixture(initial_capital=100000.0, daily_loss_limit_pct=0.02, k_stop=1.5, execution_model="next_open", slippage=0.0)
    res = RiskEngineV2(cfg).run(df, sig_fn)

    assert res.circuit_breaker_tripped is True
    assert len(res.trades) == 1
    rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.DAILY_LOSS_LIMIT.value]
    assert len(rejections) == 3


def test_adversarial_consecutive_loss_cooldown_same_close_reversal():
    """
    Suspected Failure Mode: When execution_model == 'same_close', reversal exits omitted updating
    consecutive_losses and checking cooldown_until, allowing consecutive-loss breaker bypass.
    Expected Invariant: 3 consecutive reversal losses must activate cooling-off pause and reject
    the 4th reversal signal with CONSECUTIVE_LOSS_COOLDOWN.
    """
    records = [
        {"time": "2020-01-02 10:00:00", "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "atr": 2.0},
        {"time": "2020-01-02 10:01:00", "open": 100.0, "high": 100.5, "low": 99.0, "close": 99.5, "atr": 2.0},
        {"time": "2020-01-02 10:02:00", "open": 99.5, "high": 101.0, "low": 99.5, "close": 100.5, "atr": 2.0},
        {"time": "2020-01-02 10:03:00", "open": 100.5, "high": 101.0, "low": 99.5, "close": 99.5, "atr": 2.0},
        {"time": "2020-01-02 10:04:00", "open": 99.5, "high": 100.0, "low": 99.0, "close": 99.5, "atr": 2.0},
    ]
    df = make_candles(records)
    cfg = RiskEngineConfigV2.test_fixture(
        initial_capital=500000.0,
        daily_loss_limit_pct=0.50,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="same_close",
        slippage=0.0,
    )

    def sig_fn(row, prev):
        if row.name == pd.Timestamp("2020-01-02 10:00:00"): return PositionSide.LONG
        if row.name == pd.Timestamp("2020-01-02 10:01:00"): return PositionSide.SHORT
        if row.name == pd.Timestamp("2020-01-02 10:02:00"): return PositionSide.LONG
        if row.name == pd.Timestamp("2020-01-02 10:03:00"): return PositionSide.SHORT
        return None

    res = RiskEngineV2(cfg).run(df, sig_fn)
    cooldown_rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value]
    assert len(cooldown_rejections) >= 1, "Consecutive loss cooldown must be enforced on same_close reversals."


# ============================================================================
# 5. Data Validation & Boundary Invariants
# ============================================================================

def test_data_validation_rejects_nan_and_inf():
    """
    Suspected Failure Mode: NaN in OHLC prices slips through (df['Low'] <= 0).any() because
    nan <= 0 is False, crashing unhandled in sizing or simulation routines.
    Expected Invariant: Data validation must raise ValueError on NaN or Inf prices.
    """
    records = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": float("nan"), "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
    ]
    df = make_candles(records)
    cfg = RiskEngineConfigV2.test_fixture()
    with pytest.raises(ValueError, match="Non-finite price"):
        RiskEngineV2(cfg).run(df, lambda r, p: None)


def test_no_position_or_order_carry_across_session_boundary():
    """Verify pending orders at 15:29 are strictly rejected and not carried into 09:15 next day."""
    candles = [
        {"time": "2020-01-02 15:29:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-03 09:15:00", "open": 302.0, "high": 303.0, "low": 301.0, "close": 302.0, "atr": 4.0},
        {"time": "2020-01-03 09:16:00", "open": 302.0, "high": 303.0, "low": 301.0, "close": 302.0, "atr": 4.0},
    ]
    df = make_candles(candles)
    cfg = RiskEngineConfigV2.test_fixture(execution_model="next_open")
    res = RiskEngineV2(cfg).run(df, lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 15:29:00") else None)

    assert len(res.trades) == 0
    rejections = [r for r in res.audit_rejections if r["reason"] == RejectionReason.DAY_ROLLOVER_CANCELLED.value]
    assert len(rejections) == 1
    assert rejections[0]["time"] == pd.Timestamp("2020-01-03 09:15:00")


def test_signal_on_final_bar_does_not_execute_or_corrupt():
    """Verify that a signal on the very last bar of a partition does not create an orphan trade."""
    candles = [
        {"time": "2020-01-02 15:28:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
        {"time": "2020-01-02 15:29:00", "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.0, "atr": 4.0},
    ]
    df = make_candles(candles)
    cfg = RiskEngineConfigV2.test_fixture(execution_model="next_open")
    res = RiskEngineV2(cfg).run(df, lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 15:29:00") else None)
    assert len(res.trades) == 0


def test_deterministic_replay_and_hash_stability():
    """Verify bit-for-bit identical trade log hash across repeated invocations."""
    candles = [
        {"time": "2020-01-02 10:00:00", "open": 300.0, "high": 302.0, "low": 299.0, "close": 301.0, "atr": 4.0},
        {"time": "2020-01-02 10:01:00", "open": 301.0, "high": 308.0, "low": 300.0, "close": 307.0, "atr": 4.0},
        {"time": "2020-01-02 10:02:00", "open": 307.0, "high": 309.0, "low": 302.0, "close": 304.0, "atr": 4.0},
        {"time": "2020-01-02 10:03:00", "open": 304.0, "high": 305.0, "low": 290.0, "close": 292.0, "atr": 4.0},
    ]
    df = make_candles(candles)
    cfg = RiskEngineConfigV2.test_fixture()
    r1 = RiskEngineV2(cfg).run(df, lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:00:00") else None)
    r2 = RiskEngineV2(cfg).run(df, lambda r, p: PositionSide.LONG if r.name == pd.Timestamp("2020-01-02 10:00:00") else None)

    assert r1.trade_log_hash == r2.trade_log_hash
    assert len(r1.trade_log_hash) == 64

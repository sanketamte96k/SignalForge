"""
SignalForge Phase 24G.14 — Independent Cost Model and Alpha Investigation Tests
================================================================================
Validates statutory Indian intraday equity transaction friction calculations,
turnover accounting, morning window slippage dynamics, and the mathematical
mechanics behind the trade count discrepancy (3,948 vs 962 trades).
"""

import pytest
import pandas as pd
from datetime import time as dtime

from src.backtest.risk_engine_v2 import (
    CostBreakdown,
    CostModelType,
    PositionSide,
    RejectionReason,
    calculate_transaction_costs,
    calculate_position_size,
    calculate_clamped_stop_distance,
)


def test_statutory_charges_large_turnover_long():
    """Verify statutory Indian fees on a large turnover LONG trade (brokerage capped at Rs 20/leg)."""
    # 1000 shares @ entry 400.0, exit 402.0
    entry_p = 400.0
    exit_p = 402.0
    qty = 1000
    entry_turnover = entry_p * qty  # 400,000
    exit_turnover = exit_p * qty   # 402,000
    total_turnover = entry_turnover + exit_turnover  # 802,000

    cb = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        entry_time=pd.Timestamp("2020-01-02 10:15:00"),
        exit_time=pd.Timestamp("2020-01-02 10:45:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
        slippage_per_share=0.0,
    )

    # 1. Brokerage: min(20, 0.05% of 400k = 200) -> 20.0 per leg = 40.0
    assert cb.brokerage == 40.0

    # 2. STT: 0.025% on sell side (exit for LONG) = 402,000 * 0.00025 = 100.50
    assert cb.stt == pytest.approx(100.50, rel=1e-4)

    # 3. NSE turnover charges: 0.00297% on total turnover = 802,000 * 0.0000297 = 23.8194
    assert cb.exchange_charges == pytest.approx(23.8194, rel=1e-4)

    # 4. SEBI charges: 0.0001% on total turnover = 802,000 * 0.000001 = 0.8020
    assert cb.sebi_charges == pytest.approx(0.8020, rel=1e-4)

    # 5. Stamp duty: 0.003% on buy side (entry for LONG) = 400,000 * 0.00003 = 12.0
    assert cb.stamp_duty == pytest.approx(12.0, rel=1e-4)

    # 6. GST: 18% on (Brokerage + NSE + SEBI) = 0.18 * (40.0 + 23.8194 + 0.8020) = 0.18 * 64.6214 = 11.631852
    assert cb.gst == pytest.approx(11.6319, rel=1e-4)

    # 7. Slippage: 2 bps on entry (after 09:30) and 2 bps on exit
    # entry: max(400,000 * 0.0002 = 80.0, 50.0) = 80.0
    # exit: max(402,000 * 0.0002 = 80.4, 50.0) = 80.4
    # total slippage = 160.40
    assert cb.slippage == pytest.approx(160.40, rel=1e-4)

    expected_total = 40.0 + 100.50 + 23.8194 + 0.8020 + 12.0 + 11.631852 + 160.40
    assert cb.total_costs == pytest.approx(expected_total, rel=1e-4)


def test_statutory_charges_short_side_asymmetry():
    """Verify STT and Stamp Duty side asymmetry for SHORT positions (STT on entry, Stamp duty on exit)."""
    entry_p = 350.0
    exit_p = 345.0
    qty = 500
    entry_turnover = entry_p * qty  # 175,000
    exit_turnover = exit_p * qty   # 172,500

    cb = calculate_transaction_costs(
        side=PositionSide.SHORT,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        entry_time=pd.Timestamp("2020-01-02 11:00:00"),
        exit_time=pd.Timestamp("2020-01-02 11:30:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )

    # For SHORT: Entry is Sell, Exit is Buy
    # STT must be assessed on entry turnover (175,000 * 0.00025 = 43.75)
    assert cb.stt == pytest.approx(43.75, rel=1e-4)

    # Stamp duty must be assessed on exit turnover (172,500 * 0.00003 = 5.175)
    assert cb.stamp_duty == pytest.approx(5.175, rel=1e-4)


def test_statutory_charges_small_turnover_minimum_tick_slippage():
    """Verify that small turnover trades correctly hit the Rs 0.05/share minimum tick slippage floor."""
    entry_p = 300.0
    exit_p = 305.0
    qty = 2  # Total turnover = 600 + 610 = 1210
    entry_turnover = 600.0
    exit_turnover = 610.0

    cb = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=qty,
        entry_time=pd.Timestamp("2020-01-02 10:00:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )

    # Brokerage: 0.05% of 600 = 0.30 (< 20); exit: 0.05% of 610 = 0.305 (< 20) -> 0.605
    assert cb.brokerage == pytest.approx(0.605, rel=1e-4)

    # Slippage at 2 bps would be 600 * 0.0002 = 0.12.
    # But min tick slippage is 0.05 * 2 = 0.10.
    # Here 0.12 > 0.10, so 0.12 is taken.
    # What if price is 100? Turnover = 200, 2 bps = 0.04. Min tick 0.05 * 2 = 0.10 -> 0.10 floor binds!
    cb_low = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=100.0,
        exit_price=100.0,
        quantity=2,
        entry_time=pd.Timestamp("2020-01-02 10:00:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )
    # Entry: max(200 * 0.0002 = 0.04, 0.05 * 2 = 0.10) = 0.10
    # Exit: max(200 * 0.0002 = 0.04, 0.05 * 2 = 0.10) = 0.10
    # Total slippage = 0.20
    assert cb_low.slippage == pytest.approx(0.20, rel=1e-4)


def test_morning_window_slippage_rate():
    """Verify 5 bps entry slippage rate applies in morning window (09:15–09:30) vs 2 bps afterwards."""
    # Morning trade at 09:20:00
    cb_morning = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=500.0,
        exit_price=500.0,
        quantity=1000,
        entry_time=pd.Timestamp("2020-01-02 09:20:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )
    # Entry turnover = 500,000 * 0.0005 (5 bps) = 250.0
    # Exit turnover = 500,000 * 0.0002 (2 bps) = 100.0
    # Total slippage = 350.0
    assert cb_morning.slippage == pytest.approx(350.0, rel=1e-4)

    # Post-morning trade at 10:00:00
    cb_post = calculate_transaction_costs(
        side=PositionSide.LONG,
        entry_price=500.0,
        exit_price=500.0,
        quantity=1000,
        entry_time=pd.Timestamp("2020-01-02 10:00:00"),
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )
    # Entry turnover = 500,000 * 0.0002 = 100.0
    # Exit turnover = 500,000 * 0.0002 = 100.0
    # Total slippage = 200.0
    assert cb_post.slippage == pytest.approx(200.0, rel=1e-4)


def test_rejection_mechanics_trade_count_discrepancy():
    """
    Verify the mathematical cause of the 3,948 vs 962 trade count discrepancy:
    When capital is depleted below (Price / MaxLeverage), quantity drops to 0,
    causing continuous INSUFFICIENT_CAPITAL rejections.
    """
    stock_price = 350.0
    stop_dist = 1.0
    max_leverage = 5.0
    risk_pct = 0.01

    # Case A: Capital = Rs 1,000 (solvent, small size)
    qty_a = calculate_position_size(
        capital=1000.0,
        risk_pct=risk_pct,
        entry_price=stock_price,
        stop_distance=stop_dist,
        max_leverage=max_leverage,
    )
    # q_risk = floor(1000 * 0.01 / 1.0) = 10
    # q_leverage = floor(1000 * 5 / 350) = 14
    # qty = min(10, 14) = 10
    assert qty_a == 10

    # Case B: Capital = Rs 312.81 (ending capital of 1 bps baseline run)
    qty_b = calculate_position_size(
        capital=312.81,
        risk_pct=risk_pct,
        entry_price=stock_price,
        stop_distance=stop_dist,
        max_leverage=max_leverage,
    )
    # q_risk = floor(3.1281 / 1.0) = 3
    # q_leverage = floor(1564.05 / 350) = 4
    # qty = min(3, 4) = 3 >= 1 (TRADE IS PERMITTED)
    assert qty_b == 3

    # Case C: Capital = Rs 52.28 (ending capital of realistic cost run in April 2020)
    qty_c = calculate_position_size(
        capital=52.28,
        risk_pct=risk_pct,
        entry_price=stock_price,
        stop_distance=stop_dist,
        max_leverage=max_leverage,
    )
    # q_risk = floor(0.5228 / 1.0) = 0
    # q_leverage = floor(261.4 / 350) = 0
    # qty = 0 < 1 -> INSUFFICIENT_CAPITAL REJECTION!
    assert qty_c == 0

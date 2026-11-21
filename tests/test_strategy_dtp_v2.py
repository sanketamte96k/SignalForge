"""
SignalForge — Phase 32E.1: Dedicated DTP-V2 Strategy Unit Tests
==============================================================
File: tests/test_strategy_dtp_v2.py

Isolated unit test suite for DTP-V2 (Delivery Trend-Pullback V2) swing strategy.
Uses purely synthetic in-memory fixtures.
Strictly zero historical dataset loading.

Covers all Phase 32E.1 regression mandates:
  1. 2.0x ATR Chandelier calculation (HH - 2.0 * ATR)
  2. Highest-high anchor updates
  3. Stop never moves downward for a long position (non-ratcheting monotonicity)
  4. Stop activation timing and no lookahead
  5. Gap-through-stop execution (slippage against position)
  6. Initial stop behavior
  7. +3.0R target behavior
  8. 10-session exit when MFE < 1.5R
  9. Excursion bypass when MFE >= 1.5R
  10. Position sizing parity with DTP-V1
  11. Entry signal generation parity with DTP-V1
  12. Immutability verification of DTP-V1
  13. Breakeven stop progression at +1.0R
  14. Trend breakdown (2 closes < EMA50) and Dynamic Overbought exits
  15. End-to-End Orchestrator (DTPV2Strategy) lifecycle
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest

# DTP-V1 imports for immutability and parity verification
from src.strategy.dtp_v1.config import DTPV1Config
from src.strategy.dtp_v1.risk_manager import calculate_dtp_position_size as calc_size_v1
from src.strategy.dtp_v1.signal_engine import (
    evaluate_exit_conditions as eval_exit_v1,
    generate_eod_signal as gen_signal_v1,
)

# DTP-V2 imports
from src.strategy.dtp_v2.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV2Config,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import (
    calculate_dtp_roundtrip_costs,
)
from src.strategy.dtp_v2.indicators import (
    calculate_atr,
    calculate_dtp_indicators,
    calculate_ema,
    calculate_rsi,
)
from src.strategy.dtp_v2.portfolio_rules import (
    DTPPortfolioTracker,
)
from src.strategy.dtp_v2.risk_manager import (
    calculate_dtp_position_size,
)
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)
from src.strategy.dtp_v2.strategy import (
    DTPV2Strategy,
)


# ---------------------------------------------------------------------------
# Synthetic In-Memory Data Generator
# ---------------------------------------------------------------------------

def make_synthetic_ohlcv(
    n_bars: int = 120,
    start_price: float = 1000.0,
    regime: str = "uptrend",
    start_date: date = date(2018, 1, 1),
) -> pd.DataFrame:
    """Creates deterministic synthetic daily OHLCV dataframe."""
    dates = [start_date + timedelta(days=i) for i in range(n_bars)]
    prices = [start_price]

    for i in range(1, n_bars):
        prev = prices[-1]
        if regime == "uptrend":
            drift = 1.5 if (i % 15) < 10 else -1.2
        elif regime == "downtrend":
            drift = -1.8 if (i % 15) < 10 else 0.8
        else:
            drift = 1.0 if (i % 10) < 5 else -1.0
        prices.append(max(50.0, prev + drift))

    opens, highs, lows, closes, volumes = [], [], [], [], []
    for i, c in enumerate(prices):
        prev_c = prices[i - 1] if i > 0 else c
        o = (prev_c + c) / 2.0
        h = max(o, c) + 3.0
        l = min(o, c) - 2.5
        v = 100000.0 + (10000.0 if (c > o) else -10000.0) + (i * 100.0)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(max(1000.0, v))

    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=pd.DatetimeIndex(dates),
    )


# ---------------------------------------------------------------------------
# Test Suite: DTP-V2 Core Regression Requirements
# ---------------------------------------------------------------------------

def test_01_chandelier_2_0_atr_calculation():
    """
    Verify Chandelier trailing stop calculation in DTP-V2:
      Chandelier Stop = Highest High - (2.0 * ATR)
    """
    cfg = DTPV2Config()
    assert cfg.trailing_atr_mult == 2.0
    assert cfg.name == "DTP-V2"

    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1005.0,
        r_distance=30.0,  # 1R = 30.0 -> +1.5R = 1045.0
        highest_high=1032.0,
        highest_close=1028.0,
        is_breakeven_activated=True,
    )

    # Bar achieves High 1050.0 (+1.67R >= 1.5R), Close 1045.0, ATR = 10.0
    # Expected Chandelier Stop = Highest High (1050.0) - (2.0 * 10.0) = 1030.0
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1050.0,
        current_low=1025.0,
        current_close=1045.0,
        current_open=1030.0,
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=65.0,
        current_bb_upper=1080.0,
        config=cfg,
    )

    assert reason is None  # Held
    assert pos.is_trailing_activated is True
    assert pos.highest_high == 1050.0
    assert pos.current_stop_price == pytest.approx(1030.0)


def test_02_highest_high_anchor_updates():
    """
    Verify that subsequent higher highs dynamically advance the anchor and the stop.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1030.0,
        r_distance=30.0,
        highest_high=1050.0,
        highest_close=1045.0,
        is_trailing_activated=True,
    )

    # Next bar makes a new High of 1065.0, Close 1060.0, ATR = 10.0
    # Expected Chandelier Stop = 1065.0 - (2.0 * 10.0) = 1045.0
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1065.0,
        current_low=1040.0,
        current_close=1060.0,
        current_open=1045.0,
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=70.0,
        current_bb_upper=1090.0,
        config=cfg,
    )

    assert reason is None
    assert pos.highest_high == 1065.0
    assert pos.current_stop_price == pytest.approx(1045.0)


def test_03_stop_never_moves_downward_monotonicity():
    """
    Verify non-ratcheting monotonicity: stop price NEVER moves downward for a long position,
    even if ATR expands or subsequent bars make lower highs.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1045.0,  # Previous stop was 1045.0
        r_distance=30.0,
        highest_high=1065.0,
        highest_close=1060.0,
        is_trailing_activated=True,
    )

    # Next bar is an inside consolidation day with higher volatility:
    # High=1055.0, Low=1046.0, ATR expands to 15.0
    # Formula would produce: 1065.0 - (2.0 * 15.0) = 1035.0 (which is lower than 1045.0)
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1055.0,
        current_low=1046.0,
        current_close=1050.0,
        current_open=1052.0,
        current_atr=15.0,
        current_ema50=950.0,
        current_rsi=65.0,
        current_bb_upper=1090.0,
        config=cfg,
    )

    assert reason is None
    # Stop must remain at 1045.0 and NOT drop to 1035.0
    assert pos.current_stop_price == pytest.approx(1045.0)


def test_04_stop_activation_timing_and_no_lookahead():
    """
    Verify causal timing:
      - Bar T's Low is checked against the stop established BEFORE Bar T.
      - The trailing stop calculated from Bar T's completed data only applies to Bar T+1 onwards.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,  # Established prior to Bar T
        r_distance=30.0,
        highest_high=1000.0,
        highest_close=1000.0,
    )

    # Bar T: Huge surge from Open 1005 to High 1055, Low was 1002 (well above 970).
    # Stop updates to 1055 - 2*10 = 1035.0 at EOD of Bar T.
    reason_t, exit_px_t, _ = evaluate_exit_conditions(
        pos=pos,
        current_high=1055.0,
        current_low=1002.0,
        current_close=1050.0,
        current_open=1005.0,
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=68.0,
        current_bb_upper=1080.0,
        config=cfg,
    )
    assert reason_t is None  # Bar T was held
    assert pos.current_stop_price == pytest.approx(1035.0)

    # Bar T+1: Opens at 1040, drops to Low 1030 (violates the 1035 stop established on Bar T).
    reason_t1, exit_px_t1, _ = evaluate_exit_conditions(
        pos=pos,
        current_high=1042.0,
        current_low=1030.0,  # <= 1035.0
        current_close=1032.0,
        current_open=1040.0,
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=60.0,
        current_bb_upper=1080.0,
        config=cfg,
    )
    assert reason_t1 == DTPExitReason.TRAILING_STOP
    # Filled at min(Open, Stop) = 1035.0 minus 3 bps friction
    assert exit_px_t1 == pytest.approx(1035.0 * (1.0 - 0.0003), rel=1e-5)


def test_05_gap_through_stop_execution():
    """
    Verify that if session opens below stop price, exit fills at Open (adverse gap slippage),
    NOT at the higher stop price.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1030.0,  # Stop is 1030.0
        r_distance=30.0,
        highest_high=1050.0,
        highest_close=1045.0,
        is_trailing_activated=True,
    )

    # Adverse gap-down: Opens at 1015.0 (below 1030.0 stop), Low is 1010.0
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1020.0,
        current_low=1010.0,
        current_close=1018.0,
        current_open=1015.0,  # Open below stop
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=55.0,
        current_bb_upper=1080.0,
        config=cfg,
    )

    assert reason == DTPExitReason.TRAILING_STOP
    # Must fill at open price (1015.0) minus friction, not 1030.0
    expected_exit = 1015.0 * (1.0 - 0.0003)
    assert exit_px == pytest.approx(expected_exit, rel=1e-5)


def test_06_initial_stop_behavior():
    """
    Verify initial stop-loss triggers before any breakeven or trailing stop activates.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,
        highest_high=1005.0,  # Excursion < 1.0R
        highest_close=1002.0,
    )

    # Low hits 968.0 (<= 970.0 stop)
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=995.0,
        current_low=968.0,
        current_close=972.0,
        current_open=990.0,
        current_atr=12.0,
        current_ema50=950.0,
        current_rsi=45.0,
        current_bb_upper=1030.0,
        config=cfg,
    )

    assert reason == DTPExitReason.INITIAL_STOP
    assert exit_px == pytest.approx(970.0 * (1.0 - 0.0003), rel=1e-5)


def test_07_profit_target_at_3r_behavior():
    """
    Verify full +3.0R profit target exit is preserved and functions accurately.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1040.0,
        r_distance=30.0,  # +3.0R target = 1090.0
        highest_high=1070.0,
        highest_close=1065.0,
        is_trailing_activated=True,
    )

    # Bar achieves High 1095.0 (>= 1090.0)
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1095.0,
        current_low=1060.0,
        current_close=1085.0,
        current_open=1065.0,
        current_atr=12.0,
        current_ema50=950.0,
        current_rsi=74.0,
        current_bb_upper=1110.0,
        config=cfg,
    )

    assert reason == DTPExitReason.PROFIT_TARGET
    assert exit_px == pytest.approx(1090.0 * (1.0 - 0.0003), rel=1e-5)


def test_08_10_session_exit_when_mfe_below_1_5r():
    """
    Verify that a position held for 10 sessions exits at Session 10 Close
    if maximum favorable excursion remains below 1.5R.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,  # 1.5R = 45.0 (1045.0)
        highest_high=1025.0,  # Excursion = 25 / 30 = 0.83R (< 1.5R)
        highest_close=1020.0,
        holding_days=9,       # Reaches 10 on this bar
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1022.0,
        current_low=1008.0,
        current_close=1015.0,
        current_open=1012.0,
        current_atr=10.0,
        current_ema50=960.0,
        current_rsi=54.0,
        current_bb_upper=1040.0,
        config=cfg,
    )

    assert reason == DTPExitReason.TIME_LIMIT
    assert pos.holding_days == 10
    assert exit_px == pytest.approx(1015.0 * (1.0 - 0.0003), rel=1e-5)


def test_09_excursion_bypass_when_mfe_reaches_1_5r():
    """
    Verify Phase 32D.6 excursion bypass: if maximum favorable excursion >= 1.5R,
    the position BYPASSES the 10-session exit and continues trailing into session 11+.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1010.0,
        r_distance=30.0,  # 1.5R = 45.0 (1045.0)
        highest_high=1048.0,  # Excursion = 48 / 30 = 1.60R (>= 1.5R)
        highest_close=1042.0,
        holding_days=9,       # Reaches 10 on this bar
        is_trailing_activated=True,
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1046.0,
        current_low=1030.0,
        current_close=1040.0,
        current_open=1035.0,
        current_atr=10.0,
        current_ema50=960.0,
        current_rsi=62.0,
        current_bb_upper=1060.0,
        config=cfg,
    )

    # Must NOT exit on TIME_LIMIT because excursion >= 1.5R!
    assert reason is None
    assert pos.holding_days == 10
    assert "Hold position" in msg


def test_10_position_sizing_parity_with_dtp_v1():
    """
    Verify position sizing calculation in DTP-V2 produces exact parity with DTP-V1
    under identical equity, cash, entry price, stop price, and sector exposures.
    """
    cfg_v1 = DTPV1Config()
    cfg_v2 = DTPV2Config()

    # Approved cases where notional >= ₹5,000
    approved_cases = [
        (100000.0, 100000.0, 1000.0, 970.0, "Information Technology", 0.0),
        (100000.0, 50000.0, 500.0, 480.0, "Energy", 20000.0),
        (250000.0, 150000.0, 150.0, 140.0, "Automobile", 50000.0),
    ]

    for eq, cash, entry_px, stop_px, sector, sec_exp in approved_cases:
        shares_v1, msg_v1 = calc_size_v1(eq, cash, entry_px, stop_px, sector, sec_exp, cfg_v1)
        shares_v2, msg_v2 = calculate_dtp_position_size(eq, cash, entry_px, stop_px, sector, sec_exp, cfg_v2)

        assert shares_v2 == shares_v1
        assert shares_v2 > 0
        assert msg_v2 == msg_v1

    # Rejected case where notional < ₹5,000 floor
    floor_rejected_case = (100000.0, 10000.0, 2500.0, 2400.0, "Financial Services", 35000.0)
    eq, cash, entry_px, stop_px, sector, sec_exp = floor_rejected_case
    shares_v1, msg_v1 = calc_size_v1(eq, cash, entry_px, stop_px, sector, sec_exp, cfg_v1)
    shares_v2, msg_v2 = calculate_dtp_position_size(eq, cash, entry_px, stop_px, sector, sec_exp, cfg_v2)
    assert shares_v2 == shares_v1 == 0
    assert "below minimum efficiency floor" in msg_v2
    assert "below minimum efficiency floor" in msg_v1


def test_11_entry_signal_parity_with_dtp_v1():
    """
    Verify that EOD signal generation produces identical signals between DTP-V1 and DTP-V2.
    """
    df = make_synthetic_ohlcv(n_bars=120, start_price=1000.0, regime="uptrend")
    cfg_v1 = DTPV1Config()
    cfg_v2 = DTPV2Config()

    df_ind_v1 = calculate_dtp_indicators(df, config=cfg_v2)  # indicators are identical

    sig_v1 = gen_signal_v1("INFY", df_ind_v1, DTPRegimeState.BULLISH, cfg_v1, bar_idx=100)
    sig_v2 = generate_eod_signal("INFY", df_ind_v1, DTPRegimeState.BULLISH, cfg_v2, bar_idx=100)

    if sig_v1 is None:
        assert sig_v2 is None
    else:
        assert sig_v2 is not None
        assert sig_v2.symbol == sig_v1.symbol
        assert sig_v2.entry_trigger_price == pytest.approx(sig_v1.entry_trigger_price)
        assert sig_v2.initial_stop_price == pytest.approx(sig_v1.initial_stop_price)
        assert sig_v2.r_distance == pytest.approx(sig_v1.r_distance)
        assert sig_v2.action == sig_v1.action


def test_12_dtp_v1_immutability():
    """
    Verify DTP-V1 configuration and logic remain completely untouched and unaltered.
    """
    cfg_v1 = DTPV1Config()
    assert cfg_v1.name == "DTP-V1"
    assert cfg_v1.trailing_atr_mult == 1.5  # DTP-V1 stays 1.5

    cfg_v2 = DTPV2Config()
    assert cfg_v2.name == "DTP-V2"
    assert cfg_v2.trailing_atr_mult == 2.0  # DTP-V2 is 2.0


def test_13_breakeven_stop_progression_at_1r():
    """
    Verify stop advances to breakeven (entry + 0.50% buffer) once price achieves +1.0R.
    """
    cfg = DTPV2Config()
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,  # 1.0R = 30.0 -> +1.0R = 1030.0
        highest_high=1000.0,
        highest_close=1000.0,
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1032.0,  # Crosses 1030.0
        current_low=998.0,
        current_close=1028.0,
        current_open=1005.0,
        current_atr=15.0,
        current_ema50=950.0,
        current_rsi=60.0,
        current_bb_upper=1060.0,
        config=cfg,
    )

    assert reason is None
    assert pos.is_breakeven_activated is True
    # Breakeven stop = 1000.0 * 1.005 = 1005.0
    assert pos.current_stop_price == pytest.approx(1005.0)


def test_14_trend_breakdown_and_dynamic_overbought():
    """
    Verify trend breakdown (2 closes < EMA50) and dynamic overbought exits.
    """
    cfg = DTPV2Config()

    # Breakdown test
    pos_bd = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=950.0,
        current_stop_price=950.0,
        r_distance=50.0,
        highest_high=1010.0,
        highest_close=1005.0,
        consecutive_closes_below_ema50=1,
    )
    reason_bd, _, _ = evaluate_exit_conditions(
        pos=pos_bd,
        current_high=980.0,
        current_low=960.0,
        current_close=965.0,
        current_open=978.0,
        current_atr=15.0,
        current_ema50=970.0,
        current_rsi=35.0,
        current_bb_upper=1030.0,
        config=cfg,
    )
    assert reason_bd == DTPExitReason.TREND_BREAKDOWN

    # Overbought test
    pos_ob = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1020.0,
        r_distance=30.0,
        highest_high=1060.0,
        highest_close=1055.0,
    )
    reason_ob, _, _ = evaluate_exit_conditions(
        pos=pos_ob,
        current_high=1082.0,
        current_low=1050.0,
        current_close=1075.0,
        current_open=1052.0,
        current_atr=12.0,
        current_ema50=960.0,
        current_rsi=80.5,
        current_bb_upper=1080.0,
        config=cfg,
    )
    assert reason_ob == DTPExitReason.DYNAMIC_OVERBOUGHT


def test_15_dtp_v2_orchestrator_lifecycle():
    """
    Verify complete DTPV2Strategy lifecycle orchestration:
      evaluate_eod -> execute_next_open -> evaluate_position_exits with delivery costs.
    """
    strat = DTPV2Strategy(initial_capital=100000.0)
    assert strat.config.name == "DTP-V2"
    assert strat.config.trailing_atr_mult == 2.0

    # Create dummy signal manually to test execute_next_open
    sig = DTPEODSignal(
        symbol="INFY",
        signal_date=date(2018, 5, 11),
        action=OrderAction.ENTER_LONG,
        entry_trigger_price=1000.0,
        initial_stop_price=970.0,
        r_distance=30.0,
        regime=DTPRegimeState.BULLISH,
    )
    strat.pending_signals["INFY"] = sig

    # Execute at next open 1005.0
    action, pos, msg = strat.execute_next_open("INFY", 1005.0, date(2018, 5, 12))
    assert action == OrderAction.ENTER_LONG
    assert pos is not None
    assert pos.symbol == "INFY"
    assert strat.portfolio.cash < 100000.0

    # Evaluate exit with profit target hit
    bar = pd.Series({
        "open": 1050.0,
        "high": 1100.0,  # >= 1005 + 3.0*30 = 1095.0 target
        "low": 1040.0,
        "close": 1090.0,
        "atr": 10.0,
        "ema_slow": 960.0,
        "rsi": 70.0,
        "bb_upper": 1110.0,
    })

    reason, cost_summary, exit_msg = strat.evaluate_position_exits("INFY", bar, date(2018, 5, 20))
    assert reason == DTPExitReason.PROFIT_TARGET
    assert cost_summary is not None
    assert cost_summary.net_pnl > 0.0
    assert len(strat.closed_trades) == 1
    assert "INFY" not in strat.portfolio.positions

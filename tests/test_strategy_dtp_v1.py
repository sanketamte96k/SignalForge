"""
SignalForge — Phase 32C.5: Dedicated DTP-V1 Strategy Unit Tests
==============================================================
File: tests/test_strategy_dtp_v1.py

Unit test suite for DTP-V1 (Delivery Trend-Pullback V1) swing strategy.
Uses purely synthetic in-memory data fixtures.
Strictly zero historical dataset loading.

Covers:
  1. Technical Indicators & Causal Lagging (Tests 1-6)
  2. Market Regime & Breadth Filter (Tests 7-11)
  3. Stock Trend & Pullback Identification (Tests 12-14)
  4. Signal Generation & Gap Execution (Tests 15-18)
  5. Exit Hierarchy & Trailing Progression (Tests 19-25)
  6. Position Sizing & Portfolio Risk Constraints (Tests 26-33)
  7. Delivery Cost Engine Integration (Tests 34-36)
  8. End-to-End Orchestration & Safety Handling (Tests 37-38)
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest

from src.strategy.dtp_v1.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV1Config,
    OrderAction,
)
from src.strategy.dtp_v1.cost_integration import (
    calculate_dtp_roundtrip_costs,
    calculate_pending_entry_costs,
)
from src.strategy.dtp_v1.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_dtp_indicators,
    calculate_ema,
    calculate_relative_strength,
    calculate_rsi,
    calculate_sma,
    calculate_tr,
)
from src.strategy.dtp_v1.market_filter import (
    evaluate_breadth_regime,
    evaluate_nifty_regime,
    get_market_regime,
)
from src.strategy.dtp_v1.portfolio_rules import (
    DTPActivePosition,
    DTPPortfolioTracker,
)
from src.strategy.dtp_v1.risk_manager import (
    calculate_dtp_position_size,
)
from src.strategy.dtp_v1.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    check_reversal_trigger,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
    is_pullback_active,
    is_trend_aligned,
)
from src.strategy.dtp_v1.strategy import (
    DTPV1Strategy,
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
    """Creates deterministic synthetic daily OHLCV dataframe with realistic price structure."""
    dates = [start_date + timedelta(days=i) for i in range(n_bars)]
    prices = [start_price]

    for i in range(1, n_bars):
        prev = prices[-1]
        if regime == "uptrend":
            # Rising drift + cyclical pullbacks
            drift = 1.5 if (i % 15) < 10 else -1.2
        elif regime == "downtrend":
            drift = -1.8 if (i % 15) < 10 else 0.8
        elif regime == "sideways":
            drift = 1.0 if (i % 10) < 5 else -1.0
        else:
            drift = 0.0
        prices.append(max(50.0, prev + drift))

    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

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

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
        index=pd.DatetimeIndex(dates),
    )
    return df


# ---------------------------------------------------------------------------
# Suite 1: Technical Indicators & Causal Lagging (Tests 1-6)
# ---------------------------------------------------------------------------

def test_01_ema_and_sma_calculation():
    """Verify EMA and SMA produce mathematically valid smoothed series."""
    series = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
    sma = calculate_sma(series, period=3)
    ema = calculate_ema(series, period=3)

    assert pd.isna(sma.iloc[0]) and pd.isna(sma.iloc[1])
    assert sma.iloc[2] == pytest.approx(11.0)
    assert sma.iloc[5] == pytest.approx(14.0)
    assert ema.iloc[-1] > ema.iloc[0]


def test_02_atr_wilder_smoothing():
    """Verify ATR computes true range and smooths via Wilder's formula."""
    df = make_synthetic_ohlcv(n_bars=30)
    atr = calculate_atr(df["high"], df["low"], df["close"], period=14)
    assert len(atr) == 30
    assert (atr > 0).all()
    # High - Low spread is around 5.5, so ATR should be in 5.0 to 6.5 range
    assert 4.0 <= atr.iloc[-1] <= 7.0


def test_03_rsi_wilder_smoothing():
    """Verify RSI responds to price advances and declines within [0, 100]."""
    # Monotonically increasing closes should have RSI near 100
    up_series = pd.Series([100.0 + i * 2.0 for i in range(30)])
    rsi_up = calculate_rsi(up_series, period=14)
    assert rsi_up.iloc[-1] > 90.0

    # Monotonically decreasing closes should have RSI near 0
    down_series = pd.Series([200.0 - i * 2.0 for i in range(30)])
    rsi_down = calculate_rsi(down_series, period=14)
    assert rsi_down.iloc[-1] < 10.0


def test_04_adx_directional_system():
    """Verify ADX, +DI, and -DI accurately reflect directional movement."""
    df = make_synthetic_ohlcv(n_bars=50, regime="uptrend")
    adx, plus_di, minus_di = calculate_adx(df["high"], df["low"], df["close"], period=14)

    assert len(adx) == 50
    # In an established uptrend, +DI should dominate -DI
    assert plus_di.iloc[-1] > minus_di.iloc[-1]
    assert 0.0 <= adx.iloc[-1] <= 100.0


def test_05_bollinger_bands_and_swing_levels():
    """Verify Bollinger Bands and 20-day swing boundaries envelope price."""
    df = make_synthetic_ohlcv(n_bars=60)
    upper, mid, lower = calculate_bollinger_bands(df["close"], period=20, num_std=2.5)

    assert (upper.iloc[25:] >= mid.iloc[25:]).all()
    assert (mid.iloc[25:] >= lower.iloc[25:]).all()

    augmented = calculate_dtp_indicators(df)
    assert "swing_high_20" in augmented.columns
    assert "swing_low_20" in augmented.columns


def test_06_causal_no_lookahead_guarantee():
    """Verify indicators at Bar T do NOT change when future bars T+1, T+2 are mutated."""
    df1 = make_synthetic_ohlcv(n_bars=50, regime="uptrend")
    df2 = df1.copy()

    # Mutate the last 5 bars in df2 dramatically
    df2.iloc[-5:, df2.columns.get_loc("close")] *= 2.5
    df2.iloc[-5:, df2.columns.get_loc("high")] *= 2.5

    res1 = calculate_dtp_indicators(df1)
    res2 = calculate_dtp_indicators(df2)

    # Values at Bar 40 (prior to mutation) must be bit-for-bit identical
    for col in ["ema_fast", "ema_slow", "atr", "rsi", "adx", "swing_high_20"]:
        assert res1[col].iloc[40] == pytest.approx(res2[col].iloc[40])


# ---------------------------------------------------------------------------
# Suite 2: Market Regime & Breadth Filter (Tests 7-11)
# ---------------------------------------------------------------------------

def test_07_nifty_regime_bullish():
    """Verify NIFTY 50 uptrend qualifies as BULLISH regime."""
    df_nifty = make_synthetic_ohlcv(n_bars=100, regime="uptrend")
    regime, reason = evaluate_nifty_regime(df_nifty)
    assert regime == DTPRegimeState.BULLISH
    assert "confirmed uptrend" in reason


def test_08_nifty_regime_neutral():
    """Verify sideways NIFTY 50 qualifies as NEUTRAL regime."""
    df_nifty = make_synthetic_ohlcv(n_bars=220, regime="uptrend")
    # Pull close below EMA50 but keep above SMA200 for consolidating regime
    df_nifty.iloc[-5:, df_nifty.columns.get_loc("close")] = 1100.0
    regime, reason = evaluate_nifty_regime(df_nifty)
    assert regime == DTPRegimeState.NEUTRAL
    assert "consolidating" in reason


def test_09_nifty_regime_bearish():
    """Verify falling NIFTY 50 below moving averages triggers BEARISH regime."""
    df_nifty = make_synthetic_ohlcv(n_bars=100, regime="downtrend")
    regime, reason = evaluate_nifty_regime(df_nifty)
    assert regime == DTPRegimeState.BEARISH
    assert "downtrend" in reason or "below" in reason


def test_10_breadth_regime_fallback():
    """Verify universe breadth fallback evaluates ratio of stocks above EMA50."""
    u_bullish = {
        "S1": make_synthetic_ohlcv(80, regime="uptrend"),
        "S2": make_synthetic_ohlcv(80, regime="uptrend"),
        "S3": make_synthetic_ohlcv(80, regime="downtrend"),
    }
    regime_bull, _ = evaluate_breadth_regime(u_bullish)
    assert regime_bull == DTPRegimeState.BULLISH  # 2 of 3 stocks above EMA50 = 66.7%

    u_bearish = {
        "S1": make_synthetic_ohlcv(80, regime="downtrend"),
        "S2": make_synthetic_ohlcv(80, regime="downtrend"),
        "S3": make_synthetic_ohlcv(80, regime="uptrend"),
    }
    regime_bear, _ = evaluate_breadth_regime(u_bearish)
    assert regime_bear == DTPRegimeState.BEARISH  # 1 of 3 = 33.3% <= 33.3%


def test_11_market_regime_failsafe_unknown():
    """Verify missing or empty market inputs return UNKNOWN regime safely."""
    regime, reason = get_market_regime(nifty_df=None, universe_dfs=None)
    assert regime == DTPRegimeState.UNKNOWN
    assert "No market data" in reason


# ---------------------------------------------------------------------------
# Suite 3: Stock Trend & Pullback Identification (Tests 12-14)
# ---------------------------------------------------------------------------

def test_12_stock_trend_filter_acceptance_and_rejection():
    """Verify trend alignment checks: Close > EMA50, EMA20 > EMA50, ADX >= 20."""
    df = make_synthetic_ohlcv(n_bars=80, regime="uptrend")
    aug = calculate_dtp_indicators(df)
    aligned, msg = is_trend_aligned(aug, idx=75)
    assert aligned is True

    # Test rejection when Close < EMA50
    df_down = make_synthetic_ohlcv(n_bars=80, regime="downtrend")
    aug_down = calculate_dtp_indicators(df_down)
    aligned_down, msg_down = is_trend_aligned(aug_down, idx=75)
    assert aligned_down is False
    assert "Close" in msg_down or "EMA20" in msg_down or "ADX" in msg_down


def test_13_pullback_qualification_and_volume_contraction():
    """Verify pullback detection checks EMA20 proximity, EMA50 support, RSI 38-52."""
    df = make_synthetic_ohlcv(n_bars=80, regime="uptrend")
    aug = calculate_dtp_indicators(df)

    # Force bar 70 into a valid pullback state
    ema20_val = aug["ema_fast"].iloc[70]
    aug.iloc[70, aug.columns.get_loc("low")] = ema20_val * 1.002  # touches proximity within 1.0% of EMA20
    aug.iloc[70, aug.columns.get_loc("close")] = ema20_val * 1.005  # above EMA50
    aug.iloc[70, aug.columns.get_loc("rsi")] = 45.0  # in [38, 52] band
    aug.iloc[70, aug.columns.get_loc("volume")] = aug["volume_sma"].iloc[69] * 0.8  # contracting

    is_pb, pb_msg = is_pullback_active(aug, idx=70)
    assert is_pb is True


def test_14_reversal_trigger_confirmation():
    """Verify reversal bar reclaims EMA20 with expanding volume."""
    df = make_synthetic_ohlcv(n_bars=80, regime="uptrend")
    aug = calculate_dtp_indicators(df)

    # Set bar 70 as pullback
    ema20 = aug["ema_fast"].iloc[70]
    ema50 = aug["ema_slow"].iloc[70]
    aug.iloc[70, aug.columns.get_loc("low")] = ema20 * 0.999
    aug.iloc[70, aug.columns.get_loc("close")] = ema20 * 1.002
    aug.iloc[70, aug.columns.get_loc("rsi")] = 46.0

    # Set bar 71 as bullish reversal candle
    aug.iloc[71, aug.columns.get_loc("open")] = ema20 * 1.001
    aug.iloc[71, aug.columns.get_loc("close")] = ema20 * 1.015  # green candle > 20 EMA
    aug.iloc[71, aug.columns.get_loc("volume")] = aug["volume"].iloc[70] * 1.5  # expanding volume

    rev_ok, rev_msg = check_reversal_trigger(aug, idx=71)
    assert rev_ok is True


# ---------------------------------------------------------------------------
# Suite 4: Signal Generation & Gap Execution (Tests 15-18)
# ---------------------------------------------------------------------------

def test_15_eod_signal_generation_at_bar_close():
    """Verify EOD signal outputs correct trigger price, initial stop, and R-distance."""
    df = make_synthetic_ohlcv(n_bars=80, regime="uptrend")
    aug = calculate_dtp_indicators(df)

    # Stage setup on bar 75
    ema20 = aug["ema_fast"].iloc[74]
    aug.iloc[74, aug.columns.get_loc("low")] = ema20 * 0.998
    aug.iloc[74, aug.columns.get_loc("close")] = ema20 * 1.002
    aug.iloc[74, aug.columns.get_loc("rsi")] = 45.0

    aug.iloc[75, aug.columns.get_loc("open")] = ema20 * 1.001
    aug.iloc[75, aug.columns.get_loc("close")] = ema20 * 1.018
    aug.iloc[75, aug.columns.get_loc("volume")] = aug["volume"].iloc[74] * 1.3

    signal = generate_eod_signal(
        symbol="INFY",
        df=aug,
        market_regime=DTPRegimeState.BULLISH,
        bar_idx=75,
        signal_date=date(2018, 5, 10),
    )

    assert signal is not None
    assert signal.symbol == "INFY"
    assert signal.action == OrderAction.ENTER_LONG
    assert signal.initial_stop_price < signal.entry_trigger_price
    assert signal.r_distance > 0.0


def test_16_gap_up_rejection_over_1_5_pct():
    """Verify execution engine rejects entry if open gaps up > 1.5% above trigger."""
    signal = DTPEODSignal(
        symbol="RELIANCE",
        signal_date=date(2018, 5, 10),
        action=OrderAction.ENTER_LONG,
        entry_trigger_price=1000.0,
        initial_stop_price=970.0,
        r_distance=30.0,
        regime=DTPRegimeState.BULLISH,
    )

    # 1.6% gap up -> 1016.0
    action, fill_px, msg = evaluate_next_open_execution(signal, next_open_price=1016.0)
    assert action == OrderAction.REJECT_GAP_UP
    assert fill_px == 0.0
    assert "exceeds" in msg


def test_17_gap_down_rejection_below_stop():
    """Verify execution engine rejects entry if open gaps down below stop loss."""
    signal = DTPEODSignal(
        symbol="RELIANCE",
        signal_date=date(2018, 5, 10),
        action=OrderAction.ENTER_LONG,
        entry_trigger_price=1000.0,
        initial_stop_price=970.0,
        r_distance=30.0,
        regime=DTPRegimeState.BULLISH,
    )

    # Gap down to 965.0 (below stop 970.0)
    action, fill_px, msg = evaluate_next_open_execution(signal, next_open_price=965.0)
    assert action == OrderAction.REJECT_GAP_DOWN
    assert fill_px == 0.0
    assert "Gap-down below stop-loss" in msg


def test_18_normal_open_execution_with_friction():
    """Verify normal open fills with modeled slippage and half-spread (3.0 bps)."""
    signal = DTPEODSignal(
        symbol="ICICIBANK",
        signal_date=date(2018, 5, 10),
        action=OrderAction.ENTER_LONG,
        entry_trigger_price=1000.0,
        initial_stop_price=970.0,
        r_distance=30.0,
        regime=DTPRegimeState.BULLISH,
    )

    # Normal open at 1002.0 (+0.2% gap)
    action, fill_px, msg = evaluate_next_open_execution(signal, next_open_price=1002.0)
    assert action == OrderAction.ENTER_LONG
    # 3.0 bps = 0.0003 -> 1002.0 * 1.0003 = 1002.3006
    assert fill_px == pytest.approx(1002.0 * 1.0003, rel=1e-5)


# ---------------------------------------------------------------------------
# Suite 5: Exit Hierarchy & Trailing Progression (Tests 19-25)
# ---------------------------------------------------------------------------

def test_19_initial_stop_loss_hit():
    """Verify position is stopped out when session Low crosses initial stop."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,
        highest_high=1005.0,
        highest_close=1002.0,
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=995.0,
        current_low=968.0,  # crosses 970.0 stop
        current_close=972.0,
        current_open=985.0,
        current_atr=15.0,
        current_ema50=950.0,
        current_rsi=40.0,
        current_bb_upper=1050.0,
    )

    assert reason == DTPExitReason.INITIAL_STOP
    # Stop filled at 970 minus 3 bps friction
    assert exit_px == pytest.approx(970.0 * (1.0 - 0.0003), rel=1e-5)


def test_20_breakeven_stop_progression_at_1r():
    """Verify stop advances to breakeven (entry + 0.50% buffer) once price achieves +1.0R."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,  # 1R = 30.0 -> +1.0R = 1030.0
        highest_high=1000.0,
        highest_close=1000.0,
    )

    # Bar touches 1032.0 (+1.06R excursion)
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1032.0,
        current_low=998.0,
        current_close=1028.0,
        current_open=1005.0,
        current_atr=15.0,
        current_ema50=950.0,
        current_rsi=60.0,
        current_bb_upper=1060.0,
    )

    assert reason is None  # Held
    assert pos.is_breakeven_activated is True
    # Breakeven stop = 1000.0 * 1.005 = 1005.0
    assert pos.current_stop_price == pytest.approx(1005.0)


def test_21_chandelier_trailing_stop_progression_at_1_5r():
    """Verify Chandelier trailing stop activates after +1.5R and trails highest close."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1005.0,
        r_distance=30.0,  # +1.5R = 1045.0
        highest_high=1032.0,
        highest_close=1028.0,
        is_breakeven_activated=True,
    )

    # Bar achieves 1055.0 (+1.83R) with close at 1050.0 and ATR = 10.0
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1055.0,
        current_low=1025.0,
        current_close=1050.0,
        current_open=1030.0,
        current_atr=10.0,
        current_ema50=950.0,
        current_rsi=68.0,
        current_bb_upper=1070.0,
    )

    assert reason is None  # Held
    assert pos.is_trailing_activated is True
    # Chandelier stop = Highest Close (1050) - (1.5 * ATR 10.0) = 1050 - 15 = 1035.0
    assert pos.current_stop_price == pytest.approx(1035.0)


def test_22_trend_breakdown_exit_two_closes_below_ema50():
    """Verify position exits upon 2 consecutive closes below 50-day EMA."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=950.0,
        current_stop_price=950.0,
        r_distance=50.0,
        highest_high=1010.0,
        highest_close=1005.0,
        consecutive_closes_below_ema50=1,  # 1 close already recorded
    )

    # 2nd close below EMA50
    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=980.0,
        current_low=960.0,
        current_close=965.0,  # Close < EMA50 (970.0)
        current_open=978.0,
        current_atr=15.0,
        current_ema50=970.0,
        current_rsi=35.0,
        current_bb_upper=1030.0,
    )

    assert reason == DTPExitReason.TREND_BREAKDOWN
    assert "Trend breakdown" in msg


def test_23_max_holding_period_exit_at_10_sessions():
    """Verify position exits after 10 sessions if swing target/trailing stop not reached."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=970.0,
        r_distance=30.0,
        highest_high=1020.0,  # Excursion < 1.5R (45.0)
        highest_close=1015.0,
        holding_days=9,       # Reaches 10 on this evaluation
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1018.0,
        current_low=1002.0,
        current_close=1010.0,
        current_open=1008.0,
        current_atr=12.0,
        current_ema50=960.0,
        current_rsi=52.0,
        current_bb_upper=1040.0,
    )

    assert reason == DTPExitReason.TIME_LIMIT
    assert pos.holding_days == 10


def test_24_profit_target_exit_at_3r():
    """Verify position hits full +3.0R profit target."""
    pos = DTPPositionState(
        symbol="INFY",
        entry_date=date(2018, 5, 11),
        entry_price=1000.0,
        quantity=50,
        initial_stop_price=970.0,
        current_stop_price=1040.0,
        r_distance=30.0,  # +3.0R = 1090.0
        highest_high=1070.0,
        highest_close=1065.0,
    )

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1095.0,  # Crosses 1090.0 target
        current_low=1060.0,
        current_close=1085.0,
        current_open=1065.0,
        current_atr=12.0,
        current_ema50=960.0,
        current_rsi=72.0,
        current_bb_upper=1110.0,
    )

    assert reason == DTPExitReason.PROFIT_TARGET
    assert exit_px == pytest.approx(1090.0 * (1.0 - 0.0003), rel=1e-5)


def test_25_dynamic_overbought_exit_rsi_and_bb():
    """Verify dynamic blow-off profit taking when RSI >= 78 and High >= Upper Bollinger Band."""
    pos = DTPPositionState(
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

    reason, exit_px, msg = evaluate_exit_conditions(
        pos=pos,
        current_high=1082.0,  # >= Upper BB (1080.0)
        current_low=1050.0,
        current_close=1075.0,
        current_open=1052.0,
        current_atr=12.0,
        current_ema50=960.0,
        current_rsi=80.5,     # >= 78.0
        current_bb_upper=1080.0,
    )

    assert reason == DTPExitReason.DYNAMIC_OVERBOUGHT


# ---------------------------------------------------------------------------
# Suite 6: Position Sizing & Portfolio Risk Constraints (Tests 26-33)
# ---------------------------------------------------------------------------

def test_26_position_sizing_risk_constrained():
    """Verify position sizing is constrained by 1% portfolio equity risk."""
    equity = 100000.0
    cash = 100000.0
    entry_px = 100.0
    stop_px = 90.0  # Stop distance = ₹10.0
    # 1% risk = ₹1,000 / ₹10 = 100 shares
    # 100 shares * ₹100 = ₹10,000 (10% of equity < 33.3% cap)

    shares, msg = calculate_dtp_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_px,
        stop_price=stop_px,
    )

    assert shares == 100
    assert "Approved 100 shares" in msg


def test_27_position_sizing_capital_cap_constrained():
    """Verify position sizing is capped at 33.3% of portfolio equity."""
    equity = 100000.0
    cash = 100000.0
    entry_px = 100.0
    stop_px = 99.0  # Stop distance = ₹1.0 -> Risk allows 1,000 shares (₹1,00,000)
    # Capital cap = 33.3% = ₹33,300 / (100 * 1.005) = 331 shares

    shares, msg = calculate_dtp_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_px,
        stop_price=stop_px,
    )

    assert shares == 331
    assert "Cap=331" in msg


def test_28_position_sizing_cash_constrained():
    """Verify position sizing cannot exceed liquid unallocated cash."""
    equity = 100000.0
    cash = 15000.0  # Only ₹15,000 cash left
    entry_px = 100.0
    stop_px = 95.0  # Stop distance = ₹5.0 -> Risk allows 200 shares (₹20,000)
    # Cash allows: 15,000 / (100 * 1.005) = 149 shares

    shares, msg = calculate_dtp_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_px,
        stop_price=stop_px,
    )

    assert shares == 149
    assert "Cash=149" in msg


def test_29_position_sizing_sector_cap_constrained():
    """Verify position sizing respects 40% sector exposure ceiling."""
    equity = 100000.0
    cash = 50000.0
    entry_px = 100.0
    stop_px = 95.0
    # Sector currently has ₹34,000 invested. Max sector (40%) = ₹40,000.
    # Remaining sector budget = ₹6,000 -> 6000 / (100 * 1.005) = 59 shares
    # Notional = 59 * 100 = ₹5,900 >= ₹5,000 minimum floor

    shares, msg = calculate_dtp_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_px,
        stop_price=stop_px,
        sector="Information Technology",
        current_sector_exposure=34000.0,
    )

    assert shares == 59
    assert "Sector=59" in msg


def test_30_position_sizing_minimum_notional_floor():
    """Verify trades with notional value under ₹5,000 are rejected."""
    equity = 10000.0
    cash = 10000.0
    entry_px = 500.0
    stop_px = 475.0  # Stop dist = 25. Risk budget = 100 -> 4 shares = ₹2,000 < ₹5,000

    shares, msg = calculate_dtp_position_size(
        equity=equity,
        available_cash=cash,
        entry_price=entry_px,
        stop_price=stop_px,
    )

    assert shares == 0
    assert "below minimum efficiency floor" in msg


def test_31_portfolio_duplicate_position_prevention():
    """Verify portfolio tracker prevents duplicate positions in the same symbol (no pyramiding)."""
    tracker = DTPPortfolioTracker(initial_capital=100000.0)
    tracker.open_position(
        symbol="INFY",
        entry_price=1000.0,
        shares=30,
        stop_price=970.0,
        r_distance=30.0,
        entry_date=date(2018, 5, 10),
        order_id="BUY_1",
    )

    can_open, msg = tracker.can_open_position(
        symbol="INFY",
        entry_price=1010.0,
        proposed_shares=10,
    )

    assert can_open is False
    assert "pyramiding prohibited" in msg


def test_32_portfolio_max_concurrent_positions_limit():
    """Verify portfolio tracker caps simultaneous positions at 3."""
    tracker = DTPPortfolioTracker(initial_capital=100000.0)

    for i, sym in enumerate(["INFY", "RELIANCE", "ICICIBANK"], 1):
        tracker.open_position(
            symbol=sym,
            entry_price=500.0,
            shares=20,
            stop_price=480.0,
            r_distance=20.0,
            entry_date=date(2018, 5, 10),
            order_id=f"BUY_{i}",
        )

    # 4th position attempt must fail
    can_open, msg = tracker.can_open_position(
        symbol="TCS",
        entry_price=500.0,
        proposed_shares=20,
    )

    assert can_open is False
    assert "concurrent positions active" in msg


def test_33_portfolio_zero_margin_leverage_limit():
    """Verify total invested capital cannot exceed portfolio equity (zero leverage)."""
    tracker = DTPPortfolioTracker(initial_capital=30000.0)
    tracker.cash = 5000.0  # Cash depleted

    can_open, msg = tracker.can_open_position(
        symbol="INFY",
        entry_price=1000.0,
        proposed_shares=10,  # Requires ₹10,000 > ₹5,000 cash
    )

    assert can_open is False
    assert "Insufficient unallocated cash" in msg


# ---------------------------------------------------------------------------
# Suite 7: Delivery Cost Engine Integration (Tests 34-36)
# ---------------------------------------------------------------------------

def test_34_delivery_cost_integration_official_schedule():
    """Verify delivery cost integration uses official ₹307/cr schedule and exact itemization."""
    breakdown, summary = calculate_dtp_roundtrip_costs(
        symbol="INFY",
        isin="INE009A01021",
        entry_date=date(2026, 3, 2),
        exit_date=date(2026, 3, 10),
        entry_price=1000.0,
        exit_price=1100.0,
        quantity=50,
        use_stress_profile=False,
    )

    # Buy turnover = ₹50,000, Sell turnover = ₹55,000
    assert summary.buy_turnover == 50000.0
    assert summary.sell_turnover == 55000.0
    assert summary.gross_pnl == 5000.0
    assert summary.is_hypothetical_override is False

    # Check statutory taxes
    assert summary.total_stt == pytest.approx(105.0)  # 0.1% buy (50) + 0.1% sell (55)
    assert summary.total_stamp_duty == pytest.approx(7.50)  # 0.015% buy (7.50)
    assert summary.total_dp_charge == pytest.approx(20.00)  # Groww ₹16.50 + CDSL ₹3.50
    assert summary.net_pnl == summary.gross_pnl - summary.total_friction_costs


def test_35_delivery_cost_integration_stress_317_profile():
    """Verify stress test uses hypothetical ₹317/cr profile without double-counting IPFT."""
    breakdown, summary = calculate_dtp_roundtrip_costs(
        symbol="INFY",
        isin="INE009A01021",
        entry_date=date(2026, 3, 2),
        exit_date=date(2026, 3, 10),
        entry_price=1000.0,
        exit_price=1100.0,
        quantity=50,
        use_stress_profile=True,
    )

    assert summary.is_hypothetical_override is True
    # Under override, IPFT is 0.0
    assert summary.ipft_charge == 0.0
    assert "Broker override active" in str(summary.notes)


def test_36_delivery_cost_dp_charge_and_gst_attribution():
    """Verify DP charges apply only on sell leg and GST strictly excludes STT and stamp duty."""
    pending_buy = calculate_pending_entry_costs(
        symbol="INFY",
        isin="INE009A01021",
        entry_date=date(2026, 3, 2),
        entry_price=1000.0,
        quantity=50,
    )

    # Buy entry leg must have ZERO DP charges
    assert pending_buy.total_dp_base == Decimal("0.00")
    # Buy STT and Stamp Duty must be strictly excluded from taxable base
    assert pending_buy.taxable_services_base < pending_buy.total_turnover


# ---------------------------------------------------------------------------
# Suite 8: End-to-End Orchestration & Safety Handling (Tests 37-38)
# ---------------------------------------------------------------------------

def test_37_full_trade_lifecycle_orchestration():
    """Verify complete lifecycle: EOD signal -> T+1 Open entry -> Trailing stop -> Exit settlement."""
    strat = DTPV1Strategy(initial_capital=100000.0)

    # 1. Synthesize setup on INFY
    df = make_synthetic_ohlcv(n_bars=80, regime="uptrend")
    aug = calculate_dtp_indicators(df)
    ema20 = aug["ema_fast"].iloc[74]
    aug.iloc[74, aug.columns.get_loc("low")] = ema20 * 1.002
    aug.iloc[74, aug.columns.get_loc("close")] = ema20 * 1.004
    aug.iloc[74, aug.columns.get_loc("rsi")] = 45.0

    aug.iloc[75, aug.columns.get_loc("open")] = ema20 * 1.003
    aug.iloc[75, aug.columns.get_loc("close")] = ema20 * 1.018
    aug.iloc[75, aug.columns.get_loc("volume")] = aug["volume"].iloc[74] * 1.3

    # Generate EOD Signal
    sig = strat.evaluate_eod("INFY", aug, DTPRegimeState.BULLISH, bar_idx=75)
    assert sig is not None
    assert "INFY" in strat.pending_signals

    # Execute at next session open
    next_open = sig.entry_trigger_price * 1.002  # +0.2% gap
    action, pos, act_msg = strat.execute_next_open("INFY", next_open, date(2018, 5, 11))
    assert action == OrderAction.ENTER_LONG
    assert "INFY" in strat.portfolio.positions
    assert strat.portfolio.position_count == 1

    # Simulate exit session hitting profit target (Low above stop-loss)
    exit_bar = pd.Series(
        {
            "open": 1050.0,
            "high": pos.entry_price + (3.2 * pos.r_distance),  # hits 3.0R target
            "low": 1050.0,  # well above stop-loss
            "close": 1080.0,
            "atr": 12.0,
            "ema_slow": 950.0,
            "rsi": 65.0,
            "bb_upper": 1150.0,
        }
    )

    reason, summary, r_msg = strat.evaluate_position_exits("INFY", exit_bar, date(2018, 5, 15))
    assert reason == DTPExitReason.PROFIT_TARGET
    assert summary is not None
    assert summary.gross_pnl > 0.0
    assert summary.net_pnl > 0.0
    assert strat.portfolio.position_count == 0
    assert len(strat.closed_trades) == 1


def test_38_invalid_inputs_rejected_safely():
    """Verify invalid parameters fail safely with clear ValueError."""
    with pytest.raises(ValueError, match="Initial capital must be positive"):
        DTPPortfolioTracker(initial_capital=-500.0)

    with pytest.raises(ValueError, match="Quantity must be positive"):
        calculate_dtp_roundtrip_costs(
            symbol="INFY",
            isin="INE009A01021",
            entry_date=date(2018, 5, 10),
            exit_date=date(2018, 5, 15),
            entry_price=1000.0,
            exit_price=1100.0,
            quantity=0,
        )

    with pytest.raises(ValueError, match="Input DataFrame missing required OHLCV columns"):
        calculate_dtp_indicators(pd.DataFrame({"invalid": [1, 2, 3]}))

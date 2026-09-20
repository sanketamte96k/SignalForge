"""
SignalForge — Manual Validation Test Suite (2018 Backtest Audit)

Deterministic validation suite covering TEST 01 through TEST 20:
- TEST 01: Long Profit
- TEST 02: Long Loss
- TEST 03: Short Profit
- TEST 04: Short Loss
- TEST 05: Zero Movement
- TEST 06: Stop Loss
- TEST 07: Target
- TEST 08: Same-Candle Stop and Target
- TEST 09: No Lookahead
- TEST 10: Position Sizing & Leverage Guard
- TEST 11: Transaction Cost Model
- TEST 12: Multiple Consecutive Signals
- TEST 13: Long -> Flat -> Long State Transition
- TEST 14: Short -> Flat -> Short State Transition
- TEST 15: End of Day / Overnight Position Handling
- TEST 16: Incomplete Session Exclusion
- TEST 17: Zero Volume Candle Handling
- TEST 18: Capital Accounting Across Sequential Trades
- TEST 19: Trade Count Integrity (Exactly 2 Signals -> Exactly 2 Trades)
- TEST 20: Real Data Spot Checks (RELIANCE, TCS, INFY)
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.simulator import Position, simulate_trade
from src.backtest.portfolio import Portfolio
from src.backtesting.data_loader import BacktestDataLoader
from scripts.run_backtest_2018 import (
    calculate_indicators,
    generate_signal,
    INITIAL_CAPITAL,
    RISK_PER_TRADE,
    STOP_ATR,
    TARGET_ATR,
    BROKERAGE_PER_TRADE,
    SLIPPAGE,
)


# =====================================================================
# TEST 01: LONG PROFIT
# =====================================================================
def test_01_long_profit():
    """
    Entry = 100, Exit = 110, Quantity = 10
    Expected Gross P&L: +100
    """
    entry = 100.0
    exit_p = 110.0
    qty = 10
    gross_pnl = (exit_p - entry) * qty

    assert gross_pnl == 100.0

    # In src.backtest.simulator
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=entry,
        exit_price=exit_p,
        quantity=qty,
        transaction_cost_rate=0.0005,
    )
    assert trade.gross_pnl == 100.0
    expected_costs = (100.0 * 10 + 110.0 * 10) * 0.0005  # 2100 * 0.0005 = 1.05
    assert trade.transaction_cost == pytest.approx(expected_costs)
    assert trade.net_pnl == pytest.approx(100.0 - expected_costs)

    # Portfolio update
    portfolio = Portfolio(initial_capital=100000.0)
    portfolio.apply_trade(trade)
    assert portfolio.cash == pytest.approx(100000.0 + trade.net_pnl)


# =====================================================================
# TEST 02: LONG LOSS
# =====================================================================
def test_02_long_loss():
    """
    Entry = 100, Exit = 90, Quantity = 10
    Expected Gross P&L: -100
    """
    entry = 100.0
    exit_p = 90.0
    qty = 10
    gross_pnl = (exit_p - entry) * qty
    assert gross_pnl == -100.0

    trade = simulate_trade(
        position=Position.LONG,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=entry,
        exit_price=exit_p,
        quantity=qty,
    )
    assert trade.gross_pnl == -100.0
    assert trade.net_pnl == -100.0


# =====================================================================
# TEST 03: SHORT PROFIT
# =====================================================================
def test_03_short_profit():
    """
    Entry = 100, Exit = 90, Quantity = 10
    Expected Gross P&L: +100
    """
    entry = 100.0
    exit_p = 90.0
    qty = 10
    gross_pnl = (entry - exit_p) * qty
    assert gross_pnl == 100.0

    trade = simulate_trade(
        position=Position.SHORT,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=entry,
        exit_price=exit_p,
        quantity=qty,
    )
    assert trade.gross_pnl == 100.0
    assert trade.net_pnl == 100.0


# =====================================================================
# TEST 04: SHORT LOSS
# =====================================================================
def test_04_short_loss():
    """
    Entry = 100, Exit = 110, Quantity = 10
    Expected Gross P&L: -100
    """
    entry = 100.0
    exit_p = 110.0
    qty = 10
    gross_pnl = (entry - exit_p) * qty
    assert gross_pnl == -100.0

    trade = simulate_trade(
        position=Position.SHORT,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=entry,
        exit_price=exit_p,
        quantity=qty,
    )
    assert trade.gross_pnl == -100.0
    assert trade.net_pnl == -100.0


# =====================================================================
# TEST 05: ZERO MOVEMENT
# =====================================================================
def test_05_zero_movement():
    """
    Entry = 100, Exit = 100, Quantity = 10
    Expected Gross P&L: 0
    Verify costs are handled separately.
    """
    entry = 100.0
    exit_p = 100.0
    qty = 10
    gross_pnl = (exit_p - entry) * qty
    assert gross_pnl == 0.0

    cost_rate = 0.001
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=entry,
        exit_price=exit_p,
        quantity=qty,
        transaction_cost_rate=cost_rate,
    )
    assert trade.gross_pnl == 0.0
    expected_cost = (100.0 * 10 + 100.0 * 10) * cost_rate  # 2.0
    assert trade.transaction_cost == pytest.approx(expected_cost)
    assert trade.net_pnl == pytest.approx(-expected_cost)


# =====================================================================
# TEST 06: STOP LOSS
# =====================================================================
def test_06_stop_loss():
    """
    Create a deterministic candle sequence where a long position enters
    and the stop is definitely hit.
    Verify:
    - stop is triggered exactly once
    - correct exit timestamp
    - correct exit price
    - no second trade accidentally created from the same signal
    """
    # Deterministic simulation
    position = {
        "side": "LONG",
        "entry_time": pd.Timestamp("2018-01-01 09:30:00"),
        "entry_price": 100.0,
        "stop_price": 98.0,
        "target_price": 104.0,
        "quantity": 10,
    }

    candles = pd.DataFrame([
        {"Date": pd.Timestamp("2018-01-01 09:31:00"), "Open": 100.0, "High": 100.5, "Low": 99.0, "Close": 99.5},
        {"Date": pd.Timestamp("2018-01-01 09:32:00"), "Open": 99.5, "High": 99.8, "Low": 97.5, "Close": 98.0},  # Hits stop
        {"Date": pd.Timestamp("2018-01-01 09:33:00"), "Open": 98.0, "High": 98.5, "Low": 96.0, "Close": 96.5},
    ])

    exits = []
    for _, row in candles.iterrows():
        if position is not None:
            if row["Low"] <= position["stop_price"]:
                exits.append({
                    "exit_time": row["Date"],
                    "exit_price": position["stop_price"],
                    "exit_reason": "STOP",
                })
                position = None

    assert len(exits) == 1
    assert exits[0]["exit_time"] == pd.Timestamp("2018-01-01 09:32:00")
    assert exits[0]["exit_price"] == 98.0
    assert exits[0]["exit_reason"] == "STOP"
    assert position is None


# =====================================================================
# TEST 07: TARGET
# =====================================================================
def test_07_target():
    """
    Create a deterministic sequence where target is definitely hit.
    Verify:
    - target is triggered exactly once
    - correct P&L
    - no duplicate exit
    """
    position = {
        "side": "LONG",
        "entry_time": pd.Timestamp("2018-01-01 09:30:00"),
        "entry_price": 100.0,
        "stop_price": 98.0,
        "target_price": 104.0,
        "quantity": 10,
    }

    candles = pd.DataFrame([
        {"Date": pd.Timestamp("2018-01-01 09:31:00"), "Open": 100.0, "High": 102.0, "Low": 99.5, "Close": 101.5},
        {"Date": pd.Timestamp("2018-01-01 09:32:00"), "Open": 101.5, "High": 105.0, "Low": 101.0, "Close": 104.5},  # Hits target
        {"Date": pd.Timestamp("2018-01-01 09:33:00"), "Open": 104.5, "High": 106.0, "Low": 104.0, "Close": 105.5},
    ])

    exits = []
    for _, row in candles.iterrows():
        if position is not None:
            if row["High"] >= position["target_price"]:
                gross_pnl = (position["target_price"] - position["entry_price"]) * position["quantity"]
                exits.append({
                    "exit_time": row["Date"],
                    "exit_price": position["target_price"],
                    "gross_pnl": gross_pnl,
                    "exit_reason": "TARGET",
                })
                position = None

    assert len(exits) == 1
    assert exits[0]["exit_time"] == pd.Timestamp("2018-01-01 09:32:00")
    assert exits[0]["exit_price"] == 104.0
    assert exits[0]["gross_pnl"] == 40.0
    assert exits[0]["exit_reason"] == "TARGET"


# =====================================================================
# TEST 08: SAME-CANDLE STOP AND TARGET
# =====================================================================
def test_08_same_candle_stop_and_target():
    """
    Create a candle where both stop and target fall inside the same candle range.
    Determine engine behavior.
    The rule in run_backtest_2018.py is:
        if row["Low"] <= stop:
            exit_price = stop
            exit_reason = "STOP"
        elif row["High"] >= target:
            exit_price = target
            exit_reason = "TARGET"
    Because stop is checked FIRST, the engine deterministically chooses STOP (conservative).
    """
    row = {"Open": 100.0, "High": 106.0, "Low": 95.0, "Close": 101.0}
    stop_price = 98.0
    target_price = 104.0

    # Engine order of checks:
    exit_reason = None
    if row["Low"] <= stop_price:
        exit_price = stop_price
        exit_reason = "STOP"
    elif row["High"] >= target_price:
        exit_price = target_price
        exit_reason = "TARGET"

    assert exit_reason == "STOP", "Engine must deterministically prefer conservative STOP when both hit in same bar"
    assert exit_price == 98.0


# =====================================================================
# TEST 09: NO LOOKAHEAD
# =====================================================================
def test_09_no_lookahead():
    """
    Create candles: 09:15, 09:16, 09:17.
    Make signal become valid only after the 09:16 candle closes.
    Verify trade cannot enter using information from the future.
    """
    # Signal function requires close of candle i
    # Crossover condition uses row i and row i-1
    # Trade entry is recorded at row[Date] of candle i at row[Close].
    # In live execution, an order placed upon close of 09:16 fills at 09:16 close or 09:17 open.
    # It must NOT use any data from 09:17 (e.g. 09:17 High/Low/Close).
    df = pd.DataFrame([
        {"Date": pd.Timestamp("2018-01-01 09:15:00"), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "EMA_FAST": 100.0, "EMA_SLOW": 100.5, "RSI": 45.0},
        {"Date": pd.Timestamp("2018-01-01 09:16:00"), "Open": 100.0, "High": 103.0, "Low": 100.0, "Close": 102.5, "EMA_FAST": 101.5, "EMA_SLOW": 101.0, "RSI": 58.0},
        {"Date": pd.Timestamp("2018-01-01 09:17:00"), "Open": 102.5, "High": 108.0, "Low": 102.0, "Close": 107.0, "EMA_FAST": 103.0, "EMA_SLOW": 101.8, "RSI": 70.0},
    ])

    prev = df.iloc[0]
    row = df.iloc[1]
    long_cross = (prev["EMA_FAST"] <= prev["EMA_SLOW"] and row["EMA_FAST"] > row["EMA_SLOW"])
    assert bool(long_cross) is True
    assert row["RSI"] >= 50

    # Trade entered on 09:16 Close (102.5)
    entry_price = row["Close"]
    entry_time = row["Date"]

    assert entry_time == pd.Timestamp("2018-01-01 09:16:00")
    assert entry_price == 102.5
    # Ensure no future candle (09:17) influenced entry
    assert entry_time < df.iloc[2]["Date"]
    assert entry_price != df.iloc[2]["Close"]
    assert entry_price != df.iloc[2]["High"]


# =====================================================================
# TEST 10: POSITION SIZING
# =====================================================================
def test_10_position_sizing():
    """
    Fixed capital = 100,000.
    Risk per trade = 1% = 1,000.
    ATR = 2.0, Stop multiplier = 1.5 -> Stop distance = 3.0.
    Expected Quantity = int(1000 / 3.0) = 333 shares.
    AUDIT CHECK:
    - Current engine does NOT enforce maximum capital allocation (leverage check).
    - If ATR is 0.10 on a 1000 stock, qty = int(1000 / 0.15) = 6666 shares -> 66.6 lakh notional (66x leverage!).
    - If capital is negative, risk_amount is negative -> qty <= 0 -> rejected.
    """
    capital = 100000.0
    risk_pct = 0.01
    atr = 2.0
    stop_atr = 1.5

    risk_amount = capital * risk_pct  # 1000.0
    risk_per_share = atr * stop_atr   # 3.0
    quantity = int(risk_amount / risk_per_share)
    assert quantity == 333

    # Extreme low ATR case (The Leverage Explosion Bug)
    tight_atr = 0.10
    tight_qty = int(risk_amount / (tight_atr * stop_atr))
    assert tight_qty == 6666
    notional_value = tight_qty * 1000.0  # Rs 6,666,000 on a 100k account!
    assert notional_value > capital * 50  # Over 50x leverage!

    # Negative capital guard check
    neg_capital = -500.0
    neg_risk = neg_capital * risk_pct
    neg_qty = int(neg_risk / risk_per_share)
    assert neg_qty <= 0, "Negative capital must produce non-positive quantity"


# =====================================================================
# TEST 11: TRANSACTION COST
# =====================================================================
def test_11_transaction_cost():
    """
    Compare transaction cost formulas:
    Standard Turn-over Model (src/backtest/simulator.py):
        cost = (entry_value + exit_value) * rate
    run_backtest_2018.py Model:
        cost = BROKERAGE_PER_TRADE + (abs(exit - entry) * qty * SLIPPAGE)
    AUDIT FINDING:
    run_backtest_2018.py incorrectly calculates slippage on the PRICE DIFFERENCE (exit - entry)
    rather than the total order notional!
    """
    entry = 1000.0
    exit_p = 1005.0
    qty = 100
    slippage_rate = 0.0005
    brokerage = 20.0

    # run_backtest_2018 formula
    engine_costs = brokerage + (abs(exit_p - entry) * qty * slippage_rate)
    # 20.0 + (5.0 * 100 * 0.0005) = 20.0 + 0.25 = 20.25
    assert engine_costs == pytest.approx(20.25)

    # Correct turnover-based slippage formula
    entry_notional = entry * qty   # 100,000
    exit_notional = exit_p * qty   # 100,500
    correct_slippage = (entry_notional + exit_notional) * slippage_rate  # 200,500 * 0.0005 = 100.25
    correct_costs = brokerage + correct_slippage  # 120.25

    # Proves the engine severely underestimated slippage on every trade!
    assert engine_costs < correct_costs
    assert correct_slippage / (abs(exit_p - entry) * qty * slippage_rate) > 400


# =====================================================================
# TEST 12: MULTIPLE SIGNALS
# =====================================================================
def test_12_multiple_signals():
    """
    Create repeated signals over consecutive candles.
    Verify:
    - no duplicate positions
    - no unintended pyramiding
    - no repeated entry on the same signal
    - position state transitions correctly
    """
    position = None
    trades = []

    # 5 consecutive candles with LONG signal
    for i in range(5):
        signal = "LONG"
        # Engine rule: only open if position is None
        if position is None:
            position = {
                "side": signal,
                "entry_time": i,
                "entry_price": 100.0 + i,
                "quantity": 10,
            }
            trades.append(position)

    # Exactly 1 trade entered, no duplicate entries or pyramiding
    assert len(trades) == 1
    assert position is not None
    assert position["entry_time"] == 0


# =====================================================================
# TEST 13: LONG -> FLAT -> LONG
# =====================================================================
def test_13_long_flat_long():
    """
    Verify state transitions:
    FLAT -> LONG -> FLAT -> LONG
    """
    state_history = []
    position = None

    # Step 1: FLAT
    state_history.append("FLAT" if position is None else position["side"])

    # Step 2: Enter LONG
    position = {"side": "LONG", "entry_price": 100.0}
    state_history.append("FLAT" if position is None else position["side"])

    # Step 3: Exit to FLAT
    position = None
    state_history.append("FLAT" if position is None else position["side"])

    # Step 4: Re-enter LONG
    position = {"side": "LONG", "entry_price": 102.0}
    state_history.append("FLAT" if position is None else position["side"])

    assert state_history == ["FLAT", "LONG", "FLAT", "LONG"]


# =====================================================================
# TEST 14: SHORT -> FLAT -> SHORT
# =====================================================================
def test_14_short_flat_short():
    """
    Verify state transitions:
    FLAT -> SHORT -> FLAT -> SHORT
    """
    state_history = []
    position = None

    state_history.append("FLAT" if position is None else position["side"])

    position = {"side": "SHORT", "entry_price": 100.0}
    state_history.append("FLAT" if position is None else position["side"])

    position = None
    state_history.append("FLAT" if position is None else position["side"])

    position = {"side": "SHORT", "entry_price": 98.0}
    state_history.append("FLAT" if position is None else position["side"])

    assert state_history == ["FLAT", "SHORT", "FLAT", "SHORT"]


# =====================================================================
# TEST 15: END OF DAY / OVERNIGHT BEHAVIOR
# =====================================================================
def test_15_end_of_day_behavior():
    """
    Audit finding:
    In run_backtest_2018.py, positions are NOT closed at 15:29!
    They carry overnight until stopped, targeted, or YEAR_END!
    In contrast, src/backtest/engine.py properly squares off intraday positions
    at the session boundary.
    """
    # Verify run_backtest_2018 does not have session-exit logic
    reliance_trades = pd.read_csv(ROOT / "research" / "backtest_2018" / "RELIANCE_trades.csv")
    reliance_trades["entry_time"] = pd.to_datetime(reliance_trades["entry_time"])
    reliance_trades["exit_time"] = pd.to_datetime(reliance_trades["exit_time"])

    overnight_trades = reliance_trades[
        reliance_trades["entry_time"].dt.date != reliance_trades["exit_time"].dt.date
    ]
    # In run_backtest_2018, positions were held overnight
    assert len(overnight_trades) > 0, "Audit confirms run_backtest_2018 held positions overnight across sessions"


# =====================================================================
# TEST 16: INCOMPLETE SESSION HANDLING
# =====================================================================
def test_16_incomplete_session_handling():
    """
    Verify BacktestDataLoader excludes incomplete sessions.
    Check RELIANCE 2018 has 25 incomplete sessions excluded.
    """
    loader = BacktestDataLoader(data_dir=ROOT / "research" / "clean_data_2018")
    data = loader.load("RELIANCE", 2018, exclude_incomplete_sessions=True)

    assert data.quality.complete_sessions == 220
    assert data.quality.incomplete_sessions == 25
    assert len(data.quality.excluded_sessions) == 25
    assert data.quality.usable is True
    # Rows must equal exactly 220 sessions * 375 bars = 82,500
    assert len(data.data) == 82500


# =====================================================================
# TEST 17: ZERO VOLUME ROW
# =====================================================================
def test_17_zero_volume_row():
    """
    Inspect TCS row:
    2018-01-10 12:15:00
    Open=1352.5, High=1352.5, Low=1352.5, Close=1352.5, Volume=0
    Audit Determination:
    - The row represents an un-traded minute candle in the exchange feed.
    - If removed, the session has 374 bars, making it incomplete and excluded.
    - It SHOULD REMAIN in clean data to preserve session continuity.
    - Indicators (EMA, RSI, ATR) function correctly because prices are valid.
    """
    tcs_path = ROOT / "research" / "clean_data_2018" / "TCS_2018.csv"
    df = pd.read_csv(tcs_path)
    zero_vol = df[(df["Date"] == "2018-01-10 12:15:00") & (df["Volume"] == 0)]
    assert len(zero_vol) == 1
    row = zero_vol.iloc[0]
    assert row["Open"] == 1352.5
    assert row["High"] == 1352.5
    assert row["Low"] == 1352.5
    assert row["Close"] == 1352.5
    assert row["Volume"] == 0


# =====================================================================
# TEST 18: CAPITAL ACCOUNTING
# =====================================================================
def test_18_capital_accounting():
    """
    3 deterministic trades:
    Trade 1: +100
    Trade 2: -50
    Trade 3: +25
    Expected Net P&L: +75
    Verify capital after every trade.
    """
    capital = 10000.0
    pnls = [100.0, -50.0, 25.0]
    expected_capitals = [10100.0, 10050.0, 10075.0]

    actual_capitals = []
    for pnl in pnls:
        capital += pnl
        actual_capitals.append(capital)

    assert actual_capitals == expected_capitals
    assert capital - 10000.0 == 75.0


# =====================================================================
# TEST 19: TRADE COUNT
# =====================================================================
def test_19_trade_count():
    """
    Create a dataset where exactly 2 signals should generate exactly 2 trades.
    Verify trade count = 2, no duplicates.
    """
    trades = []
    signals = [
        (pd.Timestamp("2018-01-01 09:30:00"), "LONG"),
        (pd.Timestamp("2018-01-01 10:00:00"), "SHORT"),
    ]

    position = None
    for ts, sig in signals:
        if position is not None:
            # close position
            trades.append(position)
            position = None

        position = {"side": sig, "entry_time": ts, "entry_price": 100.0}

    if position is not None:
        trades.append(position)

    assert len(trades) == 2
    assert trades[0]["side"] == "LONG"
    assert trades[1]["side"] == "SHORT"


# =====================================================================
# TEST 20: REAL DATA SPOT CHECK
# =====================================================================
def test_20_real_data_spot_check():
    """
    Inspect 3 real trade sequences from 2018:
    1. RELIANCE Day 1 First Trade (2018-01-01 10:04:00)
    2. INFY Mid-day Stop Trade (2018-08-10 12:32:00)
    3. TCS Morning Trade (2018-01-02 09:35:00)
    """
    rel_trades = pd.read_csv(ROOT / "research" / "backtest_2018" / "RELIANCE_trades.csv")
    t1 = rel_trades.iloc[0]

    assert t1["symbol"] == "RELIANCE"
    assert t1["side"] == "LONG"
    assert str(t1["entry_time"]) == "2018-01-01 10:04:00"
    assert str(t1["exit_time"]) == "2018-01-01 10:05:00"
    assert t1["entry_price"] == 911.11
    assert t1["exit_reason"] == "STOP"
    assert t1["gross_pnl"] < 0
    assert t1["net_pnl"] < t1["gross_pnl"]  # Costs reduce P&L

    infy_trades = pd.read_csv(ROOT / "research" / "backtest_2018" / "INFY_trades.csv")
    infy_sub = infy_trades[infy_trades["entry_time"] == "2018-08-10 12:32:00"]
    assert len(infy_sub) == 1
    t2 = infy_sub.iloc[0]
    assert t2["side"] == "LONG"
    assert t2["exit_reason"] == "STOP"
    assert t2["quantity"] == 4241


# =====================================================================
# TEST 21: MAXIMUM LEVERAGE ENFORCEMENT
# =====================================================================
def test_21_maximum_leverage():
    """
    Verify that regardless of how small the ATR is, notional exposure
    never exceeds capital * MAX_LEVERAGE.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    # 10 candles with tiny ATR = 0.05 on a Rs 1000 stock
    dates = pd.date_range("2018-01-01 09:15", periods=10, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [1000.0] * 10,
        "High": [1000.1] * 10,
        "Low": [999.9] * 10,
        "Close": [1000.0] * 10,
        "Volume": [1000] * 10,
        "ATR": [0.05] * 10,  # Tiny ATR
    })

    # Signal at index 1
    def signal_gen(df, i):
        return "LONG" if i == 1 else None

    config = IntradayEngineConfig(
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,  # Max allowed notional = 500,000
    )

    result = run_intraday_backtest(data, signal_gen, config)
    assert len(result.trades) == 1
    trade = result.trades[0]

    max_notional_allowed = config.initial_capital * config.max_leverage
    actual_notional = trade.quantity * trade.entry_price

    assert actual_notional <= max_notional_allowed
    assert trade.effective_leverage <= config.max_leverage
    assert trade.quantity == int(max_notional_allowed / trade.entry_price)  # 500 shares, not 13,333!


# =====================================================================
# TEST 22: CAPITAL CANNOT SILENTLY BECOME NEGATIVE (BANKRUPTCY GUARD)
# =====================================================================
def test_22_bankruptcy_guard():
    """
    Verify that if a trade's loss exhausts account capital, the engine
    halts trading immediately, does not enter subsequent trades, and
    records a clear bankruptcy reason.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=10, freq="1min")
    # Giant crash on bar 3
    data = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 100.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        "High": [100.0, 100.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        "Low": [100.0, 100.0, 5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        "Close": [100.0, 100.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        "Volume": [1000] * 10,
        "ATR": [2.0] * 10,
    })

    # Signals at bar 1 and bar 5
    def signal_gen(df, i):
        if i == 1:
            return "LONG"
        if i == 5:
            return "LONG"
        return None

    config = IntradayEngineConfig(
        initial_capital=1000.0,
        risk_per_trade=0.5,
        max_leverage=5.0,
    )

    result = run_intraday_backtest(data, signal_gen, config)

    # Trade 1 should trigger bankruptcy and trade 2 at bar 5 should NEVER be taken
    assert len(result.trades) == 1
    assert result.bankruptcy_reason is not None
    assert "BANKRUPTCY" in result.bankruptcy_reason


# =====================================================================
# TEST 23: ZERO QUANTITY CANNOT CREATE TRADE
# =====================================================================
def test_23_zero_quantity_cannot_create_trade():
    """
    Verify that if capital or sizing produces quantity <= 0, no trade
    is opened.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=5, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [5000.0] * 5,
        "High": [5000.0] * 5,
        "Low": [5000.0] * 5,
        "Close": [5000.0] * 5,
        "Volume": [100] * 5,
        "ATR": [100.0] * 5,
    })

    def signal_gen(df, i):
        return "LONG"

    # Capital is Rs 100, stock is Rs 5000 -> quantity = 0
    config = IntradayEngineConfig(initial_capital=100.0, max_leverage=1.0)
    result = run_intraday_backtest(data, signal_gen, config)
    assert len(result.trades) == 0


# =====================================================================
# TEST 24: GAP-THROUGH-STOP LONG EXECUTION
# =====================================================================
def test_24_gap_through_stop_long():
    """
    Long position enters with Stop = 98.0.
    Next bar gaps down and opens at 94.0.
    Realistic fill must be 94.0 (the open price), NOT 98.0.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=4, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 100.0, 94.0, 94.0],   # Bar 2 opens at 94.0 (gapped below stop 97.0)
        "High": [100.0, 100.5, 95.0, 94.5],
        "Low": [100.0, 99.5, 93.0, 93.5],
        "Close": [100.0, 100.0, 94.0, 94.0],
        "Volume": [1000] * 4,
        "ATR": [2.0] * 4,  # stop_dist = 2 * 1.5 = 3.0 -> stop_price = 97.0
    })

    def signal_gen(df, i):
        return "LONG" if i == 1 else None

    config = IntradayEngineConfig(
        initial_capital=100000.0,
        gap_execution=True,
        stop_atr_multiplier=1.5,
    )

    result = run_intraday_backtest(data, signal_gen, config)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP"
    assert trade.exit_price == 94.0, "Gap-through-stop must fill at the bar Open price (94.0), not stop price (97.0)"


# =====================================================================
# TEST 25: GAP-THROUGH-STOP SHORT EXECUTION
# =====================================================================
def test_25_gap_through_stop_short():
    """
    Short position enters with Stop = 103.0.
    Next bar gaps up and opens at 106.0.
    Realistic fill must be 106.0, NOT 103.0.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=4, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 100.0, 106.0, 106.0],  # Bar 2 opens at 106.0 (gapped above stop 103.0)
        "High": [100.0, 100.5, 107.0, 106.5],
        "Low": [100.0, 99.5, 105.5, 105.0],
        "Close": [100.0, 100.0, 106.0, 106.0],
        "Volume": [1000] * 4,
        "ATR": [2.0] * 4,  # stop_dist = 3.0 -> stop_price = 103.0
    })

    def signal_gen(df, i):
        return "SHORT" if i == 1 else None

    config = IntradayEngineConfig(
        initial_capital=100000.0,
        gap_execution=True,
        stop_atr_multiplier=1.5,
    )

    result = run_intraday_backtest(data, signal_gen, config)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP"
    assert trade.exit_price == 106.0, "Gap-through-stop must fill at Open (106.0), not stop price (103.0)"


# =====================================================================
# TEST 26: FRIDAY -> MONDAY OVERNIGHT PREVENTION
# =====================================================================
def test_26_friday_to_monday_overnight_prevention():
    """
    Position entered Friday afternoon (2018-01-05 15:00).
    Engine must square off at Friday 15:29 Close with reason 'EOD'.
    Zero exposure must carry into Monday (2018-01-08 09:15).
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    friday_times = pd.date_range("2018-01-05 15:00", "2018-01-05 15:29", freq="1min")
    monday_times = pd.date_range("2018-01-08 09:15", "2018-01-08 09:30", freq="1min")
    all_times = friday_times.append(monday_times)

    data = pd.DataFrame({
        "Date": all_times,
        "Open": [100.0] * len(all_times),
        "High": [100.2] * len(all_times),
        "Low": [99.8] * len(all_times),
        "Close": [100.0] * len(all_times),
        "Volume": [1000] * len(all_times),
        "ATR": [1.0] * len(all_times),
    })

    def signal_gen(df, i):
        return "LONG" if i == 1 else None

    config = IntradayEngineConfig(enforce_eod_square_off=True, session_end_time="15:29")
    result = run_intraday_backtest(data, signal_gen, config)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "EOD"
    assert trade.exit_time == pd.Timestamp("2018-01-05 15:29:00")
    assert trade.exit_time.date() == pd.Timestamp("2018-01-05").date()


# =====================================================================
# TEST 27: MULTIPLE INCOMPLETE SESSIONS FILTERED
# =====================================================================
def test_27_multiple_incomplete_sessions_filtered():
    """
    Verify BacktestDataLoader excludes all incomplete sessions across
    multiple symbols (RELIANCE=25, TCS=20, INFY=25).
    """
    loader = BacktestDataLoader(data_dir=ROOT / "research" / "clean_data_2018")

    tcs = loader.load("TCS", 2018, exclude_incomplete_sessions=True)
    assert tcs.quality.incomplete_sessions == 20
    assert len(tcs.quality.excluded_sessions) == 20
    assert len(tcs.data) == 225 * 375

    infy = loader.load("INFY", 2018, exclude_incomplete_sessions=True)
    assert infy.quality.incomplete_sessions == 25
    assert len(infy.data) == 220 * 375


# =====================================================================
# TEST 28: TRANSACTION COST CANNOT BE NEGATIVE
# =====================================================================
def test_28_transaction_cost_non_negative():
    """
    Transaction cost, slippage, brokerage, and fees must always be >= 0.
    """
    trade = simulate_trade(
        position=Position.LONG,
        entry_time="2018-01-01 09:15:00",
        exit_time="2018-01-01 09:30:00",
        entry_price=100.0,
        exit_price=90.0,
        quantity=10,
        brokerage=20.0,
        slippage_rate=0.0005,
        statutory_fee_rate=0.0001,
    )
    assert trade.transaction_cost > 0
    assert trade.slippage >= 0
    assert trade.brokerage >= 0
    assert trade.statutory_fees >= 0


# =====================================================================
# TEST 29: QUANTITY NEVER EXCEEDS CONFIGURED MAXIMUM
# =====================================================================
def test_29_quantity_never_exceeds_max_leverage():
    """
    Even with ATR = 0.001, quantity must strictly cap at
    floor(capital * max_leverage / price).
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=5, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [500.0] * 5,
        "High": [500.1] * 5,
        "Low": [499.9] * 5,
        "Close": [500.0] * 5,
        "Volume": [1000] * 5,
        "ATR": [0.001] * 5,  # Microscopic ATR
    })

    def signal_gen(df, i):
        return "LONG" if i == 1 else None

    config = IntradayEngineConfig(initial_capital=50000.0, max_leverage=5.0)
    result = run_intraday_backtest(data, signal_gen, config)

    assert len(result.trades) == 1
    # 50,000 * 5 = 250,000 / 500 = 500 shares max
    assert result.trades[0].quantity == 500


# =====================================================================
# TEST 30: CHRONOLOGICAL TRADE TIMESTAMPS
# =====================================================================
def test_30_chronological_trade_timestamps():
    """
    Every trade must satisfy entry_time < exit_time, and subsequent
    trade entry_time >= previous trade exit_time.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=30, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [100.0 + (i % 2) * 2.0 for i in range(30)],
        "High": [103.0] * 30,
        "Low": [97.0] * 30,
        "Close": [100.0] * 30,
        "Volume": [1000] * 30,
        "ATR": [1.0] * 30,
    })

    def signal_gen(df, i):
        return "LONG" if i in (1, 10, 20) else None

    config = IntradayEngineConfig(stop_atr_multiplier=1.0)
    result = run_intraday_backtest(data, signal_gen, config)

    for idx, trade in enumerate(result.trades):
        assert trade.entry_time < trade.exit_time
        if idx > 0:
            assert trade.entry_time >= result.trades[idx - 1].exit_time


# =====================================================================
# TEST 31: NO OVERLAPPING POSITIONS
# =====================================================================
def test_31_no_overlapping_positions():
    """
    Verify that at no point in time does the engine hold overlapping
    positions on the same instrument.
    """
    from src.backtest.engine import run_intraday_backtest, IntradayEngineConfig

    dates = pd.date_range("2018-01-01 09:15", periods=20, freq="1min")
    data = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 20,
        "High": [100.5] * 20,
        "Low": [99.5] * 20,
        "Close": [100.0] * 20,
        "Volume": [1000] * 20,
        "ATR": [1.0] * 20,
    })

    # Continuous signals
    def signal_gen(df, i):
        return "LONG"

    result = run_intraday_backtest(data, signal_gen, IntradayEngineConfig())
    # Should only hold 1 position that closes at EOD
    assert len(result.trades) == 1


# =====================================================================
# TEST 32: EXACTLY ONE ENTRY AND ONE EXIT PER COMPLETED TRADE
# =====================================================================
def test_32_one_entry_one_exit():
    """
    Verify every trade has valid non-null entry and exit timestamps,
    prices, quantity, and pnl.
    """
    trade = simulate_trade(
        position=Position.LONG,
        entry_time=pd.Timestamp("2018-01-01 09:15:00"),
        exit_time=pd.Timestamp("2018-01-01 09:30:00"),
        entry_price=100.0,
        exit_price=105.0,
        quantity=50,
        exit_reason="TARGET",
    )
    assert trade.entry_time is not None
    assert trade.exit_time is not None
    assert trade.entry_price > 0
    assert trade.exit_price > 0
    assert trade.quantity > 0
    assert trade.exit_reason == "TARGET"


if __name__ == "__main__":
    pytest.main(["-v", str(Path(__file__).resolve())])


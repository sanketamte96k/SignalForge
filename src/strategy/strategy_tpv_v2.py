"""
SignalForge — Phase 32B: Strategy TPV-V2 (Trend-Pullback Value Engine)
======================================================================
File: src/strategy/strategy_tpv_v2.py

Strategy Specification:
- Execution Timeframe: 5-minute candles.
- Macro Direction: Completed 15-minute and 30-minute EMA20/EMA50 trend alignment.
  * LONG: 15m EMA20 > EMA50 AND 30m EMA20 > EMA50.
  * SHORT: 15m EMA20 < EMA50 AND 30m EMA20 < EMA50.
  * Causal Synchronicity: HTF indicators only use completed HTF candles and are causally
    merged via merge_asof(direction='backward').
- Pullback to Value Zone:
  * In bullish trend, 5m price pulls back into the dynamic value zone between 5m EMA20 and EMA50.
  * Low must reach or pierce EMA20 (low <= EMA20) while remaining above EMA50 - 0.5 * ATR.
  * In bearish trend, High must reach or pierce EMA20 (high >= EMA20) while remaining below EMA50 + 0.5 * ATR.
- Momentum Oscillator Reset:
  * LONG: 5m RSI(14) resets into neutral cooldown zone (40.0 <= RSI <= 56.0).
  * SHORT: 5m RSI(14) resets into neutral cooldown zone (44.0 <= RSI <= 60.0).
- Trend Confirmation & Reversal Trigger:
  * 5m candle closes back in the direction of the macro trend (close > open for LONG, close < open for SHORT).
  * Close above EMA20 for LONG (Close below EMA20 for SHORT).
- Anti-Chasing Proximity Gate:
  * Entry signal candle close must be within 0.5 * ATR of 5m EMA20.
- ADX Confirmation:
  * 5m ADX(14) >= 15.0 (confirms directional momentum, avoids dead consolidation).
- Time-of-Day Filter:
  * No entries before 09:35 IST (09:15-09:35 opening blackout).
  * No entries after 14:45 IST.
  * Mandatory EOD Square-Off at 15:15 IST.
- Daily Session Limit: Maximum 1 trade per symbol per trading session.
- Exits:
  * Initial Stop-Loss: 1.2 * ATR below pullback swing low (for LONG) or above pullback swing high (for SHORT).
  * Target: 3.0 * ATR from entry price.
  * Trailing Logic: Activated once price achieves +2.0 * ATR favorable excursion.
  * Intrabar Collision Priority: Stop First if both stop and target touched in the same bar.
- Risk & Sizing:
  * 1% portfolio equity risk per trade, capped at 5x leverage.
  * Cost-aware sizing via calculate_cost_aware_position_size.
  * Canonical Indian transaction costs (DISCOUNT_BROKER_REALISTIC / CONSERVATIVE_STRESS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from src.backtest.capital_allocator import calculate_cost_aware_position_size
from src.backtest.indian_market_costs import (
    IntradayCostConfig,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    CONSERVATIVE_STRESS_CONFIG,
    calculate_trade_transaction_costs,
)
from src.backtest.simulator import Position, Trade, simulate_trade
from src.data.resampler import resample_ohlcv

IST_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class TPVV2Config:
    """Configuration parameters for TPV-V2 (Trend-Pullback Value Engine)."""
    name: str = "TPV-V2"
    description: str = "5m Pullback to Value with dual 15m/30m causal EMA trend alignment"
    ema20_period: int = 20
    ema50_period: int = 50
    atr_period: int = 14
    rsi_period: int = 14
    adx_period: int = 14
    min_adx: float = 15.0
    rsi_long_min: float = 40.0
    rsi_long_max: float = 56.0
    rsi_short_min: float = 44.0
    rsi_short_max: float = 60.0
    proximity_atr_mult: float = 0.5
    initial_stop_atr_mult: float = 1.2
    target_atr_mult: float = 3.0
    trailing_activation_atr: float = 2.0
    trailing_offset_atr: float = 1.5
    trailing_guarantee_atr: float = 0.5
    risk_per_trade_pct: float = 0.01
    max_leverage: float = 5.0
    opening_blackout_end: str = "09:35"
    last_entry_time: str = "14:45"
    eod_square_off_time: str = "15:15"
    max_trades_per_session: int = 1


DEFAULT_TPV_V2_CONFIG = TPVV2Config()


def calc_wilder_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Welles Wilder's Average True Range with causal smoothing."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate causal Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate causal Welles Wilder ADX."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    plus_dm = high - prev_high
    minus_dm = prev_low - low

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_plus_dm = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()
    smooth_minus_dm = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * (smooth_plus_dm / atr.replace(0, np.nan))
    minus_di = 100.0 * (smooth_minus_dm / atr.replace(0, np.nan))

    di_diff = (plus_di - minus_di).abs()
    di_sum = plus_di + minus_di
    dx = 100.0 * (di_diff / di_sum.replace(0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx.fillna(0.0)


def compute_tpv_v2_indicators(
    df_1m: pd.DataFrame,
    config: Optional[TPVV2Config] = None,
) -> dict[str, Any]:
    """
    Computes all causal 5m, 15m, and 30m indicators for TPV-V2.
    
    Guarantees:
    - 5m, 15m, 30m candles formed strictly from completed 1-minute bars.
    - 15m indicators available strictly at index + 15m.
    - 30m indicators available strictly at index + 30m.
    - Causal asof backward merging onto 5m completion times.
    """
    if config is None:
        config = DEFAULT_TPV_V2_CONFIG

    df_raw = df_1m.copy()
    df_raw.columns = [c.lower() for c in df_raw.columns]
    if "timestamp" in df_raw.columns:
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
        df_raw.set_index("timestamp", inplace=True)
    df_raw.sort_index(inplace=True)

    # 1. Resample to 5m, 15m, 30m
    df_5m = resample_ohlcv(df_raw, "5m").copy()
    df_15m = resample_ohlcv(df_raw, "15m").copy()
    df_30m = resample_ohlcv(df_raw, "30m").copy()

    # 2. 5m Indicators
    df_5m["ema20"] = df_5m["close"].ewm(span=config.ema20_period, adjust=False).mean()
    df_5m["ema50"] = df_5m["close"].ewm(span=config.ema50_period, adjust=False).mean()
    df_5m["atr"] = calc_wilder_atr(df_5m, config.atr_period)
    df_5m["rsi"] = calc_rsi(df_5m["close"], config.rsi_period)
    df_5m["adx"] = calc_adx(df_5m, config.adx_period)

    # 3. 15m Indicators
    df_15m["ema20_15m"] = df_15m["close"].ewm(span=config.ema20_period, adjust=False).mean()
    df_15m["ema50_15m"] = df_15m["close"].ewm(span=config.ema50_period, adjust=False).mean()
    df_15m["trend_15m"] = np.where(df_15m["ema20_15m"] > df_15m["ema50_15m"], 1, np.where(df_15m["ema20_15m"] < df_15m["ema50_15m"], -1, 0))
    df_15m["available_at_15m"] = df_15m.index + pd.Timedelta(minutes=15)

    # 4. 30m Indicators
    df_30m["ema20_30m"] = df_30m["close"].ewm(span=config.ema20_period, adjust=False).mean()
    df_30m["ema50_30m"] = df_30m["close"].ewm(span=config.ema50_period, adjust=False).mean()
    df_30m["trend_30m"] = np.where(df_30m["ema20_30m"] > df_30m["ema50_30m"], 1, np.where(df_30m["ema20_30m"] < df_30m["ema50_30m"], -1, 0))
    df_30m["available_at_30m"] = df_30m.index + pd.Timedelta(minutes=30)

    # 5. Causal merge onto 5m completion times (index + 5m)
    df_5m["completed_at"] = df_5m.index + pd.Timedelta(minutes=5)

    merged_15 = pd.merge_asof(
        df_5m.sort_values("completed_at"),
        df_15m[["available_at_15m", "trend_15m"]].sort_values("available_at_15m"),
        left_on="completed_at",
        right_on="available_at_15m",
        direction="backward",
    )
    merged_15.index = df_5m.index
    df_5m["trend_15m"] = merged_15["trend_15m"].fillna(0)

    merged_30 = pd.merge_asof(
        df_5m.sort_values("completed_at"),
        df_30m[["available_at_30m", "trend_30m"]].sort_values("available_at_30m"),
        left_on="completed_at",
        right_on="available_at_30m",
        direction="backward",
    )
    merged_30.index = df_5m.index
    df_5m["trend_30m"] = merged_30["trend_30m"].fillna(0)

    df_5m["macro_bull"] = (df_5m["trend_15m"] == 1) & (df_5m["trend_30m"] == 1)
    df_5m["macro_bear"] = (df_5m["trend_15m"] == -1) & (df_5m["trend_30m"] == -1)

    return {
        "df_5m": df_5m,
        "df_15m": df_15m,
        "df_30m": df_30m,
        "df_1m": df_raw,
    }


@dataclass
class TPVV2BacktestResult:
    """Detailed results from TPV-V2 simulation."""
    symbol: str
    strategy_name: str
    trades: list[Trade]
    initial_capital: float
    ending_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_pnl: float
    total_costs: float
    brokerage_costs: float
    statutory_costs: float
    slippage_and_spread_costs: float
    net_pnl: float
    gross_profit_factor: float
    net_profit_factor: float
    net_expectancy: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    max_drawdown_inr: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    total_turnover: float
    turnover_ratio: float
    avg_holding_duration_mins: float
    bootstrap_ci_95: tuple[float, float]
    trades_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def run_tpv_v2_backtest(
    df_1m: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100000.0,
    cost_config: Optional[IntradayCostConfig] = None,
    config: Optional[TPVV2Config] = None,
) -> TPVV2BacktestResult:
    """
    Executes a strict, zero-lookahead backtest for TPV-V2 (Trend-Pullback Value Engine).
    
    Execution semantics:
    - Signal generated at close of 5m bar T.
    - Order executes at Open of 5m bar T+1 (next_open fill).
    - Stop-loss and Target evaluated intrabar on subsequent bars.
    - If stop and target both touched in the same bar, Stop-Loss triggers first.
    - Trailing logic updates stop causally once +2 ATR excursion is reached.
    - Mandatory square-off at 15:15 IST.
    - Sizing: 1% risk per trade, 5x leverage cap, cost-aware.
    """
    if config is None:
        config = DEFAULT_TPV_V2_CONFIG
    if cost_config is None:
        cost_config = DISCOUNT_BROKER_REALISTIC_CONFIG

    features = compute_tpv_v2_indicators(df_1m, config)
    df_5m = features["df_5m"]

    capital = float(initial_capital)
    trades: list[Trade] = []

    # Parse blackout and cutoffs
    bh_h, bh_m = [int(x) for x in config.opening_blackout_end.split(":")]
    blackout_end = dtime(bh_h, bh_m)
    le_h, le_m = [int(x) for x in config.last_entry_time.split(":")]
    last_entry = dtime(le_h, le_m)
    eod_h, eod_m = [int(x) for x in config.eod_square_off_time.split(":")]
    eod_square_off = dtime(eod_h, eod_m)

    # Active position tracking
    active_position: Optional[Position] = None
    entry_price = 0.0
    entry_time: Optional[pd.Timestamp] = None
    quantity = 0
    current_stop = 0.0
    current_target = 0.0
    atr_at_entry = 0.0
    trailing_activated = False
    highest_since_entry = 0.0
    lowest_since_entry = 0.0
    capital_before_entry = 0.0

    # Session tracking for 1-trade-per-session limit
    session_trades_count = 0
    current_session_date = None

    n_bars = len(df_5m)
    timestamps = df_5m.index

    for i in range(n_bars):
        cur_ts = timestamps[i]
        cur_date = cur_ts.date()
        cur_time = cur_ts.time()

        # New session reset
        if cur_date != current_session_date:
            current_session_date = cur_date
            session_trades_count = 0

        bar = df_5m.iloc[i]
        b_open = float(bar["open"])
        b_high = float(bar["high"])
        b_low = float(bar["low"])
        b_close = float(bar["close"])

        # -------------------------------------------------------------
        # 1. Manage Active Position
        # -------------------------------------------------------------
        if active_position is not None:
            exit_triggered = False
            exit_price = 0.0
            exit_reason = ""

            # Check EOD Square-Off
            if cur_time >= eod_square_off:
                exit_triggered = True
                exit_price = b_open
                exit_reason = "EOD_SQUARE_OFF"
            else:
                if active_position == Position.LONG:
                    highest_since_entry = max(highest_since_entry, b_high)
                    hit_stop = b_low <= current_stop
                    hit_target = b_high >= current_target

                    if hit_stop and hit_target:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_triggered = True
                        exit_price = current_target
                        exit_reason = "TARGET"
                    else:
                        # Trailing Update
                        if not trailing_activated and (b_high >= entry_price + (config.trailing_activation_atr * atr_at_entry)):
                            trailing_activated = True
                        if trailing_activated:
                            trail_stop = highest_since_entry - (config.trailing_offset_atr * atr_at_entry)
                            guarantee_stop = entry_price + (config.trailing_guarantee_atr * atr_at_entry)
                            current_stop = max(current_stop, guarantee_stop, trail_stop)

                elif active_position == Position.SHORT:
                    lowest_since_entry = min(lowest_since_entry, b_low)
                    hit_stop = b_high >= current_stop
                    hit_target = b_low <= current_target

                    if hit_stop and hit_target:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_triggered = True
                        exit_price = current_target
                        exit_reason = "TARGET"
                    else:
                        # Trailing Update
                        if not trailing_activated and (b_low <= entry_price - (config.trailing_activation_atr * atr_at_entry)):
                            trailing_activated = True
                        if trailing_activated:
                            trail_stop = lowest_since_entry + (config.trailing_offset_atr * atr_at_entry)
                            guarantee_stop = entry_price - (config.trailing_guarantee_atr * atr_at_entry)
                            current_stop = min(current_stop, guarantee_stop, trail_stop)

            if exit_triggered:
                trade = simulate_trade(
                    position=active_position,
                    entry_time=entry_time,
                    exit_time=cur_ts,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    cost_config=cost_config,
                    symbol=symbol,
                    exit_reason=exit_reason,
                    capital_before=capital_before_entry,
                    capital_after=capital + (exit_price - entry_price if active_position == Position.LONG else entry_price - exit_price) * quantity,
                    atr=atr_at_entry,
                    stop_distance=abs(entry_price - current_stop),
                )
                trades.append(trade)
                capital += trade.net_pnl

                active_position = None
                entry_price = 0.0
                entry_time = None
                quantity = 0
                current_stop = 0.0
                current_target = 0.0
                atr_at_entry = 0.0
                trailing_activated = False

        # -------------------------------------------------------------
        # 2. Evaluate Signals at Candle Close (if no active position)
        # -------------------------------------------------------------
        if active_position is None and session_trades_count < config.max_trades_per_session:
            # Check timing filters
            if cur_time < blackout_end or cur_time > last_entry:
                continue

            atr = bar["atr"]
            if pd.isna(atr) or atr <= 0.0:
                continue
            ema20 = bar["ema20"]
            ema50 = bar["ema50"]
            if pd.isna(ema20) or pd.isna(ema50):
                continue
            adx = bar["adx"]
            if pd.isna(adx) or adx < config.min_adx:
                continue
            rsi = bar["rsi"]
            if pd.isna(rsi):
                continue

            macro_bull = bool(bar["macro_bull"])
            macro_bear = bool(bar["macro_bear"])

            sig_side: Optional[PositionSide] = None
            swing_ref = 0.0

            # LONG Pullback to Value Conditions:
            # 1. Macro trend aligned bullish on 15m and 30m
            # 2. Candle pulled back to touch/pierce EMA20 (low <= ema20) but held above ema50 - 0.5 * atr
            # 3. RSI reset in healthy neutral pullback zone [40, 56]
            # 4. Bullish reversal candle: close > open and close >= ema20 * 0.999
            # 5. Proximity gate: close <= ema20 + 0.5 * atr (prevents chasing)
            if macro_bull:
                pulled_back = (b_low <= ema20) and (b_low >= ema50 - (0.5 * atr))
                rsi_reset = config.rsi_long_min <= rsi <= config.rsi_long_max
                bullish_reversal = (b_close > b_open) and (b_close >= ema20 * 0.999)
                not_chasing = b_close <= (ema20 + (config.proximity_atr_mult * atr))

                if pulled_back and rsi_reset and bullish_reversal and not_chasing:
                    sig_side = Position.LONG
                    swing_ref = b_low

            # SHORT Pullback to Value Conditions:
            # 1. Macro trend aligned bearish on 15m and 30m
            # 2. Candle pulled back up to touch/pierce EMA20 (high >= ema20) but held below ema50 + 0.5 * atr
            # 3. RSI reset in healthy neutral pullback zone [44, 60]
            # 4. Bearish reversal candle: close < open and close <= ema20 * 1.001
            # 5. Proximity gate: close >= ema20 - 0.5 * atr (prevents chasing)
            elif macro_bear:
                pulled_back = (b_high >= ema20) and (b_high <= ema50 + (0.5 * atr))
                rsi_reset = config.rsi_short_min <= rsi <= config.rsi_short_max
                bearish_reversal = (b_close < b_open) and (b_close <= ema20 * 1.001)
                not_chasing = b_close >= (ema20 - (config.proximity_atr_mult * atr))

                if pulled_back and rsi_reset and bearish_reversal and not_chasing:
                    sig_side = Position.SHORT
                    swing_ref = b_high

            # If signal fired, fill at Next Bar Open (i+1)
            if sig_side is not None and (i + 1 < n_bars):
                next_bar = df_5m.iloc[i + 1]
                next_ts = timestamps[i + 1]

                if next_ts.date() == cur_date and next_ts.time() < eod_square_off:
                    fill_price = float(next_bar["open"])

                    # Planned stop 1.2 ATR below/above pullback swing
                    if sig_side == Position.LONG:
                        planned_stop = min(swing_ref, fill_price - (0.5 * atr)) - (config.initial_stop_atr_mult * atr)
                    else:
                        planned_stop = max(swing_ref, fill_price + (0.5 * atr)) + (config.initial_stop_atr_mult * atr)

                    # Calculate cost-aware size
                    qty, _, _ = calculate_cost_aware_position_size(
                        entry_price=fill_price,
                        stop_loss=planned_stop,
                        capital=capital,
                        risk_per_trade_pct=config.risk_per_trade_pct,
                        max_leverage=config.max_leverage,
                        side=sig_side,
                        cost_config=cost_config,
                        include_costs_in_sizing=True,
                    )

                    if qty > 0:
                        active_position = sig_side
                        entry_price = fill_price
                        entry_time = next_ts
                        quantity = qty
                        atr_at_entry = atr
                        current_stop = planned_stop
                        current_target = fill_price + (config.target_atr_mult * atr) if sig_side == Position.LONG else fill_price - (config.target_atr_mult * atr)
                        highest_since_entry = fill_price
                        lowest_since_entry = fill_price
                        trailing_activated = False
                        capital_before_entry = capital
                        session_trades_count += 1

    # -------------------------------------------------------------
    # 3. Post-Backtest Metrics Aggregation
    # -------------------------------------------------------------
    return _aggregate_backtest_results(
        symbol=symbol,
        strategy_name=config.name,
        initial_capital=initial_capital,
        ending_capital=capital,
        trades=trades,
    )


def _aggregate_backtest_results(
    symbol: str,
    strategy_name: str,
    initial_capital: float,
    ending_capital: float,
    trades: list[Trade],
) -> TPVV2BacktestResult:
    """Computes all required performance, cost, and statistical metrics."""
    total_trades = len(trades)
    if total_trades == 0:
        return TPVV2BacktestResult(
            symbol=symbol,
            strategy_name=strategy_name,
            trades=[],
            initial_capital=initial_capital,
            ending_capital=initial_capital,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            gross_pnl=0.0,
            total_costs=0.0,
            brokerage_costs=0.0,
            statutory_costs=0.0,
            slippage_and_spread_costs=0.0,
            net_pnl=0.0,
            gross_profit_factor=0.0,
            net_profit_factor=0.0,
            net_expectancy=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            payoff_ratio=0.0,
            max_drawdown_inr=0.0,
            max_drawdown_pct=0.0,
            max_consecutive_losses=0,
            total_turnover=0.0,
            turnover_ratio=0.0,
            avg_holding_duration_mins=0.0,
            bootstrap_ci_95=(0.0, 0.0),
            trades_df=pd.DataFrame(),
        )

    records = []
    wins = 0
    losses = 0
    gross_wins = 0.0
    gross_losses = 0.0
    net_wins = 0.0
    net_losses = 0.0
    total_brokerage = 0.0
    total_statutory = 0.0
    total_slippage_spread = 0.0
    total_turnover = 0.0
    durations = []

    for t in trades:
        records.append({
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "position": t.position.value,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "gross_pnl": t.gross_pnl,
            "transaction_cost": t.transaction_cost,
            "brokerage": t.brokerage,
            "statutory_fees": t.statutory_fees,
            "slippage_and_spread": t.slippage,
            "net_pnl": t.net_pnl,
            "exit_reason": t.exit_reason,
            "turnover": (t.entry_price + t.exit_price) * t.quantity,
            "holding_mins": (pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 60.0,
        })

        if t.net_pnl > 0:
            wins += 1
            net_wins += t.net_pnl
        else:
            losses += 1
            net_losses += abs(t.net_pnl)

        if t.gross_pnl > 0:
            gross_wins += t.gross_pnl
        else:
            gross_losses += abs(t.gross_pnl)

        total_brokerage += t.brokerage
        total_statutory += t.statutory_fees
        total_slippage_spread += t.slippage
        total_turnover += (t.entry_price + t.exit_price) * t.quantity
        durations.append((pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 60.0)

    trades_df = pd.DataFrame(records)

    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)

    win_rate_pct = (wins / total_trades) * 100.0
    gross_pf = (gross_wins / gross_losses) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)
    net_pf = (net_wins / net_losses) if net_losses > 0 else (99.0 if net_wins > 0 else 0.0)
    net_expectancy = net_pnl / total_trades

    avg_win = (net_wins / wins) if wins > 0 else 0.0
    avg_loss = (net_losses / losses) if losses > 0 else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    # Drawdown calculation
    equity_curve = [initial_capital]
    peak = initial_capital
    max_dd_inr = 0.0
    max_dd_pct = 0.0

    consecutive_losses = 0
    max_consecutive_losses = 0

    for t in trades:
        equity_curve.append(equity_curve[-1] + t.net_pnl)
        eq = equity_curve[-1]
        if eq > peak:
            peak = eq
        dd = peak - eq
        dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0
        if dd > max_dd_inr:
            max_dd_inr = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        if t.net_pnl <= 0:
            consecutive_losses += 1
            if consecutive_losses > max_consecutive_losses:
                max_consecutive_losses = consecutive_losses
        else:
            consecutive_losses = 0

    turnover_ratio = total_turnover / initial_capital
    avg_duration = float(np.mean(durations)) if durations else 0.0

    # Bootstrap 95% Confidence Interval for Net Expectancy (1,000 resamples)
    net_pnls = np.array([t.net_pnl for t in trades])
    np.random.seed(42)
    boot_means = []
    for _ in range(1000):
        resample = np.random.choice(net_pnls, size=total_trades, replace=True)
        boot_means.append(float(np.mean(resample)))
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    return TPVV2BacktestResult(
        symbol=symbol,
        strategy_name=strategy_name,
        trades=trades,
        initial_capital=initial_capital,
        ending_capital=ending_capital,
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        win_rate_pct=round(win_rate_pct, 2),
        gross_pnl=round(gross_pnl, 2),
        total_costs=round(total_costs, 2),
        brokerage_costs=round(total_brokerage, 2),
        statutory_costs=round(total_statutory, 2),
        slippage_and_spread_costs=round(total_slippage_spread, 2),
        net_pnl=round(net_pnl, 2),
        gross_profit_factor=round(gross_pf, 2),
        net_profit_factor=round(net_pf, 2),
        net_expectancy=round(net_expectancy, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        payoff_ratio=round(payoff_ratio, 2),
        max_drawdown_inr=round(max_dd_inr, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_consecutive_losses=max_consecutive_losses,
        total_turnover=round(total_turnover, 2),
        turnover_ratio=round(turnover_ratio, 2),
        avg_holding_duration_mins=round(avg_duration, 1),
        bootstrap_ci_95=(round(ci_lower, 2), round(ci_upper, 2)),
        trades_df=trades_df,
    )

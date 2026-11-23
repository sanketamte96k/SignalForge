"""
SignalForge — Phase 32I: DTP-V3 Signal Generation & Exit Engine
=================================================================
File: src/strategy/dtp_v3/signal_engine.py

Implements deterministic EOD signal evaluation, next-session open execution,
and adaptive exit conditions for DTP-V3 delivery swing trading:
  - Macro trend alignment with 14-period Choppiness Index filter (CI <= 60.0).
  - Upper-half reversal candle confirmation ((Close - Low) / (High - Low) >= 0.50).
  - Causal next-open execution with gap-risk filtering (+1.5% max gap-up, stop-violation gap-down).
  - 2.0x ATR Chandelier trailing stop anchored to Highest High (HH - 2.0 * ATR) at +1.5R excursion.
  - Non-ratcheting stop logic: stop price never moves downward for a long position.
  - Preserved +3.0R profit target.
  - Preserved 10-session maximum holding rule with excursion bypass (positions reaching >= 1.5R bypass session 10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)


@dataclass
class DTPEODSignal:
    """EOD Signal generated at Bar T close for execution at Bar T+1 open."""
    symbol: str
    signal_date: date
    action: OrderAction
    entry_trigger_price: float       # Close price of Bar T
    initial_stop_price: float        # Structural or ATR-based stop
    r_distance: float                # Initial risk distance (Entry - Stop)
    regime: DTPRegimeState
    notes: List[str] = field(default_factory=list)


@dataclass
class DTPPositionState:
    """Internal state tracking an active delivery position across sessions."""
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    initial_stop_price: float
    current_stop_price: float
    r_distance: float
    highest_high: float
    highest_close: float
    holding_days: int = 0
    is_breakeven_activated: bool = False
    is_trailing_activated: bool = False
    consecutive_closes_below_ema50: int = 0


def is_trend_aligned(
    df: pd.DataFrame,
    idx: int,
    config: DTPV3Config,
) -> Tuple[bool, str]:
    """
    Evaluates individual stock macro trend alignment at Bar T:
      1. Close > 200 SMA (or 50 EMA if insufficient history)
      2. 20 EMA > 50 EMA (fast moving average above slow moving average)
      3. 50 EMA sloping upwards over previous 5 sessions
      4. 14-period ADX >= 20.0 (active directional trend)
      5. Relative strength >= 0.0 versus benchmark
      6. Choppiness Index <= 60.0 (market is not in choppy/sideways stagnation)
    """
    row = df.iloc[idx]
    c = row["close"]
    ema20 = row["ema_fast"]
    ema50 = row["ema_slow"]
    adx = row["adx"]

    # 1. 200-day SMA or 50-day EMA trend alignment
    if "sma_trend" in row and pd.notna(row["sma_trend"]):
        sma200 = row["sma_trend"]
        if c < sma200:
            return False, f"Close ({c:.2f}) below 200 SMA ({sma200:.2f})"
    else:
        if c < ema50:
            return False, f"Close ({c:.2f}) below 50 EMA ({ema50:.2f})"

    # 2. Moving average alignment
    if ema20 <= ema50:
        return False, f"20 EMA ({ema20:.2f}) not above 50 EMA ({ema50:.2f})"

    # 3. 50 EMA slope over past 5 bars
    slope_lookback = max(0, idx - 5)
    past_ema50 = df["ema_slow"].iloc[slope_lookback]
    if ema50 <= past_ema50:
        return False, f"50 EMA not sloping upward ({ema50:.2f} <= {past_ema50:.2f})"

    # 4. ADX trend strength
    if adx < config.adx_min_threshold:
        return False, f"ADX ({adx:.1f}) below threshold ({config.adx_min_threshold:.1f})"

    # 5. Relative strength
    if "relative_strength" in row and pd.notna(row["relative_strength"]):
        rs = row["relative_strength"]
        if rs < 0.0:
            return False, f"Relative strength negative ({rs:.3f})"

    # 6. Choppiness Index Filter
    if config.use_chop_filter and "chop_index" in row and pd.notna(row["chop_index"]):
        chop = row["chop_index"]
        if chop > config.max_chop_index:
            return False, f"Choppiness Index ({chop:.1f}) exceeds ceiling ({config.max_chop_index:.1f})"

    return True, "Trend aligned"


def is_pullback_active(
    df: pd.DataFrame,
    idx: int,
    config: DTPV3Config,
) -> Tuple[bool, str]:
    """
    Evaluates orderly pullback into key value zone during the pullback window:
      1. 14-period RSI between 38.0 and 52.0
      2. Low approached within 1.0% of 20-day EMA
      3. Retracement does not exceed 61.8% of prior 20-day swing
      4. Volume contracted (<= 1.10 * 20-day volume SMA) during pullback
    """
    row = df.iloc[idx]
    c = row["close"]
    l = row["low"]
    rsi = row["rsi"]
    ema20 = row["ema_fast"]
    vol = row["volume"]
    vol_sma = row["volume_sma"]

    # RSI condition
    if rsi < config.rsi_pullback_min or rsi > config.rsi_pullback_max:
        return False, f"RSI ({rsi:.1f}) outside pullback band [{config.rsi_pullback_min}, {config.rsi_pullback_max}]"

    # EMA20 proximity: Low must be within 1.0% above or below 20 EMA
    ema_distance = abs(l - ema20) / ema20
    if ema_distance > config.ema20_proximity_pct and l > ema20:
        return False, f"Low ({l:.2f}) not within {config.ema20_proximity_pct:.1%} of 20 EMA ({ema20:.2f})"

    # Retracement depth vs 20-day swing
    if "swing_high_20" in row and "swing_low_20" in row:
        sh = row["swing_high_20"]
        sl = row["swing_low_20"]
        if pd.notna(sh) and pd.notna(sl) and sh > sl:
            total_swing = sh - sl
            retrace = (sh - l) / total_swing
            if retrace > config.max_retracement_depth:
                return False, f"Retracement depth ({retrace:.1%}) exceeds {config.max_retracement_depth:.1%}"

    # Volume contraction
    if pd.notna(vol_sma) and vol_sma > 0:
        if vol > vol_sma * config.volume_contraction_ratio:
            return False, f"Volume ({vol:,.0f}) exceeded contraction threshold ({vol_sma * config.volume_contraction_ratio:,.0f})"

    return True, "Pullback active"


def check_reversal_trigger(
    df: pd.DataFrame,
    idx: int,
    config: DTPV3Config,
) -> Tuple[bool, str]:
    """
    Evaluates bullish reversal candle at Bar T:
      1. Bullish candle structure: Close > Open, OR hammer pattern.
      2. Upper-half close confirmation: (Close - Low) / (High - Low) >= 0.50.
      3. Close reclaims 20 EMA: Close >= 20 EMA.
      4. Expanding volume: Volume >= 0.90 * volume SMA or Volume > prior volume.
      5. Active pullback condition occurred within previous 3 sessions.
    """
    # Verify pullback occurred within window
    window_start = max(0, idx - config.pullback_window_days)
    pullback_found = False
    for i in range(window_start, idx + 1):
        pb_ok, _ = is_pullback_active(df, i, config)
        if pb_ok:
            pullback_found = True
            break

    if not pullback_found:
        return False, f"No active pullback identified in prior {config.pullback_window_days} days"

    row = df.iloc[idx]
    prev_row = df.iloc[idx - 1] if idx > 0 else row

    o = row["open"]
    h = row["high"]
    l = row["low"]
    c = row["close"]
    vol = row["volume"]
    prev_vol = prev_row["volume"]
    vol_sma = row["volume_sma"]
    ema20 = row["ema_fast"]

    candle_range = h - l
    body = abs(c - o)
    lower_wick = min(o, c) - l

    is_bullish_close = c > o
    is_hammer = (lower_wick >= 2.0 * body) and (candle_range > 0) if body > 0 else False

    if not (is_bullish_close or is_hammer):
        return False, "Reversal bar is neither bullish close nor hammer"

    # Upper-half close confirmation (Phase 32I innovation)
    if config.require_upper_half_close and candle_range > 0:
        close_range_ratio = (c - l) / candle_range
        if close_range_ratio < config.min_close_range_ratio:
            return False, f"Close ({c:.2f}) not in upper {config.min_close_range_ratio:.0%} of range ({close_range_ratio:.1%})"

    # Reclaim 20 EMA
    if c < ema20:
        return False, f"Close ({c:.2f}) failed to reclaim 20 EMA ({ema20:.2f})"

    # Volume expansion
    vol_ok = False
    if pd.notna(vol_sma) and vol_sma > 0:
        prev_vol_sma = df["volume_sma"].iloc[idx - 1]
        if vol >= prev_vol_sma * config.volume_expansion_ratio:
            vol_ok = True
    if vol > prev_vol:
        vol_ok = True

    if not vol_ok:
        return False, "Reversal bar lacked expanding volume confirmation"

    return True, "Bullish reversal confirmed"


def generate_eod_signal(
    symbol: str,
    df: pd.DataFrame,
    market_regime: DTPRegimeState,
    config: Optional[DTPV3Config] = None,
    bar_idx: int = -1,
    signal_date: Optional[date] = None,
) -> Optional[DTPEODSignal]:
    """Generates a causal EOD signal at Bar T close for execution at Bar T+1 open."""
    if config is None:
        config = DTPV3Config()

    # Bearish market regime halts all new entry signals
    if market_regime == DTPRegimeState.BEARISH or market_regime == DTPRegimeState.UNKNOWN:
        return None

    n_rows = len(df)
    target_idx = bar_idx if bar_idx >= 0 else n_rows + bar_idx
    if target_idx < max(config.ema_slow_period, config.pullback_window_days + 1):
        return None

    # 1. Macro Trend Filter (includes Choppiness filter)
    trend_ok, trend_msg = is_trend_aligned(df, target_idx, config)
    if not trend_ok:
        return None

    # 2. Pullback & Reversal Trigger (includes Upper-half close confirmation)
    reversal_ok, rev_msg = check_reversal_trigger(df, target_idx, config)
    if not reversal_ok:
        return None

    # 3. Calculate Stop-Loss and Risk
    c = float(df["close"].iloc[target_idx])
    atr = float(df["atr"].iloc[target_idx])

    # Find lowest low during the 3-day pullback window
    window_start = max(0, target_idx - config.pullback_window_days)
    lowest_pullback_low = float(df["low"].iloc[window_start : target_idx + 1].min())

    atr_stop = c - (config.initial_stop_atr_mult * atr)
    initial_stop = min(lowest_pullback_low, atr_stop)

    # Enforce maximum stop distance cap (3.0 * ATR)
    max_stop_distance = config.max_stop_atr_mult * atr
    if (c - initial_stop) > max_stop_distance:
        initial_stop = c - max_stop_distance

    r_distance = c - initial_stop
    if r_distance <= 0.0:
        return None

    if signal_date is None:
        if isinstance(df.index, pd.DatetimeIndex):
            signal_date = df.index[target_idx].date()
        else:
            signal_date = date.today()

    return DTPEODSignal(
        symbol=symbol,
        signal_date=signal_date,
        action=OrderAction.ENTER_LONG,
        entry_trigger_price=c,
        initial_stop_price=initial_stop,
        r_distance=r_distance,
        regime=market_regime,
        notes=[trend_msg, rev_msg],
    )


def evaluate_next_open_execution(
    signal: DTPEODSignal,
    next_open_price: float,
    config: Optional[DTPV3Config] = None,
) -> Tuple[OrderAction, float, str]:
    """Evaluates execution of an EOD signal at next session open."""
    if config is None:
        config = DTPV3Config()

    trigger = signal.entry_trigger_price
    max_open = trigger * (1.0 + config.max_gap_up_pct)

    if next_open_price > max_open:
        gap_pct = (next_open_price - trigger) / trigger
        return (
            OrderAction.REJECT_GAP_UP,
            0.0,
            f"Gap-up {gap_pct:.2%} exceeds {config.max_gap_up_pct:.1%} ceiling (Open={next_open_price:.2f}, Max={max_open:.2f})",
        )

    if next_open_price <= signal.initial_stop_price:
        return (
            OrderAction.REJECT_GAP_DOWN,
            0.0,
            f"Gap-down below stop-loss (Open={next_open_price:.2f} <= Stop={signal.initial_stop_price:.2f})",
        )

    friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
    fill_price = next_open_price * (1.0 + friction_rate)
    return OrderAction.ENTER_LONG, fill_price, "Normal open execution with friction"


def evaluate_exit_conditions(
    pos: DTPPositionState,
    current_high: float,
    current_low: float,
    current_close: float,
    current_open: float,
    current_atr: float,
    current_ema50: float,
    current_rsi: float,
    current_bb_upper: float,
    config: Optional[DTPV3Config] = None,
) -> Tuple[Optional[DTPExitReason], float, str]:
    """
    Evaluates deterministic exit hierarchy for an active delivery position:
      1. Stop-Loss: Low <= current_stop_price -> exit immediately at min(Open, current_stop)
      2. Trailing Stop updates: Breakeven (+1.0R) and Chandelier trailing (HH - 2.0*ATR at +1.5R)
      3. Profit Target: High >= Entry + 3.0R -> exit
      4. Dynamic Overbought: RSI >= 78.0 and High >= BB_Upper -> exit
      5. Trend Breakdown: 2 consecutive closes < EMA50 -> exit
      6. Time-based: holding_days >= 10 and excursion_r < 1.5 -> exit
    """
    if config is None:
        config = DTPV3Config()

    pos.holding_days += 1
    friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0

    if current_high > pos.highest_high:
        pos.highest_high = current_high
    if current_close > pos.highest_close:
        pos.highest_close = current_close

    # 1. Stop-Loss Trigger (Highest Priority)
    if current_low <= pos.current_stop_price:
        raw_exit = min(current_open, pos.current_stop_price)
        exit_price = raw_exit * (1.0 - friction_rate)

        if pos.is_trailing_activated:
            reason = DTPExitReason.TRAILING_STOP
        elif pos.is_breakeven_activated:
            reason = DTPExitReason.BREAKEVEN_STOP
        else:
            reason = DTPExitReason.INITIAL_STOP
        return reason, exit_price, f"Stop-loss executed (Low={current_low:.2f} <= Stop={pos.current_stop_price:.2f})"

    # 2. Advance Trailing / Breakeven Stops
    excursion_r = (pos.highest_high - pos.entry_price) / pos.r_distance

    # Breakeven advancement (+1.0R)
    if excursion_r >= config.breakeven_r_mult and not pos.is_breakeven_activated:
        pos.is_breakeven_activated = True
        be_stop = pos.entry_price * (1.0 + config.breakeven_cost_buffer_pct)
        pos.current_stop_price = max(pos.current_stop_price, be_stop)

    # Chandelier Trailing advancement (+1.5R): Anchored to Highest High (HH - 2.0 * ATR)
    if excursion_r >= config.trailing_r_mult:
        pos.is_trailing_activated = True
        chandelier_stop = pos.highest_high - (config.trailing_atr_mult * current_atr)
        pos.current_stop_price = max(pos.current_stop_price, chandelier_stop)

    # 3. Full Profit Target Hit (+3.0R)
    target_price = pos.entry_price + (config.profit_target_r_mult * pos.r_distance)
    if current_high >= target_price:
        exit_price = target_price * (1.0 - friction_rate)
        return (
            DTPExitReason.PROFIT_TARGET,
            exit_price,
            f"Profit target achieved (+{config.profit_target_r_mult:.1f}R at {target_price:.2f})",
        )

    # 4. Dynamic Overbought Blow-off (RSI >= 78 + Upper BB)
    if current_rsi >= config.rsi_overbought_threshold and current_high >= current_bb_upper:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.DYNAMIC_OVERBOUGHT,
            exit_price,
            f"Overbought exit (RSI={current_rsi:.1f} >= {config.rsi_overbought_threshold}, High={current_high:.2f} >= BB={current_bb_upper:.2f})",
        )

    # 5. Trend Breakdown Check (2 consecutive closes < EMA50)
    if current_close < current_ema50:
        pos.consecutive_closes_below_ema50 += 1
    else:
        pos.consecutive_closes_below_ema50 = 0

    if pos.consecutive_closes_below_ema50 >= config.consecutive_breakdown_bars:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.TREND_BREAKDOWN,
            exit_price,
            f"Trend breakdown ({pos.consecutive_closes_below_ema50} closes below EMA50={current_ema50:.2f})",
        )

    # 6. Time-Based Horizon Limit (10 sessions with excursion bypass)
    if pos.holding_days >= config.max_holding_sessions and excursion_r < config.trailing_r_mult:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.TIME_LIMIT,
            exit_price,
            f"Time limit reached ({pos.holding_days} sessions, excursion {excursion_r:.2f}R < {config.trailing_r_mult}R)",
        )

    return None, 0.0, "Hold position"

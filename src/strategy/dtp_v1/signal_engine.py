"""
SignalForge — Phase 32C.5: DTP-V1 Signal Engine
===============================================
File: src/strategy/dtp_v1/signal_engine.py

Implements deterministic signal generation, pullback verification, next-session
execution gating, and hierarchical exit evaluations for DTP-V1 delivery swing strategy.

Strict Causality Invariants:
  - All EOD signals are generated strictly from completed Bar T data.
  - Next-session execution intent targets Bar T+1 Open with gap-risk filtering.
  - No future bars or intrabar look-ahead are ever used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v1.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV1Config,
    OrderAction,
)


@dataclass(frozen=True)
class DTPEODSignal:
    """EOD trade candidate signal generated at Bar T close."""
    symbol: str
    signal_date: date
    action: OrderAction
    entry_trigger_price: float
    initial_stop_price: float
    r_distance: float
    regime: DTPRegimeState
    notes: List[str] = field(default_factory=list)


@dataclass
class DTPPositionState:
    """Tracks state and dynamic stop progression for an active delivery position."""
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
    consecutive_closes_below_ema50: int = 0
    is_breakeven_activated: bool = False
    is_trailing_activated: bool = False


def is_trend_aligned(
    df: pd.DataFrame,
    idx: int,
    config: Optional[DTPV1Config] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether an individual stock is in a confirmed macro uptrend on Bar idx:
      1. Close > EMA50
      2. EMA20 > EMA50
      3. ADX >= 20.0 AND +DI > -DI
      4. Relative Strength >= 0.0 (outperforming or in-line with benchmark)
    """
    if config is None:
        config = DTPV1Config()

    c = df["close"].iloc[idx]
    ema20 = df["ema_fast"].iloc[idx]
    ema50 = df["ema_slow"].iloc[idx]
    adx = df["adx"].iloc[idx]
    p_di = df["plus_di"].iloc[idx]
    m_di = df["minus_di"].iloc[idx]
    rs = df["relative_strength"].iloc[idx]

    if pd.isna(ema50) or pd.isna(ema20) or pd.isna(adx):
        return False, "Indicators not ready (warmup)"

    if c <= ema50:
        return False, f"Close ({c:.2f}) <= EMA50 ({ema50:.2f})"
    if ema20 <= ema50:
        return False, f"EMA20 ({ema20:.2f}) <= EMA50 ({ema50:.2f})"
    if adx < config.adx_min_threshold:
        return False, f"ADX ({adx:.1f}) < min threshold ({config.adx_min_threshold})"
    if p_di <= m_di:
        return False, f"+DI ({p_di:.1f}) <= -DI ({m_di:.1f})"
    if pd.notna(rs) and rs < 0.0:
        return False, f"Relative Strength ({rs:.3f}) < 0.0"

    return True, "Stock in confirmed macro uptrend"


def is_pullback_active(
    df: pd.DataFrame,
    idx: int,
    config: Optional[DTPV1Config] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether Bar idx qualifies as a valid, controlled pullback:
      1. Low <= EMA20 * (1 + proximity_pct)  [touches or nears 20 EMA]
      2. Close > EMA50                       [preserves intermediate support]
      3. Retracement depth <= 61.8% of 20-day swing range
      4. 38.0 <= RSI <= 52.0                 [bull-market support zone]
      5. Volume contraction: Volume <= 1.10 * 20-day volume SMA
    """
    if config is None:
        config = DTPV1Config()

    low = df["low"].iloc[idx]
    c = df["close"].iloc[idx]
    ema20 = df["ema_fast"].iloc[idx]
    ema50 = df["ema_slow"].iloc[idx]
    rsi = df["rsi"].iloc[idx]
    vol = df["volume"].iloc[idx]
    vol_sma = df["volume_sma"].iloc[idx]
    swing_h = df["swing_high_20"].iloc[idx]
    swing_l = df["swing_low_20"].iloc[idx]

    if pd.isna(ema20) or pd.isna(rsi):
        return False, "Indicators not ready"

    # 1. Proximity to 20-day EMA
    max_low_boundary = ema20 * (1.0 + config.ema20_proximity_pct)
    if low > max_low_boundary:
        return False, f"Low ({low:.2f}) did not pull back to 20 EMA ({ema20:.2f})"

    # 2. Support preservation above 50-day EMA
    if c <= ema50:
        return False, f"Close ({c:.2f}) violated 50 EMA ({ema50:.2f})"

    # 3. Retracement depth <= 61.8%
    if pd.notna(swing_h) and pd.notna(swing_l) and swing_h > swing_l:
        swing_range = swing_h - swing_l
        retracement = (swing_h - low) / swing_range
        if retracement > config.max_retracement_depth:
            return False, f"Retracement depth ({retracement:.1%}) exceeded {config.max_retracement_depth:.1%}"

    # 4. RSI support band (38 to 52)
    if rsi < config.rsi_pullback_min or rsi > config.rsi_pullback_max:
        return False, f"RSI ({rsi:.1f}) outside pullback support band [{config.rsi_pullback_min}, {config.rsi_pullback_max}]"

    # 5. Volume contraction
    if pd.notna(vol_sma) and vol_sma > 0:
        prev_vol_sma = df["volume_sma"].iloc[max(0, idx - 1)]
        if vol > prev_vol_sma * config.volume_contraction_ratio:
            return False, f"Volume ({vol:,.0f}) exceeds contraction threshold ({prev_vol_sma * config.volume_contraction_ratio:,.0f})"

    return True, "Valid controlled pullback"


def check_reversal_trigger(
    df: pd.DataFrame,
    idx: int,
    config: Optional[DTPV1Config] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether Bar idx produces a bullish reversal confirmation from a recent pullback:
      1. Pullback active within previous config.pullback_window_days (1 to 3 days ago).
      2. Bar idx is bullish green candle: Close > Open AND Close > prev_Close.
      3. Bar idx Close reclaims 20-day EMA: Close >= EMA20.
      4. Volume expansion on reversal: Volume >= 0.90 * volume_SMA OR Volume > prev_Volume.
    """
    if config is None:
        config = DTPV1Config()

    if idx < config.pullback_window_days:
        return False, "Insufficient history for pullback window"

    # Check that a valid pullback occurred in the recent lookback window
    pullback_found = False
    for lookback in range(1, config.pullback_window_days + 1):
        p_idx = idx - lookback
        valid_pb, _ = is_pullback_active(df, p_idx, config)
        if valid_pb:
            pullback_found = True
            break

    if not pullback_found:
        return False, f"No valid pullback in previous {config.pullback_window_days} sessions"

    c = df["close"].iloc[idx]
    o = df["open"].iloc[idx]
    prev_c = df["close"].iloc[idx - 1]
    ema20 = df["ema_fast"].iloc[idx]
    vol = df["volume"].iloc[idx]
    prev_vol = df["volume"].iloc[idx - 1]
    vol_sma = df["volume_sma"].iloc[idx]

    # Bullish green candle
    if c <= o or c <= prev_c:
        return False, f"Trigger candle not bullish (Close={c:.2f}, Open={o:.2f}, PrevClose={prev_c:.2f})"

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
    config: Optional[DTPV1Config] = None,
    bar_idx: int = -1,
    signal_date: Optional[date] = None,
) -> Optional[DTPEODSignal]:
    """
    Generates a causal EOD signal at Bar T close.
    Returns DTPEODSignal if all conditions are met, otherwise None.
    """
    if config is None:
        config = DTPV1Config()

    # Bearish market regime halts all new entry signals
    if market_regime == DTPRegimeState.BEARISH or market_regime == DTPRegimeState.UNKNOWN:
        return None

    n_rows = len(df)
    target_idx = bar_idx if bar_idx >= 0 else n_rows + bar_idx
    if target_idx < max(config.ema_slow_period, config.pullback_window_days + 1):
        return None

    # 1. Macro Trend Filter
    trend_ok, trend_msg = is_trend_aligned(df, target_idx, config)
    if not trend_ok:
        return None

    # 2. Pullback & Reversal Trigger
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
    config: Optional[DTPV1Config] = None,
) -> Tuple[OrderAction, float, str]:
    """
    Evaluates execution of an EOD signal at next session open:
      1. Gap-up > +1.5%: REJECT_GAP_UP (do not chase runaway gaps).
      2. Gap-down < initial_stop_price: REJECT_GAP_DOWN (trade thesis broken).
      3. Normal open: fills at open + execution friction (slippage + spread).
    """
    if config is None:
        config = DTPV1Config()

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
    config: Optional[DTPV1Config] = None,
) -> Tuple[Optional[DTPExitReason], float, str]:
    """
    Evaluates deterministic exit hierarchy for an active delivery position on current session:
      1. Stop-Loss: Low <= current_stop_price -> exit immediately at min(Open, current_stop)
      2. Trailing Stop updates: Breakeven (+1.0R) and Chandelier trailing (+1.5R)
      3. Trend Breakdown: 2 consecutive closes < EMA50 -> exit
      4. Time-based: holding_days >= 10 and price < Entry + 1.5R -> exit
      5. Profit Target: High >= Entry + 3.0R -> exit
      6. Dynamic Overbought: RSI >= 78.0 and High >= BB_Upper -> exit
    """
    if config is None:
        config = DTPV1Config()

    pos.holding_days += 1
    friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0

    # Track excursion
    if current_high > pos.highest_high:
        pos.highest_high = current_high
    if current_close > pos.highest_close:
        pos.highest_close = current_close

    # 1. Stop-Loss Trigger (Highest Priority)
    if current_low <= pos.current_stop_price:
        # If opened below stop, filled at open price (slippage against position)
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

    # Chandelier Trailing advancement (+1.5R)
    if excursion_r >= config.trailing_r_mult:
        pos.is_trailing_activated = True
        chandelier_stop = pos.highest_close - (config.trailing_atr_mult * current_atr)
        pos.current_stop_price = max(pos.current_stop_price, chandelier_stop)

    # 3. Full Profit Target Hit (+3.0R)
    target_price = pos.entry_price + (config.profit_target_r_mult * pos.r_distance)
    if current_high >= target_price:
        exit_price = target_price * (1.0 - friction_rate)
        return DTPExitReason.PROFIT_TARGET, exit_price, f"Profit target achieved (+3.0R at {target_price:.2f})"

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

    # 6. Time-Based Horizon Limit (10 sessions without reaching +1.5R)
    if pos.holding_days >= config.max_holding_sessions and excursion_r < config.trailing_r_mult:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.TIME_LIMIT,
            exit_price,
            f"Time limit reached ({pos.holding_days} sessions, excursion {excursion_r:.2f}R < {config.trailing_r_mult}R)",
        )

    return None, 0.0, "Hold position"

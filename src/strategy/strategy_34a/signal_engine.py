"""
SignalForge — Phase 34A: Signal Generation & Exit Evaluation Engine
===================================================================
File: src/strategy/strategy_34a/signal_engine.py

Generates causal entry signals and evaluates multi-tier exits:
  - Entry: Weekly trend + Daily momentum + RS vs Nifty + Volume confirmation
  - Exits: Initial ATR protective stop, EOD trend deterioration exit, and max holding time stop
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.strategy_34a.config import (
    DailyMomentumFilter,
    ExitReason,
    RSPeriod,
    Strategy34AConfig,
    VolumeThreshold,
    WeeklyTrendFilter,
)


@dataclass
class Strategy34ASignal:
    """Represents an actionable EOD entry signal for execution on next session open."""
    symbol: str
    signal_date: date
    close: float
    atr14: float
    stop_loss_price: float
    dema20: float
    dema50: float
    rsi14: float
    weekly_close: float
    wema10: float
    wema20: float
    wema30: float
    rs_val: float
    vol_ratio: float
    config_id: str


def check_weekly_trend_filter(row: pd.Series, filter_mode: WeeklyTrendFilter) -> bool:
    """Evaluates Experiment A: Weekly trend filter against completed weekly candles."""
    if filter_mode == WeeklyTrendFilter.NONE:
        return True

    wclose = row.get("weekly_close", np.nan)
    wema10 = row.get("wema10", np.nan)
    wema20 = row.get("wema20", np.nan)
    wema30 = row.get("wema30", np.nan)

    if pd.isna(wclose) or pd.isna(wema10) or pd.isna(wema20) or pd.isna(wema30):
        return False

    if filter_mode == WeeklyTrendFilter.A1_CLOSE_GT_WEMA10:
        return bool(wclose > wema10)
    elif filter_mode == WeeklyTrendFilter.A2_CLOSE_GT_WEMA20:
        return bool(wclose > wema20)
    elif filter_mode == WeeklyTrendFilter.A3_CLOSE_GT_WEMA30:
        return bool(wclose > wema30)
    elif filter_mode == WeeklyTrendFilter.A4_WEMA10_GT_WEMA20:
        return bool(wema10 > wema20)

    return False


def check_daily_momentum_filter(row: pd.Series, filter_mode: DailyMomentumFilter) -> bool:
    """Evaluates Experiment B: Daily momentum confirmation."""
    if filter_mode == DailyMomentumFilter.NONE:
        return True

    close = row.get("close", np.nan)
    dema20 = row.get("dema20", np.nan)
    dema50 = row.get("dema50", np.nan)
    rsi14 = row.get("rsi14", np.nan)

    if pd.isna(close) or pd.isna(dema20) or pd.isna(dema50) or pd.isna(rsi14):
        return False

    if filter_mode == DailyMomentumFilter.B1_CLOSE_GT_EMA20_AND_EMA20_GT_EMA50:
        return bool(close > dema20 and dema20 > dema50)
    elif filter_mode == DailyMomentumFilter.B2_CLOSE_GT_EMA20_AND_RSI14_GT_50:
        return bool(close > dema20 and rsi14 > 50.0)
    elif filter_mode == DailyMomentumFilter.B3_EMA20_GT_EMA50_AND_RSI_RANGE:
        return bool(dema20 > dema50 and 50.0 <= rsi14 <= 70.0)

    return False


def check_relative_strength_filter(row: pd.Series, rs_period: RSPeriod) -> Tuple[bool, float]:
    """Evaluates Experiment C: Relative strength vs Nifty 50 over N sessions."""
    if rs_period == RSPeriod.NONE:
        return True, 0.0

    rs_col = f"rs_{rs_period.value}"
    rs_val = row.get(rs_col, np.nan)
    if pd.isna(rs_val):
        return False, 0.0

    return bool(rs_val > 0.0), float(rs_val)


def check_volume_confirmation_filter(row: pd.Series, vol_thresh: VolumeThreshold) -> Tuple[bool, float]:
    """Evaluates Experiment D: Volume ratio vs 20-day Volume SMA."""
    if vol_thresh == VolumeThreshold.NONE:
        return True, 1.0

    vol_ratio = row.get("vol_ratio", np.nan)
    if pd.isna(vol_ratio):
        return False, 0.0

    return bool(vol_ratio >= vol_thresh.value), float(vol_ratio)


def generate_34a_signals(
    symbol: str,
    row: pd.Series,
    signal_date: date,
    config: Strategy34AConfig,
) -> Optional[Strategy34ASignal]:
    """
    Evaluates entry conditions on day t at EOD.
    Returns Strategy34ASignal if all conditions are satisfied.
    """
    # 1. Weekly Trend Filter
    if not check_weekly_trend_filter(row, config.weekly_filter):
        return None

    # 2. Daily Momentum Confirmation
    if not check_daily_momentum_filter(row, config.daily_filter):
        return None

    # 3. Relative Strength vs Nifty
    rs_ok, rs_val = check_relative_strength_filter(row, config.rs_period)
    if not rs_ok:
        return None

    # 4. Volume Confirmation
    vol_ok, vol_ratio = check_volume_confirmation_filter(row, config.volume_threshold)
    if not vol_ok:
        return None

    # ATR check for stop sizing
    atr14 = row.get("atr14", np.nan)
    close = float(row.get("close", 0.0))
    if pd.isna(atr14) or atr14 <= 0 or close <= 0:
        return None

    stop_loss = close - (config.atr_stop_multiplier * atr14)
    if stop_loss <= 0:
        stop_loss = close * 0.90  # Safety fallback

    return Strategy34ASignal(
        symbol=symbol,
        signal_date=signal_date,
        close=close,
        atr14=float(atr14),
        stop_loss_price=float(stop_loss),
        dema20=float(row.get("dema20", 0.0)),
        dema50=float(row.get("dema50", 0.0)),
        rsi14=float(row.get("rsi14", 0.0)),
        weekly_close=float(row.get("weekly_close", 0.0)),
        wema10=float(row.get("wema10", 0.0)),
        wema20=float(row.get("wema20", 0.0)),
        wema30=float(row.get("wema30", 0.0)),
        rs_val=rs_val,
        vol_ratio=vol_ratio,
        config_id=config.config_id,
    )


def evaluate_34a_exit(
    pos: Dict[str, Any],
    bar: pd.Series,
    is_final_bar: bool,
    config: Strategy34AConfig,
) -> Tuple[bool, float, Optional[ExitReason], str, bool]:
    """
    Evaluates exit logic for an active position:
      - Returns (should_exit_now, exit_price, reason, note, exit_next_open)
      - If should_exit_now: execute exit immediately on current bar (intraday stop or final bar close).
      - If exit_next_open: execute exit on next session open (trend deterioration or max hold).
    """
    open_px = float(bar["open"])
    high_px = float(bar["high"])
    low_px = float(bar["low"])
    close_px = float(bar["close"])
    dema20 = float(bar.get("dema20", np.nan))

    # 1. Final bar of data liquidation
    if is_final_bar:
        return True, close_px, ExitReason.END_OF_DATA_LIQUIDATION, "Final bar backtest liquidation", False

    # 2. Intraday Protective Stop
    if low_px <= pos["stop_loss_price"]:
        exec_px = min(open_px, pos["stop_loss_price"])
        return True, exec_px, ExitReason.PROTECTIVE_STOP, f"ATR stop breach at {exec_px:.2f}", False

    # 3. EOD Trend Deterioration Exit (Close < Daily EMA 20)
    if config.exit_on_ema20_break and not pd.isna(dema20) and close_px < dema20:
        return False, 0.0, ExitReason.TREND_DETERIORATION, f"Daily close {close_px:.2f} < D-EMA20 {dema20:.2f}", True

    # 4. Maximum Holding Period
    if pos["bars_held"] >= config.max_holding_bars:
        return False, 0.0, ExitReason.TIME_STOP, f"Max holding period reached ({pos['bars_held']} bars)", True

    return False, 0.0, None, "", False

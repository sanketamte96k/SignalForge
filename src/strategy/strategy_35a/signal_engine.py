"""
SignalForge — Phase 35A: Signal Generation & Exit Evaluation Engine
===================================================================
File: src/strategy/strategy_35a/signal_engine.py

Generates causal entry signals and evaluates three pre-defined exit concepts:
  - Regimes: A (SMA50/200), B (Nifty SMA100 + SMA200), C (EMA50 rising)
  - Entries: MR1 (RSI5 + Lower BB), MR2 (RSI2 + EMA20), MR3 (1-ATR Pullback + RSI14)
  - Exits: Exit A (EMA20 recovery), Exit B (BB Middle target + 2 ATR stop), Exit C (ATR Trailing Stop)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.strategy.strategy_35a.config import (
    ExitConceptType,
    ExitReason,
    MeanReversionEntryType,
    RegimeFilterType,
    Strategy35AConfig,
)


@dataclass
class Strategy35ASignal:
    """Actionable EOD entry signal for execution on next session open."""
    symbol: str
    signal_date: date
    close: float
    atr14: float
    stop_loss_price: float
    rsi2: float
    rsi5: float
    rsi14: float
    ema20: float
    ema50: float
    bb_lower: float
    bb_middle: float
    regime_mode: str
    entry_mode: str


def check_regime_filter(row: pd.Series, regime_type: RegimeFilterType) -> bool:
    """Evaluates whether the market / stock meets the pre-defined bullish regime condition."""
    if regime_type == RegimeFilterType.NONE:
        return True

    close = row.get("close", np.nan)
    if pd.isna(close) or close <= 0:
        return False

    if regime_type == RegimeFilterType.REGIME_A:
        sma50 = row.get("sma50", np.nan)
        sma200 = row.get("sma200", np.nan)
        if pd.isna(sma50) or pd.isna(sma200):
            return False
        return bool(close > sma200 and sma50 > sma200)

    elif regime_type == RegimeFilterType.REGIME_B:
        sma200 = row.get("sma200", np.nan)
        nifty_close = row.get("nifty_close", np.nan)
        nifty_sma100 = row.get("nifty_sma100", np.nan)
        if pd.isna(sma200) or pd.isna(nifty_close) or pd.isna(nifty_sma100):
            return False
        return bool(nifty_close > nifty_sma100 and close > sma200)

    elif regime_type == RegimeFilterType.REGIME_C:
        ema50 = row.get("ema50", np.nan)
        ema50_slope = row.get("ema50_slope", np.nan)
        if pd.isna(ema50) or pd.isna(ema50_slope):
            return False
        return bool(close > ema50 and ema50_slope > 0.0)

    return False


def check_entry_concept(row: pd.Series, entry_type: MeanReversionEntryType) -> bool:
    """Evaluates whether the stock triggers a pre-registered mean-reversion entry condition."""
    close = row.get("close", np.nan)
    if pd.isna(close) or close <= 0:
        return False

    if entry_type == MeanReversionEntryType.MR1_RSI5_BB:
        rsi5 = row.get("rsi5", np.nan)
        bb_lower = row.get("bb_lower", np.nan)
        if pd.isna(rsi5) or pd.isna(bb_lower):
            return False
        return bool(rsi5 < 30.0 and close < bb_lower)

    elif entry_type == MeanReversionEntryType.MR2_RSI2_EMA20:
        rsi2 = row.get("rsi2", np.nan)
        ema20 = row.get("ema20", np.nan)
        if pd.isna(rsi2) or pd.isna(ema20):
            return False
        return bool(rsi2 < 10.0 and close < ema20)

    elif entry_type == MeanReversionEntryType.MR3_PULLBACK_ATR:
        ema20 = row.get("ema20", np.nan)
        atr14 = row.get("atr14", np.nan)
        rsi14 = row.get("rsi14", np.nan)
        if pd.isna(ema20) or pd.isna(atr14) or pd.isna(rsi14) or atr14 <= 0:
            return False
        pullback_threshold = ema20 - (1.0 * atr14)
        return bool(close <= pullback_threshold and rsi14 < 40.0)

    return False


def generate_35a_signals(
    symbol: str,
    row: pd.Series,
    signal_date: date,
    config: Strategy35AConfig,
) -> Optional[Strategy35ASignal]:
    """Evaluates EOD entry conditions on day t for next morning open execution."""
    # 1. Check Bullish Regime Filter
    if not check_regime_filter(row, config.regime_filter):
        return None

    # 2. Check Mean Reversion Entry Concept
    if not check_entry_concept(row, config.entry_concept):
        return None

    # Sizing metrics
    close = float(row.get("close", 0.0))
    atr14 = float(row.get("atr14", 0.0))
    if close <= 0 or atr14 <= 0 or pd.isna(atr14):
        return None

    stop_loss = close - (config.atr_stop_multiplier * atr14)
    if stop_loss <= 0:
        stop_loss = close * 0.90

    return Strategy35ASignal(
        symbol=symbol,
        signal_date=signal_date,
        close=close,
        atr14=atr14,
        stop_loss_price=float(stop_loss),
        rsi2=float(row.get("rsi2", 0.0)),
        rsi5=float(row.get("rsi5", 0.0)),
        rsi14=float(row.get("rsi14", 0.0)),
        ema20=float(row.get("ema20", 0.0)),
        ema50=float(row.get("ema50", 0.0)),
        bb_lower=float(row.get("bb_lower", 0.0)),
        bb_middle=float(row.get("bb_middle", 0.0)),
        regime_mode=config.regime_filter.value,
        entry_mode=config.entry_concept.value,
    )


def evaluate_35a_exit(
    pos: Dict[str, Any],
    bar: pd.Series,
    is_final_bar: bool,
    config: Strategy35AConfig,
) -> Tuple[bool, float, Optional[ExitReason], str, bool]:
    """
    Evaluates exit logic for an active position:
      - Returns: (should_exit_now, exit_price, reason, note, exit_next_open)
      - should_exit_now: Intraday execution (stop hit or intraday target).
      - exit_next_open: EOD trigger (EMA20 recovery or max hold) executed next morning.
    """
    open_px = float(bar["open"])
    high_px = float(bar["high"])
    low_px = float(bar["low"])
    close_px = float(bar["close"])
    ema20 = float(bar.get("ema20", np.nan))
    bb_middle = float(bar.get("bb_middle", np.nan))
    atr14 = float(bar.get("atr14", pos.get("initial_atr", 1.0)))

    # 1. Final bar of backtest window
    if is_final_bar:
        return True, close_px, ExitReason.END_OF_DATA, "Final bar backtest liquidation", False

    # 2. Concept-specific Exits
    if config.exit_concept == ExitConceptType.EXIT_A:
        # Exit A: Recover above EMA 20 (EOD check) or Max 10 sessions
        if not pd.isna(ema20) and close_px > ema20:
            return False, 0.0, ExitReason.TARGET_RECOVERY, f"Close {close_px:.2f} > EMA20 {ema20:.2f}", True
        if pos["bars_held"] >= config.max_holding_bars:
            return False, 0.0, ExitReason.TIME_STOP, f"Max holding period ({pos['bars_held']} bars)", True

    elif config.exit_concept == ExitConceptType.EXIT_B:
        # Exit B: Initial stop 2 ATR, Target BB middle, or Max 10 sessions
        # 1. Protective stop (intraday)
        if low_px <= pos["stop_loss_price"]:
            exec_px = min(open_px, pos["stop_loss_price"])
            return True, exec_px, ExitReason.INITIAL_STOP, f"Initial 2-ATR stop hit at {exec_px:.2f}", False

        # 2. Profit target: reaches BB middle (intraday)
        if not pd.isna(bb_middle) and high_px >= bb_middle:
            exec_px = max(open_px, bb_middle)
            return True, exec_px, ExitReason.TARGET_RECOVERY, f"BB middle band reached at {exec_px:.2f}", False

        # 3. Time stop
        if pos["bars_held"] >= config.max_holding_bars:
            return False, 0.0, ExitReason.TIME_STOP, f"Max holding period ({pos['bars_held']} bars)", True

    elif config.exit_concept == ExitConceptType.EXIT_C:
        # Exit C: ATR Trailing Stop (2 ATR from highest high) or Max 10 sessions
        highest_high = max(pos.get("highest_high", open_px), high_px)
        pos["highest_high"] = highest_high
        trailing_stop = highest_high - (config.atr_stop_multiplier * atr14)
        pos["current_trailing_stop"] = max(pos.get("current_trailing_stop", pos["stop_loss_price"]), trailing_stop)

        if low_px <= pos["current_trailing_stop"]:
            exec_px = min(open_px, pos["current_trailing_stop"])
            return True, exec_px, ExitReason.TRAILING_STOP, f"ATR trailing stop hit at {exec_px:.2f}", False

        if pos["bars_held"] >= config.max_holding_bars:
            return False, 0.0, ExitReason.TIME_STOP, f"Max holding period ({pos['bars_held']} bars)", True

    return False, 0.0, None, "", False

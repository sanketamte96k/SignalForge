"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Signal & Exit Engine
=======================================================================
File: src/strategy/dtp_v3_exit_research/signal_engine.py

Implements deterministic evaluation of alternative exit methods:
  - Method A: EXISTING_EXIT (Current DTP-V3 exit hierarchy)
  - Method B: BREAKEVEN_ONLY (Stop to entry price at +1.0R, no trailing ATR)
  - Method C: ATR_TRAILING (At +1.0R, trail at Close - 2x ATR)
  - Method D: CHANDELIER_HIGHEST_CLOSE (At +1.0R, trail at Highest Close - 2x ATR)
  - Method E: PARTIAL_PROFIT_BOOKING (At +1.5R, exit 50% shares, trail rest with existing stop)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3.config import DTPExitReason, DTPRegimeState, OrderAction
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal,
    evaluate_next_open_execution,
    generate_eod_signal,
)
from src.strategy.dtp_v3_exit_research.config import DTPV3ExitResearchConfig, ExitResearchMethod


@dataclass
class DTPExitPositionState:
    """Represents mutable state of an active position during exit research."""
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    initial_quantity: int
    initial_stop_price: float
    current_stop_price: float
    r_distance: float
    holding_days: int = 0
    highest_high: float = 0.0
    highest_close: float = 0.0
    consecutive_closes_below_ema50: int = 0
    is_breakeven_activated: bool = False
    is_trailing_activated: bool = False
    is_partial_taken: bool = False


def evaluate_research_exit_conditions(
    pos: DTPExitPositionState,
    current_high: float,
    current_low: float,
    current_close: float,
    current_open: float,
    current_atr: float,
    current_ema50: float,
    current_rsi: float,
    current_bb_upper: float,
    config: Optional[DTPV3ExitResearchConfig] = None,
) -> Tuple[Optional[DTPExitReason], float, str, Optional[Dict[str, Any]]]:
    """
    Evaluates exit conditions for the specified ExitResearchMethod:
    Returns (exit_reason, exit_price, exit_message, partial_exit_info).
    """
    if config is None:
        config = DTPV3ExitResearchConfig()

    pos.holding_days += 1
    friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0

    if current_high > pos.highest_high:
        pos.highest_high = current_high
    if current_close > pos.highest_close:
        pos.highest_close = current_close

    excursion_r = (pos.highest_high - pos.entry_price) / pos.r_distance if pos.r_distance > 0 else 0.0
    partial_info: Optional[Dict[str, Any]] = None

    # =========================================================================
    # Step 1: Check Stop-Loss Execution (Highest Priority)
    # =========================================================================
    if current_low <= pos.current_stop_price:
        raw_exit = min(current_open, pos.current_stop_price)
        exit_price = raw_exit * (1.0 - friction_rate)
        if pos.is_trailing_activated:
            reason = DTPExitReason.TRAILING_STOP
        elif pos.is_breakeven_activated:
            reason = DTPExitReason.BREAKEVEN_STOP
        else:
            reason = DTPExitReason.INITIAL_STOP
        return reason, exit_price, f"Stop-loss executed (Low={current_low:.2f} <= Stop={pos.current_stop_price:.2f})", None

    # =========================================================================
    # Step 2: Handle Partial Profit Booking (+1.5R) for Method E
    # =========================================================================
    if config.exit_method == ExitResearchMethod.PARTIAL_PROFIT_BOOKING:
        target_partial = pos.entry_price + (config.partial_profit_r_mult * pos.r_distance)
        if not pos.is_partial_taken and current_high >= target_partial:
            shares_to_sell = pos.quantity // 2
            if shares_to_sell > 0:
                pos.is_partial_taken = True
                p_exit_price = target_partial * (1.0 - friction_rate)
                partial_info = {
                    "partial_shares": shares_to_sell,
                    "partial_price": p_exit_price,
                    "partial_reason": "PARTIAL_PROFIT_1.5R",
                }

    # =========================================================================
    # Step 3: Advance Stop Price Based on Exit Method
    # =========================================================================
    method = config.exit_method

    if method == ExitResearchMethod.EXISTING_EXIT or method == ExitResearchMethod.PARTIAL_PROFIT_BOOKING:
        # Standard DTP-V3 Exit Logic:
        # Breakeven at +1.0R (with 0.5% cost buffer)
        if excursion_r >= config.breakeven_r_mult and not pos.is_breakeven_activated:
            pos.is_breakeven_activated = True
            be_stop = pos.entry_price * (1.0 + config.breakeven_cost_buffer_pct)
            pos.current_stop_price = max(pos.current_stop_price, be_stop)

        # Chandelier Trailing Stop at +1.5R: Anchored to Highest High (HH - 2.0 * ATR)
        if excursion_r >= config.trailing_r_mult:
            pos.is_trailing_activated = True
            chandelier_stop = pos.highest_high - (config.trailing_atr_mult * current_atr)
            pos.current_stop_price = max(pos.current_stop_price, chandelier_stop)

    elif method == ExitResearchMethod.BREAKEVEN_ONLY:
        # Method B: Move stop to exact entry price at +1.0R; no trailing ATR
        if excursion_r >= config.breakeven_r_mult and not pos.is_breakeven_activated:
            pos.is_breakeven_activated = True
            pos.current_stop_price = max(pos.current_stop_price, pos.entry_price)

    elif method == ExitResearchMethod.ATR_TRAILING:
        # Method C: At +1.0R, activate 2x ATR trailing stop anchored to Current Close
        if excursion_r >= config.trailing_activation_r_mult:
            pos.is_trailing_activated = True
            atr_stop = current_close - (config.trailing_atr_mult * current_atr)
            pos.current_stop_price = max(pos.current_stop_price, atr_stop)

    elif method == ExitResearchMethod.CHANDELIER_HIGHEST_CLOSE:
        # Method D: At +1.0R, trail at Highest Close minus 2x ATR
        if excursion_r >= config.trailing_activation_r_mult:
            pos.is_trailing_activated = True
            chandelier_hc_stop = pos.highest_close - (config.trailing_atr_mult * current_atr)
            pos.current_stop_price = max(pos.current_stop_price, chandelier_hc_stop)

    # =========================================================================
    # Step 4: Full Profit Target Hit (+3.0R)
    # =========================================================================
    target_price = pos.entry_price + (config.profit_target_r_mult * pos.r_distance)
    if current_high >= target_price:
        exit_price = target_price * (1.0 - friction_rate)
        return (
            DTPExitReason.PROFIT_TARGET,
            exit_price,
            f"Profit target achieved (+{config.profit_target_r_mult:.1f}R at {target_price:.2f})",
            partial_info,
        )

    # =========================================================================
    # Step 5: Dynamic Overbought Blow-off (RSI >= 78.0 + Upper BB)
    # =========================================================================
    if current_rsi >= config.rsi_overbought_threshold and current_high >= current_bb_upper:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.DYNAMIC_OVERBOUGHT,
            exit_price,
            f"Overbought exit (RSI={current_rsi:.1f} >= {config.rsi_overbought_threshold}, High={current_high:.2f} >= BB={current_bb_upper:.2f})",
            partial_info,
        )

    # =========================================================================
    # Step 6: Trend Breakdown Check (2 consecutive closes < EMA50)
    # =========================================================================
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
            partial_info,
        )

    # =========================================================================
    # Step 7: Time-Based Horizon Limit (10 sessions with excursion bypass)
    # =========================================================================
    if pos.holding_days >= config.max_holding_sessions and excursion_r < config.trailing_r_mult:
        exit_price = current_close * (1.0 - friction_rate)
        return (
            DTPExitReason.TIME_LIMIT,
            exit_price,
            f"Time limit reached ({pos.holding_days} sessions, excursion {excursion_r:.2f}R < {config.trailing_r_mult}R)",
            partial_info,
        )

    return None, 0.0, "Hold position", partial_info

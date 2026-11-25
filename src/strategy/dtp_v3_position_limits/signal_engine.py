"""
SignalForge — Phase 32J.5: Signal Engine Re-exports
===================================================
File: src/strategy/dtp_v3_position_limits/signal_engine.py

Uses the frozen Method A (Existing DTP-V3 Exit) signal and exit logic:
  - Initial stop: swing low or 3x ATR.
  - At +1.0R: stop moves to entry price.
  - At +2.0R: trailing stop at Highest High - 2.5x ATR.
  - Max holding period: 15 trading bars.
"""
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)

__all__ = [
    "DTPEODSignal",
    "DTPPositionState",
    "evaluate_exit_conditions",
    "evaluate_next_open_execution",
    "generate_eod_signal",
]

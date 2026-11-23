"""
SignalForge — Phase 32J.3.1: DTP-V3 Regime Signal Engine
=========================================================
File: src/strategy/dtp_v3_regime/signal_engine.py
Re-exports signal generation, position state, and exit conditions from frozen DTP-V3.
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

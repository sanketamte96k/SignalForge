"""
SignalForge — Phase 34A: Multi-Timeframe Momentum Research Module
================================================================
Package: src/strategy/strategy_34a

Completely independent implementation of multi-timeframe swing trading strategies
using weekly trend direction and daily momentum confirmation.
"""

from src.strategy.strategy_34a.config import (
    CombinedConfigID,
    DailyMomentumFilter,
    ExitReason,
    RSPeriod,
    Strategy34AConfig,
    VolumeThreshold,
    WeeklyTrendFilter,
)
from src.strategy.strategy_34a.indicators import (
    attach_multi_timeframe_indicators,
    build_completed_weekly_bars,
    calculate_nifty_relative_strength,
)
from src.strategy.strategy_34a.signal_engine import (
    Strategy34ASignal,
    evaluate_34a_exit,
    generate_34a_signals,
)
from src.strategy.strategy_34a.portfolio_simulator import (
    CompletedTrade34A,
    SimulationResult34A,
    run_34a_simulation,
)

__all__ = [
    "WeeklyTrendFilter",
    "DailyMomentumFilter",
    "RSPeriod",
    "VolumeThreshold",
    "CombinedConfigID",
    "ExitReason",
    "Strategy34AConfig",
    "build_completed_weekly_bars",
    "calculate_nifty_relative_strength",
    "attach_multi_timeframe_indicators",
    "Strategy34ASignal",
    "generate_34a_signals",
    "evaluate_34a_exit",
    "CompletedTrade34A",
    "SimulationResult34A",
    "run_34a_simulation",
]

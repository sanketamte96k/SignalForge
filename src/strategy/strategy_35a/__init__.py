"""
SignalForge — Phase 35A: Regime-Filtered Mean Reversion Research Module
======================================================================
Package: src/strategy/strategy_35a

Completely independent research module for mean reversion within established bullish regimes.
"""

from src.strategy.strategy_35a.config import (
    ExitConceptType,
    ExitReason,
    MeanReversionEntryType,
    RegimeFilterType,
    RiskTier,
    Strategy35AConfig,
)
from src.strategy.strategy_35a.indicators import (
    attach_35a_indicators,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    calculate_sma,
    validate_ohlcv,
)
from src.strategy.strategy_35a.signal_engine import (
    Strategy35ASignal,
    check_entry_concept,
    check_regime_filter,
    evaluate_35a_exit,
    generate_35a_signals,
)
from src.strategy.strategy_35a.portfolio_simulator import (
    CompletedTrade35A,
    SimulationResult35A,
    run_35a_simulation,
    to_py_date,
)

__all__ = [
    "RegimeFilterType",
    "MeanReversionEntryType",
    "ExitConceptType",
    "RiskTier",
    "ExitReason",
    "Strategy35AConfig",
    "validate_ohlcv",
    "calculate_sma",
    "calculate_ema",
    "calculate_atr",
    "calculate_rsi",
    "calculate_bollinger_bands",
    "attach_35a_indicators",
    "Strategy35ASignal",
    "check_regime_filter",
    "check_entry_concept",
    "generate_35a_signals",
    "evaluate_35a_exit",
    "CompletedTrade35A",
    "SimulationResult35A",
    "run_35a_simulation",
    "to_py_date",
]

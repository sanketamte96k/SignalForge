"""
SignalForge — Experimental Strategy Layer
=========================================
Package: src/strategy/experimental
"""

from src.strategy.experimental.trend_filtered_strategy import (
    ExperimentalStrategyConfig,
    calculate_experimental_indicators,
    backtest_experimental_symbol,
)

__all__ = [
    "ExperimentalStrategyConfig",
    "calculate_experimental_indicators",
    "backtest_experimental_symbol",
]

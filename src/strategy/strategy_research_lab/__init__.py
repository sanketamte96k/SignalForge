"""
SignalForge — Phase 33A: Independent Strategy Research Lab
==========================================================
Package: src/strategy/strategy_research_lab

Offline Historical Quantitative Research module for 5 independent trading strategy candidates:
  - Strategy 1: Trend Pullback
  - Strategy 2: Donchian Breakout
  - Strategy 3: Relative Strength Momentum
  - Strategy 4: Trend-Conditioned Mean Reversion
  - Strategy 5: Volatility Contraction Breakout

Governed by strict SignalForge research standards:
  - Approved 91-stock universe, 2017-2019 data (739 sessions each).
  - No look-ahead, realistic execution, integer shares, zero shorting/margin.
  - Max 2 concurrent positions.
  - Certified delivery transaction costs (Official ₹307/cr and Stress ₹317/cr).
"""

from src.strategy.strategy_research_lab.config import (
    ExitReason,
    RiskTier,
    StrategyCandidateConfig,
    StrategyID,
    StrategyLabConfig,
)
from src.strategy.strategy_research_lab.indicators import (
    attach_all_indicators,
    compute_cross_sectional_ranks,
    validate_ohlc_invariants,
)
from src.strategy.strategy_research_lab.signal_engines import (
    CandidateSignal,
    evaluate_candidate_exit,
    generate_candidate_signals,
)
from src.strategy.strategy_research_lab.portfolio_simulator import (
    CompletedTrade,
    PortfolioSimulationResult,
    run_strategy_simulation,
    run_combined_portfolio_simulation,
)

__all__ = [
    "StrategyID",
    "ExitReason",
    "RiskTier",
    "StrategyLabConfig",
    "StrategyCandidateConfig",
    "attach_all_indicators",
    "compute_cross_sectional_ranks",
    "validate_ohlc_invariants",
    "CandidateSignal",
    "generate_candidate_signals",
    "evaluate_candidate_exit",
    "CompletedTrade",
    "PortfolioSimulationResult",
    "run_strategy_simulation",
    "run_combined_portfolio_simulation",
]

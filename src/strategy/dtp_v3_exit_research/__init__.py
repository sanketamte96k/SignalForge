"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Package
==========================================================
Package: src/strategy/dtp_v3_exit_research
"""

from src.strategy.dtp_v3_exit_research.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3ExitResearchConfig,
    ExitResearchMethod,
    OrderAction,
    RegimeFilterMode,
)
from src.strategy.dtp_v3_exit_research.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3_exit_research.indicators import calculate_choppiness_index, calculate_dtp_indicators
from src.strategy.dtp_v3_exit_research.market_filter import NiftyMarketFilter, evaluate_breadth_regime
from src.strategy.dtp_v3_exit_research.portfolio_rules import DTPActivePosition, DTPPortfolioTracker
from src.strategy.dtp_v3_exit_research.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3_exit_research.signal_engine import (
    DTPEODSignal,
    DTPExitPositionState,
    evaluate_next_open_execution,
    evaluate_research_exit_conditions,
    generate_eod_signal,
)

__all__ = [
    "DTPExitReason",
    "DTPRegimeState",
    "DTPV3ExitResearchConfig",
    "ExitResearchMethod",
    "OrderAction",
    "RegimeFilterMode",
    "calculate_dtp_roundtrip_costs",
    "calculate_dtp_indicators",
    "calculate_choppiness_index",
    "NiftyMarketFilter",
    "evaluate_breadth_regime",
    "DTPActivePosition",
    "DTPPortfolioTracker",
    "calculate_dtp_position_size",
    "DTPEODSignal",
    "DTPExitPositionState",
    "evaluate_next_open_execution",
    "evaluate_research_exit_conditions",
    "generate_eod_signal",
]

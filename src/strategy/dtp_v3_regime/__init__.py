"""
SignalForge — Phase 32J.3.1: DTP-V3 Market Regime Strategy Package
===================================================================
Package: src/strategy/dtp_v3_regime
"""

from src.strategy.dtp_v3_regime.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3RegimeConfig,
    OrderAction,
    RegimeFilterMode,
)
from src.strategy.dtp_v3_regime.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3_regime.indicators import calculate_choppiness_index, calculate_dtp_indicators
from src.strategy.dtp_v3_regime.market_filter import NiftyMarketFilter, evaluate_breadth_regime
from src.strategy.dtp_v3_regime.portfolio_rules import DTPActivePosition, DTPPortfolioTracker
from src.strategy.dtp_v3_regime.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3_regime.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)

__all__ = [
    "DTPExitReason",
    "DTPRegimeState",
    "DTPV3RegimeConfig",
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
    "DTPPositionState",
    "evaluate_exit_conditions",
    "evaluate_next_open_execution",
    "generate_eod_signal",
]

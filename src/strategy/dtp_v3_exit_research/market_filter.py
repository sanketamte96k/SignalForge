"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Re-exports
=============================================================
File: src/strategy/dtp_v3_exit_research/market_filter.py
Re-exports NiftyMarketFilter and evaluate_breadth_regime.
"""
from src.strategy.dtp_v3_regime.market_filter import NiftyMarketFilter, evaluate_breadth_regime

__all__ = ["NiftyMarketFilter", "evaluate_breadth_regime"]

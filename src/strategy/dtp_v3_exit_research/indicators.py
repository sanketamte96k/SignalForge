"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Indicators
=============================================================
File: src/strategy/dtp_v3_exit_research/indicators.py
Re-exports technical indicators from DTP-V3.
"""
from src.strategy.dtp_v3_regime.indicators import calculate_choppiness_index, calculate_dtp_indicators

__all__ = ["calculate_choppiness_index", "calculate_dtp_indicators"]

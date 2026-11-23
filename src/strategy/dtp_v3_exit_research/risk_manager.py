"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Risk Manager
===============================================================
File: src/strategy/dtp_v3_exit_research/risk_manager.py
Re-exports fixed-fractional integer share sizing.
"""
from src.strategy.dtp_v3_regime.risk_manager import calculate_dtp_position_size

__all__ = ["calculate_dtp_position_size"]

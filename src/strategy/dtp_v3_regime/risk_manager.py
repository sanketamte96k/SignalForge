"""
SignalForge — Phase 32J.3.1: DTP-V3 Regime Risk Management
===========================================================
File: src/strategy/dtp_v3_regime/risk_manager.py
Re-exports fixed-fractional integer share sizing from frozen DTP-V3.
"""
from src.strategy.dtp_v3.risk_manager import calculate_dtp_position_size

__all__ = ["calculate_dtp_position_size"]

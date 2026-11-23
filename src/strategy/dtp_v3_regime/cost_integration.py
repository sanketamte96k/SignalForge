"""
SignalForge — Phase 32J.3.1: DTP-V3 Regime Cost Integration
=============================================================
File: src/strategy/dtp_v3_regime/cost_integration.py
Re-exports statutory delivery cost calculation from frozen DTP-V3.
"""
from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs

__all__ = ["calculate_dtp_roundtrip_costs"]

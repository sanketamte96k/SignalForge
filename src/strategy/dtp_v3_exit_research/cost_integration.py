"""
SignalForge — Phase 32J.3.2: DTP-V3 Exit Research Cost Integration
===================================================================
File: src/strategy/dtp_v3_exit_research/cost_integration.py
Re-exports statutory delivery cost calculation engine.
"""
from src.strategy.dtp_v3_regime.cost_integration import calculate_dtp_roundtrip_costs

__all__ = ["calculate_dtp_roundtrip_costs"]

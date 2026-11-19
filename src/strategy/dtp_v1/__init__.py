"""
SignalForge — Phase 32C.5: DTP-V1 Strategy Module Package
=========================================================
File: src/strategy/dtp_v1/__init__.py

Exposes public interfaces for DTP-V1 delivery swing strategy:
  - Configuration: DTPV1Config, DTPRegimeState, DTPExitReason, OrderAction
  - Indicators: calculate_dtp_indicators, calculate_ema, calculate_atr, calculate_rsi, calculate_adx
  - Market Filter: get_market_regime, evaluate_nifty_regime, evaluate_breadth_regime
  - Signal Engine: generate_eod_signal, evaluate_next_open_execution, evaluate_exit_conditions
  - Risk Management: calculate_dtp_position_size
  - Portfolio Rules: DTPPortfolioTracker, DTPActivePosition
  - Cost Integration: calculate_dtp_roundtrip_costs, DTPTradeCostSummary
  - Strategy Orchestrator: DTPV1Strategy
"""

from src.strategy.dtp_v1.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV1Config,
    OrderAction,
)
from src.strategy.dtp_v1.cost_integration import (
    DTPTradeCostSummary,
    calculate_dtp_roundtrip_costs,
    calculate_pending_entry_costs,
)
from src.strategy.dtp_v1.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_dtp_indicators,
    calculate_ema,
    calculate_relative_strength,
    calculate_rsi,
    calculate_sma,
    calculate_tr,
)
from src.strategy.dtp_v1.market_filter import (
    evaluate_breadth_regime,
    evaluate_nifty_regime,
    get_market_regime,
)
from src.strategy.dtp_v1.portfolio_rules import (
    DTPActivePosition,
    DTPPortfolioTracker,
)
from src.strategy.dtp_v1.risk_manager import (
    calculate_dtp_position_size,
)
from src.strategy.dtp_v1.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    check_reversal_trigger,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
    is_pullback_active,
    is_trend_aligned,
)
from src.strategy.dtp_v1.strategy import (
    DTPV1Strategy,
)

__all__ = [
    "DTPExitReason",
    "DTPRegimeState",
    "DTPV1Config",
    "OrderAction",
    "DTPTradeCostSummary",
    "calculate_dtp_roundtrip_costs",
    "calculate_pending_entry_costs",
    "calculate_adx",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_dtp_indicators",
    "calculate_ema",
    "calculate_relative_strength",
    "calculate_rsi",
    "calculate_sma",
    "calculate_tr",
    "evaluate_breadth_regime",
    "evaluate_nifty_regime",
    "get_market_regime",
    "DTPActivePosition",
    "DTPPortfolioTracker",
    "calculate_dtp_position_size",
    "DTPEODSignal",
    "DTPPositionState",
    "check_reversal_trigger",
    "evaluate_exit_conditions",
    "evaluate_next_open_execution",
    "generate_eod_signal",
    "is_pullback_active",
    "is_trend_aligned",
    "DTPV1Strategy",
]

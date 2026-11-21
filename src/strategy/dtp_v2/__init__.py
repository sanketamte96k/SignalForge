"""
SignalForge — Phase 32E.1: DTP-V2 Delivery Swing Strategy
=========================================================
File: src/strategy/dtp_v2/__init__.py

Public API for DTP-V2 (Delivery Trend-Pullback V2) swing trading strategy:
  - 2.0x ATR Chandelier trailing stop anchored to Highest High (HH - 2.0 * ATR).
  - Preserved +3.0R profit target.
  - Preserved 10-session maximum holding rule with Phase 32D.6 excursion bypass (MFE >= 1.5R).
  - Preserved entry logic, sizing, indicators, and universe constraints.
"""

from src.strategy.dtp_v2.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV2Config,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import (
    DTPTradeCostSummary,
    calculate_dtp_roundtrip_costs,
    calculate_pending_entry_costs,
)
from src.strategy.dtp_v2.indicators import (
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
from src.strategy.dtp_v2.market_filter import (
    evaluate_breadth_regime,
    evaluate_nifty_regime,
    get_market_regime,
)
from src.strategy.dtp_v2.portfolio_rules import (
    DTPActivePosition,
    DTPPortfolioTracker,
)
from src.strategy.dtp_v2.risk_manager import (
    calculate_dtp_position_size,
)
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    check_reversal_trigger,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
    is_pullback_active,
    is_trend_aligned,
)
from src.strategy.dtp_v2.strategy import (
    DTPV2Strategy,
)

__all__ = [
    "DTPExitReason",
    "DTPRegimeState",
    "DTPV2Config",
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
    "DTPV2Strategy",
]

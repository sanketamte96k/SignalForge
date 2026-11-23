"""
SignalForge — Phase 32I: DTP-V3 Strategy Package
================================================
Package: src/strategy/dtp_v3

Delivery Trend-Pullback V3 (DTP-V3) Swing Trading Strategy.
Incorporates:
  - Choppiness Index (CI <= 60.0) sideways regime filter.
  - Upper-half reversal candle confirmation ((Close - Low) / (High - Low) >= 0.50).
  - 2.0x ATR Chandelier trailing stop anchored to Highest High at +1.5R excursion.
  - +3.0R profit target and 10-session maximum holding duration with excursion bypass.
  - Variable risk configurations: E1 (1.0%), E2 (2.0%), E3 (3.0%).
  - Zero-martingale fixed-fractional integer share sizing.
  - Drawdown protection circuit breaker (15% maximum portfolio drawdown cap).
  - Preserved statutory delivery cost engine (Official ₹307/cr and Stress ₹317/cr).
"""

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)
from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3.indicators import calculate_dtp_indicators, calculate_choppiness_index
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v3.portfolio_rules import DTPActivePosition, DTPPortfolioTracker
from src.strategy.dtp_v3.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)
from src.strategy.dtp_v3.strategy import DTPV3Strategy

__all__ = [
    "DTPExitReason",
    "DTPRegimeState",
    "DTPV3Config",
    "OrderAction",
    "calculate_dtp_roundtrip_costs",
    "calculate_dtp_indicators",
    "calculate_choppiness_index",
    "evaluate_breadth_regime",
    "DTPActivePosition",
    "DTPPortfolioTracker",
    "calculate_dtp_position_size",
    "DTPEODSignal",
    "DTPPositionState",
    "evaluate_exit_conditions",
    "evaluate_next_open_execution",
    "generate_eod_signal",
    "DTPV3Strategy",
]

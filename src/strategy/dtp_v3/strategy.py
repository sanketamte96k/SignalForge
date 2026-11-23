"""
SignalForge — Phase 32I: DTP-V3 Strategy Implementation
=======================================================
File: src/strategy/dtp_v3/strategy.py

Encapsulates DTP-V3 strategy execution, state management, and lifecycle hooks
for delivery swing trading.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v3.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3Config,
    OrderAction,
)
from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3.indicators import calculate_dtp_indicators
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v3.portfolio_rules import DTPPortfolioTracker
from src.strategy.dtp_v3.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)


class DTPV3Strategy:
    """Delivery Trend-Pullback V3 (DTP-V3) Swing Trading Strategy."""

    def __init__(
        self,
        config: Optional[DTPV3Config] = None,
        initial_capital: float = 100000.0,
        use_stress_costs: bool = False,
    ) -> None:
        self.config = config or DTPV3Config()
        self.initial_capital = initial_capital
        self.use_stress_costs = use_stress_costs
        self.portfolio = DTPPortfolioTracker(initial_capital=initial_capital, config=self.config)
        self.positions_state: Dict[str, DTPPositionState] = {}
        self.pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str]]] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.trade_counter = 0

    def compute_indicators(
        self,
        df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Computes causal indicators for a symbol's historical OHLCV data."""
        return calculate_dtp_indicators(df, benchmark_df=benchmark_df, config=self.config)

    def evaluate_regime(
        self,
        universe_dict: Dict[str, pd.DataFrame],
        bar_idx: int = -1,
    ) -> DTPRegimeState:
        """Evaluates universe breadth market regime."""
        return evaluate_breadth_regime(universe_dict, bar_idx=bar_idx, config=self.config)

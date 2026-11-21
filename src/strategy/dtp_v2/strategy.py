"""
SignalForge — Phase 32E.1: DTP-V2 Strategy Orchestrator
=======================================================
File: src/strategy/dtp_v2/strategy.py

Orchestrates the complete lifecycle of DTP-V2 delivery swing trading:
  - Daily EOD signal generation with causal indicator lagging (100% DTP-V1 entry parity).
  - Next-session execution intent with gap-risk filtering.
  - Conservative fixed-fractional risk sizing and 100% cash delivery limits.
  - Deterministic exit evaluation incorporating Phase 32D.6 findings:
      - 2.0x ATR Chandelier trailing stop anchored to Highest High (HH - 2.0 * ATR).
      - Preserved +3.0R profit target.
      - Preserved initial stop-loss behavior.
      - Preserved 10-session maximum holding rule with excursion bypass (MFE >= 1.5R).
  - Exact transaction-cost calculation via src/backtest/indian_delivery_costs.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.strategy.dtp_v2.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV2Config,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import (
    DTPTradeCostSummary,
    calculate_dtp_roundtrip_costs,
)
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators
from src.strategy.dtp_v2.market_filter import get_market_regime
from src.strategy.dtp_v2.portfolio_rules import (
    DTPActivePosition,
    DTPPortfolioTracker,
)
from src.strategy.dtp_v2.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)


class DTPV2Strategy:
    """
    Modular DTP-V2 Strategy implementation incorporating Phase 32D.6 adaptive exit research.
    Completely isolated from DTP-V1.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        config: Optional[DTPV2Config] = None,
        use_stress_cost_profile: bool = False,
    ) -> None:
        self.config = config or DTPV2Config()
        self.use_stress_cost_profile = use_stress_cost_profile
        self.portfolio = DTPPortfolioTracker(initial_capital, self.config)
        self.position_states: Dict[str, DTPPositionState] = {}
        self.pending_signals: Dict[str, DTPEODSignal] = {}
        self.closed_trades: List[DTPTradeCostSummary] = []

    def evaluate_eod(
        self,
        symbol: str,
        df: pd.DataFrame,
        market_regime: DTPRegimeState,
        bar_idx: int = -1,
        signal_date: Optional[date] = None,
    ) -> Optional[DTPEODSignal]:
        """
        Evaluates completed Bar T at market close and stores pending signal if eligible.
        """
        if "ema_fast" not in df.columns:
            df = calculate_dtp_indicators(df, config=self.config)

        # Do not generate duplicate signal if position is already open
        if symbol in self.portfolio.positions:
            return None

        signal = generate_eod_signal(
            symbol=symbol,
            df=df,
            market_regime=market_regime,
            config=self.config,
            bar_idx=bar_idx,
            signal_date=signal_date,
        )

        if signal is not None and signal.action == OrderAction.ENTER_LONG:
            self.pending_signals[symbol] = signal
            return signal

        self.pending_signals.pop(symbol, None)
        return None

    def execute_next_open(
        self,
        symbol: str,
        next_open_price: float,
        next_date: date,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[OrderAction, Optional[DTPActivePosition], str]:
        """
        Executes a pending EOD signal at next session open (T+1 09:15 IST) with gap handling.
        """
        if symbol not in self.pending_signals:
            return OrderAction.NO_ACTION, None, f"No pending signal for {symbol}"

        signal = self.pending_signals.pop(symbol)

        # 1. Gap Handling & Fill Price
        action, fill_price, action_msg = evaluate_next_open_execution(
            signal=signal,
            next_open_price=next_open_price,
            config=self.config,
        )

        if action != OrderAction.ENTER_LONG:
            return action, None, action_msg

        # 2. Position Sizing
        equity = self.portfolio.get_portfolio_equity(current_prices)
        sector = self.config.symbol_sector_map.get(symbol, "General")
        curr_sec_exp = self.portfolio.get_sector_exposure(sector, current_prices)

        shares, sizing_msg = calculate_dtp_position_size(
            equity=equity,
            available_cash=self.portfolio.cash,
            entry_price=fill_price,
            stop_price=signal.initial_stop_price,
            sector=sector,
            current_sector_exposure=curr_sec_exp,
            config=self.config,
        )

        if shares <= 0:
            return OrderAction.NO_ACTION, None, f"Sizing rejected: {sizing_msg}"

        # 3. Portfolio Gate Checks
        can_open, gate_msg = self.portfolio.can_open_position(
            symbol=symbol,
            entry_price=fill_price,
            proposed_shares=shares,
            sector=sector,
            current_prices=current_prices,
        )

        if not can_open:
            return OrderAction.NO_ACTION, None, f"Portfolio gate rejected: {gate_msg}"

        # 4. Open Position & Track State
        order_id = f"DTP_V2_BUY_{symbol}_{next_date.isoformat()}"
        active_pos = self.portfolio.open_position(
            symbol=symbol,
            entry_price=fill_price,
            shares=shares,
            stop_price=signal.initial_stop_price,
            r_distance=signal.r_distance,
            entry_date=next_date,
            order_id=order_id,
            sector=sector,
        )

        self.position_states[symbol] = DTPPositionState(
            symbol=symbol,
            entry_date=next_date,
            entry_price=fill_price,
            quantity=shares,
            initial_stop_price=signal.initial_stop_price,
            current_stop_price=signal.initial_stop_price,
            r_distance=signal.r_distance,
            highest_high=fill_price,
            highest_close=fill_price,
        )

        return OrderAction.ENTER_LONG, active_pos, f"Opened {shares} shares at ₹{fill_price:.2f}"

    def evaluate_position_exits(
        self,
        symbol: str,
        current_bar: pd.Series,
        current_date: date,
    ) -> Tuple[Optional[DTPExitReason], Optional[DTPTradeCostSummary], str]:
        """
        Evaluates exit conditions for an active position during or at the end of a session.
        If an exit condition is met, computes delivery transaction costs and settles the trade.
        """
        if symbol not in self.portfolio.positions or symbol not in self.position_states:
            return None, None, f"No active position for {symbol}"

        active_pos = self.portfolio.positions[symbol]
        pos_state = self.position_states[symbol]

        high = float(current_bar["high"])
        low = float(current_bar["low"])
        close = float(current_bar["close"])
        open_px = float(current_bar["open"])
        atr = float(current_bar.get("atr", 1.0))
        ema50 = float(current_bar.get("ema_slow", close))
        rsi = float(current_bar.get("rsi", 50.0))
        bb_upper = float(current_bar.get("bb_upper", close * 1.10))

        exit_reason, exit_price, reason_msg = evaluate_exit_conditions(
            pos=pos_state,
            current_high=high,
            current_low=low,
            current_close=close,
            current_open=open_px,
            current_atr=atr,
            current_ema50=ema50,
            current_rsi=rsi,
            current_bb_upper=bb_upper,
            config=self.config,
        )

        if exit_reason is None:
            return None, None, reason_msg

        # Compute full delivery transaction costs
        isin = self.config.symbol_isin_map.get(symbol, "DEFAULT_ISIN")
        breakdown, summary = calculate_dtp_roundtrip_costs(
            symbol=symbol,
            isin=isin,
            entry_date=active_pos.entry_date,
            exit_date=current_date,
            entry_price=active_pos.entry_price,
            exit_price=exit_price,
            quantity=active_pos.quantity,
            use_stress_profile=self.use_stress_cost_profile,
            order_id_prefix="DTP_V2",
        )

        net_proceeds = summary.sell_turnover - summary.total_friction_costs
        self.portfolio.close_position(symbol, exit_price, net_proceeds)
        self.position_states.pop(symbol, None)
        self.closed_trades.append(summary)

        return exit_reason, summary, reason_msg

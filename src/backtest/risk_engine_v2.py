"""
SignalForge — Phase 24G.11: Isolated V2 Risk and Exit Engine
============================================================
Document Reference: SF-SPEC-RISK-2026-V2
Parent Specification: research/strategy_evolution_2018/phase24G10_risk_engine_spec/risk_and_exit_engine_specification.md
Acceptance Matrix: research/strategy_evolution_2018/phase24G10_risk_engine_spec/acceptance_test_matrix.md
Unresolved Decisions: research/strategy_evolution_2018/phase24G10_risk_engine_spec/unresolved_decisions_register.md

RESEARCH CANDIDATE ONLY:
This module is an isolated research candidate implementing the Phase 24G.10
risk sizing, active exit, and circuit breaker specifications.
- Does NOT modify frozen SignalForge V1 baseline.
- Does NOT modify active paper trading, live ledgers, or universe registry.
- Simulator engineering only: NOT approved for paper or live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time, timedelta
from enum import Enum
import hashlib
import json
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.backtest.simulator import Position


# ============================================================================
# 1. Enums & Constants
# ============================================================================

class PositionSide(str, Enum):
    """Simulated position direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(str, Enum):
    """Reason code for trade liquidation."""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    MAX_TIME = "MAX_TIME"
    EOD = "EOD"
    REVERSAL = "REVERSAL"
    DAILY_LOSS_HALT = "DAILY_LOSS_HALT"
    COOLDOWN_HALT = "COOLDOWN_HALT"
    PARTITION_PURGE = "PARTITION_PURGE"
    DATA_CORRUPTION = "DATA_CORRUPTION"


class RejectionReason(str, Enum):
    """Reason code for order / signal rejection."""
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    CONSECUTIVE_LOSS_COOLDOWN = "CONSECUTIVE_LOSS_COOLDOWN"
    MORNING_BLACKOUT = "MORNING_BLACKOUT"
    MISSING_DATA_GAP = "MISSING_DATA_GAP"
    INVALID_DATA = "INVALID_DATA"
    BANKRUPTCY = "BANKRUPTCY"
    DAY_ROLLOVER_CANCELLED = "DAY_ROLLOVER_CANCELLED"
    PARTITION_BOUNDARY_PURGED = "PARTITION_BOUNDARY_PURGED"


class CostModelType(str, Enum):
    """Supported transaction cost models."""
    HISTORICAL_BASELINE = "historical_baseline"
    REALISTIC_INTRADAY = "realistic_intraday"


# ============================================================================
# 2. Transaction Friction Modeling
# ============================================================================

@dataclass(frozen=True)
class CostBreakdown:
    """Detailed fee and friction accounting for a completed trade."""
    turnover: float
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    gst: float = 0.0
    slippage: float = 0.0
    total_costs: float = 0.0


def calculate_transaction_costs(
    side: PositionSide | str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    entry_time: pd.Timestamp | None = None,
    exit_time: pd.Timestamp | None = None,
    cost_model: CostModelType | str = CostModelType.HISTORICAL_BASELINE,
    slippage_per_share: float = 0.0,
) -> CostBreakdown:
    """
    Compute transaction costs according to Section 2.9 of SF-SPEC-RISK-2026-V2.

    Model 1: Historical Research Baseline
      - Flat 1 basis point (0.0001) on total turnover.
    Model 2: Production Indian Equity Intraday Friction Model
      - Brokerage: min(Rs 20, 0.05% turnover) per executed leg (entry & exit).
      - STT: 0.025% on Sell leg turnover only.
      - NSE Turnover Charge: 0.00297% on total turnover.
      - SEBI Turnover Charges: 0.0001% on total turnover.
      - Stamp Duty: 0.003% on Buy leg turnover only.
      - GST: 18% on (Brokerage + NSE + SEBI).
      - Slippage: 1 tick (Rs 0.05) or 2 bps normal / 5 bps morning (09:15-09:30).
    """
    if isinstance(side, str):
        side = PositionSide(side.upper())
    if isinstance(cost_model, str):
        cost_model = CostModelType(cost_model.lower())

    entry_turnover = entry_price * quantity
    exit_turnover = exit_price * quantity
    total_turnover = entry_turnover + exit_turnover

    if cost_model == CostModelType.HISTORICAL_BASELINE:
        flat_cost = total_turnover * 0.0001
        explicit_slippage = 2 * slippage_per_share * quantity if slippage_per_share > 0 else 0.0
        total = round(flat_cost + explicit_slippage, 4)
        return CostBreakdown(
            turnover=round(total_turnover, 2),
            brokerage=0.0,
            stt=0.0,
            exchange_charges=0.0,
            sebi_charges=0.0,
            stamp_duty=0.0,
            gst=0.0,
            slippage=round(explicit_slippage, 4),
            total_costs=total,
        )

    # Production Indian Equity Intraday Model
    entry_brokerage = min(20.0, entry_turnover * 0.0005)
    exit_brokerage = min(20.0, exit_turnover * 0.0005)
    total_brokerage = entry_brokerage + exit_brokerage

    # STT: 0.025% on Sell side only
    sell_turnover = exit_turnover if side == PositionSide.LONG else entry_turnover
    stt = sell_turnover * 0.00025

    # Exchange & SEBI charges on total turnover
    nse_charges = total_turnover * 0.0000297
    sebi_charges = total_turnover * 0.000001

    # Stamp Duty: 0.003% on Buy side only
    buy_turnover = entry_turnover if side == PositionSide.LONG else exit_turnover
    stamp_duty = buy_turnover * 0.00003

    # GST: 18% on (Brokerage + Exchange + SEBI)
    gst = 0.18 * (total_brokerage + nse_charges + sebi_charges)

    # Slippage: Check if morning window (09:15 to 09:30)
    morning_cutoff = time(9, 30)
    morning_entry = entry_time is not None and entry_time.time() <= morning_cutoff
    entry_slip_rate = 0.0005 if morning_entry else 0.0002
    exit_slip_rate = 0.0002

    if slippage_per_share > 0:
        total_slippage = 2 * slippage_per_share * quantity
    else:
        slip_entry = max(entry_turnover * entry_slip_rate, 0.05 * quantity)
        slip_exit = max(exit_turnover * exit_slip_rate, 0.05 * quantity)
        total_slippage = slip_entry + slip_exit

    statutory_fees = stt + nse_charges + sebi_charges + stamp_duty + gst
    total = total_brokerage + statutory_fees + total_slippage

    return CostBreakdown(
        turnover=round(total_turnover, 2),
        brokerage=round(total_brokerage, 4),
        stt=round(stt, 4),
        exchange_charges=round(nse_charges, 4),
        sebi_charges=round(sebi_charges, 4),
        stamp_duty=round(stamp_duty, 4),
        gst=round(gst, 4),
        slippage=round(total_slippage, 4),
        total_costs=round(total, 4),
    )


# ============================================================================
# 3. Position Sizing & Stop Distance Calculations
# ============================================================================

def calculate_position_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_distance: float,
    max_leverage: float = 5.0,
) -> int:
    """
    Calculate risk-bounded, leverage-capped executable order quantity.
    Equations from SF-SPEC-RISK-2026-V2 Section 2.1:
      R_trade = C * r
      Q_risk = floor(R_trade / D_stop)
      Q_leverage = floor((C * L_max) / P_entry)
      Q = min(Q_risk, Q_leverage)
      If Q < 1: trade must be rejected.
    """
    if not (
        math.isfinite(capital)
        and math.isfinite(risk_pct)
        and math.isfinite(entry_price)
        and math.isfinite(stop_distance)
        and math.isfinite(max_leverage)
    ):
        return 0
    if capital <= 0 or risk_pct <= 0 or entry_price <= 0 or stop_distance <= 0 or max_leverage <= 0:
        return 0

    risk_budget = capital * risk_pct
    q_risk = math.floor(risk_budget / stop_distance)
    q_leverage = math.floor((capital * max_leverage) / entry_price)
    return max(0, min(q_risk, q_leverage))


def calculate_clamped_stop_distance(
    entry_price: float,
    atr: float,
    k_stop: float,
    tick_size: float = 0.05,
    min_stop_pct: float = 0.0020,
) -> float:
    """
    Compute stop distance clamped to at least 1 tick or 0.20% of entry price.
    Prevents division-by-zero or oversized allocations on compressed candles.
    """
    if not (math.isfinite(entry_price) and math.isfinite(atr) and math.isfinite(k_stop)):
        return 0.0
    if atr <= 0 or k_stop <= 0 or entry_price <= 0:
        return 0.0
    raw_dist = atr * k_stop
    min_dist = max(tick_size, entry_price * min_stop_pct)
    return round(max(raw_dist, min_dist), 4)


# ============================================================================
# 4. Trailing Stop Ratchet Engine
# ============================================================================

class TrailingStopRatchet:
    """
    Maintains a strictly monotonic trailing stop ratchet.
    Guarantees:
      - Long: P_stop(t+1) >= P_stop(t) (cannot loosen on pullbacks).
      - Short: P_stop(t+1) <= P_stop(t) (cannot loosen on rallies).
      - Activation condition: activates only after unrealized gain >= activation_r * D_stop.
    """

    def __init__(
        self,
        side: PositionSide | str,
        initial_stop: float,
        trail_distance: float,
        entry_price: float,
        stop_distance: float,
        activation_r: float = 1.0,
    ) -> None:
        self.side = PositionSide(side.upper()) if isinstance(side, str) else side
        self.initial_stop = initial_stop
        self.current_stop = initial_stop
        self.trail_distance = trail_distance
        self.entry_price = entry_price
        self.stop_distance = stop_distance
        self.activation_r = activation_r

        self.extreme_favorable = -float("inf") if self.side == PositionSide.LONG else float("inf")
        self.is_activated = activation_r <= 0.0  # Immediately active if activation_r <= 0

    def update(self, candle_high: float, candle_low: float) -> float:
        """Update trailing stop using the candle's extreme price."""
        if self.side == PositionSide.LONG:
            if candle_high > self.extreme_favorable:
                self.extreme_favorable = candle_high

            # Check activation threshold
            if not self.is_activated and self.stop_distance > 0:
                required_move = self.entry_price + (self.activation_r * self.stop_distance)
                if self.extreme_favorable >= required_move:
                    self.is_activated = True

            if self.is_activated:
                candidate = round(self.extreme_favorable - self.trail_distance, 2)
                if candidate > self.current_stop:
                    self.current_stop = candidate

        elif self.side == PositionSide.SHORT:
            if candle_low < self.extreme_favorable:
                self.extreme_favorable = candle_low

            if not self.is_activated and self.stop_distance > 0:
                required_move = self.entry_price - (self.activation_r * self.stop_distance)
                if self.extreme_favorable <= required_move:
                    self.is_activated = True

            if self.is_activated:
                candidate = round(self.extreme_favorable + self.trail_distance, 2)
                if candidate < self.current_stop:
                    self.current_stop = candidate

        return self.current_stop


# ============================================================================
# 5. Configuration & Governance Dataclass
# ============================================================================

@dataclass(frozen=True)
class RiskEngineConfigV2:
    """
    Configuration for Isolated V2 Risk and Exit Engine.

    Unresolved parameters from SF-REG-DECISIONS-2026-V2 must be pre-registered
    or clearly flagged as a test fixture.
    """
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01
    max_leverage: float = 5.0

    # ATR Multipliers
    k_stop: float = 1.5
    k_target: Optional[float] = 3.0
    k_trail: Optional[float] = None
    trail_activation_r: float = 1.0

    # Exits and Blackout
    max_holding_bars: Optional[int] = None
    morning_blackout_end: Optional[str] = None  # e.g., "09:30:00"
    session_end_time: str = "15:29:00"

    # Circuit Breakers
    daily_loss_limit_pct: float = 0.02
    consecutive_loss_limit: int = 3
    cooldown_minutes: int = 60

    # Execution and Cost Parameters
    execution_model: str = "next_open"  # "next_open" or "same_close"
    cost_model: CostModelType = CostModelType.HISTORICAL_BASELINE
    slippage: float = 0.0
    tick_size: float = 0.05
    min_stop_pct: float = 0.0020
    conservative_collision_rule: str = "stop_first"

    # Governance Pre-Registration Flags
    is_pre_registered: bool = False
    is_test_fixture: bool = False
    registration_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be > 0.")
        if not (0.0 < self.risk_per_trade <= 0.02):
            raise ValueError("risk_per_trade must be in range (0.0, 0.02].")
        if not (0.0 < self.max_leverage <= 5.0):
            raise ValueError("max_leverage must be in range (0.0, 5.0].")
        if self.k_stop <= 0:
            raise ValueError("k_stop must be > 0.")
        if self.k_target is not None and self.k_target < self.k_stop:
            raise ValueError(f"k_target ({self.k_target}) must be >= k_stop ({self.k_stop}) to ensure reward/risk >= 1.0.")
        if self.conservative_collision_rule != "stop_first":
            raise ValueError("DEC-08 frozen specification: conservative_collision_rule must be 'stop_first'.")
        if self.execution_model not in ("next_open", "same_close"):
            raise ValueError(f"Unsupported execution_model: {self.execution_model}.")

    @classmethod
    def test_fixture(cls, **kwargs) -> RiskEngineConfigV2:
        """Create a configuration explicitly marked as a test fixture."""
        kwargs["is_test_fixture"] = True
        return cls(**kwargs)

    @classmethod
    def pre_registered(cls, registration_id: str, **kwargs) -> RiskEngineConfigV2:
        """Create an explicitly pre-registered research candidate configuration."""
        kwargs["is_pre_registered"] = True
        kwargs["registration_id"] = registration_id
        return cls(**kwargs)


# ============================================================================
# 6. Completed Trade & Engine Result Structures
# ============================================================================

@dataclass(frozen=True)
class V2Trade:
    """Record of a completed trade executed by RiskEngineV2."""
    trade_id: int
    side: PositionSide
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    initial_stop: float
    final_stop: float
    target_price: Optional[float]
    quantity: int
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    return_pct: float
    exit_reason: str
    bars_held: int
    stop_distance: float
    risk_budget: float
    r_multiple: float
    capital_before: float
    capital_after: float
    cost_breakdown: CostBreakdown

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "side": self.side.value,
            "entry_time": str(self.entry_time),
            "exit_time": str(self.exit_time),
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "initial_stop": round(self.initial_stop, 4),
            "final_stop": round(self.final_stop, 4),
            "target_price": round(self.target_price, 4) if self.target_price is not None else None,
            "quantity": self.quantity,
            "gross_pnl": round(self.gross_pnl, 4),
            "transaction_cost": round(self.transaction_cost, 4),
            "net_pnl": round(self.net_pnl, 4),
            "return_pct": round(self.return_pct, 4),
            "exit_reason": self.exit_reason,
            "bars_held": self.bars_held,
            "stop_distance": round(self.stop_distance, 4),
            "risk_budget": round(self.risk_budget, 4),
            "r_multiple": round(self.r_multiple, 4),
            "capital_before": round(self.capital_before, 4),
            "capital_after": round(self.capital_after, 4),
        }


@dataclass(frozen=True)
class RiskEngineV2Result:
    """Complete results, performance metrics, and audit logs from a V2 run."""
    trades: tuple[V2Trade, ...]
    initial_capital: float
    final_capital: float
    net_pnl: float
    gross_pnl: float
    total_transaction_costs: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    audit_rejections: tuple[dict, ...]
    circuit_breaker_tripped: bool
    bankruptcy_reason: Optional[str]
    trade_log_hash: str


# ============================================================================
# 7. Isolated V2 Risk Engine Core
# ============================================================================

class RiskEngineV2:
    """
    Isolated V2 Risk and Exit Engine Simulator.

    Implements:
      - Causal next-open execution.
      - ATR-based initial stop and position sizing clamped to risk and leverage.
      - Optional take-profit and monotonic trailing-stop ratchet.
      - Maximum holding duration and mandatory 15:29 EOD square-off.
      - Daily loss circuit breaker and consecutive-loss cooldown.
      - Gap-through-stop and conservative stop-first collision resolution.
      - Session rollover order cancellation and partition boundary purges.
      - Missing data gap rejection, invalid price data rejection, bankruptcy protection.
      - Historical-baseline vs realistic Indian equity intraday transaction friction.
    """

    def __init__(self, config: RiskEngineConfigV2) -> None:
        self.config = config
        self._session_end_time = pd.Timestamp(config.session_end_time).time()
        self._morning_blackout_end = (
            pd.Timestamp(config.morning_blackout_end).time()
            if config.morning_blackout_end is not None
            else None
        )

    def run(
        self,
        data: pd.DataFrame,
        signals: Union[Callable[[pd.Series, pd.Series], Optional[Position | str]], pd.Series, np.ndarray, list],
    ) -> RiskEngineV2Result:
        """Run the isolated V2 simulator across historical candle data."""
        df = self._validate_and_prepare_data(data)

        capital = float(self.config.initial_capital)
        trades: list[V2Trade] = []
        audit_rejections: list[dict] = []

        # Engine State Variables
        active_position: Optional[dict] = None
        pending_order: Optional[dict] = None
        ratchet: Optional[TrailingStopRatchet] = None

        current_day_date = None
        day_start_capital = capital
        day_realized_pnl = 0.0
        day_halted = False
        consecutive_losses = 0
        cooldown_until: Optional[pd.Timestamp] = None
        circuit_breaker_tripped = False
        bankruptcy_reason: Optional[str] = None

        # Pre-extract numpy arrays for fast, deterministic evaluation
        n_bars = len(df)
        datetimes = df.index.to_pydatetime()
        opens = df["Open"].to_numpy(dtype=float)
        highs = df["High"].to_numpy(dtype=float)
        lows = df["Low"].to_numpy(dtype=float)
        closes = df["Close"].to_numpy(dtype=float)
        atrs = df["ATR"].to_numpy(dtype=float)

        trade_counter = 0

        # Helper to extract signal for bar i
        def get_signal_at_bar(bar_idx: int) -> Optional[PositionSide]:
            if isinstance(signals, (pd.Series, np.ndarray, list)):
                sig_val = signals[bar_idx]
            else:
                prev_row = df.iloc[bar_idx - 1] if bar_idx > 0 else df.iloc[0]
                sig_val = signals(df.iloc[bar_idx], prev_row)

            if sig_val is None or pd.isna(sig_val):
                return None
            if isinstance(sig_val, Position):
                return PositionSide(sig_val.value)
            if isinstance(sig_val, PositionSide):
                return sig_val
            if isinstance(sig_val, str):
                val_upper = sig_val.upper()
                if val_upper in ("LONG", "BUY", "1"):
                    return PositionSide.LONG
                elif val_upper in ("SHORT", "SELL", "-1"):
                    return PositionSide.SHORT
            return None

        # --------------------------------------------------------------------
        # Main Bar-by-Bar Simulation Loop
        # --------------------------------------------------------------------
        for i in range(n_bars):
            cur_time = pd.Timestamp(datetimes[i])
            cur_date = cur_time.date()
            cur_bar_open = opens[i]
            cur_bar_high = highs[i]
            cur_bar_low = lows[i]
            cur_bar_close = closes[i]
            cur_atr = atrs[i]

            prev_time = pd.Timestamp(datetimes[i - 1]) if i > 0 else cur_time

            # ----------------------------------------------------------------
            # Step 1: Session Rollover & Day Reset
            # ----------------------------------------------------------------
            if current_day_date != cur_date:
                # Force close overnight carryover if any existed (Mandatory zero overnight carry)
                if active_position is not None:
                    exit_p = float(closes[i - 1])
                    t = self._execute_exit(
                        trade_id=trade_counter + 1,
                        position=active_position,
                        exit_price=exit_p,
                        exit_time=prev_time,
                        exit_reason=ExitReason.EOD.value,
                        capital_before=capital,
                    )
                    trade_counter += 1
                    capital += t.net_pnl
                    day_realized_pnl += t.net_pnl
                    trades.append(t)
                    active_position = None
                    ratchet = None

                # Cancel any pending entry order from previous session
                if pending_order is not None:
                    audit_rejections.append({
                        "time": cur_time,
                        "reason": RejectionReason.DAY_ROLLOVER_CANCELLED.value,
                        "details": f"Pending order from {pending_order['queued_time']} cancelled at session rollover."
                    })
                    pending_order = None

                # Reset intraday state for new calendar day
                current_day_date = cur_date
                day_start_capital = capital
                day_realized_pnl = 0.0
                day_halted = False
                consecutive_losses = 0
                cooldown_until = None

            # ----------------------------------------------------------------
            # Step 2: Missing Data Discontinuity Check
            # ----------------------------------------------------------------
            if i > 0 and cur_date == prev_time.date():
                time_delta_min = (cur_time - prev_time).total_seconds() / 60.0
                if time_delta_min > 1.0 and time(9, 15) <= cur_time.time() <= time(15, 30):
                    if pending_order is not None:
                        audit_rejections.append({
                            "time": cur_time,
                            "reason": RejectionReason.MISSING_DATA_GAP.value,
                            "details": f"Missing data gap of {time_delta_min:.1f}m detected ({prev_time} to {cur_time}). Pending order cancelled."
                        })
                        pending_order = None

            # ----------------------------------------------------------------
            # Step 3: Check Bankruptcy Protection
            # ----------------------------------------------------------------
            if capital <= 0.0:
                bankruptcy_reason = f"BANKRUPTCY: Capital dropped to {capital:.2f} at {cur_time}"
                break

            # ----------------------------------------------------------------
            # Step 4: Execute Pending Next-Open Order (At Bar Open)
            # ----------------------------------------------------------------
            just_entered = False
            if self.config.execution_model == "next_open" and pending_order is not None:
                # Handle Reversal: if in open position, liquidate it at Bar Open first
                if pending_order.get("is_reversal") and active_position is not None:
                    exit_p = (
                        cur_bar_open - self.config.slippage
                        if active_position["side"] == PositionSide.LONG
                        else cur_bar_open + self.config.slippage
                    )
                    t = self._execute_exit(
                        trade_id=trade_counter + 1,
                        position=active_position,
                        exit_price=exit_p,
                        exit_time=cur_time,
                        exit_reason=ExitReason.REVERSAL.value,
                        capital_before=capital,
                    )
                    trade_counter += 1
                    capital += t.net_pnl
                    day_realized_pnl += t.net_pnl
                    trades.append(t)
                    active_position = None
                    ratchet = None

                    # Check consecutive loss streak
                    if t.net_pnl < 0:
                        consecutive_losses += 1
                        if consecutive_losses >= self.config.consecutive_loss_limit:
                            cooldown_until = cur_time + timedelta(minutes=self.config.cooldown_minutes)
                    elif t.net_pnl > 0:
                        consecutive_losses = 0

                    # Check Daily Loss Circuit Breaker
                    max_allowed_loss = day_start_capital * self.config.daily_loss_limit_pct
                    if day_realized_pnl <= -max_allowed_loss:
                        day_halted = True
                        circuit_breaker_tripped = True

                # Check Circuit Breakers & Filters before filling
                is_blackout = (
                    self._morning_blackout_end is not None
                    and cur_time.time() < self._morning_blackout_end
                )
                is_cooldown = cooldown_until is not None and cur_time < cooldown_until

                if day_halted:
                    audit_rejections.append({
                        "time": cur_time,
                        "reason": RejectionReason.DAILY_LOSS_LIMIT.value,
                        "details": "Daily loss circuit breaker active. Pending order rejected."
                    })
                    pending_order = None
                elif is_cooldown:
                    audit_rejections.append({
                        "time": cur_time,
                        "reason": RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value,
                        "details": f"Consecutive loss cooldown active until {cooldown_until}. Pending order rejected."
                    })
                    pending_order = None
                elif is_blackout:
                    audit_rejections.append({
                        "time": cur_time,
                        "reason": RejectionReason.MORNING_BLACKOUT.value,
                        "details": f"Morning entry blackout active until {self._morning_blackout_end}. Order rejected."
                    })
                    pending_order = None
                elif capital <= 0.0:
                    bankruptcy_reason = f"BANKRUPTCY: Capital dropped to {capital:.2f} at {cur_time}"
                    pending_order = None
                    break
                else:
                    # Execute fill at Bar Open
                    ord_side = pending_order["side"]
                    fill_p = (
                        cur_bar_open + self.config.slippage
                        if ord_side == PositionSide.LONG
                        else cur_bar_open - self.config.slippage
                    )
                    order_atr = pending_order["atr"]

                    stop_dist = calculate_clamped_stop_distance(
                        entry_price=fill_p,
                        atr=order_atr,
                        k_stop=self.config.k_stop,
                        tick_size=self.config.tick_size,
                        min_stop_pct=self.config.min_stop_pct,
                    )
                    qty = calculate_position_size(
                        capital=capital,
                        risk_pct=self.config.risk_per_trade,
                        entry_price=fill_p,
                        stop_distance=stop_dist,
                        max_leverage=self.config.max_leverage,
                    )

                    if qty < 1:
                        audit_rejections.append({
                            "time": cur_time,
                            "reason": RejectionReason.INSUFFICIENT_CAPITAL.value,
                            "details": f"Insufficient capital (C={capital:.2f}, StopDist={stop_dist:.2f}) to afford 1 unit."
                        })
                    else:
                        stop_p = (
                            round(fill_p - stop_dist, 2)
                            if ord_side == PositionSide.LONG
                            else round(fill_p + stop_dist, 2)
                        )
                        tgt_p = None
                        if self.config.k_target is not None:
                            tgt_p = (
                                round(fill_p + (self.config.k_target * order_atr), 2)
                                if ord_side == PositionSide.LONG
                                else round(fill_p - (self.config.k_target * order_atr), 2)
                            )

                        active_position = {
                            "side": ord_side,
                            "entry_time": cur_time,
                            "entry_price": fill_p,
                            "initial_stop": stop_p,
                            "current_stop": stop_p,
                            "target_price": tgt_p,
                            "quantity": qty,
                            "atr": order_atr,
                            "stop_distance": stop_dist,
                            "risk_budget": capital * self.config.risk_per_trade,
                            "bars_held": 0,
                            "capital_at_entry": capital,
                        }
                        just_entered = True
                        if self.config.k_trail is not None:
                            ratchet = TrailingStopRatchet(
                                side=ord_side,
                                initial_stop=stop_p,
                                trail_distance=self.config.k_trail * order_atr,
                                entry_price=fill_p,
                                stop_distance=stop_dist,
                                activation_r=self.config.trail_activation_r,
                            )
                        else:
                            ratchet = None

                    pending_order = None

            # ----------------------------------------------------------------
            # Step 5: Active Position Management (Exits & Stops on Bar i)
            # ----------------------------------------------------------------
            if active_position is not None:
                if not just_entered:
                    active_position["bars_held"] += 1
                pos_side = active_position["side"]
                entry_p = active_position["entry_price"]
                cur_stop = active_position["current_stop"]
                tgt_p = active_position["target_price"]
                bars_held = active_position["bars_held"]

                exit_triggered = False
                exit_fill_price = 0.0
                exit_reason = ""

                # A. Maximum Holding Duration Exit
                if (
                    self.config.max_holding_bars is not None
                    and not just_entered
                    and bars_held > self.config.max_holding_bars
                ):
                    exit_fill_price = (
                        cur_bar_open - self.config.slippage
                        if pos_side == PositionSide.LONG
                        else cur_bar_open + self.config.slippage
                    )
                    exit_reason = ExitReason.MAX_TIME.value
                    exit_triggered = True

                # B. Opening Gap Check at Bar Open (uses stop from previous bar close)
                stop_at_open = cur_stop
                if not exit_triggered and not just_entered:
                    if pos_side == PositionSide.LONG:
                        if cur_bar_open < stop_at_open:
                            exit_fill_price = cur_bar_open - self.config.slippage
                            exit_reason = ExitReason.STOP_LOSS.value
                            exit_triggered = True
                        elif tgt_p is not None and cur_bar_open > tgt_p:
                            exit_fill_price = cur_bar_open - self.config.slippage
                            exit_reason = ExitReason.TAKE_PROFIT.value
                            exit_triggered = True
                    elif pos_side == PositionSide.SHORT:
                        if cur_bar_open > stop_at_open:
                            exit_fill_price = cur_bar_open + self.config.slippage
                            exit_reason = ExitReason.STOP_LOSS.value
                            exit_triggered = True
                        elif tgt_p is not None and cur_bar_open < tgt_p:
                            exit_fill_price = cur_bar_open + self.config.slippage
                            exit_reason = ExitReason.TAKE_PROFIT.value
                            exit_triggered = True

                # C. Intrabar Stop Evaluation against Pre-Existing Stop
                # Under conservative stop-first precedence (DEC-09), if the bar's extreme breaches
                # the stop active at the start of the bar, it must exit at that stop price.
                # The trailing ratchet cannot use the bar's favorable extreme to erase a stop hit.
                stop_before_bar = cur_stop
                if not exit_triggered:
                    if pos_side == PositionSide.LONG:
                        # Same-Candle Collision or Stop Hit against pre-existing stop
                        if cur_bar_low <= stop_before_bar:
                            exit_fill_price = stop_before_bar - self.config.slippage
                            exit_reason = (
                                ExitReason.TRAILING_STOP.value
                                if stop_before_bar > active_position["initial_stop"]
                                else ExitReason.STOP_LOSS.value
                            )
                            exit_triggered = True
                        elif tgt_p is not None and cur_bar_high >= tgt_p:
                            exit_fill_price = tgt_p - self.config.slippage
                            exit_reason = ExitReason.TAKE_PROFIT.value
                            exit_triggered = True

                    elif pos_side == PositionSide.SHORT:
                        # Same-Candle Collision or Stop Hit against pre-existing stop
                        if cur_bar_high >= stop_before_bar:
                            exit_fill_price = stop_before_bar + self.config.slippage
                            exit_reason = (
                                ExitReason.TRAILING_STOP.value
                                if stop_before_bar < active_position["initial_stop"]
                                else ExitReason.STOP_LOSS.value
                            )
                            exit_triggered = True
                        elif tgt_p is not None and cur_bar_low <= tgt_p:
                            exit_fill_price = tgt_p + self.config.slippage
                            exit_reason = ExitReason.TAKE_PROFIT.value
                            exit_triggered = True

                # D. Trailing Ratchet Update (Intrabar progression if stop/target not hit)
                if not exit_triggered and ratchet is not None:
                    cur_stop = ratchet.update(candle_high=cur_bar_high, candle_low=cur_bar_low)
                    active_position["current_stop"] = cur_stop

                # D. Mandatory EOD Liquidation at Session End (15:29:00 close)
                if not exit_triggered and cur_time.time() >= self._session_end_time:
                    exit_fill_price = (
                        cur_bar_close - self.config.slippage
                        if pos_side == PositionSide.LONG
                        else cur_bar_close + self.config.slippage
                    )
                    exit_reason = ExitReason.EOD.value
                    exit_triggered = True

                # E. Execute Exit if triggered
                if exit_triggered:
                    t = self._execute_exit(
                        trade_id=trade_counter + 1,
                        position=active_position,
                        exit_price=exit_fill_price,
                        exit_time=cur_time,
                        exit_reason=exit_reason,
                        capital_before=capital,
                    )
                    trade_counter += 1
                    capital += t.net_pnl
                    day_realized_pnl += t.net_pnl
                    trades.append(t)
                    active_position = None
                    ratchet = None

                    # Check losing streak cooldown
                    if t.net_pnl < 0:
                        consecutive_losses += 1
                        if consecutive_losses >= self.config.consecutive_loss_limit:
                            cooldown_until = cur_time + timedelta(minutes=self.config.cooldown_minutes)
                    elif t.net_pnl > 0:
                        consecutive_losses = 0

                    # Check Daily Loss Circuit Breaker
                    max_allowed_loss = day_start_capital * self.config.daily_loss_limit_pct
                    if day_realized_pnl <= -max_allowed_loss:
                        day_halted = True
                        circuit_breaker_tripped = True

                # F. Check Running Unrealized P&L Daily Circuit Breaker while in trade
                elif active_position is not None:
                    cur_qty = active_position["quantity"]
                    cur_unrealized_gross = (
                        (cur_bar_close - entry_p) * cur_qty
                        if pos_side == PositionSide.LONG
                        else (entry_p - cur_bar_close) * cur_qty
                    )
                    total_day_pnl = day_realized_pnl + cur_unrealized_gross
                    max_allowed_loss = day_start_capital * self.config.daily_loss_limit_pct

                    if total_day_pnl <= -max_allowed_loss:
                        # Liquidate immediately at market close
                        exit_fill_p = (
                            cur_bar_close - self.config.slippage
                            if pos_side == PositionSide.LONG
                            else cur_bar_close + self.config.slippage
                        )
                        t = self._execute_exit(
                            trade_id=trade_counter + 1,
                            position=active_position,
                            exit_price=exit_fill_p,
                            exit_time=cur_time,
                            exit_reason=ExitReason.DAILY_LOSS_HALT.value,
                            capital_before=capital,
                        )
                        trade_counter += 1
                        capital += t.net_pnl
                        day_realized_pnl += t.net_pnl
                        trades.append(t)
                        active_position = None
                        ratchet = None
                        day_halted = True
                        circuit_breaker_tripped = True

            # ----------------------------------------------------------------
            # Step 6: Process Strategy Signals at Bar Close
            # ----------------------------------------------------------------
            if cur_time.time() <= self._session_end_time and capital > 0:
                sig = get_signal_at_bar(i)
                if sig is not None:
                    if day_halted:
                        audit_rejections.append({
                            "time": cur_time,
                            "reason": RejectionReason.DAILY_LOSS_LIMIT.value,
                            "details": "Daily loss circuit breaker active. Signal rejected."
                        })
                    else:
                        # Check Morning Blackout
                        is_blackout = (
                            self._morning_blackout_end is not None
                            and cur_time.time() < self._morning_blackout_end
                        )
                        # Check Cooldown
                        is_cooldown = cooldown_until is not None and cur_time < cooldown_until

                        if is_cooldown:
                            audit_rejections.append({
                                "time": cur_time,
                                "reason": RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value,
                                "details": f"Consecutive loss cooldown active until {cooldown_until}. Signal rejected."
                            })
                        elif is_blackout:
                            audit_rejections.append({
                                "time": cur_time,
                                "reason": RejectionReason.MORNING_BLACKOUT.value,
                                "details": f"Morning entry blackout active until {self._morning_blackout_end}. Signal rejected."
                            })
                        else:
                            # Handle existing position vs new signal
                            if active_position is not None:
                                if sig != active_position["side"]:
                                    # Reversal signal
                                    if self.config.execution_model == "same_close":
                                        # Close existing at close, enter new at close
                                        exit_p = (
                                            cur_bar_close - self.config.slippage
                                            if active_position["side"] == PositionSide.LONG
                                            else cur_bar_close + self.config.slippage
                                        )
                                        t = self._execute_exit(
                                            trade_id=trade_counter + 1,
                                            position=active_position,
                                            exit_price=exit_p,
                                            exit_time=cur_time,
                                            exit_reason=ExitReason.REVERSAL.value,
                                            capital_before=capital,
                                        )
                                        trade_counter += 1
                                        capital += t.net_pnl
                                        day_realized_pnl += t.net_pnl
                                        trades.append(t)
                                        active_position = None
                                        ratchet = None

                                        # Check consecutive loss streak
                                        if t.net_pnl < 0:
                                            consecutive_losses += 1
                                            if consecutive_losses >= self.config.consecutive_loss_limit:
                                                cooldown_until = cur_time + timedelta(minutes=self.config.cooldown_minutes)
                                        elif t.net_pnl > 0:
                                            consecutive_losses = 0

                                        # Check circuit breaker and cooldown before opening reversal
                                        max_allowed_loss = day_start_capital * self.config.daily_loss_limit_pct
                                        is_cooldown = cooldown_until is not None and cur_time < cooldown_until
                                        if day_realized_pnl <= -max_allowed_loss:
                                            day_halted = True
                                            circuit_breaker_tripped = True
                                        elif is_cooldown:
                                            audit_rejections.append({
                                                "time": cur_time,
                                                "reason": RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value,
                                                "details": f"Consecutive loss cooldown active until {cooldown_until}. Reversal entry rejected."
                                            })
                                        else:
                                            # Open reversal position
                                            active_position, ratchet = self._open_same_close_position(
                                                side=sig,
                                                entry_time=cur_time,
                                                entry_price=cur_bar_close,
                                                atr=cur_atr,
                                                capital=capital,
                                                audit_rejections=audit_rejections,
                                            )
                                    else:
                                        # next_open: Liquidate at next open, queue new position
                                        pending_order = {
                                            "side": sig,
                                            "queued_time": cur_time,
                                            "atr": cur_atr,
                                            "is_reversal": True,
                                        }
                            else:
                                # Position is flat
                                if self.config.execution_model == "next_open":
                                    pending_order = {
                                        "side": sig,
                                        "queued_time": cur_time,
                                        "atr": cur_atr,
                                        "is_reversal": False,
                                    }
                                else:
                                    active_position, ratchet = self._open_same_close_position(
                                        side=sig,
                                        entry_time=cur_time,
                                        entry_price=cur_bar_close,
                                        atr=cur_atr,
                                        capital=capital,
                                        audit_rejections=audit_rejections,
                                    )

        # Step 7: Final Dataset Purge / Close
        if active_position is not None:
            last_time = pd.Timestamp(datetimes[-1])
            pos_side = active_position["side"]
            exit_p = (
                float(closes[-1]) - self.config.slippage
                if pos_side == PositionSide.LONG
                else float(closes[-1]) + self.config.slippage
            )
            t = self._execute_exit(
                trade_id=trade_counter + 1,
                position=active_position,
                exit_price=exit_p,
                exit_time=last_time,
                exit_reason=ExitReason.EOD.value,
                capital_before=capital,
            )
            trade_counter += 1
            capital += t.net_pnl
            trades.append(t)
            active_position = None
            ratchet = None

        # --------------------------------------------------------------------
        # Step 8: Metric Computation & Deterministic Replay Hash
        # --------------------------------------------------------------------
        return self._summarize_results(
            trades=trades,
            initial_capital=self.config.initial_capital,
            final_capital=capital,
            audit_rejections=audit_rejections,
            circuit_breaker_tripped=circuit_breaker_tripped,
            bankruptcy_reason=bankruptcy_reason,
        )

    # ------------------------------------------------------------------------
    # Private Helper Methods
    # ------------------------------------------------------------------------

    def _open_same_close_position(
        self,
        side: PositionSide,
        entry_time: pd.Timestamp,
        entry_price: float,
        atr: float,
        capital: float,
        audit_rejections: list[dict],
    ) -> Tuple[Optional[dict], Optional[TrailingStopRatchet]]:
        """Open a position immediately on candle close (same_close model)."""
        fill_p = (
            entry_price + self.config.slippage
            if side == PositionSide.LONG
            else entry_price - self.config.slippage
        )
        stop_dist = calculate_clamped_stop_distance(
            entry_price=fill_p,
            atr=atr,
            k_stop=self.config.k_stop,
            tick_size=self.config.tick_size,
            min_stop_pct=self.config.min_stop_pct,
        )
        qty = calculate_position_size(
            capital=capital,
            risk_pct=self.config.risk_per_trade,
            entry_price=fill_p,
            stop_distance=stop_dist,
            max_leverage=self.config.max_leverage,
        )
        if qty < 1:
            audit_rejections.append({
                "time": entry_time,
                "reason": RejectionReason.INSUFFICIENT_CAPITAL.value,
                "details": f"Insufficient capital (C={capital:.2f}) to afford 1 unit."
            })
            return None, None

        stop_p = (
            round(fill_p - stop_dist, 2)
            if side == PositionSide.LONG
            else round(fill_p + stop_dist, 2)
        )
        tgt_p = None
        if self.config.k_target is not None:
            tgt_p = (
                round(fill_p + (self.config.k_target * atr), 2)
                if side == PositionSide.LONG
                else round(fill_p - (self.config.k_target * atr), 2)
            )

        pos = {
            "side": side,
            "entry_time": entry_time,
            "entry_price": fill_p,
            "initial_stop": stop_p,
            "current_stop": stop_p,
            "target_price": tgt_p,
            "quantity": qty,
            "atr": atr,
            "stop_distance": stop_dist,
            "risk_budget": capital * self.config.risk_per_trade,
            "bars_held": 0,
            "capital_at_entry": capital,
        }
        ratchet = None
        if self.config.k_trail is not None:
            ratchet = TrailingStopRatchet(
                side=side,
                initial_stop=stop_p,
                trail_distance=self.config.k_trail * atr,
                entry_price=fill_p,
                stop_distance=stop_dist,
                activation_r=self.config.trail_activation_r,
            )
        return pos, ratchet

    def _execute_exit(
        self,
        trade_id: int,
        position: dict,
        exit_price: float,
        exit_time: pd.Timestamp,
        exit_reason: str,
        capital_before: float,
    ) -> V2Trade:
        """Construct completed V2Trade record with exact fee and P&L accounting."""
        side = position["side"]
        entry_p = position["entry_price"]
        qty = position["quantity"]
        entry_t = position["entry_time"]
        stop_dist = position["stop_distance"]
        initial_stop = position["initial_stop"]
        final_stop = position["current_stop"]
        target_p = position["target_price"]
        bars_held = position["bars_held"]
        risk_budget = position["risk_budget"]

        # Gross P&L
        if side == PositionSide.LONG:
            gross_pnl = (exit_price - entry_p) * qty
        else:
            gross_pnl = (entry_p - exit_price) * qty

        # Transaction Friction
        costs = calculate_transaction_costs(
            side=side,
            entry_price=entry_p,
            exit_price=exit_price,
            quantity=qty,
            entry_time=entry_t,
            exit_time=exit_time,
            cost_model=self.config.cost_model,
            slippage_per_share=self.config.slippage,
        )

        # Slippage accounting reconciliation:
        # If execution slippage was already embedded into executed fill prices (self.config.slippage > 0),
        # deducting costs.slippage again would double-count slippage.
        # Only non-price friction (brokerage + statutory fees) is deducted from gross P&L.
        deducted_costs = costs.total_costs - costs.slippage if self.config.slippage > 0 else costs.total_costs
        net_pnl = gross_pnl - deducted_costs
        notional_entry = entry_p * qty
        ret_pct = (net_pnl / notional_entry * 100.0) if notional_entry > 0 else 0.0
        r_mult = (net_pnl / (qty * stop_dist)) if (qty * stop_dist) > 0 else 0.0

        return V2Trade(
            trade_id=trade_id,
            side=side,
            entry_time=entry_t,
            exit_time=exit_time,
            entry_price=round(entry_p, 4),
            exit_price=round(exit_price, 4),
            initial_stop=round(initial_stop, 4),
            final_stop=round(final_stop, 4),
            target_price=round(target_p, 4) if target_p is not None else None,
            quantity=qty,
            gross_pnl=round(gross_pnl, 4),
            transaction_cost=round(deducted_costs, 4),
            net_pnl=round(net_pnl, 4),
            return_pct=round(ret_pct, 4),
            exit_reason=exit_reason,
            bars_held=bars_held,
            stop_distance=round(stop_dist, 4),
            risk_budget=round(risk_budget, 4),
            r_multiple=round(r_mult, 4),
            capital_before=round(capital_before, 4),
            capital_after=round(capital_before + net_pnl, 4),
            cost_breakdown=costs,
        )

    def _validate_and_prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate input DataFrame, enforce OHLC constraints, compute ATR if missing."""
        if not isinstance(data, pd.DataFrame):
            raise TypeError("data must be a pandas DataFrame.")
        if data.empty:
            raise ValueError("data cannot be empty.")

        df = data.copy()

        # Handle Datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp").sort_index()
            elif "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date").sort_index()
            else:
                raise TypeError("DataFrame must have a DatetimeIndex or 'timestamp'/'Date' column.")

        if df.index.has_duplicates:
            raise ValueError("data index cannot contain duplicate timestamps.")
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        col_map = {str(c).lower(): c for c in df.columns}
        for req in ("open", "high", "low", "close"):
            if req not in col_map:
                raise ValueError(f"Missing required price column: {req}")

        df["Open"] = df[col_map["open"]].astype(float)
        df["High"] = df[col_map["high"]].astype(float)
        df["Low"] = df[col_map["low"]].astype(float)
        df["Close"] = df[col_map["close"]].astype(float)

        # Validate price integrity
        for p_col in ("Open", "High", "Low", "Close"):
            if df[p_col].isna().any() or not np.isfinite(df[p_col]).all():
                raise ValueError(f"Data corruption: Non-finite price found in '{p_col}' column.")
        if (df["High"] < df["Low"]).any():
            raise ValueError("Data corruption: High < Low found in input dataset.")
        if (df["Low"] <= 0).any() or (df["Open"] <= 0).any() or (df["Close"] <= 0).any():
            raise ValueError("Data corruption: Non-positive price found in input dataset.")
        if "volume" in col_map and (df[col_map["volume"]] < 0).any():
            raise ValueError("Data corruption: Negative volume found in input dataset.")

        # Compute ATR(14) if missing
        if "atr" in col_map:
            df["ATR"] = df[col_map["atr"]].astype(float)
        elif "atr14" in col_map:
            df["ATR"] = df[col_map["atr14"]].astype(float)
        else:
            prev_close = df["Close"].shift(1)
            tr1 = df["High"] - df["Low"]
            tr2 = (df["High"] - prev_close).abs()
            tr3 = (df["Low"] - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df["ATR"] = tr.rolling(14).mean().bfill()

        return df

    def _summarize_results(
        self,
        trades: list[V2Trade],
        initial_capital: float,
        final_capital: float,
        audit_rejections: list[dict],
        circuit_breaker_tripped: bool,
        bankruptcy_reason: Optional[str],
    ) -> RiskEngineV2Result:
        """Calculate overall backtest performance metrics and canonical SHA-256 hash."""
        total_trades = len(trades)
        winning = [t for t in trades if t.net_pnl > 0]
        losing = [t for t in trades if t.net_pnl < 0]
        breakeven = [t for t in trades if t.net_pnl == 0]

        gross_pnl = sum(t.gross_pnl for t in trades)
        total_costs = sum(t.transaction_cost for t in trades)
        net_pnl = sum(t.net_pnl for t in trades)

        win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(t.net_pnl for t in winning)
        gross_loss = abs(sum(t.net_pnl for t in losing))
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 0.0)
        )

        # Max Drawdown
        equity = initial_capital
        peak = initial_capital
        max_dd_amount = 0.0
        max_dd_pct = 0.0
        consecutive_loss_streak = 0
        max_loss_streak = 0

        for t in trades:
            equity += t.net_pnl
            if equity > peak:
                peak = equity
            dd_amount = peak - equity
            dd_pct = (dd_amount / peak * 100.0) if peak > 0 else 0.0
            if dd_amount > max_dd_amount:
                max_dd_amount = dd_amount
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

            if t.net_pnl < 0:
                consecutive_loss_streak += 1
                if consecutive_loss_streak > max_loss_streak:
                    max_loss_streak = consecutive_loss_streak
            elif t.net_pnl > 0:
                consecutive_loss_streak = 0

        # Canonical SHA-256 hash for deterministic replay validation
        trade_logs_dict = [t.to_dict() for t in trades]
        canonical_json = json.dumps(trade_logs_dict, sort_keys=True)
        trade_hash = hashlib.sha256(canonical_json.encode()).hexdigest()

        return RiskEngineV2Result(
            trades=tuple(trades),
            initial_capital=round(initial_capital, 2),
            final_capital=round(final_capital, 2),
            net_pnl=round(net_pnl, 2),
            gross_pnl=round(gross_pnl, 2),
            total_transaction_costs=round(total_costs, 2),
            win_rate_pct=round(win_rate, 2),
            profit_factor=round(profit_factor, 4) if np.isfinite(profit_factor) else float("inf"),
            max_drawdown_amount=round(max_dd_amount, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            max_consecutive_losses=max_loss_streak,
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            breakeven_trades=len(breakeven),
            audit_rejections=tuple(audit_rejections),
            circuit_breaker_tripped=circuit_breaker_tripped,
            bankruptcy_reason=bankruptcy_reason,
            trade_log_hash=trade_hash,
        )

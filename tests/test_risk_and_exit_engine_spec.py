"""
Unit and Acceptance Tests for SignalForge Risk and Exit Engine Specification (V2).

Validates the mathematical formulas, risk bounds, gap execution rules,
same-candle collision precedence, and trailing ratchet behavior specified
in research/strategy_evolution_2018/phase24G10_risk_engine_spec/.
"""

import math
import pytest


# ============================================================================
# 1. Position Sizing & Capital Allocation
# ============================================================================

def calculate_position_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_distance: float,
    max_leverage: float = 5.0,
) -> int:
    """Calculate risk-bounded, leverage-capped position size."""
    if capital <= 0 or risk_pct <= 0 or entry_price <= 0 or stop_distance <= 0 or max_leverage <= 0:
        return 0

    risk_budget = capital * risk_pct
    q_risk = math.floor(risk_budget / stop_distance)
    q_leverage = math.floor((capital * max_leverage) / entry_price)
    return min(q_risk, q_leverage)


def test_position_sizing_respects_risk_budget():
    """Verify that monetary risk never exceeds the allocated risk budget."""
    capital = 100000.0
    risk_pct = 0.01  # 1% = Rs 1000
    entry_price = 300.0
    stop_distance = 6.0  # 1.5 * ATR(4.0)

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance)
    assert qty == 166

    monetary_risk = qty * stop_distance
    assert monetary_risk <= 1000.0
    assert monetary_risk == 996.0


def test_position_sizing_respects_leverage_cap():
    """Verify that notional exposure never exceeds capital * max_leverage."""
    capital = 10000.0
    risk_pct = 0.01  # Rs 100 budget
    entry_price = 1000.0
    stop_distance = 0.50  # Very tight stop -> q_risk would be 200 units (Rs 200,000 notional = 20x)
    max_leverage = 5.0    # Capped at Rs 50,000 notional -> max 50 units

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance, max_leverage)
    assert qty == 50

    notional_exposure = qty * entry_price
    assert notional_exposure <= capital * max_leverage
    assert notional_exposure == 50000.0


def test_position_sizing_rejects_insufficient_capital():
    """Verify that if capital cannot afford even 1 unit within risk bounds, size is 0."""
    capital = 100.0
    risk_pct = 0.01  # Rs 1.00 budget
    entry_price = 500.0
    stop_distance = 10.0  # q_risk = floor(1 / 10) = 0

    qty = calculate_position_size(capital, risk_pct, entry_price, stop_distance)
    assert qty == 0


# ============================================================================
# 2. Gap-Through-Stop Execution
# ============================================================================

def resolve_stop_exit_price(
    position: str,
    stop_price: float,
    candle_open: float,
    candle_high: float,
    candle_low: float,
    slippage: float = 0.05,
) -> float | None:
    """Resolve exit fill price for a stop loss under intrabar vs opening gap conditions."""
    if position.upper() == "LONG":
        # Check gap-through first
        if candle_open < stop_price:
            return candle_open - slippage
        # Check intrabar penetration
        if candle_low <= stop_price:
            return stop_price - slippage
    elif position.upper() == "SHORT":
        if candle_open > stop_price:
            return candle_open + slippage
        if candle_high >= stop_price:
            return stop_price + slippage
    return None


def test_gap_through_stop_uses_open_price():
    """Verify that an opening gap past the stop fills at Open, NOT at nominal stop."""
    stop_price = 294.00
    candle_open = 288.00  # Gapped down 6 points below stop
    candle_high = 290.00
    candle_low = 286.00

    fill_p = resolve_stop_exit_price("LONG", stop_price, candle_open, candle_high, candle_low, slippage=0.05)
    assert fill_p == 287.95
    assert fill_p < stop_price


def test_normal_intrabar_stop_uses_stop_price():
    """Verify that normal intrabar stop fills at nominal stop price minus slippage."""
    stop_price = 294.00
    candle_open = 297.00
    candle_high = 298.00
    candle_low = 293.00

    fill_p = resolve_stop_exit_price("LONG", stop_price, candle_open, candle_high, candle_low, slippage=0.05)
    assert fill_p == 293.95


# ============================================================================
# 3. Same-Candle Collision Resolution (Conservative Stop-First Precedence)
# ============================================================================

def resolve_collision_candle(
    position: str,
    stop_price: float,
    target_price: float,
    candle_open: float,
    candle_high: float,
    candle_low: float,
) -> tuple[str, float]:
    """
    Evaluate same-candle stop and target touching.
    Conservative rule: Stop-loss is ASSUMED TO TRIGGER FIRST.
    """
    if position.upper() == "LONG":
        stop_hit = candle_low <= stop_price
        target_hit = candle_high >= target_price
        if stop_hit and target_hit:
            exit_p = candle_open - 0.05 if candle_open < stop_price else stop_price - 0.05
            return ("STOP_LOSS", exit_p)
        elif target_hit:
            return ("TAKE_PROFIT", target_price)
        elif stop_hit:
            exit_p = candle_open - 0.05 if candle_open < stop_price else stop_price - 0.05
            return ("STOP_LOSS", exit_p)
    return ("NONE", 0.0)


def test_same_candle_collision_stop_first_precedence():
    """Verify conservative stop-first precedence when single bar hits both Stop and Target."""
    stop_p = 294.00
    target_p = 312.00
    # Wide bar touching both
    candle_open = 305.00
    candle_high = 314.00  # Target hit
    candle_low = 292.00   # Stop hit

    reason, fill_p = resolve_collision_candle("LONG", stop_p, target_p, candle_open, candle_high, candle_low)
    assert reason == "STOP_LOSS"
    assert fill_p == 293.95


# ============================================================================
# 4. Trailing Stop Ratchet Monotonicity
# ============================================================================

class TrailingStopRatchet:
    """Maintains a monotonically ratcheting trailing stop."""

    def __init__(self, position: str, initial_stop: float, trail_distance: float):
        self.position = position.upper()
        self.current_stop = initial_stop
        self.trail_distance = trail_distance
        self.extreme_favorable = -float("inf") if self.position == "LONG" else float("inf")

    def update(self, candle_high: float, candle_low: float) -> float:
        if self.position == "LONG":
            if candle_high > self.extreme_favorable:
                self.extreme_favorable = candle_high
            candidate = self.extreme_favorable - self.trail_distance
            if candidate > self.current_stop:
                self.current_stop = candidate
        elif self.position == "SHORT":
            if candle_low < self.extreme_favorable:
                self.extreme_favorable = candle_low
            candidate = self.extreme_favorable + self.trail_distance
            if candidate < self.current_stop:
                self.current_stop = candidate
        return self.current_stop


def test_trailing_stop_ratchet_monotonicity():
    """Verify trailing stop ratchets up on new highs and never loosens on pullbacks."""
    trail = TrailingStopRatchet("LONG", initial_stop=294.00, trail_distance=6.0)

    # Bar 1: Market rallies to 308
    s1 = trail.update(candle_high=308.0, candle_low=300.0)
    assert s1 == 302.0  # 308 - 6

    # Bar 2: Market pulls back to 304 (High is 305)
    s2 = trail.update(candle_high=305.0, candle_low=301.0)
    assert s2 == 302.0  # Stop CANNOT decrease
    assert s2 >= s1

    # Bar 3: Market breaks out to 316
    s3 = trail.update(candle_high=316.0, candle_low=304.0)
    assert s3 == 310.0  # 316 - 6
    assert s3 > s2


# ============================================================================
# 5. Daily Loss Circuit Breaker
# ============================================================================

def is_daily_circuit_breaker_tripped(
    day_start_capital: float,
    realized_day_pnl: float,
    unrealized_day_pnl: float,
    max_daily_loss_pct: float = 0.02,
) -> bool:
    """Return True if cumulative realized + unrealized loss exceeds daily threshold."""
    total_day_pnl = realized_day_pnl + unrealized_day_pnl
    max_allowed_loss = day_start_capital * max_daily_loss_pct
    return total_day_pnl <= -max_allowed_loss


def test_daily_loss_circuit_breaker_calculation():
    """Verify that daily circuit breaker trips when cumulative loss reaches 2%."""
    day_start = 100000.0
    limit_pct = 0.02  # Rs 2,000 max loss

    # Case A: Realized loss Rs 1,500, no unrealized -> False
    assert not is_daily_circuit_breaker_tripped(day_start, -1500.0, 0.0, limit_pct)

    # Case B: Realized loss Rs 1,500, unrealized loss Rs 600 (total -2,100) -> True
    assert is_daily_circuit_breaker_tripped(day_start, -1500.0, -600.0, limit_pct)

    # Case C: Exact boundary Rs 2,000 loss -> True
    assert is_daily_circuit_breaker_tripped(day_start, -2000.0, 0.0, limit_pct)

"""
SignalForge — Phase 32C.5: DTP-V1 Strategy Configuration & Enums
================================================================
File: src/strategy/dtp_v1/config.py

Defines configuration parameters, enums, and data models for DTP-V1
(Delivery Trend-Pullback V1) in accordance with phase32c_4_dtp_v1_strategy_specification.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class DTPRegimeState(str, Enum):
    """Market regime classification for broader environment."""
    BULLISH = "BULLISH"      # Full capital allocation permitted
    NEUTRAL = "NEUTRAL"      # Scaled allocation / conservative entries
    BEARISH = "BEARISH"      # Strict trading freeze; 100% cash preservation
    UNKNOWN = "UNKNOWN"      # Insufficient data or missing inputs


class DTPExitReason(str, Enum):
    """Exit classification reasons for DTP-V1 delivery positions."""
    INITIAL_STOP = "INITIAL_STOP"            # Structural or ATR-based stop-loss hit
    BREAKEVEN_STOP = "BREAKEVEN_STOP"        # Breakeven stop triggered (+1.0R excursion)
    TRAILING_STOP = "TRAILING_STOP"          # Chandelier trailing stop triggered (+1.5R)
    TREND_BREAKDOWN = "TREND_BREAKDOWN"      # 2 consecutive closes below 50-day EMA
    TIME_LIMIT = "TIME_LIMIT"                # Maximum holding period reached (10 sessions)
    PROFIT_TARGET = "PROFIT_TARGET"          # Full target reached (+3.0R)
    DYNAMIC_OVERBOUGHT = "DYNAMIC_OVERBOUGHT" # Extreme overbought (RSI >= 78 + Upper BB)
    MANUAL_CLOSE = "MANUAL_CLOSE"            # Administrative / end of backtest liquidation


class OrderAction(str, Enum):
    """Next-session execution order actions."""
    ENTER_LONG = "ENTER_LONG"
    REJECT_GAP_UP = "REJECT_GAP_UP"
    REJECT_GAP_DOWN = "REJECT_GAP_DOWN"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class DTPV1Config:
    """
    Frozen configuration container for DTP-V1 delivery swing strategy.
    All parameter values originate from phase32c_4_dtp_v1_strategy_specification.md.
    No parameter tuning or optimization permitted on historical validation data.
    """
    name: str = "DTP-V1"
    description: str = "Delivery Trend-Pullback V1 Swing Strategy for NSE Cash Equities"

    # Moving Average & Trend Periods
    ema_fast_period: int = 20
    ema_slow_period: int = 50
    sma_trend_period: int = 200

    # Volatility & Momentum Indicators
    atr_period: int = 14
    rsi_period: int = 14
    adx_period: int = 14
    volume_sma_period: int = 20
    bb_period: int = 20
    bb_std_mult: float = 2.5

    # Stock Trend & Selection Filters
    adx_min_threshold: float = 20.0
    relative_strength_window: int = 20

    # Pullback Identification Thresholds
    rsi_pullback_min: float = 38.0
    rsi_pullback_max: float = 52.0
    ema20_proximity_pct: float = 0.010       # 1.0% tolerance to 20-day EMA
    max_retracement_depth: float = 0.618      # 61.8% Fibonacci swing boundary
    volume_contraction_ratio: float = 1.10    # Volume <= 1.10 * 20-day volume SMA
    volume_expansion_ratio: float = 0.90      # Trigger volume >= 0.90 * SMA or > prev volume
    pullback_window_days: int = 3             # Lookback for active pullback condition

    # Execution & Gap Handling
    max_gap_up_pct: float = 0.015             # 1.5% maximum allowable open gap-up
    execution_slippage_bps: float = 2.0       # 2.0 bps modeled execution slippage
    execution_spread_bps: float = 1.0         # 1.0 bp modeled half-spread friction

    # Exit & Trailing Stop Thresholds
    initial_stop_atr_mult: float = 2.0        # 2.0 * ATR structural stop-loss distance
    max_stop_atr_mult: float = 3.0            # 3.0 * ATR maximum stop distance cap
    breakeven_r_mult: float = 1.0             # Excursion required to advance stop to breakeven
    breakeven_cost_buffer_pct: float = 0.005  # 0.50% buffer to guarantee all costs covered
    trailing_r_mult: float = 1.5              # Excursion required to activate trailing stop
    trailing_atr_mult: float = 1.5           # 1.5 * ATR Chandelier trailing stop distance
    consecutive_breakdown_bars: int = 2       # 2 consecutive closes < EMA50 for breakdown exit
    max_holding_sessions: int = 10            # 10 trading sessions maximum holding duration
    profit_target_r_mult: float = 3.0         # 3.0 * R full swing target
    rsi_overbought_threshold: float = 78.0    # 78.0 RSI blow-off profit taking

    # Portfolio & Risk Limits
    risk_fraction_per_trade: float = 0.010    # 1.0% equity risk per trade
    max_position_allocation_pct: float = 0.333 # 33.3% maximum capital in single position
    max_portfolio_exposure_pct: float = 1.00  # 100% maximum total equity exposure (no margin)
    max_sector_exposure_pct: float = 0.40     # 40% maximum capital in any single sector
    max_concurrent_positions: int = 3         # 3 maximum simultaneous open positions
    min_trade_notional: float = 5000.0        # ₹5,000 minimum trade notional floor

    # Sector mapping for approved research universe
    symbol_sector_map: Dict[str, str] = field(default_factory=lambda: {
        "INFY": "Information Technology",
        "RELIANCE": "Energy",
        "ICICIBANK": "Financial Services",
    })

    # ISIN mapping for approved research universe
    symbol_isin_map: Dict[str, str] = field(default_factory=lambda: {
        "INFY": "INE009A01021",
        "RELIANCE": "INE002A01018",
        "ICICIBANK": "INE090A01021",
    })

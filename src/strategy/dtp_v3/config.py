"""
SignalForge — Phase 32I: DTP-V3 Strategy Configuration & Enums
================================================================
File: src/strategy/dtp_v3/config.py

Defines configuration parameters, enums, and data models for DTP-V3
(Delivery Trend-Pullback V3) incorporating Phase 32I research improvements:
  - Choppiness Index (CI <= 60.0) false breakout & sideways filter.
  - Upper-half close reversal confirmation ((Close - Low) / (High - Low) >= 0.50).
  - 2.0x ATR Chandelier trailing stop anchored to Highest High (HH - 2.0 * ATR).
  - Preserved +3.0R profit target.
  - Preserved 10-session maximum holding rule with excursion bypass (MFE >= 1.5R).
  - Risk experiments support: E1 (1.0%), E2 (2.0%), E3 (3.0%).
  - Maximum drawdown protection pause threshold (15.0%).
  - Completely isolated from DTP-V1 and DTP-V2.
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
    """Exit classification reasons for DTP-V3 delivery positions."""
    INITIAL_STOP = "INITIAL_STOP"            # Structural or ATR-based stop-loss hit
    BREAKEVEN_STOP = "BREAKEVEN_STOP"        # Breakeven stop triggered (+1.0R excursion)
    TRAILING_STOP = "TRAILING_STOP"          # Chandelier trailing stop triggered (+1.5R excursion)
    TREND_BREAKDOWN = "TREND_BREAKDOWN"      # 2 consecutive closes below 50-day EMA
    TIME_LIMIT = "TIME_LIMIT"                # Maximum holding period reached (10 sessions, MFE < 1.5R)
    PROFIT_TARGET = "PROFIT_TARGET"          # Full target reached (+3.0R)
    DYNAMIC_OVERBOUGHT = "DYNAMIC_OVERBOUGHT" # Extreme overbought (RSI >= 78 + Upper BB)
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"      # Emergency portfolio drawdown pause
    MANUAL_CLOSE = "MANUAL_CLOSE"            # Administrative / end of backtest liquidation


class OrderAction(str, Enum):
    """Next-session execution order actions."""
    ENTER_LONG = "ENTER_LONG"
    REJECT_GAP_UP = "REJECT_GAP_UP"
    REJECT_GAP_DOWN = "REJECT_GAP_DOWN"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class DTPV3Config:
    """
    Configuration container for DTP-V3 delivery swing strategy.
    Incorporates Phase 32I validated Choppiness filter and upper-half close confirmation.
    """
    name: str = "DTP-V3"
    description: str = "Delivery Trend-Pullback V3 with Choppiness Filter & Upper-Half Confirmation"

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
    choppiness_period: int = 14

    # Stock Trend & Selection Filters
    adx_min_threshold: float = 20.0
    relative_strength_window: int = 20

    # Sideways & Choppiness Filter (Phase 32I Core Innovation)
    use_chop_filter: bool = True
    max_chop_index: float = 60.0               # Avoid entries when Choppiness Index > 60.0

    # Entry Confirmation & Reversal Structure (Phase 32I Core Innovation)
    require_upper_half_close: bool = True      # (Close - Low) / (High - Low) >= 0.50
    min_close_range_ratio: float = 0.50

    # Pullback Identification Thresholds
    rsi_pullback_min: float = 38.0
    rsi_pullback_max: float = 52.0
    ema20_proximity_pct: float = 0.010         # 1.0% tolerance to 20-day EMA
    max_retracement_depth: float = 0.618       # 61.8% Fibonacci swing boundary
    volume_contraction_ratio: float = 1.10     # Volume <= 1.10 * 20-day volume SMA
    volume_expansion_ratio: float = 0.90       # Trigger volume >= 0.90 * SMA or > prev volume
    pullback_window_days: int = 3              # Lookback for active pullback condition

    # Execution & Gap Handling
    max_gap_up_pct: float = 0.015              # 1.5% maximum allowable open gap-up
    execution_slippage_bps: float = 2.0        # 2.0 bps modeled execution slippage
    execution_spread_bps: float = 1.0          # 1.0 bp modeled half-spread friction

    # Exit & Trailing Stop Thresholds
    initial_stop_atr_mult: float = 2.0         # 2.0 * ATR structural stop-loss distance
    max_stop_atr_mult: float = 3.0             # 3.0 * ATR maximum stop distance cap
    breakeven_r_mult: float = 1.0              # Excursion required to advance stop to breakeven (+1.0R)
    breakeven_cost_buffer_pct: float = 0.005   # 0.50% buffer to guarantee all costs covered
    trailing_r_mult: float = 1.5               # Excursion required to activate trailing stop (+1.5R)
    trailing_atr_mult: float = 2.0             # 2.0 * ATR Chandelier trailing stop distance
    consecutive_breakdown_bars: int = 2        # 2 consecutive closes < EMA50 for breakdown exit
    max_holding_sessions: int = 10             # 10 trading sessions maximum holding duration (excursion bypass applies)
    profit_target_r_mult: float = 3.0          # 3.0 * R full swing target
    rsi_overbought_threshold: float = 78.0     # 78.0 RSI blow-off profit taking

    # Risk & Portfolio Limits
    risk_fraction_per_trade: float = 0.010     # Default 1.0% (E1: 0.01, E2: 0.02, E3: 0.03)
    max_position_allocation_pct: float = 0.333  # 33.3% maximum capital in single position
    max_portfolio_exposure_pct: float = 1.00   # 100% maximum total equity exposure (no margin)
    max_sector_exposure_pct: float = 0.40      # 40% maximum capital in any single sector
    max_concurrent_positions: int = 3          # 3 maximum simultaneous open positions
    min_trade_notional: float = 5000.0         # ₹5,000 minimum trade notional floor
    max_allowable_drawdown_pct: float = 0.15   # 15.0% maximum portfolio drawdown before pause

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

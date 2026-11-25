"""
SignalForge — Phase 35A: Strategy Configuration & Parameter Definitions
=======================================================================
File: src/strategy/strategy_35a/config.py

Defines configuration data structures, enums for Regime Filters (A, B, C),
Mean Reversion Entry Concepts (MR1, MR2, MR3), Exit Concepts (Exit A, B, C),
risk tiers E1-E3, and execution parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class RegimeFilterType(str, Enum):
    """Pre-defined Bullish Market Regime Filters."""
    NONE = "NONE"
    REGIME_A = "REGIME_A"  # Stock Close > SMA200 and SMA50 > SMA200
    REGIME_B = "REGIME_B"  # Nifty Close > SMA100 and Stock Close > SMA200
    REGIME_C = "REGIME_C"  # Stock Close > EMA50 and EMA50 rising


class MeanReversionEntryType(str, Enum):
    """Pre-registered Mean Reversion Entry Concepts."""
    MR1_RSI5_BB = "MR1_RSI5_BB"          # RSI 5 < 30 and Close < Lower BB(20, 2)
    MR2_RSI2_EMA20 = "MR2_RSI2_EMA20"    # RSI 2 < 10 and Close < EMA 20
    MR3_PULLBACK_ATR = "MR3_PULLBACK_ATR"# Close <= EMA 20 - 1.0 ATR and RSI 14 < 40


class ExitConceptType(str, Enum):
    """Pre-defined Exit Concepts."""
    EXIT_A = "EXIT_A"  # Close > EMA 20 or max 10 sessions
    EXIT_B = "EXIT_B"  # Price reaches BB Middle or 2 ATR stop or max 10 sessions
    EXIT_C = "EXIT_C"  # ATR Trailing Stop (2 ATR) or max 10 sessions


class RiskTier(float, Enum):
    """Position Risk Fraction Tiers."""
    E1 = 0.01  # 1% risk per trade
    E2 = 0.02  # 2% risk per trade
    E3 = 0.03  # 3% risk per trade


class ExitReason(str, Enum):
    """Exit classification reasons."""
    INITIAL_STOP = "initial_stop"            # 2.0 ATR initial protective stop
    TRAILING_STOP = "trailing_stop"          # ATR trailing stop
    TARGET_RECOVERY = "target_recovery"      # Price recovered (Close > EMA20 or BB Middle)
    TIME_STOP = "time_stop"                  # Max 10 sessions held
    END_OF_DATA = "end_of_data"              # Backtest window liquidation


@dataclass
class Strategy35AConfig:
    """Complete parameter specification for Phase 35A Regime-Filtered Mean Reversion."""
    # Portfolio Capital & Risk
    initial_capital: float = 100_000.0
    max_concurrent_positions: int = 2
    risk_per_trade: float = 0.02  # Default E2: 2%
    risk_tier: RiskTier = RiskTier.E2

    # Regime & Strategy Architecture
    regime_filter: RegimeFilterType = RegimeFilterType.REGIME_A
    entry_concept: MeanReversionEntryType = MeanReversionEntryType.MR1_RSI5_BB
    exit_concept: ExitConceptType = ExitConceptType.EXIT_A

    # Exit Parameters
    atr_stop_multiplier: float = 2.0
    max_holding_bars: int = 10

    # Execution Friction
    execution_slippage_bps: float = 5.0
    use_stress_costs: bool = True  # Stress ₹317/cr vs Official ₹307/cr

    # Identification
    config_id: str = "MR-DEFAULT"
    description: str = "Regime-Filtered Mean Reversion"

    # Symbol Mappings
    symbol_sector_map: Dict[str, str] = field(default_factory=dict)
    symbol_isin_map: Dict[str, str] = field(default_factory=dict)

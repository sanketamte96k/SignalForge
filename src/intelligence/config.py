"""
SignalForge Intelligence Engine — Configuration
===============================================
Configurable parameters, weights, and thresholds for the market intelligence
and opportunity scoring engine.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class IntelligenceWeights:
    """
    Conceptual weights for the Opportunity Score synthesis.
    Must sum to 1.0 (or normalized automatically).
    """
    trend: float = 0.25
    structure: float = 0.20
    momentum: float = 0.15
    volatility: float = 0.15
    risk_reward: float = 0.15
    session: float = 0.10


@dataclass
class IntelligenceThresholds:
    """
    Threshold boundaries for decisions and classifications.
    """
    # Tradeability decision thresholds
    tradeable_min_score: float = 65.0
    caution_min_score: float = 40.0
    min_confidence_tradeable: float = 55.0
    
    # Trend thresholds
    strong_trend_threshold: float = 70.0
    weak_trend_threshold: float = 30.0
    
    # Volatility thresholds (multiples of baseline ATR)
    vol_extreme_ratio: float = 2.0
    vol_high_ratio: float = 1.35
    vol_low_ratio: float = 0.70
    vol_very_low_ratio: float = 0.45
    
    # Momentum RSI boundaries
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    rsi_neutral_low: float = 45.0
    rsi_neutral_high: float = 55.0
    
    # Session risk cutoffs (NSE minutes from 09:15)
    # Market close is 15:30 (375 mins). Last 30 mins (after 15:00) is CLOSING.
    no_trade_session_minutes_remaining: int = 15
    late_session_minutes_remaining: int = 30
    opening_settle_minutes: int = 15


@dataclass
class IntelligenceConfig:
    """
    Master configuration object for SignalForge Intelligence.
    """
    weights: IntelligenceWeights = field(default_factory=IntelligenceWeights)
    thresholds: IntelligenceThresholds = field(default_factory=IntelligenceThresholds)
    default_capital_risk: float = 1000.0  # Contextual sizing reference
    min_required_bars: int = 50  # Minimum lookback bars needed for reliable evaluation

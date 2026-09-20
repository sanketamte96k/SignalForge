"""
SignalForge — Phase 6: Signal Engine & Presentation Interface
==============================================================
File: src/strategy/signal_engine.py

Unifies MarketState + SetupEngine + SetupScore + RiskEngine into
explainable, institutional-grade trade signal objects.

Produces structured setup explanations:
- Setup name & direction
- Market state classification
- Quality score (0–100) & confidence tier
- Entry / Stop / Target / R:R geometry
- Bulleted causal reasons
- Specific structural invalidation criteria
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd

from src.strategy.setup_score import QualityBreakdown


@dataclass
class SignalForgeSignal:
    symbol: str
    datetime: pd.Timestamp
    direction: str
    setup_name: str
    market_state: str
    quality_score: float
    confidence_tier: str
    entry_price: float
    stop_price: float
    target_price: float
    reward_risk_ratio: float
    reasons: List[str]
    invalidation_criteria: str
    pillar_scores: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "datetime": str(self.datetime),
            "direction": self.direction,
            "setup_name": self.setup_name,
            "market_state": self.market_state,
            "quality_score": self.quality_score,
            "confidence_tier": self.confidence_tier,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "reward_risk_ratio": self.reward_risk_ratio,
            "reasons": self.reasons,
            "invalidation_criteria": self.invalidation_criteria,
            "pillar_scores": self.pillar_scores,
        }

    def format_ui_card(self) -> str:
        """Formats signal for UI presentation as defined in PART 15."""
        reasons_fmt = "\n".join(f"✓ {r}" for r in self.reasons)
        card = f"""
------------------------------------------------------------
SIGNALFORGE SETUP

Symbol:       {self.symbol}
Direction:    {self.direction}
Setup:        {self.setup_name}
Market State: {self.market_state}
Quality:      {self.quality_score} / 100
Confidence:   {self.confidence_tier}

Entry:        ₹{self.entry_price:,.2f}
Stop:         ₹{self.stop_price:,.2f}
Target:       ₹{self.target_price:,.2f}
Risk/Reward:  1 : {self.reward_risk_ratio:.1f}

Reasons:
{reasons_fmt}

Invalidation:
{self.invalidation_criteria}
------------------------------------------------------------
"""
        return card.strip()


def generate_signal(
    symbol: str,
    dt: pd.Timestamp,
    setup_name: str,
    direction: str,
    market_state: str,
    entry_p: float,
    stop_p: float,
    target_p: float,
    rr_ratio: float,
    quality: QualityBreakdown,
    features: Dict[str, Any]
) -> SignalForgeSignal:
    """Constructs a fully explainable SignalForgeSignal instance."""
    reasons = []

    # Build explainable reasons
    if quality.trend_score >= 15.0:
        reasons.append("Strong trend alignment on multi-candle EMA structure")
    if quality.structure_score >= 15.0:
        reasons.append("High-quality structural compression prior to setup trigger")
    if quality.momentum_score >= 15.0:
        reasons.append("Dominant directional conviction and strong candle expansion")
    if quality.volatility_score >= 15.0:
        reasons.append("Expanding volatility regime favorable for target realization")
    if quality.entry_location_score >= 15.0:
        reasons.append("Optimal risk location with favorable asymmetric distance to stop")

    if not reasons:
        reasons.append(f"Setup {setup_name} triggered within {market_state} market state")

    # Invalidation criteria based on setup type
    if setup_name == "BREAKOUT":
        invalidation = f"Price closes back inside prior 20-candle consolidation (below/above breakout level)."
    elif setup_name == "PULLBACK":
        invalidation = f"Price violates 21-period EMA trendline support/resistance."
    elif setup_name == "RANGE_REVERSAL":
        invalidation = f"Price breaks and closes beyond range extreme boundary."
    elif setup_name == "MOMENTUM_EXPANSION":
        invalidation = f"Price retraces greater than 50% of the expansion candle body."
    else:
        invalidation = f"Price crosses ATR-defined stop boundary at ₹{stop_p:,.2f}."

    return SignalForgeSignal(
        symbol=symbol,
        datetime=dt,
        direction=direction,
        setup_name=setup_name,
        market_state=market_state,
        quality_score=quality.total_score,
        confidence_tier=quality.confidence_tier,
        entry_price=entry_p,
        stop_price=stop_p,
        target_price=target_p,
        reward_risk_ratio=rr_ratio,
        reasons=reasons,
        invalidation_criteria=invalidation,
        pillar_scores={
            "trend": quality.trend_score,
            "structure": quality.structure_score,
            "momentum": quality.momentum_score,
            "volatility": quality.volatility_score,
            "entry_location": quality.entry_location_score,
        }
    )

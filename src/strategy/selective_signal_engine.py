"""
SignalForge — Phase 7: Selective Signal Engine & Quality Scoring
================================================================
File: src/strategy/selective_signal_engine.py

Calculates transparent 0–100 quality score across 5 equal-weight pillars:
1. Structure Quality      (0–20)
2. MTF Context            (0–20)
3. Market Location        (0–20)
4. Momentum/Volatility    (0–20)
5. Risk/Reward            (0–20)

Three Decision States:
- Quality < 60  -> NO_TRADE
- 60–79         -> WATCH
- 80–100        -> SIGNAL_CANDIDATE

Includes institutional signal explanation formatting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd

from src.strategy.expected_move import StructuralSetupCandidate


@dataclass
class QualityBreakdown:
    total_score: float
    structure_score: float
    mtf_score: float
    location_score: float
    momentum_score: float
    rr_score: float
    decision_state: str  # NO_TRADE (<60), WATCH (60-79), SIGNAL_CANDIDATE (80-100)


def calculate_selective_quality(candidate: StructuralSetupCandidate) -> QualityBreakdown:
    """
    Computes transparent equal-weight quality score from 0 to 100.
    Uses only information known at timestamp T (from candidate and its context).
    """
    ctx = candidate.context
    direction = candidate.direction

    # 1. Structure Quality (0–20)
    struct_score = 10.0
    st_strength = float(ctx.get("structure_strength", 0.5))
    struct_score += (st_strength - 0.5) * 12.0  # +6 to -6

    comp = float(ctx.get("range_compression", 1.0))
    if comp < 0.95:
        struct_score += 4.0
    elif comp > 1.3:
        struct_score -= 4.0

    st_age = int(ctx.get("structure_age", 5))
    if 2 <= st_age <= 12:
        struct_score += 3.0  # Fresh confirmed structure
    elif st_age > 25:
        struct_score -= 3.0  # Stale level

    structure_score = float(round(max(min(struct_score, 20.0), 0.0), 1))

    # 2. MTF Context (0–20)
    # Aligned timeframes: 1m (+5), 5m (+5), 15m (+5), 30m (+5)
    target_dir = 1 if direction == "LONG" else -1
    mtf_score = 0.0
    if ctx.get("trend_dir_1m", 0) == target_dir:
        mtf_score += 5.0
    if ctx.get("trend_dir_5m", 0) == target_dir:
        mtf_score += 5.0
    if ctx.get("trend_dir_15m", 0) == target_dir:
        mtf_score += 5.0
    if ctx.get("trend_dir_30m", 0) == target_dir:
        mtf_score += 5.0
    mtf_score = float(round(mtf_score, 1))

    # 3. Market Location (0–20)
    # For Long: far from resistance above (>1.0 ATR: +10), close to support below (<=0.5 ATR: +10)
    # For Short: far from support below (>1.0 ATR: +10), close to resistance above (<=0.5 ATR: +10)
    loc_score = 0.0
    dist_res = float(ctx.get("dist_to_resistance_atr", 1.0))
    dist_sup = float(ctx.get("dist_to_support_atr", 1.0))

    if direction == "LONG":
        if dist_res >= 1.2:
            loc_score += 10.0
        elif dist_res >= 0.6:
            loc_score += 6.0
        else:
            loc_score += 2.0

        if dist_sup <= 0.4:
            loc_score += 10.0
        elif dist_sup <= 0.8:
            loc_score += 6.0
        else:
            loc_score += 2.0
    else:  # SHORT
        if dist_sup >= 1.2:
            loc_score += 10.0
        elif dist_sup >= 0.6:
            loc_score += 6.0
        else:
            loc_score += 2.0

        if dist_res <= 0.4:
            loc_score += 10.0
        elif dist_res <= 0.8:
            loc_score += 6.0
        else:
            loc_score += 2.0
    location_score = float(round(max(min(loc_score, 20.0), 0.0), 1))

    # 4. Momentum / Volatility (0–20)
    mom_score = 10.0
    atr_ratio = float(ctx.get("atr_ratio", 1.0))
    if atr_ratio >= 1.15:
        mom_score += 5.0  # Expanding volatility
    elif atr_ratio < 0.85:
        mom_score -= 4.0  # Stagnant volatility

    candle_body = float(ctx.get("candle_body_ratio", 0.5))
    if candle_body >= 0.65:
        mom_score += 5.0  # Strong conviction close
    elif candle_body < 0.40:
        mom_score -= 3.0  # Indecisive doji/spinning top
    momentum_score = float(round(max(min(mom_score, 20.0), 0.0), 1))

    # 5. Risk / Reward (0–20)
    rr = candidate.reward_risk_ratio
    if rr >= 2.0:
        rr_score = 20.0
    elif rr >= 1.75:
        rr_score = 16.0
    elif rr >= 1.5:
        rr_score = 12.0
    elif rr >= 1.25:
        rr_score = 8.0
    elif rr >= 1.0:
        rr_score = 4.0
    else:
        rr_score = 0.0
    risk_reward_score = float(round(rr_score, 1))

    total = round(structure_score + mtf_score + location_score + momentum_score + risk_reward_score, 1)

    if total < 60.0:
        decision = "NO_TRADE"
    elif total < 80.0:
        decision = "WATCH"
    else:
        decision = "SIGNAL_CANDIDATE"

    return QualityBreakdown(
        total_score=total,
        structure_score=structure_score,
        mtf_score=mtf_score,
        location_score=location_score,
        momentum_score=momentum_score,
        rr_score=risk_reward_score,
        decision_state=decision
    )


def format_signal_explanation(candidate: StructuralSetupCandidate, q: QualityBreakdown) -> str:
    """Formats an institutional-grade explainable setup card."""
    ctx = candidate.context
    tf_str = []
    target_dir = 1 if candidate.direction == "LONG" else -1
    for tf in ["1m", "5m", "15m", "30m"]:
        val = ctx.get(f"trend_dir_{tf}", 0)
        status = "bullish" if val == 1 else ("bearish" if val == -1 else "range")
        tf_str.append(f"{tf} {status}")
    mtf_summary = "\n".join(f"  ✓ {s}" for s in tf_str)

    invalidation_text = f"Breakdown below ₹{candidate.stop_price:,.2f} structural level" if candidate.direction == "LONG" else f"Breakout above ₹{candidate.stop_price:,.2f} structural ceiling"

    card = f"""
------------------------------------------------------------
SIGNAL CANDIDATE

Symbol:       {candidate.symbol}
Direction:    {candidate.direction}
Setup:        {candidate.setup_type}
Quality:      {q.total_score:.0f} / 100
Decision:     {q.decision_state}

Structure:    {q.structure_score:.0f} / 20
  ✓ {ctx.get('structure_type', 'STRUCTURE_CONFIRMED')}
MTF Context:  {q.mtf_score:.0f} / 20
{mtf_summary}
Market Loc:   {q.location_score:.0f} / 20
  ✓ Support dist: {ctx.get('dist_to_support_atr', 0):.1f} ATR | Resistance dist: {ctx.get('dist_to_resistance_atr', 0):.1f} ATR
Momentum:     {q.momentum_score:.0f} / 20
  ✓ ATR ratio: {ctx.get('atr_ratio', 1.0):.2f} | Conviction: {ctx.get('candle_body_ratio', 0.5):.0%}
Risk/Reward:  {q.rr_score:.0f} / 20
  ✓ 1 : {candidate.reward_risk_ratio:.1f}

Entry:        ₹{candidate.entry_price:,.2f}
Stop:         ₹{candidate.stop_price:,.2f}
Target:       ₹{candidate.target_price:,.2f}
Invalidation: {invalidation_text}
------------------------------------------------------------
"""
    return card.strip()

"""
SignalForge Intelligence Engine — Market Structure Engine
=========================================================
Causal market structure analysis identifying swing pivots, structural progression
(HH/HL vs LH/LL), range location, and breakout states without lookahead.
"""

from __future__ import annotations

from typing import List, Tuple
import numpy as np
import pandas as pd

from src.intelligence.models import StructureAnalysis, StructureState


def calculate_structure_analysis(df: pd.DataFrame) -> StructureAnalysis:
    """
    Computes causal market structure strictly looking backwards from index -1.
    Uses rolling 20-bar lookbacks and causal pivot confirmation.
    """
    if len(df) < 10:
        last_price = float(df["Close"].iloc[-1]) if len(df) > 0 and "Close" in df.columns else 0.0
        return StructureAnalysis(
            state=StructureState.UNCLEAR,
            quality_score=0.0,
            recent_swing_high=last_price,
            recent_swing_low=last_price,
            distance_to_high_pct=0.0,
            distance_to_low_pct=0.0,
            range_position=0.5,
            breakout_state="WITHIN_RANGE",
            reasons=["Insufficient historical bars (<10) for market structure analysis"]
        )

    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    close = df["Close"] if "Close" in df.columns else df["close"]
    price = float(close.iloc[-1])

    # Rolling 20-bar window for immediate structural range (excluding current bar)
    win_len = min(20, len(df) - 1)
    past_highs = high.iloc[-win_len - 1:-1]
    past_lows = low.iloc[-win_len - 1:-1]

    recent_swing_high = float(past_highs.max())
    recent_swing_low = float(past_lows.min())

    # Range position (0.0 at low, 1.0 at high)
    span = recent_swing_high - recent_swing_low
    if span > 1e-4:
        range_pos = (price - recent_swing_low) / span
        range_pos = min(1.0, max(0.0, range_pos))
    else:
        range_pos = 0.5

    dist_to_high_pct = ((recent_swing_high - price) / price) * 100.0
    dist_to_low_pct = ((price - recent_swing_low) / price) * 100.0

    # Breakout detection
    breakout_state = "WITHIN_RANGE"
    if price > recent_swing_high:
        breakout_state = "BREAKOUT_UP"
    elif price < recent_swing_low:
        breakout_state = "BREAKOUT_DOWN"

    # Multi-window swing progression (20-bar vs prior 20-bar window)
    reasons: List[str] = []
    if len(df) >= 40:
        prior_highs = high.iloc[-40:-20]
        prior_lows = low.iloc[-40:-20]
        prior_sh = float(prior_highs.max())
        prior_sl = float(prior_lows.min())

        is_higher_high = recent_swing_high > prior_sh
        is_higher_low = recent_swing_low > prior_sl
        is_lower_high = recent_swing_high < prior_sh
        is_lower_low = recent_swing_low < prior_sl
    else:
        is_higher_high = False
        is_higher_low = False
        is_lower_high = False
        is_lower_low = False

    # Structure Classification & Quality Scoring (0-100)
    if breakout_state == "BREAKOUT_UP":
        state = StructureState.BREAKOUT_UP
        quality = 85.0
        reasons.append(f"Price breaking out above 20-bar range high ({recent_swing_high:.2f})")
    elif breakout_state == "BREAKOUT_DOWN":
        state = StructureState.BREAKOUT_DOWN
        quality = 85.0
        reasons.append(f"Price breaking down below 20-bar range low ({recent_swing_low:.2f})")
    elif is_higher_high and is_higher_low:
        state = StructureState.BULLISH_STRUCTURE
        quality = 80.0
        reasons.append("Clean bullish structural progression: Higher Highs and Higher Lows confirmed")
    elif is_lower_high and is_lower_low:
        state = StructureState.BEARISH_STRUCTURE
        quality = 80.0
        reasons.append("Clean bearish structural progression: Lower Highs and Lower Lows confirmed")
    elif 0.35 <= range_pos <= 0.65:
        state = StructureState.RANGE_STRUCTURE
        quality = 50.0
        reasons.append(f"Price oscillating near midpoint of 20-bar range ({range_pos*100:.0f}% position)")
    elif range_pos > 0.8:
        state = StructureState.BULLISH_STRUCTURE if is_higher_low else StructureState.RANGE_STRUCTURE
        quality = 65.0
        reasons.append(f"Price pressing upper range boundary ({range_pos*100:.0f}% position)")
    elif range_pos < 0.2:
        state = StructureState.BEARISH_STRUCTURE if is_lower_high else StructureState.RANGE_STRUCTURE
        quality = 65.0
        reasons.append(f"Price pressing lower range boundary ({range_pos*100:.0f}% position)")
    else:
        state = StructureState.UNCLEAR
        quality = 35.0
        reasons.append("Mixed swing highs and lows without clear directional hierarchy")

    reasons.append(f"Distance to nearest structural high: {dist_to_high_pct:.2f}%; low: {dist_to_low_pct:.2f}%")

    return StructureAnalysis(
        state=state,
        quality_score=round(float(quality), 1),
        recent_swing_high=round(float(recent_swing_high), 2),
        recent_swing_low=round(float(recent_swing_low), 2),
        distance_to_high_pct=round(float(dist_to_high_pct), 3),
        distance_to_low_pct=round(float(dist_to_low_pct), 3),
        range_position=round(float(range_pos), 3),
        breakout_state=breakout_state,
        reasons=reasons
    )

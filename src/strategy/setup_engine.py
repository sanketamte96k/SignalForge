"""
SignalForge — Phase 6: Setup Detection Engine
==============================================
File: src/strategy/setup_engine.py

Detects 4 independent, economically motivated market setups:
A. BREAKOUT: Price breaks recent 20-period boundary after range compression.
B. PULLBACK: Established trend with controlled retracement to EMA and continuation.
C. RANGE_REVERSAL: Rejection of recent range extreme back into the value zone.
D. MOMENTUM_EXPANSION: Sudden directional return/candle expansion after compression.

Each setup operates independently and yields:
- setup_name
- direction (LONG / SHORT)
- entry_price
- stop_price (ATR based)
- target_price (R:R based)
- raw features for quality scoring
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd


@dataclass
class SetupCandidate:
    symbol: str
    datetime: pd.Timestamp
    setup_name: str  # BREAKOUT, PULLBACK, RANGE_REVERSAL, MOMENTUM_EXPANSION
    direction: str   # LONG or SHORT
    entry_price: float
    stop_price: float
    target_price: float
    risk_amount: float
    reward_amount: float
    reward_risk_ratio: float
    market_state: str
    atr: float
    features: Dict[str, Any]
    bar_index: int = 0



def detect_breakout_setups(df: pd.DataFrame, symbol: str) -> List[SetupCandidate]:
    """Detects Breakout setups."""
    candidates = []
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    open_p = df["Open"].to_numpy()
    atr = df["atr14"].to_numpy()
    roll_high = df["rolling_high_20"].shift(1).to_numpy()
    roll_low = df["rolling_low_20"].shift(1).to_numpy()
    compression = df["range_compression"].shift(1).to_numpy()
    atr_ratio = df["atr_ratio"].to_numpy()
    state = df["market_state"].to_numpy()
    dts = df.index

    # Long Breakout: Close breaks above 20-candle high after compression
    for i in range(25, len(df)):
        c = close[i]
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue

        # LONG Breakout
        if c > roll_high[i] and compression[i] < 1.15 and atr_ratio[i] >= 0.95:
            risk = 1.5 * a
            stop = c - risk
            target = c + (1.5 * risk)  # Base 1.5 R:R
            candidates.append(SetupCandidate(
                symbol=symbol,
                datetime=dts[i],
                setup_name="BREAKOUT",
                direction="LONG",
                entry_price=round(float(c), 2),
                stop_price=round(float(stop), 2),
                target_price=round(float(target), 2),
                risk_amount=round(float(risk), 2),
                reward_amount=round(float(1.5 * risk), 2),
                reward_risk_ratio=1.5,
                market_state=state[i],
                atr=round(float(a), 2),
                features={
                    "compression": float(compression[i]),
                    "atr_ratio": float(atr_ratio[i]),
                    "breakout_distance_atr": float((c - roll_high[i]) / a),
                    "ema9_slope": float(df["ema9_slope"].iloc[i]),
                    "adx14": float(df["adx14"].iloc[i]),
                },
                bar_index=i
            ))

        # SHORT Breakout
        elif c < roll_low[i] and compression[i] < 1.15 and atr_ratio[i] >= 0.95:
            risk = 1.5 * a
            stop = c + risk
            target = c - (1.5 * risk)
            candidates.append(SetupCandidate(
                symbol=symbol,
                datetime=dts[i],
                setup_name="BREAKOUT",
                direction="SHORT",
                entry_price=round(float(c), 2),
                stop_price=round(float(stop), 2),
                target_price=round(float(target), 2),
                risk_amount=round(float(risk), 2),
                reward_amount=round(float(1.5 * risk), 2),
                reward_risk_ratio=1.5,
                market_state=state[i],
                atr=round(float(a), 2),
                features={
                    "compression": float(compression[i]),
                    "atr_ratio": float(atr_ratio[i]),
                    "breakout_distance_atr": float((roll_low[i] - c) / a),
                    "ema9_slope": float(df["ema9_slope"].iloc[i]),
                    "adx14": float(df["adx14"].iloc[i]),
                },
                bar_index=i
            ))

    return candidates


def detect_pullback_setups(df: pd.DataFrame, symbol: str) -> List[SetupCandidate]:
    """Detects Pullback Continuation setups."""
    candidates = []
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    open_p = df["Open"].to_numpy()
    atr = df["atr14"].to_numpy()
    ema9 = df["ema9"].to_numpy()
    ema21 = df["ema21"].to_numpy()
    adx = df["adx14"].to_numpy()
    state = df["market_state"].to_numpy()
    dts = df.index

    for i in range(25, len(df)):
        c = close[i]
        o = open_p[i]
        h = high[i]
        l = low[i]
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue

        # Bullish Pullback Continuation: Trend up (EMA9 > EMA21), prior low tested EMA21, current is bullish reversal
        if ema9[i] > ema21[i] and adx[i] >= 18.0:
            prior_pulled_back = abs(low[i-1] - ema21[i-1]) <= (1.0 * a)
            continuation_candle = (c > o) and (c > high[i-1])
            if prior_pulled_back and continuation_candle:
                risk = max(c - min(low[i], low[i-1]), 1.2 * a)
                stop = c - risk
                target = c + (1.5 * risk)
                candidates.append(SetupCandidate(
                    symbol=symbol,
                    datetime=dts[i],
                    setup_name="PULLBACK",
                    direction="LONG",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(stop), 2),
                    target_price=round(float(target), 2),
                    risk_amount=round(float(risk), 2),
                    reward_amount=round(float(1.5 * risk), 2),
                    reward_risk_ratio=1.5,
                    market_state=state[i],
                    atr=round(float(a), 2),
                    features={
                        "pullback_depth_atr": float(abs(c - ema21[i]) / a),
                        "ema_spread": float((ema9[i] - ema21[i]) / c),
                        "adx14": float(adx[i]),
                    },
                    bar_index=i
                ))

        # Bearish Pullback Continuation
        elif ema9[i] < ema21[i] and adx[i] >= 18.0:
            prior_pulled_back = abs(high[i-1] - ema21[i-1]) <= (1.0 * a)
            continuation_candle = (c < o) and (c < low[i-1])
            if prior_pulled_back and continuation_candle:
                risk = max(max(high[i], high[i-1]) - c, 1.2 * a)
                stop = c + risk
                target = c - (1.5 * risk)
                candidates.append(SetupCandidate(
                    symbol=symbol,
                    datetime=dts[i],
                    setup_name="PULLBACK",
                    direction="SHORT",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(stop), 2),
                    target_price=round(float(target), 2),
                    risk_amount=round(float(risk), 2),
                    reward_amount=round(float(1.5 * risk), 2),
                    reward_risk_ratio=1.5,
                    market_state=state[i],
                    atr=round(float(a), 2),
                    features={
                        "pullback_depth_atr": float(abs(c - ema21[i]) / a),
                        "ema_spread": float((ema21[i] - ema9[i]) / c),
                        "adx14": float(adx[i]),
                    },
                    bar_index=i
                ))

    return candidates


def detect_range_reversal_setups(df: pd.DataFrame, symbol: str) -> List[SetupCandidate]:
    """Detects Range Reversal setups (rejection of range boundary)."""
    candidates = []
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    open_p = df["Open"].to_numpy()
    atr = df["atr14"].to_numpy()
    roll_high = df["rolling_high_20"].shift(1).to_numpy()
    roll_low = df["rolling_low_20"].shift(1).to_numpy()
    adx = df["adx14"].to_numpy()
    state = df["market_state"].to_numpy()
    dts = df.index

    for i in range(25, len(df)):
        c = close[i]
        o = open_p[i]
        h = high[i]
        l = low[i]
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue

        # Only in non-trending / range environments
        if adx[i] < 25.0:
            # Bullish Reversal at Range Low: Tested or pierced roll_low, closes back above with lower wick
            if l <= roll_low[i] and c > roll_low[i] and c > o:
                lower_wick = min(o, c) - l
                body = abs(c - o)
                if lower_wick >= (0.8 * body) and lower_wick >= (0.3 * (h - l)):
                    risk = max(c - l, 1.2 * a)
                    stop = c - risk
                    target = c + (1.5 * risk)
                    candidates.append(SetupCandidate(
                        symbol=symbol,
                        datetime=dts[i],
                        setup_name="RANGE_REVERSAL",
                        direction="LONG",
                        entry_price=round(float(c), 2),
                        stop_price=round(float(stop), 2),
                        target_price=round(float(target), 2),
                        risk_amount=round(float(risk), 2),
                        reward_amount=round(float(1.5 * risk), 2),
                        reward_risk_ratio=1.5,
                        market_state=state[i],
                        atr=round(float(a), 2),
                        features={
                            "range_width_atr": float((roll_high[i] - roll_low[i]) / a),
                            "lower_wick_ratio": float(lower_wick / (h - l)) if (h - l) > 0 else 0.5,
                            "adx14": float(adx[i]),
                        },
                        bar_index=i
                    ))

            # Bearish Reversal at Range High: Tested or pierced roll_high, closes back below with upper wick
            elif h >= roll_high[i] and c < roll_high[i] and c < o:
                upper_wick = h - max(o, c)
                body = abs(c - o)
                if upper_wick >= (0.8 * body) and upper_wick >= (0.3 * (h - l)):
                    risk = max(h - c, 1.2 * a)
                    stop = c + risk
                    target = c - (1.5 * risk)
                    candidates.append(SetupCandidate(
                        symbol=symbol,
                        datetime=dts[i],
                        setup_name="RANGE_REVERSAL",
                        direction="SHORT",
                        entry_price=round(float(c), 2),
                        stop_price=round(float(stop), 2),
                        target_price=round(float(target), 2),
                        risk_amount=round(float(risk), 2),
                        reward_amount=round(float(1.5 * risk), 2),
                        reward_risk_ratio=1.5,
                        market_state=state[i],
                        atr=round(float(a), 2),
                        features={
                            "range_width_atr": float((roll_high[i] - roll_low[i]) / a),
                            "upper_wick_ratio": float(upper_wick / (h - l)) if (h - l) > 0 else 0.5,
                            "adx14": float(adx[i]),
                        },
                        bar_index=i
                    ))

    return candidates


def detect_momentum_expansion_setups(df: pd.DataFrame, symbol: str) -> List[SetupCandidate]:
    """Detects Momentum Expansion setups (sudden expansion after compression)."""
    candidates = []
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    open_p = df["Open"].to_numpy()
    atr = df["atr14"].to_numpy()
    compression = df["range_compression"].shift(1).to_numpy()
    atr_ratio = df["atr_ratio"].to_numpy()
    state = df["market_state"].to_numpy()
    dts = df.index

    for i in range(25, len(df)):
        c = close[i]
        o = open_p[i]
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue

        body = abs(c - o)
        # Prior compression with large expansion candle >= 1.2 ATR and expanding ATR
        if compression[i] < 1.10 and atr_ratio[i] > 1.05 and body >= (1.1 * a):
            if c > o:  # Bullish Momentum Expansion
                risk = 1.3 * a
                stop = c - risk
                target = c + (1.5 * risk)
                candidates.append(SetupCandidate(
                    symbol=symbol,
                    datetime=dts[i],
                    setup_name="MOMENTUM_EXPANSION",
                    direction="LONG",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(stop), 2),
                    target_price=round(float(target), 2),
                    risk_amount=round(float(risk), 2),
                    reward_amount=round(float(1.5 * risk), 2),
                    reward_risk_ratio=1.5,
                    market_state=state[i],
                    atr=round(float(a), 2),
                    features={
                        "body_expansion_ratio": float(body / a),
                        "compression_prior": float(compression[i]),
                        "atr_ratio": float(atr_ratio[i]),
                    },
                    bar_index=i
                ))
            else:  # Bearish Momentum Expansion
                risk = 1.3 * a
                stop = c + risk
                target = c - (1.5 * risk)
                candidates.append(SetupCandidate(
                    symbol=symbol,
                    datetime=dts[i],
                    setup_name="MOMENTUM_EXPANSION",
                    direction="SHORT",
                    entry_price=round(float(c), 2),
                    stop_price=round(float(stop), 2),
                    target_price=round(float(target), 2),
                    risk_amount=round(float(risk), 2),
                    reward_amount=round(float(1.5 * risk), 2),
                    reward_risk_ratio=1.5,
                    market_state=state[i],
                    atr=round(float(a), 2),
                    features={
                        "body_expansion_ratio": float(body / a),
                        "compression_prior": float(compression[i]),
                        "atr_ratio": float(atr_ratio[i]),
                    },
                    bar_index=i
                ))

    return candidates


def detect_all_setups(df: pd.DataFrame, symbol: str) -> List[SetupCandidate]:
    """Runs all 4 independent setup detectors on the dataset."""
    all_setups = []
    all_setups.extend(detect_breakout_setups(df, symbol))
    all_setups.extend(detect_pullback_setups(df, symbol))
    all_setups.extend(detect_range_reversal_setups(df, symbol))
    all_setups.extend(detect_momentum_expansion_setups(df, symbol))

    # Sort chronologically
    all_setups.sort(key=lambda s: s.datetime)
    return all_setups

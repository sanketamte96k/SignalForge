"""
SignalForge — Phase 33B: S5 Forensic Research Configurations
============================================================
File: src/strategy/s5_forensic_research/config.py

Defines hypotheses, parameter sets, and execution modes for forensic analysis of S5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class S5HypothesisID(str, Enum):
    BASELINE_S5 = "S5_BASELINE (Official Baseline)"
    H1_VOLUME_EXPANSION_1_5X = "H1_VOLUME_1_5X (Volume > 1.5x SMA20)"
    H2_PROFIT_TARGET_3ATR = "H2_TARGET_3ATR (Fixed 3.0 ATR Profit Target)"
    H3_TIGHT_CONTRACTION_10PCT = "H3_SQUEEZE_10PCT (BB Width <= 10th Percentile)"


@dataclass(frozen=True)
class S5ForensicConfig:
    """Configuration for S5 forensic variations."""
    hypothesis_id: S5HypothesisID
    description: str
    bb_period: int = 20
    bb_std: float = 2.0
    bb_width_lookback: int = 120
    bb_width_pct_thresh: float = 0.20  # 20% in baseline; 10% in H3
    breakout_bars: int = 20
    volume_mult: float = 1.0  # 1.0 in baseline; 1.5 in H1
    stop_atr_mult: float = 2.0
    trailing_low_bars: int = 10
    max_hold_bars: int = 10
    profit_target_atr_mult: Optional[float] = None  # None in baseline; 3.0 in H2


FORENSIC_HYPOTHESIS_CONFIGS: Dict[S5HypothesisID, S5ForensicConfig] = {
    S5HypothesisID.BASELINE_S5: S5ForensicConfig(
        hypothesis_id=S5HypothesisID.BASELINE_S5,
        description="Phase 33A S5 Baseline: BB Width <= 20th %ile, 20d High Breakout, Volume > SMA20, 2.0 ATR Stop, 10d Trailing Low.",
        bb_width_pct_thresh=0.20,
        volume_mult=1.0,
        profit_target_atr_mult=None,
    ),
    S5HypothesisID.H1_VOLUME_EXPANSION_1_5X: S5ForensicConfig(
        hypothesis_id=S5HypothesisID.H1_VOLUME_EXPANSION_1_5X,
        description="Hypothesis 1: Require 1.5x Volume expansion (matching Strategy 2) to filter out low-volume false breakouts.",
        bb_width_pct_thresh=0.20,
        volume_mult=1.5,
        profit_target_atr_mult=None,
    ),
    S5HypothesisID.H2_PROFIT_TARGET_3ATR: S5ForensicConfig(
        hypothesis_id=S5HypothesisID.H2_PROFIT_TARGET_3ATR,
        description="Hypothesis 2: Add protective 3.0 ATR profit target (1.5:1 reward/risk) to lock in gains and prevent roundtripping.",
        bb_width_pct_thresh=0.20,
        volume_mult=1.0,
        profit_target_atr_mult=3.0,
    ),
    S5HypothesisID.H3_TIGHT_CONTRACTION_10PCT: S5ForensicConfig(
        hypothesis_id=S5HypothesisID.H3_TIGHT_CONTRACTION_10PCT,
        description="Hypothesis 3: Require extreme volatility squeeze (BB Width <= 10th %ile) to isolate highest-conviction compressions.",
        bb_width_pct_thresh=0.10,
        volume_mult=1.0,
        profit_target_atr_mult=None,
    ),
}

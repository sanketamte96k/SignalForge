"""
SignalForge — Phase 33A: Strategy Signal Engines & Exit Evaluator
=================================================================
File: src/strategy/strategy_research_lab/signal_engines.py

Implements deterministic EOD signal generators and intraday/EOD exit evaluation
for the five independent strategy candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.strategy.strategy_research_lab.config import (
    DEFAULT_STRATEGY_CONFIGS,
    ExitReason,
    StrategyCandidateConfig,
    StrategyID,
)


@dataclass
class CandidateSignal:
    """Represents a trading candidate signal generated at EOD for execution next session."""
    strategy_id: StrategyID
    symbol: str
    signal_date: date
    execution_date: date
    signal_close: float
    atr14: float
    stop_loss_price: float
    profit_target_price: Optional[float] = None
    trailing_exit_level: Optional[float] = None
    max_hold_bars: int = 10
    priority_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


def generate_candidate_signals(
    strategy_id: StrategyID,
    augmented_universe: Dict[str, pd.DataFrame],
    day_idx: int,
    current_dt: date,
    next_dt: date,
    nifty_df: Optional[pd.DataFrame] = None,
    cfg: Optional[StrategyCandidateConfig] = None,
) -> List[CandidateSignal]:
    """
    Evaluates entry conditions at the end of session `day_idx` (date `current_dt`).
    Returns list of signals eligible for execution at next session open (`next_dt`).
    """
    if cfg is None:
        cfg = DEFAULT_STRATEGY_CONFIGS[strategy_id]

    signals: List[CandidateSignal] = []

    # Check Nifty trend for Strategy 2 if required
    nifty_is_positive = True
    if strategy_id == StrategyID.STRATEGY_2_DONCHIAN_BREAKOUT and nifty_df is not None:
        if day_idx >= 100 and current_dt in nifty_df.index:
            nifty_row = nifty_df.loc[current_dt]
            nifty_close = float(nifty_row["close"])
            nifty_sma100 = float(nifty_row["sma_100"])
            nifty_sma100_prev = float(nifty_row["sma_100_prev"])
            # Nifty close above SMA100 and SMA100 rising
            nifty_is_positive = (nifty_close > nifty_sma100) and (nifty_sma100 >= nifty_sma100_prev)
        else:
            nifty_is_positive = False

    for sym, df in augmented_universe.items():
        if day_idx >= len(df):
            continue
        row = df.iloc[day_idx]
        if pd.isna(row["close"]) or pd.isna(row["atr_14"]) or float(row["atr_14"]) <= 0:
            continue

        close = float(row["close"])
        open_px = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        atr14 = float(row["atr_14"])
        volume = float(row["volume"])

        # Prior row for daily changes
        prior_close = float(df.iloc[day_idx - 1]["close"]) if day_idx > 0 else close

        # -------------------------------------------------------------
        # STRATEGY 1 — TREND PULLBACK
        # -------------------------------------------------------------
        if strategy_id == StrategyID.STRATEGY_1_TREND_PULLBACK:
            sma200 = float(row["sma_200"])
            ema20 = float(row["ema_20"])
            ema50 = float(row["ema_50"])
            rsi14 = float(row["rsi_14"])

            if pd.isna(sma200) or pd.isna(ema20) or pd.isna(ema50) or pd.isna(rsi14):
                continue

            cond_trend = close > sma200 and ema20 > ema50
            cond_pullback = low <= ema20 and close >= ema20 * 0.95
            cond_rsi = cfg.s1_rsi_min <= rsi14 <= cfg.s1_rsi_max
            cond_bullish = close > open_px and close > prior_close

            if cond_trend and cond_pullback and cond_rsi and cond_bullish:
                stop_loss = close - (cfg.stop_atr_mult * atr14)
                profit_target = close + (cfg.s1_target_atr_mult * atr14)
                priority = abs(50.0 - rsi14)  # Closer to 50 is more balanced
                signals.append(
                    CandidateSignal(
                        strategy_id=strategy_id,
                        symbol=sym,
                        signal_date=current_dt,
                        execution_date=next_dt,
                        signal_close=close,
                        atr14=atr14,
                        stop_loss_price=stop_loss,
                        profit_target_price=profit_target,
                        max_hold_bars=cfg.max_hold_bars,
                        priority_score=-priority,  # highest priority first
                        metadata={"rsi14": rsi14, "ema20": ema20, "sma200": sma200},
                    )
                )

        # -------------------------------------------------------------
        # STRATEGY 2 — DONCHIAN BREAKOUT
        # -------------------------------------------------------------
        elif strategy_id == StrategyID.STRATEGY_2_DONCHIAN_BREAKOUT:
            if not nifty_is_positive:
                continue

            dh_20 = float(row["donchian_high_20"])
            dl_10 = float(row["donchian_low_10"])
            vol_sma20 = float(row["volume_sma_20"])

            if pd.isna(dh_20) or pd.isna(vol_sma20) or vol_sma20 <= 0:
                continue

            cond_breakout = close > dh_20
            cond_volume = volume > (cfg.s2_volume_mult * vol_sma20)

            if cond_breakout and cond_volume:
                stop_loss = close - (cfg.stop_atr_mult * atr14)
                vol_ratio = volume / vol_sma20
                signals.append(
                    CandidateSignal(
                        strategy_id=strategy_id,
                        symbol=sym,
                        signal_date=current_dt,
                        execution_date=next_dt,
                        signal_close=close,
                        atr14=atr14,
                        stop_loss_price=stop_loss,
                        trailing_exit_level=dl_10,
                        max_hold_bars=cfg.max_hold_bars,
                        priority_score=vol_ratio,
                        metadata={"donchian_high_20": dh_20, "volume_ratio": vol_ratio},
                    )
                )

        # -------------------------------------------------------------
        # STRATEGY 3 — RELATIVE STRENGTH MOMENTUM
        # -------------------------------------------------------------
        elif strategy_id == StrategyID.STRATEGY_3_RELATIVE_STRENGTH:
            cs_rank = float(row.get("cs_rank_percentile", np.nan))
            sma50 = float(row["sma_50"])
            sma200 = float(row["sma_200"])

            if pd.isna(cs_rank) or pd.isna(sma50) or pd.isna(sma200):
                continue

            cond_rs = cs_rank >= cfg.s3_top_percentile
            cond_trend = close > sma50 and close > sma200

            if cond_rs and cond_trend:
                stop_loss = close - (cfg.stop_atr_mult * atr14)
                signals.append(
                    CandidateSignal(
                        strategy_id=strategy_id,
                        symbol=sym,
                        signal_date=current_dt,
                        execution_date=next_dt,
                        signal_close=close,
                        atr14=atr14,
                        stop_loss_price=stop_loss,
                        max_hold_bars=cfg.max_hold_bars,
                        priority_score=cs_rank,
                        metadata={"cs_rank": cs_rank, "return_60": float(row.get("return_60", 0.0))},
                    )
                )

        # -------------------------------------------------------------
        # STRATEGY 4 — TREND-CONDITIONED MEAN REVERSION
        # -------------------------------------------------------------
        elif strategy_id == StrategyID.STRATEGY_4_MEAN_REVERSION:
            sma200 = float(row["sma_200"])
            rsi14 = float(row["rsi_14"])
            bb_lower = float(row["bb_lower"])
            bb_middle = float(row["bb_middle"])

            if pd.isna(sma200) or pd.isna(rsi14) or pd.isna(bb_lower) or pd.isna(bb_middle):
                continue

            cond_trend = close > sma200
            cond_oversold = rsi14 < cfg.s4_rsi_oversold
            cond_bb = close < bb_lower
            cond_bullish = close > open_px

            if cond_trend and cond_oversold and cond_bb and cond_bullish:
                stop_loss = close - (cfg.stop_atr_mult * atr14)
                recovery_target = bb_middle
                oversold_depth = cfg.s4_rsi_oversold - rsi14
                signals.append(
                    CandidateSignal(
                        strategy_id=strategy_id,
                        symbol=sym,
                        signal_date=current_dt,
                        execution_date=next_dt,
                        signal_close=close,
                        atr14=atr14,
                        stop_loss_price=stop_loss,
                        profit_target_price=recovery_target,
                        max_hold_bars=cfg.s4_max_hold_bars,
                        priority_score=oversold_depth,
                        metadata={"rsi14": rsi14, "bb_lower": bb_lower, "bb_middle": bb_middle},
                    )
                )

        # -------------------------------------------------------------
        # STRATEGY 5 — VOLATILITY CONTRACTION BREAKOUT
        # -------------------------------------------------------------
        elif strategy_id == StrategyID.STRATEGY_5_VOLATILITY_CONTRACTION:
            bb_width_pct = float(row.get("bb_width_pct_120", np.nan))
            dh_20 = float(row["donchian_high_20"])
            dl_10 = float(row["donchian_low_10"])
            vol_sma20 = float(row["volume_sma_20"])

            if pd.isna(bb_width_pct) or pd.isna(dh_20) or pd.isna(vol_sma20):
                continue

            cond_squeeze = bb_width_pct <= cfg.s5_bb_width_pct_thresh
            cond_breakout = close > dh_20
            cond_volume = volume > vol_sma20

            if cond_squeeze and cond_breakout and cond_volume:
                stop_loss = close - (cfg.stop_atr_mult * atr14)
                squeeze_intensity = 1.0 - bb_width_pct
                signals.append(
                    CandidateSignal(
                        strategy_id=strategy_id,
                        symbol=sym,
                        signal_date=current_dt,
                        execution_date=next_dt,
                        signal_close=close,
                        atr14=atr14,
                        stop_loss_price=stop_loss,
                        trailing_exit_level=dl_10,
                        max_hold_bars=cfg.max_hold_bars,
                        priority_score=squeeze_intensity,
                        metadata={"bb_width_pct": bb_width_pct, "donchian_high_20": dh_20},
                    )
                )

    # Sort descending by priority score for deterministic selection
    signals.sort(key=lambda s: s.priority_score, reverse=True)
    return signals


def evaluate_candidate_exit(
    strategy_id: StrategyID,
    bar: pd.Series,
    entry_price: float,
    stop_loss_price: float,
    bars_held: int,
    max_hold_bars: int,
    is_final_bar: bool,
    profit_target_price: Optional[float] = None,
    trailing_exit_level: Optional[float] = None,
    cfg: Optional[StrategyCandidateConfig] = None,
) -> Optional[Tuple[float, ExitReason, str]]:
    """
    Evaluates whether an active position should exit on the current daily bar.
    Returns (raw_exit_price, ExitReason, notes) or None if trade remains open.
    """
    if cfg is None:
        cfg = DEFAULT_STRATEGY_CONFIGS[strategy_id]

    open_px = float(bar["open"])
    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])

    # 1. Final bar liquidation
    if is_final_bar:
        return close, ExitReason.END_OF_DATA_LIQUIDATION, "End of dataset liquidation"

    # 2. Protective Stop Loss (Intraday check: Low <= Stop)
    if low <= stop_loss_price:
        exec_px = min(open_px, stop_loss_price)
        return exec_px, ExitReason.PROTECTIVE_STOP, f"Protective stop triggered at {exec_px:.2f}"

    # 3. Trailing Stop Check (for S2 and S5)
    if strategy_id in (StrategyID.STRATEGY_2_DONCHIAN_BREAKOUT, StrategyID.STRATEGY_5_VOLATILITY_CONTRACTION):
        current_trail = float(bar.get("donchian_low_10", np.nan))
        active_trail = current_trail if not pd.isna(current_trail) else trailing_exit_level
        if active_trail is not None and low < active_trail:
            exec_px = min(open_px, active_trail)
            return exec_px, ExitReason.TRAILING_STOP, f"Trailing 10-session low exit at {exec_px:.2f}"

    # 4. Profit Target Check (for S1 and S4)
    if strategy_id == StrategyID.STRATEGY_1_TREND_PULLBACK and profit_target_price is not None:
        if high >= profit_target_price:
            exec_px = max(open_px, profit_target_price)
            return exec_px, ExitReason.PROFIT_TARGET, f"Fixed risk-multiple profit target reached at {exec_px:.2f}"

    if strategy_id == StrategyID.STRATEGY_4_MEAN_REVERSION:
        bb_middle = float(bar.get("bb_middle", np.nan))
        target = bb_middle if not pd.isna(bb_middle) else profit_target_price
        if target is not None and high >= target:
            exec_px = max(open_px, target)
            return exec_px, ExitReason.PROFIT_TARGET, f"Mean reversion target BB Middle reached at {exec_px:.2f}"

    # 5. Relative Strength Rebalance Exit (for S3)
    if strategy_id == StrategyID.STRATEGY_3_RELATIVE_STRENGTH:
        cs_rank = float(bar.get("cs_rank_percentile", np.nan))
        if not pd.isna(cs_rank) and cs_rank < cfg.s3_exit_percentile:
            return close, ExitReason.REBALANCE_EXIT, f"Relative strength fell below 50th percentile ({cs_rank:.2f})"

    # 6. Time Stop (Max Holding Period)
    if bars_held >= max_hold_bars:
        return close, ExitReason.TIME_STOP, f"Maximum holding period reached ({bars_held} bars)"

    return None

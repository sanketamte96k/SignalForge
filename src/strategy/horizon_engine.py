"""
SignalForge — Phase 8: Horizon & Edge Discovery Engine
======================================================
File: src/strategy/horizon_engine.py

Core causal architecture evaluating:
1. Multiple Trading Horizons: 5m, 15m, 30m, 60m, 120m
2. Causal Market Regimes:
   - TREND_UP, TREND_DOWN, RANGE
   - HIGH_VOLATILITY, LOW_VOLATILITY, VOLATILITY_EXPANSION, VOLATILITY_CONTRACTION
   - OPENING_SESSION, MIDDAY, CLOSING_SESSION
3. Six Simple Price-Action Hypotheses:
   - HYPOTHESIS A: TREND CONTINUATION
   - HYPOTHESIS B: PULLBACK CONTINUATION
   - HYPOTHESIS C: RANGE MEAN REVERSION
   - HYPOTHESIS D: BREAKOUT FOLLOW-THROUGH
   - HYPOTHESIS E: OPENING SESSION MOMENTUM
   - HYPOTHESIS F: VOLATILITY EXPANSION

Strictly causal: All regime and setup classifications use information known at timestamp T.
Forward horizon metrics are evaluation labels ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd


HORIZONS = [5, 15, 30, 60, 120]

HYPOTHESES = [
    "HYPOTHESIS_A_TREND_CONTINUATION",
    "HYPOTHESIS_B_PULLBACK_CONTINUATION",
    "HYPOTHESIS_C_RANGE_MEAN_REVERSION",
    "HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH",
    "HYPOTHESIS_E_OPENING_SESSION_MOMENTUM",
    "HYPOTHESIS_F_VOLATILITY_EXPANSION",
]

REGIMES = [
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "VOLATILITY_EXPANSION",
    "VOLATILITY_CONTRACTION",
    "OPENING_SESSION",
    "MIDDAY",
    "CLOSING_SESSION",
]


@dataclass
class HorizonOutcome:
    horizon_minutes: int
    exit_datetime: pd.Timestamp
    exit_price: float
    forward_return_pct: float
    mfe_price: float
    mfe_atr: float
    mae_price: float
    mae_atr: float
    return_over_atr: float
    vol_adjusted_return: float
    time_to_mfe: int  # minutes
    time_to_mae: int  # minutes
    prob_positive: int  # 1 or 0
    reach_plus_05_atr: int
    reach_plus_10_atr: int
    reach_plus_15_atr: int
    reach_minus_05_atr: int
    reach_minus_10_atr: int
    excursion_ratio: float
    # Trade simulation outcomes across cost multipliers
    gross_pnl: float
    turnover: float
    base_cost: float
    net_pnl_1_0x: float
    net_pnl_1_5x: float
    net_pnl_2_0x: float


@dataclass
class HorizonEvent:
    setup_id: str
    symbol: str
    timestamp: pd.Timestamp
    bar_index: int
    hypothesis: str
    direction: str  # LONG or SHORT
    entry_price: float
    atr: float
    regime: str
    session_regime: str
    features: Dict[str, Any] = field(default_factory=dict)
    horizons: Dict[int, HorizonOutcome] = field(default_factory=dict)


def classify_causal_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all causal features and classifies market conditions at timestamp T.
    Zero future data is used.
    """
    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]
    open_p = out["Open"]
    vol = out["Volume"]

    # 1. EMAs and Slopes
    out["ema9"] = close.ewm(span=9, adjust=False).mean()
    out["ema21"] = close.ewm(span=21, adjust=False).mean()
    out["ema50"] = close.ewm(span=50, adjust=False).mean()
    out["ema9_slope"] = (out["ema9"].diff(5) / 5.0).fillna(0.0)
    out["ema_spread"] = (out["ema9"] - out["ema21"]) / close

    # 2. True Range and ATR(14)
    prev_close = close.shift(1).bfill()
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["tr"] = tr
    out["atr14"] = tr.ewm(span=14, adjust=False).mean()
    out["atr_sma50"] = out["atr14"].rolling(50, min_periods=10).mean().bfill()
    out["atr_ratio"] = out["atr14"] / out["atr_sma50"].replace(0, np.nan).fillna(1.0)

    # Rolling ATR Percentile (100 candles) - fast vectorized
    atr_min_100 = out["atr14"].rolling(100, min_periods=20).min()
    atr_max_100 = out["atr14"].rolling(100, min_periods=20).max()
    atr_denom = (atr_max_100 - atr_min_100).replace(0, np.nan)
    out["atr_pctile"] = ((out["atr14"] - atr_min_100) / atr_denom * 100.0).bfill().fillna(50.0)

    # 3. Directional Movement (ADX 14)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    alpha = 1.0 / 14.0
    smooth_plus = pd.Series(plus_dm, index=out.index).ewm(alpha=alpha, adjust=False).mean()
    smooth_minus = pd.Series(minus_dm, index=out.index).ewm(alpha=alpha, adjust=False).mean()
    atr_smooth = tr.ewm(alpha=alpha, adjust=False).mean().replace(0, np.nan)
    plus_di = (smooth_plus / atr_smooth) * 100.0
    minus_di = (smooth_minus / atr_smooth) * 100.0
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / di_sum) * 100.0
    out["adx14"] = dx.ewm(alpha=alpha, adjust=False).mean().bfill().fillna(20.0)

    # 4. Rolling Range (20 candles)
    out["rolling_high_20"] = high.shift(1).rolling(20, min_periods=5).max().bfill()
    out["rolling_low_20"] = low.shift(1).rolling(20, min_periods=5).min().bfill()
    out["rolling_range_20"] = out["rolling_high_20"] - out["rolling_low_20"]
    out["range_compression"] = (out["rolling_range_20"] / (out["atr14"] * np.sqrt(20.0))).replace(0, np.nan).bfill().fillna(1.0)
    range_span = out["rolling_range_20"].replace(0, np.nan)
    out["range_position"] = ((close - out["rolling_low_20"]) / range_span).bfill().fillna(0.5)

    # Candle body conviction
    candle_range = (high - low).replace(0, np.nan)
    out["candle_body_ratio"] = ((close - open_p).abs() / candle_range).bfill().fillna(0.5)

    # Returns
    out["return_5m"] = close.pct_change(5).fillna(0.0)

    # 5. Session Regimes
    times = out.index.time
    t_open_end = pd.Timestamp("10:30:00").time()
    t_mid_end = pd.Timestamp("14:00:00").time()

    sess_regimes = np.where(
        times < t_open_end, "OPENING_SESSION",
        np.where(times < t_mid_end, "MIDDAY", "CLOSING_SESSION")
    )
    out["session_regime"] = sess_regimes

    # 6. Primary Market Regimes
    conditions = [
        (out["ema9"] > out["ema21"]) & (out["ema9_slope"] > 0) & (out["adx14"] >= 20.0),
        (out["ema9"] < out["ema21"]) & (out["ema9_slope"] < 0) & (out["adx14"] >= 20.0),
        (out["adx14"] < 20.0) | (out["range_compression"] < 1.05),
        (out["atr_pctile"] >= 70.0),
        (out["atr_pctile"] <= 30.0),
        (out["atr_ratio"] > 1.15),
        (out["atr_ratio"] < 0.85),
    ]
    choices = [
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "VOLATILITY_EXPANSION",
        "VOLATILITY_CONTRACTION",
    ]
    out["primary_regime"] = np.select(conditions, choices, default="RANGE")

    return out


def detect_hypothesis_events(df_feat: pd.DataFrame, symbol: str) -> List[HorizonEvent]:
    """
    Detects causal entry events for each of the 6 simple price-action hypotheses:
    A. Trend Continuation
    B. Pullback Continuation
    C. Range Mean Reversion
    D. Breakout Follow-Through
    E. Opening Session Momentum
    F. Volatility Expansion
    """
    events: List[HorizonEvent] = []
    n = len(df_feat)
    if n < 60:
        return events

    close = df_feat["Close"].to_numpy()
    high = df_feat["High"].to_numpy()
    low = df_feat["Low"].to_numpy()
    open_p = df_feat["Open"].to_numpy()
    atr = df_feat["atr14"].to_numpy()
    dts = df_feat.index

    ema9 = df_feat["ema9"].to_numpy()
    ema21 = df_feat["ema21"].to_numpy()
    ema9_slope = df_feat["ema9_slope"].to_numpy()
    comp = df_feat["range_compression"].to_numpy()
    r_pos = df_feat["range_position"].to_numpy()
    r_high = df_feat["rolling_high_20"].to_numpy()
    r_low = df_feat["rolling_low_20"].to_numpy()
    atr_ratio = df_feat["atr_ratio"].to_numpy()
    body_ratio = df_feat["candle_body_ratio"].to_numpy()
    prim_regime = df_feat["primary_regime"].to_numpy()
    sess_regime = df_feat["session_regime"].to_numpy()
    times = df_feat.index.time

    t_start = pd.Timestamp("09:25:00").time()
    t_cutoff = pd.Timestamp("14:45:00").time()

    # Track last event bar per hypothesis to avoid excessive clustered duplicates (minimum 5 bars apart)
    last_event_bar: Dict[str, int] = {h: -999 for h in HYPOTHESES}

    for i in range(25, n - 125):  # Leave room for causal lookahead isolation
        t_curr = times[i]
        if t_curr < t_start or t_curr > t_cutoff:
            continue

        c = close[i]
        h = high[i]
        l = low[i]
        o = open_p[i]
        a = max(atr[i], 0.1)
        dt = dts[i]
        dt_str = dt.strftime("%Y%m%d_%H%M")

        # ---------------------------------------------------------------------
        # HYPOTHESIS A: TREND CONTINUATION
        # Moving directionally, EMA structure confirmed, strong close
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_A_TREND_CONTINUATION"] >= 5:
            if ema9[i] > ema21[i] and ema9_slope[i] > 0 and c > o and body_ratio[i] >= 0.55:
                # Bullish trend continuation
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HA_LONG_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_A_TREND_CONTINUATION",
                    direction="LONG", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"ema9_slope": float(ema9_slope[i]), "body_ratio": float(body_ratio[i])}
                ))
                last_event_bar["HYPOTHESIS_A_TREND_CONTINUATION"] = i

            elif ema9[i] < ema21[i] and ema9_slope[i] < 0 and c < o and body_ratio[i] >= 0.55:
                # Bearish trend continuation
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HA_SHORT_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_A_TREND_CONTINUATION",
                    direction="SHORT", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"ema9_slope": float(ema9_slope[i]), "body_ratio": float(body_ratio[i])}
                ))
                last_event_bar["HYPOTHESIS_A_TREND_CONTINUATION"] = i

        # ---------------------------------------------------------------------
        # HYPOTHESIS B: PULLBACK CONTINUATION
        # Prior trend, retracement near EMA21, recovery candle
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_B_PULLBACK_CONTINUATION"] >= 5:
            if ema9[i] > ema21[i] and abs(l - ema21[i]) <= 0.35 * a and c > o and c > ema21[i]:
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HB_LONG_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_B_PULLBACK_CONTINUATION",
                    direction="LONG", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"dist_to_ema21": float(abs(l - ema21[i]) / a)}
                ))
                last_event_bar["HYPOTHESIS_B_PULLBACK_CONTINUATION"] = i

            elif ema9[i] < ema21[i] and abs(h - ema21[i]) <= 0.35 * a and c < o and c < ema21[i]:
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HB_SHORT_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_B_PULLBACK_CONTINUATION",
                    direction="SHORT", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"dist_to_ema21": float(abs(h - ema21[i]) / a)}
                ))
                last_event_bar["HYPOTHESIS_B_PULLBACK_CONTINUATION"] = i

        # ---------------------------------------------------------------------
        # HYPOTHESIS C: RANGE MEAN REVERSION
        # Range compressed, price at range extreme, rejection candle toward midpoint
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_C_RANGE_MEAN_REVERSION"] >= 5:
            if comp[i] < 1.15:
                # Reversal from range high
                if r_pos[i] >= 0.85 and c < o and (h - max(c, o)) >= 0.3 * (h - l):
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HC_SHORT_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_C_RANGE_MEAN_REVERSION",
                        direction="SHORT", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"range_position": float(r_pos[i]), "compression": float(comp[i])}
                    ))
                    last_event_bar["HYPOTHESIS_C_RANGE_MEAN_REVERSION"] = i

                # Reversal from range low
                elif r_pos[i] <= 0.15 and c > o and (min(c, o) - l) >= 0.3 * (h - l):
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HC_LONG_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_C_RANGE_MEAN_REVERSION",
                        direction="LONG", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"range_position": float(r_pos[i]), "compression": float(comp[i])}
                    ))
                    last_event_bar["HYPOTHESIS_C_RANGE_MEAN_REVERSION"] = i

        # ---------------------------------------------------------------------
        # HYPOTHESIS D: BREAKOUT FOLLOW-THROUGH
        # Established range, confirmed close outside range, ATR expanding
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH"] >= 5:
            if comp[i] < 1.20 and close[i - 1] <= r_high[i] and c > r_high[i]:
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HD_LONG_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH",
                    direction="LONG", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"breakout_dist": float((c - r_high[i]) / a)}
                ))
                last_event_bar["HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH"] = i

            elif comp[i] < 1.20 and close[i - 1] >= r_low[i] and c < r_low[i]:
                events.append(HorizonEvent(
                    setup_id=f"{symbol}_HD_SHORT_{dt_str}",
                    symbol=symbol, timestamp=dt, bar_index=i,
                    hypothesis="HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH",
                    direction="SHORT", entry_price=round(float(c), 2),
                    atr=round(float(a), 2), regime=str(prim_regime[i]),
                    session_regime=str(sess_regime[i]),
                    features={"breakout_dist": float((r_low[i] - c) / a)}
                ))
                last_event_bar["HYPOTHESIS_D_BREAKOUT_FOLLOW_THROUGH"] = i

        # ---------------------------------------------------------------------
        # HYPOTHESIS E: OPENING SESSION MOMENTUM
        # 09:30 to 10:15 window: strong net directional return from open
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_E_OPENING_SESSION_MOMENTUM"] >= 5:
            t_open_start = pd.Timestamp("09:30:00").time()
            t_open_finish = pd.Timestamp("10:15:00").time()
            if t_open_start <= t_curr <= t_open_finish:
                ret_5m = float(df_feat["return_5m"].iloc[i])
                if ret_5m >= 0.003 and c > ema9[i]:
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HE_LONG_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_E_OPENING_SESSION_MOMENTUM",
                        direction="LONG", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"return_5m": ret_5m}
                    ))
                    last_event_bar["HYPOTHESIS_E_OPENING_SESSION_MOMENTUM"] = i

                elif ret_5m <= -0.003 and c < ema9[i]:
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HE_SHORT_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_E_OPENING_SESSION_MOMENTUM",
                        direction="SHORT", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"return_5m": ret_5m}
                    ))
                    last_event_bar["HYPOTHESIS_E_OPENING_SESSION_MOMENTUM"] = i

        # ---------------------------------------------------------------------
        # HYPOTHESIS F: VOLATILITY EXPANSION
        # Compression broken by sudden expansion candle (range >= 1.25 ATR, body >= 0.6 range)
        # ---------------------------------------------------------------------
        if i - last_event_bar["HYPOTHESIS_F_VOLATILITY_EXPANSION"] >= 5:
            if comp[i] < 1.05 and (h - l) >= 1.25 * a and body_ratio[i] >= 0.60:
                if c > o:
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HF_LONG_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_F_VOLATILITY_EXPANSION",
                        direction="LONG", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"candle_range_atr": float((h - l) / a)}
                    ))
                    last_event_bar["HYPOTHESIS_F_VOLATILITY_EXPANSION"] = i
                else:
                    events.append(HorizonEvent(
                        setup_id=f"{symbol}_HF_SHORT_{dt_str}",
                        symbol=symbol, timestamp=dt, bar_index=i,
                        hypothesis="HYPOTHESIS_F_VOLATILITY_EXPANSION",
                        direction="SHORT", entry_price=round(float(c), 2),
                        atr=round(float(a), 2), regime=str(prim_regime[i]),
                        session_regime=str(sess_regime[i]),
                        features={"candle_range_atr": float((h - l) / a)}
                    ))
                    last_event_bar["HYPOTHESIS_F_VOLATILITY_EXPANSION"] = i

    return events


def evaluate_forward_horizons(
    events: List[HorizonEvent],
    df: pd.DataFrame,
    fixed_capital_risk: float = 1000.0
) -> None:
    """
    For each event and each horizon H in [5, 15, 30, 60, 120]:
    Computes forward return, MFE, MAE, excursion ratios, probability metrics,
    and simulated trade P&L across cost multipliers.
    
    STRICT RESEARCH PURPOSE: Modifies event.horizons for empirical evaluation.
    """
    n = len(df)
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    close = df["Close"].to_numpy()
    dts = df.index
    dates = df.index.date
    eod_times = df.index.time >= pd.Timestamp("15:15:00").time()

    for ev in events:
        idx = ev.bar_index
        entry = ev.entry_price
        direction = ev.direction
        atr = ev.atr
        curr_date = dates[idx]

        # Sizing by fixed capital risk (1.5 * ATR)
        risk_per_share = max(1.5 * atr, 0.5)
        qty = max(int(fixed_capital_risk / risk_per_share), 1)

        for h in HORIZONS:
            # End index for horizon holding
            target_idx = min(idx + h, n - 1)

            # Restrict to same trading day and before 15:15 EOD square-off
            actual_end_idx = target_idx
            if dates[target_idx] != curr_date or eod_times[target_idx]:
                for j in range(idx + 1, target_idx + 1):
                    if dates[j] != curr_date or eod_times[j]:
                        actual_end_idx = j
                        break

            exit_dt = dts[actual_end_idx]
            exit_price = float(close[actual_end_idx])

            # Forward window slice [idx + 1 : actual_end_idx + 1]
            sub_h = high[idx + 1 : actual_end_idx + 1]
            sub_l = low[idx + 1 : actual_end_idx + 1]

            if len(sub_h) == 0:
                sub_h = np.array([entry])
                sub_l = np.array([entry])

            if direction == "LONG":
                ret_pct = float((exit_price - entry) / entry) * 100.0
                mfe_val = float(np.max(sub_h) - entry)
                mae_val = float(entry - np.min(sub_l))
                time_mfe = int(np.argmax(sub_h) + 1)
                time_mae = int(np.argmin(sub_l) + 1)
                gross_pnl = float((exit_price - entry) * qty)
            else:  # SHORT
                ret_pct = float((entry - exit_price) / entry) * 100.0
                mfe_val = float(entry - np.min(sub_l))
                mae_val = float(np.max(sub_h) - entry)
                time_mfe = int(np.argmin(sub_l) + 1)
                time_mae = int(np.argmax(sub_h) + 1)
                gross_pnl = float((entry - exit_price) * qty)

            mfe_atr = mfe_val / atr
            mae_atr = mae_val / atr
            ret_atr = (exit_price - entry) / atr if direction == "LONG" else (entry - exit_price) / atr
            vol_adj_ret = ret_pct / (atr / entry * 100.0) if atr > 0 else 0.0

            exc_ratio = mfe_val / max(mae_val, 0.01)

            # Transaction costs (Zerodha ₹20 flat + 0.05% turnover)
            turnover = float((entry + exit_price) * qty)
            base_cost = 20.0 + (turnover * 0.0005)
            net_1_0x = gross_pnl - base_cost
            net_1_5x = gross_pnl - (base_cost * 1.5)
            net_2_0x = gross_pnl - (base_cost * 2.0)

            ev.horizons[h] = HorizonOutcome(
                horizon_minutes=h,
                exit_datetime=exit_dt,
                exit_price=round(exit_price, 2),
                forward_return_pct=round(ret_pct, 3),
                mfe_price=round(mfe_val, 2),
                mfe_atr=round(mfe_atr, 2),
                mae_price=round(mae_val, 2),
                mae_atr=round(mae_atr, 2),
                return_over_atr=round(ret_atr, 3),
                vol_adjusted_return=round(vol_adj_ret, 3),
                time_to_mfe=time_mfe,
                time_to_mae=time_mae,
                prob_positive=1 if ret_pct > 0 else 0,
                reach_plus_05_atr=1 if mfe_atr >= 0.5 else 0,
                reach_plus_10_atr=1 if mfe_atr >= 1.0 else 0,
                reach_plus_15_atr=1 if mfe_atr >= 1.5 else 0,
                reach_minus_05_atr=1 if mae_atr >= 0.5 else 0,
                reach_minus_10_atr=1 if mae_atr >= 1.0 else 0,
                excursion_ratio=round(exc_ratio, 2),
                gross_pnl=round(gross_pnl, 2),
                turnover=round(turnover, 2),
                base_cost=round(base_cost, 2),
                net_pnl_1_0x=round(net_1_0x, 2),
                net_pnl_1_5x=round(net_1_5x, 2),
                net_pnl_2_0x=round(net_2_0x, 2),
            )

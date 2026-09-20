"""
SignalForge — Phase 6: Risk & Execution Engine
===============================================
File: src/strategy/risk_engine.py

Calculates risk geometry, stop-loss, profit-target, and position sizing.
Simulates realistic trade lifecycle without look-ahead bias:
- Intraday forward step-through until Target hit, Stop hit, or EOD exit (15:15).
- Realistic transaction cost model: Rs. 20 flat brokerage + 0.05% turnover.
- Slippage stress testing support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class TradeResult:
    symbol: str
    setup_name: str
    market_state: str
    direction: str
    quality_score: float
    confidence_tier: str
    entry_datetime: pd.Timestamp
    exit_datetime: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    planned_rr: float
    quantity: int
    exit_reason: str  # TARGET, STOP, EOD
    gross_pnl: float
    costs: float
    net_pnl: float
    holding_minutes: int
    pillar_scores: Dict[str, float]


def calculate_risk_reward(
    entry_price: float,
    direction: str,
    atr: float,
    stop_mult: float = 1.5,
    rr_ratio: float = 1.5
) -> Dict[str, float]:
    """Calculates entry, stop, target, risk, reward, and reward/risk ratio."""
    risk_distance = max(atr * stop_mult, 0.5)
    reward_distance = risk_distance * rr_ratio

    if direction == "LONG":
        stop_price = round(entry_price - risk_distance, 2)
        target_price = round(entry_price + reward_distance, 2)
    else:  # SHORT
        stop_price = round(entry_price + risk_distance, 2)
        target_price = round(entry_price - reward_distance, 2)

    return {
        "entry_price": round(entry_price, 2),
        "stop_price": stop_price,
        "target_price": target_price,
        "risk_distance": round(risk_distance, 2),
        "reward_distance": round(reward_distance, 2),
        "reward_risk_ratio": round(rr_ratio, 2),
    }


def simulate_trade(
    symbol: str,
    setup_name: str,
    market_state: str,
    direction: str,
    entry_idx: int,
    df: pd.DataFrame,
    quality_score: float,
    confidence_tier: str,
    pillar_scores: Dict[str, float],
    stop_mult: float = 1.5,
    rr_ratio: float = 1.5,
    cost_multiplier: float = 1.0,
    slippage_pct: float = 0.0,
    fixed_capital_risk: float = 1000.0  # Rs. 1,000 risk per trade
) -> Optional[TradeResult]:
    """
    Simulates a trade forward in time starting at candle entry_idx.
    Strictly causal: uses subsequent candles to evaluate target/stop/EOD.
    """
    if entry_idx >= len(df) - 1:
        return None

    # Cache numpy arrays and session metadata on df for high-throughput execution
    if "_np_high" not in df.attrs:
        df.attrs["_np_high"] = df["High"].to_numpy()
        df.attrs["_np_low"] = df["Low"].to_numpy()
        df.attrs["_np_close"] = df["Close"].to_numpy()
        df.attrs["_np_dt"] = df.index.to_numpy()
        df.attrs["_np_dates"] = df.index.date
        df.attrs["_np_eod"] = df.index.time >= pd.Timestamp("15:15:00").time()
        df.attrs["_np_atr"] = df["atr14"].to_numpy()

    dt_arr = df.attrs["_np_dt"]
    close_arr = df.attrs["_np_close"]
    atr_arr = df.attrs["_np_atr"]
    high_arr = df.attrs["_np_high"]
    low_arr = df.attrs["_np_low"]
    dates_arr = df.attrs["_np_dates"]
    eod_arr = df.attrs["_np_eod"]

    entry_dt = pd.Timestamp(dt_arr[entry_idx])
    entry_price = float(close_arr[entry_idx])
    atr = float(atr_arr[entry_idx])

    # Enforce trading session: entries allowed only between 09:20 and 14:45
    t_entry = entry_dt.time()
    t_start = pd.Timestamp("09:20:00").time()
    t_cutoff = pd.Timestamp("14:45:00").time()
    if t_entry < t_start or t_entry >= t_cutoff:
        return None

    rr_geom = calculate_risk_reward(entry_price, direction, atr, stop_mult, rr_ratio)
    stop_p = rr_geom["stop_price"]
    target_p = rr_geom["target_price"]
    risk_dist = rr_geom["risk_distance"]

    if risk_dist <= 0:
        return None

    # Position sizing: Risk Rs. 1,000 per trade
    qty = max(int(fixed_capital_risk / risk_dist), 1)

    exit_price = entry_price
    exit_dt = entry_dt
    exit_reason = "EOD"

    # Step forward until hit or end of trading day (15:15)
    entry_date = dates_arr[entry_idx]
    max_idx = min(entry_idx + 380, len(df))

    for curr_idx in range(entry_idx + 1, max_idx):
        if dates_arr[curr_idx] != entry_date or eod_arr[curr_idx]:
            # End of day square-off
            exit_price = float(close_arr[curr_idx])
            exit_dt = pd.Timestamp(dt_arr[curr_idx])
            exit_reason = "EOD"
            break

        c_high = high_arr[curr_idx]
        c_low = low_arr[curr_idx]

        if direction == "LONG":
            # Check stop first (conservative)
            if c_low <= stop_p:
                exit_price = stop_p
                exit_dt = pd.Timestamp(dt_arr[curr_idx])
                exit_reason = "STOP"
                break
            elif c_high >= target_p:
                exit_price = target_p
                exit_dt = pd.Timestamp(dt_arr[curr_idx])
                exit_reason = "TARGET"
                break
        else:  # SHORT
            if c_high >= stop_p:
                exit_price = stop_p
                exit_dt = pd.Timestamp(dt_arr[curr_idx])
                exit_reason = "STOP"
                break
            elif c_low <= target_p:
                exit_price = target_p
                exit_dt = pd.Timestamp(dt_arr[curr_idx])
                exit_reason = "TARGET"
                break

    # P&L calculation
    if direction == "LONG":
        gross_pnl = (exit_price - entry_price) * qty
    else:
        gross_pnl = (entry_price - exit_price) * qty

    # Costs: Zerodha model (Rs. 20 flat brokerage + 0.05% turnover)
    turnover = (entry_price + exit_price) * qty
    base_cost = 20.0 + (turnover * 0.0005)
    slippage = turnover * slippage_pct
    total_costs = (base_cost * cost_multiplier) + slippage
    net_pnl = gross_pnl - total_costs

    holding_minutes = int((exit_dt - entry_dt).total_seconds() / 60.0)

    return TradeResult(
        symbol=symbol,
        setup_name=setup_name,
        market_state=market_state,
        direction=direction,
        quality_score=quality_score,
        confidence_tier=confidence_tier,
        entry_datetime=entry_dt,
        exit_datetime=exit_dt,
        entry_price=round(entry_price, 2),
        exit_price=round(exit_price, 2),
        stop_price=round(stop_p, 2),
        target_price=round(target_p, 2),
        planned_rr=round(rr_ratio, 2),
        quantity=qty,
        exit_reason=exit_reason,
        gross_pnl=round(gross_pnl, 2),
        costs=round(total_costs, 2),
        net_pnl=round(net_pnl, 2),
        holding_minutes=max(holding_minutes, 1),
        pillar_scores=pillar_scores
    )

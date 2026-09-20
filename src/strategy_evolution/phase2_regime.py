"""
SignalForge — Strategy Evolution Phase 2: Market Regime & Momentum Filters
==========================================================================
File: src/strategy_evolution/phase2_regime.py

Implements the experimental Phase 2 framework to evaluate whether causal
regime (ADX) and momentum/trend strength (normalized EMA distance) filters
reduce 1-minute EMA crossover noise and overtrading without HTF phase lag.

Variants:
- Variant 0: Baseline Control (1m 9/21 EMA crossover + RSI(14) >= 50 / <= 50)
- Variant 1: ADX Regime Filter (ADX(14) >= 20)
- Variant 2: ADX Strong Regime Filter (ADX(14) >= 25)
- Variant 3: EMA Distance Filter (Normalized EMA(9)-EMA(21) distance >= 0.00005, i.e. 0.5 bps)
- Variant 4: ADX + EMA Distance (ADX >= 20 AND Normalized EMA distance >= 0.00005)

Execution & Accounting:
- 1% risk position sizing
- 1.5 ATR Stop Loss, 3.0 ATR Target
- ₹20 Brokerage + 0.05% Slippage
- Single active position per symbol
- Strictly causal indicators calculated on current/past 1-minute bars only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np
import pandas as pd


VariantType = Literal[
    "baseline",
    "adx20",
    "adx25",
    "ema_distance",
    "adx20_ema_distance",
]

# Clearly documented fixed threshold for normalized EMA distance: 0.5 basis points (0.005% of price)
DEFAULT_EMA_DIST_THRESHOLD: float = 0.00005


@dataclass(frozen=True)
class Phase2Config:
    name: str = "BASELINE"
    description: str = "Baseline Control: 1m 9/21 EMA + RSI(14)"
    variant: VariantType = "baseline"
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    adx_period: int = 14
    adx_threshold: float = 20.0
    ema_dist_threshold: float = DEFAULT_EMA_DIST_THRESHOLD
    stop_atr: float = 1.5
    target_atr: float = 3.0
    risk_per_trade: float = 0.01
    brokerage_per_trade: float = 20.0
    slippage: float = 0.0005
    initial_capital: float = 100000.0


def calculate_phase2_indicators(
    df_raw: pd.DataFrame,
    config: Optional[Phase2Config] = None,
) -> dict:
    """Precomputes strictly causal 1-minute indicators: EMA9, EMA21, RSI(14), ATR(14), ADX(14), and Normalized EMA Distance."""
    if config is None:
        config = Phase2Config()

    df = df_raw.copy()
    df["dt"] = pd.to_datetime(df["Date"])

    # 1. 1-minute EMA 9 and 21
    df["EMA9"] = df["Close"].ewm(span=config.fast_ema, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=config.slow_ema, adjust=False).mean()

    # 2. 1-minute RSI(14)
    delta = df["Close"].diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / config.rsi_period, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / config.rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 3. 1-minute True Range & ATR(14)
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(config.atr_period).mean()

    # 4. 1-minute Wilder's ADX(14)
    up_move = df["High"] - df["High"].shift(1)
    down_move = df["Low"].shift(1) - df["Low"]
    pos_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    neg_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr_smooth = tr.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()
    pos_dm_smooth = pos_dm.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()
    neg_dm_smooth = neg_dm.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()

    pos_di = 100 * (pos_dm_smooth / tr_smooth.replace(0, np.nan))
    neg_di = 100 * (neg_dm_smooth / tr_smooth.replace(0, np.nan))
    di_sum = pos_di + neg_di
    dx = (100 * ((pos_di - neg_di).abs() / di_sum.replace(0, np.nan))).fillna(0.0)
    df["ADX"] = dx.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()

    # 5. Normalized EMA Distance
    df["EMA_DIST"] = (df["EMA9"] - df["EMA21"]).abs() / df["Close"]

    timestamps = (df["dt"] - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64").to_numpy()

    return {
        "df": df,
        "highs": df["High"].to_numpy(),
        "lows": df["Low"].to_numpy(),
        "closes": df["Close"].to_numpy(),
        "atrs": df["ATR"].to_numpy(),
        "ema9": df["EMA9"].to_numpy(),
        "ema21": df["EMA21"].to_numpy(),
        "rsis": df["RSI"].to_numpy(),
        "adxs": df["ADX"].to_numpy(),
        "ema_dists": df["EMA_DIST"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_phase2_symbol(
    symbol: str,
    data: dict,
    config: Phase2Config,
) -> tuple[list[dict], list[dict]]:
    """Simulates a single symbol under the given Phase 2 configuration.

    Returns:
        trades: list of executed trade records.
        filtered_signals: list of rejected crossover signals with diagnostic attributes.
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    adxs = data["adxs"]
    ema_dists = data["ema_dists"]
    dates = data["dates"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    trades = []
    filtered_signals = []

    warmup = max(config.slow_ema, config.rsi_period, config.atr_period) + 2

    for i in range(1, n):
        # 1. Manage open position
        if position is not None:
            side = position["side"]
            entry = position["entry_price"]
            stop = position["stop_price"]
            target = position["target_price"]
            exit_price = None
            exit_reason = None

            if side == "LONG":
                if lows[i] <= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif highs[i] >= target:
                    exit_price = target
                    exit_reason = "TARGET"
            else:
                if highs[i] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif lows[i] <= target:
                    exit_price = target
                    exit_reason = "TARGET"

            if exit_price is not None:
                if side == "LONG":
                    gross_pnl = (exit_price - entry) * position["quantity"]
                else:
                    gross_pnl = (entry - exit_price) * position["quantity"]

                costs = config.brokerage_per_trade + (
                    abs(exit_price - entry) * position["quantity"] * config.slippage
                )
                net_pnl = gross_pnl - costs
                capital += net_pnl

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "quantity": position["quantity"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                })
                position = None
                continue

        # 2. Check entry signal if flat
        if position is None and i < n - 1 and i >= warmup:
            # 1-minute EMA 9 / 21 crossover
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                adx_val = adxs[i]
                dist_val = ema_dists[i]
                filter_pass = True
                filter_reason = "PASS"

                if config.variant == "baseline":
                    filter_pass = True
                elif config.variant == "adx20":
                    if np.isnan(adx_val) or adx_val < 20.0:
                        filter_pass = False
                        filter_reason = "ADX_BELOW_20"
                elif config.variant == "adx25":
                    if np.isnan(adx_val) or adx_val < 25.0:
                        filter_pass = False
                        filter_reason = "ADX_BELOW_25"
                elif config.variant == "ema_distance":
                    if np.isnan(dist_val) or dist_val < config.ema_dist_threshold:
                        filter_pass = False
                        filter_reason = "EMA_DIST_BELOW_THRESH"
                elif config.variant == "adx20_ema_distance":
                    if np.isnan(adx_val) or adx_val < 20.0:
                        filter_pass = False
                        filter_reason = "ADX_BELOW_20"
                    elif np.isnan(dist_val) or dist_val < config.ema_dist_threshold:
                        filter_pass = False
                        filter_reason = "EMA_DIST_BELOW_THRESH"

                if not filter_pass:
                    filtered_signals.append({
                        "symbol": symbol,
                        "datetime": dates[i],
                        "direction": signal,
                        "adx": round(float(adx_val), 2) if not np.isnan(adx_val) else np.nan,
                        "ema9": round(float(ema9[i]), 2),
                        "ema21": round(float(ema21[i]), 2),
                        "ema_distance": round(float(dist_val), 6) if not np.isnan(dist_val) else np.nan,
                        "price": round(float(closes[i]), 2),
                        "filter_result": filter_reason,
                    })
                    continue

                # Sizing & Position setup
                atr = atrs[i]
                if np.isnan(atr) or atr <= 0:
                    continue

                entry_price = closes[i]
                risk_amount = capital * config.risk_per_trade
                risk_per_share = atr * config.stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                if signal == "LONG":
                    stop = entry_price - atr * config.stop_atr
                    target = entry_price + atr * config.target_atr
                else:
                    stop = entry_price + atr * config.stop_atr
                    target = entry_price - atr * config.target_atr

                position = {
                    "side": signal,
                    "entry_time": dates[i],
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                }

    # 3. Year-end square-off if position remains open
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]

        if side == "LONG":
            gross_pnl = (last_close - entry) * position["quantity"]
        else:
            gross_pnl = (entry - last_close) * position["quantity"]

        costs = config.brokerage_per_trade + (
            abs(last_close - entry) * position["quantity"] * config.slippage
        )
        net_pnl = gross_pnl - costs
        capital += net_pnl

        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_price": entry,
            "exit_price": last_close,
            "quantity": position["quantity"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
        })

    return trades, filtered_signals

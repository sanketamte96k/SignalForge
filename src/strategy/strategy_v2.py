"""
SignalForge — Strategy V2 (Trend + Regime + Cooldown) Module
============================================================
File: src/strategy/strategy_v2.py

Implements Strategy V2 variants in an isolated, pure strategy layer:
- Baseline control: 1m 9/21 EMA crossover + RSI(14) >= 50 / <= 50
- V2-A: Baseline + Causal 15-minute 9/21 EMA Higher-Timeframe Trend confirmation
- V2-B: V2-A + Sideways / Regime Filter (ADX(14) >= 15 and crossover consolidation protection)
- V2-C: V2-B + Post-Trade Cooldown (10 minutes)
- V2-D: Baseline + Regime Filter (ADX(14) >= 15) + Post-Trade Cooldown (10 minutes, zero HTF lag)

Guarantees:
- Zero look-ahead bias: HTF candles available strictly at T + timeframe.
- Exact mechanical execution: 1.5 ATR stop, 3.0 ATR target, 1% risk sizing, ₹20 brokerage, 0.05% slippage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VariantConfig:
    name: str
    description: str
    use_htf_15m: bool = False
    min_adx: float = 0.0
    max_crossover_20: Optional[int] = None
    cooldown_minutes: int = 0


VARIANTS = {
    "BASELINE": VariantConfig(
        name="BASELINE",
        description="Locked 1-minute 9/21 EMA crossover with RSI(14) filter (Control Group)",
        use_htf_15m=False,
        min_adx=0.0,
        max_crossover_20=None,
        cooldown_minutes=0,
    ),
    "V2-A": VariantConfig(
        name="V2-A",
        description="1m EMA crossover + Causal 15-minute 9/21 EMA Higher-Timeframe Trend filter",
        use_htf_15m=True,
        min_adx=0.0,
        max_crossover_20=None,
        cooldown_minutes=0,
    ),
    "V2-B": VariantConfig(
        name="V2-B",
        description="V2-A + Regime / Sideways filter (ADX >= 15 and consolidation protection)",
        use_htf_15m=True,
        min_adx=15.0,
        max_crossover_20=2,
        cooldown_minutes=0,
    ),
    "V2-C": VariantConfig(
        name="V2-C",
        description="V2-B + Post-trade cooldown (10 minutes)",
        use_htf_15m=True,
        min_adx=15.0,
        max_crossover_20=2,
        cooldown_minutes=10,
    ),
    "V2-D": VariantConfig(
        name="V2-D",
        description="Regime Filter (ADX >= 15) + Cooldown (10 minutes) without HTF lag",
        use_htf_15m=False,
        min_adx=15.0,
        max_crossover_20=None,
        cooldown_minutes=10,
    ),
}

INITIAL_CAPITAL = 100000.0
FAST_EMA = 9
SLOW_EMA = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
STOP_ATR = 1.5
TARGET_ATR = 3.0
RISK_PER_TRADE = 0.01
SLIPPAGE = 0.0005
BROKERAGE_PER_TRADE = 20.0


def compute_v2_indicators(df_raw: pd.DataFrame) -> dict:
    """Computes all causal 1m and HTF indicators for a symbol."""
    df = df_raw.copy()
    df["dt"] = pd.to_datetime(df["Date"])

    # 1. 1-minute EMA 9 and 21
    df["EMA9"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # 2. 1-minute RSI(14)
    delta = df["Close"].diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / RSI_PERIOD, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 3. 1-minute True Range & ATR(14)
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(ATR_PERIOD).mean()

    # 4. 1-minute ADX(14) (Wilder's formulation)
    up_move = df["High"] - df["High"].shift(1)
    down_move = df["Low"].shift(1) - df["Low"]
    pos_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    neg_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr_smooth = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False).mean()
    pos_dm_smooth = pos_dm.ewm(alpha=1.0 / ATR_PERIOD, adjust=False).mean()
    neg_dm_smooth = neg_dm.ewm(alpha=1.0 / ATR_PERIOD, adjust=False).mean()

    pos_di = 100 * (pos_dm_smooth / tr_smooth.replace(0, np.nan))
    neg_di = 100 * (neg_dm_smooth / tr_smooth.replace(0, np.nan))
    di_sum = pos_di + neg_di
    dx = (100 * ((pos_di - neg_di).abs() / di_sum.replace(0, np.nan))).fillna(0.0)
    df["ADX"] = dx.ewm(alpha=1.0 / ATR_PERIOD, adjust=False).mean()

    # 5. Crossover count in the last 20 bars (consolidation / chop protection)
    crossover = (
        ((df["EMA9"].shift(1) <= df["EMA21"].shift(1)) & (df["EMA9"] > df["EMA21"]))
        | ((df["EMA9"].shift(1) >= df["EMA21"].shift(1)) & (df["EMA9"] < df["EMA21"]))
    )
    df["crossover_count_20"] = crossover.astype(int).rolling(20).sum()

    # 6. Causal 15-minute Higher Timeframe Resampling
    df_indexed = df.set_index("dt")
    df_15m = (
        df_indexed.resample("15min", origin="start", closed="left", label="left")
        .agg({"Close": "last"})
        .dropna()
    )
    df_15m["EMA9_15"] = df_15m["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df_15m["EMA21_15"] = df_15m["Close"].ewm(span=SLOW_EMA, adjust=False).mean()
    df_15m["available_at"] = df_15m.index + pd.Timedelta(minutes=15)

    merged = pd.merge_asof(
        df.sort_values("dt"),
        df_15m[["available_at", "EMA9_15", "EMA21_15"]],
        left_on="dt",
        right_on="available_at",
        direction="backward",
    )
    df["EMA9_15"] = merged["EMA9_15"]
    df["EMA21_15"] = merged["EMA21_15"]

    # Timestamps in Unix seconds
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
        "adx": df["ADX"].to_numpy(),
        "crossover_20": df["crossover_count_20"].to_numpy(),
        "ema9_15": df["EMA9_15"].to_numpy(),
        "ema21_15": df["EMA21_15"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_strategy_variant(
    symbol: str,
    data: dict,
    config: VariantConfig,
) -> list[dict]:
    """Runs a single-symbol simulation under the given VariantConfig."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    adx = data["adx"]
    crossover_20 = data["crossover_20"]
    ema9_15 = data["ema9_15"]
    ema21_15 = data["ema21_15"]
    times = data["times"]
    dates = data["dates"]
    n = data["n"]

    cooldown_sec = config.cooldown_minutes * 60
    capital = INITIAL_CAPITAL
    position = None
    last_exit_time = -999999999
    trades = []

    warmup = max(SLOW_EMA, RSI_PERIOD, ATR_PERIOD) + 2

    for i in range(1, n):
        # 1. Manage existing open position
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

                costs = BROKERAGE_PER_TRADE + (abs(exit_price - entry) * position["quantity"] * SLIPPAGE)
                net_pnl = gross_pnl - costs
                capital += net_pnl
                last_exit_time = times[i]

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
                    "variant": config.name,
                })
                position = None
                continue

        # 2. Open new position if flat
        if position is None and i < n - 1 and i >= warmup:
            # Check cooldown
            if cooldown_sec > 0 and (times[i] - last_exit_time) < cooldown_sec:
                continue

            # 1-minute EMA 9 / 21 crossover
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50:
                signal = "SHORT"

            if signal is not None:
                # Higher-timeframe trend filter
                if config.use_htf_15m:
                    if signal == "LONG":
                        if np.isnan(ema9_15[i]) or ema9_15[i] <= ema21_15[i]:
                            continue
                    else:
                        if np.isnan(ema9_15[i]) or ema9_15[i] >= ema21_15[i]:
                            continue

                # Regime / Sideways filter (ADX)
                if config.min_adx > 0:
                    if np.isnan(adx[i]) or adx[i] < config.min_adx:
                        continue

                # Consolidation / Chop protection (recent crossover count)
                if config.max_crossover_20 is not None:
                    if not np.isnan(crossover_20[i]) and crossover_20[i] > config.max_crossover_20:
                        continue

                # Position sizing
                atr = atrs[i]
                if np.isnan(atr) or atr <= 0:
                    continue

                entry_price = closes[i]
                risk_amount = capital * RISK_PER_TRADE
                risk_per_share = atr * STOP_ATR
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                if signal == "LONG":
                    stop = entry_price - atr * STOP_ATR
                    target = entry_price + atr * TARGET_ATR
                else:
                    stop = entry_price + atr * STOP_ATR
                    target = entry_price - atr * TARGET_ATR

                position = {
                    "side": signal,
                    "entry_time": dates[i],
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                }

    # 3. Final dataset square-off if position remains open
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]

        if side == "LONG":
            gross_pnl = (last_close - entry) * position["quantity"]
        else:
            gross_pnl = (entry - last_close) * position["quantity"]

        costs = BROKERAGE_PER_TRADE + (abs(last_close - entry) * position["quantity"] * SLIPPAGE)
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
            "variant": config.name,
        })

    return trades

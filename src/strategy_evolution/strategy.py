"""
SignalForge — Strategy Evolution Phase 1: Higher-Timeframe Trend Filters
========================================================================
File: src/strategy_evolution/strategy.py

Implements the experimental strategy evolution pipeline testing HTF trend filters:
1. Baseline: No HTF filter (1m 9/21 EMA crossover + RSI(14) >= 50 / <= 50)
2. 15-Minute Trend Filter: LONG only when 15m EMA9 > EMA21; SHORT only when 15m EMA9 < EMA21
3. 30-Minute Trend Filter: LONG only when 30m EMA9 > EMA21; SHORT only when 30m EMA9 < EMA21
4. 15m + 30m Alignment: LONG only when both are bullish; SHORT only when both are bearish

Execution & Accounting:
- Conservative 1% risk position sizing
- 1.5 ATR Stop Loss, 3.0 ATR Target
- ₹20 Brokerage + 0.05% Slippage
- Single active position per symbol
- Strictly causal HTF candle resampling (candle [T, T+TF) available strictly at T + TF)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal
import numpy as np
import pandas as pd


VariantType = Literal["baseline", "trend_15m", "trend_30m", "trend_alignment"]


@dataclass(frozen=True)
class StrategyEvolutionConfig:
    name: str = "BASELINE"
    description: str = "Baseline: 1m 9/21 EMA + RSI(14)"
    variant: VariantType = "baseline"
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    stop_atr: float = 1.5
    target_atr: float = 3.0
    risk_per_trade: float = 0.01
    brokerage_per_trade: float = 20.0
    slippage: float = 0.0005
    initial_capital: float = 100000.0


def calculate_indicators_evolution(
    df_raw: pd.DataFrame,
    config: Optional[StrategyEvolutionConfig] = None,
) -> dict:
    """Precomputes causal 1m indicators and causal 15m & 30m HTF EMA indicators."""
    if config is None:
        config = StrategyEvolutionConfig()

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

    # 4. Causal 15-minute Higher-Timeframe Trend
    df_indexed = df.set_index("dt")
    df_15m = (
        df_indexed.resample("15min", origin="start", closed="left", label="left")
        .agg({"Close": "last"})
        .dropna()
    )
    df_15m["EMA9_15m"] = df_15m["Close"].ewm(span=config.fast_ema, adjust=False).mean()
    df_15m["EMA21_15m"] = df_15m["Close"].ewm(span=config.slow_ema, adjust=False).mean()
    df_15m["available_at"] = df_15m.index + pd.Timedelta(minutes=15)

    # 5. Causal 30-minute Higher-Timeframe Trend
    df_30m = (
        df_indexed.resample("30min", origin="start", closed="left", label="left")
        .agg({"Close": "last"})
        .dropna()
    )
    df_30m["EMA9_30m"] = df_30m["Close"].ewm(span=config.fast_ema, adjust=False).mean()
    df_30m["EMA21_30m"] = df_30m["Close"].ewm(span=config.slow_ema, adjust=False).mean()
    df_30m["available_at"] = df_30m.index + pd.Timedelta(minutes=30)

    # Backward as-of merge: candle at [T, T+TF) only available at T + TF
    m15 = pd.merge_asof(
        df.sort_values("dt"),
        df_15m[["available_at", "EMA9_15m", "EMA21_15m"]],
        left_on="dt",
        right_on="available_at",
        direction="backward",
    )
    m30 = pd.merge_asof(
        df.sort_values("dt"),
        df_30m[["available_at", "EMA9_30m", "EMA21_30m"]],
        left_on="dt",
        right_on="available_at",
        direction="backward",
    )

    df["EMA9_15m"] = m15["EMA9_15m"]
    df["EMA21_15m"] = m15["EMA21_15m"]
    df["EMA9_30m"] = m30["EMA9_30m"]
    df["EMA21_30m"] = m30["EMA21_30m"]

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
        "ema9_15m": df["EMA9_15m"].to_numpy(),
        "ema21_15m": df["EMA21_15m"].to_numpy(),
        "ema9_30m": df["EMA9_30m"].to_numpy(),
        "ema21_30m": df["EMA21_30m"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_strategy_evolution(
    symbol: str,
    data: dict,
    config: StrategyEvolutionConfig,
) -> list[dict]:
    """Runs single-symbol simulation under the specified StrategyEvolutionConfig."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    ema9_15m = data["ema9_15m"]
    ema21_15m = data["ema21_15m"]
    ema9_30m = data["ema9_30m"]
    ema21_30m = data["ema21_30m"]
    dates = data["dates"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    trades = []

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
                # Higher-timeframe trend filters
                if config.variant == "trend_15m":
                    if signal == "LONG":
                        if np.isnan(ema9_15m[i]) or ema9_15m[i] <= ema21_15m[i]:
                            continue
                    else:
                        if np.isnan(ema9_15m[i]) or ema9_15m[i] >= ema21_15m[i]:
                            continue

                elif config.variant == "trend_30m":
                    if signal == "LONG":
                        if np.isnan(ema9_30m[i]) or ema9_30m[i] <= ema21_30m[i]:
                            continue
                    else:
                        if np.isnan(ema9_30m[i]) or ema9_30m[i] >= ema21_30m[i]:
                            continue

                elif config.variant == "trend_alignment":
                    if signal == "LONG":
                        if (
                            np.isnan(ema9_15m[i])
                            or ema9_15m[i] <= ema21_15m[i]
                            or np.isnan(ema9_30m[i])
                            or ema9_30m[i] <= ema21_30m[i]
                        ):
                            continue
                    else:
                        if (
                            np.isnan(ema9_15m[i])
                            or ema9_15m[i] >= ema21_15m[i]
                            or np.isnan(ema9_30m[i])
                            or ema9_30m[i] >= ema21_30m[i]
                        ):
                            continue

                # Position sizing
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

    return trades

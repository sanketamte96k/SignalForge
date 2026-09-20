"""
SignalForge — Strategy V3 (Structural Entry Confirmation) Module
================================================================
File: src/strategy/strategy_v3.py

Implements Strategy V3 variants with structural confirmation filters:
- BASELINE: Locked 1m 9/21 EMA crossover + RSI(14)
- V2-D: Baseline + ADX(14) >= 15 + 10m post-trade cooldown (Best V2 benchmark)
- V3-A: V2-D + Volume confirmation (Current Volume >= 20-period rolling median)
- V3-B: V3-A + Intraday VWAP confirmation (Close > VWAP for LONG, Close < VWAP for SHORT)
- V3-C: V3-B + Breakout confirmation (Close > previous 20-bar High for LONG, Close < previous 20-bar Low for SHORT)
- V3-D: V3-B + ATR Volatility filter (ATR(14)/Close >= 20-period rolling median)

Strict Look-Ahead Bias Guarantees:
- VWAP resets causally at the beginning of each trading day (09:15 IST) using intraday bars up to current bar.
- 20-bar breakout levels strictly exclude the current bar via shift(1).
- Rolling medians (Volume, ATR ratio) use strictly causal historical windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VariantV3Config:
    name: str
    description: str
    use_adx_filter: bool = False
    adx_threshold: float = 15.0
    cooldown_minutes: int = 0
    use_volume_filter: bool = False
    volume_window: int = 20
    use_vwap_filter: bool = False
    use_breakout_filter: bool = False
    breakout_window: int = 20
    use_atr_vol_filter: bool = False
    atr_vol_window: int = 20


VARIANTS_V3 = {
    "BASELINE": VariantV3Config(
        name="BASELINE",
        description="Locked 1m 9/21 EMA crossover with RSI(14) filter (Control Group)",
        use_adx_filter=False,
        cooldown_minutes=0,
    ),
    "V2-D": VariantV3Config(
        name="V2-D",
        description="Baseline + ADX(14) >= 15 + 10-minute cooldown (V2 Benchmark)",
        use_adx_filter=True,
        adx_threshold=15.0,
        cooldown_minutes=10,
    ),
    "V3-A": VariantV3Config(
        name="V3-A",
        description="V2-D + Volume Confirmation (Volume >= 20-period rolling median)",
        use_adx_filter=True,
        adx_threshold=15.0,
        cooldown_minutes=10,
        use_volume_filter=True,
        volume_window=20,
    ),
    "V3-B": VariantV3Config(
        name="V3-B",
        description="V3-A + Intraday VWAP Confirmation (Close > VWAP for LONG, Close < VWAP for SHORT)",
        use_adx_filter=True,
        adx_threshold=15.0,
        cooldown_minutes=10,
        use_volume_filter=True,
        volume_window=20,
        use_vwap_filter=True,
    ),
    "V3-C": VariantV3Config(
        name="V3-C",
        description="V3-B + 20-bar Breakout Confirmation (Close > High20 for LONG, Close < Low20 for SHORT)",
        use_adx_filter=True,
        adx_threshold=15.0,
        cooldown_minutes=10,
        use_volume_filter=True,
        volume_window=20,
        use_vwap_filter=True,
        use_breakout_filter=True,
        breakout_window=20,
    ),
    "V3-D": VariantV3Config(
        name="V3-D",
        description="V3-B + ATR Volatility Filter (ATR/Close >= 20-period rolling median)",
        use_adx_filter=True,
        adx_threshold=15.0,
        cooldown_minutes=10,
        use_volume_filter=True,
        volume_window=20,
        use_vwap_filter=True,
        use_atr_vol_filter=True,
        atr_vol_window=20,
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


def compute_v3_indicators(df_raw: pd.DataFrame) -> dict:
    """Computes all causal 1m and structural indicators for a symbol."""
    df = df_raw.copy()
    df["dt"] = pd.to_datetime(df["Date"])
    df["date"] = df["dt"].dt.date

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

    # 5. Volume Confirmation: 20-period rolling median
    df["vol_med_20"] = df["Volume"].rolling(20).median()

    # 6. Intraday VWAP: Resetting daily at market open (09:15)
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    tp_v = typical_price * df["Volume"]
    df["cum_tpv"] = tp_v.groupby(df["date"]).cumsum()
    df["cum_vol"] = df["Volume"].groupby(df["date"]).cumsum()
    df["vwap"] = df["cum_tpv"] / df["cum_vol"].replace(0, np.nan)

    # 7. Breakout Levels: Previous 20-bar High and Low (strictly excluding current bar via shift(1))
    df["high_20"] = df["High"].shift(1).rolling(20).max()
    df["low_20"] = df["Low"].shift(1).rolling(20).min()

    # 8. ATR Volatility Ratio: ATR(14) / Close and its 20-period rolling median
    atr_ratio = df["ATR"] / df["Close"]
    df["atr_ratio"] = atr_ratio
    df["atr_med_20"] = atr_ratio.rolling(20).median()

    # Timestamps in Unix seconds
    timestamps = (df["dt"] - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64").to_numpy()

    return {
        "df": df,
        "highs": df["High"].to_numpy(),
        "lows": df["Low"].to_numpy(),
        "closes": df["Close"].to_numpy(),
        "volumes": df["Volume"].to_numpy(),
        "vol_med_20": df["vol_med_20"].to_numpy(),
        "vwap": df["vwap"].to_numpy(),
        "high_20": df["high_20"].to_numpy(),
        "low_20": df["low_20"].to_numpy(),
        "atr_ratio": df["atr_ratio"].to_numpy(),
        "atr_med_20": df["atr_med_20"].to_numpy(),
        "atrs": df["ATR"].to_numpy(),
        "ema9": df["EMA9"].to_numpy(),
        "ema21": df["EMA21"].to_numpy(),
        "rsis": df["RSI"].to_numpy(),
        "adx": df["ADX"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_strategy_v3_variant(
    symbol: str,
    data: dict,
    config: VariantV3Config,
) -> list[dict]:
    """Runs a single-symbol simulation under the given VariantV3Config."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    volumes = data["volumes"]
    vol_med_20 = data["vol_med_20"]
    vwap = data["vwap"]
    high_20 = data["high_20"]
    low_20 = data["low_20"]
    atr_ratio = data["atr_ratio"]
    atr_med_20 = data["atr_med_20"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    adx = data["adx"]
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

        # 2. Check entry signals if flat
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
                # 1. Regime filter (ADX)
                if config.use_adx_filter:
                    if np.isnan(adx[i]) or adx[i] < config.adx_threshold:
                        continue

                # 2. Volume confirmation filter
                if config.use_volume_filter:
                    if np.isnan(vol_med_20[i]) or volumes[i] < vol_med_20[i]:
                        continue

                # 3. Intraday VWAP confirmation filter
                if config.use_vwap_filter:
                    if np.isnan(vwap[i]):
                        continue
                    if signal == "LONG" and closes[i] <= vwap[i]:
                        continue
                    elif signal == "SHORT" and closes[i] >= vwap[i]:
                        continue

                # 4. Breakout confirmation filter
                if config.use_breakout_filter:
                    if signal == "LONG":
                        if np.isnan(high_20[i]) or closes[i] <= high_20[i]:
                            continue
                    elif signal == "SHORT":
                        if np.isnan(low_20[i]) or closes[i] >= low_20[i]:
                            continue

                # 5. ATR volatility filter
                if config.use_atr_vol_filter:
                    if np.isnan(atr_med_20[i]) or atr_ratio[i] <= atr_med_20[i]:
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

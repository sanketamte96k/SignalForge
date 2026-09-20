"""
SignalForge — Experimental Trend-Filtered Strategy (15m 20/50 EMA Filter + Cooldown)
=====================================================================================
File: src/strategy/experimental/trend_filtered_strategy.py

Implements the experimental strategy to reduce 1-minute EMA crossover noise and overtrading:
1. Entry trigger: 1-minute 9/21 EMA crossover
2. Higher-timeframe trend filter:
   - 15-minute candles derived from 1-minute data
   - 20 EMA and 50 EMA on 15-minute timeframe
   - LONG allowed only when 15m EMA20 > EMA50
   - SHORT allowed only when 15m EMA20 < EMA50
   - Fully closed 15m candle only (strictly causal backward merge at T+15m)
3. Momentum confirmation:
   - 1-minute RSI(14): LONG requires RSI >= 50; SHORT requires RSI <= 50
4. Avoid immediate crossover noise:
   - Fresh 9/21 crossover required
   - Configurable 5-minute post-trade cooldown after trade exit
5. Trading session filter:
   - No new entries during the final 15 minutes of trading session (>= 15:15 IST)
   - EOD exit behavior preserved
6. Conservative risk management:
   - Initial capital: ₹100,000 per symbol
   - Risk: 1% per trade
   - Stop Loss: 1.5 * ATR(14)
   - Target: 3.0 * ATR(14)
   - Brokerage: ₹20.00 per trade
   - Slippage: 0.05% of traded value
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

# Default Parameter Constants
FAST_EMA: int = 9
SLOW_EMA: int = 21
HTF_TIMEFRAME: str = "15min"
HTF_FAST_EMA: int = 20
HTF_SLOW_EMA: int = 50
RSI_PERIOD: int = 14
LONG_RSI_MIN: float = 50.0
SHORT_RSI_MAX: float = 50.0
COOLDOWN_MINUTES: int = 5
NO_ENTRY_FINAL_MINUTES: int = 15
STOP_ATR: float = 1.5
TARGET_ATR: float = 3.0
RISK_PER_TRADE: float = 0.01
BROKERAGE_PER_TRADE: float = 20.0
SLIPPAGE: float = 0.0005
INITIAL_CAPITAL: float = 100000.0


@dataclass(frozen=True)
class ExperimentalStrategyConfig:
    fast_ema: int = FAST_EMA
    slow_ema: int = SLOW_EMA
    htf_timeframe: str = HTF_TIMEFRAME
    htf_fast_ema: int = HTF_FAST_EMA
    htf_slow_ema: int = HTF_SLOW_EMA
    rsi_period: int = RSI_PERIOD
    long_rsi_min: float = LONG_RSI_MIN
    short_rsi_max: float = SHORT_RSI_MAX
    cooldown_minutes: int = COOLDOWN_MINUTES
    no_entry_final_minutes: int = NO_ENTRY_FINAL_MINUTES
    stop_atr: float = STOP_ATR
    target_atr: float = TARGET_ATR
    risk_per_trade: float = RISK_PER_TRADE
    brokerage_per_trade: float = BROKERAGE_PER_TRADE
    slippage: float = SLIPPAGE
    initial_capital: float = INITIAL_CAPITAL


def calculate_experimental_indicators(
    df_raw: pd.DataFrame,
    config: Optional[ExperimentalStrategyConfig] = None,
) -> dict:
    """Precomputes 1m causal indicators and causal 15m HTF 20/50 EMA."""
    if config is None:
        config = ExperimentalStrategyConfig()

    df = df_raw.copy()
    df["dt"] = pd.to_datetime(df["Date"])

    # 1. 1-minute EMA 9 and 21
    df["EMA_FAST"] = df["Close"].ewm(span=config.fast_ema, adjust=False).mean()
    df["EMA_SLOW"] = df["Close"].ewm(span=config.slow_ema, adjust=False).mean()

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
    df["ATR"] = tr.rolling(14).mean()

    # 4. Causal 15-minute Higher-Timeframe Resampling & 20/50 EMA
    df_indexed = df.set_index("dt")
    df_htf = (
        df_indexed.resample(config.htf_timeframe, origin="start", closed="left", label="left")
        .agg({"Close": "last"})
        .dropna()
    )
    df_htf["EMA_FAST_HTF"] = df_htf["Close"].ewm(span=config.htf_fast_ema, adjust=False).mean()
    df_htf["EMA_SLOW_HTF"] = df_htf["Close"].ewm(span=config.htf_slow_ema, adjust=False).mean()

    # Available time: candle completes strictly 15 minutes after start
    df_htf["available_at"] = df_htf.index + pd.Timedelta(minutes=15)

    merged = pd.merge_asof(
        df.sort_values("dt"),
        df_htf[["available_at", "EMA_FAST_HTF", "EMA_SLOW_HTF"]],
        left_on="dt",
        right_on="available_at",
        direction="backward",
    )
    df["EMA_FAST_HTF"] = merged["EMA_FAST_HTF"]
    df["EMA_SLOW_HTF"] = merged["EMA_SLOW_HTF"]

    timestamps = (df["dt"] - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64").to_numpy()
    times_of_day = df["dt"].dt.time.to_numpy()
    session_cutoff_time = pd.to_datetime("15:15:00").time()

    return {
        "df": df,
        "highs": df["High"].to_numpy(),
        "lows": df["Low"].to_numpy(),
        "closes": df["Close"].to_numpy(),
        "atrs": df["ATR"].to_numpy(),
        "ema_fast": df["EMA_FAST"].to_numpy(),
        "ema_slow": df["EMA_SLOW"].to_numpy(),
        "rsis": df["RSI"].to_numpy(),
        "ema_fast_htf": df["EMA_FAST_HTF"].to_numpy(),
        "ema_slow_htf": df["EMA_SLOW_HTF"].to_numpy(),
        "times": timestamps,
        "times_of_day": times_of_day,
        "cutoff_time": session_cutoff_time,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def backtest_experimental_symbol(
    symbol: str,
    data: dict,
    config: Optional[ExperimentalStrategyConfig] = None,
) -> tuple[pd.DataFrame, dict]:
    """Executes the experimental strategy backtest for a single symbol."""
    if config is None:
        config = ExperimentalStrategyConfig()

    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema_f = data["ema_fast"]
    ema_s = data["ema_slow"]
    rsis = data["rsis"]
    ema_f_htf = data["ema_fast_htf"]
    ema_s_htf = data["ema_slow_htf"]
    times = data["times"]
    times_of_day = data["times_of_day"]
    cutoff_time = data["cutoff_time"]
    dates = data["dates"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    last_exit_time = -999999999
    cooldown_sec = config.cooldown_minutes * 60
    trades = []

    warmup = max(config.slow_ema, config.rsi_period, 14) + 2

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
                })
                position = None
                continue

        # 2. Open new position if flat
        if position is None and i < n - 1 and i >= warmup:
            # Session filter: do not open positions in the final 15 minutes
            if times_of_day[i] >= cutoff_time:
                continue

            # Cooldown check
            if cooldown_sec > 0 and (times[i] - last_exit_time) < cooldown_sec:
                continue

            # Fresh 1m EMA 9 / 21 crossover
            long_crossover = (ema_f[i - 1] <= ema_s[i - 1]) and (ema_f[i] > ema_s[i])
            short_crossover = (ema_f[i - 1] >= ema_s[i - 1]) and (ema_f[i] < ema_s[i])

            signal = None
            if long_crossover and rsis[i] >= config.long_rsi_min:
                signal = "LONG"
            elif short_crossover and rsis[i] <= config.short_rsi_max:
                signal = "SHORT"

            if signal is not None:
                # Higher-timeframe 15m 20/50 EMA Trend Filter
                if signal == "LONG":
                    if np.isnan(ema_f_htf[i]) or ema_f_htf[i] <= ema_s_htf[i]:
                        continue
                else:
                    if np.isnan(ema_f_htf[i]) or ema_f_htf[i] >= ema_s_htf[i]:
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

    # 3. Year-end dataset square-off if position remains open
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

    df_trades = pd.DataFrame(trades)
    n_trades = len(df_trades)
    wins = df_trades[df_trades["pnl"] > 0] if n_trades > 0 else pd.DataFrame()
    losses = df_trades[df_trades["pnl"] < 0] if n_trades > 0 else pd.DataFrame()

    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0

    gp = float(wins["pnl"].sum()) if n_wins > 0 else 0.0
    gl = float(abs(losses["pnl"].sum())) if n_losses > 0 else 0.0
    pf = (gp / gl) if gl > 0 else np.nan

    gross_pnl = float(df_trades["gross_pnl"].sum()) if n_trades > 0 else 0.0
    costs = float(df_trades["costs"].sum()) if n_trades > 0 else 0.0
    net_pnl = float(df_trades["pnl"].sum()) if n_trades > 0 else 0.0
    ret_pct = (net_pnl / config.initial_capital) * 100.0

    cum = df_trades["pnl"].cumsum() if n_trades > 0 else pd.Series([0.0])
    max_dd = float((cum.cummax() - cum).max()) if n_trades > 0 else 0.0
    avg_trade = (net_pnl / n_trades) if n_trades > 0 else 0.0

    if n_trades > 0:
        dur = (pd.to_datetime(df_trades["exit_datetime"]) - pd.to_datetime(df_trades["entry_datetime"])).dt.total_seconds() / 60.0
        avg_dur = float(dur.mean())
    else:
        avg_dur = 0.0

    stop_cnt = int((df_trades["exit_reason"] == "STOP").sum()) if n_trades > 0 else 0
    target_cnt = int((df_trades["exit_reason"] == "TARGET").sum()) if n_trades > 0 else 0
    eod_cnt = int((df_trades["exit_reason"] == "YEAR_END").sum()) if n_trades > 0 else 0

    metrics = {
        "symbol": symbol,
        "trades": n_trades,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate": round(win_rate, 2),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(ret_pct, 2),
        "profit_factor": round(pf, 4) if np.isfinite(pf) else 0.0,
        "max_drawdown": round(max_dd, 2),
        "average_trade": round(avg_trade, 2),
        "average_duration": round(avg_dur, 1),
        "stop_count": stop_cnt,
        "target_count": target_cnt,
        "eod_count": eod_cnt,
        "transaction_costs": round(costs, 2),
    }

    return df_trades, metrics

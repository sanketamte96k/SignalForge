"""
SignalForge — Strategy Evolution Phase 3: Entry Quality & Pullback Confirmation Engine
======================================================================================
File: src/strategy_evolution/phase3_entry_quality.py

Implements Phase 3 research engine evaluating entry timing and pullback confirmation:
- Variant 0: Baseline Control (1m 9/21 EMA crossover + RSI(14) >= 50 / <= 50)
- Variant 1: Crossover + RSI Confirmation (RSI >= 55 for LONG / <= 45 for SHORT)
- Variant 2: Crossover + Pullback (Wait up to 5 bars for EMA retest & rejection)
- Variant 3: Crossover + Pullback + RSI Confirmation (Pullback rejection + RSI >= 50 / <= 50)
- Variant 4: Crossover + Pullback + Candle Confirmation (Pullback + directional candle)
- Variant 5: ADX25 + Pullback (ADX >= 25 regime filter + Pullback)

Execution & Accounting:
- Strictly causal, zero look-ahead
- 1% risk position sizing
- 1.5 ATR Stop Loss, 3.0 ATR Target
- ₹20 Brokerage + 0.05% Slippage
- Single active position per symbol
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import numpy as np
import pandas as pd

VariantType = Literal[
    "baseline",
    "rsi_confirmation",
    "pullback",
    "pullback_rsi",
    "pullback_candle",
    "adx25_pullback",
]

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

DEFAULT_STOP_ATR: float = 1.5
DEFAULT_TARGET_ATR: float = 3.0
DEFAULT_RISK_PER_TRADE: float = 0.01
DEFAULT_BROKERAGE: float = 20.0
DEFAULT_SLIPPAGE: float = 0.0005
DEFAULT_INITIAL_CAPITAL: float = 100000.0


@dataclass(frozen=True)
class Phase3Config:
    name: str = "BASELINE"
    variant: VariantType = "baseline"
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    adx_period: int = 14
    adx_threshold: float = 25.0
    rsi_long_threshold: float = 55.0
    rsi_short_threshold: float = 45.0
    max_wait_bars: int = 5
    stop_atr: float = DEFAULT_STOP_ATR
    target_atr: float = DEFAULT_TARGET_ATR
    risk_per_trade: float = DEFAULT_RISK_PER_TRADE
    brokerage_per_trade: float = DEFAULT_BROKERAGE
    slippage: float = DEFAULT_SLIPPAGE
    initial_capital: float = DEFAULT_INITIAL_CAPITAL


def load_clean_symbol_data(symbol: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Loads clean 2018 1-minute data for the given symbol."""
    if data_dir is None:
        data_dir = Path("c:/Study Roadmap/PROJECTS/SignalForge/research/clean_data_2018")
    
    candidates = [
        data_dir / f"{symbol}_2018.csv",
        data_dir / f"{symbol}_2018.parquet",
        data_dir / f"{symbol}.parquet",
        data_dir / f"{symbol}.csv",
    ]
    for p in candidates:
        if p.exists():
            if p.suffix == ".parquet":
                df = pd.read_parquet(p)
            else:
                df = pd.read_csv(p)
            df["dt"] = pd.to_datetime(df["Date"])
            return df
    
    raise FileNotFoundError(f"No clean 2018 data found for {symbol} in {data_dir}")


def calculate_phase3_indicators(
    df_raw: pd.DataFrame,
    config: Optional[Phase3Config] = None,
) -> dict:
    """Precomputes strictly causal 1-minute indicators bit-identical to validated baseline."""
    if config is None:
        config = Phase3Config()

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

    timestamps = (df["dt"] - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64").to_numpy()

    return {
        "df": df,
        "highs": df["High"].to_numpy(),
        "lows": df["Low"].to_numpy(),
        "closes": df["Close"].to_numpy(),
        "opens": df["Open"].to_numpy(),
        "atrs": df["ATR"].to_numpy(),
        "ema9": df["EMA9"].to_numpy(),
        "ema21": df["EMA21"].to_numpy(),
        "rsis": df["RSI"].to_numpy(),
        "adxs": df["ADX"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "dt_series": df["dt"],
        "n": len(df),
    }


def simulate_phase3_symbol(
    symbol: str,
    data: dict,
    config: Phase3Config,
) -> list[dict]:
    """Simulates trading for a single symbol under the specified Phase 3 configuration.
    
    Zero look-ahead:
    - Decisions on candle i rely only on information up to and including candle i.
    - Pullback searches occur forward-in-time candle by candle.
    - Crossover invalidation cancels the setup immediately.
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    opens = data["opens"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    adxs = data["adxs"]
    dates = data["dates"]
    dt_series = data["dt_series"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    trades = []
    warmup = max(config.slow_ema, config.rsi_period, config.atr_period) + 2

    i = 1
    while i < n:
        # -------------------------------------------------------------
        # 1. Manage Active Position
        # -------------------------------------------------------------
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

                entry_bar = position["entry_bar_idx"]
                exit_bar = i
                # Compute MAE & MFE over trade holding period [entry_bar, exit_bar]
                trade_highs = highs[entry_bar : exit_bar + 1]
                trade_lows = lows[entry_bar : exit_bar + 1]
                atr_entry = position["atr_at_entry"]

                if side == "LONG":
                    min_low = float(np.min(trade_lows))
                    max_high = float(np.max(trade_highs))
                    mae_pts = max(0.0, entry - min_low)
                    mfe_pts = max(0.0, max_high - entry)
                else:
                    min_low = float(np.min(trade_lows))
                    max_high = float(np.max(trade_highs))
                    mae_pts = max(0.0, max_high - entry)
                    mfe_pts = max(0.0, entry - min_low)

                mae_atr = (mae_pts / atr_entry) if atr_entry > 0 else 0.0
                mfe_atr = (mfe_pts / atr_entry) if atr_entry > 0 else 0.0

                # Entry delay metrics
                delay_bars = entry_bar - position["crossover_bar_idx"]
                delay_mins = delay_bars  # 1-minute bars

                # Pullback depth: distance between crossover close and lowest/highest price before entry
                co_close = position["crossover_close"]
                if side == "LONG":
                    pb_min = float(np.min(lows[position["crossover_bar_idx"] : entry_bar + 1]))
                    pb_depth_pts = max(0.0, co_close - pb_min)
                else:
                    pb_max = float(np.max(highs[position["crossover_bar_idx"] : entry_bar + 1]))
                    pb_depth_pts = max(0.0, pb_max - co_close)
                pb_depth_atr = (pb_depth_pts / atr_entry) if atr_entry > 0 else 0.0

                # Retrospective classification
                # - trend continuation: hits target
                # - failed crossover: stopped out within 5 bars
                # - whipsaw: stopped out after minimal favorable excursion (< 0.5 ATR)
                # - pullback continuation: pullback entered and reaches >= 1.5 ATR MFE
                # - late entry: entered > 3 bars after crossover
                if exit_reason == "TARGET":
                    retrospective_class = "trend_continuation"
                elif mfe_atr < 0.5 and exit_reason == "STOP":
                    retrospective_class = "whipsaw"
                elif (exit_bar - entry_bar) <= 5 and exit_reason == "STOP":
                    retrospective_class = "failed_crossover"
                elif delay_bars >= 3:
                    retrospective_class = "late_entry"
                else:
                    retrospective_class = "pullback_continuation"

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": position["quantity"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                    "crossover_datetime": position["crossover_time"],
                    "delay_minutes": delay_mins,
                    "delay_bars": delay_bars,
                    "pullback_depth_points": round(pb_depth_pts, 3),
                    "pullback_depth_atr": round(pb_depth_atr, 3),
                    "mae_points": round(mae_pts, 3),
                    "mae_atr": round(mae_atr, 3),
                    "mfe_points": round(mfe_pts, 3),
                    "mfe_atr": round(mfe_atr, 3),
                    "holding_duration_bars": exit_bar - entry_bar,
                    "entry_hour": dt_series.iloc[entry_bar].hour,
                    "entry_month": dt_series.iloc[entry_bar].month,
                    "retrospective_class": retrospective_class,
                })
                position = None
                i += 1
                continue

        # -------------------------------------------------------------
        # 2. Check Signals when Flat
        # -------------------------------------------------------------
        if position is None and i < n - 1 and i >= warmup:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            if config.variant == "baseline":
                signal = None
                if long_crossover and rsis[i] >= 50.0:
                    signal = "LONG"
                elif short_crossover and rsis[i] <= 50.0:
                    signal = "SHORT"

                if signal is not None:
                    atr = atrs[i]
                    if not np.isnan(atr) and atr > 0:
                        entry_price = closes[i]
                        risk_amount = capital * config.risk_per_trade
                        risk_per_share = atr * config.stop_atr
                        qty = int(risk_amount / risk_per_share)
                        if qty > 0:
                            if signal == "LONG":
                                stop = entry_price - atr * config.stop_atr
                                target = entry_price + atr * config.target_atr
                            else:
                                stop = entry_price + atr * config.stop_atr
                                target = entry_price - atr * config.target_atr

                            position = {
                                "side": signal,
                                "entry_time": dates[i],
                                "entry_bar_idx": i,
                                "entry_price": entry_price,
                                "stop_price": stop,
                                "target_price": target,
                                "quantity": qty,
                                "atr_at_entry": atr,
                                "crossover_time": dates[i],
                                "crossover_bar_idx": i,
                                "crossover_close": closes[i],
                            }
                            i += 1
                            continue

            elif config.variant == "rsi_confirmation":
                # Stricter momentum confirmation: RSI >= 55 for LONG, <= 45 for SHORT
                signal = None
                if long_crossover and rsis[i] >= config.rsi_long_threshold:
                    signal = "LONG"
                elif short_crossover and rsis[i] <= config.rsi_short_threshold:
                    signal = "SHORT"

                if signal is not None:
                    atr = atrs[i]
                    if not np.isnan(atr) and atr > 0:
                        entry_price = closes[i]
                        risk_amount = capital * config.risk_per_trade
                        risk_per_share = atr * config.stop_atr
                        qty = int(risk_amount / risk_per_share)
                        if qty > 0:
                            if signal == "LONG":
                                stop = entry_price - atr * config.stop_atr
                                target = entry_price + atr * config.target_atr
                            else:
                                stop = entry_price + atr * config.stop_atr
                                target = entry_price - atr * config.target_atr

                            position = {
                                "side": signal,
                                "entry_time": dates[i],
                                "entry_bar_idx": i,
                                "entry_price": entry_price,
                                "stop_price": stop,
                                "target_price": target,
                                "quantity": qty,
                                "atr_at_entry": atr,
                                "crossover_time": dates[i],
                                "crossover_bar_idx": i,
                                "crossover_close": closes[i],
                            }
                            i += 1
                            continue

            elif config.variant in ["pullback", "pullback_rsi", "pullback_candle", "adx25_pullback"]:
                co_signal = None
                if long_crossover:
                    co_signal = "LONG"
                elif short_crossover:
                    co_signal = "SHORT"

                # Check ADX >= 25 regime filter if in adx25_pullback variant
                if config.variant == "adx25_pullback" and co_signal is not None:
                    if np.isnan(adxs[i]) or adxs[i] < config.adx_threshold:
                        co_signal = None

                if co_signal is not None:
                    crossover_bar = i
                    crossover_time = dates[i]
                    crossover_close = closes[i]
                    entry_found = False
                    entry_bar = None

                    # Search forward up to max_wait_bars causally
                    for step in range(1, config.max_wait_bars + 1):
                        cand = i + step
                        if cand >= n - 1:
                            break

                        if co_signal == "LONG":
                            # Invalidation: opposite EMA crossover
                            if ema9[cand] < ema21[cand]:
                                break
                            # Pullback condition: low touches or pierces EMA area
                            pulled_back = (lows[cand] <= ema9[cand])
                            # Rejection & resume: bullish close back at or above EMA9
                            rejected = (closes[cand] > opens[cand]) and (closes[cand] >= ema9[cand])

                            if config.variant == "pullback":
                                if pulled_back and rejected:
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "pullback_rsi":
                                # Pullback rejection + RSI confirms bullish (>= 50)
                                if pulled_back and rejected and (rsis[cand] >= 50.0):
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "pullback_candle":
                                # Pullback + Directional confirmation candle (engulfs prev high, strong body)
                                candle_ok = (
                                    (closes[cand] > opens[cand])
                                    and (closes[cand] > highs[cand - 1])
                                    and ((closes[cand] - opens[cand]) >= 0.3 * (highs[cand] - lows[cand]))
                                )
                                if pulled_back and candle_ok:
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "adx25_pullback":
                                if pulled_back and rejected:
                                    entry_found = True
                                    entry_bar = cand
                                    break

                        else:  # SHORT
                            # Invalidation: opposite EMA crossover
                            if ema9[cand] > ema21[cand]:
                                break
                            pulled_back = (highs[cand] >= ema9[cand])
                            rejected = (closes[cand] < opens[cand]) and (closes[cand] <= ema9[cand])

                            if config.variant == "pullback":
                                if pulled_back and rejected:
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "pullback_rsi":
                                # Pullback rejection + RSI confirms bearish (<= 50)
                                if pulled_back and rejected and (rsis[cand] <= 50.0):
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "pullback_candle":
                                candle_ok = (
                                    (closes[cand] < opens[cand])
                                    and (closes[cand] < lows[cand - 1])
                                    and ((opens[cand] - closes[cand]) >= 0.3 * (highs[cand] - lows[cand]))
                                )
                                if pulled_back and candle_ok:
                                    entry_found = True
                                    entry_bar = cand
                                    break
                            elif config.variant == "adx25_pullback":
                                if pulled_back and rejected:
                                    entry_found = True
                                    entry_bar = cand
                                    break

                    if entry_found and entry_bar is not None:
                        atr = atrs[entry_bar]
                        if not np.isnan(atr) and atr > 0:
                            entry_price = closes[entry_bar]
                            risk_amount = capital * config.risk_per_trade
                            risk_per_share = atr * config.stop_atr
                            qty = int(risk_amount / risk_per_share)
                            if qty > 0:
                                if co_signal == "LONG":
                                    stop = entry_price - atr * config.stop_atr
                                    target = entry_price + atr * config.target_atr
                                else:
                                    stop = entry_price + atr * config.stop_atr
                                    target = entry_price - atr * config.target_atr

                                position = {
                                    "side": co_signal,
                                    "entry_time": dates[entry_bar],
                                    "entry_bar_idx": entry_bar,
                                    "entry_price": entry_price,
                                    "stop_price": stop,
                                    "target_price": target,
                                    "quantity": qty,
                                    "atr_at_entry": atr,
                                    "crossover_time": crossover_time,
                                    "crossover_bar_idx": crossover_bar,
                                    "crossover_close": crossover_close,
                                }
                                i = entry_bar + 1
                                continue
        i += 1

    # -----------------------------------------------------------------
    # 3. Year-end Square-off if Position Remains Open
    # -----------------------------------------------------------------
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

        entry_bar = position["entry_bar_idx"]
        exit_bar = n - 1
        trade_highs = highs[entry_bar : exit_bar + 1]
        trade_lows = lows[entry_bar : exit_bar + 1]
        atr_entry = position["atr_at_entry"]

        if side == "LONG":
            min_low = float(np.min(trade_lows))
            max_high = float(np.max(trade_highs))
            mae_pts = max(0.0, entry - min_low)
            mfe_pts = max(0.0, max_high - entry)
        else:
            min_low = float(np.min(trade_lows))
            max_high = float(np.max(trade_highs))
            mae_pts = max(0.0, max_high - entry)
            mfe_pts = max(0.0, entry - min_low)

        mae_atr = (mae_pts / atr_entry) if atr_entry > 0 else 0.0
        mfe_atr = (mfe_pts / atr_entry) if atr_entry > 0 else 0.0
        delay_bars = entry_bar - position["crossover_bar_idx"]

        co_close = position["crossover_close"]
        if side == "LONG":
            pb_min = float(np.min(lows[position["crossover_bar_idx"] : entry_bar + 1]))
            pb_depth_pts = max(0.0, co_close - pb_min)
        else:
            pb_max = float(np.max(highs[position["crossover_bar_idx"] : entry_bar + 1]))
            pb_depth_pts = max(0.0, pb_max - co_close)
        pb_depth_atr = (pb_depth_pts / atr_entry) if atr_entry > 0 else 0.0

        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_price": entry,
            "exit_price": last_close,
            "stop_price": position["stop_price"],
            "target_price": position["target_price"],
            "quantity": position["quantity"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
            "crossover_datetime": position["crossover_time"],
            "delay_minutes": delay_bars,
            "delay_bars": delay_bars,
            "pullback_depth_points": round(pb_depth_pts, 3),
            "pullback_depth_atr": round(pb_depth_atr, 3),
            "mae_points": round(mae_pts, 3),
            "mae_atr": round(mae_atr, 3),
            "mfe_points": round(mfe_pts, 3),
            "mfe_atr": round(mfe_atr, 3),
            "holding_duration_bars": exit_bar - entry_bar,
            "entry_hour": dt_series.iloc[entry_bar].hour,
            "entry_month": dt_series.iloc[entry_bar].month,
            "retrospective_class": "pullback_continuation" if delay_bars >= 1 else "late_entry",
        })

    return trades


def calculate_portfolio_metrics(trades_list: list[dict]) -> dict:
    """Calculates all required portfolio metrics for a trade sequence."""
    n = len(trades_list)
    if n == 0:
        return {}

    df = pd.DataFrame(trades_list)
    df_sorted = df.sort_values("exit_datetime").reset_index(drop=True)

    wins = df_sorted[df_sorted["pnl"] > 0]
    losses = df_sorted[df_sorted["pnl"] < 0]
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = (n_wins / n * 100.0) if n > 0 else 0.0

    gross_profit = float(df_sorted[df_sorted["gross_pnl"] > 0]["gross_pnl"].sum())
    gross_loss = float(abs(df_sorted[df_sorted["gross_pnl"] < 0]["gross_pnl"].sum()))
    gross_pf = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    net_profit_sum = float(wins["pnl"].sum()) if n_wins > 0 else 0.0
    net_loss_sum = float(abs(losses["pnl"].sum())) if n_losses > 0 else 0.0
    net_pf = (net_profit_sum / net_loss_sum) if net_loss_sum > 0 else 0.0

    gross_pnl = float(df_sorted["gross_pnl"].sum())
    net_pnl = float(df_sorted["pnl"].sum())
    costs = float(df_sorted["costs"].sum())

    gross_exp = float(df_sorted["gross_pnl"].mean())
    net_exp = float(df_sorted["pnl"].mean())

    avg_winner = float(wins["pnl"].mean()) if n_wins > 0 else 0.0
    avg_loser = float(abs(losses["pnl"].mean())) if n_losses > 0 else 0.0
    reward_risk = (avg_winner / avg_loser) if avg_loser > 0 else 0.0

    # Max drawdown
    equity = df_sorted["capital_after_trade"].to_numpy()
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

    # Max loss streak
    is_loss = (df_sorted["pnl"] < 0).astype(int).to_numpy()
    max_loss_streak = 0
    curr_streak = 0
    for val in is_loss:
        if val == 1:
            curr_streak += 1
            if curr_streak > max_loss_streak:
                max_loss_streak = curr_streak
        else:
            curr_streak = 0

    avg_holding = float(df_sorted["holding_duration_bars"].mean())
    median_trade = float(df_sorted["pnl"].median())

    stop_count = int((df_sorted["exit_reason"] == "STOP").sum())
    target_count = int((df_sorted["exit_reason"] == "TARGET").sum())
    eod_count = int((df_sorted["exit_reason"] == "YEAR_END").sum())

    stop_pct = round(stop_count / n * 100.0, 2)
    target_pct = round(target_count / n * 100.0, 2)
    eod_pct = round(eod_count / n * 100.0, 2)

    return {
        "trades": n,
        "trades_per_day": round(n / 245.0, 1),  # approx 245 trading days in 2018
        "win_rate": round(win_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "gross_profit_factor": round(gross_pf, 4),
        "profit_factor": round(net_pf, 4),
        "gross_expectancy": round(gross_exp, 2),
        "net_expectancy": round(net_exp, 2),
        "average_trade": round(net_exp, 2),
        "median_trade": round(median_trade, 2),
        "average_winner": round(avg_winner, 2),
        "average_loser": round(avg_loser, 2),
        "reward_risk_ratio": round(reward_risk, 2),
        "max_drawdown": round(max_dd, 2),
        "max_loss_streak": max_loss_streak,
        "transaction_costs": round(costs, 2),
        "avg_holding_duration": round(avg_holding, 1),
        "stop_pct": stop_pct,
        "target_pct": target_pct,
        "eod_pct": eod_pct,
        "stop_count": stop_count,
        "target_count": target_count,
        "eod_count": eod_count,
    }

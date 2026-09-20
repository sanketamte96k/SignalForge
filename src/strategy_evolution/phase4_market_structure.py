"""
SignalForge — Strategy Evolution Phase 4: Market Structure & Price Action Engine
================================================================================
File: src/strategy_evolution/phase4_market_structure.py

Provides causal opening range extraction, swing detection, break of structure (BOS),
liquidity sweep detection, VWAP alignment, relative volume (RVOL), volatility regimes,
candidate strategy simulation, train/val/holdout partitioning, and cost sensitivity.

Strictly preserves baseline data integrity and avoids look-ahead bias.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

BASELINE_INITIAL_CAPITAL = 100000.0
BASELINE_RISK_PER_TRADE = 0.01
BASELINE_BROKERAGE = 20.0
BASELINE_SLIPPAGE = 0.0005


def load_clean_symbol_data(symbol: str) -> pd.DataFrame:
    """Loads validated 2018 1-minute data without modifying source."""
    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing validated clean dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    df["dt"] = pd.to_datetime(df["Date"])
    return df


def calculate_phase4_features(df_raw: pd.DataFrame) -> dict:
    """Computes strictly causal indicators, opening ranges, swings, VWAP, and volume features."""
    df = df_raw.copy()
    if "dt" not in df.columns:
        df["dt"] = pd.to_datetime(df["Date"])

    df["Date_Only"] = df["dt"].dt.date
    df["Time"] = df["dt"].dt.time
    df["Hour"] = df["dt"].dt.hour
    df["Minute"] = df["dt"].dt.minute
    df["Minute_Of_Day"] = df["Hour"] * 60 + df["Minute"]

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]
    opens = df["Open"]
    volumes = df["Volume"]

    # 1. EMAs & ATR
    df["EMA9"] = closes.ewm(span=9, adjust=False).mean()
    df["EMA21"] = closes.ewm(span=21, adjust=False).mean()
    df["EMA50"] = closes.ewm(span=50, adjust=False).mean()

    # True Range & ATR(14)
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(14).mean()
    df["ATR_PCT"] = (df["ATR"] / closes) * 100.0

    # Wilder RSI(14)
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100.0 - (100.0 / (1.0 + rs))

    # 2. Causal Intraday Cumulative VWAP (Reset daily)
    typical_price = (highs + lows + closes) / 3.0
    pv = typical_price * volumes
    cum_pv = pv.groupby(df["Date_Only"]).cumsum()
    cum_vol = volumes.groupby(df["Date_Only"]).cumsum()
    df["VWAP"] = cum_pv / cum_vol.replace(0, np.nan)

    # 3. Relative Volume (RVOL)
    df["VOL_ROLL_20"] = volumes.rolling(20).mean()
    df["RVOL"] = volumes / df["VOL_ROLL_20"].replace(0, np.nan)

    # 4. Opening Ranges (15m: 09:15-09:30, 30m: 09:15-09:45, 45m: 09:15-10:00)
    # Computed causally: for any candle t, opening range is active only after the window has closed!
    n = len(df)
    times = df["Time"].to_numpy()
    high_arr = highs.to_numpy(dtype=float)
    low_arr = lows.to_numpy(dtype=float)
    date_arr = df["Date_Only"].to_numpy()

    or15_high = np.full(n, np.nan)
    or15_low = np.full(n, np.nan)
    or30_high = np.full(n, np.nan)
    or30_low = np.full(n, np.nan)
    or45_high = np.full(n, np.nan)
    or45_low = np.full(n, np.nan)

    # Pre-extract session daily boundaries
    unique_dates = df["Date_Only"].unique()
    date_indices = df.groupby("Date_Only").indices

    t_0930 = pd.to_datetime("09:30:00").time()
    t_0945 = pd.to_datetime("09:45:00").time()
    t_1000 = pd.to_datetime("10:00:00").time()

    for d in unique_dates:
        idx_range = date_indices[d]
        sub_high = high_arr[idx_range]
        sub_low = low_arr[idx_range]
        sub_times = times[idx_range]

        # 15m window (< 09:30)
        mask15 = sub_times < t_0930
        if np.any(mask15):
            h15 = float(np.max(sub_high[mask15]))
            l15 = float(np.min(sub_low[mask15]))
            # Populate strictly starting from 09:30:00 onwards
            valid15 = sub_times >= t_0930
            or15_high[idx_range[valid15]] = h15
            or15_low[idx_range[valid15]] = l15

        # 30m window (< 09:45)
        mask30 = sub_times < t_0945
        if np.any(mask30):
            h30 = float(np.max(sub_high[mask30]))
            l30 = float(np.min(sub_low[mask30]))
            valid30 = sub_times >= t_0945
            or30_high[idx_range[valid30]] = h30
            or30_low[idx_range[valid30]] = l30

        # 45m window (< 10:00)
        mask45 = sub_times < t_1000
        if np.any(mask45):
            h45 = float(np.max(sub_high[mask45]))
            l45 = float(np.min(sub_low[mask45]))
            valid45 = sub_times >= t_1000
            or45_high[idx_range[valid45]] = h45
            or45_low[idx_range[valid45]] = l45

    df["OR15_HIGH"] = or15_high
    df["OR15_LOW"] = or15_low
    df["OR30_HIGH"] = or30_high
    df["OR30_LOW"] = or30_low
    df["OR45_HIGH"] = or45_high
    df["OR45_LOW"] = or45_low

    # 5. Causal Swing Detection (order k=3)
    # Candle i-k is confirmed swing high at bar i if High[i-k] is highest in [i-2k, i]
    k = 3
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)
    last_swing_high = np.full(n, np.nan)
    last_swing_low = np.full(n, np.nan)
    market_structure = np.full(n, "RANGE", dtype=object)

    curr_last_sh = np.nan
    curr_last_sl = np.nan
    prev_sh = np.nan
    prev_sl = np.nan

    for i in range(2 * k, n):
        mid = i - k
        # Swing High check at mid
        is_sh = True
        for j in range(i - 2 * k, i + 1):
            if j != mid and high_arr[j] > high_arr[mid]:
                is_sh = False
                break
        if is_sh:
            swing_highs[mid] = high_arr[mid]
            prev_sh = curr_last_sh
            curr_last_sh = high_arr[mid]

        # Swing Low check at mid
        is_sl = True
        for j in range(i - 2 * k, i + 1):
            if j != mid and low_arr[j] < low_arr[mid]:
                is_sl = False
                break
        if is_sl:
            swing_lows[mid] = low_arr[mid]
            prev_sl = curr_last_sl
            curr_last_sl = low_arr[mid]

        last_swing_high[i] = curr_last_sh
        last_swing_low[i] = curr_last_sl

        # Market structure regime classification
        if not np.isnan(curr_last_sh) and not np.isnan(prev_sh) and not np.isnan(curr_last_sl) and not np.isnan(prev_sl):
            if curr_last_sh > prev_sh and curr_last_sl > prev_sl:
                market_structure[i] = "BULLISH"
            elif curr_last_sh < prev_sh and curr_last_sl < prev_sl:
                market_structure[i] = "BEARISH"
            else:
                market_structure[i] = "RANGE"

    df["LAST_SWING_HIGH"] = last_swing_high
    df["LAST_SWING_LOW"] = last_swing_low
    df["MARKET_STRUCTURE"] = market_structure

    # 6. Break of Structure (BOS)
    df["BOS_LONG"] = (df["Close"] > df["LAST_SWING_HIGH"]) & (df["Close"].shift(1) <= df["LAST_SWING_HIGH"])
    df["BOS_SHORT"] = (df["Close"] < df["LAST_SWING_LOW"]) & (df["Close"].shift(1) >= df["LAST_SWING_LOW"])

    return {
        "df": df,
        "highs": high_arr,
        "lows": low_arr,
        "closes": closes.to_numpy(dtype=float),
        "opens": opens.to_numpy(dtype=float),
        "volumes": volumes.to_numpy(dtype=float),
        "atrs": df["ATR"].to_numpy(dtype=float),
        "ema9": df["EMA9"].to_numpy(dtype=float),
        "ema21": df["EMA21"].to_numpy(dtype=float),
        "ema50": df["EMA50"].to_numpy(dtype=float),
        "rsis": df["RSI"].to_numpy(dtype=float),
        "vwaps": df["VWAP"].to_numpy(dtype=float),
        "rvols": df["RVOL"].to_numpy(dtype=float),
        "or15_high": or15_high,
        "or15_low": or15_low,
        "or30_high": or30_high,
        "or30_low": or30_low,
        "or45_high": or45_high,
        "or45_low": or45_low,
        "last_swing_high": last_swing_high,
        "last_swing_low": last_swing_low,
        "market_structure": market_structure,
        "dates": df["Date"].tolist(),
        "times": times,
        "minute_of_day": df["Minute_Of_Day"].to_numpy(dtype=int),
        "date_only": date_arr,
        "n": n,
    }


def calculate_portfolio_metrics(trades_list: list[dict]) -> dict:
    """Computes comprehensive portfolio performance and risk metrics."""
    n = len(trades_list)
    if n == 0:
        return {
            "trades": 0, "win_rate": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
            "gross_pnl": 0.0, "costs": 0.0, "net_pnl": 0.0, "profit_factor": 0.0,
            "gross_profit_factor": 0.0, "average_trade": 0.0, "max_drawdown": 0.0,
            "max_consecutive_losses": 0, "expectancy": 0.0,
        }

    df = pd.DataFrame(trades_list).sort_values("exit_datetime").reset_index(drop=True)
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] < 0]
    n_wins = len(wins)
    win_rate = (n_wins / n * 100.0) if n > 0 else 0.0

    net_win_sum = float(wins["pnl"].sum()) if n_wins > 0 else 0.0
    net_loss_sum = float(abs(losses["pnl"].sum())) if len(losses) > 0 else 0.0
    pf = (net_win_sum / net_loss_sum) if net_loss_sum > 0 else 0.0

    gross_wins = df[df["gross_pnl"] > 0]
    gross_losses = df[df["gross_pnl"] < 0]
    gross_win_sum = float(gross_wins["gross_pnl"].sum()) if len(gross_wins) > 0 else 0.0
    gross_loss_sum = float(abs(gross_losses["gross_pnl"].sum())) if len(gross_losses) > 0 else 0.0
    gross_pf = (gross_win_sum / gross_loss_sum) if gross_loss_sum > 0 else 0.0

    net_pnl = float(df["pnl"].sum())
    gross_pnl = float(df["gross_pnl"].sum())
    costs = float(df["costs"].sum())
    avg_trade = net_pnl / n if n > 0 else 0.0

    cum = df["pnl"].cumsum()
    max_dd = float((cum.cummax() - cum).max()) if len(cum) > 0 else 0.0

    max_streak = 0
    curr_streak = 0
    for p in df["pnl"]:
        if p < 0:
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
        else:
            curr_streak = 0

    return {
        "trades": n,
        "win_rate": round(win_rate, 2),
        "gross_profit": round(gross_win_sum, 2),
        "gross_loss": round(gross_loss_sum, 2),
        "gross_pnl": round(gross_pnl, 2),
        "costs": round(costs, 2),
        "net_pnl": round(net_pnl, 2),
        "profit_factor": round(pf, 4),
        "gross_profit_factor": round(gross_pf, 4),
        "average_trade": round(avg_trade, 2),
        "max_drawdown": round(max_dd, 2),
        "max_consecutive_losses": max_streak,
        "expectancy": round(avg_trade, 2),
    }


def calculate_mae_mfe(trades: list[dict], data_dict: dict[str, dict]) -> list[dict]:
    """Calculates strictly causal normalized MAE and MFE for each trade."""
    enriched_trades = []

    for t in trades:
        t_copy = dict(t)
        sym = t["symbol"]
        data = data_dict[sym]
        highs = data["highs"]
        lows = data["lows"]

        start_idx = t["entry_bar_idx"] + 1
        end_idx = t["exit_bar_idx"]
        entry_price = t["entry_price"]
        side = t["direction"]
        atr_entry = t["atr_at_entry"]
        stop_price = t["stop_price"]
        target_price = t["target_price"]

        if start_idx > end_idx:
            start_idx = end_idx

        holding_highs = highs[start_idx : end_idx + 1]
        holding_lows = lows[start_idx : end_idx + 1]

        if side == "LONG":
            max_favorable_points = max(0.0, float(np.max(holding_highs) - entry_price))
            max_adverse_points = max(0.0, float(entry_price - np.min(holding_lows)))
            if t["exit_reason"] == "STOP":
                max_adverse_points = max(max_adverse_points, entry_price - stop_price)
            if t["exit_reason"] == "TARGET":
                max_favorable_points = max(max_favorable_points, target_price - entry_price)
        else:
            max_favorable_points = max(0.0, float(entry_price - np.min(holding_lows)))
            max_adverse_points = max(0.0, float(np.max(holding_highs) - entry_price))
            if t["exit_reason"] == "STOP":
                max_adverse_points = max(max_adverse_points, stop_price - entry_price)
            if t["exit_reason"] == "TARGET":
                max_favorable_points = max(max_favorable_points, entry_price - target_price)

        mae_atr = max_adverse_points / atr_entry if atr_entry > 0 else 0.0
        mfe_atr = max_favorable_points / atr_entry if atr_entry > 0 else 0.0

        t_copy["mae_points"] = round(max_adverse_points, 4)
        t_copy["mfe_points"] = round(max_favorable_points, 4)
        t_copy["mae_atr"] = round(mae_atr, 4)
        t_copy["mfe_atr"] = round(mfe_atr, 4)
        t_copy["holding_bars"] = end_idx - t["entry_bar_idx"]

        enriched_trades.append(t_copy)

    return enriched_trades


def simulate_opening_range_breakout(
    symbol: str,
    data: dict,
    or_window: str = "15m",
    breakout_mode: str = "close_confirm",  # immediate, close_confirm, retest, volume_confirm, vwap_confirm
    stop_atr: float = 1.5,
    target_atr: float = 2.0,
    rvol_threshold: float = 1.25,
) -> list[dict]:
    """Simulates Opening Range Breakout across selected window and breakout confirmation mode."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    opens = data["opens"]
    atrs = data["atrs"]
    vwaps = data["vwaps"]
    rvols = data["rvols"]
    dates = data["dates"]
    times = data["times"]
    n = data["n"]

    if or_window == "15m":
        or_high_arr = data["or15_high"]
        or_low_arr = data["or15_low"]
        start_min = 570
    elif or_window == "30m":
        or_high_arr = data["or30_high"]
        or_low_arr = data["or30_low"]
        start_min = 585
    else:
        or_high_arr = data["or45_high"]
        or_low_arr = data["or45_low"]
        start_min = 600
    cutoff_entry_min = 690  # 11:30
    squareoff_min = 915     # 15:15
    minute_of_day = data["minute_of_day"]
    date_only = data["date_only"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    last_trade_date = None

    roll_prev_h = pd.Series(highs).shift(1).rolling(5).max().to_numpy()
    roll_prev_l = pd.Series(lows).shift(1).rolling(5).min().to_numpy()

    for i in range(1, n):
        cur_m = minute_of_day[i]
        cur_date = date_only[i]

        # 1. Manage active position
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
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"
            else:
                if highs[i] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif lows[i] <= target:
                    exit_price = target
                    exit_reason = "TARGET"
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"

            if exit_price is not None:
                gross_pnl = (exit_price - entry) * position["quantity"] if side == "LONG" else (entry - exit_price) * position["quantity"]
                costs = BASELINE_BROKERAGE + (abs(exit_price - entry) * position["quantity"] * BASELINE_SLIPPAGE)
                net_pnl = gross_pnl - costs
                capital += net_pnl

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_bar_idx": position["entry_bar_idx"],
                    "exit_bar_idx": i,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": position["quantity"],
                    "atr_at_entry": position["atr_at_entry"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                })
                position = None
                continue

        # 2. Check for Breakout Entry (Max 1 trade per symbol per day to avoid overtrading)
        if position is None:
            if cur_date == last_trade_date:
                continue
            if cur_m < start_min or cur_m > cutoff_entry_min:
                continue

            or_h = or_high_arr[i]
            or_l = or_low_arr[i]
            if np.isnan(or_h) or np.isnan(or_l):
                continue

            atr = atrs[i]
            if np.isnan(atr) or atr <= 0:
                continue

            signal = None

            if breakout_mode == "immediate":
                if highs[i] > or_h and closes[i-1] <= or_h:
                    signal = "LONG"
                elif lows[i] < or_l and closes[i-1] >= or_l:
                    signal = "SHORT"

            elif breakout_mode == "close_confirm":
                if closes[i] > or_h and closes[i-1] <= or_h:
                    signal = "LONG"
                elif closes[i] < or_l and closes[i-1] >= or_l:
                    signal = "SHORT"

            elif breakout_mode == "volume_confirm":
                if closes[i] > or_h and closes[i-1] <= or_h and rvols[i] >= rvol_threshold:
                    signal = "LONG"
                elif closes[i] < or_l and closes[i-1] >= or_l and rvols[i] >= rvol_threshold:
                    signal = "SHORT"

            elif breakout_mode == "vwap_confirm":
                if closes[i] > or_h and closes[i-1] <= or_h and closes[i] > vwaps[i]:
                    signal = "LONG"
                elif closes[i] < or_l and closes[i-1] >= or_l and closes[i] < vwaps[i]:
                    signal = "SHORT"

            elif breakout_mode == "retest":
                # Retest: price previously broke out and is now retesting OR level
                # For long: prior high > or_h, current low touches or_h, close >= or_h
                if roll_prev_h[i] > or_h and lows[i] <= or_h and closes[i] >= or_h:
                    signal = "LONG"
                elif roll_prev_l[i] < or_l and highs[i] >= or_l and closes[i] <= or_l:
                    signal = "SHORT"

            if signal is not None:
                entry_price = closes[i]
                risk_amount = capital * BASELINE_RISK_PER_TRADE
                risk_per_share = atr * stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                stop = entry_price - atr * stop_atr if signal == "LONG" else entry_price + atr * stop_atr
                target = entry_price + atr * target_atr if signal == "LONG" else entry_price - atr * target_atr

                position = {
                    "side": signal,
                    "entry_time": dates[i],
                    "entry_bar_idx": i,
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                    "atr_at_entry": atr,
                }
                last_trade_date = cur_date

    # Year-end cleanup
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]
        gross_pnl = (last_close - entry) * position["quantity"] if side == "LONG" else (entry - last_close) * position["quantity"]
        costs = BASELINE_BROKERAGE + (abs(last_close - entry) * position["quantity"] * BASELINE_SLIPPAGE)
        net_pnl = gross_pnl - costs
        capital += net_pnl
        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_bar_idx": position["entry_bar_idx"],
            "exit_bar_idx": n - 1,
            "entry_price": entry,
            "exit_price": last_close,
            "stop_price": position["stop_price"],
            "target_price": position["target_price"],
            "quantity": position["quantity"],
            "atr_at_entry": position["atr_at_entry"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
        })

    return trades


def simulate_market_structure_bos(
    symbol: str,
    data: dict,
    require_retest: bool = False,
    stop_atr: float = 1.5,
    target_atr: float = 2.5,
) -> list[dict]:
    """Simulates trading Break of Structure (BOS) with optional pullback/retest requirement."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    last_sh = data["last_swing_high"]
    last_sl = data["last_swing_low"]
    dates = data["dates"]
    times = data["times"]
    n = data["n"]

    minute_of_day = data["minute_of_day"]
    cutoff_min = 870   # 14:30
    squareoff_min = 915 # 15:15

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []

    roll_prev_h = pd.Series(highs).shift(1).rolling(5).max().to_numpy()
    roll_prev_l = pd.Series(lows).shift(1).rolling(5).min().to_numpy()

    for i in range(10, n):
        cur_m = minute_of_day[i]

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
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"
            else:
                if highs[i] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif lows[i] <= target:
                    exit_price = target
                    exit_reason = "TARGET"
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"

            if exit_price is not None:
                gross_pnl = (exit_price - entry) * position["quantity"] if side == "LONG" else (entry - exit_price) * position["quantity"]
                costs = BASELINE_BROKERAGE + (abs(exit_price - entry) * position["quantity"] * BASELINE_SLIPPAGE)
                net_pnl = gross_pnl - costs
                capital += net_pnl

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_bar_idx": position["entry_bar_idx"],
                    "exit_bar_idx": i,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": position["quantity"],
                    "atr_at_entry": position["atr_at_entry"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                })
                position = None
                continue

        if position is None and cur_m < cutoff_min:
            sh = last_sh[i]
            sl = last_sl[i]
            if np.isnan(sh) or np.isnan(sl):
                continue

            atr = atrs[i]
            if np.isnan(atr) or atr <= 0:
                continue

            signal = None

            if not require_retest:
                # Direct BOS close
                if closes[i] > sh and closes[i-1] <= sh:
                    signal = "LONG"
                elif closes[i] < sl and closes[i-1] >= sl:
                    signal = "SHORT"
            else:
                # BOS + Retest: prior 5 bars had BOS, current bar retests broken level
                if roll_prev_h[i] > sh and lows[i] <= sh and closes[i] >= sh:
                    signal = "LONG"
                elif roll_prev_l[i] < sl and highs[i] >= sl and closes[i] <= sl:
                    signal = "SHORT"

            if signal is not None:
                entry_price = closes[i]
                risk_amount = capital * BASELINE_RISK_PER_TRADE
                risk_per_share = atr * stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                stop = entry_price - atr * stop_atr if signal == "LONG" else entry_price + atr * stop_atr
                target = entry_price + atr * target_atr if signal == "LONG" else entry_price - atr * target_atr

                position = {
                    "side": signal,
                    "entry_time": dates[i],
                    "entry_bar_idx": i,
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                    "atr_at_entry": atr,
                }

    # Year-end cleanup
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]
        gross_pnl = (last_close - entry) * position["quantity"] if side == "LONG" else (entry - last_close) * position["quantity"]
        costs = BASELINE_BROKERAGE + (abs(last_close - entry) * position["quantity"] * BASELINE_SLIPPAGE)
        net_pnl = gross_pnl - costs
        capital += net_pnl
        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_bar_idx": position["entry_bar_idx"],
            "exit_bar_idx": n - 1,
            "entry_price": entry,
            "exit_price": last_close,
            "stop_price": position["stop_price"],
            "target_price": position["target_price"],
            "quantity": position["quantity"],
            "atr_at_entry": position["atr_at_entry"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
        })

    return trades


def simulate_liquidity_sweep(
    symbol: str,
    data: dict,
    lookback_window: int = 20,
    stop_atr: float = 1.25,
    target_atr: float = 2.0,
) -> list[dict]:
    """Simulates Liquidity Sweep: price sweeps recent extreme, closes back inside, followed by confirmation."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    opens = data["opens"]
    atrs = data["atrs"]
    dates = data["dates"]
    times = data["times"]
    n = data["n"]

    minute_of_day = data["minute_of_day"]
    cutoff_min = 870   # 14:30
    squareoff_min = 915 # 15:15

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []

    roll_ref_min = pd.Series(lows).shift(2).rolling(lookback_window).min().to_numpy()
    roll_ref_max = pd.Series(highs).shift(2).rolling(lookback_window).max().to_numpy()

    for i in range(lookback_window + 1, n):
        cur_m = minute_of_day[i]

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
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"
            else:
                if highs[i] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif lows[i] <= target:
                    exit_price = target
                    exit_reason = "TARGET"
                elif cur_m >= squareoff_min:
                    exit_price = closes[i]
                    exit_reason = "EOD_SQUAREOFF"

            if exit_price is not None:
                gross_pnl = (exit_price - entry) * position["quantity"] if side == "LONG" else (entry - exit_price) * position["quantity"]
                costs = BASELINE_BROKERAGE + (abs(exit_price - entry) * position["quantity"] * BASELINE_SLIPPAGE)
                net_pnl = gross_pnl - costs
                capital += net_pnl

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_bar_idx": position["entry_bar_idx"],
                    "exit_bar_idx": i,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": position["quantity"],
                    "atr_at_entry": position["atr_at_entry"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                })
                position = None
                continue

        if position is None and cur_m < cutoff_min:
            recent_min = roll_ref_min[i]
            recent_max = roll_ref_max[i]
            if np.isnan(recent_min) or np.isnan(recent_max):
                continue

            atr = atrs[i]
            if np.isnan(atr) or atr <= 0:
                continue

            signal = None

            # Bullish sweep on bar i-1, confirmed on bar i
            # Bar i-1 swept low (Low < recent_min) but closed back inside (Close > recent_min)
            # Bar i confirms: Close[i] > Open[i] and Close[i] > Close[i-1]
            if lows[i-1] < recent_min and closes[i-1] > recent_min:
                if closes[i] > opens[i] and closes[i] > closes[i-1]:
                    signal = "LONG"

            # Bearish sweep on bar i-1, confirmed on bar i
            elif highs[i-1] > recent_max and closes[i-1] < recent_max:
                if closes[i] < opens[i] and closes[i] < closes[i-1]:
                    signal = "SHORT"

            if signal is not None:
                entry_price = closes[i]
                risk_amount = capital * BASELINE_RISK_PER_TRADE
                risk_per_share = atr * stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                stop = entry_price - atr * stop_atr if signal == "LONG" else entry_price + atr * stop_atr
                target = entry_price + atr * target_atr if signal == "LONG" else entry_price - atr * target_atr

                position = {
                    "side": signal,
                    "entry_time": dates[i],
                    "entry_bar_idx": i,
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                    "atr_at_entry": atr,
                }

    # Year-end cleanup
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]
        gross_pnl = (last_close - entry) * position["quantity"] if side == "LONG" else (entry - last_close) * position["quantity"]
        costs = BASELINE_BROKERAGE + (abs(last_close - entry) * position["quantity"] * BASELINE_SLIPPAGE)
        net_pnl = gross_pnl - costs
        capital += net_pnl
        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_bar_idx": position["entry_bar_idx"],
            "exit_bar_idx": n - 1,
            "entry_price": entry,
            "exit_price": last_close,
            "stop_price": position["stop_price"],
            "target_price": position["target_price"],
            "quantity": position["quantity"],
            "atr_at_entry": position["atr_at_entry"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
        })

    return trades


def simulate_candidate(
    candidate_id: str,
    data_dict: dict[str, dict],
    stop_atr: float = 1.5,
    target_atr: float = 2.0,
) -> list[dict]:
    """Executes one of the 4 Phase 4 candidate strategies across all symbols."""
    all_trades = []

    for sym, data in data_dict.items():
        if candidate_id == "candidate_a":
            # Candidate A: Opening Range Breakout (15m OR, close confirmation)
            t = simulate_opening_range_breakout(
                symbol=sym,
                data=data,
                or_window="15m",
                breakout_mode="close_confirm",
                stop_atr=stop_atr,
                target_atr=target_atr,
            )
        elif candidate_id == "candidate_b":
            # Candidate B: Opening Range Breakout + VWAP (30m OR, VWAP alignment, RVOL >= 1.0)
            t = simulate_opening_range_breakout(
                symbol=sym,
                data=data,
                or_window="30m",
                breakout_mode="vwap_confirm",
                stop_atr=stop_atr,
                target_atr=target_atr,
            )
        elif candidate_id == "candidate_c":
            # Candidate C: Structure Break + Retest (BOS + Retest)
            t = simulate_market_structure_bos(
                symbol=sym,
                data=data,
                require_retest=True,
                stop_atr=stop_atr,
                target_atr=target_atr,
            )
        elif candidate_id == "candidate_d":
            # Candidate D: Liquidity Sweep + Structure Confirmation (20-bar lookback)
            t = simulate_liquidity_sweep(
                symbol=sym,
                data=data,
                lookback_window=20,
                stop_atr=stop_atr,
                target_atr=target_atr,
            )
        else:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")

        all_trades.extend(t)

    return all_trades

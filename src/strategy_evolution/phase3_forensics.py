"""
SignalForge — Strategy Evolution Phase 3: Entry/Exit Forensic & Strategy Improvement Engine
============================================================================================
File: src/strategy_evolution/phase3_forensics.py

Provides strictly causal feature extraction, MAE/MFE trade forensics, stop/target parameter
grid evaluation, entry delay/pullback/confirmation tests, chop and regime analysis,
controlled candidate strategy simulation, and cost sensitivity analysis.

Never touches or modifies production baseline code or raw data.
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

# Baseline execution parameters (strictly preserved from Phase 1 & 2)
BASELINE_INITIAL_CAPITAL = 100000.0
BASELINE_RISK_PER_TRADE = 0.01
BASELINE_STOP_ATR = 1.5
BASELINE_TARGET_ATR = 3.0
BASELINE_BROKERAGE = 20.0
BASELINE_SLIPPAGE = 0.0005


def load_clean_symbol_data(symbol: str) -> pd.DataFrame:
    """Loads validated 2018 1-minute data for a symbol without modifying the source."""
    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing validated clean dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    df["dt"] = pd.to_datetime(df["Date"])
    return df


def calculate_phase3_indicators(df_raw: pd.DataFrame) -> dict:
    """Precomputes strictly causal 1-minute indicators and entry feature arrays.
    
    All indicators are causal and use only current and past bars (indices <= i).
    No look-ahead information is utilized.
    """
    df = df_raw.copy()
    if "dt" not in df.columns:
        df["dt"] = pd.to_datetime(df["Date"])

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]
    opens = df["Open"]
    volumes = df["Volume"]

    # 1. EMAs: 9, 21, 50, 200
    df["EMA9"] = closes.ewm(span=9, adjust=False).mean()
    df["EMA21"] = closes.ewm(span=21, adjust=False).mean()
    df["EMA50"] = closes.ewm(span=50, adjust=False).mean()
    df["EMA200"] = closes.ewm(span=200, adjust=False).mean()

    # 2. RSI(14) - Wilder style
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100.0 - (100.0 / (1.0 + rs))

    # 3. True Range & ATR(14)
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(14).mean()

    # 4. Wilder's ADX(14)
    up_move = highs - highs.shift(1)
    down_move = lows.shift(1) - lows
    pos_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    neg_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    tr_smooth = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    pos_dm_smooth = pos_dm.ewm(alpha=1.0 / 14, adjust=False).mean()
    neg_dm_smooth = neg_dm.ewm(alpha=1.0 / 14, adjust=False).mean()
    pos_di = 100.0 * (pos_dm_smooth / tr_smooth.replace(0, np.nan))
    neg_di = 100.0 * (neg_dm_smooth / tr_smooth.replace(0, np.nan))
    di_sum = pos_di + neg_di
    dx = (100.0 * ((pos_di - neg_di).abs() / di_sum.replace(0, np.nan))).fillna(0.0)
    df["ADX"] = dx.ewm(alpha=1.0 / 14, adjust=False).mean()

    # 5. EMA Spreads & Slopes
    df["EMA_SPREAD"] = df["EMA9"] - df["EMA21"]
    df["EMA_SPREAD_PCT"] = (df["EMA_SPREAD"] / closes) * 100.0
    df["EMA9_SLOPE"] = (df["EMA9"] - df["EMA9"].shift(1)) / closes * 100.0
    df["EMA21_SLOPE"] = (df["EMA21"] - df["EMA21"].shift(1)) / closes * 100.0

    # 6. ATR Percentage
    df["ATR_PCT"] = (df["ATR"] / closes) * 100.0

    # 7. Candle Body & Range Percentages
    candle_range = highs - lows
    df["CANDLE_RANGE_PCT"] = (candle_range / closes) * 100.0
    df["CANDLE_BODY_PCT"] = (opens - closes).abs() / candle_range.replace(0, np.nan) * 100.0

    # 8. Distance from recent high/low (20-bar rolling)
    roll_high_20 = highs.rolling(20).max()
    roll_low_20 = lows.rolling(20).min()
    df["DIST_HIGH_20_PCT"] = (roll_high_20 - closes) / closes * 100.0
    df["DIST_LOW_20_PCT"] = (closes - roll_low_20) / closes * 100.0

    # 9. Intraday Cumulative VWAP (Reset daily)
    df["Date_Only"] = df["dt"].dt.date
    typical_price = (highs + lows + closes) / 3.0
    pv = typical_price * volumes
    cum_pv = pv.groupby(df["Date_Only"]).cumsum()
    cum_vol = volumes.groupby(df["Date_Only"]).cumsum()
    df["VWAP"] = cum_pv / cum_vol.replace(0, np.nan)
    df["DIST_VWAP_PCT"] = (closes - df["VWAP"]) / df["VWAP"].replace(0, np.nan) * 100.0

    # 10. Previous Returns: 3, 5, 10, 15 bars
    df["RET_3BAR"] = (closes - closes.shift(3)) / closes.shift(3) * 100.0
    df["RET_5BAR"] = (closes - closes.shift(5)) / closes.shift(5) * 100.0
    df["RET_10BAR"] = (closes - closes.shift(10)) / closes.shift(10) * 100.0
    df["RET_15BAR"] = (closes - closes.shift(15)) / closes.shift(15) * 100.0

    # 11. Rolling Volume Ratio
    df["VOL_ROLLING_20"] = volumes.rolling(20).mean()
    df["VOL_RATIO"] = volumes / df["VOL_ROLLING_20"].replace(0, np.nan)

    # 12. Chop Score Components
    crossover_event = (df["EMA9"] > df["EMA21"]) != (df["EMA9"].shift(1) > df["EMA21"].shift(1))
    df["CROSSOVER_COUNT_20"] = crossover_event.rolling(20).sum()
    path_len_20 = (closes.diff().abs()).rolling(20).sum()
    displacement_20 = (closes - closes.shift(20)).abs()
    df["EFFICIENCY_RATIO_20"] = displacement_20 / path_len_20.replace(0, np.nan)

    # 13. Market Regime classification (Causal)
    df["ATR_MEDIAN_100"] = df["ATR"].rolling(100).median()
    df["IS_HIGH_VOL"] = df["ATR"] > df["ATR_MEDIAN_100"]

    timestamps = (df["dt"] - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64").to_numpy()

    return {
        "df": df,
        "highs": highs.to_numpy(dtype=float),
        "lows": lows.to_numpy(dtype=float),
        "closes": closes.to_numpy(dtype=float),
        "opens": opens.to_numpy(dtype=float),
        "volumes": volumes.to_numpy(dtype=float),
        "atrs": df["ATR"].to_numpy(dtype=float),
        "ema9": df["EMA9"].to_numpy(dtype=float),
        "ema21": df["EMA21"].to_numpy(dtype=float),
        "ema50": df["EMA50"].to_numpy(dtype=float),
        "ema200": df["EMA200"].to_numpy(dtype=float),
        "rsis": df["RSI"].to_numpy(dtype=float),
        "adxs": df["ADX"].to_numpy(dtype=float),
        "vwaps": df["VWAP"].to_numpy(dtype=float),
        "crossover_count_20": df["CROSSOVER_COUNT_20"].to_numpy(dtype=float),
        "efficiency_ratio_20": df["EFFICIENCY_RATIO_20"].to_numpy(dtype=float),
        "is_high_vol": df["IS_HIGH_VOL"].to_numpy(dtype=bool),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_baseline_forensics(
    symbol: str,
    data: dict,
    stop_atr: float = BASELINE_STOP_ATR,
    target_atr: float = BASELINE_TARGET_ATR,
    brokerage: float = BASELINE_BROKERAGE,
    slippage: float = BASELINE_SLIPPAGE,
) -> list[dict]:
    """Simulates baseline execution while capturing exact entry and exit bar indices for MAE/MFE forensics.
    
    Reproduces baseline execution with mathematical exactness:
    - 1m EMA9 / EMA21 crossover with RSI >= 50 (LONG) or <= 50 (SHORT)
    - Single active position per symbol
    - 1% risk position sizing
    - Exit on Stop or Target or Year-End
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    n = data["n"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    warmup = 23  # max(21, 14) + 2

    for i in range(1, n):
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

                costs = brokerage + (abs(exit_price - entry) * position["quantity"] * slippage)
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

        # 2. Check crossover signal when flat
        if position is None and i < n - 1 and i >= warmup:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                atr = atrs[i]
                if np.isnan(atr) or atr <= 0:
                    continue

                entry_price = closes[i]
                risk_amount = capital * BASELINE_RISK_PER_TRADE
                risk_per_share = atr * stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    continue

                if signal == "LONG":
                    stop = entry_price - atr * stop_atr
                    target = entry_price + atr * target_atr
                else:
                    stop = entry_price + atr * stop_atr
                    target = entry_price - atr * target_atr

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

    # 3. Year-end square off
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]

        if side == "LONG":
            gross_pnl = (last_close - entry) * position["quantity"]
        else:
            gross_pnl = (entry - last_close) * position["quantity"]

        costs = brokerage + (abs(last_close - entry) * position["quantity"] * slippage)
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


def calculate_mae_mfe(trades: list[dict], data_dict: dict[str, dict]) -> list[dict]:
    """Calculates strictly causal MAE and MFE for every trade normalized by ATR at entry.
    
    MAE = Maximum Adverse Excursion during trade holding period
    MFE = Maximum Favorable Excursion during trade holding period
    """
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

        # If trade exited immediately at next bar
        if start_idx > end_idx:
            start_idx = end_idx

        holding_highs = highs[start_idx : end_idx + 1]
        holding_lows = lows[start_idx : end_idx + 1]

        if side == "LONG":
            # For LONG: favorable is price above entry, adverse is price below entry
            # On the exit bar itself, bounded by stop / target execution
            max_favorable_points = max(0.0, float(np.max(holding_highs) - entry_price))
            max_adverse_points = max(0.0, float(entry_price - np.min(holding_lows)))

            # Cap adverse excursion at stop if exit reason was STOP
            if t["exit_reason"] == "STOP":
                max_adverse_points = max(max_adverse_points, entry_price - stop_price)
            if t["exit_reason"] == "TARGET":
                max_favorable_points = max(max_favorable_points, target_price - entry_price)

        else:
            # For SHORT: favorable is price below entry, adverse is price above entry
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

        enriched_trades.append(t_copy)

    return enriched_trades


def extract_entry_features(trades: list[dict], data_dict: dict[str, dict]) -> list[dict]:
    """Extracts all Part B required features for every trade using information available strictly at entry bar."""
    # Pre-extract numpy arrays per symbol for ultra-fast vector access
    sym_arrays = {}
    for sym, data in data_dict.items():
        df = data["df"]
        sym_arrays[sym] = {
            "ema9": df["EMA9"].to_numpy(dtype=float),
            "ema21": df["EMA21"].to_numpy(dtype=float),
            "ema50": df["EMA50"].to_numpy(dtype=float),
            "ema_spread": df["EMA_SPREAD"].to_numpy(dtype=float),
            "ema_spread_pct": df["EMA_SPREAD_PCT"].to_numpy(dtype=float),
            "rsi14": df["RSI"].to_numpy(dtype=float),
            "atr14": df["ATR"].to_numpy(dtype=float),
            "atr_pct": df["ATR_PCT"].to_numpy(dtype=float),
            "adx14": df["ADX"].to_numpy(dtype=float),
            "candle_body_pct": df["CANDLE_BODY_PCT"].to_numpy(dtype=float),
            "candle_range_pct": df["CANDLE_RANGE_PCT"].to_numpy(dtype=float),
            "dist_recent_high_pct": df["DIST_HIGH_20_PCT"].to_numpy(dtype=float),
            "dist_recent_low_pct": df["DIST_LOW_20_PCT"].to_numpy(dtype=float),
            "dist_vwap_pct": df["DIST_VWAP_PCT"].to_numpy(dtype=float),
            "slope_ema9": df["EMA9_SLOPE"].to_numpy(dtype=float),
            "slope_ema21": df["EMA21_SLOPE"].to_numpy(dtype=float),
            "prev_3bar_ret": df["RET_3BAR"].to_numpy(dtype=float),
            "prev_5bar_ret": df["RET_5BAR"].to_numpy(dtype=float),
            "prev_10bar_ret": df["RET_10BAR"].to_numpy(dtype=float),
            "prev_15bar_ret": df["RET_15BAR"].to_numpy(dtype=float),
            "vol_relative_rolling": df["VOL_RATIO"].to_numpy(dtype=float),
            "crossover_count_20": df["CROSSOVER_COUNT_20"].to_numpy(dtype=float),
            "efficiency_ratio_20": df["EFFICIENCY_RATIO_20"].to_numpy(dtype=float),
            "is_high_vol": df["IS_HIGH_VOL"].to_numpy(dtype=bool),
            "closes": df["Close"].to_numpy(dtype=float),
        }

    featured_trades = []
    for t in trades:
        t_copy = dict(t)
        sym = t["symbol"]
        arr = sym_arrays[sym]
        idx = t["entry_bar_idx"]

        entry_dt = pd.to_datetime(t["entry_datetime"])
        t_copy["hour"] = entry_dt.hour
        t_copy["minute"] = entry_dt.minute
        t_copy["ema9"] = round(float(arr["ema9"][idx]), 4)
        t_copy["ema21"] = round(float(arr["ema21"][idx]), 4)
        t_copy["ema_spread"] = round(float(arr["ema_spread"][idx]), 4)
        t_copy["ema_spread_pct"] = round(float(arr["ema_spread_pct"][idx]), 4)
        t_copy["rsi14"] = round(float(arr["rsi14"][idx]), 2)
        t_copy["atr14"] = round(float(arr["atr14"][idx]), 4)
        t_copy["atr_pct"] = round(float(arr["atr_pct"][idx]), 4)
        t_copy["adx14"] = round(float(arr["adx14"][idx]), 2)
        cbp = arr["candle_body_pct"][idx]
        t_copy["candle_body_pct"] = round(float(cbp), 2) if not np.isnan(cbp) else 0.0
        t_copy["candle_range_pct"] = round(float(arr["candle_range_pct"][idx]), 4)
        t_copy["dist_recent_high_pct"] = round(float(arr["dist_recent_high_pct"][idx]), 4)
        t_copy["dist_recent_low_pct"] = round(float(arr["dist_recent_low_pct"][idx]), 4)
        dv = arr["dist_vwap_pct"][idx]
        t_copy["dist_vwap_pct"] = round(float(dv), 4) if not np.isnan(dv) else 0.0
        s9 = arr["slope_ema9"][idx]
        t_copy["slope_ema9"] = round(float(s9), 4) if not np.isnan(s9) else 0.0
        s21 = arr["slope_ema21"][idx]
        t_copy["slope_ema21"] = round(float(s21), 4) if not np.isnan(s21) else 0.0
        r3 = arr["prev_3bar_ret"][idx]
        t_copy["prev_3bar_ret"] = round(float(r3), 4) if not np.isnan(r3) else 0.0
        r5 = arr["prev_5bar_ret"][idx]
        t_copy["prev_5bar_ret"] = round(float(r5), 4) if not np.isnan(r5) else 0.0
        r10 = arr["prev_10bar_ret"][idx]
        t_copy["prev_10bar_ret"] = round(float(r10), 4) if not np.isnan(r10) else 0.0
        r15 = arr["prev_15bar_ret"][idx]
        t_copy["prev_15bar_ret"] = round(float(r15), 4) if not np.isnan(r15) else 0.0
        vr = arr["vol_relative_rolling"][idx]
        t_copy["vol_relative_rolling"] = round(float(vr), 2) if not np.isnan(vr) else 1.0
        cc = arr["crossover_count_20"][idx]
        t_copy["crossover_count_20"] = int(cc) if not np.isnan(cc) else 0
        er = arr["efficiency_ratio_20"][idx]
        t_copy["efficiency_ratio_20"] = round(float(er), 4) if not np.isnan(er) else 0.0
        t_copy["is_high_vol"] = bool(arr["is_high_vol"][idx])

        # Regime classification
        close = arr["closes"][idx]
        ema50 = arr["ema50"][idx]
        ema21 = arr["ema21"][idx]
        prev_idx = max(0, idx - 10)
        prev_ema21 = arr["ema21"][prev_idx]

        if close > ema50 and ema21 > prev_ema21:
            regime = "TREND_UP"
        elif close < ema50 and ema21 < prev_ema21:
            regime = "TREND_DOWN"
        else:
            regime = "RANGE"

        t_copy["regime_trend"] = regime
        t_copy["regime_vol"] = "HIGH_VOL" if arr["is_high_vol"][idx] else "LOW_VOL"

        featured_trades.append(t_copy)

    return featured_trades


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
    n_losses = len(losses)
    win_rate = (n_wins / n * 100.0) if n > 0 else 0.0

    # Net-based profit factor (matching Phase 1 & 2 baseline of 0.9248)
    net_win_sum = float(wins["pnl"].sum()) if n_wins > 0 else 0.0
    net_loss_sum = float(abs(losses["pnl"].sum())) if n_losses > 0 else 0.0
    pf = (net_win_sum / net_loss_sum) if net_loss_sum > 0 else 0.0

    # Gross profit factor
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

    # Max loss streak
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


def run_stop_target_grid(
    data_dict: dict[str, dict],
    stop_mults: list[float] = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5],
    target_mults: list[float] = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0],
) -> list[dict]:
    """Evaluates the 7x7 (49 combination) Stop and Target matrix across all 5 symbols."""
    results = []

    for stop_m in stop_mults:
        for target_m in target_mults:
            all_trades = []
            for sym, data in data_dict.items():
                t = simulate_baseline_forensics(
                    symbol=sym,
                    data=data,
                    stop_atr=stop_m,
                    target_atr=target_m,
                )
                all_trades.extend(t)

            m = calculate_portfolio_metrics(all_trades)
            results.append({
                "stop_multiplier": stop_m,
                "target_multiplier": target_m,
                "reward_to_risk": round(target_m / stop_m, 2),
                "trades": m["trades"],
                "win_rate": m["win_rate"],
                "gross_pnl": m["gross_pnl"],
                "costs": m["costs"],
                "net_pnl": m["net_pnl"],
                "profit_factor": m["profit_factor"],
                "average_trade": m["average_trade"],
                "max_drawdown": m["max_drawdown"],
                "max_loss_streak": m["max_consecutive_losses"],
            })

    return results


def simulate_entry_delay(
    symbol: str,
    data: dict,
    delay_bars: int = 0,
    stop_atr: float = BASELINE_STOP_ATR,
    target_atr: float = BASELINE_TARGET_ATR,
) -> list[dict]:
    """Simulates fixed entry execution delay (0, 1, 2, 3, 5 bars) after EMA crossover signal."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    n = data["n"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    warmup = 23

    i = warmup
    while i < n - 1:
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
            else:
                if highs[i] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif lows[i] <= target:
                    exit_price = target
                    exit_reason = "TARGET"

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
                i += 1
                continue

        # 2. Check crossover signal when flat
        if position is None:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                entry_bar = i + delay_bars
                if entry_bar >= n - 1:
                    i += 1
                    continue

                atr = atrs[entry_bar]
                if np.isnan(atr) or atr <= 0:
                    i += 1
                    continue

                entry_price = closes[entry_bar]
                risk_amount = capital * BASELINE_RISK_PER_TRADE
                risk_per_share = atr * stop_atr
                qty = int(risk_amount / risk_per_share)
                if qty <= 0:
                    i += 1
                    continue

                if signal == "LONG":
                    stop = entry_price - atr * stop_atr
                    target = entry_price + atr * target_atr
                else:
                    stop = entry_price + atr * stop_atr
                    target = entry_price - atr * target_atr

                position = {
                    "side": signal,
                    "entry_time": dates[entry_bar],
                    "entry_bar_idx": entry_bar,
                    "entry_price": entry_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                    "atr_at_entry": atr,
                }
                i = entry_bar + 1
                continue

        i += 1

    # Square off at year end
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


def simulate_pullback_entry(
    symbol: str,
    data: dict,
    max_wait_bars: int = 5,
    stop_atr: float = BASELINE_STOP_ATR,
    target_atr: float = BASELINE_TARGET_ATR,
) -> list[dict]:
    """Simulates waiting for a price pullback toward EMA21 after a crossover before entering."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    n = data["n"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    warmup = 23
    i = warmup

    while i < n - 1:
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
                i += 1
                continue

        if position is None:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                # Wait for pullback to EMA21 within max_wait_bars
                entry_found = False
                for step in range(1, max_wait_bars + 1):
                    cand_idx = i + step
                    if cand_idx >= n - 1:
                        break
                    
                    if signal == "LONG":
                        # Crossover invalidation check
                        if ema9[cand_idx] < ema21[cand_idx]:
                            break
                        # Pullback: low reaches or pierces EMA21
                        if lows[cand_idx] <= ema21[cand_idx]:
                            entry_found = True
                            entry_bar = cand_idx
                            break
                    else:
                        if ema9[cand_idx] > ema21[cand_idx]:
                            break
                        if highs[cand_idx] >= ema21[cand_idx]:
                            entry_found = True
                            entry_bar = cand_idx
                            break

                if entry_found:
                    atr = atrs[entry_bar]
                    if not np.isnan(atr) and atr > 0:
                        entry_price = closes[entry_bar]
                        risk_amount = capital * BASELINE_RISK_PER_TRADE
                        risk_per_share = atr * stop_atr
                        qty = int(risk_amount / risk_per_share)
                        if qty > 0:
                            if signal == "LONG":
                                stop = entry_price - atr * stop_atr
                                target = entry_price + atr * target_atr
                            else:
                                stop = entry_price + atr * stop_atr
                                target = entry_price - atr * target_atr

                            position = {
                                "side": signal,
                                "entry_time": dates[entry_bar],
                                "entry_bar_idx": entry_bar,
                                "entry_price": entry_price,
                                "stop_price": stop,
                                "target_price": target,
                                "quantity": qty,
                                "atr_at_entry": atr,
                            }
                            i = entry_bar + 1
                            continue
                # If no entry or expired, advance
                i += 1
                continue

        i += 1

    # Square off at year end
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


def simulate_momentum_confirmation_entry(
    symbol: str,
    data: dict,
    max_confirm_bars: int = 3,
    stop_atr: float = BASELINE_STOP_ATR,
    target_atr: float = BASELINE_TARGET_ATR,
) -> list[dict]:
    """Simulates entering only upon momentum confirmation (break of signal bar high/low)."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    n = data["n"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    warmup = 23
    i = warmup

    while i < n - 1:
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
                i += 1
                continue

        if position is None:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
                trigger_price = highs[i]
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"
                trigger_price = lows[i]

            if signal is not None:
                entry_found = False
                for step in range(1, max_confirm_bars + 1):
                    cand_idx = i + step
                    if cand_idx >= n - 1:
                        break
                    
                    if signal == "LONG":
                        if ema9[cand_idx] < ema21[cand_idx]:
                            break
                        if closes[cand_idx] > trigger_price:
                            entry_found = True
                            entry_bar = cand_idx
                            break
                    else:
                        if ema9[cand_idx] > ema21[cand_idx]:
                            break
                        if closes[cand_idx] < trigger_price:
                            entry_found = True
                            entry_bar = cand_idx
                            break

                if entry_found:
                    atr = atrs[entry_bar]
                    if not np.isnan(atr) and atr > 0:
                        entry_price = closes[entry_bar]
                        risk_amount = capital * BASELINE_RISK_PER_TRADE
                        risk_per_share = atr * stop_atr
                        qty = int(risk_amount / risk_per_share)
                        if qty > 0:
                            if signal == "LONG":
                                stop = entry_price - atr * stop_atr
                                target = entry_price + atr * target_atr
                            else:
                                stop = entry_price + atr * stop_atr
                                target = entry_price - atr * target_atr

                            position = {
                                "side": signal,
                                "entry_time": dates[entry_bar],
                                "entry_bar_idx": entry_bar,
                                "entry_price": entry_price,
                                "stop_price": stop,
                                "target_price": target,
                                "quantity": qty,
                                "atr_at_entry": atr,
                            }
                            i = entry_bar + 1
                            continue

                i += 1
                continue

        i += 1

    # Square off at year end
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


def simulate_candidate_strategy(
    symbol: str,
    data: dict,
    candidate_id: str,
    stop_atr: float = 1.5,
    target_atr: float = 3.0,
) -> tuple[list[dict], int]:
    """Simulates controlled candidate strategies:
    
    Candidate 1: Chop-Filtered Trend Follower
      - Crossover + Chop Score < 2 (crossovers in last 20 bars < 2)
      - Alignment with intermediate trend (LONG: Close > EMA50, SHORT: Close < EMA50)
      - Stop: 1.5 ATR, Target: 2.5 ATR
    
    Candidate 2: Pullback Entry with Tighter Target
      - Wait for pullback to EMA21 (within 5 bars)
      - Evidence-based stop/target from forensic matrix (Stop: 1.25 ATR, Target: 1.5 ATR)
    
    Candidate 3: Time Window + Momentum Breakout
      - Avoid lunch chop (Trade only 09:30-11:15 and 13:30-15:00)
      - Require momentum confirmation bar breakout (Close > Signal High for LONG, Close < Signal Low for SHORT)
      - Stop: 1.5 ATR, Target: 2.0 ATR
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    ema50 = data["ema50"]
    rsis = data["rsis"]
    crossover_cnt = data["crossover_count_20"]
    dates = data["dates"]
    n = data["n"]

    capital = BASELINE_INITIAL_CAPITAL
    position = None
    trades = []
    filtered_signals_count = 0
    warmup = 52

    i = warmup
    while i < n - 1:
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
                i += 1
                continue

        if position is None:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                # ----------------------------------------------------
                # CANDIDATE 1: Chop-Filtered Trend Follower
                # ----------------------------------------------------
                if candidate_id == "candidate_1":
                    # Filter 1: Chop exclusion (less than 2 crossovers in past 20 bars)
                    if crossover_cnt[i] >= 2:
                        filtered_signals_count += 1
                        i += 1
                        continue
                    # Filter 2: Trend alignment with EMA50
                    if signal == "LONG" and closes[i] <= ema50[i]:
                        filtered_signals_count += 1
                        i += 1
                        continue
                    if signal == "SHORT" and closes[i] >= ema50[i]:
                        filtered_signals_count += 1
                        i += 1
                        continue

                    # Execute entry at bar close
                    atr = atrs[i]
                    if np.isnan(atr) or atr <= 0:
                        i += 1
                        continue
                    entry_price = closes[i]
                    qty = int((capital * BASELINE_RISK_PER_TRADE) / (atr * stop_atr))
                    if qty <= 0:
                        i += 1
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
                    i += 1
                    continue

                # ----------------------------------------------------
                # CANDIDATE 2: Pullback Entry with Tighter Target
                # ----------------------------------------------------
                elif candidate_id == "candidate_2":
                    entry_found = False
                    for step in range(1, 6):
                        cand_idx = i + step
                        if cand_idx >= n - 1:
                            break
                        if signal == "LONG":
                            if ema9[cand_idx] < ema21[cand_idx]:
                                break
                            if lows[cand_idx] <= ema21[cand_idx]:
                                entry_found = True
                                entry_bar = cand_idx
                                break
                        else:
                            if ema9[cand_idx] > ema21[cand_idx]:
                                break
                            if highs[cand_idx] >= ema21[cand_idx]:
                                entry_found = True
                                entry_bar = cand_idx
                                break

                    if not entry_found:
                        filtered_signals_count += 1
                        i += 1
                        continue

                    atr = atrs[entry_bar]
                    if np.isnan(atr) or atr <= 0:
                        i += 1
                        continue
                    entry_price = closes[entry_bar]
                    qty = int((capital * BASELINE_RISK_PER_TRADE) / (atr * stop_atr))
                    if qty <= 0:
                        i += 1
                        continue

                    stop = entry_price - atr * stop_atr if signal == "LONG" else entry_price + atr * stop_atr
                    target = entry_price + atr * target_atr if signal == "LONG" else entry_price - atr * target_atr
                    position = {
                        "side": signal,
                        "entry_time": dates[entry_bar],
                        "entry_bar_idx": entry_bar,
                        "entry_price": entry_price,
                        "stop_price": stop,
                        "target_price": target,
                        "quantity": qty,
                        "atr_at_entry": atr,
                    }
                    i = entry_bar + 1
                    continue

                # ----------------------------------------------------
                # CANDIDATE 3: Time Window + Momentum Confirmation
                # ----------------------------------------------------
                elif candidate_id == "candidate_3":
                    dt_val = pd.to_datetime(dates[i])
                    time_val = dt_val.time()
                    # Trading hours: 09:30-11:15 or 13:30-15:00
                    in_morning = (time_val >= pd.to_datetime("09:30").time()) and (time_val <= pd.to_datetime("11:15").time())
                    in_afternoon = (time_val >= pd.to_datetime("13:30").time()) and (time_val <= pd.to_datetime("15:00").time())
                    if not (in_morning or in_afternoon):
                        filtered_signals_count += 1
                        i += 1
                        continue

                    # Momentum confirmation: break of signal candle high / low
                    trigger = highs[i] if signal == "LONG" else lows[i]
                    entry_found = False
                    for step in range(1, 4):
                        cand_idx = i + step
                        if cand_idx >= n - 1:
                            break
                        if signal == "LONG":
                            if ema9[cand_idx] < ema21[cand_idx]:
                                break
                            if closes[cand_idx] > trigger:
                                entry_found = True
                                entry_bar = cand_idx
                                break
                        else:
                            if ema9[cand_idx] > ema21[cand_idx]:
                                break
                            if closes[cand_idx] < trigger:
                                entry_found = True
                                entry_bar = cand_idx
                                break

                    if not entry_found:
                        filtered_signals_count += 1
                        i += 1
                        continue

                    atr = atrs[entry_bar]
                    if np.isnan(atr) or atr <= 0:
                        i += 1
                        continue
                    entry_price = closes[entry_bar]
                    qty = int((capital * BASELINE_RISK_PER_TRADE) / (atr * stop_atr))
                    if qty <= 0:
                        i += 1
                        continue

                    stop = entry_price - atr * stop_atr if signal == "LONG" else entry_price + atr * stop_atr
                    target = entry_price + atr * target_atr if signal == "LONG" else entry_price - atr * target_atr
                    position = {
                        "side": signal,
                        "entry_time": dates[entry_bar],
                        "entry_bar_idx": entry_bar,
                        "entry_price": entry_price,
                        "stop_price": stop,
                        "target_price": target,
                        "quantity": qty,
                        "atr_at_entry": atr,
                    }
                    i = entry_bar + 1
                    continue

        i += 1

    # Square off at year end
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

    return trades, filtered_signals_count

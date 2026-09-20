"""
SignalForge — Phase 4: Setup Quality & Signal Scoring Engine
============================================================
File: src/strategy/phase4_signal_quality.py

Implements a causal 0-100 setup quality scoring engine for 1-minute EMA crossover candidates:
- Extracts 20 strictly causal features at the candidate entry timestamp.
- Classifies market regimes without future information (TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY).
- Calculates controlled scoring models (Variants A, B, C, D, E) bounded in [0, 100].
- Supports score threshold evaluations (>= 50, 60, 70, 80).
- Preserves exact baseline execution mathematics and validated 2018 dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple, Dict, Any, List
import numpy as np
import pandas as pd

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

DEFAULT_STOP_ATR: float = 1.5
DEFAULT_TARGET_ATR: float = 3.0
DEFAULT_RISK_PER_TRADE: float = 0.01
DEFAULT_BROKERAGE: float = 20.0
DEFAULT_SLIPPAGE: float = 0.0005
DEFAULT_INITIAL_CAPITAL: float = 100000.0


@dataclass(frozen=True)
class SignalQualityConfig:
    name: str = "FULL_QUALITY"
    model_type: Literal["variant_a", "variant_b", "variant_c", "variant_d", "variant_e"] = "variant_e"
    min_score_threshold: float = 0.0
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    adx_period: int = 14
    stop_atr: float = DEFAULT_STOP_ATR
    target_atr: float = DEFAULT_TARGET_ATR
    risk_per_trade: float = DEFAULT_RISK_PER_TRADE
    brokerage_per_trade: float = DEFAULT_BROKERAGE
    slippage: float = DEFAULT_SLIPPAGE
    initial_capital: float = DEFAULT_INITIAL_CAPITAL


def load_clean_symbol_data(symbol: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Loads validated clean 2018 1-minute data for the given symbol."""
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


def calculate_causal_features(df_raw: pd.DataFrame, config: Optional[SignalQualityConfig] = None) -> dict:
    """Precomputes 20 strictly causal features and regimes across all 1-minute bars."""
    if config is None:
        config = SignalQualityConfig()

    df = df_raw.copy()
    if "dt" not in df.columns:
        df["dt"] = pd.to_datetime(df["Date"])

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]
    opens = df["Open"]
    volumes = df["Volume"]

    # 1. EMA 9 & 21
    df["EMA9"] = closes.ewm(span=config.fast_ema, adjust=False).mean()
    df["EMA21"] = closes.ewm(span=config.slow_ema, adjust=False).mean()

    # 2. EMA Separation % & Slope
    df["EMA_SEP_PCT"] = (df["EMA9"] - df["EMA21"]).abs() / closes * 100.0
    df["EMA_SLOPE"] = (df["EMA9"] - df["EMA9"].shift(1)) / closes * 100.0

    # 3. RSI(14)
    delta = closes.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / config.rsi_period, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / config.rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100.0 - (100.0 / (1.0 + rs))

    # 4. True Range & ATR(14)
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(config.atr_period).mean()
    df["ATR_PCT"] = (df["ATR"] / closes) * 100.0

    # 5. Wilder's ADX(14), +DI, -DI
    up_move = highs - highs.shift(1)
    down_move = lows.shift(1) - lows
    pos_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    neg_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr_smooth = tr.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()
    pos_dm_smooth = pos_dm.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()
    neg_dm_smooth = neg_dm.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()

    df["POS_DI"] = 100.0 * (pos_dm_smooth / tr_smooth.replace(0, np.nan))
    df["NEG_DI"] = 100.0 * (neg_dm_smooth / tr_smooth.replace(0, np.nan))
    di_sum = df["POS_DI"] + df["NEG_DI"]
    dx = (100.0 * ((df["POS_DI"] - df["NEG_DI"]).abs() / di_sum.replace(0, np.nan))).fillna(0.0)
    df["ADX"] = dx.ewm(alpha=1.0 / config.adx_period, adjust=False).mean()

    # 6. Recent momentum (5-bar return)
    df["RET_5"] = (closes - closes.shift(5)) / closes.shift(5) * 100.0

    # 7. Volume relative to 20-bar rolling average
    vol_mean_20 = volumes.rolling(20).mean()
    df["VOL_RATIO"] = volumes / vol_mean_20.replace(0, np.nan)

    # 8. Candle body/range ratio & direction
    c_range = highs - lows
    df["CANDLE_BODY_RATIO"] = (closes - opens).abs() / c_range.replace(0, np.nan)
    df["CANDLE_DIR"] = np.where(closes > opens, 1, np.where(closes < opens, -1, 0))

    # 9. Distance from EMA9 & EMA21
    df["DIST_EMA9"] = (closes - df["EMA9"]) / closes * 100.0
    df["DIST_EMA21"] = (closes - df["EMA21"]) / closes * 100.0

    # 10. Distance from 20-bar extreme
    df["ROLL_HIGH_20"] = highs.rolling(20).max()
    df["ROLL_LOW_20"] = lows.rolling(20).min()
    df["DIST_HIGH_20"] = (df["ROLL_HIGH_20"] - closes) / closes * 100.0
    df["DIST_LOW_20"] = (closes - df["ROLL_LOW_20"]) / closes * 100.0

    # 11. Time of day
    df["HOUR"] = df["dt"].dt.hour
    df["MINUTE"] = df["dt"].dt.minute

    # 12. Realized Volatility (20-bar return std dev)
    log_ret = np.log(closes / closes.shift(1))
    df["REALIZED_VOL"] = log_ret.rolling(20).std() * np.sqrt(252 * 375) * 100.0

    # 13. Regime Classification (strictly causal)
    atr_mean_100 = df["ATR_PCT"].rolling(100).mean()
    is_high_vol = df["ATR_PCT"] > (atr_mean_100 * 1.35)
    is_low_vol = df["ATR_PCT"] < (atr_mean_100 * 0.70)
    is_trend_up = (df["EMA9"] > df["EMA21"]) & (df["ADX"] >= 20.0) & (df["POS_DI"] > df["NEG_DI"])
    is_trend_down = (df["EMA9"] < df["EMA21"]) & (df["ADX"] >= 20.0) & (df["NEG_DI"] > df["POS_DI"])

    regimes = []
    for idx in range(len(df)):
        if is_high_vol.iloc[idx]:
            regimes.append("HIGH_VOLATILITY")
        elif is_low_vol.iloc[idx]:
            regimes.append("LOW_VOLATILITY")
        elif is_trend_up.iloc[idx]:
            regimes.append("TREND_UP")
        elif is_trend_down.iloc[idx]:
            regimes.append("TREND_DOWN")
        else:
            regimes.append("RANGE")
    df["REGIME"] = regimes

    # Fill initial NaNs safely with neutral values
    df = df.bfill().ffill()

    return {
        "df": df,
        "highs": df["High"].to_numpy(),
        "lows": df["Low"].to_numpy(),
        "closes": df["Close"].to_numpy(),
        "opens": df["Open"].to_numpy(),
        "volumes": df["Volume"].to_numpy(),
        "atrs": df["ATR"].to_numpy(),
        "atr_pcts": df["ATR_PCT"].to_numpy(),
        "ema9": df["EMA9"].to_numpy(),
        "ema21": df["EMA21"].to_numpy(),
        "ema_sep_pct": df["EMA_SEP_PCT"].to_numpy(),
        "ema_slope": df["EMA_SLOPE"].to_numpy(),
        "rsis": df["RSI"].to_numpy(),
        "adxs": df["ADX"].to_numpy(),
        "pos_di": df["POS_DI"].to_numpy(),
        "neg_di": df["NEG_DI"].to_numpy(),
        "ret_5": df["RET_5"].to_numpy(),
        "vol_ratio": df["VOL_RATIO"].to_numpy(),
        "candle_body_ratio": df["CANDLE_BODY_RATIO"].to_numpy(),
        "candle_dir": df["CANDLE_DIR"].to_numpy(),
        "dist_ema9": df["DIST_EMA9"].to_numpy(),
        "dist_ema21": df["DIST_EMA21"].to_numpy(),
        "dist_high_20": df["DIST_HIGH_20"].to_numpy(),
        "dist_low_20": df["DIST_LOW_20"].to_numpy(),
        "hours": df["HOUR"].to_numpy(),
        "realized_vol": df["REALIZED_VOL"].to_numpy(),
        "regimes": df["REGIME"].tolist(),
        "dates": df["Date"].tolist(),
        "dt_series": df["dt"],
        "n": len(df),
    }


def compute_setup_score(
    i: int,
    direction: str,
    data: dict,
    model_type: str = "variant_e",
) -> float:
    """Computes a strictly causal 0-100 setup quality score for candidate entry at bar i."""
    if model_type == "variant_a":
        return 50.0  # Baseline: uniform unweighted

    adx_val = data["adxs"][i]
    pos_di_val = data["pos_di"][i]
    neg_di_val = data["neg_di"][i]
    rsi_val = data["rsis"][i]
    ret5_val = data["ret_5"][i]
    vol_rat = data["vol_ratio"][i]
    c_body = data["candle_body_ratio"][i]
    c_dir = data["candle_dir"][i]
    hour = data["hours"][i]
    dist_ema9 = abs(data["dist_ema9"][i])
    atr_pct = data["atr_pcts"][i]

    # 1. Trend Sub-Score (0-100)
    adx_score = min(100.0, max(0.0, (adx_val - 15.0) / 25.0 * 100.0))
    if direction == "LONG":
        di_spread = pos_di_val - neg_di_val
    else:
        di_spread = neg_di_val - pos_di_val
    di_score = min(100.0, max(0.0, (di_spread + 10.0) / 30.0 * 100.0))
    trend_score = 0.5 * adx_score + 0.5 * di_score

    # 2. Momentum Sub-Score (0-100)
    if direction == "LONG":
        rsi_score = min(100.0, max(0.0, (rsi_val - 45.0) / 25.0 * 100.0))
        mom_score = min(100.0, max(0.0, (ret5_val + 0.2) / 0.8 * 100.0))
    else:
        rsi_score = min(100.0, max(0.0, (55.0 - rsi_val) / 25.0 * 100.0))
        mom_score = min(100.0, max(0.0, (-ret5_val + 0.2) / 0.8 * 100.0))
    momentum_score = 0.6 * rsi_score + 0.4 * mom_score

    # 3. Volatility Sub-Score (0-100) - optimal intraday ATR% around 0.15% - 0.45%
    if np.isnan(atr_pct) or atr_pct <= 0:
        vol_score = 50.0
    elif 0.12 <= atr_pct <= 0.45:
        vol_score = 85.0
    elif 0.08 <= atr_pct < 0.12 or 0.45 < atr_pct <= 0.65:
        vol_score = 55.0
    else:
        vol_score = 25.0

    # 4. Volume Sub-Score (0-100)
    if np.isnan(vol_rat) or vol_rat <= 0:
        volume_score = 50.0
    else:
        volume_score = min(100.0, max(0.0, (vol_rat - 0.5) / 1.5 * 100.0))

    # 5. Candle Structure Sub-Score (0-100)
    expected_dir = 1 if direction == "LONG" else -1
    dir_match = (c_dir == expected_dir)
    c_ratio = 0.5 if np.isnan(c_body) else c_body
    candle_score = min(100.0, max(0.0, (c_ratio * 70.0 + (30.0 if dir_match else 0.0))))

    # 6. Price Location Sub-Score (0-100) - closer to EMA9 is better (less overextended)
    loc_score = min(100.0, max(0.0, 100.0 - (dist_ema9 / 0.3 * 100.0)))

    # 7. Time of Day Sub-Score (0-100)
    # Opening session (9:30-11:30) & Afternoon (13:30-15:00) best; Midday (11:30-13:30) worst
    if hour in [9, 10, 14]:
        tod_score = 80.0
    elif hour in [13, 15]:
        tod_score = 65.0
    else:  # hours 11, 12
        tod_score = 35.0

    # Model Variants weighting
    if model_type == "variant_b":
        # Equal-weight quality score across 6 components
        score = (trend_score + momentum_score + vol_score + volume_score + candle_score + loc_score) / 6.0
    elif model_type == "variant_c":
        # Trend + momentum weighted score
        score = 0.55 * trend_score + 0.45 * momentum_score
    elif model_type == "variant_d":
        # Trend + momentum + volatility + volume score
        score = 0.40 * trend_score + 0.30 * momentum_score + 0.15 * vol_score + 0.15 * volume_score
    elif model_type == "variant_e":
        # Full quality score (all dimensions including time-of-day and candle confirmation)
        score = (
            0.30 * trend_score
            + 0.25 * momentum_score
            + 0.15 * vol_score
            + 0.10 * volume_score
            + 0.10 * candle_score
            + 0.05 * loc_score
            + 0.05 * tod_score
        )
    else:
        score = 50.0

    return round(float(min(100.0, max(0.0, score))), 2)


def simulate_signal_quality(
    symbol: str,
    data: dict,
    config: SignalQualityConfig,
) -> Tuple[List[dict], List[dict]]:
    """Simulates trading under the SignalQualityConfig.
    
    Returns:
        trades: list of executed trades that met the score threshold.
        all_candidates: list of ALL crossover candidate opportunities with full feature vectors and scores.
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    dt_series = data["dt_series"]
    regimes = data["regimes"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    trades = []
    all_candidates = []
    warmup = max(config.slow_ema, config.rsi_period, config.atr_period) + 2

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
                gross_pnl = (exit_price - entry) * position["quantity"] if side == "LONG" else (entry - exit_price) * position["quantity"]
                costs = config.brokerage_per_trade + (abs(exit_price - entry) * position["quantity"] * config.slippage)
                net_pnl = gross_pnl - costs
                capital += net_pnl

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
                    "setup_score": position["setup_score"],
                    "regime": position["regime"],
                    "holding_duration_bars": i - position["entry_bar_idx"],
                    "entry_hour": dt_series.iloc[position["entry_bar_idx"]].hour,
                    "entry_month": dt_series.iloc[position["entry_bar_idx"]].month,
                })
                position = None
                continue

        # 2. Check crossover candidates when flat
        if position is None and i < n - 1 and i >= warmup:
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50.0:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50.0:
                signal = "SHORT"

            if signal is not None:
                # Compute causal 0-100 setup score
                score = compute_setup_score(i, signal, data, model_type=config.model_type)

                candidate_rec = {
                    "symbol": symbol,
                    "datetime": dates[i],
                    "bar_idx": i,
                    "direction": signal,
                    "setup_score": score,
                    "regime": regimes[i],
                    "ema9": round(float(ema9[i]), 2),
                    "ema21": round(float(ema21[i]), 2),
                    "ema_sep_pct": round(float(data["ema_sep_pct"][i]), 4),
                    "ema_slope": round(float(data["ema_slope"][i]), 4),
                    "rsi": round(float(rsis[i]), 2),
                    "atr": round(float(atrs[i]), 2),
                    "atr_pct": round(float(data["atr_pcts"][i]), 3),
                    "adx": round(float(data["adxs"][i]), 2),
                    "pos_di": round(float(data["pos_di"][i]), 2),
                    "neg_di": round(float(data["neg_di"][i]), 2),
                    "ret_5": round(float(data["ret_5"][i]), 3),
                    "vol_ratio": round(float(data["vol_ratio"][i]), 2),
                    "candle_body_ratio": round(float(data["candle_body_ratio"][i]), 3),
                    "candle_dir": int(data["candle_dir"][i]),
                    "dist_ema9": round(float(data["dist_ema9"][i]), 3),
                    "dist_ema21": round(float(data["dist_ema21"][i]), 3),
                    "hour": int(data["hours"][i]),
                    "realized_vol": round(float(data["realized_vol"][i]), 2),
                }
                all_candidates.append(candidate_rec)

                # Filter by score threshold
                if score >= config.min_score_threshold:
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
                                "setup_score": score,
                                "regime": regimes[i],
                            }

    # 3. Year-end square-off
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]
        qty = position["quantity"]

        gross_pnl = (last_close - entry) * qty if side == "LONG" else (entry - last_close) * qty
        costs = config.brokerage_per_trade + (abs(last_close - entry) * qty * config.slippage)
        net_pnl = gross_pnl - costs
        capital += net_pnl

        trades.append({
            "symbol": symbol,
            "direction": side,
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_price": entry,
            "exit_price": last_close,
            "stop_price": position["stop_price"],
            "target_price": position["target_price"],
            "quantity": qty,
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
            "setup_score": position["setup_score"],
            "regime": position["regime"],
            "holding_duration_bars": n - 1 - position["entry_bar_idx"],
            "entry_hour": dt_series.iloc[position["entry_bar_idx"]].hour,
            "entry_month": dt_series.iloc[position["entry_bar_idx"]].month,
        })

    return trades, all_candidates


def calculate_portfolio_metrics(trades_list: list[dict]) -> dict:
    """Calculates all required portfolio metrics for a trade sequence."""
    n = len(trades_list)
    if n == 0:
        return {
            "trades": 0, "trades_per_day": 0.0, "win_rate": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
            "gross_pnl": 0.0, "net_pnl": 0.0, "gross_profit_factor": 0.0, "profit_factor": 0.0,
            "gross_expectancy": 0.0, "net_expectancy": 0.0, "average_trade": 0.0, "median_trade": 0.0,
            "average_winner": 0.0, "average_loser": 0.0, "reward_risk_ratio": 0.0, "max_drawdown": 0.0,
            "max_loss_streak": 0, "transaction_costs": 0.0,
        }

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

    equity = df_sorted["capital_after_trade"].to_numpy()
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

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

    median_trade = float(df_sorted["pnl"].median())

    return {
        "trades": n,
        "trades_per_day": round(n / 245.0, 1),
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
    }

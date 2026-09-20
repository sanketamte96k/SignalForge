"""
SignalForge — Strategy Evolution Phase 4: Exit & Risk/Reward Architecture Engine
================================================================================
File: src/strategy_evolution/phase4_exit_risk.py

Implements Phase 4 research engine evaluating exit architectures on top of
the Phase 3 Pullback candidate and validating against Baseline Control:
- Variant 0: Baseline Control (Exact existing 1m EMA crossover + RSI >= 50, 1.5/3.0 ATR)
- Variant 1: Pullback + Current Exit (1.5 ATR stop, 3.0 ATR target = 1:2 R:R)
- Variant 2: Pullback + 1:1.5 Risk/Reward (1.5 ATR stop, 2.25 ATR target = 1:1.5 R:R)
- Variant 3: Pullback + 1:2 Risk/Reward (1.5 ATR stop, 3.0 ATR target = 1:2 R:R)
- Variant 4: Pullback + 1:2.5 Risk/Reward (1.5 ATR stop, 3.75 ATR target = 1:2.5 R:R)
- Variant 5: Pullback + Trailing Stop (1.5 ATR stop, trail at peak - 1.5 ATR after +1.0R)
- Variant 6: Pullback + Partial Exit (50% exit at +1.0R, remaining 50% at +2.0R or stop)
- Variant 7: Pullback + Time Exit (Exit after 20 bars if still open)
- Variant 8: Pullback + Adaptive ATR Exit (1.0 ATR stop, 2.0 ATR target)

Execution & Accounting:
- Strictly causal, zero look-ahead
- Conservative 1% risk position sizing
- ₹20 Brokerage + 0.05% Slippage
- Single active position per symbol
- Trailing stop ratchet: strictly non-reversing
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import numpy as np
import pandas as pd

VariantType = Literal[
    "baseline",
    "pullback_current",
    "rr_1_5",
    "rr_2",
    "rr_2_5",
    "trailing_stop",
    "partial_exit",
    "time_exit",
    "adaptive_atr",
]

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

DEFAULT_STOP_ATR: float = 1.5
DEFAULT_TARGET_ATR: float = 3.0
DEFAULT_RISK_PER_TRADE: float = 0.01
DEFAULT_BROKERAGE: float = 20.0
DEFAULT_SLIPPAGE: float = 0.0005
DEFAULT_INITIAL_CAPITAL: float = 100000.0


@dataclass(frozen=True)
class Phase4Config:
    name: str = "BASELINE"
    variant: VariantType = "baseline"
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    max_wait_bars: int = 5
    stop_atr: float = DEFAULT_STOP_ATR
    target_atr: float = DEFAULT_TARGET_ATR
    target_r_multiple: float = 2.0
    trailing_activation_r: float = 1.0
    trailing_distance_atr: float = 1.5
    time_exit_bars: int = 20
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


def calculate_phase4_indicators(
    df_raw: pd.DataFrame,
    config: Optional[Phase4Config] = None,
) -> dict:
    """Precomputes strictly causal 1-minute indicators bit-identical to validated baseline."""
    if config is None:
        config = Phase4Config()

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
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "dt_series": df["dt"],
        "n": len(df),
    }


def simulate_phase4_symbol(
    symbol: str,
    data: dict,
    config: Phase4Config,
) -> list[dict]:
    """Simulates trading for a single symbol under the specified Phase 4 configuration.
    
    Zero look-ahead guarantee:
    - Decisions on candle i rely strictly on information available up to and including candle i.
    - Exits are executed sequentially without future knowledge.
    - Trailing stop updates are ratcheted causally (never moving backward).
    """
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    opens = data["opens"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    dates = data["dates"]
    dt_series = data["dt_series"]
    n = data["n"]

    capital = config.initial_capital
    position = None
    trades = []
    warmup = max(config.slow_ema, config.rsi_period, config.atr_period) + 2

    # Determine stop/target multipliers based on variant
    v = config.variant
    if v == "adaptive_atr":
        base_stop_atr = 1.0
        base_target_atr = 2.0
    elif v == "rr_1_5":
        base_stop_atr = 1.5
        base_target_atr = 1.5 * 1.5  # 2.25 ATR
    elif v in ["pullback_current", "rr_2"]:
        base_stop_atr = 1.5
        base_target_atr = 3.0
    elif v == "rr_2_5":
        base_stop_atr = 1.5
        base_target_atr = 1.5 * 2.5  # 3.75 ATR
    else:
        base_stop_atr = config.stop_atr
        base_target_atr = config.target_atr

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
            entry_bar = position["entry_bar_idx"]
            elapsed_bars = i - entry_bar

            exit_price = None
            exit_reason = None
            partial_exit_data = None

            # Special case: Variant 5 (Trailing Stop)
            if v == "trailing_stop":
                atr_entry = position["atr_at_entry"]
                r_dist = atr_entry * base_stop_atr

                # Check if reached activation threshold (+1.0R)
                if side == "LONG":
                    max_seen = max(position.get("peak_price", entry), highs[i])
                    position["peak_price"] = max_seen
                    if (max_seen - entry) >= r_dist:
                        # Activate / ratchet trailing stop at max_seen - 1.5 ATR
                        new_stop = max_seen - (atr_entry * config.trailing_distance_atr)
                        if new_stop > position["stop_price"]:
                            position["stop_price"] = new_stop
                    stop = position["stop_price"]

                    # Check exit: Stop or Year-end (no fixed target for trailing stop)
                    if lows[i] <= stop:
                        exit_price = stop
                        exit_reason = "TRAILING_STOP" if position.get("peak_price", entry) - entry >= r_dist else "STOP"
                else:  # SHORT
                    min_seen = min(position.get("trough_price", entry), lows[i])
                    position["trough_price"] = min_seen
                    if (entry - min_seen) >= r_dist:
                        new_stop = min_seen + (atr_entry * config.trailing_distance_atr)
                        if new_stop < position["stop_price"]:
                            position["stop_price"] = new_stop
                    stop = position["stop_price"]

                    if highs[i] >= stop:
                        exit_price = stop
                        exit_reason = "TRAILING_STOP" if entry - position.get("trough_price", entry) >= r_dist else "STOP"

            # Special case: Variant 6 (Partial Exit: 50% at 1R, remaining 50% at 2R or stop)
            elif v == "partial_exit":
                r_dist = position["atr_at_entry"] * base_stop_atr
                tranche1_target = entry + r_dist if side == "LONG" else entry - r_dist
                tranche2_target = entry + 2.0 * r_dist if side == "LONG" else entry - 2.0 * r_dist

                # Check tranche 1 if not yet taken
                if not position.get("tranche1_taken", False):
                    t1_hit = False
                    if side == "LONG" and highs[i] >= tranche1_target:
                        t1_hit = True
                    elif side == "SHORT" and lows[i] <= tranche1_target:
                        t1_hit = True

                    # Also check if stopped out before tranche 1
                    stopped_out = False
                    if side == "LONG" and lows[i] <= stop:
                        stopped_out = True
                    elif side == "SHORT" and highs[i] >= stop:
                        stopped_out = True

                    if stopped_out:
                        exit_price = stop
                        exit_reason = "STOP"
                    elif t1_hit:
                        # Execute Tranche 1 (50% qty)
                        t1_qty = position["quantity"] // 2
                        if t1_qty <= 0:
                            t1_qty = 1
                        rem_qty = position["quantity"] - t1_qty
                        
                        t1_exit = tranche1_target
                        t1_gross = (t1_exit - entry) * t1_qty if side == "LONG" else (entry - t1_exit) * t1_qty
                        t1_costs = (config.brokerage_per_trade * 0.5) + (abs(t1_exit - entry) * t1_qty * config.slippage)
                        t1_net = t1_gross - t1_costs
                        capital += t1_net

                        # Record tranche 1 trade
                        trades.append({
                            "symbol": symbol,
                            "direction": side,
                            "entry_datetime": position["entry_time"],
                            "exit_datetime": dates[i],
                            "entry_price": entry,
                            "exit_price": t1_exit,
                            "stop_price": stop,
                            "target_price": tranche1_target,
                            "quantity": t1_qty,
                            "gross_pnl": t1_gross,
                            "costs": t1_costs,
                            "pnl": t1_net,
                            "exit_reason": "PARTIAL_TARGET_1R",
                            "capital_after_trade": capital,
                            "holding_duration_bars": i - entry_bar,
                            "entry_hour": dt_series.iloc[entry_bar].hour,
                            "entry_month": dt_series.iloc[entry_bar].month,
                            "mae_points": 0.0,
                            "mfe_points": abs(t1_exit - entry),
                            "atr_at_entry": position["atr_at_entry"],
                        })

                        # Update position to remain active with remaining quantity
                        position["tranche1_taken"] = True
                        position["quantity"] = rem_qty
                        position["target_price"] = tranche2_target
                        # Move stop to breakeven after 1R target hit
                        position["stop_price"] = entry
                        stop = entry
                        target = tranche2_target

                        if rem_qty <= 0:
                            position = None
                            i += 1
                            continue

                # Manage remaining tranche (tranche 2)
                if position is not None and position.get("tranche1_taken", False):
                    if side == "LONG":
                        if lows[i] <= stop:
                            exit_price = stop
                            exit_reason = "BREAKEVEN_STOP"
                        elif highs[i] >= target:
                            exit_price = target
                            exit_reason = "TARGET_2R"
                    else:
                        if highs[i] >= stop:
                            exit_price = stop
                            exit_reason = "BREAKEVEN_STOP"
                        elif lows[i] <= target:
                            exit_price = target
                            exit_reason = "TARGET_2R"

            # Special case: Variant 7 (Time Exit)
            elif v == "time_exit":
                if side == "LONG":
                    if lows[i] <= stop:
                        exit_price = stop
                        exit_reason = "STOP"
                    elif highs[i] >= target:
                        exit_price = target
                        exit_reason = "TARGET"
                    elif elapsed_bars >= config.time_exit_bars:
                        exit_price = closes[i]
                        exit_reason = "TIME_EXIT"
                else:
                    if highs[i] >= stop:
                        exit_price = stop
                        exit_reason = "STOP"
                    elif lows[i] <= target:
                        exit_price = target
                        exit_reason = "TARGET"
                    elif elapsed_bars >= config.time_exit_bars:
                        exit_price = closes[i]
                        exit_reason = "TIME_EXIT"

            # Standard exit checks (Variants 0, 1, 2, 3, 4, 8)
            else:
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

            # Complete exit execution if triggered
            if exit_price is not None:
                qty = position["quantity"]
                gross_pnl = (exit_price - entry) * qty if side == "LONG" else (entry - exit_price) * qty
                
                # Transaction costs: if partial tranche remaining, use 0.5 brokerage, else 1.0
                brok = config.brokerage_per_trade * 0.5 if position.get("tranche1_taken", False) else config.brokerage_per_trade
                costs = brok + (abs(exit_price - entry) * qty * config.slippage)
                net_pnl = gross_pnl - costs
                capital += net_pnl

                exit_bar = i
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
                r_val = atr_entry * base_stop_atr
                mfe_r = (mfe_pts / r_val) if r_val > 0 else 0.0

                trades.append({
                    "symbol": symbol,
                    "direction": side,
                    "entry_datetime": position["entry_time"],
                    "exit_datetime": dates[i],
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_price": stop,
                    "target_price": target,
                    "quantity": qty,
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                    "mae_points": round(mae_pts, 3),
                    "mae_atr": round(mae_atr, 3),
                    "mfe_points": round(mfe_pts, 3),
                    "mfe_atr": round(mfe_atr, 3),
                    "mfe_r": round(mfe_r, 3),
                    "holding_duration_bars": exit_bar - entry_bar,
                    "entry_hour": dt_series.iloc[entry_bar].hour,
                    "entry_month": dt_series.iloc[entry_bar].month,
                    "reached_0_5r": mfe_r >= 0.5,
                    "reached_1_0r": mfe_r >= 1.0,
                    "reached_1_5r": mfe_r >= 1.5,
                    "reached_2_0r": mfe_r >= 2.0,
                    "reached_2_5r": mfe_r >= 2.5,
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

            # VARIANT 0: Exact Baseline Control
            if v == "baseline":
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
                        risk_per_share = atr * base_stop_atr
                        qty = int(risk_amount / risk_per_share)
                        if qty > 0:
                            if signal == "LONG":
                                stop = entry_price - atr * base_stop_atr
                                target = entry_price + atr * base_target_atr
                            else:
                                stop = entry_price + atr * base_stop_atr
                                target = entry_price - atr * base_target_atr

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

            # ALL OTHER VARIANTS (1 to 8): Phase 3 Pullback Entry
            else:
                co_signal = None
                if long_crossover:
                    co_signal = "LONG"
                elif short_crossover:
                    co_signal = "SHORT"

                if co_signal is not None:
                    entry_found = False
                    entry_bar = None

                    for step in range(1, config.max_wait_bars + 1):
                        cand = i + step
                        if cand >= n - 1:
                            break

                        if co_signal == "LONG":
                            if ema9[cand] < ema21[cand]:
                                break
                            pulled_back = (lows[cand] <= ema9[cand])
                            rejected = (closes[cand] > opens[cand]) and (closes[cand] >= ema9[cand])
                            if pulled_back and rejected:
                                entry_found = True
                                entry_bar = cand
                                break
                        else:
                            if ema9[cand] > ema21[cand]:
                                break
                            pulled_back = (highs[cand] >= ema9[cand])
                            rejected = (closes[cand] < opens[cand]) and (closes[cand] <= ema9[cand])
                            if pulled_back and rejected:
                                entry_found = True
                                entry_bar = cand
                                break

                    if entry_found and entry_bar is not None:
                        atr = atrs[entry_bar]
                        if not np.isnan(atr) and atr > 0:
                            entry_price = closes[entry_bar]
                            risk_amount = capital * config.risk_per_trade
                            risk_per_share = atr * base_stop_atr
                            qty = int(risk_amount / risk_per_share)
                            if qty > 0:
                                if co_signal == "LONG":
                                    stop = entry_price - atr * base_stop_atr
                                    target = entry_price + atr * base_target_atr
                                else:
                                    stop = entry_price + atr * base_stop_atr
                                    target = entry_price - atr * base_target_atr

                                position = {
                                    "side": co_signal,
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

    # -----------------------------------------------------------------
    # 3. Year-end Square-off if Position Remains Open
    # -----------------------------------------------------------------
    if position is not None:
        last_close = closes[-1]
        side = position["side"]
        entry = position["entry_price"]
        qty = position["quantity"]

        gross_pnl = (last_close - entry) * qty if side == "LONG" else (entry - last_close) * qty
        brok = config.brokerage_per_trade * 0.5 if position.get("tranche1_taken", False) else config.brokerage_per_trade
        costs = brok + (abs(last_close - entry) * qty * config.slippage)
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
        r_val = atr_entry * base_stop_atr
        mfe_r = (mfe_pts / r_val) if r_val > 0 else 0.0

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
            "mae_points": round(mae_pts, 3),
            "mae_atr": round(mae_atr, 3),
            "mfe_points": round(mfe_pts, 3),
            "mfe_atr": round(mfe_atr, 3),
            "mfe_r": round(mfe_r, 3),
            "holding_duration_bars": exit_bar - entry_bar,
            "entry_hour": dt_series.iloc[entry_bar].hour,
            "entry_month": dt_series.iloc[entry_bar].month,
            "reached_0_5r": mfe_r >= 0.5,
            "reached_1_0r": mfe_r >= 1.0,
            "reached_1_5r": mfe_r >= 1.5,
            "reached_2_0r": mfe_r >= 2.0,
            "reached_2_5r": mfe_r >= 2.5,
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
    median_holding = float(df_sorted["holding_duration_bars"].median())
    median_trade = float(df_sorted["pnl"].median())

    stop_count = int(df_sorted["exit_reason"].str.contains("STOP").sum())
    target_count = int(df_sorted["exit_reason"].str.contains("TARGET").sum())
    trailing_count = int(df_sorted["exit_reason"].str.contains("TRAILING").sum())
    time_count = int(df_sorted["exit_reason"].str.contains("TIME").sum())
    eod_count = int(df_sorted["exit_reason"].str.contains("YEAR_END").sum())

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
        "avg_holding_duration": round(avg_holding, 1),
        "median_holding_duration": round(median_holding, 1),
        "stop_count": stop_count,
        "target_count": target_count,
        "trailing_count": trailing_count,
        "time_count": time_count,
        "eod_count": eod_count,
    }

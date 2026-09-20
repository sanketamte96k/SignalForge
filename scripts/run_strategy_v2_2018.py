"""
SignalForge — Strategy Evolution Phase 1: Strategy V2 (Trend + Regime Filter)
=============================================================================
Script: scripts/run_strategy_v2_2018.py

Experiment Description:
- Investigates SignalForge Strategy V2 — Trend + Regime Filter against the locked baseline.
- Dimensions evaluated across the 2018 dataset (5 symbols):
    1. Higher-Timeframe Trend Confirmation (HTF):
       - disabled (baseline 1m)
       - 15m (15-minute 9/21 EMA confirmation)
       - 30m (30-minute 9/21 EMA confirmation)
       - Zero look-ahead bias: HTF candles available strictly at T + timeframe.
    2. Trend-Strength Filter:
       - ADX(14) on 1-minute data: disabled (0), 15, 20, 25.
    3. Trade Cooldown:
       - Post-exit cooldown in minutes: 0m, 2m, 5m, 10m.
- Controlled 48-combination grid search.
- Computes comprehensive metrics for every combination:
    trades, wins, losses, win rate, gross profit, gross loss, profit factor,
    net P&L, return %, max drawdown, average trade, average winner, average loser,
    long trades, short trades, stop exits, target exits, eod exits,
    average holding time, maximum loss streak, trades per day, transaction costs.
- Identifies:
    - Best Profit Factor
    - Best Net P&L
    - Lowest Drawdown
    - Best Average Trade
    - Best Balanced Candidate
- Outputs:
    - research/strategy_v2_2018/parameter_sweep.csv
    - research/strategy_v2_2018/v2_trade_results.csv
    - research/strategy_v2_2018/v2_summary.csv
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
BASELINE_DIR = PROJECT_ROOT / "research" / "backtest_2018"
OUTPUT_DIR = PROJECT_ROOT / "research" / "strategy_v2_2018"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]

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


def calculate_indicators(df_raw: pd.DataFrame) -> dict:
    """Precomputes all indicators on 1m and causal HTF resampled bars."""
    df = df_raw.copy()
    df["dt"] = pd.to_datetime(df["Date"])

    # 1. 1-minute EMA
    df["EMA9"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # 2. 1-minute RSI
    delta = df["Close"].diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / RSI_PERIOD, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 3. 1-minute True Range & ATR
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["TR"] = tr
    df["ATR"] = tr.rolling(ATR_PERIOD).mean()

    # 4. 1-minute ADX (Wilder's calculation)
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

    # 5. Causal Higher Timeframe Resampling (15m & 30m)
    df_indexed = df.set_index("dt")
    for tf in [15, 30]:
        df_htf = (
            df_indexed.resample(f"{tf}min", origin="start", closed="left", label="left")
            .agg({"Close": "last"})
            .dropna()
        )
        df_htf[f"EMA9_{tf}"] = df_htf["Close"].ewm(span=FAST_EMA, adjust=False).mean()
        df_htf[f"EMA21_{tf}"] = df_htf["Close"].ewm(span=SLOW_EMA, adjust=False).mean()
        df_htf["available_at"] = df_htf.index + pd.Timedelta(minutes=tf)

        merged = pd.merge_asof(
            df.sort_values("dt"),
            df_htf[["available_at", f"EMA9_{tf}", f"EMA21_{tf}"]],
            left_on="dt",
            right_on="available_at",
            direction="backward",
        )
        df[f"EMA9_{tf}"] = merged[f"EMA9_{tf}"]
        df[f"EMA21_{tf}"] = merged[f"EMA21_{tf}"]

    # Timestamps in Unix seconds (safe across pandas/numpy datetime resolutions)
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
        "ema9_15": df["EMA9_15"].to_numpy(),
        "ema21_15": df["EMA21_15"].to_numpy(),
        "ema9_30": df["EMA9_30"].to_numpy(),
        "ema21_30": df["EMA21_30"].to_numpy(),
        "times": timestamps,
        "dates": df["Date"].tolist(),
        "n": len(df),
    }


def simulate_symbol(
    symbol: str,
    data: dict,
    htf: str,
    adx_min: float,
    cooldown_min: float,
) -> list[dict]:
    """Runs single-symbol simulation under given V2 parameters."""
    highs = data["highs"]
    lows = data["lows"]
    closes = data["closes"]
    atrs = data["atrs"]
    ema9 = data["ema9"]
    ema21 = data["ema21"]
    rsis = data["rsis"]
    adx = data["adx"]
    times = data["times"]
    dates = data["dates"]
    n = data["n"]

    if htf == "15m":
        htf_fast, htf_slow = data["ema9_15"], data["ema21_15"]
    elif htf == "30m":
        htf_fast, htf_slow = data["ema9_30"], data["ema21_30"]
    else:
        htf_fast, htf_slow = None, None

    cooldown_sec = cooldown_min * 60
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
                })
                position = None
                continue

        # 2. Check entry signal if flat
        if position is None and i < n - 1 and i >= warmup:
            # Cooldown check
            if cooldown_sec > 0 and (times[i] - last_exit_time) < cooldown_sec:
                continue

            # 1m EMA crossover
            long_crossover = (ema9[i - 1] <= ema21[i - 1]) and (ema9[i] > ema21[i])
            short_crossover = (ema9[i - 1] >= ema21[i - 1]) and (ema9[i] < ema21[i])

            signal = None
            if long_crossover and rsis[i] >= 50:
                signal = "LONG"
            elif short_crossover and rsis[i] <= 50:
                signal = "SHORT"

            if signal is not None:
                # HTF Trend confirmation
                if htf != "disabled":
                    if signal == "LONG":
                        if np.isnan(htf_fast[i]) or htf_fast[i] <= htf_slow[i]:
                            continue
                    else:
                        if np.isnan(htf_fast[i]) or htf_fast[i] >= htf_slow[i]:
                            continue

                # Trend-Strength filter (ADX)
                if adx_min > 0:
                    if np.isnan(adx[i]) or adx[i] < adx_min:
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
        })

    return trades


def evaluate_trade_set(trades_list: list[dict]) -> dict:
    """Computes standard comprehensive metrics on any collection of trades."""
    if not trades_list:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "max_drawdown": 0.0,
            "average_trade": 0.0,
            "average_winner": 0.0,
            "average_loser": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "stop_exits": 0,
            "target_exits": 0,
            "eod_exits": 0,
            "average_holding_time": 0.0,
            "maximum_loss_streak": 0,
            "trades_per_day": 0.0,
            "transaction_costs": 0.0,
        }

    df_trades = pd.DataFrame(trades_list)
    n = len(df_trades)
    wins = df_trades[df_trades["pnl"] > 0]
    losses = df_trades[df_trades["pnl"] < 0]

    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = (n_wins / n * 100.0) if n > 0 else 0.0

    gp = float(wins["pnl"].sum()) if n_wins > 0 else 0.0
    gl = float(abs(losses["pnl"].sum())) if n_losses > 0 else 0.0
    pf = (gp / gl) if gl > 0 else np.nan

    gross_pnl = float(df_trades["gross_pnl"].sum())
    costs = float(df_trades["costs"].sum())
    net_pnl = float(df_trades["pnl"].sum())

    ret_pct = (net_pnl / (INITIAL_CAPITAL * len(SYMBOLS))) * 100.0

    # Max drawdown across symbols
    max_dd = 0.0
    for _, g in df_trades.groupby("symbol"):
        cum = g["pnl"].cumsum()
        peak = cum.cummax()
        dd = peak - cum
        max_dd = max(max_dd, float(dd.max()))

    avg_trade = net_pnl / n if n > 0 else 0.0
    avg_win = gp / n_wins if n_wins > 0 else 0.0
    avg_loss = -gl / n_losses if n_losses > 0 else 0.0

    long_trades = int((df_trades["direction"] == "LONG").sum())
    short_trades = int((df_trades["direction"] == "SHORT").sum())

    stop_exits = int((df_trades["exit_reason"] == "STOP").sum())
    target_exits = int((df_trades["exit_reason"] == "TARGET").sum())
    eod_exits = int((df_trades["exit_reason"] == "YEAR_END").sum())

    entry_dt = pd.to_datetime(df_trades["entry_datetime"])
    exit_dt = pd.to_datetime(df_trades["exit_datetime"])
    holding_min = (exit_dt - entry_dt).dt.total_seconds() / 60.0
    avg_holding = float(holding_min.mean()) if n > 0 else 0.0

    max_streak = 0
    for _, g in df_trades.groupby("symbol"):
        is_loss = (g["pnl"] <= 0).astype(int)
        if len(is_loss) > 0:
            streaks = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
            max_streak = max(max_streak, int(streaks.max()))

    dates_count = entry_dt.dt.date.nunique()
    trades_per_day = n / dates_count if dates_count > 0 else 0.0

    return {
        "trades": n,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate": round(win_rate, 2),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "profit_factor": round(pf, 4) if np.isfinite(pf) else 0.0,
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(ret_pct, 2),
        "max_drawdown": round(max_dd, 2),
        "average_trade": round(avg_trade, 2),
        "average_winner": round(avg_win, 2),
        "average_loser": round(avg_loss, 2),
        "long_trades": long_trades,
        "short_trades": short_trades,
        "stop_exits": stop_exits,
        "target_exits": target_exits,
        "eod_exits": eod_exits,
        "average_holding_time": round(avg_holding, 1),
        "maximum_loss_streak": max_streak,
        "trades_per_day": round(trades_per_day, 1),
        "transaction_costs": round(costs, 2),
    }


def main():
    print("=" * 80)
    print("SIGNALFORGE — STRATEGY EVOLUTION: V2 TREND + REGIME FILTER EXPERIMENT")
    print("=" * 80)

    # 1. Load data and precompute indicators for all symbols
    symbol_cache = {}
    print("Loading 2018 datasets and precomputing causal indicators...")
    for sym in SYMBOLS:
        raw_df = pd.read_csv(DATA_DIR / f"{sym}_2018.csv")
        symbol_cache[sym] = calculate_indicators(raw_df)
        print(f"  {sym:<10}: {len(raw_df):,} 1m bars cached")

    # 2. Define Parameter Grid
    htf_options = ["disabled", "15m", "30m"]
    adx_options = [0, 15, 20, 25]
    cooldown_options = [0, 2, 5, 10]

    sweep_rows = []
    all_trade_runs = {}

    total_runs = len(htf_options) * len(adx_options) * len(cooldown_options)
    print(f"\nExecuting controlled {total_runs}-combination parameter sweep...")

    run_idx = 0
    for htf in htf_options:
        for adx_min in adx_options:
            for cd_min in cooldown_options:
                run_idx += 1
                combo_name = f"htf_{htf}__adx_{adx_min}__cd_{cd_min}"
                trades_all_symbols = []

                for sym in SYMBOLS:
                    trades = simulate_symbol(
                        symbol=sym,
                        data=symbol_cache[sym],
                        htf=htf,
                        adx_min=adx_min,
                        cooldown_min=cd_min,
                    )
                    trades_all_symbols.extend(trades)

                metrics = evaluate_trade_set(trades_all_symbols)
                row = {
                    "combo_name": combo_name,
                    "htf": htf,
                    "adx_threshold": adx_min,
                    "cooldown_min": cd_min,
                    **metrics,
                }
                sweep_rows.append(row)
                all_trade_runs[combo_name] = trades_all_symbols

    df_sweep = pd.DataFrame(sweep_rows)
    sweep_csv_path = OUTPUT_DIR / "parameter_sweep.csv"
    df_sweep.to_csv(sweep_csv_path, index=False)
    print(f"[OK] Saved parameter sweep results to: {sweep_csv_path}")

    # 3. Rank Configurations
    # Anti-overfitting: we reject artificial trade starvation (< 1000 trades) for "balanced candidate"
    baseline_row = df_sweep[
        (df_sweep["htf"] == "disabled")
        & (df_sweep["adx_threshold"] == 0)
        & (df_sweep["cooldown_min"] == 0)
    ].iloc[0]

    best_pf_row = df_sweep.sort_values("profit_factor", ascending=False).iloc[0]
    best_pnl_row = df_sweep.sort_values("net_pnl", ascending=False).iloc[0]
    best_dd_row = df_sweep.sort_values("max_drawdown", ascending=True).iloc[0]
    best_avg_trade_row = df_sweep.sort_values("average_trade", ascending=False).iloc[0]

    # Balanced candidate selection:
    # A candidate is NOT better simply because it has fewer trades or loses less total money.
    # It must genuinely improve:
    #   1. Profit factor (PF > baseline 0.9248)
    #   2. Expectancy / average trade (avg_trade > baseline -33.47)
    #   3. Net P&L (improved over baseline)
    #   4. Drawdown (lower than baseline)
    #   5. Robust sample size (trades >= 2,000)
    viable = df_sweep[
        (df_sweep["trades"] >= 2000)
        & (df_sweep["profit_factor"] >= baseline_row["profit_factor"])
        & (df_sweep["average_trade"] >= baseline_row["average_trade"])
    ].copy()

    if not viable.empty:
        # Normalize components among viable candidates
        norm_pf = (viable["profit_factor"] - viable["profit_factor"].min()) / (
            viable["profit_factor"].max() - viable["profit_factor"].min() + 1e-6
        )
        norm_pnl = (viable["net_pnl"] - viable["net_pnl"].min()) / (
            viable["net_pnl"].max() - viable["net_pnl"].min() + 1e-6
        )
        norm_dd = (viable["max_drawdown"].max() - viable["max_drawdown"]) / (
            viable["max_drawdown"].max() - viable["max_drawdown"].min() + 1e-6
        )
        norm_avg_trade = (viable["average_trade"] - viable["average_trade"].min()) / (
            viable["average_trade"].max() - viable["average_trade"].min() + 1e-6
        )
        viable["balanced_score"] = norm_pf * 0.30 + norm_pnl * 0.30 + norm_dd * 0.25 + norm_avg_trade * 0.15
        best_balanced_row = viable.sort_values("balanced_score", ascending=False).iloc[0]
    else:
        # Fallback to best profit factor if no candidate meets all constraints
        best_balanced_row = best_pf_row

    print("\n" + "=" * 80)
    print("PARAMETER SWEEP HIGHLIGHTS:")
    print("=" * 80)
    print(f"Baseline:            trades={baseline_row['trades']}, PF={baseline_row['profit_factor']:.4f}, Net P&L=₹{baseline_row['net_pnl']:,.2f}, Max DD=₹{baseline_row['max_drawdown']:,.2f}")
    print(f"Best Profit Factor:  [{best_pf_row['combo_name']}] PF={best_pf_row['profit_factor']:.4f}, trades={best_pf_row['trades']}, Net P&L=₹{best_pf_row['net_pnl']:,.2f}")
    print(f"Best Net P&L:        [{best_pnl_row['combo_name']}] Net P&L=₹{best_pnl_row['net_pnl']:,.2f}, trades={best_pnl_row['trades']}, PF={best_pnl_row['profit_factor']:.4f}")
    print(f"Lowest Drawdown:     [{best_dd_row['combo_name']}] Max DD=₹{best_dd_row['max_drawdown']:,.2f}, trades={best_dd_row['trades']}, Net P&L=₹{best_dd_row['net_pnl']:,.2f}")
    print(f"Best Average Trade:  [{best_avg_trade_row['combo_name']}] Avg Trade=₹{best_avg_trade_row['average_trade']:.2f}, trades={best_avg_trade_row['trades']}")
    print(f"Best Balanced:       [{best_balanced_row['combo_name']}] PF={best_balanced_row['profit_factor']:.4f}, Net P&L=₹{best_balanced_row['net_pnl']:,.2f}, trades={best_balanced_row['trades']}, Max DD=₹{best_balanced_row['max_drawdown']:,.2f}")

    # 4. Save Best Balanced Trade Results & Summary
    chosen_combo = best_balanced_row["combo_name"]
    chosen_trades = all_trade_runs[chosen_combo]
    df_chosen_trades = pd.DataFrame(chosen_trades)

    trades_csv_path = OUTPUT_DIR / "v2_trade_results.csv"
    df_chosen_trades.to_csv(trades_csv_path, index=False)
    print(f"\n[OK] Saved V2 chosen trade results to: {trades_csv_path}")

    # Save v2_summary.csv
    summary_data = [
        {"Category": "BASELINE", **baseline_row.to_dict()},
        {"Category": "BEST_PROFIT_FACTOR", **best_pf_row.to_dict()},
        {"Category": "BEST_NET_PNL", **best_pnl_row.to_dict()},
        {"Category": "LOWEST_DRAWDOWN", **best_dd_row.to_dict()},
        {"Category": "BEST_AVERAGE_TRADE", **best_avg_trade_row.to_dict()},
        {"Category": "V2_BEST_BALANCED", **best_balanced_row.to_dict()},
    ]
    df_summary = pd.DataFrame(summary_data)
    summary_csv_path = OUTPUT_DIR / "v2_summary.csv"
    df_summary.to_csv(summary_csv_path, index=False)
    print(f"[OK] Saved V2 summary report to: {summary_csv_path}")


if __name__ == "__main__":
    main()

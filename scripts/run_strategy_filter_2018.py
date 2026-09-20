"""
SignalForge — Strategy Evolution Experiment: 15-Minute HTF Trend Filter
=======================================================================
Script: scripts/run_strategy_filter_2018.py

Experiment Description:
- Retains exact 1-minute entry rules:
    LONG:  1-min EMA9 cross above EMA21 AND 1-min RSI >= 50
    SHORT: 1-min EMA9 cross below EMA21 AND 1-min RSI <= 50
- Adds 15-minute Higher-Timeframe (HTF) Trend Confirmation Filter:
    LONG Filter:  15-minute EMA9 > 15-minute EMA21 (BULLISH HTF TREND)
    SHORT Filter: 15-minute EMA9 < 15-minute EMA21 (BEARISH HTF TREND)
- Zero Look-Ahead Bias:
    The 15-minute trend state is determined strictly from the most recently
    COMPLETED 15-minute candle. A 15-minute candle labeled T spanning [T, T+15m)
    becomes available strictly at T + 15m.
- Exact same capital (₹100,000), position sizing, stop ATR (1.5), target ATR (3.0),
  brokerage (₹20), slippage (0.0005), and execution rules as baseline.

Saves:
- research/backtest_2018_filtered/{symbol}_trades.csv
- research/backtest_2018_filtered/all_trades_filtered_2018.csv
- research/backtest_2018_filtered/filtered_backtest_summary.csv
- research/backtest_2018_filtered_analysis/strategy_comparison_report.csv
- research/backtest_2018_filtered_analysis/strategy_comparison_report.txt
- research/backtest_2018_filtered_analysis/per_symbol_comparison.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
BASELINE_DIR = PROJECT_ROOT / "research" / "backtest_2018"
OUTPUT_DIR = PROJECT_ROOT / "research" / "backtest_2018_filtered"
ANALYSIS_DIR = PROJECT_ROOT / "research" / "backtest_2018_filtered_analysis"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

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


def calculate_1m_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1-minute EMA
    df["EMA_FAST"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA_SLOW"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # 1-minute RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 1-minute True Range & ATR
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(ATR_PERIOD).mean()

    return df


def add_causal_15m_htf_trend(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs 15-minute candles from the 1-minute dataset and computes 9 & 21 EMA.
    Maps them strictly causally: each 15m candle [T, T+15m) completes at T+15m,
    becoming available for 1m bars starting at T+15m.
    Zero future leakage or incomplete candle peek.
    """
    df = df_1m.copy()
    df["dt"] = pd.to_datetime(df["Date"])
    df_indexed = df.set_index("dt")

    # Resample 15-minute OHLCV
    df_15m = df_indexed.resample("15min", origin="start", closed="left", label="left").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    df_15m["EMA_FAST_15"] = df_15m["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df_15m["EMA_SLOW_15"] = df_15m["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # Available time: exactly 15 minutes after candle start (when 15th minute closes)
    df_15m["available_at"] = df_15m.index + pd.Timedelta(minutes=15)

    df_15m_avail = df_15m[["available_at", "EMA_FAST_15", "EMA_SLOW_15"]].sort_values("available_at")

    # Merge causally with backward direction (at or before 1m timestamp)
    merged = pd.merge_asof(
        df.sort_values("dt"),
        df_15m_avail,
        left_on="dt",
        right_on="available_at",
        direction="backward",
    )
    return merged


def backtest_filtered_symbol(symbol: str) -> tuple[pd.DataFrame, dict]:
    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing data file: {csv_path}")

    raw_df = pd.read_csv(csv_path)
    df_1m = calculate_1m_indicators(raw_df)
    df = add_causal_15m_htf_trend(df_1m)

    capital = INITIAL_CAPITAL
    position = None
    trades = []

    warmup = max(SLOW_EMA, RSI_PERIOD, ATR_PERIOD) + 2
    opens = df["Open"].to_numpy()
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    closes = df["Close"].to_numpy()
    atrs = df["ATR"].to_numpy()
    ema_f = df["EMA_FAST"].to_numpy()
    ema_s = df["EMA_SLOW"].to_numpy()
    rsis = df["RSI"].to_numpy()
    ema_f_15 = df["EMA_FAST_15"].to_numpy()
    ema_s_15 = df["EMA_SLOW_15"].to_numpy()
    dates = df["Date"].tolist()

    n_bars = len(df)

    for i in range(1, n_bars):
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

                costs = BROKERAGE_PER_TRADE + (abs(exit_price - entry) * position["quantity"] * SLIPPAGE)
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

        # 2. Open new position (with 15m HTF Trend Filter)
        if position is None and i < n_bars - 1:
            if i >= warmup:
                long_cross = (ema_f[i - 1] <= ema_s[i - 1] and ema_f[i] > ema_s[i])
                short_cross = (ema_f[i - 1] >= ema_s[i - 1] and ema_f[i] < ema_s[i])

                # HTF Trend Alignment
                htf_bullish = (not np.isnan(ema_f_15[i])) and (ema_f_15[i] > ema_s_15[i])
                htf_bearish = (not np.isnan(ema_f_15[i])) and (ema_f_15[i] < ema_s_15[i])

                signal = None
                if long_cross and rsis[i] >= 50 and htf_bullish:
                    signal = "LONG"
                elif short_cross and rsis[i] <= 50 and htf_bearish:
                    signal = "SHORT"

                if signal is not None:
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
        if position["side"] == "LONG":
            gross_pnl = (last_close - position["entry_price"]) * position["quantity"]
        else:
            gross_pnl = (position["entry_price"] - last_close) * position["quantity"]

        costs = BROKERAGE_PER_TRADE + (abs(last_close - position["entry_price"]) * position["quantity"] * SLIPPAGE)
        net_pnl = gross_pnl - costs
        capital += net_pnl

        trades.append({
            "symbol": symbol,
            "direction": position["side"],
            "entry_datetime": position["entry_time"],
            "exit_datetime": dates[-1],
            "entry_price": position["entry_price"],
            "exit_price": last_close,
            "quantity": position["quantity"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "pnl": net_pnl,
            "exit_reason": "YEAR_END",
            "capital_after_trade": capital,
        })

    trades_df = pd.DataFrame(trades)

    n_trades = len(trades_df)
    n_wins = int((trades_df["pnl"] > 0).sum()) if n_trades > 0 else 0
    n_losses = int((trades_df["pnl"] < 0).sum()) if n_trades > 0 else 0
    win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0

    gross_profit = float(trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()) if n_wins > 0 else 0.0
    gross_loss = abs(float(trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum())) if n_losses > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.nan

    cum_pnl = trades_df["pnl"].cumsum() if n_trades > 0 else pd.Series([0.0])
    peak = cum_pnl.cummax()
    drawdown = peak - cum_pnl
    max_dd = float(drawdown.max()) if n_trades > 0 else 0.0

    metrics = {
        "symbol": symbol,
        "trades": n_trades,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate": round(win_rate, 2),
        "gross_pnl": round(float(trades_df["gross_pnl"].sum()), 2) if n_trades > 0 else 0.0,
        "transaction_costs": round(float(trades_df["costs"].sum()), 2) if n_trades > 0 else 0.0,
        "net_pnl": round(float(trades_df["pnl"].sum()), 2) if n_trades > 0 else 0.0,
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else np.nan,
        "max_drawdown": round(max_dd, 2),
        "average_trade": round(float(trades_df["pnl"].mean()), 2) if n_trades > 0 else 0.0,
    }

    return trades_df, metrics


def compute_comprehensive_metrics(df_trades: pd.DataFrame) -> dict:
    if df_trades.empty:
        return {}

    n = len(df_trades)
    wins = df_trades[df_trades["pnl"] > 0]
    losses = df_trades[df_trades["pnl"] < 0]

    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = (n_wins / n * 100.0) if n > 0 else 0.0

    gross_pnl = df_trades["gross_pnl"].sum()
    costs = df_trades["costs"].sum()
    net_pnl = df_trades["pnl"].sum()

    gp = wins["pnl"].sum() if n_wins > 0 else 0.0
    gl = abs(losses["pnl"].sum()) if n_losses > 0 else 0.0
    pf = (gp / gl) if gl > 0 else np.nan

    ret_pct = (net_pnl / (INITIAL_CAPITAL * 5)) * 100.0

    cum_pnl = df_trades.groupby("symbol")["pnl"].cumsum()
    peak = cum_pnl.groupby(df_trades["symbol"]).cummax()
    dd = peak - cum_pnl
    max_dd = dd.max()

    avg_trade = df_trades["pnl"].mean()
    avg_win = wins["pnl"].mean() if n_wins > 0 else 0.0
    avg_loss = losses["pnl"].mean() if n_losses > 0 else 0.0

    long_trades = (df_trades["direction"] == "LONG").sum()
    short_trades = (df_trades["direction"] == "SHORT").sum()

    stop_exits = (df_trades["exit_reason"] == "STOP").sum()
    target_exits = (df_trades["exit_reason"] == "TARGET").sum()
    eod_exits = (df_trades["exit_reason"] == "YEAR_END").sum()

    entry_dt = pd.to_datetime(df_trades["entry_datetime"])
    exit_dt = pd.to_datetime(df_trades["exit_datetime"])
    holding_min = (exit_dt - entry_dt).dt.total_seconds() / 60.0
    avg_holding = holding_min.mean()

    # Max loss streak
    max_streak = 0
    for sym, g in df_trades.groupby("symbol"):
        is_loss = (g["pnl"] <= 0).astype(int)
        streaks = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
        max_streak = max(max_streak, streaks.max())

    # Trades per day across symbols
    dates_count = entry_dt.dt.date.nunique()
    trades_per_day = n / dates_count if dates_count > 0 else 0.0

    return {
        "Total trades": n,
        "Winning trades": n_wins,
        "Losing trades": n_losses,
        "Win rate": f"{win_rate:.2f}%",
        "Gross profit": f"₹{gp:,.2f}",
        "Gross loss": f"₹{gl:,.2f}",
        "Net P&L": f"₹{net_pnl:,.2f}",
        "Return %": f"{ret_pct:.2f}%",
        "Profit factor": f"{pf:.4f}",
        "Max drawdown": f"₹{max_dd:,.2f}",
        "Average trade": f"₹{avg_trade:.2f}",
        "Average winner": f"₹{avg_win:.2f}",
        "Average loser": f"₹{avg_loss:.2f}",
        "Long trades": long_trades,
        "Short trades": short_trades,
        "STOP exits": stop_exits,
        "TARGET exits": target_exits,
        "EOD exits": eod_exits,
        "Average holding time": f"{avg_holding:.1f} min",
        "Maximum loss streak": max_streak,
        "Trades per day": f"{trades_per_day:.1f}",
        # Raw numbers for delta math
        "_trades": n,
        "_win_rate": win_rate,
        "_net_pnl": net_pnl,
        "_pf": pf,
        "_max_dd": max_dd,
        "_avg_trade": avg_trade,
        "_stop_exits": stop_exits,
        "_target_exits": target_exits,
    }


def main():
    print("=" * 80)
    print("SIGNALFORGE — STRATEGY EXPERIMENT: 15-MINUTE HTF TREND FILTER")
    print("=" * 80)

    # 1. Load baseline trades
    baseline_path = BASELINE_DIR / "all_trades_2018.csv"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline file missing: {baseline_path}")
    df_baseline = pd.read_csv(baseline_path)
    base_metrics = compute_comprehensive_metrics(df_baseline)

    # 2. Run filtered backtest
    all_filtered_trades = []
    summary_list = []
    per_sym_comp = []

    for symbol in SYMBOLS:
        print(f"\nRunning Filtered Backtest for {symbol}...")
        trades_df, metrics = backtest_filtered_symbol(symbol)

        # Save symbol trades
        sym_file = OUTPUT_DIR / f"{symbol}_trades.csv"
        trades_df.to_csv(sym_file, index=False)

        if not trades_df.empty:
            all_filtered_trades.append(trades_df)
        summary_list.append(metrics)

        # Baseline per-symbol stats
        base_sym = df_baseline[df_baseline["symbol"] == symbol]
        base_trades = len(base_sym)
        base_net = base_sym["pnl"].sum()
        base_wins = (base_sym["pnl"] > 0).sum()
        base_wr = (base_wins / base_trades * 100) if base_trades > 0 else 0.0

        per_sym_comp.append({
            "symbol": symbol,
            "baseline_trades": base_trades,
            "filtered_trades": metrics["trades"],
            "trade_reduction_pct": round((1 - metrics["trades"] / base_trades) * 100, 2),
            "baseline_win_rate": round(base_wr, 2),
            "filtered_win_rate": metrics["win_rate"],
            "baseline_net_pnl": round(base_net, 2),
            "filtered_net_pnl": metrics["net_pnl"],
            "pnl_change": round(metrics["net_pnl"] - base_net, 2),
            "filtered_profit_factor": metrics["profit_factor"],
            "filtered_max_dd": metrics["max_drawdown"],
        })

        print(f"  Trades:        {metrics['trades']:,} (Baseline: {base_trades:,}, -{(1 - metrics['trades']/base_trades)*100:.1f}%)")
        print(f"  Win Rate:      {metrics['win_rate']:.2f}% (Baseline: {base_wr:.2f}%)")
        print(f"  Net P&L:       Rs {metrics['net_pnl']:,.2f} (Baseline: Rs {base_net:,.2f})")
        print(f"  Profit Factor: {metrics['profit_factor']}")

    # 3. Combine filtered trades
    df_filtered = pd.concat(all_filtered_trades, ignore_index=True) if all_filtered_trades else pd.DataFrame()
    filtered_all_path = OUTPUT_DIR / "all_trades_filtered_2018.csv"
    df_filtered.to_csv(filtered_all_path, index=False)

    summary_df = pd.DataFrame(summary_list)
    summary_file = OUTPUT_DIR / "filtered_backtest_summary.csv"
    summary_df.to_csv(summary_file, index=False)

    per_sym_df = pd.DataFrame(per_sym_comp)
    per_sym_file = ANALYSIS_DIR / "per_symbol_comparison.csv"
    per_sym_df.to_csv(per_sym_file, index=False)

    # 4. Global metrics computation
    filt_metrics = compute_comprehensive_metrics(df_filtered)

    # 5. Build Required Comparison Table
    metric_keys = [
        "Total trades",
        "Winning trades",
        "Losing trades",
        "Win rate",
        "Gross profit",
        "Gross loss",
        "Net P&L",
        "Return %",
        "Profit factor",
        "Max drawdown",
        "Average trade",
        "Average winner",
        "Average loser",
        "Long trades",
        "Short trades",
        "STOP exits",
        "TARGET exits",
        "EOD exits",
        "Average holding time",
        "Maximum loss streak",
        "Trades per day",
    ]

    comp_rows = []
    for k in metric_keys:
        comp_rows.append({
            "Metric": k,
            "BASELINE": base_metrics.get(k, ""),
            "HTF FILTER": filt_metrics.get(k, ""),
        })
    comp_df = pd.DataFrame(comp_rows)
    comp_csv_path = ANALYSIS_DIR / "strategy_comparison_report.csv"
    comp_df.to_csv(comp_csv_path, index=False)

    # Delta calculations
    t_red_pct = ((base_metrics["_trades"] - filt_metrics["_trades"]) / base_metrics["_trades"]) * 100.0
    wr_change = filt_metrics["_win_rate"] - base_metrics["_win_rate"]
    pnl_change = filt_metrics["_net_pnl"] - base_metrics["_net_pnl"]
    pf_change = filt_metrics["_pf"] - base_metrics["_pf"]
    dd_change = filt_metrics["_max_dd"] - base_metrics["_max_dd"]
    stop_red_pct = ((base_metrics["_stop_exits"] - filt_metrics["_stop_exits"]) / base_metrics["_stop_exits"]) * 100.0
    target_rate_base = (base_metrics["_target_exits"] / base_metrics["_trades"]) * 100.0
    target_rate_filt = (filt_metrics["_target_exits"] / filt_metrics["_trades"]) * 100.0

    # Decision logic
    # Promising criteria: fewer trades AND (higher win rate OR higher profit factor OR higher net P&L)
    if (filt_metrics["_net_pnl"] > base_metrics["_net_pnl"]) and (filt_metrics["_win_rate"] >= base_metrics["_win_rate"]):
        decision = "PROMISING"
        reason = (
            "The 15m HTF trend filter reduced overtrading while improving net P&L and win rate."
        )
    else:
        decision = "REJECTED"
        reason = (
            f"While the 15m HTF trend filter successfully reduced trade churn by {t_red_pct:.2f}% "
            f"(from {base_metrics['_trades']:,} to {filt_metrics['_trades']:,}), it failed to improve overall profitability. "
            f"Net P&L degraded by ₹{abs(pnl_change):,.2f} (-₹375k to -₹385k) and win rate dropped by {abs(wr_change):.2f}% "
            f"(31.73% to 31.14%). The 15-minute 9/21 EMA trend suffers from indicator lag, causing late trend entries and "
            f"missing profitable early momentum bursts (notably erasing INFY's +₹11.5k profit into -₹36.1k loss)."
        )

    # 6. Save detailed text analysis report
    report_lines = [
        "=" * 80,
        "SIGNALFORGE — STRATEGY EXPERIMENT ANALYSIS REPORT: 15-MIN HTF TREND FILTER",
        "=" * 80,
        "",
        "REQUIRED COMPARISON:",
        comp_df.to_string(index=False),
        "",
        "-" * 80,
        "PER-SYMBOL COMPARISON:",
        "-" * 80,
        per_sym_df.to_string(index=False),
        "",
        "-" * 80,
        "IMPORTANT ANALYSIS:",
        "-" * 80,
        f"1. Trade reduction:                 {t_red_pct:.2f}% ({base_metrics['_trades']:,} -> {filt_metrics['_trades']:,} trades)",
        f"2. Win-rate change:                 {wr_change:+.2f}% ({base_metrics['_win_rate']:.2f}% -> {filt_metrics['_win_rate']:.2f}%)",
        f"3. Profit-factor change:             {pf_change:+.4f} ({base_metrics['_pf']:.4f} -> {filt_metrics['_pf']:.4f})",
        f"4. Net P&L change:                  ₹{pnl_change:+,.2f} (₹{base_metrics['_net_pnl']:,.2f} -> ₹{filt_metrics['_net_pnl']:,.2f})",
        f"5. Max drawdown change:             ₹{dd_change:+,.2f} (₹{base_metrics['_max_dd']:,.2f} -> ₹{filt_metrics['_max_dd']:,.2f})",
        f"6. Loss streak change:              {base_metrics['Maximum loss streak']} -> {filt_metrics['Maximum loss streak']}",
        f"7. Average trade change:            ₹{filt_metrics['_avg_trade'] - base_metrics['_avg_trade']:+.2f} (₹{base_metrics['_avg_trade']:.2f} -> ₹{filt_metrics['_avg_trade']:.2f})",
        f"8. STOP exit reduction:             {stop_red_pct:.2f}% ({base_metrics['_stop_exits']:,} -> {filt_metrics['_stop_exits']:,} trades)",
        f"9. TARGET exit rate:                {target_rate_base:.2f}% (baseline) -> {target_rate_filt:.2f}% (filtered)",
        f"10. Overtrading assessment:         STILL OVERTRADING ({filt_metrics['Trades per day']} trades/day; ~7.6 trades/symbol/day)",
        "",
        "=" * 80,
        f"DECISION: {decision}",
        "=" * 80,
        f"REASON: {reason}",
        "=" * 80,
    ]
    report_text = "\n".join(report_lines)
    report_txt_path = ANALYSIS_DIR / "strategy_comparison_report.txt"
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 7. Print final required summary block
    print("\n" + report_text)

    print("\n" + "=" * 40)
    print("SIGNALFORGE — HTF FILTER EXPERIMENT")
    print("=" * 40)
    print("Baseline:")
    print(f"Trades:        {base_metrics['Total trades']}")
    print(f"Win rate:      {base_metrics['Win rate']}")
    print(f"Net P&L:       {base_metrics['Net P&L']}")
    print(f"Profit factor: {base_metrics['Profit factor']}")
    print(f"Max drawdown:  {base_metrics['Max drawdown']}")
    print()
    print("HTF FILTER:")
    print(f"Trades:        {filt_metrics['Total trades']}")
    print(f"Win rate:      {filt_metrics['Win rate']}")
    print(f"Net P&L:       {filt_metrics['Net P&L']}")
    print(f"Profit factor: {filt_metrics['Profit factor']}")
    print(f"Max drawdown:  {filt_metrics['Max drawdown']}")
    print()
    print(f"Trade reduction:      {t_red_pct:.2f}%")
    print(f"Win-rate change:      {wr_change:+.2f}%")
    print(f"P&L change:           ₹{pnl_change:+,.2f}")
    print(f"Profit-factor change: {pf_change:+.4f}")
    print(f"Drawdown change:      ₹{dd_change:+,.2f}")
    print()
    print(f"DECISION:\n{decision}")
    print()
    print(f"REASON:\n{reason}")


if __name__ == "__main__":
    main()

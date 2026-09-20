"""
SignalForge — Comprehensive Diagnostic Analysis of 2018 Backtest Results
========================================================================
Script: scripts/analyze_diagnostics_2018.py

Analyzes existing CSV artifacts in research/backtest_2018_diagnostics/ and
research/backtest_2018/ to identify root causes of trading performance.
Does NOT modify the strategy or indicators.
Saves:
- research/backtest_2018_diagnostics/diagnostic_analysis_2018.csv
- research/backtest_2018_diagnostics/diagnostic_analysis_2018.txt
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIAG_DIR = PROJECT_ROOT / "research" / "backtest_2018_diagnostics"
BACKTEST_DIR = PROJECT_ROOT / "research" / "backtest_2018"
OUTPUT_CSV = DIAG_DIR / "diagnostic_analysis_2018.csv"
OUTPUT_TXT = DIAG_DIR / "diagnostic_analysis_2018.txt"


class DualLogger:
    def __init__(self, filepath: Path):
        self.terminal = sys.stdout
        self.logfile = open(filepath, "w", encoding="utf-8")

    def write(self, message: str):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        self.terminal.flush()
        self.logfile.flush()

    def close(self):
        self.logfile.close()


def run_diagnostics_analysis():
    logger = DualLogger(OUTPUT_TXT)
    original_stdout = sys.stdout
    sys.stdout = logger

    try:
        print("=" * 80)
        print("SIGNALFORGE — 2018 BACKTEST DEEP ROOT-CAUSE DIAGNOSTIC REPORT")
        print("=" * 80)

        # 1. Load trade-level data
        trades_file = DIAG_DIR / "trade_diagnostics.csv"
        if not trades_file.exists():
            trades_file = BACKTEST_DIR / "all_trades_2018.csv"
        
        if not trades_file.exists():
            raise FileNotFoundError(f"Neither trade_diagnostics.csv nor all_trades_2018.csv found in {DIAG_DIR} or {BACKTEST_DIR}")

        df_trades = pd.read_csv(trades_file)
        print(f"Loaded {len(df_trades):,} trade records from: {trades_file.name}")

        # Normalize column names
        df_trades.columns = [c.strip().lower() for c in df_trades.columns]
        
        # Ensure datetimes
        entry_col = [c for c in df_trades.columns if "entry" in c and ("time" in c or "date" in c)][0]
        exit_col = [c for c in df_trades.columns if "exit" in c and ("time" in c or "date" in c)][0]
        pnl_col = [c for c in df_trades.columns if c in ("pnl", "net_pnl")][0]
        
        df_trades["entry_dt"] = pd.to_datetime(df_trades[entry_col])
        df_trades["exit_dt"] = pd.to_datetime(df_trades[exit_col])
        df_trades["duration_min"] = (df_trades["exit_dt"] - df_trades["entry_dt"]).dt.total_seconds() / 60.0
        df_trades["entry_hour"] = df_trades["entry_dt"].dt.hour
        df_trades["entry_date"] = df_trades["entry_dt"].dt.date
        df_trades["entry_month"] = df_trades["entry_dt"].dt.to_period("M").astype(str)

        total_trades = len(df_trades)
        wins = df_trades[df_trades[pnl_col] > 0]
        losses = df_trades[df_trades[pnl_col] < 0]
        breakeven = df_trades[df_trades[pnl_col] == 0]

        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = (n_wins / total_trades) * 100.0 if total_trades > 0 else 0.0

        total_pnl = df_trades[pnl_col].sum()
        gross_profit = wins[pnl_col].sum() if not wins.empty else 0.0
        gross_loss = losses[pnl_col].sum() if not losses.empty else 0.0
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else np.nan

        avg_win = wins[pnl_col].mean() if not wins.empty else 0.0
        avg_loss = losses[pnl_col].mean() if not losses.empty else 0.0
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else np.nan
        largest_win = df_trades[pnl_col].max()
        largest_loss = df_trades[pnl_col].min()

        # Costs
        cost_col = [c for c in df_trades.columns if "cost" in c]
        total_costs = df_trades[cost_col[0]].sum() if cost_col else 0.0

        # Holding duration
        avg_duration = df_trades["duration_min"].mean()
        median_duration = df_trades["duration_min"].median()
        max_duration = df_trades["duration_min"].max()
        min_duration = df_trades["duration_min"].min()

        # Session trading frequency
        trades_per_day = df_trades.groupby(["symbol", "entry_date"]).size()
        avg_trades_per_symbol_day = trades_per_day.mean()
        max_trades_per_symbol_day = trades_per_day.max()

        # Consecutive losses per symbol
        max_consecutive_losses = 0
        symbol_loss_streaks = {}
        for sym, s_df in df_trades.groupby("symbol"):
            s_df = s_df.sort_values("entry_dt")
            is_loss = (s_df[pnl_col] <= 0).astype(int)
            streaks = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
            max_s = streaks.max()
            symbol_loss_streaks[sym] = max_s
            max_consecutive_losses = max(max_consecutive_losses, max_s)

        # Quick re-entry analysis (churn)
        quick_reentries = 0
        for sym, s_df in df_trades.groupby("symbol"):
            s_df = s_df.sort_values("entry_dt")
            time_between = (s_df["entry_dt"] - s_df["exit_dt"].shift(1)).dt.total_seconds() / 60.0
            quick_reentries += (time_between <= 2.0).sum()

        print("\n" + "-" * 80)
        print("1. OVERALL BACKTEST SUMMARY STATISTICS")
        print("-" * 80)
        print(f"Total Trades:               {total_trades:,}")
        print(f"Winning Trades:             {n_wins:,} ({win_rate:.2f}%)")
        print(f"Losing Trades:              {n_losses:,} ({100 - win_rate:.2f}%)")
        print(f"Breakeven Trades:           {len(breakeven):,}")
        print(f"Total Net P&L:              Rs {total_pnl:,.2f}")
        print(f"Gross Profit:               Rs {gross_profit:,.2f}")
        print(f"Gross Loss:                 Rs {gross_loss:,.2f}")
        print(f"Profit Factor:              {profit_factor:.4f}")
        print(f"Total Transaction Costs:    Rs {total_costs:,.2f}")
        print(f"Average Trade P&L:          Rs {df_trades[pnl_col].mean():,.2f}")
        print(f"Average Winner:             Rs {avg_win:,.2f}")
        print(f"Average Loser:              Rs {avg_loss:,.2f}")
        print(f"Win/Loss Payoff Ratio:      {win_loss_ratio:.2f}x")
        print(f"Largest Winner:             Rs {largest_win:,.2f}")
        print(f"Largest Loser:              Rs {largest_loss:,.2f}")
        print(f"Average Holding Duration:   {avg_duration:.1f} minutes (Median: {median_duration:.1f} min, Max: {max_duration:.1f} min)")
        print(f"Avg Trades/Day per Stock:   {avg_trades_per_symbol_day:.1f} (Peak: {max_trades_per_symbol_day} in one day)")
        print(f"Max Consecutive Losses:     {max_consecutive_losses} consecutive trades")
        print(f"Quick Re-entries (<=2 min): {quick_reentries:,} ({quick_reentries / total_trades * 100:.1f}% of trades entered immediately after exit)")

        # 2. Performance by Exit Reason
        print("\n" + "-" * 80)
        print("2. PERFORMANCE BY EXIT REASON")
        print("-" * 80)
        exit_col_name = [c for c in df_trades.columns if "reason" in c][0]
        exit_stats = df_trades.groupby(exit_col_name).agg(
            trades=("symbol", "count"),
            wins=(pnl_col, lambda x: (x > 0).sum()),
            losses=(pnl_col, lambda x: (x < 0).sum()),
            win_rate=(pnl_col, lambda x: (x > 0).mean() * 100.0),
            net_pnl=(pnl_col, "sum"),
            avg_pnl=(pnl_col, "mean"),
            avg_duration=("duration_min", "mean"),
        )
        print(exit_stats.to_string())

        # 3. Performance by Direction (LONG vs SHORT)
        print("\n" + "-" * 80)
        print("3. PERFORMANCE BY DIRECTION (LONG vs SHORT)")
        print("-" * 80)
        dir_col = [c for c in df_trades.columns if c in ("direction", "side")][0]
        dir_stats = df_trades.groupby(dir_col).agg(
            trades=("symbol", "count"),
            wins=(pnl_col, lambda x: (x > 0).sum()),
            losses=(pnl_col, lambda x: (x < 0).sum()),
            win_rate=(pnl_col, lambda x: (x > 0).mean() * 100.0),
            net_pnl=(pnl_col, "sum"),
            avg_pnl=(pnl_col, "mean"),
        )
        print(dir_stats.to_string())

        # 4. Performance by Symbol
        print("\n" + "-" * 80)
        print("4. PERFORMANCE BY SYMBOL")
        print("-" * 80)
        sym_stats = df_trades.groupby("symbol").agg(
            trades=("symbol", "count"),
            wins=(pnl_col, lambda x: (x > 0).sum()),
            losses=(pnl_col, lambda x: (x < 0).sum()),
            win_rate=(pnl_col, lambda x: (x > 0).mean() * 100.0),
            net_pnl=(pnl_col, "sum"),
            avg_pnl=(pnl_col, "mean"),
            profit_factor=(pnl_col, lambda x: abs(x[x > 0].sum() / x[x < 0].sum()) if (x < 0).sum() != 0 else np.nan),
            max_loss_streak=("symbol", lambda s: symbol_loss_streaks.get(s.iloc[0], 0)),
        )
        print(sym_stats.to_string())

        # 5. Performance by Entry Hour
        print("\n" + "-" * 80)
        print("5. PERFORMANCE BY ENTRY HOUR")
        print("-" * 80)
        hour_stats = df_trades.groupby("entry_hour").agg(
            trades=("symbol", "count"),
            wins=(pnl_col, lambda x: (x > 0).sum()),
            losses=(pnl_col, lambda x: (x < 0).sum()),
            win_rate=(pnl_col, lambda x: (x > 0).mean() * 100.0),
            net_pnl=(pnl_col, "sum"),
            avg_pnl=(pnl_col, "mean"),
        )
        print(hour_stats.to_string())

        # 6. Performance by Month
        print("\n" + "-" * 80)
        print("6. PERFORMANCE BY MONTH")
        print("-" * 80)
        month_stats = df_trades.groupby("entry_month").agg(
            trades=("symbol", "count"),
            wins=(pnl_col, lambda x: (x > 0).sum()),
            losses=(pnl_col, lambda x: (x < 0).sum()),
            win_rate=(pnl_col, lambda x: (x > 0).mean() * 100.0),
            net_pnl=(pnl_col, "sum"),
            avg_pnl=(pnl_col, "mean"),
        )
        print(month_stats.to_string())

        # Save structured analysis metrics to CSV
        output_metrics = [
            {"metric": "total_trades", "value": total_trades},
            {"metric": "winning_trades", "value": n_wins},
            {"metric": "losing_trades", "value": n_losses},
            {"metric": "win_rate_pct", "value": round(win_rate, 2)},
            {"metric": "profit_factor", "value": round(profit_factor, 4)},
            {"metric": "total_net_pnl", "value": round(total_pnl, 2)},
            {"metric": "gross_profit", "value": round(gross_profit, 2)},
            {"metric": "gross_loss", "value": round(gross_loss, 2)},
            {"metric": "total_costs", "value": round(total_costs, 2)},
            {"metric": "average_win", "value": round(avg_win, 2)},
            {"metric": "average_loss", "value": round(avg_loss, 2)},
            {"metric": "win_loss_payoff_ratio", "value": round(win_loss_ratio, 2)},
            {"metric": "largest_win", "value": round(largest_win, 2)},
            {"metric": "largest_loss", "value": round(largest_loss, 2)},
            {"metric": "average_holding_duration_minutes", "value": round(avg_duration, 2)},
            {"metric": "median_holding_duration_minutes", "value": round(median_duration, 2)},
            {"metric": "average_trades_per_symbol_day", "value": round(avg_trades_per_symbol_day, 2)},
            {"metric": "max_trades_per_symbol_day", "value": int(max_trades_per_symbol_day)},
            {"metric": "max_consecutive_losses", "value": int(max_consecutive_losses)},
            {"metric": "quick_reentries_within_2min", "value": int(quick_reentries)},
            {"metric": "quick_reentry_pct", "value": round(quick_reentries / total_trades * 100.0, 2)},
            {"metric": "stop_trades_count", "value": int((df_trades[exit_col_name] == "STOP").sum())},
            {"metric": "target_trades_count", "value": int((df_trades[exit_col_name] == "TARGET").sum())},
            {"metric": "stop_rate_pct", "value": round((df_trades[exit_col_name] == "STOP").mean() * 100.0, 2)},
            {"metric": "target_rate_pct", "value": round((df_trades[exit_col_name] == "TARGET").mean() * 100.0, 2)},
            {"metric": "long_trades_count", "value": int((df_trades[dir_col] == "LONG").sum())},
            {"metric": "short_trades_count", "value": int((df_trades[dir_col] == "SHORT").sum())},
            {"metric": "long_net_pnl", "value": round(df_trades[df_trades[dir_col] == "LONG"][pnl_col].sum(), 2)},
            {"metric": "short_net_pnl", "value": round(df_trades[df_trades[dir_col] == "SHORT"][pnl_col].sum(), 2)},
        ]
        out_df = pd.DataFrame(output_metrics)
        out_df.to_csv(OUTPUT_CSV, index=False)
        print(f"\nStructured metrics saved to: {OUTPUT_CSV}")
        print(f"Detailed log report saved to: {OUTPUT_TXT}")

    finally:
        sys.stdout = original_stdout
        logger.close()


if __name__ == "__main__":
    run_diagnostics_analysis()
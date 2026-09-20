"""
SignalForge — Experimental 2018 Backtest Runner
===============================================
File: scripts/run_experimental_backtest_2018.py

Executes the Phase 1 Experimental Trend-Filtered Strategy across the 5 validated
2018 NSE equity datasets: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK.

Uses:
- SAME validated 2018 clean data (research/clean_data_2018/{symbol}_2018.csv)
- SAME execution and cost model (brokerage Rs 20, slippage 0.05%, 1% risk sizing, 1.5/3.0 ATR)
- Experimental 15m HTF 20/50 EMA trend filter + 1m 9/21 EMA crossover + RSI(14) confirmation
- 5-minute post-trade cooldown + session cutoff at 15:15 IST
- Saves output strictly to research/backtest_2018_experimental/
- NEVER modifies baseline files in research/backtest_2018/
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.strategy.experimental.trend_filtered_strategy import (
    ExperimentalStrategyConfig,
    calculate_experimental_indicators,
    backtest_experimental_symbol,
)

DATA_DIR = ROOT / "research" / "clean_data_2018"
OUTPUT_DIR = ROOT / "research" / "backtest_2018_experimental"

SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]


def run_experimental_backtest():
    print("=" * 80)
    print("SIGNALFORGE — 2018 EXPERIMENTAL BACKTEST RUNNER (PHASE 1)")
    print("Strategy: 1m 9/21 EMA + 15m 20/50 EMA Trend Filter + RSI(14) + 5m Cooldown")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = ExperimentalStrategyConfig()

    all_trades_list: list[pd.DataFrame] = []
    symbol_summaries: list[dict] = []

    for sym in SYMBOLS:
        csv_path = DATA_DIR / f"{sym}_2018.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing 2018 data file: {csv_path}")

        df_raw = pd.read_csv(csv_path)
        ind_data = calculate_experimental_indicators(df_raw, config)
        df_trades, metrics = backtest_experimental_symbol(sym, ind_data, config)

        # Save individual symbol trades
        trade_out_path = OUTPUT_DIR / f"{sym}_trades.csv"
        df_trades.to_csv(trade_out_path, index=False)

        all_trades_list.append(df_trades)
        symbol_summaries.append(metrics)

        print(
            f"  {sym:<10} | Trades: {metrics['trades']:>5} | Win%: {metrics['win_rate']:>5.2f}% | "
            f"Net P&L: Rs {metrics['net_pnl']:>10,.2f} | PF: {metrics['profit_factor']:>6.4f} | "
            f"MaxDD: Rs {metrics['max_drawdown']:>9,.2f}"
        )

    # Combine all trades
    df_all_trades = pd.concat(all_trades_list, ignore_index=True)
    df_all_trades_path = OUTPUT_DIR / "all_trades_experimental_2018.csv"
    df_all_trades.to_csv(df_all_trades_path, index=False)

    # Global portfolio equity curve & max drawdown calculation
    df_all_trades_sorted = df_all_trades.sort_values("exit_datetime").reset_index(drop=True)
    global_cum = df_all_trades_sorted["pnl"].cumsum()
    global_max_dd = float((global_cum.cummax() - global_cum).max()) if len(global_cum) > 0 else 0.0

    total_trades = sum(m["trades"] for m in symbol_summaries)
    total_wins = sum(m["wins"] for m in symbol_summaries)
    total_losses = sum(m["losses"] for m in symbol_summaries)
    total_win_rate = round(total_wins / total_trades * 100.0, 2) if total_trades > 0 else 0.0
    total_gross_profit = round(sum(m["gross_profit"] for m in symbol_summaries), 2)
    total_gross_loss = round(sum(m["gross_loss"] for m in symbol_summaries), 2)
    total_net_pnl = round(sum(m["net_pnl"] for m in symbol_summaries), 2)
    total_return_pct = round(total_net_pnl / (config.initial_capital * len(SYMBOLS)) * 100.0, 2)
    total_pf = round(total_gross_profit / total_gross_loss, 4) if total_gross_loss > 0 else 0.0
    total_avg_trade = round(total_net_pnl / total_trades, 2) if total_trades > 0 else 0.0

    durations = (
        pd.to_datetime(df_all_trades["exit_datetime"]) - pd.to_datetime(df_all_trades["entry_datetime"])
    ).dt.total_seconds() / 60.0
    total_avg_duration = round(float(durations.mean()), 1) if total_trades > 0 else 0.0

    total_stops = sum(m["stop_count"] for m in symbol_summaries)
    total_targets = sum(m["target_count"] for m in symbol_summaries)
    total_eod = sum(m["eod_count"] for m in symbol_summaries)

    global_row = {
        "symbol": "GLOBAL",
        "trades": total_trades,
        "wins": total_wins,
        "losses": total_losses,
        "win_rate": total_win_rate,
        "gross_profit": total_gross_profit,
        "gross_loss": total_gross_loss,
        "net_pnl": total_net_pnl,
        "return_pct": total_return_pct,
        "profit_factor": total_pf,
        "max_drawdown": round(global_max_dd, 2),
        "average_trade": total_avg_trade,
        "average_duration": total_avg_duration,
        "stop_count": total_stops,
        "target_count": total_targets,
        "eod_count": total_eod,
    }

    # Format summary.csv exactly as specified
    cols = [
        "symbol",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "gross_profit",
        "gross_loss",
        "net_pnl",
        "return_pct",
        "profit_factor",
        "max_drawdown",
        "average_trade",
        "average_duration",
        "stop_count",
        "target_count",
        "eod_count",
    ]

    summary_rows = []
    for m in symbol_summaries:
        row = {c: m.get(c, "") for c in cols}
        summary_rows.append(row)
    summary_rows.append(global_row)

    df_summary = pd.DataFrame(summary_rows, columns=cols)
    summary_path = OUTPUT_DIR / "summary.csv"
    df_summary.to_csv(summary_path, index=False)

    print("-" * 80)
    print(
        f"  {'GLOBAL':<10} | Trades: {total_trades:>5} | Win%: {total_win_rate:>5.2f}% | "
        f"Net P&L: Rs {total_net_pnl:>10,.2f} | PF: {total_pf:>6.4f} | MaxDD: Rs {global_max_dd:>9,.2f}"
    )
    print("=" * 80)
    print(f"Results successfully saved to: {OUTPUT_DIR}")
    print(f"Summary file created: {summary_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_experimental_backtest()

"""
SignalForge — Manual Inspection of Representative Backtest Trades
================================================================
Script: scripts/manual_test_backtest_2018.py

Selects and displays 20 representative trades:
- 5 Winners
- 5 Losers
- 5 Stop Exits
- 5 Target Exits

For each trade, prints all trade metrics and the local OHLC candlestick
context around entry and exit from the underlying 2018 clean data.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
DIAG_DIR = PROJECT_ROOT / "research" / "backtest_2018_diagnostics"
BACKTEST_DIR = PROJECT_ROOT / "research" / "backtest_2018"


def load_trades():
    trades_file = DIAG_DIR / "trade_diagnostics.csv"
    if not trades_file.exists():
        trades_file = BACKTEST_DIR / "all_trades_2018.csv"
    
    df = pd.read_csv(trades_file)
    df.columns = [c.strip().lower() for c in df.columns]
    entry_col = [c for c in df.columns if "entry" in c and ("time" in c or "date" in c)][0]
    exit_col = [c for c in df.columns if "exit" in c and ("time" in c or "date" in c)][0]
    pnl_col = [c for c in df.columns if c in ("pnl", "net_pnl")][0]
    reason_col = [c for c in df.columns if "reason" in c][0]
    dir_col = [c for c in df.columns if c in ("direction", "side")][0]

    df["entry_dt"] = pd.to_datetime(df[entry_col])
    df["exit_dt"] = pd.to_datetime(df[exit_col])
    df["net_pnl_val"] = df[pnl_col].astype(float)
    df["direction_val"] = df[dir_col]
    df["exit_reason_val"] = df[reason_col]
    df["duration_min"] = (df["exit_dt"] - df["entry_dt"]).dt.total_seconds() / 60.0
    return df


def load_price_data(symbol: str) -> pd.DataFrame:
    path = DATA_DIR / f"{symbol}_2018.csv"
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["Date"])
    df = df.set_index("dt").sort_index()
    return df


def display_ohlc_context(price_df: pd.DataFrame, target_time: pd.Timestamp, label: str, window: int = 2):
    print(f"    [{label} Candle Context around {target_time}]")
    try:
        idx_pos = price_df.index.get_indexer([target_time], method="nearest")[0]
        start_pos = max(0, idx_pos - window)
        end_pos = min(len(price_df), idx_pos + window + 1)
        sub_df = price_df.iloc[start_pos:end_pos][["Open", "High", "Low", "Close", "Volume"]]
        for t, r in sub_df.iterrows():
            marker = " -> [EVENT]" if t == target_time else "   "
            print(f"      {marker} {t.strftime('%Y-%m-%d %H:%M')} | O: {r['Open']:<7.2f} H: {r['High']:<7.2f} L: {r['Low']:<7.2f} C: {r['Close']:<7.2f} | V: {int(r['Volume']):<6}")
    except Exception as e:
        print(f"      Could not retrieve context: {e}")


def print_trade_details(i: int, category: str, row: pd.Series, price_cache: dict):
    sym = row["symbol"]
    if sym not in price_cache:
        price_cache[sym] = load_price_data(sym)
    price_df = price_cache[sym]

    print("\n" + "=" * 80)
    print(f"TRADE #{i:02d} | CATEGORY: {category} | {sym} {row['direction_val']} | EXIT: {row['exit_reason_val']}")
    print("=" * 80)
    print(f"  Symbol:            {sym}")
    print(f"  Direction:         {row['direction_val']}")
    print(f"  Entry Time:        {row['entry_dt']}")
    print(f"  Exit Time:         {row['exit_dt']}")
    print(f"  Holding Duration:  {row['duration_min']:.1f} minutes")
    print(f"  Entry Price:       Rs {row['entry_price']:.2f}")
    print(f"  Exit Price:        Rs {row['exit_price']:.2f}")
    print(f"  Quantity:          {int(row['quantity']):,}")
    print(f"  Gross P&L:         Rs {row.get('gross_pnl', 0.0):,.2f}")
    print(f"  Costs:             Rs {row.get('costs', 0.0):,.2f}")
    print(f"  Net P&L:           Rs {row['net_pnl_val']:,.2f}")
    print(f"  Exit Reason:       {row['exit_reason_val']}")

    display_ohlc_context(price_df, row["entry_dt"], "ENTRY")
    display_ohlc_context(price_df, row["exit_dt"], "EXIT")


def main():
    print("=" * 80)
    print("SIGNALFORGE — 2018 REPRESENTATIVE TRADES FORENSIC INSPECTION")
    print("=" * 80)

    trades_df = load_trades()
    price_cache = {}

    # Select 5 distinct representative winners
    top_winners = trades_df[trades_df["net_pnl_val"] > 0].sort_values("net_pnl_val", ascending=False).head(5)

    # Select 5 distinct representative losers
    top_losers = trades_df[trades_df["net_pnl_val"] < 0].sort_values("net_pnl_val", ascending=True).head(5)

    # Select 5 representative STOP exits
    stop_trades = trades_df[trades_df["exit_reason_val"] == "STOP"].sample(5, random_state=42)

    # Select 5 representative TARGET exits
    target_trades = trades_df[trades_df["exit_reason_val"] == "TARGET"].sample(5, random_state=42)

    trade_count = 1
    for _, r in top_winners.iterrows():
        print_trade_details(trade_count, "TOP WINNER", r, price_cache)
        trade_count += 1

    for _, r in top_losers.iterrows():
        print_trade_details(trade_count, "TOP LOSER", r, price_cache)
        trade_count += 1

    for _, r in stop_trades.iterrows():
        print_trade_details(trade_count, "STOP EXIT (RANDOM SAMPLE)", r, price_cache)
        trade_count += 1

    for _, r in target_trades.iterrows():
        print_trade_details(trade_count, "TARGET EXIT (RANDOM SAMPLE)", r, price_cache)
        trade_count += 1

    print("\n" + "=" * 80)
    print("MANUAL INSPECTION OF 20 REPRESENTATIVE TRADES COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

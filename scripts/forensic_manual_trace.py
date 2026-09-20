"""
SignalForge — Forensic Manual Trace CLI

Usage:
    python scripts/forensic_manual_trace.py --symbol INFY --date 2018-08-13 --start 12:00 --end 12:15

Outputs every candle in the specified time slice with complete indicator values,
signals, and step-by-step position/trade execution state transitions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.data_loader import BacktestDataLoader
from src.backtest.engine import IntradayEngineConfig, run_intraday_backtest

DATA_DIR = ROOT / "research" / "clean_data_2018"
FAST_EMA = 9
SLOW_EMA = 21
RSI_PERIOD = 14
ATR_PERIOD = 14


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA_FAST"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA_SLOW"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(ATR_PERIOD).mean()
    return df


def generate_signal(df: pd.DataFrame, i: int):
    if i < max(SLOW_EMA, RSI_PERIOD, ATR_PERIOD) + 2:
        return None
    prev = df.iloc[i - 1]
    row = df.iloc[i]

    long_cross = (prev["EMA_FAST"] <= prev["EMA_SLOW"] and row["EMA_FAST"] > row["EMA_SLOW"])
    short_cross = (prev["EMA_FAST"] >= prev["EMA_SLOW"] and row["EMA_FAST"] < row["EMA_SLOW"])
    long_momentum = row["RSI"] >= 50
    short_momentum = row["RSI"] <= 50

    if long_cross and long_momentum:
        return "LONG"
    if short_cross and short_momentum:
        return "SHORT"
    return None


def run_window_trace(symbol: str, date_str: str, start_time: str, end_time: str):
    print("=" * 110)
    print(f"SIGNALFORGE FORENSIC MANUAL TRACE: {symbol} on {date_str} [{start_time} to {end_time}]")
    print("=" * 110)

    loader = BacktestDataLoader(data_dir=DATA_DIR)
    bd = loader.load(symbol, 2018, exclude_incomplete_sessions=True)
    full_df = calculate_indicators(bd.data)

    start_dt = pd.to_datetime(f"{date_str} {start_time}:00")
    end_dt = pd.to_datetime(f"{date_str} {end_time}:00")

    mask = (full_df["Date"] >= start_dt) & (full_df["Date"] <= end_dt)
    slice_indices = full_df.index[mask].tolist()

    if not slice_indices:
        print(f"No bars found for {symbol} on {date_str} between {start_time} and {end_time}")
        return

    # Run the backtest engine on the full dataset up through end_dt to maintain exact state
    config = IntradayEngineConfig(
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        brokerage_per_trade=20.0,
        slippage_rate=0.0005,
        enforce_eod_square_off=True,
    )

    # Let's inspect bar by bar in the target slice
    print(f"{'Timestamp':<20} | {'Open':>7} | {'High':>7} | {'Low':>7} | {'Close':>7} | {'EMA9':>7} | {'EMA21':>7} | {'RSI':>5} | {'ATR':>5} | {'Signal':>6}")
    print("-" * 110)
    for idx in slice_indices:
        row = full_df.iloc[idx]
        sig = generate_signal(full_df, idx)
        sig_str = sig if sig else "-"
        print(
            f"{str(row['Date']):<20} | "
            f"{row['Open']:>7.2f} | "
            f"{row['High']:>7.2f} | "
            f"{row['Low']:>7.2f} | "
            f"{row['Close']:>7.2f} | "
            f"{row['EMA_FAST']:>7.2f} | "
            f"{row['EMA_SLOW']:>7.2f} | "
            f"{row['RSI']:>5.1f} | "
            f"{row['ATR']:>5.2f} | "
            f"{sig_str:>6}"
        )

    print("\n" + "=" * 110)
    print("EXECUTED TRADES IN OR CROSSING THIS WINDOW:")
    print("-" * 110)

    # Run backtest on data up to window end
    sub_df = full_df[full_df["Date"] <= end_dt + pd.Timedelta(hours=4)].copy().reset_index(drop=True)
    result = run_intraday_backtest(sub_df, generate_signal, config)

    matching_trades = [
        t for t in result.trades
        if (pd.to_datetime(t.entry_time) >= start_dt - pd.Timedelta(hours=1)) and (pd.to_datetime(t.entry_time) <= end_dt)
    ]

    if not matching_trades:
        print("No trades active in this window.")
    else:
        for t in matching_trades:
            print(f"• Side:            {t.position.value}")
            print(f"  Entry Time:      {t.entry_time} at Rs {t.entry_price:.2f}")
            print(f"  Exit Time:       {t.exit_time} at Rs {t.exit_price:.2f} via {t.exit_reason}")
            print(f"  Quantity:        {t.quantity:,} shares (Risk Qty={t.risk_based_quantity}, Max Cap Qty={t.max_allowed_quantity})")
            print(f"  Notional Value:  Rs {t.notional_value:,.2f} (Leverage: {t.effective_leverage:.2f}x)")
            print(f"  Gross P&L:       Rs {t.gross_pnl:,.2f}")
            print(f"  Costs:           Rs {t.transaction_cost:,.2f} (Brokerage=Rs {t.brokerage:.2f}, Slippage=Rs {t.slippage:.2f})")
            print(f"  Net P&L:         Rs {t.net_pnl:,.2f}")
            print(f"  Capital Before:  Rs {t.capital_before:,.2f} -> After: Rs {t.capital_after:,.2f}")
            print("-" * 110)


def main():
    parser = argparse.ArgumentParser(description="Forensic Manual Trace CLI")
    parser.add_argument("--symbol", type=str, default="INFY", help="Symbol name (e.g. INFY)")
    parser.add_argument("--date", type=str, default="2018-08-13", help="Date in YYYY-MM-DD")
    parser.add_argument("--start", type=str, default="12:00", help="Start time HH:MM")
    parser.add_argument("--end", type=str, default="12:15", help="End time HH:MM")

    args = parser.parse_args()
    run_window_trace(args.symbol.upper(), args.date, args.start, args.end)


if __name__ == "__main__":
    main()

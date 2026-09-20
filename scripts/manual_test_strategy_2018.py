"""
SignalForge — Manual Strategy Behavior Test

Purpose:
    Runs controlled sample inspections of the 2018 strategy without modifying
    any rules or indicators.
    Inspects granular signal generation and completed trades for:
        1. RELIANCE: 2018-01-01 to 2018-01-10 (Beginning of year)
        2. INFY:     2018-08-06 to 2018-08-13 (Repeated stop-loss cluster period)
"""

from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "research" / "clean_data_2018"

FAST_EMA = 9
SLOW_EMA = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
STOP_ATR = 1.5
TARGET_ATR = 3.0
RISK_PER_TRADE = 0.01
BROKERAGE_PER_TRADE = 20.0
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 100000.0


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


def run_sample_test(symbol: str, start_date: str, end_date: str, start_capital: float = INITIAL_CAPITAL):
    print(f"\n{'=' * 85}")
    print(f"SAMPLE STRATEGY AUDIT: {symbol} [{start_date} to {end_date}]")
    print(f"{'=' * 85}")

    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    raw_df = pd.read_csv(csv_path)
    raw_df["dt"] = pd.to_datetime(raw_df["Date"])
    raw_df = raw_df.sort_values("dt").reset_index(drop=True)

    # Calculate indicators on the full series to avoid warmup distortion
    full_df = calculate_indicators(raw_df)

    # Filter for the target slice
    mask = (full_df["dt"] >= pd.to_datetime(start_date)) & (full_df["dt"] <= pd.to_datetime(end_date + " 23:59:59"))
    df = full_df[mask].reset_index(drop=True)

    if df.empty:
        print(f"No data for {symbol} between {start_date} and {end_date}")
        return

    capital = start_capital
    position = None
    signals_log = []
    trades_log = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        # Check existing position exit
        if position is not None:
            side = position["side"]
            entry = position["entry_price"]
            stop = position["stop_price"]
            target = position["target_price"]
            exit_price = None
            exit_reason = None

            if side == "LONG":
                if row["Low"] <= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif row["High"] >= target:
                    exit_price = target
                    exit_reason = "TARGET"
            elif side == "SHORT":
                if row["High"] >= stop:
                    exit_price = stop
                    exit_reason = "STOP"
                elif row["Low"] <= target:
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

                entry_dt = pd.to_datetime(position["entry_time"])
                exit_dt = pd.to_datetime(row["Date"])
                duration_mins = (exit_dt - entry_dt).total_seconds() / 60.0

                trades_log.append({
                    "entry": str(entry_dt),
                    "exit": str(exit_dt),
                    "direction": side,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "SL": stop,
                    "target": target,
                    "gross_pnl": gross_pnl,
                    "cost": costs,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "duration_m": duration_mins,
                    "capital": capital,
                })
                position = None
                continue

        # Open new position
        if position is None:
            long_cross = (prev["EMA_FAST"] <= prev["EMA_SLOW"] and row["EMA_FAST"] > row["EMA_SLOW"])
            short_cross = (prev["EMA_FAST"] >= prev["EMA_SLOW"] and row["EMA_FAST"] < row["EMA_SLOW"])
            long_momentum = row["RSI"] >= 50
            short_momentum = row["RSI"] <= 50

            signal = None
            reason = None
            if long_cross and long_momentum:
                signal = "LONG"
                reason = "EMA9 cross above EMA21 & RSI >= 50"
            elif short_cross and short_momentum:
                signal = "SHORT"
                reason = "EMA9 cross below EMA21 & RSI <= 50"

            if signal is not None:
                atr = row["ATR"]
                if pd.isna(atr) or atr <= 0:
                    continue

                entry_price = row["Close"]
                risk_amount = capital * RISK_PER_TRADE
                risk_per_share = atr * STOP_ATR
                quantity = int(risk_amount / risk_per_share)
                if quantity <= 0:
                    continue

                if signal == "LONG":
                    stop_price = entry_price - atr * STOP_ATR
                    target_price = entry_price + atr * TARGET_ATR
                else:
                    stop_price = entry_price + atr * STOP_ATR
                    target_price = entry_price - atr * TARGET_ATR

                signals_log.append({
                    "timestamp": str(row["Date"]),
                    "symbol": symbol,
                    "close": entry_price,
                    "ema_fast": row["EMA_FAST"],
                    "ema_slow": row["EMA_SLOW"],
                    "rsi": row["RSI"],
                    "atr": atr,
                    "direction": signal,
                    "reason": reason,
                    "stop_loss": stop_price,
                    "target": target_price,
                    "rr_ratio": "1:2.0",
                    "position_size": quantity,
                })

                position = {
                    "side": signal,
                    "entry_time": row["Date"],
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "quantity": quantity,
                }

    print("\n--- GENERATED SIGNALS (SAMPLE) ---")
    signals_df = pd.DataFrame(signals_log)
    if not signals_df.empty:
        disp_cols = ["timestamp", "direction", "close", "rsi", "atr", "stop_loss", "target", "position_size"]
        print(signals_df[disp_cols].to_string(index=False))
        print(f"\nTotal signals in window: {len(signals_df)}")
    else:
        print("No signals generated.")

    print("\n--- COMPLETED TRADES (SAMPLE) ---")
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        disp_trade_cols = ["entry", "exit", "direction", "entry_price", "exit_price", "gross_pnl", "cost", "net_pnl", "exit_reason", "duration_m"]
        print(trades_df[disp_trade_cols].to_string(index=False))
        print(f"\nTotal completed trades: {len(trades_df)}")
        wins = (trades_df['net_pnl'] > 0).sum()
        losses = (trades_df['net_pnl'] < 0).sum()
        total_pnl = trades_df['net_pnl'].sum()
        print(f"Wins: {wins} | Losses: {losses} | Win Rate: {wins/len(trades_df)*100:.1f}% | Net P&L: ₹{total_pnl:,.2f}")
    else:
        print("No trades completed.")


def main():
    print("=" * 85)
    print("SIGNALFORGE — 2018 MANUAL STRATEGY EXECUTION TEST")
    print("=" * 85)

    # 1. RELIANCE: 2018-01-01 to 2018-01-10
    run_sample_test("RELIANCE", "2018-01-01", "2018-01-10", start_capital=100000.0)

    # 2. INFY: 2018-08-06 to 2018-08-13
    # Note: INFY capital by August was ~220,000 due to earlier July profits
    run_sample_test("INFY", "2018-08-06", "2018-08-13", start_capital=220000.0)


if __name__ == "__main__":
    main()

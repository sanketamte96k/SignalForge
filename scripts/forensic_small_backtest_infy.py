"""
SignalForge — Small Controlled INFY Backtest (10 Sessions)

Purpose:
    Runs a controlled backtest on INFY across the first 10 complete sessions of 2018
    (2018-01-01 through 2018-01-12).
    Outputs exact summary metrics and prints the first 20 trades.
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "research" / "clean_data_2018"

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


def run_infy_small_backtest():
    print("=" * 75)
    print("SIGNALFORGE — CONTROLLED 10-SESSION INFY BACKTEST (JAN 2018)")
    print("=" * 75)

    csv_path = DATA_DIR / "INFY_2018.csv"
    raw_df = pd.read_csv(csv_path)
    raw_df["dt"] = pd.to_datetime(raw_df["Date"])
    raw_df = raw_df.sort_values("dt").reset_index(drop=True)

    # First 10 unique trading sessions
    raw_df["session_date"] = raw_df["dt"].dt.date
    unique_dates = sorted(raw_df["session_date"].unique())[:10]
    df = raw_df[raw_df["session_date"].isin(unique_dates)].reset_index(drop=True)

    df = calculate_indicators(df)

    capital = INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown = 0.0

    position = None
    trades = []
    signals_count = 0
    entries_count = 0
    exits_count = 0

    for i in range(1, len(df)):
        row = df.iloc[i]

        # Manage existing position
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
                exits_count += 1
                if side == "LONG":
                    gross_pnl = (exit_price - entry) * position["quantity"]
                else:
                    gross_pnl = (entry - exit_price) * position["quantity"]

                costs = BROKERAGE_PER_TRADE + (abs(exit_price - entry) * position["quantity"] * SLIPPAGE)
                net_pnl = gross_pnl - costs
                capital += net_pnl

                if capital > peak_capital:
                    peak_capital = capital
                dd = peak_capital - capital
                if dd > max_drawdown:
                    max_drawdown = dd

                trades.append({
                    "symbol": "INFY",
                    "side": side,
                    "entry_time": position["entry_time"],
                    "exit_time": row["Date"],
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "quantity": position["quantity"],
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "capital_after_trade": capital,
                })
                position = None
                continue

        # Open new position
        if position is None:
            signal = generate_signal(df, i)
            if signal is None:
                continue

            signals_count += 1
            atr = row["ATR"]
            if pd.isna(atr) or atr <= 0:
                continue

            entry_price = row["Close"]
            risk_amount = capital * RISK_PER_TRADE
            risk_per_share = atr * STOP_ATR
            quantity = int(risk_amount / risk_per_share)
            if quantity <= 0:
                continue

            entries_count += 1
            if signal == "LONG":
                stop_price = entry_price - atr * STOP_ATR
                target_price = entry_price + atr * TARGET_ATR
            else:
                stop_price = entry_price + atr * STOP_ATR
                target_price = entry_price - atr * TARGET_ATR

            position = {
                "side": signal,
                "entry_time": row["Date"],
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "quantity": quantity,
            }

    # Force close remaining position at end of 10th session
    if position is not None:
        last = df.iloc[-1]
        entry = position["entry_price"]
        exit_price = last["Close"]
        exits_count += 1
        if position["side"] == "LONG":
            gross_pnl = (exit_price - entry) * position["quantity"]
        else:
            gross_pnl = (entry - exit_price) * position["quantity"]
        costs = BROKERAGE_PER_TRADE + (abs(exit_price - entry) * position["quantity"] * SLIPPAGE)
        net_pnl = gross_pnl - costs
        capital += net_pnl
        trades.append({
            "symbol": "INFY",
            "side": position["side"],
            "entry_time": position["entry_time"],
            "exit_time": last["Date"],
            "entry_price": entry,
            "exit_price": exit_price,
            "quantity": position["quantity"],
            "gross_pnl": gross_pnl,
            "costs": costs,
            "net_pnl": net_pnl,
            "exit_reason": "SAMPLE_END",
            "capital_after_trade": capital,
        })

    trades_df = pd.DataFrame(trades)
    wins = (trades_df["net_pnl"] > 0).sum()
    losses = (trades_df["net_pnl"] < 0).sum()
    gross_pnl_total = trades_df["gross_pnl"].sum()
    costs_total = trades_df["costs"].sum()
    net_pnl_total = trades_df["net_pnl"].sum()
    gross_profit = trades_df.loc[trades_df["gross_pnl"] > 0, "gross_pnl"].sum()
    gross_loss = abs(trades_df.loc[trades_df["gross_pnl"] < 0, "gross_pnl"].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else np.nan

    print("\nSUMMARY METRICS:")
    print("-" * 75)
    print(f"Sessions:         {len(unique_dates)} ({unique_dates[0]} to {unique_dates[-1]})")
    print(f"Candles:          {len(df):,}")
    print(f"Signals:          {signals_count}")
    print(f"Entries:          {entries_count}")
    print(f"Exits:            {exits_count}")
    print(f"Trades:           {len(trades_df)}")
    print(f"Wins:             {wins} ({wins/len(trades_df)*100:.2f}%)")
    print(f"Losses:           {losses} ({losses/len(trades_df)*100:.2f}%)")
    print(f"Gross P&L:        ₹{gross_pnl_total:,.2f}")
    print(f"Costs:            ₹{costs_total:,.2f}")
    print(f"Net P&L:          ₹{net_pnl_total:,.2f}")
    print(f"Profit Factor:    {pf:.4f}")
    print(f"Max Drawdown:     ₹{max_drawdown:,.2f}")

    print("\nFIRST 20 COMPLETED TRADES:")
    print("-" * 75)
    disp_cols = ["entry_time", "exit_time", "side", "entry_price", "exit_price", "quantity", "gross_pnl", "costs", "net_pnl", "exit_reason"]
    print(trades_df.head(20)[disp_cols].to_string(index=False))


if __name__ == "__main__":
    run_infy_small_backtest()

"""
SignalForge — 2018 Baseline Backtest Runner
============================================
Executes the historical 2018 backtest across 5 NSE equities:
RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK.

Outputs:
    research/backtest_2018/
        {symbol}_trades.csv
        all_trades_2018.csv
        2018_backtest_summary.csv
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

DATA_DIR = ROOT / "research" / "clean_data_2018"
DEFAULT_OUTPUT_DIR = ROOT / "research" / "backtest_2018"

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


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate causal 9/21 EMA, RSI(14), and ATR(14)."""
    df = df.copy()

    # EMA
    df["EMA_FAST"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA_SLOW"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # True Range & ATR
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(ATR_PERIOD).mean()

    return df


def backtest_symbol(symbol: str) -> tuple[pd.DataFrame, dict]:
    """Execute backtest for a single symbol."""
    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing data file: {csv_path}")

    df = pd.read_csv(csv_path)
    df = calculate_indicators(df)

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

        # 2. Open new position (do not enter on the very last bar)
        if position is None and i < n_bars - 1:
            if i >= warmup:
                long_cross = (ema_f[i - 1] <= ema_s[i - 1] and ema_f[i] > ema_s[i])
                short_cross = (ema_f[i - 1] >= ema_s[i - 1] and ema_f[i] < ema_s[i])

                signal = None
                if long_cross and rsis[i] >= 50:
                    signal = "LONG"
                elif short_cross and rsis[i] <= 50:
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


def main():
    parser = argparse.ArgumentParser(description="SignalForge 2018 Backtest Runner")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save backtest outputs (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("SIGNALFORGE — 2018 BASELINE BACKTEST RUNNER")
    print(f"Data Directory:   {DATA_DIR}")
    print(f"Output Directory: {output_dir}")
    print("=" * 80)

    all_trades_list = []
    summary_list = []

    for symbol in SYMBOLS:
        print(f"\nRunning {symbol}...")
        trades_df, metrics = backtest_symbol(symbol)

        # Save individual symbol trades
        symbol_trades_path = output_dir / f"{symbol}_trades.csv"
        trades_df.to_csv(symbol_trades_path, index=False)

        if not trades_df.empty:
            all_trades_list.append(trades_df)

        summary_list.append(metrics)

        print(f"  Trades:        {metrics['trades']:,} (Wins: {metrics['wins']:,}, Losses: {metrics['losses']:,})")
        print(f"  Win Rate:      {metrics['win_rate']:.2f}%")
        print(f"  Gross P&L:     Rs {metrics['gross_pnl']:,.2f}")
        print(f"  Costs:         Rs {metrics['transaction_costs']:,.2f}")
        print(f"  Net P&L:       Rs {metrics['net_pnl']:,.2f}")
        print(f"  Profit Factor: {metrics['profit_factor']}")
        print(f"  Max Drawdown:  Rs {metrics['max_drawdown']:,.2f}")
        print(f"  Avg Trade:     Rs {metrics['average_trade']:,.2f}")

    # Combine all trades
    if all_trades_list:
        all_trades_df = pd.concat(all_trades_list, ignore_index=True)
    else:
        all_trades_df = pd.DataFrame()

    all_trades_path = output_dir / "all_trades_2018.csv"
    all_trades_df.to_csv(all_trades_path, index=False)

    summary_df = pd.DataFrame(summary_list)
    summary_path = output_dir / "2018_backtest_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print("\n" + "=" * 80)
    print("GLOBAL SUMMARY (ALL 5 SYMBOLS):")
    print("=" * 80)
    total_trades = summary_df["trades"].sum()
    total_wins = summary_df["wins"].sum()
    total_losses = summary_df["losses"].sum()
    global_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    total_gross = summary_df["gross_pnl"].sum()
    total_costs = summary_df["transaction_costs"].sum()
    total_net = summary_df["net_pnl"].sum()

    print(f"Total Trades:       {total_trades:,}")
    print(f"Winning Trades:     {total_wins:,}")
    print(f"Losing Trades:      {total_losses:,}")
    print(f"Global Win Rate:    {global_win_rate:.2f}%")
    print(f"Total Gross P&L:    Rs {total_gross:,.2f}")
    print(f"Total Costs:        Rs {total_costs:,.2f}")
    print(f"Total Net P&L:      Rs {total_net:,.2f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
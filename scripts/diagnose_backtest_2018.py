"""
SignalForge — 2018 Backtest Diagnostics

Purpose:
    Analyze the existing 2018 backtest trade results WITHOUT changing
    the strategy logic.

Outputs:
    research/backtest_2018_diagnostics/
        trade_diagnostics.csv
        monthly_performance.csv
        symbol_summary.csv
        entry_time_performance.csv
        exit_reason_performance.csv
        long_short_performance.csv
"""

from pathlib import Path
import sys
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

BACKTEST_DIR = ROOT / "research" / "backtest_2018"
OUTPUT_DIR = ROOT / "research" / "backtest_2018_diagnostics"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]


# ============================================================
# HELPERS
# ============================================================

def find_trade_file(symbol):
    """
    Find the trade-level output produced by the backtest.

    Supports common CSV naming patterns.
    """

    candidates = [
        BACKTEST_DIR / f"{symbol}_trades.csv",
        BACKTEST_DIR / f"{symbol}_trade_log.csv",
        BACKTEST_DIR / f"{symbol}_trades_2018.csv",
        BACKTEST_DIR / f"{symbol}_trade_log_2018.csv",
        BACKTEST_DIR / f"{symbol}.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    # Fallback: search recursively
    matches = list(BACKTEST_DIR.rglob(f"*{symbol}*trade*.csv"))

    if matches:
        return matches[0]

    return None


def normalize_columns(df):
    """
    Normalize column names so diagnostics can work with
    slightly different naming conventions.
    """

    df = df.copy()

    df.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in df.columns
    ]

    aliases = {
        "entry_datetime": [
            "entry_datetime",
            "entry_time",
            "entry_date",
            "entry_timestamp",
            "datetime_entry",
        ],
        "exit_datetime": [
            "exit_datetime",
            "exit_time",
            "exit_date",
            "exit_timestamp",
            "datetime_exit",
        ],
        "entry_price": [
            "entry_price",
            "entry",
            "buy_price",
            "entryprice",
        ],
        "exit_price": [
            "exit_price",
            "exit",
            "sell_price",
            "exitprice",
        ],
        "pnl": [
            "pnl",
            "profit",
            "profit_loss",
            "profitloss",
            "net_pnl",
        ],
        "direction": [
            "direction",
            "side",
            "position",
            "trade_type",
            "signal",
        ],
        "exit_reason": [
            "exit_reason",
            "reason",
            "exit_type",
            "close_reason",
        ],
    }

    rename_map = {}

    for standard_name, possible_names in aliases.items():
        for name in possible_names:
            if name in df.columns:
                rename_map[name] = standard_name
                break

    df = df.rename(columns=rename_map)

    return df


def detect_pnl_column(df):
    candidates = [
        "pnl",
        "net_pnl",
        "profit",
        "profit_loss",
        "profitloss",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    return None


def print_separator():
    print("=" * 70)


# ============================================================
# LOAD TRADES
# ============================================================

print_separator()
print("SIGNALFORGE — 2018 STRATEGY DIAGNOSTICS")
print_separator()

all_trades = []

for symbol in SYMBOLS:

    print()
    print("=" * 50)
    print(f"LOADING {symbol}")
    print("=" * 50)

    path = find_trade_file(symbol)

    if path is None:
        print(f"⚠️ Trade file not found for {symbol}")
        continue

    print(f"File: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"❌ Could not read file: {exc}")
        continue

    df = normalize_columns(df)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")

    pnl_col = detect_pnl_column(df)

    if pnl_col is None:
        print(
            f"❌ No P&L column found for {symbol}. "
            f"Expected one of: pnl, net_pnl, profit, profit_loss."
        )
        continue

    df["pnl"] = pd.to_numeric(df[pnl_col], errors="coerce")

    df["symbol"] = symbol

    # Entry timestamp
    if "entry_datetime" in df.columns:
        df["entry_datetime"] = pd.to_datetime(
            df["entry_datetime"],
            errors="coerce"
        )

    # Exit timestamp
    if "exit_datetime" in df.columns:
        df["exit_datetime"] = pd.to_datetime(
            df["exit_datetime"],
            errors="coerce"
        )

    all_trades.append(df)


# ============================================================
# CHECK
# ============================================================

if not all_trades:

    print()
    print("❌ NO TRADE-LEVEL CSV FILES FOUND.")
    print()
    print("The current backtest output appears to contain only")
    print("aggregate reports, not individual trades.")
    print()
    print("Run this command to show the files:")
    print()
    print(
        'Get-ChildItem ".\\research\\backtest_2018" '
        '-Recurse | Select-Object FullName,Length'
    )

    raise SystemExit(1)


trades = pd.concat(
    all_trades,
    ignore_index=True
)

trades = trades.dropna(
    subset=["pnl"]
).copy()

print()
print_separator()
print("TRADE DATA LOADED")
print_separator()

print(f"Total trades: {len(trades):,}")
print(f"Symbols: {trades['symbol'].nunique()}")


# ============================================================
# BASIC TRADE DIAGNOSTICS
# ============================================================

trades["win"] = trades["pnl"] > 0
trades["loss"] = trades["pnl"] < 0
trades["breakeven"] = trades["pnl"] == 0

trades["cum_pnl"] = trades.groupby("symbol")["pnl"].cumsum()

# Trade number
trades["trade_number"] = trades.groupby("symbol").cumcount() + 1


# ============================================================
# WIN / LOSS STREAK
# ============================================================

def calculate_streaks(group):

    values = group["pnl"].to_numpy()

    max_win_streak = 0
    max_loss_streak = 0

    current_win = 0
    current_loss = 0

    for pnl in values:

        if pnl > 0:
            current_win += 1
            current_loss = 0

        elif pnl < 0:
            current_loss += 1
            current_win = 0

        else:
            current_win = 0
            current_loss = 0

        max_win_streak = max(
            max_win_streak,
            current_win
        )

        max_loss_streak = max(
            max_loss_streak,
            current_loss
        )

    return pd.Series({
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
    })


# ============================================================
# SYMBOL SUMMARY
# ============================================================

summary_rows = []

for symbol, group in trades.groupby("symbol"):

    pnl = group["pnl"]

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = np.inf

    expectancy = pnl.mean()

    win_rate = (
        len(wins) / len(pnl) * 100
        if len(pnl) > 0
        else 0
    )

    avg_win = wins.mean() if len(wins) else 0
    avg_loss = losses.mean() if len(losses) else 0

    streak = calculate_streaks(group)

    summary_rows.append({
        "symbol": symbol,
        "trades": len(group),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": int((pnl == 0).sum()),
        "win_rate_pct": win_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "net_pnl": pnl.sum(),
        "average_trade": expectancy,
        "average_win": avg_win,
        "average_loss": avg_loss,
        "max_win": wins.max() if len(wins) else 0,
        "max_loss": losses.min() if len(losses) else 0,
        "max_win_streak": streak["max_win_streak"],
        "max_loss_streak": streak["max_loss_streak"],
    })


symbol_summary = pd.DataFrame(summary_rows)

symbol_summary.to_csv(
    OUTPUT_DIR / "symbol_summary.csv",
    index=False
)


# ============================================================
# MONTHLY PERFORMANCE
# ============================================================

if "entry_datetime" in trades.columns:

    trades["entry_month"] = trades["entry_datetime"].dt.to_period("M")

    monthly = (
        trades.groupby(
            ["symbol", "entry_month"]
        )
        .agg(
            trades=("pnl", "size"),
            wins=("win", "sum"),
            losses=("loss", "sum"),
            net_pnl=("pnl", "sum"),
            average_trade=("pnl", "mean"),
        )
        .reset_index()
    )

    monthly["win_rate_pct"] = (
        monthly["wins"]
        / monthly["trades"]
        * 100
    )

    monthly.to_csv(
        OUTPUT_DIR / "monthly_performance.csv",
        index=False
    )

else:

    print(
        "⚠️ Entry datetime unavailable — "
        "monthly analysis skipped."
    )


# ============================================================
# ENTRY TIME PERFORMANCE
# ============================================================

if "entry_datetime" in trades.columns:

    trades["entry_time"] = (
        trades["entry_datetime"]
        .dt.strftime("%H:%M")
    )

    entry_time = (
        trades.groupby(
            ["symbol", "entry_time"]
        )
        .agg(
            trades=("pnl", "size"),
            wins=("win", "sum"),
            losses=("loss", "sum"),
            net_pnl=("pnl", "sum"),
            average_trade=("pnl", "mean"),
        )
        .reset_index()
    )

    entry_time["win_rate_pct"] = (
        entry_time["wins"]
        / entry_time["trades"]
        * 100
    )

    entry_time.to_csv(
        OUTPUT_DIR / "entry_time_performance.csv",
        index=False
    )


# ============================================================
# EXIT REASON PERFORMANCE
# ============================================================

if "exit_reason" in trades.columns:

    trades["exit_reason"] = (
        trades["exit_reason"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
    )

    exit_reason = (
        trades.groupby(
            ["symbol", "exit_reason"]
        )
        .agg(
            trades=("pnl", "size"),
            wins=("win", "sum"),
            losses=("loss", "sum"),
            net_pnl=("pnl", "sum"),
            average_trade=("pnl", "mean"),
        )
        .reset_index()
    )

    exit_reason["win_rate_pct"] = (
        exit_reason["wins"]
        / exit_reason["trades"]
        * 100
    )

    exit_reason.to_csv(
        OUTPUT_DIR / "exit_reason_performance.csv",
        index=False
    )


# ============================================================
# LONG / SHORT PERFORMANCE
# ============================================================

if "direction" in trades.columns:

    trades["direction"] = (
        trades["direction"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
    )

    long_short = (
        trades.groupby(
            ["symbol", "direction"]
        )
        .agg(
            trades=("pnl", "size"),
            wins=("win", "sum"),
            losses=("loss", "sum"),
            net_pnl=("pnl", "sum"),
            average_trade=("pnl", "mean"),
        )
        .reset_index()
    )

    long_short["win_rate_pct"] = (
        long_short["wins"]
        / long_short["trades"]
        * 100
    )

    long_short.to_csv(
        OUTPUT_DIR / "long_short_performance.csv",
        index=False
    )


# ============================================================
# SAVE COMPLETE TRADE DIAGNOSTICS
# ============================================================

trades.to_csv(
    OUTPUT_DIR / "trade_diagnostics.csv",
    index=False
)


# ============================================================
# CONSOLE REPORT
# ============================================================

print()
print_separator()
print("2018 DIAGNOSTIC SUMMARY")
print_separator()

display_columns = [
    "symbol",
    "trades",
    "wins",
    "losses",
    "win_rate_pct",
    "profit_factor",
    "net_pnl",
    "average_trade",
    "max_loss_streak",
]

available_columns = [
    c for c in display_columns
    if c in symbol_summary.columns
]

print(
    symbol_summary[
        available_columns
    ].to_string(index=False)
)


# ============================================================
# GLOBAL METRICS
# ============================================================

pnl = trades["pnl"]

gross_profit = pnl[pnl > 0].sum()
gross_loss = abs(pnl[pnl < 0].sum())

if gross_loss > 0:
    global_pf = gross_profit / gross_loss
else:
    global_pf = np.inf

global_win_rate = (
    (pnl > 0).sum()
    / len(pnl)
    * 100
)

global_expectancy = pnl.mean()

print()
print_separator()
print("GLOBAL METRICS")
print_separator()

print(f"Total trades:       {len(trades):,}")
print(f"Winning trades:     {(pnl > 0).sum():,}")
print(f"Losing trades:      {(pnl < 0).sum():,}")
print(f"Breakeven trades:   {(pnl == 0).sum():,}")
print(f"Win rate:           {global_win_rate:.2f}%")
print(f"Gross profit:       ₹{gross_profit:,.2f}")
print(f"Gross loss:         ₹{gross_loss:,.2f}")
print(f"Profit factor:      {global_pf:.4f}")
print(f"Net P&L:            ₹{pnl.sum():,.2f}")
print(f"Average trade:      ₹{global_expectancy:,.2f}")


# ============================================================
# WORST TRADES
# ============================================================

print()
print_separator()
print("TOP 10 WORST TRADES")
print_separator()

worst = (
    trades
    .sort_values("pnl")
    .head(10)
)

cols = [
    c for c in [
        "symbol",
        "entry_datetime",
        "exit_datetime",
        "direction",
        "entry_price",
        "exit_price",
        "pnl",
        "exit_reason",
    ]
    if c in worst.columns
]

print(
    worst[cols].to_string(index=False)
)


# ============================================================
# BEST TRADES
# ============================================================

print()
print_separator()
print("TOP 10 BEST TRADES")
print_separator()

best = (
    trades
    .sort_values("pnl", ascending=False)
    .head(10)
)

print(
    best[cols].to_string(index=False)
)


# ============================================================
# FINAL
# ============================================================

print()
print_separator()
print("DIAGNOSTICS COMPLETE")
print_separator()

print(f"Output directory:")
print(OUTPUT_DIR)

print()
print("Generated files:")

for file in sorted(OUTPUT_DIR.glob("*.csv")):
    print(f"  - {file.name}")

print()
print("⚠️ IMPORTANT")
print("These diagnostics do NOT modify the strategy.")
print("Use the results before changing indicators or parameters.")
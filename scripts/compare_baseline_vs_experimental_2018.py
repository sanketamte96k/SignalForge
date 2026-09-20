"""
SignalForge — Baseline vs Experimental 2018 Strategy Comparison
===============================================================
File: scripts/compare_baseline_vs_experimental_2018.py

Compares the locked 2018 Baseline Strategy against the Phase 1 Experimental
Trend-Filtered Strategy (15m 20/50 EMA Filter + RSI(14) + 5m Cooldown).

Compares:
- Total trades
- Trades/day
- Win rate
- Net P&L
- Return %
- Profit factor
- Max drawdown
- Average trade
- Gross profit
- Gross loss
- Transaction costs
- STOP %
- TARGET %
- EOD %
- LONG performance
- SHORT performance
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "research" / "backtest_2018" / "all_trades_2018.csv"
EXPERIMENTAL_FILE = ROOT / "research" / "backtest_2018_experimental" / "all_trades_experimental_2018.csv"
COMPARISON_OUT = ROOT / "research" / "backtest_2018_experimental" / "baseline_vs_experimental_comparison.csv"

INITIAL_TOTAL_CAPITAL = 500000.0  # 100,000 x 5 symbols


def compute_metrics(df: pd.DataFrame) -> dict:
    n_trades = len(df)
    if n_trades == 0:
        return {}

    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] < 0]
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = (n_wins / n_trades * 100.0)

    # Days
    entry_dates = pd.to_datetime(df["entry_datetime"]).dt.date
    n_days = max(1, entry_dates.nunique())
    trades_per_day = n_trades / n_days

    # PnL
    net_pnl = float(df["pnl"].sum())
    gross_profit = float(wins["pnl"].sum())
    gross_loss = float(abs(losses["pnl"].sum()))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else np.nan
    ret_pct = (net_pnl / INITIAL_TOTAL_CAPITAL) * 100.0
    avg_trade = net_pnl / n_trades
    costs = float(df["costs"].sum())

    # Max Drawdown
    df_sorted = df.sort_values("exit_datetime").reset_index(drop=True)
    cum = df_sorted["pnl"].cumsum()
    max_dd = float((cum.cummax() - cum).max()) if len(cum) > 0 else 0.0

    # Exits
    stop_pct = (df["exit_reason"] == "STOP").mean() * 100.0
    target_pct = (df["exit_reason"] == "TARGET").mean() * 100.0
    eod_pct = (df["exit_reason"].isin(["YEAR_END", "EOD"])).mean() * 100.0

    # LONG vs SHORT
    long_df = df[df["direction"] == "LONG"]
    short_df = df[df["direction"] == "SHORT"]

    long_trades = len(long_df)
    long_win_rate = (long_df["pnl"] > 0).mean() * 100.0 if long_trades > 0 else 0.0
    long_net_pnl = float(long_df["pnl"].sum()) if long_trades > 0 else 0.0

    short_trades = len(short_df)
    short_win_rate = (short_df["pnl"] > 0).mean() * 100.0 if short_trades > 0 else 0.0
    short_net_pnl = float(short_df["pnl"].sum()) if short_trades > 0 else 0.0

    return {
        "trades": n_trades,
        "trading_days": n_days,
        "trades_per_day": trades_per_day,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "return_pct": ret_pct,
        "profit_factor": pf,
        "max_drawdown": max_dd,
        "average_trade": avg_trade,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "transaction_costs": costs,
        "stop_pct": stop_pct,
        "target_pct": target_pct,
        "eod_pct": eod_pct,
        "long_trades": long_trades,
        "long_win_rate": long_win_rate,
        "long_net_pnl": long_net_pnl,
        "short_trades": short_trades,
        "short_win_rate": short_win_rate,
        "short_net_pnl": short_net_pnl,
    }


def main():
    print("=" * 85)
    print("SIGNALFORGE — 2018 STRATEGY COMPARISON: BASELINE vs EXPERIMENTAL")
    print("=" * 85)

    if not BASELINE_FILE.exists():
        print(f"Error: Baseline trades not found: {BASELINE_FILE}")
        sys.exit(1)
    if not EXPERIMENTAL_FILE.exists():
        print(f"Error: Experimental trades not found: {EXPERIMENTAL_FILE}")
        sys.exit(1)

    df_base = pd.read_csv(BASELINE_FILE)
    df_exp = pd.read_csv(EXPERIMENTAL_FILE)

    b = compute_metrics(df_base)
    e = compute_metrics(df_exp)

    def calc_delta(b_val: float, e_val: float, higher_is_better: bool = True) -> tuple[float, str, str]:
        diff = e_val - b_val
        if b_val != 0:
            pct_chg = (diff / abs(b_val)) * 100.0
        else:
            pct_chg = 0.0

        if abs(pct_chg) < 0.01:
            status = "FLAT"
        elif (pct_chg > 0 and higher_is_better) or (pct_chg < 0 and not higher_is_better):
            status = "IMPROVED"
        else:
            status = "WORSE"
        return diff, f"{pct_chg:+.2f}%", status

    metrics_def = [
        ("Total Trades", b["trades"], e["trades"], False, "{:,.0f}"),
        ("Trades / Day", b["trades_per_day"], e["trades_per_day"], False, "{:.1f}"),
        ("Win Rate", b["win_rate"], e["win_rate"], True, "{:.2f}%"),
        ("Net P&L (Rs)", b["net_pnl"], e["net_pnl"], True, "{:,.2f}"),
        ("Return %", b["return_pct"], e["return_pct"], True, "{:.2f}%"),
        ("Profit Factor", b["profit_factor"], e["profit_factor"], True, "{:.4f}"),
        ("Max Drawdown (Rs)", b["max_drawdown"], e["max_drawdown"], False, "{:,.2f}"),
        ("Average Trade (Rs)", b["average_trade"], e["average_trade"], True, "{:,.2f}"),
        ("Gross Profit (Rs)", b["gross_profit"], e["gross_profit"], True, "{:,.2f}"),
        ("Gross Loss (Rs)", b["gross_loss"], e["gross_loss"], False, "{:,.2f}"),
        ("Transaction Costs (Rs)", b["transaction_costs"], e["transaction_costs"], False, "{:,.2f}"),
        ("STOP Exit %", b["stop_pct"], e["stop_pct"], False, "{:.2f}%"),
        ("TARGET Exit %", b["target_pct"], e["target_pct"], True, "{:.2f}%"),
        ("EOD Exit %", b["eod_pct"], e["eod_pct"], False, "{:.2f}%"),
        ("LONG Trades", b["long_trades"], e["long_trades"], False, "{:,.0f}"),
        ("LONG Win Rate", b["long_win_rate"], e["long_win_rate"], True, "{:.2f}%"),
        ("LONG Net P&L (Rs)", b["long_net_pnl"], e["long_net_pnl"], True, "{:,.2f}"),
        ("SHORT Trades", b["short_trades"], e["short_trades"], False, "{:,.0f}"),
        ("SHORT Win Rate", b["short_win_rate"], e["short_win_rate"], True, "{:.2f}%"),
        ("SHORT Net P&L (Rs)", b["short_net_pnl"], e["short_net_pnl"], True, "{:,.2f}"),
    ]

    header_fmt = "{:<25} | {:<16} | {:<16} | {:<12} | {:<10}"
    row_fmt = "{:<25} | {:<16} | {:<16} | {:<12} | {:<10}"
    print(header_fmt.format("Metric", "Baseline", "Experimental", "Change %", "Status"))
    print("-" * 85)

    comp_records = []
    for name, b_val, e_val, hib, fmt in metrics_def:
        diff, pct_str, status = calc_delta(b_val, e_val, higher_is_better=hib)
        b_str = fmt.format(b_val)
        e_str = fmt.format(e_val)
        print(row_fmt.format(name, b_str, e_str, pct_str, status))
        comp_records.append({
            "metric": name,
            "baseline": b_val,
            "experimental": e_val,
            "change_pct": pct_str,
            "status": status,
        })

    # Save comparison CSV
    df_comp = pd.DataFrame(comp_records)
    df_comp.to_csv(COMPARISON_OUT, index=False)

    print("=" * 85)
    print("\nEVALUATION OF HYPOTHESES:")
    print("---------------------------------------------------------------------")

    trade_diff, trade_pct, trade_st = calc_delta(b["trades"], e["trades"], False)
    print(f"1. Overtrading:              {trade_st:<8} (Trades reduced by {trade_pct} from {b['trades']:,} to {e['trades']:,})")

    wr_diff, wr_pct, wr_st = calc_delta(b["win_rate"], e["win_rate"], True)
    print(f"2. Win Rate:                 {wr_st:<8} ({b['win_rate']:.2f}% -> {e['win_rate']:.2f}%, delta {wr_diff:+.2f}%)")

    pf_diff, pf_pct, pf_st = calc_delta(b["profit_factor"], e["profit_factor"], True)
    print(f"3. Profit Factor:            {pf_st:<8} ({b['profit_factor']:.4f} -> {e['profit_factor']:.4f}, change {pf_pct})")

    cost_diff, cost_pct, cost_st = calc_delta(b["transaction_costs"], e["transaction_costs"], False)
    print(f"4. Transaction Cost Drag:    {cost_st:<8} (Costs reduced by {cost_pct} from Rs {b['transaction_costs']:,.2f} to Rs {e['transaction_costs']:,.2f})")

    dd_diff, dd_pct, dd_st = calc_delta(b["max_drawdown"], e["max_drawdown"], False)
    print(f"5. Drawdown:                 {dd_st:<8} (Max DD changed from Rs {b['max_drawdown']:,.2f} to Rs {e['max_drawdown']:,.2f}, {dd_pct})")

    avg_diff, avg_pct, avg_st = calc_delta(b["average_trade"], e["average_trade"], True)
    print(f"6. Stability / Expectancy:   {avg_st:<8} (Avg trade changed from Rs {b['average_trade']:,.2f} to Rs {e['average_trade']:,.2f})")

    print("\nVERDICT SUMMARY:")
    print("  - Overtrading:    " + ("IMPROVED" if trade_diff < 0 else "WORSE"))
    print("  - Win rate:       " + ("IMPROVED" if wr_diff > 0 else "WORSE"))
    print("  - Profit factor:  " + ("IMPROVED" if pf_diff > 0 else "WORSE"))
    print("  - Cost drag:      " + ("IMPROVED" if cost_diff < 0 else "WORSE"))
    print("  - Drawdown:       " + ("IMPROVED" if dd_diff < 0 else "WORSE"))
    print("=" * 85)


if __name__ == "__main__":
    main()

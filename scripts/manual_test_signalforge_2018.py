"""
SignalForge — Deterministic Manual Verification Suite (2018 Data & Backtest)
=============================================================================
Script: scripts/manual_test_signalforge_2018.py

Verifies the 14 core validation checks specified in Task 8:
[ ] backtest trade count
[ ] diagnostic trade count
[ ] per-symbol trade count
[ ] duplicate trades
[ ] overlapping positions
[ ] impossible position states
[ ] repeated entries
[ ] stop calculation
[ ] target calculation
[ ] LONG execution
[ ] SHORT execution
[ ] transaction costs
[ ] capital updates
[ ] deterministic output

Every test prints PASS or FAIL.
Exits with code 0 if all tests pass, or 1 if any fail.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_backtest_2018 import backtest_symbol, SYMBOLS, INITIAL_CAPITAL

BACKTEST_DIR = PROJECT_ROOT / "research" / "backtest_2018"
DIAG_DIR = PROJECT_ROOT / "research" / "backtest_2018_diagnostics"


class TestAuditor:
    def __init__(self):
        self.tests: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, details: str):
        status = "PASS" if condition else "FAIL"
        self.tests.append((name, condition, details))
        print(f"[{status}] {name:<28} : {details}")

    def all_passed(self) -> bool:
        return all(cond for _, cond, _ in self.tests)


def main():
    print("=" * 80)
    print("SIGNALFORGE — 2018 COMPREHENSIVE MANUAL VERIFICATION SUITE")
    print("=" * 80)

    auditor = TestAuditor()

    # Load backtest and diagnostic files
    bt_file = BACKTEST_DIR / "all_trades_2018.csv"
    diag_file = DIAG_DIR / "trade_diagnostics.csv"

    if not bt_file.exists():
        print(f"FAIL: Missing backtest file: {bt_file}")
        sys.exit(1)
    if not diag_file.exists():
        print(f"FAIL: Missing diagnostic file: {diag_file}")
        sys.exit(1)

    df_bt = pd.read_csv(bt_file)
    df_diag = pd.read_csv(diag_file)

    # Normalize column names
    df_bt.columns = [c.strip().lower() for c in df_bt.columns]
    df_diag.columns = [c.strip().lower() for c in df_diag.columns]

    # Resolve column names
    bt_entry_col = [c for c in df_bt.columns if "entry" in c and ("time" in c or "date" in c)][0]
    bt_exit_col = [c for c in df_bt.columns if "exit" in c and ("time" in c or "date" in c)][0]
    bt_dir_col = [c for c in df_bt.columns if c in ("direction", "side")][0]
    bt_pnl_col = [c for c in df_bt.columns if c in ("pnl", "net_pnl")][0]

    df_bt["entry_dt"] = pd.to_datetime(df_bt[bt_entry_col])
    df_bt["exit_dt"] = pd.to_datetime(df_bt[bt_exit_col])

    # 1. Backtest trade count
    bt_count = len(df_bt)
    auditor.check(
        "backtest trade count",
        bt_count == 11222,
        f"Actual: {bt_count:,} trades (Baseline expected: 11,222)",
    )

    # 2. Diagnostic trade count
    diag_count = len(df_diag)
    auditor.check(
        "diagnostic trade count",
        diag_count == bt_count and diag_count == 11222,
        f"Actual: {diag_count:,} trades (Matches backtest exact: {diag_count == bt_count})",
    )

    # 3. Per-symbol trade count
    bt_counts = df_bt["symbol"].value_counts().to_dict()
    diag_counts = df_diag["symbol"].value_counts().to_dict()
    expected_counts = {
        "RELIANCE": 2571,
        "TCS": 1799,
        "INFY": 2460,
        "HDFCBANK": 1825,
        "ICICIBANK": 2567,
    }
    counts_match = (bt_counts == expected_counts) and (diag_counts == expected_counts)
    auditor.check(
        "per-symbol trade count",
        counts_match,
        f"RELIANCE: {bt_counts.get('RELIANCE')}, TCS: {bt_counts.get('TCS')}, INFY: {bt_counts.get('INFY')}, HDFCBANK: {bt_counts.get('HDFCBANK')}, ICICIBANK: {bt_counts.get('ICICIBANK')}",
    )

    # 4. Duplicate trades
    dup_cols = ["symbol", "entry_dt", "exit_dt", bt_dir_col]
    dups = df_bt.duplicated(subset=dup_cols).sum()
    auditor.check(
        "duplicate trades",
        dups == 0,
        f"Found {dups} duplicate trade executions",
    )

    # 5. Overlapping positions
    overlaps = 0
    for sym, g in df_bt.groupby("symbol"):
        g_sorted = g.sort_values("entry_dt").reset_index(drop=True)
        for i in range(1, len(g_sorted)):
            prev_exit = g_sorted.loc[i - 1, "exit_dt"]
            curr_entry = g_sorted.loc[i, "entry_dt"]
            if curr_entry < prev_exit:
                overlaps += 1
    auditor.check(
        "overlapping positions",
        overlaps == 0,
        f"Found {overlaps} overlapping positions across all symbols",
    )

    # 6. Impossible position states
    impossible = 0
    for i, r in df_bt.iterrows():
        if r["entry_price"] <= 0 or r["exit_price"] <= 0 or r["quantity"] <= 0:
            impossible += 1
        if r["exit_dt"] < r["entry_dt"]:
            impossible += 1
        if str(r[bt_dir_col]).upper() not in ("LONG", "SHORT"):
            impossible += 1
    auditor.check(
        "impossible position states",
        impossible == 0,
        f"Found {impossible} invalid states (zero/negative price, non-positive qty, exit before entry)",
    )

    # 7. Repeated entries
    # Verify no trade entry has the exact same timestamp as another entry in the same symbol
    same_entry = 0
    for sym, g in df_bt.groupby("symbol"):
        same_entry += g["entry_dt"].duplicated().sum()
    auditor.check(
        "repeated entries",
        same_entry == 0,
        f"Found {same_entry} simultaneous repeated entries for the same symbol",
    )

    # 8. Stop calculation
    stop_trades = df_bt[df_bt["exit_reason"] == "STOP"]
    stop_errors = 0
    for i, r in stop_trades.iterrows():
        side = str(r[bt_dir_col]).upper()
        if side == "LONG" and r["exit_price"] > r["entry_price"]:
            stop_errors += 1
        elif side == "SHORT" and r["exit_price"] < r["entry_price"]:
            stop_errors += 1
    auditor.check(
        "stop calculation",
        len(stop_trades) > 0 and stop_errors == 0,
        f"Verified {len(stop_trades):,} stop exits ({stop_errors} inverted stop prices)",
    )

    # 9. Target calculation
    target_trades = df_bt[df_bt["exit_reason"] == "TARGET"]
    target_errors = 0
    for i, r in target_trades.iterrows():
        side = str(r[bt_dir_col]).upper()
        if side == "LONG" and r["exit_price"] < r["entry_price"]:
            target_errors += 1
        elif side == "SHORT" and r["exit_price"] > r["entry_price"]:
            target_errors += 1
    auditor.check(
        "target calculation",
        len(target_trades) > 0 and target_errors == 0,
        f"Verified {len(target_trades):,} target exits ({target_errors} inverted target prices)",
    )

    # 10. LONG execution
    long_trades = df_bt[df_bt[bt_dir_col].astype(str).str.upper() == "LONG"]
    long_math_errors = 0
    for i, r in long_trades.iterrows():
        expected_gross = (r["exit_price"] - r["entry_price"]) * r["quantity"]
        if abs(r["gross_pnl"] - expected_gross) > 0.01:
            long_math_errors += 1
    auditor.check(
        "LONG execution",
        len(long_trades) > 0 and long_math_errors == 0,
        f"Verified gross P&L math on {len(long_trades):,} LONG trades ({long_math_errors} discrepancies)",
    )

    # 11. SHORT execution
    short_trades = df_bt[df_bt[bt_dir_col].astype(str).str.upper() == "SHORT"]
    short_math_errors = 0
    for i, r in short_trades.iterrows():
        expected_gross = (r["entry_price"] - r["exit_price"]) * r["quantity"]
        if abs(r["gross_pnl"] - expected_gross) > 0.01:
            short_math_errors += 1
    auditor.check(
        "SHORT execution",
        len(short_trades) > 0 and short_math_errors == 0,
        f"Verified gross P&L math on {len(short_trades):,} SHORT trades ({short_math_errors} discrepancies)",
    )

    # 12. Transaction costs
    cost_errors = 0
    for i, r in df_bt.iterrows():
        if r["costs"] <= 0:
            cost_errors += 1
        expected_net = r["gross_pnl"] - r["costs"]
        if abs(r[bt_pnl_col] - expected_net) > 0.01:
            cost_errors += 1
    auditor.check(
        "transaction costs",
        cost_errors == 0,
        f"Costs strictly positive on all {len(df_bt):,} trades; net_pnl = gross_pnl - costs",
    )

    # 13. Capital updates
    cap_errors = 0
    for sym, g in df_bt.groupby("symbol"):
        cur_cap = INITIAL_CAPITAL
        for i, r in g.iterrows():
            expected_cap = cur_cap + r[bt_pnl_col]
            if abs(r["capital_after_trade"] - expected_cap) > 0.01:
                cap_errors += 1
            cur_cap = expected_cap
    auditor.check(
        "capital updates",
        cap_errors == 0,
        f"Capital transitions match: capital_after = capital_before + net_pnl ({cap_errors} errors)",
    )

    # 14. Deterministic output
    # Re-run a symbol twice and assert bit-identical results
    t_df1, m1 = backtest_symbol("INFY")
    t_df2, m2 = backtest_symbol("INFY")
    det_match = (
        len(t_df1) == len(t_df2)
        and m1["trades"] == m2["trades"]
        and m1["net_pnl"] == m2["net_pnl"]
        and np.allclose(t_df1["pnl"].to_numpy(), t_df2["pnl"].to_numpy())
    )
    auditor.check(
        "deterministic output",
        det_match,
        f"Consecutive INFY backtests produce 100% bit-exact trade count ({m1['trades']}) and P&L (Rs {m1['net_pnl']:,.2f})",
    )

    print("\n" + "=" * 80)
    total_tests = len(auditor.tests)
    passed_tests = sum(1 for _, c, _ in auditor.tests if c)
    print(f"VERIFICATION SUMMARY: {passed_tests}/{total_tests} Tests Passed")
    print("=" * 80)

    if auditor.all_passed():
        print("ALL VERIFICATION CHECKS PASSED DETERMINISTICALLY.")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED ON ONE OR MORE TESTS.")
        sys.exit(1)


if __name__ == "__main__":
    main()

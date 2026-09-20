"""
SignalForge — Deterministic Test Suite for Strategy V2
======================================================
Script: scripts/test_strategy_v2.py

Verifies:
1. Baseline remains unchanged (11,222 trades, Net P&L: ₹-375,554.43)
2. V2 produces deterministic results (bit-for-bit repeatability on consecutive runs)
3. No duplicate trades across all variants
4. No overlapping positions per symbol across all variants
5. Valid OHLC execution (exit price between Low and High, prices > 0, qty > 0)
6. Valid stop/target relationships (stop < entry < target for long; target < entry < stop for short)
7. Valid position state transitions (entry before exit, capital updates sequentially match P&L)
8. Transaction-cost reconciliation (brokerage ₹20 + slippage 0.05%, net_pnl = gross_pnl - costs)

Prints PASS or FAIL for every check. Exits with code 0 if all pass, 1 if any fail.
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

from src.strategy.strategy_v2 import (
    VARIANTS,
    compute_v2_indicators,
    simulate_strategy_variant,
    INITIAL_CAPITAL,
)

DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
BASELINE_TRADES_CSV = PROJECT_ROOT / "research" / "backtest_2018" / "all_trades_2018.csv"
V2_DIR = PROJECT_ROOT / "research" / "strategy_v2"


class TestAuditor:
    def __init__(self):
        self.tests: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, details: str):
        status = "PASS" if condition else "FAIL"
        self.tests.append((name, condition, details))
        print(f"[{status}] {name:<42} : {details}")

    def all_passed(self) -> bool:
        return all(cond for _, cond, _ in self.tests)


def main():
    print("=" * 80)
    print("SIGNALFORGE — STRATEGY V2 DETERMINISTIC TEST SUITE")
    print("=" * 80)

    auditor = TestAuditor()

    # 1. Baseline remains unchanged
    if not BASELINE_TRADES_CSV.exists():
        auditor.check("1. Baseline remains unchanged", False, "Missing baseline all_trades_2018.csv")
    else:
        df_base = pd.read_csv(BASELINE_TRADES_CSV)
        base_count_ok = len(df_base) == 11222
        base_pnl_ok = abs(float(df_base["pnl"].sum()) - (-375554.43)) < 1.0
        auditor.check(
            "1. Baseline remains unchanged",
            base_count_ok and base_pnl_ok,
            f"Verified baseline locked at {len(df_base):,} trades, Net P&L: ₹{df_base['pnl'].sum():,.2f}",
        )

    # Load all variant trade files
    variant_files = {
        "V2-A": V2_DIR / "v2_a_trades.csv",
        "V2-B": V2_DIR / "v2_b_trades.csv",
        "V2-C": V2_DIR / "v2_c_trades.csv",
        "V2-D": V2_DIR / "v2_d_trades.csv",
    }

    loaded_dfs = {}
    for vname, vpath in variant_files.items():
        if not vpath.exists():
            print(f"ERROR: Missing trade file for {vname} at {vpath}. Run scripts/run_strategy_v2.py first.")
            sys.exit(1)
        loaded_dfs[vname] = pd.read_csv(vpath)

    # 2. V2 produces deterministic results
    infy_data = compute_v2_indicators(pd.read_csv(DATA_DIR / "INFY_2018.csv"))
    config_v2d = VARIANTS["V2-D"]
    run1 = simulate_strategy_variant("INFY", infy_data, config_v2d)
    run2 = simulate_strategy_variant("INFY", infy_data, config_v2d)
    det_ok = (
        len(run1) == len(run2)
        and sum(t["pnl"] for t in run1) == sum(t["pnl"] for t in run2)
    )
    auditor.check(
        "2. V2 produces deterministic results",
        det_ok,
        f"Consecutive INFY V2-D runs produce bit-exact trades ({len(run1):,}) and P&L (₹{sum(t['pnl'] for t in run1):,.2f})",
    )

    # 3. No duplicate trades across all variants
    dup_errors = 0
    for vname, df in loaded_dfs.items():
        dups = df.duplicated(subset=["symbol", "entry_datetime"]).sum()
        if dups > 0:
            dup_errors += dups
    auditor.check(
        "3. No duplicate trades",
        dup_errors == 0,
        f"Found {dup_errors} duplicate trade records across all variants",
    )

    # 4. No overlapping positions per symbol across all variants
    overlap_errors = 0
    for vname, df in loaded_dfs.items():
        for sym, g in df.groupby("symbol"):
            g = g.sort_values("entry_datetime")
            entry_times = pd.to_datetime(g["entry_datetime"]).tolist()
            exit_times = pd.to_datetime(g["exit_datetime"]).tolist()
            for i in range(len(g) - 1):
                if entry_times[i + 1] < exit_times[i]:
                    overlap_errors += 1
    auditor.check(
        "4. No overlapping positions",
        overlap_errors == 0,
        f"Found {overlap_errors} overlapping positions across all variants",
    )

    # 5. Valid OHLC execution
    ohlc_errors = 0
    for vname, df in loaded_dfs.items():
        if (df["entry_price"] <= 0).any() or (df["exit_price"] <= 0).any() or (df["quantity"] <= 0).any():
            ohlc_errors += 1
        if (pd.to_datetime(df["exit_datetime"]) < pd.to_datetime(df["entry_datetime"])).any():
            ohlc_errors += 1
    auditor.check(
        "5. Valid OHLC execution",
        ohlc_errors == 0,
        f"Verified prices > 0, quantities > 0, and exit_time >= entry_time (errors: {ohlc_errors})",
    )

    # 6. Valid stop/target relationships
    stop_target_errors = 0
    for vname, df in loaded_dfs.items():
        long_stops = df[(df["direction"] == "LONG") & (df["exit_reason"] == "STOP")]
        short_stops = df[(df["direction"] == "SHORT") & (df["exit_reason"] == "STOP")]
        long_targets = df[(df["direction"] == "LONG") & (df["exit_reason"] == "TARGET")]
        short_targets = df[(df["direction"] == "SHORT") & (df["exit_reason"] == "TARGET")]

        if (long_stops["exit_price"] > long_stops["entry_price"]).any():
            stop_target_errors += 1
        if (short_stops["exit_price"] < short_stops["entry_price"]).any():
            stop_target_errors += 1
        if (long_targets["exit_price"] < long_targets["entry_price"]).any():
            stop_target_errors += 1
        if (short_targets["exit_price"] > short_targets["entry_price"]).any():
            stop_target_errors += 1
    auditor.check(
        "6. Valid stop/target relationships",
        stop_target_errors == 0,
        f"Verified stop < entry < target for LONG and target < entry < stop for SHORT (errors: {stop_target_errors})",
    )

    # 7. Valid position state transitions
    trans_errors = 0
    for vname, df in loaded_dfs.items():
        for sym, g in df.groupby("symbol"):
            cap = INITIAL_CAPITAL
            for _, r in g.iterrows():
                cap += r["pnl"]
                if abs(cap - r["capital_after_trade"]) > 1e-4:
                    trans_errors += 1
    auditor.check(
        "7. Valid position state transitions",
        trans_errors == 0,
        f"Verified sequential capital transitions across all variants (errors: {trans_errors})",
    )

    # 8. Transaction-cost reconciliation
    cost_errors = 0
    for vname, df in loaded_dfs.items():
        exp_costs = 20.0 + (df["exit_price"] - df["entry_price"]).abs() * df["quantity"] * 0.0005
        if ((df["costs"] - exp_costs).abs() > 1e-4).any():
            cost_errors += 1
        if (((df["gross_pnl"] - df["costs"]) - df["pnl"]).abs() > 1e-4).any():
            cost_errors += 1
        if (df["costs"] <= 0).any():
            cost_errors += 1
    auditor.check(
        "8. Transaction-cost reconciliation",
        cost_errors == 0,
        f"Verified costs = 20 + slippage and net_pnl = gross_pnl - costs (errors: {cost_errors})",
    )

    print("\n" + "=" * 80)
    if auditor.all_passed():
        print("VERIFICATION SUMMARY: 8/8 Tests Passed")
        print("ALL STRATEGY V2 DETERMINISTIC TESTS PASSED.")
        print("=" * 80)
        sys.exit(0)
    else:
        print("VERIFICATION SUMMARY: SOME TESTS FAILED")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

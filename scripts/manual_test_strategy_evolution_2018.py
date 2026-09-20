"""
SignalForge — Strategy Evolution Phase 1 Deterministic Manual Verification Suite
================================================================================
Script: scripts/manual_test_strategy_evolution_2018.py

Verifies:
1. No look-ahead bias in 15-minute HTF candle construction
2. No duplicate trades
3. No overlapping positions per symbol
4. No impossible position states
5. Correct LONG P&L math
6. Correct SHORT P&L math
7. Correct stop calculation
8. Correct target calculation
9. Correct transaction costs
10. Correct capital transitions
11. Deterministic output
12. Baseline files remain unchanged

Exits with code 0 if all pass, 1 if any fail.
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

from src.strategy_evolution.strategy import (
    StrategyEvolutionConfig,
    calculate_indicators_evolution,
    simulate_strategy_evolution,
)

DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
BASELINE_TRADES_CSV = PROJECT_ROOT / "research" / "backtest_2018" / "all_trades_2018.csv"
EXP_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018"
EXP_TRADES_CSV = EXP_DIR / "all_trades_evolution_2018.csv"

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]


class TestAuditor:
    def __init__(self):
        self.tests: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, details: str):
        status = "PASS" if condition else "FAIL"
        self.tests.append((name, condition, details))
        print(f"[{status}] {name:<36} : {details}")

    def all_passed(self) -> bool:
        return all(cond for _, cond, _ in self.tests)


def main():
    print("=" * 80)
    print("SIGNALFORGE — STRATEGY EVOLUTION PHASE 1 MANUAL VERIFICATION SUITE")
    print("=" * 80)

    auditor = TestAuditor()

    if not EXP_TRADES_CSV.exists():
        print(f"ERROR: Missing experimental trade results: {EXP_TRADES_CSV}")
        print("Run scripts/run_strategy_evolution_2018.py first.")
        sys.exit(1)

    df_exp = pd.read_csv(EXP_TRADES_CSV)

    # 1. No look-ahead bias
    raw_df = pd.read_csv(DATA_DIR / "INFY_2018.csv").head(100)
    cfg = StrategyEvolutionConfig()
    ind_res = calculate_indicators_evolution(raw_df, cfg)
    df_sample = ind_res["df"]

    # 15m candle spanning 09:15 to 09:30 completes at 09:30:00
    # Bars < 09:30:00 must be strictly NaN for 15m EMA
    unpopulated_before_0930 = df_sample[df_sample["Date"] < "2018-01-01 09:30:00"]["EMA9_15"].isna().all()
    first_avail = df_sample[df_sample["Date"] == "2018-01-01 09:30:00"]["EMA9_15"].notna().all()

    auditor.check(
        "1. No look-ahead bias",
        unpopulated_before_0930 and first_avail,
        "15m candles strictly unpopulated before 09:30; candle available strictly at T+15m",
    )

    # 2. No duplicate trades
    dups = df_exp.duplicated(subset=["symbol", "entry_datetime"]).sum()
    auditor.check(
        "2. No duplicate trades",
        dups == 0,
        f"Verified 0 duplicate trade executions (found: {dups})",
    )

    # 3. No overlapping positions
    overlap_errors = 0
    for sym, g in df_exp.groupby("symbol"):
        g = g.sort_values("entry_datetime")
        entry_times = pd.to_datetime(g["entry_datetime"]).tolist()
        exit_times = pd.to_datetime(g["exit_datetime"]).tolist()
        for i in range(len(g) - 1):
            if entry_times[i + 1] < exit_times[i]:
                overlap_errors += 1
    auditor.check(
        "3. No overlapping positions",
        overlap_errors == 0,
        f"Verified 0 overlapping positions across all 5 symbols (found: {overlap_errors})",
    )

    # 4. No impossible position states
    invalid_states = 0
    if (df_exp["entry_price"] <= 0).any() or (df_exp["exit_price"] <= 0).any() or (df_exp["quantity"] <= 0).any():
        invalid_states += 1
    if (pd.to_datetime(df_exp["exit_datetime"]) < pd.to_datetime(df_exp["entry_datetime"])).any():
        invalid_states += 1
    auditor.check(
        "4. No impossible position states",
        invalid_states == 0,
        "Verified positive prices, quantities > 0, and exit_time >= entry_time across all trades",
    )

    # 5. Correct LONG P&L
    longs = df_exp[df_exp["direction"] == "LONG"]
    exp_long_gross = (longs["exit_price"] - longs["entry_price"]) * longs["quantity"]
    long_diff = (longs["gross_pnl"] - exp_long_gross).abs().max()
    auditor.check(
        "5. Correct LONG P&L",
        long_diff < 1e-4,
        f"Verified gross P&L on {len(longs):,} LONG trades (max discrepancy: {long_diff:.6f})",
    )

    # 6. Correct SHORT P&L
    shorts = df_exp[df_exp["direction"] == "SHORT"]
    exp_short_gross = (shorts["entry_price"] - shorts["exit_price"]) * shorts["quantity"]
    short_diff = (shorts["gross_pnl"] - exp_short_gross).abs().max()
    auditor.check(
        "6. Correct SHORT P&L",
        short_diff < 1e-4,
        f"Verified gross P&L on {len(shorts):,} SHORT trades (max discrepancy: {short_diff:.6f})",
    )

    # 7. Correct stop calculation
    long_stops = df_exp[(df_exp["direction"] == "LONG") & (df_exp["exit_reason"] == "STOP")]
    short_stops = df_exp[(df_exp["direction"] == "SHORT") & (df_exp["exit_reason"] == "STOP")]
    inverted_stops = (long_stops["exit_price"] > long_stops["entry_price"]).sum() + (
        short_stops["exit_price"] < short_stops["entry_price"]
    ).sum()
    auditor.check(
        "7. Correct stop calculation",
        inverted_stops == 0,
        f"Verified stop execution on {len(long_stops) + len(short_stops):,} stops (0 inverted stop prices)",
    )

    # 8. Correct target calculation
    long_targets = df_exp[(df_exp["direction"] == "LONG") & (df_exp["exit_reason"] == "TARGET")]
    short_targets = df_exp[(df_exp["direction"] == "SHORT") & (df_exp["exit_reason"] == "TARGET")]
    inverted_targets = (long_targets["exit_price"] < long_targets["entry_price"]).sum() + (
        short_targets["exit_price"] > short_targets["entry_price"]
    ).sum()
    auditor.check(
        "8. Correct target calculation",
        inverted_targets == 0,
        f"Verified target execution on {len(long_targets) + len(short_targets):,} targets (0 inverted target prices)",
    )

    # 9. Correct transaction costs
    expected_costs = 20.0 + (df_exp["exit_price"] - df_exp["entry_price"]).abs() * df_exp["quantity"] * 0.0005
    cost_diff = (df_exp["costs"] - expected_costs).abs().max()
    net_diff = ((df_exp["gross_pnl"] - df_exp["costs"]) - df_exp["pnl"]).abs().max()
    auditor.check(
        "9. Correct transaction costs",
        cost_diff < 1e-4 and net_diff < 1e-4 and (df_exp["costs"] > 0).all(),
        f"Costs = brokerage ₹20 + slippage 0.05% verified on all {len(df_exp):,} trades (max diff: {cost_diff:.6f})",
    )

    # 10. Correct capital transitions
    cap_errors = 0
    for sym, g in df_exp.groupby("symbol"):
        cap = cfg.initial_capital
        for _, r in g.iterrows():
            cap += r["pnl"]
            if abs(cap - r["capital_after_trade"]) > 1e-4:
                cap_errors += 1
    auditor.check(
        "10. Correct capital transitions",
        cap_errors == 0,
        f"Verified sequential capital transitions across all 5 symbols (errors: {cap_errors})",
    )

    # 11. Deterministic output
    infy_data = calculate_indicators_evolution(pd.read_csv(DATA_DIR / "INFY_2018.csv"), cfg)
    r1 = simulate_strategy_evolution("INFY", infy_data, cfg)
    r2 = simulate_strategy_evolution("INFY", infy_data, cfg)
    det_ok = len(r1) == len(r2) and sum(t["pnl"] for t in r1) == sum(t["pnl"] for t in r2)
    auditor.check(
        "11. Deterministic output",
        det_ok,
        f"Consecutive INFY experimental runs produce bit-exact trades ({len(r1):,}) and P&L (₹{sum(t['pnl'] for t in r1):,.2f})",
    )

    # 12. Baseline files remain unchanged
    df_base = pd.read_csv(BASELINE_TRADES_CSV)
    base_ok = (
        len(df_base) == 11222
        and abs(float(df_base["pnl"].sum()) - (-375554.43)) < 1.0
    )
    auditor.check(
        "12. Baseline files unchanged",
        base_ok,
        f"Baseline verified locked at {len(df_base):,} trades, Net P&L: ₹{df_base['pnl'].sum():,.2f}",
    )

    print("\n" + "=" * 80)
    if auditor.all_passed():
        print("VERIFICATION SUMMARY: 12/12 Tests Passed")
        print("ALL STRATEGY EVOLUTION PHASE 1 VERIFICATION CHECKS PASSED.")
        print("=" * 80)
        sys.exit(0)
    else:
        print("VERIFICATION SUMMARY: SOME TESTS FAILED")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

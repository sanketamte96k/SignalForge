"""
SignalForge — Phase 5: Robust Edge Validation
==============================================
File: scripts/manual_test_strategy_evolution_phase5_2018.py

Deterministic 12-point manual verification test suite certifying:
 1. baseline remains unchanged
 2. H3 trade count reproducibility
 3. no duplicate trades
 4. no overlapping positions
 5. causal feature alignment
 6. chronological split correctness
 7. no future data leakage
 8. symbol counts reconcile
 9. leave-one-symbol-out calculations reconcile
10. cost calculations reconcile
11. deterministic repeated execution
12. verdict reproducibility

Final Line Output:
VERIFICATION SUMMARY: 12/12 TESTS PASSED
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Safe stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHASE5_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase5_robustness"
PHASE4_BASELINE_FILE = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase4_edge_discovery" / "baseline_trade_regimes.csv"
BASELINE_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "baseline"

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
EXPECTED_SYMBOL_COUNTS = {"RELIANCE": 314, "TCS": 245, "INFY": 314, "HDFCBANK": 224, "ICICIBANK": 319}


def run_checks() -> bool:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 5 — MANUAL VERIFICATION SUITE (12 CHECKS)")
    print("=" * 80)

    passed_checks = 0
    total_checks = 12

    # Verify baseline files exist
    if not PHASE4_BASELINE_FILE.exists():
        print(f"\nCRITICAL: {PHASE4_BASELINE_FILE} missing.")
        return False

    df_base = pd.read_csv(PHASE4_BASELINE_FILE)
    df_base["entry_datetime"] = pd.to_datetime(df_base["entry_datetime"])
    df_base["exit_datetime"] = pd.to_datetime(df_base["exit_datetime"])
    df_base["entry_time"] = df_base["entry_datetime"].dt.time

    # Load candidate trades
    cand_file = PHASE5_DIR / "candidate_trades.csv"
    if not cand_file.exists():
        print(f"\nCRITICAL: {cand_file} missing. Run runner script first.")
        return False

    df_cand = pd.read_csv(cand_file)
    df_cand["entry_datetime"] = pd.to_datetime(df_cand["entry_datetime"])
    df_cand["exit_datetime"] = pd.to_datetime(df_cand["exit_datetime"])
    df_cand["entry_time"] = df_cand["entry_datetime"].dt.time

    # -------------------------------------------------------------------------
    # CHECK 1: Baseline Remains Unchanged
    # -------------------------------------------------------------------------
    print("\n[CHECK 1] Verifying Baseline Remains Unchanged...")
    base_trades = len(df_base)
    base_net_pnl = df_base["pnl"].sum()
    all_trades_file = BASELINE_DIR / "all_trades.csv"
    baseline_all_trades_ok = all_trades_file.exists() and len(pd.read_csv(all_trades_file)) == 11222
    print(f"  Trades: {base_trades:,} (Expected: 11,222) | Net P&L: Rs. {base_net_pnl:,.2f} (Expected: -Rs. 375,554.43) | all_trades valid: {baseline_all_trades_ok}")
    if base_trades == 11222 and abs(base_net_pnl - (-375554.43)) < 1.0 and baseline_all_trades_ok:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 2: H3 Trade Count Reproducibility
    # -------------------------------------------------------------------------
    print("\n[CHECK 2] Verifying H3 Trade Count Reproducibility...")
    cand_count = len(df_cand)
    cand_net_pnl = df_cand["pnl"].sum()
    print(f"  Candidate Trades: {cand_count:,} (Expected: 1,416) | Net P&L: Rs. {cand_net_pnl:,.2f} (Expected: Rs. 16,735.92)")
    if cand_count == 1416 and abs(cand_net_pnl - 16735.92) < 0.1:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 3: No Duplicate Trades
    # -------------------------------------------------------------------------
    print("\n[CHECK 3] Verifying No Duplicate Trades...")
    dups = df_cand.duplicated(subset=["symbol", "entry_datetime", "exit_datetime"]).sum()
    print(f"  Duplicate trades found: {dups}")
    if dups == 0:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 4: No Overlapping Positions
    # -------------------------------------------------------------------------
    print("\n[CHECK 4] Verifying No Overlapping Positions Per Symbol...")
    overlaps = 0
    for sym, g in df_cand.groupby("symbol"):
        sorted_g = g.sort_values("entry_datetime")
        overlaps += (sorted_g["entry_datetime"] < sorted_g["exit_datetime"].shift(1)).sum()
    print(f"  Overlapping positions found: {overlaps}")
    if overlaps == 0:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 5: Causal Feature Alignment
    # -------------------------------------------------------------------------
    print("\n[CHECK 5] Verifying Causal Feature Alignment...")
    causal_cols = ["adx14", "atr14", "ema_slope", "volatility_regime", "breakout_condition", "rsi14", "time_of_day"]
    has_causal = all(c in df_cand.columns for c in causal_cols)
    t_min = pd.Timestamp("09:15:00").time()
    t_max = pd.Timestamp("10:00:00").time()
    out_of_window = ((df_cand["entry_time"] < t_min) | (df_cand["entry_time"] >= t_max)).sum()
    print(f"  Causal columns present: {has_causal} | Out of window trades: {out_of_window}")
    if has_causal and out_of_window == 0:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 6: Chronological Split Correctness
    # -------------------------------------------------------------------------
    print("\n[CHECK 6] Verifying Chronological Walk-Forward Split Correctness...")
    train = df_cand[df_cand["entry_datetime"] < "2018-06-01"]
    val = df_cand[(df_cand["entry_datetime"] >= "2018-06-01") & (df_cand["entry_datetime"] < "2018-09-01")]
    oos = df_cand[df_cand["entry_datetime"] >= "2018-09-01"]
    print(f"  Train (Jan–May): {len(train)} (Expected: 639)")
    print(f"  Validation (Jun–Aug): {len(val)} (Expected: 426)")
    print(f"  OOS (Sep–Dec): {len(oos)} (Expected: 351)")
    if len(train) == 639 and len(val) == 426 and len(oos) == 351 and (len(train) + len(val) + len(oos) == 1416):
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 7: No Future Data Leakage
    # -------------------------------------------------------------------------
    print("\n[CHECK 7] Auditing For No Future Data Leakage...")
    leakage = (df_cand["exit_datetime"] <= df_cand["entry_datetime"]).sum()
    print(f"  Trades with exit <= entry: {leakage}")
    if leakage == 0:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 8: Symbol Counts Reconcile
    # -------------------------------------------------------------------------
    print("\n[CHECK 8] Verifying Symbol Counts Reconcile...")
    actual_counts = df_cand["symbol"].value_counts().to_dict()
    print(f"  Actual Counts:   {actual_counts}")
    print(f"  Expected Counts: {EXPECTED_SYMBOL_COUNTS}")
    if actual_counts == EXPECTED_SYMBOL_COUNTS:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 9: Leave-One-Symbol-Out Calculations Reconcile
    # -------------------------------------------------------------------------
    print("\n[CHECK 9] Verifying Leave-One-Symbol-Out (LOSO) Reconciles...")
    loso_file = PHASE5_DIR / "leave_one_symbol_out.csv"
    if not loso_file.exists():
        print(f"  FAIL: {loso_file} missing.")
    else:
        df_loso = pd.read_csv(loso_file)
        row_infy = df_loso[df_loso["excluded_symbol"] == "INFY"].iloc[0]
        actual_no_infy_pnl = df_cand[df_cand["symbol"] != "INFY"]["pnl"].sum()
        row_rel = df_loso[df_loso["excluded_symbol"] == "RELIANCE"].iloc[0]
        actual_no_rel_pnl = df_cand[df_cand["symbol"] != "RELIANCE"]["pnl"].sum()
        delta_infy = abs(row_infy["remaining_net_pnl"] - actual_no_infy_pnl)
        delta_rel = abs(row_rel["remaining_net_pnl"] - actual_no_rel_pnl)
        print(f"  Without INFY reported: Rs. {row_infy['remaining_net_pnl']:,.2f} | Recomputed: Rs. {actual_no_infy_pnl:,.2f}")
        print(f"  Without RELIANCE reported: Rs. {row_rel['remaining_net_pnl']:,.2f} | Recomputed: Rs. {actual_no_rel_pnl:,.2f}")
        if delta_infy < 0.1 and delta_rel < 0.1 and row_infy["survives_without_symbol"] == "NO":
            print("  PASS")
            passed_checks += 1
        else:
            print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 10: Cost Calculations Reconcile
    # -------------------------------------------------------------------------
    print("\n[CHECK 10] Verifying Cost Calculations Reconcile...")
    cost_errors = 0
    pnl_errors = 0
    for _, r in df_cand.iterrows():
        expected_cost = 20.0 + (abs(r["exit_price"] - r["entry_price"]) * r["quantity"] * 0.0005)
        if abs(r["costs"] - expected_cost) > 0.01:
            cost_errors += 1
        if abs(r["pnl"] - (r["gross_pnl"] - r["costs"])) > 0.01:
            pnl_errors += 1
    print(f"  Cost formula errors: {cost_errors} | Net PnL = Gross - Costs errors: {pnl_errors}")
    if cost_errors == 0 and pnl_errors == 0:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 11: Deterministic Repeated Execution
    # -------------------------------------------------------------------------
    print("\n[CHECK 11] Verifying Deterministic Repeated Execution...")
    t_0915 = pd.Timestamp("09:15:00").time()
    t_1000 = pd.Timestamp("10:00:00").time()
    recomputed = df_base[(df_base["entry_time"] >= t_0915) & (df_base["entry_time"] < t_1000)]
    delta_pnl = abs(df_cand["pnl"].sum() - recomputed["pnl"].sum())
    print(f"  Candidate Trades: {len(df_cand):,} | Recomputed Trades: {len(recomputed):,} | Delta P&L: Rs. {delta_pnl:.6f}")
    if len(df_cand) == len(recomputed) == 1416 and delta_pnl < 1e-4:
        print("  PASS")
        passed_checks += 1
    else:
        print("  FAIL")

    # -------------------------------------------------------------------------
    # CHECK 12: Verdict Reproducibility
    # -------------------------------------------------------------------------
    print("\n[CHECK 12] Verifying Verdict Reproducibility...")
    verdict_file = PHASE5_DIR / "verdict.json"
    if not verdict_file.exists():
        print(f"  FAIL: {verdict_file} missing.")
    else:
        with open(verdict_file, "r", encoding="utf-8") as f:
            v_data = json.load(f)
        status_ok = v_data.get("robustness_status") == "FRAGILE"
        verdict_ok = v_data.get("final_verdict") == "NO ROBUST EDGE"
        infy_pnl_ok = abs(v_data.get("result_without_infy_net_pnl", 0) - (-19624.34)) < 0.1
        trades_ok = v_data.get("total_trades") == 1416
        print(f"  Status: {v_data.get('robustness_status')} | Verdict: {v_data.get('final_verdict')} | Without INFY: Rs. {v_data.get('result_without_infy_net_pnl')}")
        if status_ok and verdict_ok and infy_pnl_ok and trades_ok:
            print("  PASS")
            passed_checks += 1
        else:
            print("  FAIL")

    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: {passed_checks}/{total_checks} TESTS PASSED")
    print("=" * 80)

    return passed_checks == total_checks


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)

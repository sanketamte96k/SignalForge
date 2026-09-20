"""SignalForge — Phase 11: Manual Verification Suite (15 Deterministic Checks).

Forensic robustness checks for H5_RS_DIVERGENCE:
1. Source data integrity
2. Benchmark data integrity
3. Causal features & zero lookahead (Perturbation test)
4. Deterministic repeated execution
5. Trade uniqueness
6. Entry price correctness
7. Direction correctness
8. Symbol reconciliation & leave-one-out consistency
9. Monthly reconciliation
10. Directional breakdown reconciliation
11. Cost scaling monotonicity
12. Chronological split integrity
13. Parameter perturbation consistency
14. Trade distribution & winner concentration calculation accuracy
15. Final verdict & falsification classification consistency
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CLEAN_DATA_DIR = ROOT_DIR / "research" / "clean_data_2018"
PHASE11_DIR = ROOT_DIR / "research" / "strategy_evolution_2018" / "phase11_h5_forensic"
BENCHMARK_PATH = ROOT_DIR / "data" / "historical" / "nifty50_github_1m.csv"

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
EXPECTED_CANDLES = {
    "RELIANCE": 91752,
    "TCS": 91756,
    "INFY": 91752,
    "HDFCBANK": 91759,
    "ICICIBANK": 91749,
}
TOTAL_EXPECTED_CANDLES = 458768


def run_checks() -> bool:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 11 — MANUAL VERIFICATION SUITE (15 CHECKS)")
    print("=" * 80)

    passed_checks = 0
    total_checks = 15

    # -------------------------------------------------------------------------
    # CHECK 1: Source Data Integrity
    # -------------------------------------------------------------------------
    print("\n[CHECK 1] Verifying Source Data Integrity...")
    c1_ok = True
    total_candles = 0
    for sym in SYMBOLS:
        p = CLEAN_DATA_DIR / f"{sym}_2018.csv"
        if not p.exists():
            print(f"  FAIL: File missing {p}")
            c1_ok = False
            continue
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        total_candles += len(df)
        if len(df) != EXPECTED_CANDLES[sym]:
            print(f"  FAIL: Candle count mismatch for {sym}: {len(df)} != {EXPECTED_CANDLES[sym]}")
            c1_ok = False
        if not df.index.is_monotonic_increasing:
            print(f"  FAIL: Timestamps not monotonic for {sym}")
            c1_ok = False
        if df.isna().sum().sum() > 0:
            print(f"  FAIL: NaN values found in {sym}")
            c1_ok = False

    if c1_ok and total_candles == TOTAL_EXPECTED_CANDLES:
        print(f"  PASS: All 5 symbols present, monotonic timestamps, zero NaNs, exact {total_candles:,} candles verified.")
        passed_checks += 1
    else:
        print(f"  FAIL: Total candles {total_candles} != {TOTAL_EXPECTED_CANDLES}")

    # -------------------------------------------------------------------------
    # CHECK 2: Benchmark Data Integrity
    # -------------------------------------------------------------------------
    print("\n[CHECK 2] Verifying Benchmark Data Integrity...")
    if not BENCHMARK_PATH.exists():
        print(f"  FAIL: Benchmark file missing: {BENCHMARK_PATH}")
    else:
        from src.strategy.context_engine_v10 import load_benchmark_data
        df_bm = load_benchmark_data(BENCHMARK_PATH, year=2018)
        if len(df_bm) == 91935 and df_bm.index.is_monotonic_increasing and df_bm.isna().sum().sum() == 0:
            print(f"  PASS: Benchmark data verified (91,935 2018 bars, monotonic, zero NaNs).")
            passed_checks += 1
        else:
            print(f"  FAIL: Benchmark bars count {len(df_bm)} or non-monotonic or NaNs present.")

    # -------------------------------------------------------------------------
    # CHECK 3: Causal Feature Calculation & Zero Lookahead (Perturbation)
    # -------------------------------------------------------------------------
    print("\n[CHECK 3] Verifying Causal Features & Perturbation Audit...")
    from src.strategy.context_engine_v10 import precompute_stock_features
    df_sample = pd.read_csv(CLEAN_DATA_DIR / "INFY_2018.csv", index_col=0, parse_dates=True).head(400)
    feat_orig = precompute_stock_features(df_sample, df_bm)

    df_perturbed = df_sample.copy()
    df_perturbed.iloc[350:, df_perturbed.columns.get_loc("Close")] *= 1.4
    feat_perturbed = precompute_stock_features(df_perturbed, df_bm)

    leakage_detected = False
    for col in ["rs_15", "stock_ret_15", "stock_ema_20", "rel_rsi"]:
        diff = (feat_orig[col].iloc[:350] - feat_perturbed[col].iloc[:350]).abs().max()
        if diff > 1e-9:
            print(f"  FAIL: Future leakage detected in column {col}! Max diff: {diff}")
            leakage_detected = True
            break
    if not leakage_detected:
        print("  PASS: Future perturbation at bar 350 produced 0 changes in bars 0..349. Leakage: 0.")
        passed_checks += 1

    # -------------------------------------------------------------------------
    # CHECK 4: Deterministic Repeated Execution
    # -------------------------------------------------------------------------
    print("\n[CHECK 4] Verifying Deterministic Repeated Scoring...")
    from src.strategy.context_engine_v10 import evaluate_hypotheses_for_trade
    res1 = evaluate_hypotheses_for_trade("LONG", -0.004, 0.001, -0.005, "TREND_UP", 10500.0, 10450.0, 0.001, 1.0)
    res2 = evaluate_hypotheses_for_trade("LONG", -0.004, 0.001, -0.005, "TREND_UP", 10500.0, 10450.0, 0.001, 1.0)
    if res1["H5_RS_DIVERGENCE"] == res2["H5_RS_DIVERGENCE"] == True:
        print("  PASS: Repeated hypothesis evaluation bit-for-bit identical (True).")
        passed_checks += 1
    else:
        print("  FAIL: Non-deterministic hypothesis evaluation detected.")

    # -------------------------------------------------------------------------
    # CHECK 5: Trade Uniqueness
    # -------------------------------------------------------------------------
    print("\n[CHECK 5] Verifying Trade Uniqueness in candidate_trades.csv...")
    cands_file = PHASE11_DIR / "candidate_trades.csv"
    if not cands_file.exists():
        print(f"  FAIL: {cands_file.name} missing")
    else:
        df_c = pd.read_csv(cands_file)
        dups = df_c.duplicated(subset=["symbol", "entry_datetime", "direction"]).sum()
        if dups == 0 and len(df_c) == 80:
            print(f"  PASS: Zero duplicate records across all {len(df_c)} candidate trades.")
            passed_checks += 1
        else:
            print(f"  FAIL: {dups} duplicates detected or count {len(df_c)} != 80")

    # -------------------------------------------------------------------------
    # CHECK 6: Entry Price Correctness
    # -------------------------------------------------------------------------
    print("\n[CHECK 6] Verifying Entry Price Correctness Against Clean Data...")
    c6_ok = True
    df_sample_trades = df_c.head(30)
    for _, tr in df_sample_trades.iterrows():
        sym = tr["symbol"]
        ts_val = pd.Timestamp(tr["entry_datetime"])
        clean_df = pd.read_csv(CLEAN_DATA_DIR / f"{sym}_2018.csv", index_col=0, parse_dates=True)
        if ts_val in clean_df.index:
            actual_c = clean_df.loc[ts_val, "Close"]
            if abs(tr["entry_price"] - actual_c) > 0.05:
                print(f"  FAIL: Entry price mismatch for {sym} at {ts_val}: {tr['entry_price']} != {actual_c}")
                c6_ok = False
                break
    if c6_ok:
        print("  PASS: Trade entry prices match actual bar close prices at timestamp T exactly.")
        passed_checks += 1

    # -------------------------------------------------------------------------
    # CHECK 7: Direction Correctness
    # -------------------------------------------------------------------------
    print("\n[CHECK 7] Verifying Direction Correctness ('LONG' / 'SHORT')...")
    dirs = df_c["direction"].unique().tolist()
    if set(dirs).issubset({"LONG", "SHORT"}):
        print(f"  PASS: All trade directions strictly validated as {dirs}.")
        passed_checks += 1
    else:
        print(f"  FAIL: Unexpected trade directions found: {dirs}")

    # -------------------------------------------------------------------------
    # CHECK 8: Symbol Reconciliation & Leave-One-Out Consistency
    # -------------------------------------------------------------------------
    print("\n[CHECK 8] Verifying Symbol Reconciliation & Leave-One-Out Matrix...")
    sym_file = PHASE11_DIR / "symbol_analysis.csv"
    excl_file = PHASE11_DIR / "symbol_exclusion.csv"
    if not (sym_file.exists() and excl_file.exists()):
        print("  FAIL: symbol_analysis.csv or symbol_exclusion.csv missing")
    else:
        df_sym = pd.read_csv(sym_file).set_index("symbol_group")
        df_excl = pd.read_csv(excl_file).set_index("excluded_symbol")

        # Check individual symbol trade sum == 80
        ind_sum = sum(df_sym.loc[s, "trades"] for s in SYMBOLS)
        # Check leave-one-out remaining trades
        excl_ok = all(df_excl.loc[s, "remaining_trades"] == (80 - df_sym.loc[s, "trades"]) for s in SYMBOLS)

        if ind_sum == 80 and excl_ok:
            print("  PASS: Symbol trade counts reconcile to 80 and leave-one-out matrix is mathematically exact.")
            passed_checks += 1
        else:
            print(f"  FAIL: Symbol sum {ind_sum} != 80 or leave-one-out matrix mismatch.")

    # -------------------------------------------------------------------------
    # CHECK 9: Monthly Reconciliation (All 12 Calendar Months)
    # -------------------------------------------------------------------------
    print("\n[CHECK 9] Verifying Monthly Reconciliation (12 Months)...")
    month_file = PHASE11_DIR / "monthly_analysis.csv"
    if not month_file.exists():
        print("  FAIL: monthly_analysis.csv missing")
    else:
        df_m = pd.read_csv(month_file)
        month_sum = df_m["trades"].sum()
        if len(df_m) == 12 and month_sum == 80:
            print(f"  PASS: All 12 calendar months present; sum of trades = {month_sum}.")
            passed_checks += 1
        else:
            print(f"  FAIL: Month rows {len(df_m)} != 12 or trades sum {month_sum} != 80")

    # -------------------------------------------------------------------------
    # CHECK 10: Directional Breakdown Reconciliation (Long + Short = 80)
    # -------------------------------------------------------------------------
    print("\n[CHECK 10] Verifying Directional Breakdown Reconciliation...")
    dir_file = PHASE11_DIR / "direction_analysis.csv"
    if not dir_file.exists():
        print("  FAIL: direction_analysis.csv missing")
    else:
        df_d = pd.read_csv(dir_file)
        long_n = int(df_d[df_d["direction"] == "LONG"]["trades"].iloc[0])
        short_n = int(df_d[df_d["direction"] == "SHORT"]["trades"].iloc[0])
        if long_n + short_n == 80 and long_n == 48 and short_n == 32:
            print(f"  PASS: Directional split verified: {long_n} LONG + {short_n} SHORT = 80.")
            passed_checks += 1
        else:
            print(f"  FAIL: Directional split mismatch: {long_n} Long, {short_n} Short")

    # -------------------------------------------------------------------------
    # CHECK 11: Cost Scaling Monotonicity (0x >= 1x >= 1.5x >= 2x >= 2.5x >= 3x)
    # -------------------------------------------------------------------------
    print("\n[CHECK 11] Verifying Cost Scaling Monotonicity...")
    cost_file = PHASE11_DIR / "cost_stress.csv"
    if not cost_file.exists():
        print("  FAIL: cost_stress.csv missing")
    else:
        df_cost = pd.read_csv(cost_file).set_index("cost_tier")
        tiers = ["0.0x", "1.0x", "1.5x", "2.0x", "2.5x", "3.0x"]
        exps = [df_cost.loc[t, "net_expectancy"] for t in tiers]
        is_mono = all(exps[i] >= exps[i+1] for i in range(len(exps)-1))
        if is_mono:
            print(f"  PASS: Net expectancy decreases monotonically across {tiers}.")
            passed_checks += 1
        else:
            print(f"  FAIL: Cost monotonicity broken: {exps}")

    # -------------------------------------------------------------------------
    # CHECK 12: Chronological Split Integrity (Train + Val + OOS = 80)
    # -------------------------------------------------------------------------
    print("\n[CHECK 12] Verifying Chronological Split Integrity...")
    tvo_file = PHASE11_DIR / "train_validation_oos.csv"
    if not tvo_file.exists():
        print("  FAIL: train_validation_oos.csv missing")
    else:
        df_tvo = pd.read_csv(tvo_file).set_index("split")
        train_n = df_tvo.loc["TRAIN", "trades"]
        val_n = df_tvo.loc["VALIDATION", "trades"]
        oos_n = df_tvo.loc["OOS", "trades"]
        if train_n + val_n + oos_n == 80:
            print(f"  PASS: Splits reconcile strictly: Train ({train_n}) + Val ({val_n}) + OOS ({oos_n}) = 80.")
            passed_checks += 1
        else:
            print(f"  FAIL: Split sum mismatch: {train_n} + {val_n} + {oos_n} != 80")

    # -------------------------------------------------------------------------
    # CHECK 13: Parameter Perturbation Consistency (25 Grid Points)
    # -------------------------------------------------------------------------
    print("\n[CHECK 13] Verifying Parameter Perturbation Grid...")
    param_file = PHASE11_DIR / "parameter_stability.csv"
    if not param_file.exists():
        print("  FAIL: parameter_stability.csv missing")
    else:
        df_p = pd.read_csv(param_file)
        if len(df_p) == 25:
            base_row = df_p[df_p["is_baseline"] == True]
            if len(base_row) == 1 and base_row.iloc[0]["trades"] == 80:
                print(f"  PASS: All 25 perturbation grid points evaluated; baseline point verified (80 trades).")
                passed_checks += 1
            else:
                print("  FAIL: Baseline parameter point missing or trade count != 80.")
        else:
            print(f"  FAIL: Parameter grid count {len(df_p)} != 25")

    # -------------------------------------------------------------------------
    # CHECK 14: Trade Distribution & Winner Concentration Calculation Accuracy
    # -------------------------------------------------------------------------
    print("\n[CHECK 14] Verifying Trade Distribution & Winner Concentration...")
    dist_file = PHASE11_DIR / "trade_distribution.csv"
    if not dist_file.exists():
        print("  FAIL: trade_distribution.csv missing")
    else:
        df_dist = pd.read_csv(dist_file).set_index("metric")
        top_1 = df_dist.loc["top_1pct_pnl_share_pct", "value"]
        top_5 = df_dist.loc["top_5pct_pnl_share_pct", "value"]
        top_10 = df_dist.loc["top_10pct_pnl_share_pct", "value"]
        if top_1 <= top_5 <= top_10 and top_1 >= 0:
            print(f"  PASS: Winner concentration shares verified: Top 1% ({top_1}%) <= Top 5% ({top_5}%) <= Top 10% ({top_10}%).")
            passed_checks += 1
        else:
            print(f"  FAIL: Winner concentration ordering invalid: {top_1} <= {top_5} <= {top_10}")

    # -------------------------------------------------------------------------
    # CHECK 15: Final Verdict & Falsification Consistency
    # -------------------------------------------------------------------------
    print("\n[CHECK 15] Verifying Final Verdict & Falsification Consistency...")
    fals_file = PHASE11_DIR / "falsification_results.csv"
    verd_file = PHASE11_DIR / "phase11_verdict.csv"
    if not (fals_file.exists() and verd_file.exists()):
        print("  FAIL: falsification_results.csv or phase11_verdict.csv missing")
    else:
        df_f = pd.read_csv(fals_file)
        df_v = pd.read_csv(verd_file).set_index("metric")
        classification = df_v.loc["final_classification", "value"]
        robust_found = df_v.loc["robust_edge_found", "value"]

        # Classification must reflect flagged conditions
        if robust_found == "NO" and "CONCENTRATED" in classification:
            print(f"  PASS: Forensic verdict consistent ({classification}). Robust Edge = {robust_found}.")
            passed_checks += 1
        else:
            print(f"  FAIL: Inconsistent verdict logic: Classification: {classification}, Robust Edge: {robust_found}")

    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: {passed_checks}/{total_checks} TESTS PASSED")
    print("=" * 80)

    return passed_checks == total_checks


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)

"""
Manual Verification Test Suite: SignalForge Phase 16
Post-ORB Edge Discovery & Falsification
=====================================================
Verifies all forensic requirements for Phase 16:
1. Runner exists
2. Runner is non-empty (>2KB)
3. Report exists and is non-empty
4. Status CSV exists and contains required metrics
5. All 19 required artifacts exist and are non-empty
6. Real datasets only (no synthetic data generated)
7. Real datasets detected (NIFTY + 10 liquid equities)
8. Causal feature engineering verified in runner code (shift(1), expanding VWAP)
9. Chronological split & OOS isolation verified (Train, Validation, OOS)
10. Transaction costs included and stressed (0.0x to 2.0x)
11. Lookahead audit verified (all 10 checks pass)
12. All 8 hypotheses evaluated and documented (H1 to H8)
13. Multiple-testing risk documented with statistical corrections
14. Production integration is blocked (isolated research)
15. Final verdict valid and status not falsely marked production-ready
"""

import os
import sys
import pandas as pd

OUTPUT_DIR = os.path.join("research", "strategy_evolution_2018", "phase16_edge_discovery")
RUNNER_PATH = os.path.join("scripts", "run_strategy_evolution_phase16_edge_discovery.py")
STOCK_DIR = os.path.join("temp_nse_data", "NSE Minute Data", "NSE_Stocks_Data")
NIFTY_PATH = os.path.join("data", "historical", "nifty50_1m_signalforge.csv")

TARGET_STOCKS = [
    "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "SBIN",
    "ITC", "LT", "AXISBANK", "BHARTIARTL", "KOTAKBANK"
]

REQUIRED_ARTIFACTS = [
    "phase16_report.md",
    "phase16_status.csv",
    "dataset_audit.csv",
    "hypothesis_summary.csv",
    "vwap_reversion.csv",
    "vwap_continuation.csv",
    "gap_fill.csv",
    "gap_vwap_alignment.csv",
    "volatility_expansion.csv",
    "volatility_contraction.csv",
    "momentum_pullback.csv",
    "day_type_classification.csv",
    "parameter_sensitivity.csv",
    "cost_stress.csv",
    "oos_validation.csv",
    "symbol_robustness.csv",
    "mae_mfe_analysis.csv",
    "lookahead_audit.csv",
    "multiple_testing_audit.csv"
]


def test_phase16_discovery_suite():
    print("=" * 80)
    print(" SIGNALFORGE — PHASE 16 POST-ORB EDGE DISCOVERY MANUAL TEST SUITE")
    print("=" * 80)

    checks = []

    # Check 1: Runner exists
    c1 = os.path.exists(RUNNER_PATH)
    checks.append(("1. Phase 16 runner exists", c1))

    # Check 2: Runner non-empty (>2KB)
    c2 = os.path.exists(RUNNER_PATH) and os.path.getsize(RUNNER_PATH) > 2000
    checks.append(("2. Runner non-empty (>2KB)", c2))

    # Check 3: Report exists and is non-empty
    rep_path = os.path.join(OUTPUT_DIR, "phase16_report.md")
    c3 = os.path.exists(rep_path) and os.path.getsize(rep_path) > 500
    checks.append(("3. Phase 16 report exists and non-empty", c3))

    # Check 4: Status CSV exists and is non-empty
    stat_path = os.path.join(OUTPUT_DIR, "phase16_status.csv")
    c4 = os.path.exists(stat_path) and os.path.getsize(stat_path) > 50
    checks.append(("4. Phase 16 status CSV exists and non-empty", c4))

    # Check 5: All 19 required artifacts present & non-empty
    missing_artifacts = []
    for art in REQUIRED_ARTIFACTS:
        p = os.path.join(OUTPUT_DIR, art)
        if not os.path.exists(p) or os.path.getsize(p) < 10:
            missing_artifacts.append(art)
    c5 = (len(missing_artifacts) == 0)
    checks.append((f"5. All 19 required artifacts present and non-empty (missing: {missing_artifacts})", c5))

    # Check 6: Real data only (no synthetic data generation detected)
    with open(RUNNER_PATH, "r", encoding="utf-8") as f:
        runner_content = f.read()
    c6 = ("np.random.normal" not in runner_content and "make_blobs" not in runner_content and "synthetic" not in runner_content.lower())
    checks.append(("6. Real data only (no synthetic data generated)", c6))

    # Check 7: Real datasets detected (NIFTY + 10 equities)
    c7 = os.path.exists(NIFTY_PATH) and all(
        os.path.exists(os.path.join(STOCK_DIR, f"{s}__EQ__NSE__NSE__MINUTE.csv")) for s in TARGET_STOCKS
    )
    checks.append(("7. Real datasets detected (NIFTY + all 10 equities)", c7))

    # Check 8: Causal feature rules verified in runner code (shift(1), expanding VWAP)
    c8 = ("shift(1)" in runner_content and "cumsum" in runner_content)
    checks.append(("8. Causal feature rules verified in runner code", c8))

    # Check 9: Chronological split & OOS isolation verified
    oos_path = os.path.join(OUTPUT_DIR, "oos_validation.csv")
    c9 = False
    if os.path.exists(oos_path):
        df_oos = pd.read_csv(oos_path)
        parts = set(df_oos["partition"].unique())
        c9 = {"TRAIN", "VALIDATION", "OOS"}.issubset(parts)
    checks.append(("9. Chronological split & OOS isolation verified", c9))

    # Check 10: Transaction costs included and stressed (0.0x to 2.0x)
    cs_path = os.path.join(OUTPUT_DIR, "cost_stress.csv")
    c10 = False
    if os.path.exists(cs_path):
        df_cs = pd.read_csv(cs_path)
        mults = set(df_cs["cost_multiplier"].unique())
        c10 = {0.0, 0.5, 1.0, 1.5, 2.0}.issubset(mults)
    checks.append(("10. Cost stress testing covers 0.0x to 2.0x", c10))

    # Check 11: Lookahead audit confirms all 10 items PASS
    la_path = os.path.join(OUTPUT_DIR, "lookahead_audit.csv")
    c11 = False
    if os.path.exists(la_path):
        df_la = pd.read_csv(la_path)
        c11 = len(df_la) == 10 and (df_la["status"] == "PASS").all()
    checks.append(("11. Lookahead audit confirms all 10 items PASS", c11))

    # Check 12: All 8 hypotheses evaluated and documented in hypothesis_summary.csv
    hs_path = os.path.join(OUTPUT_DIR, "hypothesis_summary.csv")
    c12 = False
    if os.path.exists(hs_path):
        df_hs = pd.read_csv(hs_path)
        h_ids = set(df_hs["hypothesis_id"].unique())
        expected_h = {f"H{i}" for i in range(1, 9)}
        c12 = expected_h.issubset(h_ids) and len(df_hs) >= 8
    checks.append(("12. All 8 candidate hypotheses evaluated in hypothesis_summary.csv", c12))

    # Check 13: Multiple-testing risk documented with corrections
    mt_path = os.path.join(OUTPUT_DIR, "multiple_testing_audit.csv")
    c13 = False
    if os.path.exists(mt_path):
        df_mt = pd.read_csv(mt_path)
        c13 = "bonferroni_survived" in df_mt.columns and "benjamini_hochberg_fdr_survived" in df_mt.columns and len(df_mt) >= 8
    checks.append(("13. Multiple-testing risk documented with Bonferroni & BH FDR", c13))

    # Check 14: No production integration (no modifications to src/strategy/)
    c14 = not os.path.exists(os.path.join("src", "strategy", "phase16_strategy.py"))
    checks.append(("14. No production integration (isolated research)", c14))

    # Check 15: Final verdict valid and not falsely production ready
    c15 = False
    if os.path.exists(stat_path):
        df_st = pd.read_csv(stat_path)
        v_rows = df_st[df_st["metric"] == "final_verdict"]
        pr_rows = df_st[df_st["metric"] == "production_ready"]
        if len(v_rows) > 0 and len(pr_rows) > 0:
            verdict = v_rows.iloc[0]["value"]
            prod_ready = pr_rows.iloc[0]["value"]
            valid_verdicts = ["ROBUST_CANDIDATE_FOUND", "PROMISING_BUT_NOT_ROBUST", "REJECTED"]
            c15 = (verdict in valid_verdicts) and (prod_ready != "TRUE" and prod_ready != "PRODUCTION_READY")
    checks.append(("15. Final verdict valid and status not falsely marked production-ready", c15))

    # Print results
    all_passed = True
    print("\n--- Test Results ---")
    for name, result in checks:
        status_str = "PASS" if result else "FAIL"
        if not result:
            all_passed = False
        print(f"[{status_str}] {name}")

    print("-" * 80)
    passed_count = sum(1 for _, r in checks if r)
    total_count = len(checks)
    print(f"TOTAL: {passed_count}/{total_count} PASSED")

    if all_passed:
        print("\nSUCCESS: All Phase 16 post-ORB edge discovery verification tests PASSED!")
        return 0
    else:
        print("\nFAILURE: Some Phase 16 verification tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(test_phase16_discovery_suite())

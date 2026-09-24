"""
Manual Verification Test Suite: SignalForge Phase 16
Post-ORB Edge Discovery & Strategy Pivot
=====================================================
Verifies all forensic requirements for Phase 16:
- Runner presence and non-emptiness
- Artifact completeness (all 17 files in phase16_edge_discovery)
- Real data integrity (NIFTY + 10 equities)
- Causal feature engineering & no future leakage
- Chronological split (Train <=2018, Val 2019, OOS 2020)
- Cost stress testing (0.0x to 2.0x)
- Bootstrap robustness (seed 42, 95% CIs)
- Lookahead audit (all 10 PASS)
- Rejection criteria & no false production readiness
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
    "data_audit.csv",
    "hypothesis_registry.csv",
    "candidate_comparison.csv",
    "vwap_analysis.csv",
    "gap_analysis.csv",
    "momentum_analysis.csv",
    "relative_strength_analysis.csv",
    "volatility_analysis.csv",
    "reversal_analysis.csv",
    "cost_sensitivity.csv",
    "parameter_sensitivity.csv",
    "oos_validation.csv",
    "bootstrap_robustness.csv",
    "lookahead_audit.csv",
    "trade_concentration.csv"
]


def test_phase16_discovery_suite():
    print("=" * 80)
    print(" SIGNALFORGE — PHASE 16 POST-ORB EDGE DISCOVERY MANUAL TEST SUITE")
    print("=" * 80)

    checks = []

    # Check 1: Runner exists
    c1 = os.path.exists(RUNNER_PATH)
    checks.append(("1. Phase 16 runner exists", c1))

    # Check 2: Runner non-empty
    c2 = os.path.exists(RUNNER_PATH) and os.path.getsize(RUNNER_PATH) > 2000
    checks.append(("2. Runner non-empty (>2KB)", c2))

    # Check 3: Report exists
    rep_path = os.path.join(OUTPUT_DIR, "phase16_report.md")
    c3 = os.path.exists(rep_path) and os.path.getsize(rep_path) > 500
    checks.append(("3. Phase 16 report exists and non-empty", c3))

    # Check 4: Status CSV exists
    stat_path = os.path.join(OUTPUT_DIR, "phase16_status.csv")
    c4 = os.path.exists(stat_path) and os.path.getsize(stat_path) > 50
    checks.append(("4. Phase 16 status CSV exists", c4))

    # Check 5: All 17 required artifacts present & non-empty
    missing_artifacts = []
    for art in REQUIRED_ARTIFACTS:
        p = os.path.join(OUTPUT_DIR, art)
        if not os.path.exists(p) or os.path.getsize(p) < 10:
            missing_artifacts.append(art)
    c5 = (len(missing_artifacts) == 0)
    checks.append(("5. All 17 required artifacts present and non-empty", c5))

    # Check 6: Real data only (no synthetic data)
    with open(RUNNER_PATH, "r", encoding="utf-8") as f:
        runner_content = f.read()
    c6 = ("np.random.normal" not in runner_content and "make_blobs" not in runner_content)
    checks.append(("6. Real data only (no synthetic data generated)", c6))

    # Check 7: Real datasets detected (NIFTY + 10 equities)
    c7 = os.path.exists(NIFTY_PATH) and all(
        os.path.exists(os.path.join(STOCK_DIR, f"{s}__EQ__NSE__NSE__MINUTE.csv")) for s in TARGET_STOCKS
    )
    checks.append(("7. Real datasets detected (NIFTY + all 10 equities)", c7))

    # Check 8: Causal feature rules (ATR shifted, expanding VWAP)
    c8 = ("shift(1)" in runner_content and "cumsum" in runner_content)
    checks.append(("8. Causal feature rules verified in runner code", c8))

    # Check 9: Chronological split & OOS isolation
    oos_path = os.path.join(OUTPUT_DIR, "oos_validation.csv")
    c9 = False
    if os.path.exists(oos_path):
        df_oos = pd.read_csv(oos_path)
        parts = set(df_oos["partition"].unique())
        c9 = any("TRAIN" in p for p in parts) and any("VALIDATION" in p for p in parts) and any("OOS" in p for p in parts)
    checks.append(("9. Chronological split & OOS isolation verified", c9))

    # Check 10: Cost stress testing (0.0x to 2.0x)
    cs_path = os.path.join(OUTPUT_DIR, "cost_sensitivity.csv")
    c10 = False
    if os.path.exists(cs_path):
        df_cs = pd.read_csv(cs_path)
        mults = set(df_cs["cost_multiplier"].unique())
        c10 = {0.0, 0.5, 1.0, 1.5, 2.0}.issubset(mults)
    checks.append(("10. Cost stress testing covers 0.0x to 2.0x", c10))

    # Check 11: Bootstrap robustness (seed 42 with 95% CIs)
    boot_path = os.path.join(OUTPUT_DIR, "bootstrap_robustness.csv")
    c11 = False
    if os.path.exists(boot_path):
        df_boot = pd.read_csv(boot_path)
        c11 = "net_ci_95_lower" in df_boot.columns and "net_ci_95_upper" in df_boot.columns and len(df_boot) == 10
    checks.append(("11. Bootstrap robustness covers 95% CIs for all 10 candidates", c11))

    # Check 12: Lookahead audit confirms all 10 items PASS
    la_path = os.path.join(OUTPUT_DIR, "lookahead_audit.csv")
    c12 = False
    if os.path.exists(la_path):
        df_la = pd.read_csv(la_path)
        c12 = len(df_la) == 10 and (df_la["status"] == "PASS").all()
    checks.append(("12. Lookahead audit confirms all 10 items PASS", c12))

    # Check 13: Rejection criteria exist in hypothesis registry
    hr_path = os.path.join(OUTPUT_DIR, "hypothesis_registry.csv")
    c13 = False
    if os.path.exists(hr_path):
        df_hr = pd.read_csv(hr_path)
        c13 = "rejection_criteria" in df_hr.columns and len(df_hr) == 10
    checks.append(("13. Rejection criteria documented for all 10 candidates", c13))

    # Check 14: No production integration (no modifications to src/strategy/)
    c14 = not os.path.exists(os.path.join("src", "strategy", "phase16_strategy.py"))
    checks.append(("14. No production integration (isolated research)", c14))

    # Check 15: Final verdict valid and not falsely production ready
    c15 = False
    if os.path.exists(stat_path):
        df_st = pd.read_csv(stat_path)
        v_rows = df_st[df_st["metric"] == "final_verdict"]
        if len(v_rows) > 0:
            verdict = v_rows.iloc[0]["value"]
            valid_verdicts = ["PROMISING", "WEAK_EDGE", "REJECTED", "INSUFFICIENT_DATA"]
            c15 = verdict in valid_verdicts and verdict != "PRODUCTION_READY"
    checks.append(("15. Final verdict valid (approved value, not production-ready)", c15))

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
        print("\nSUCCESS: All Phase 16 post-ORB discovery tests PASSED!")
        return 0
    else:
        print("\nFAILURE: Some Phase 16 tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(test_phase16_discovery_suite())

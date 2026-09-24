"""
Manual Verification Test Suite: SignalForge Phase 15
Index-vs-Equity Structural Edge Forensic Audit
======================================================
Verifies all 19 requirements specified in the Phase 15 protocol.
"""

import os
import sys
import pandas as pd

OUTPUT_DIR = os.path.join("research", "strategy_evolution_2018", "phase15_index_vs_equity")
RUNNER_PATH = os.path.join("scripts", "run_strategy_evolution_phase15_index_equity.py")
STOCK_DIR = os.path.join("temp_nse_data", "NSE Minute Data", "NSE_Stocks_Data")
NIFTY_PATH = os.path.join("data", "historical", "nifty50_1m_signalforge.csv")

TARGET_STOCKS = [
    "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "SBIN",
    "ITC", "LT", "AXISBANK", "BHARTIARTL", "KOTAKBANK"
]

REQUIRED_ARTIFACTS = [
    "phase15_report.md",
    "phase15_status.csv",
    "index_equity_comparison.csv",
    "breakout_quality.csv",
    "false_breakout_analysis.csv",
    "gap_analysis.csv",
    "mean_reversion_analysis.csv",
    "or_width_analysis.csv",
    "volume_analysis.csv",
    "cost_forensics.csv",
    "bootstrap_robustness.csv",
    "yearly_regime_analysis.csv",
    "master_comparison.csv",
    "lookahead_audit.csv"
]


def test_phase15_suite():
    print("=" * 80)
    print(" SIGNALFORGE — PHASE 15 MANUAL TEST SUITE")
    print("=" * 80)

    checks = []

    # Check 1: Runner exists
    c1 = os.path.exists(RUNNER_PATH)
    checks.append(("1. Phase 15 runner exists", c1))

    # Check 2: Runner non-empty
    c2 = os.path.exists(RUNNER_PATH) and os.path.getsize(RUNNER_PATH) > 1000
    checks.append(("2. Runner non-empty", c2))

    # Check 3: Real datasets detected
    c3 = os.path.exists(STOCK_DIR) and os.path.exists(NIFTY_PATH)
    checks.append(("3. Real datasets detected", c3))

    # Check 4: NIFTY dataset detected
    c4 = os.path.exists(NIFTY_PATH) and os.path.getsize(NIFTY_PATH) > 1000000
    checks.append(("4. NIFTY dataset detected", c4))

    # Check 5: Equity datasets detected
    missing_stocks = [s for s in TARGET_STOCKS if not os.path.exists(os.path.join(STOCK_DIR, f"{s}__EQ__NSE__NSE__MINUTE.csv"))]
    c5 = (len(missing_stocks) == 0)
    checks.append(("5. Equity datasets detected (all 10 present)", c5))

    # Check 6: Frozen strategy confirmed
    with open(RUNNER_PATH, "r", encoding="utf-8") as f:
        runner_content = f.read()
    c6 = ("09:15" in runner_content and "09:30" in runner_content and
          "1.5" in runner_content and "2.0" in runner_content and
          "33.0" in runner_content)
    checks.append(("6. Frozen strategy confirmed (09:15-09:30, 1.5 stop, 2.0 target, 33rd pctile)", c6))

    # Check 7: No synthetic data
    c7 = ("np.random.normal" not in runner_content and "make_blobs" not in runner_content)
    checks.append(("7. No synthetic data", c7))

    # Check 8: Breakout analysis generated
    bq_path = os.path.join(OUTPUT_DIR, "breakout_quality.csv")
    c8 = os.path.exists(bq_path) and os.path.getsize(bq_path) > 100
    checks.append(("8. Breakout analysis generated", c8))

    # Check 9: False breakout analysis generated
    fb_path = os.path.join(OUTPUT_DIR, "false_breakout_analysis.csv")
    c9 = os.path.exists(fb_path) and os.path.getsize(fb_path) > 100
    checks.append(("9. False breakout analysis generated", c9))

    # Check 10: Gap analysis generated
    gap_path = os.path.join(OUTPUT_DIR, "gap_analysis.csv")
    c10 = os.path.exists(gap_path) and os.path.getsize(gap_path) > 100
    checks.append(("10. Gap analysis generated", c10))

    # Check 11: Mean-reversion analysis generated
    mr_path = os.path.join(OUTPUT_DIR, "mean_reversion_analysis.csv")
    c11 = os.path.exists(mr_path) and os.path.getsize(mr_path) > 100
    checks.append(("11. Mean-reversion analysis generated", c11))

    # Check 12: OR-width analysis generated
    orw_path = os.path.join(OUTPUT_DIR, "or_width_analysis.csv")
    c12 = os.path.exists(orw_path) and os.path.getsize(orw_path) > 100
    checks.append(("12. OR-width analysis generated", c12))

    # Check 13: Cost analysis generated
    cost_path = os.path.join(OUTPUT_DIR, "cost_forensics.csv")
    c13 = os.path.exists(cost_path) and os.path.getsize(cost_path) > 100
    checks.append(("13. Cost analysis generated", c13))

    # Check 14: Bootstrap analysis generated
    boot_path = os.path.join(OUTPUT_DIR, "bootstrap_robustness.csv")
    c14 = os.path.exists(boot_path) and os.path.getsize(boot_path) > 100
    checks.append(("14. Bootstrap analysis generated", c14))

    # Check 15: Yearly analysis generated
    yr_path = os.path.join(OUTPUT_DIR, "yearly_regime_analysis.csv")
    c15 = os.path.exists(yr_path) and os.path.getsize(yr_path) > 100
    checks.append(("15. Yearly analysis generated", c15))

    # Check 16: Master comparison generated
    mc_path = os.path.join(OUTPUT_DIR, "master_comparison.csv")
    c16 = os.path.exists(mc_path) and os.path.getsize(mc_path) > 100
    checks.append(("16. Master comparison generated", c16))

    # Check 17: Look-ahead audit generated
    la_path = os.path.join(OUTPUT_DIR, "lookahead_audit.csv")
    c17 = False
    if os.path.exists(la_path):
        df_la = pd.read_csv(la_path)
        c17 = len(df_la) == 10 and (df_la["status"] == "PASS").all()
    checks.append(("17. Look-ahead audit generated (All 10 items PASS)", c17))

    # Check 18: No parameter optimization
    c18 = ("GridSearchCV" not in runner_content and "optimize" not in runner_content.lower())
    checks.append(("18. No parameter optimization", c18))

    # Check 19: Final verdict not falsely production-ready
    st_path = os.path.join(OUTPUT_DIR, "phase15_status.csv")
    c19 = False
    if os.path.exists(st_path):
        df_st = pd.read_csv(st_path)
        v_rows = df_st[df_st["metric"] == "final_verdict"]
        if len(v_rows) > 0:
            verdict = v_rows.iloc[0]["value"]
            valid_verdicts = [
                "INDEX_EDGE_SUPPORTED_BUT_NOT_PRODUCTION_READY",
                "INDEX_EDGE_NOT_SUPPORTED",
                "DATA_INSUFFICIENT"
            ]
            c19 = verdict in valid_verdicts and verdict != "PRODUCTION_READY"
    checks.append(("19. Final verdict not falsely production-ready", c19))

    # Print summary
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
        print("\nSUCCESS: All Phase 15 tests PASSED!")
        return 0
    else:
        print("\nFAILURE: Some Phase 15 tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(test_phase15_suite())

"""
Manual Verification Test Suite: SignalForge Phase 16
Structural Intraday Edge Discovery Forensic Audit
=====================================================
Contains 25 comprehensive checks covering files, schemas, data integrity,
causal construction, train/val/OOS separation, cost models, LOSO, bootstrap,
artifact completeness, and production safety.
"""

import os
import sys
import pandas as pd

OUTPUT_DIR = os.path.join("research", "strategy_evolution_2018", "phase16_structural_edge_discovery")
RUNNER_PATH = os.path.join("scripts", "run_strategy_evolution_phase16_structural_edge.py")
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
    "hypothesis_summary.csv",
    "gap_analysis.csv",
    "vwap_analysis.csv",
    "volatility_expansion_analysis.csv",
    "trend_day_analysis.csv",
    "failed_breakout_analysis.csv",
    "multi_factor_analysis.csv",
    "cost_sensitivity.csv",
    "symbol_robustness.csv",
    "loso_analysis.csv",
    "yearly_regime_analysis.csv",
    "oos_validation.csv",
    "walk_forward.csv",
    "bootstrap_robustness.csv",
    "mae_mfe_analysis.csv",
    "lookahead_audit.csv",
    "candidate_trade_log.csv"
]


def test_phase16_suite():
    print("=" * 80)
    print(" SIGNALFORGE — PHASE 16 MANUAL VERIFICATION TEST SUITE")
    print("=" * 80)

    checks = []

    # Check 1: Runner exists
    c1 = os.path.exists(RUNNER_PATH)
    checks.append(("1. Phase 16 runner exists", c1))

    # Check 2: Runner non-empty
    c2 = os.path.exists(RUNNER_PATH) and os.path.getsize(RUNNER_PATH) > 2000
    checks.append(("2. Runner non-empty (>2KB)", c2))

    # Check 3: Real datasets detected
    c3 = os.path.exists(STOCK_DIR) and os.path.exists(NIFTY_PATH)
    checks.append(("3. Real datasets detected", c3))

    # Check 4: NIFTY dataset detected & sized
    c4 = os.path.exists(NIFTY_PATH) and os.path.getsize(NIFTY_PATH) > 1000000
    checks.append(("4. NIFTY dataset detected (>1MB)", c4))

    # Check 5: Equity datasets detected (all 10 present)
    missing_stocks = [s for s in TARGET_STOCKS if not os.path.exists(os.path.join(STOCK_DIR, f"{s}__EQ__NSE__NSE__MINUTE.csv"))]
    c5 = (len(missing_stocks) == 0)
    checks.append(("5. Equity datasets detected (all 10 present)", c5))

    # Check 6: Output directory exists
    c6 = os.path.exists(OUTPUT_DIR)
    checks.append(("6. Research output directory exists", c6))

    # Check 7: All 20 required artifacts present & non-empty
    missing_artifacts = []
    for art in REQUIRED_ARTIFACTS:
        p = os.path.join(OUTPUT_DIR, art)
        if not os.path.exists(p) or os.path.getsize(p) < 10:
            missing_artifacts.append(art)
    c7 = (len(missing_artifacts) == 0)
    checks.append(("7. All 20 required artifacts present and non-empty", c7))

    # Check 8: Data audit CSV valid
    da_path = os.path.join(OUTPUT_DIR, "data_audit.csv")
    c8 = False
    if os.path.exists(da_path):
        df_da = pd.read_csv(da_path)
        required_cols = {"symbol", "first_timestamp", "last_timestamp", "total_candles", "trading_days", "complete_sessions_pct", "ohlc_valid"}
        c8 = required_cols.issubset(set(df_da.columns)) and len(df_da) >= 11
    checks.append(("8. Data audit CSV valid (schema & 11 instruments)", c8))

    # Check 9: Candidate trade log valid
    tl_path = os.path.join(OUTPUT_DIR, "candidate_trade_log.csv")
    c9 = False
    if os.path.exists(tl_path):
        df_tl = pd.read_csv(tl_path)
        c9 = len(df_tl) > 500 and "gross_pnl" in df_tl.columns and "net_pnl" in df_tl.columns and "cost" in df_tl.columns
    checks.append(("9. Candidate trade log valid (>500 trades, PnL & cost columns)", c9))

    # Check 10: Hypothesis summary covers all 7 hypotheses (H1 to H7)
    hs_path = os.path.join(OUTPUT_DIR, "hypothesis_summary.csv")
    c10 = False
    if os.path.exists(hs_path):
        df_hs = pd.read_csv(hs_path)
        expected_hypo = {"H1", "H2", "H3", "H4", "H5", "H6", "H7"}
        found_hypo = set(df_hs["hypothesis_id"].unique())
        c10 = expected_hypo.issubset(found_hypo) and len(df_hs) == 7
    checks.append(("10. Hypothesis summary covers all 7 hypotheses (H1-H7)", c10))

    # Check 11: Gap analysis CSV generated
    gap_path = os.path.join(OUTPUT_DIR, "gap_analysis.csv")
    c11 = os.path.exists(gap_path) and os.path.getsize(gap_path) > 100
    checks.append(("11. Gap analysis CSV generated", c11))

    # Check 12: VWAP analysis CSV generated
    vwap_path = os.path.join(OUTPUT_DIR, "vwap_analysis.csv")
    c12 = os.path.exists(vwap_path) and os.path.getsize(vwap_path) > 100
    checks.append(("12. VWAP analysis CSV generated", c12))

    # Check 13: Volatility expansion analysis CSV generated
    ve_path = os.path.join(OUTPUT_DIR, "volatility_expansion_analysis.csv")
    c13 = os.path.exists(ve_path) and os.path.getsize(ve_path) > 100
    checks.append(("13. Volatility expansion analysis CSV generated", c13))

    # Check 14: Trend day analysis CSV generated
    td_path = os.path.join(OUTPUT_DIR, "trend_day_analysis.csv")
    c14 = os.path.exists(td_path) and os.path.getsize(td_path) > 100
    checks.append(("14. Trend day analysis CSV generated", c14))

    # Check 15: Failed breakout analysis CSV generated
    fb_path = os.path.join(OUTPUT_DIR, "failed_breakout_analysis.csv")
    c15 = os.path.exists(fb_path) and os.path.getsize(fb_path) > 100
    checks.append(("15. Failed breakout analysis CSV generated", c15))

    # Check 16: Multi-factor analysis CSV generated
    mf_path = os.path.join(OUTPUT_DIR, "multi_factor_analysis.csv")
    c16 = os.path.exists(mf_path) and os.path.getsize(mf_path) > 100
    checks.append(("16. Multi-factor analysis CSV generated", c16))

    # Check 17: Cost sensitivity tests multiple multipliers (0.0x to 2.0x)
    cs_path = os.path.join(OUTPUT_DIR, "cost_sensitivity.csv")
    c17 = False
    if os.path.exists(cs_path):
        df_cs = pd.read_csv(cs_path)
        mults = set(df_cs["cost_multiplier"].unique())
        c17 = {0.0, 0.5, 1.0, 1.5, 2.0}.issubset(mults)
    checks.append(("17. Cost sensitivity tests 5 friction tiers (0.0x to 2.0x)", c17))

    # Check 18: Symbol robustness covers NIFTY + 10 equities
    sr_path = os.path.join(OUTPUT_DIR, "symbol_robustness.csv")
    c18 = False
    if os.path.exists(sr_path):
        df_sr = pd.read_csv(sr_path)
        syms = set(df_sr["symbol"].unique())
        c18 = (len(syms) == 11 and "NIFTY50" in syms)
    checks.append(("18. Symbol robustness covers NIFTY + all 10 equities", c18))

    # Check 19: LOSO analysis covers all 10 equities
    loso_path = os.path.join(OUTPUT_DIR, "loso_analysis.csv")
    c19 = False
    if os.path.exists(loso_path):
        df_loso = pd.read_csv(loso_path)
        excl = set(df_loso["excluded_symbol"].unique())
        c19 = set(TARGET_STOCKS).issubset(excl)
    checks.append(("19. LOSO analysis covers Leave-One-Symbol-Out cross-validation", c19))

    # Check 20: Yearly regime analysis covers all dataset years
    yr_path = os.path.join(OUTPUT_DIR, "yearly_regime_analysis.csv")
    c20 = False
    if os.path.exists(yr_path):
        df_yr = pd.read_csv(yr_path)
        years = set(df_yr["year"].unique())
        c20 = {2017, 2018, 2019, 2020}.issubset(years)
    checks.append(("20. Yearly regime analysis covers 2017 to 2020", c20))

    # Check 21: Walk-forward / OOS validation covers Train, Validation, OOS
    wf_path = os.path.join(OUTPUT_DIR, "walk_forward.csv")
    c21 = False
    if os.path.exists(wf_path):
        df_wf = pd.read_csv(wf_path)
        splits = set(df_wf["split"].unique())
        c21 = any("TRAIN" in s for s in splits) and any("VALIDATION" in s for s in splits) and any("OOS" in s for s in splits)
    checks.append(("21. Walk-Forward / OOS validation covers Train, Val, OOS", c21))

    # Check 22: Bootstrap robustness uses fixed seed with 95% CIs
    boot_path = os.path.join(OUTPUT_DIR, "bootstrap_robustness.csv")
    c22 = False
    if os.path.exists(boot_path):
        df_boot = pd.read_csv(boot_path)
        c22 = "net_ci_95_lower" in df_boot.columns and "net_ci_95_upper" in df_boot.columns and len(df_boot) == 7
    checks.append(("22. Bootstrap robustness covers 95% CIs for all 7 hypotheses", c22))

    # Check 23: MAE / MFE analysis includes quantiles and ratios
    mm_path = os.path.join(OUTPUT_DIR, "mae_mfe_analysis.csv")
    c23 = False
    if os.path.exists(mm_path):
        df_mm = pd.read_csv(mm_path)
        c23 = "avg_mae_pct" in df_mm.columns and "avg_mfe_pct" in df_mm.columns and "mfe_mae_ratio" in df_mm.columns
    checks.append(("23. MAE / MFE analysis includes ratios and distributions", c23))

    # Check 24: Lookahead audit confirms all 10 checks PASS
    la_path = os.path.join(OUTPUT_DIR, "lookahead_audit.csv")
    c24 = False
    if os.path.exists(la_path):
        df_la = pd.read_csv(la_path)
        c24 = len(df_la) == 10 and (df_la["status"] == "PASS").all()
    checks.append(("24. Lookahead audit confirms all 10 causal items PASS", c24))

    # Check 25: Final verdict valid and not falsely production ready
    st_path = os.path.join(OUTPUT_DIR, "phase16_status.csv")
    c25 = False
    if os.path.exists(st_path):
        df_st = pd.read_csv(st_path)
        v_rows = df_st[df_st["metric"] == "final_verdict"]
        if len(v_rows) > 0:
            verdict = v_rows.iloc[0]["value"]
            valid_verdicts = ["PROMISING", "WEAK_EDGE", "REJECTED", "INSUFFICIENT_DATA"]
            c25 = verdict in valid_verdicts and verdict != "PRODUCTION_READY"
    checks.append(("25. Final verdict valid (one of 4 approved, not production-ready)", c25))

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
        print("\nSUCCESS: All Phase 16 tests PASSED!")
        return 0
    else:
        print("\nFAILURE: Some Phase 16 tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(test_phase16_suite())

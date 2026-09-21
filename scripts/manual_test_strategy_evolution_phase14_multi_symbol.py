"""
SignalForge Phase 14: Manual Verification Test Suite
====================================================
Validates all 19 deterministic protocol requirements for Phase 14:
Multi-Symbol Conditioned ORB Generalization Audit.

Requirements verified:
1. Runner exists
2. Runner is non-empty
3. Real datasets detected
4. Dataset schema is valid
5. Symbol universe is documented
6. Baseline was evaluated
7. Frozen conditioned ORB was evaluated
8. TRAIN exists
9. VALIDATION exists
10. OOS exists
11. LOSO exists
12. Cost stress exists (0.5x to 2.0x)
13. Parameter sensitivity exists
14. MAE/MFE exists
15. Look-ahead audit exists
16. Synthetic data disabled
17. No per-symbol optimization
18. No OOS threshold leakage
19. Final verdict is not falsely production-ready
"""

import os
import sys
import pandas as pd

OUTPUT_DIR = os.path.join("research", "strategy_evolution_2018", "phase14_multi_symbol_orb")
RUNNER_SCRIPT = os.path.join("scripts", "run_strategy_evolution_phase14_multi_symbol.py")


def run_all_checks() -> bool:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 14 — MANUAL VERIFICATION SUITE (19 PROTOCOL CHECKS)")
    print("=" * 80)

    checks = []

    # 1. Runner exists
    chk1 = os.path.exists(RUNNER_SCRIPT)
    checks.append((1, "Runner exists", chk1, f"Found {RUNNER_SCRIPT}" if chk1 else "Missing runner script"))

    # 2. Runner non-empty
    chk2 = chk1 and os.path.getsize(RUNNER_SCRIPT) > 500
    checks.append((2, "Runner is non-empty", chk2, f"Size: {os.path.getsize(RUNNER_SCRIPT)} bytes" if chk1 else "Missing file"))

    # 3. Real datasets detected
    q_file = os.path.join(OUTPUT_DIR, "symbol_data_quality.csv")
    chk3 = os.path.exists(q_file)
    if chk3:
        df_q = pd.read_csv(q_file)
        chk3 = len(df_q) >= 10
        msg3 = f"Detected {len(df_q)} real symbol datasets"
    else:
        msg3 = "Missing symbol_data_quality.csv"
    checks.append((3, "Real datasets detected", chk3, msg3))

    # 4. Dataset schema is valid
    if os.path.exists(q_file):
        df_q = pd.read_csv(q_file)
        chk4 = df_q["ohlc_valid"].all() and (df_q["missing_values"] == 0).all()
        msg4 = f"All {len(df_q)} datasets have valid OHLC and zero missing values"
    else:
        chk4 = False
        msg4 = "Missing data quality file"
    checks.append((4, "Dataset schema is valid", chk4, msg4))

    # 5. Symbol universe documented
    sym_comp_file = os.path.join(OUTPUT_DIR, "symbol_comparison.csv")
    chk5 = os.path.exists(sym_comp_file)
    if chk5:
        df_sym = pd.read_csv(sym_comp_file)
        chk5 = len(df_sym) >= 10
        msg5 = f"Documented {len(df_sym)} symbols with comparative metrics"
    else:
        msg5 = "Missing symbol_comparison.csv"
    checks.append((5, "Symbol universe documented", chk5, msg5))

    # 6. Baseline evaluated
    chk6 = False
    port_file = os.path.join(OUTPUT_DIR, "portfolio_comparison.csv")
    if os.path.exists(port_file):
        df_port = pd.read_csv(port_file)
        base_rows = df_port[df_port["strategy"] == "BASELINE_15M_LONG"]
        chk6 = len(base_rows) > 0 and base_rows["trades"].sum() > 0
        msg6 = f"Baseline evaluated across portfolio ({base_rows['trades'].sum()} trades)"
    else:
        msg6 = "Missing portfolio_comparison.csv"
    checks.append((6, "Baseline evaluated", chk6, msg6))

    # 7. Frozen conditioned ORB evaluated
    chk7 = False
    if os.path.exists(port_file):
        df_port = pd.read_csv(port_file)
        cond_rows = df_port[df_port["strategy"] == "CONDITIONED_LOW_ATR_ORB"]
        chk7 = len(cond_rows) > 0 and cond_rows["trades"].sum() > 0
        msg7 = f"Frozen conditioned ORB evaluated ({cond_rows['trades'].sum()} trades)"
    else:
        msg7 = "Missing portfolio_comparison.csv"
    checks.append((7, "Frozen conditioned ORB evaluated", chk7, msg7))

    # 8. TRAIN exists
    chk8 = False
    if os.path.exists(port_file):
        df_port = pd.read_csv(port_file)
        chk8 = "train_net_pnl" in df_port.columns and not df_port["train_net_pnl"].isna().all()
        msg8 = f"TRAIN metrics present (Net P&L: {df_port['train_net_pnl'].iloc[1]})"
    else:
        msg8 = "Missing portfolio comparison file"
    checks.append((8, "TRAIN exists", chk8, msg8))

    # 9. VALIDATION exists
    chk9 = False
    if os.path.exists(port_file):
        df_port = pd.read_csv(port_file)
        chk9 = "val_net_pnl" in df_port.columns and not df_port["val_net_pnl"].isna().all()
        msg9 = f"VALIDATION metrics present (Net P&L: {df_port['val_net_pnl'].iloc[1]})"
    else:
        msg9 = "Missing portfolio comparison file"
    checks.append((9, "VALIDATION exists", chk9, msg9))

    # 10. OOS exists
    chk10 = False
    if os.path.exists(port_file):
        df_port = pd.read_csv(port_file)
        chk10 = "oos_net_pnl" in df_port.columns
        msg10 = "OOS partition evaluated and documented"
    else:
        msg10 = "Missing portfolio comparison file"
    checks.append((10, "OOS exists", chk10, msg10))

    # 11. LOSO exists
    loso_file = os.path.join(OUTPUT_DIR, "loso_analysis.csv")
    chk11 = os.path.exists(loso_file)
    if chk11:
        df_loso = pd.read_csv(loso_file)
        chk11 = len(df_loso) >= 10 and any("EXCLUDE_BEST" in str(c) for c in df_loso["case"])
        msg11 = f"LOSO analysis present with {len(df_loso)} cases including exclude-best"
    else:
        msg11 = "Missing loso_analysis.csv"
    checks.append((11, "LOSO exists", chk11, msg11))

    # 12. Cost stress exists (0.5x to 2.0x)
    cost_file = os.path.join(OUTPUT_DIR, "multi_symbol_cost_stress.csv")
    chk12 = os.path.exists(cost_file)
    if chk12:
        df_cost = pd.read_csv(cost_file)
        mults = set(df_cost["cost_multiplier"].tolist())
        chk12 = {0.5, 1.0, 1.5, 2.0}.issubset(mults)
        msg12 = f"Cost multipliers present: {sorted(list(mults))}"
    else:
        msg12 = "Missing multi_symbol_cost_stress.csv"
    checks.append((12, "Cost stress exists (0.5x to 2.0x)", chk12, msg12))

    # 13. Parameter sensitivity exists
    sens_file = os.path.join(OUTPUT_DIR, "parameter_sensitivity.csv")
    chk13 = os.path.exists(sens_file)
    if chk13:
        df_sens = pd.read_csv(sens_file)
        chk13 = len(df_sens) >= 3 and 33.0 in df_sens["atr_percentile"].values
        msg13 = f"Parameter sensitivity evaluated for percentiles {df_sens['atr_percentile'].tolist()}"
    else:
        msg13 = "Missing parameter_sensitivity.csv"
    checks.append((13, "Parameter sensitivity exists", chk13, msg13))

    # 14. MAE/MFE exists
    mae_file = os.path.join(OUTPUT_DIR, "mae_mfe_analysis.csv")
    chk14 = os.path.exists(mae_file)
    if chk14:
        df_mae = pd.read_csv(mae_file)
        chk14 = len(df_mae) >= 10 and "mae_median_pct" in df_mae.columns
        msg14 = f"MAE/MFE metrics computed for {len(df_mae)} cross-sections"
    else:
        msg14 = "Missing mae_mfe_analysis.csv"
    checks.append((14, "MAE/MFE exists", chk14, msg14))

    # 15. Look-ahead audit exists
    audit_file = os.path.join(OUTPUT_DIR, "lookahead_audit.csv")
    chk15 = os.path.exists(audit_file)
    if chk15:
        df_audit = pd.read_csv(audit_file)
        all_pass = (df_audit["status"] == "PASS").all()
        chk15 = all_pass and len(df_audit) >= 8
        msg15 = f"All {len(df_audit)} lookahead audit checks PASSED"
    else:
        msg15 = "Missing lookahead_audit.csv"
    checks.append((15, "Look-ahead audit exists", chk15, msg15))

    # 16. Synthetic data disabled
    status_file = os.path.join(OUTPUT_DIR, "phase14_status.csv")
    chk16 = False
    if os.path.exists(status_file):
        df_stat = pd.read_csv(status_file).set_index("metric")["value"].to_dict()
        chk16 = df_stat.get("synthetic_data_used", "").upper() == "FALSE"
        msg16 = "Synthetic data strictly FALSE"
    else:
        msg16 = "Missing phase14_status.csv"
    checks.append((16, "Synthetic data disabled", chk16, msg16))

    # 17. No per-symbol optimization
    chk17 = False
    if os.path.exists(status_file):
        df_stat = pd.read_csv(status_file).set_index("metric")["value"].to_dict()
        chk17 = df_stat.get("per_symbol_optimization", "").upper() == "FALSE"
        msg17 = "Per-symbol optimization strictly FALSE (frozen 33rd percentile applied globally)"
    else:
        msg17 = "Missing phase14_status.csv"
    checks.append((17, "No per-symbol optimization", chk17, msg17))

    # 18. No OOS threshold leakage
    chk18 = False
    if os.path.exists(audit_file):
        df_audit = pd.read_csv(audit_file)
        leakage_checks = df_audit[df_audit["check_id"].isin(["CHK_04", "CHK_05", "CHK_06"])]
        chk18 = (leakage_checks["status"] == "PASS").all()
        msg18 = "Validation and OOS strictly isolated from threshold calibration"
    else:
        msg18 = "Missing audit file"
    checks.append((18, "No OOS threshold leakage", chk18, msg18))

    # 19. Final verdict is not falsely production-ready
    chk19 = False
    if os.path.exists(status_file):
        df_stat = pd.read_csv(status_file).set_index("metric")["value"].to_dict()
        prod_ready = df_stat.get("production_ready", "").upper() == "TRUE"
        verdict = df_stat.get("final_verdict", "")
        chk19 = (not prod_ready) and (verdict in ["ROBUST_MULTI_SYMBOL_RESEARCH_CANDIDATE", "PROMISING_BUT_NOT_GENERALIZED", "REJECTED"])
        msg19 = f"Production readiness is FALSE; Valid research verdict: {verdict}"
    else:
        msg19 = "Missing status file"
    checks.append((19, "Final verdict is not falsely production-ready", chk19, msg19))

    # Print results
    all_passed = True
    for cid, name, passed, detail in checks:
        tag = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"{tag}: [Check {cid:02d}] {name} -> {detail}")

    print("=" * 80)
    if all_passed:
        print(f"PHASE 14 VERIFICATION: ALL TESTS PASSED ({len(checks)}/{len(checks)})")
    else:
        failed_count = sum(1 for _, _, p, _ in checks if not p)
        print(f"PHASE 14 VERIFICATION: {failed_count} CHECK(S) FAILED")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)

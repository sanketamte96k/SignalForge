"""SignalForge — Phase 13: Manual Verification Suite
===================================================
File: scripts/manual_test_strategy_evolution_phase13_conditioned_orb.py

Deterministic verification suite for Phase 13 Conditioned ORB Edge Discovery.
Verifies all 16 explicit protocol requirements:
 1. Runner exists
 2. Runner is non-empty
 3. Dataset exists
 4. Dataset schema is correct
 5. Correct date range is used (2015-01-09 to 2024-03-26)
 6. Phase 13 output directory exists
 7. Required output files exist
 8. Baseline was evaluated
 9. All required filters were evaluated (Filters A through G)
10. Chronological split exists (TRAIN, VAL, OOS)
11. OOS exists and is evaluated
12. Cost stress exists (up to 2.0x)
13. Look-ahead audit exists and passes
14. Synthetic data disabled
15. No OOS threshold leakage
16. Final status is not falsely production-ready
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATH = PROJECT_ROOT / "data" / "historical" / "nifty50_1m_signalforge.csv"
OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase13_conditioned_orb"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_strategy_evolution_phase13_conditioned_orb.py"


def main() -> None:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 13 — MANUAL VERIFICATION SUITE (16 PROTOCOL CHECKS)")
    print("=" * 80)

    checks = 0
    passed = 0

    def check(name: str, condition: bool, details: str = "") -> None:
        nonlocal checks, passed
        checks += 1
        if condition:
            passed += 1
            print(f"PASS: [Check {checks:02d}] {name}")
        else:
            print(f"FAIL: [Check {checks:02d}] {name} - {details}")

    # Check 01: Runner exists
    check("Runner exists", RUNNER_PATH.exists(), f"Missing: {RUNNER_PATH}")

    # Check 02: Runner is non-empty
    check(
        "Runner is non-empty",
        RUNNER_PATH.exists() and RUNNER_PATH.stat().st_size > 1000,
        f"Size: {RUNNER_PATH.stat().st_size if RUNNER_PATH.exists() else 0} bytes",
    )

    # Check 03: Dataset exists
    check("Dataset exists", DATA_PATH.exists(), f"Missing: {DATA_PATH}")

    # Check 04: Dataset schema is correct
    if DATA_PATH.exists():
        df_head = pd.read_csv(DATA_PATH, nrows=5)
        req_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        check("Dataset schema is correct", req_cols.issubset(set(df_head.columns)))
    else:
        check("Dataset schema is correct", False)

    # Check 05: Correct date range is used
    dq_file = OUT_DIR / "data_quality_report.md"
    if dq_file.exists():
        dq_text = dq_file.read_text(encoding="utf-8")
        check(
            "Correct date range is used (2015-01-09 to 2024-03-26)",
            "2015-01-09" in dq_text and "2024-03-26" in dq_text,
        )
    else:
        check("Correct date range is used", False)

    # Check 06: Phase 13 output directory exists
    check("Phase 13 output directory exists", OUT_DIR.exists() and OUT_DIR.is_dir())

    # Check 07: Required output files exist
    required_files = [
        "phase13_report.md",
        "phase13_status.csv",
        "filter_comparison.csv",
        "candidate_trades.csv",
        "yearly_analysis.csv",
        "chronological_oos.csv",
        "cost_stress.csv",
        "filter_interactions.csv",
        "mae_mfe_analysis.csv",
        "lookahead_audit.csv",
        "data_quality_report.md",
    ]
    missing_files = [f for f in required_files if not (OUT_DIR / f).exists()]
    check(
        "Required output files exist",
        len(missing_files) == 0,
        f"Missing files: {missing_files}",
    )

    # Check 08: Baseline was evaluated
    filter_file = OUT_DIR / "filter_comparison.csv"
    if filter_file.exists():
        df_f = pd.read_csv(filter_file)
        check(
            "Baseline was evaluated",
            "baseline_long" in df_f["filter_name"].tolist(),
        )
    else:
        check("Baseline was evaluated", False)

    # Check 09: All required filters were evaluated (Filters A through G)
    if filter_file.exists():
        df_f = pd.read_csv(filter_file)
        evaluated_filters = set(df_f["filter_name"].tolist())
        target_filters = {
            "baseline_long",
            "filter_a_vwap",
            "filter_b_ema20",
            "filter_c_ema50",
            "filter_d_ema_alignment",
            "filter_e_atr_low",
            "filter_e_atr_norm",
            "filter_e_atr_high",
            "filter_f_width_lt_05",
            "filter_f_width_05_10",
            "filter_f_width_10_15",
            "filter_f_width_gt_15",
            "filter_g_momentum",
        }
        missing_filters = target_filters - evaluated_filters
        check(
            "All required filters were evaluated (A through G)",
            len(missing_filters) == 0,
            f"Missing filters: {missing_filters}",
        )
    else:
        check("All required filters were evaluated", False)

    # Check 10: Chronological split exists
    oos_file = OUT_DIR / "chronological_oos.csv"
    if oos_file.exists():
        df_oos = pd.read_csv(oos_file)
        splits = set(df_oos["split"].tolist())
        check(
            "Chronological split exists (TRAIN, VAL, OOS)",
            {"TRAIN", "VALIDATION", "OOS"}.issubset(splits),
        )
    else:
        check("Chronological split exists", False)

    # Check 11: OOS exists and is evaluated
    if oos_file.exists():
        df_oos = pd.read_csv(oos_file)
        oos_rows = df_oos[df_oos["split"] == "OOS"]
        check(
            "OOS exists and is evaluated",
            len(oos_rows) == 1 and oos_rows.iloc[0]["trades"] > 0,
        )
    else:
        check("OOS exists and is evaluated", False)

    # Check 12: Cost stress exists (up to 2.0x)
    stress_file = OUT_DIR / "cost_stress.csv"
    if stress_file.exists():
        df_s = pd.read_csv(stress_file)
        check(
            "Cost stress exists and covers up to 2.0x",
            (df_s["cost_multiplier"] >= 2.0).any() and (df_s["cost_multiplier"] == 1.0).any(),
        )
    else:
        check("Cost stress exists", False)

    # Check 13: Look-ahead audit exists and passes
    lh_file = OUT_DIR / "lookahead_audit.csv"
    if lh_file.exists():
        df_lh = pd.read_csv(lh_file)
        check(
            "Look-ahead audit exists and all checks pass",
            len(df_lh) >= 5 and (df_lh["status"] == "PASS").all(),
        )
    else:
        check("Look-ahead audit exists", False)

    # Check 14: Synthetic data disabled
    status_file = OUT_DIR / "phase13_status.csv"
    if status_file.exists():
        df_stat = pd.read_csv(status_file)
        check(
            "Synthetic data disabled",
            bool(df_stat.iloc[0].get("synthetic_data_used", True)) is False,
        )
    else:
        check("Synthetic data disabled", False)

    # Check 15: No OOS threshold leakage
    if lh_file.exists():
        df_lh = pd.read_csv(lh_file)
        leak_check = df_lh[df_lh["check_name"] == "zero_oos_threshold_leakage"]
        check(
            "No OOS threshold leakage",
            len(leak_check) == 1 and leak_check.iloc[0]["status"] == "PASS",
        )
    else:
        check("No OOS threshold leakage", False)

    # Check 16: Final status is not falsely production-ready
    if status_file.exists():
        df_stat = pd.read_csv(status_file)
        stat = str(df_stat.iloc[0].get("status", ""))
        check(
            "Final status is not falsely production-ready",
            stat != "PRODUCTION_READY" and "PRODUCTION" not in stat and stat in ["ROBUST_RESEARCH_CANDIDATE", "PROMISING_BUT_NOT_ROBUST", "REJECTED"],
            f"Actual status: {stat}",
        )
    else:
        check("Final status is not falsely production-ready", False)

    print()
    print("=" * 80)
    if passed == checks:
        print("PHASE 13 VERIFICATION: ALL TESTS PASSED (16/16)")
    else:
        print(f"PHASE 13 VERIFICATION: {passed}/{checks} PASSED")
    print("=" * 80)

    if passed != checks:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

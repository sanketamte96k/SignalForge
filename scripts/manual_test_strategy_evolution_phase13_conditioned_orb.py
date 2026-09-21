"""SignalForge — Phase 13: Manual Verification Suite
===================================================
File: scripts/manual_test_strategy_evolution_phase13_conditioned_orb.py

Deterministic verification suite for Phase 13 Conditioned ORB Edge Discovery.
Verifies at minimum:
- runner exists and non-empty
- dataset exists and schema is valid
- Phase 13 status exists and is not falsely marked PRODUCTION_READY
- baseline exists in filter comparison
- all required filters evaluated (A, B1, B2, C, D, E)
- chronological split exists (TRAIN, VAL, OOS)
- cost stress analysis exists and covers up to 2.0x
- lookahead audit exists and confirms zero causality leaks
- synthetic data explicitly disabled
- no OOS threshold leakage
- data quality report exists
- report explicitly differentiates index-level vs stock-level robustness
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
    print(" SIGNALFORGE PHASE 13 — MANUAL VERIFICATION SUITE")
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

    # 1. Runner checks
    check("Phase 13 runner exists", RUNNER_PATH.exists(), f"Missing: {RUNNER_PATH}")
    check(
        "Phase 13 runner is non-empty",
        RUNNER_PATH.exists() and RUNNER_PATH.stat().st_size > 500,
        f"Runner size is {RUNNER_PATH.stat().st_size if RUNNER_PATH.exists() else 0} bytes",
    )

    # 2. Dataset checks
    check("Historical dataset exists", DATA_PATH.exists(), f"Missing: {DATA_PATH}")
    if DATA_PATH.exists():
        df_head = pd.read_csv(DATA_PATH, nrows=5)
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        check(
            "Dataset schema is valid (timestamp, open, high, low, close, volume)",
            required_cols.issubset(set(df_head.columns)),
        )
    else:
        check("Dataset schema is valid", False, "Dataset file missing")

    # 3. Status checks
    status_path = OUT_DIR / "phase13_status.csv"
    check("Phase 13 status exists", status_path.exists(), f"Missing: {status_path}")
    if status_path.exists():
        df_status = pd.read_csv(status_path)
        check("Phase 13 status contains valid record", len(df_status) >= 1)
        check(
            "Synthetic data explicitly disabled",
            bool(df_status.iloc[0].get("synthetic_data_used", True)) is False,
        )
        status_val = str(df_status.iloc[0].get("status", ""))
        check(
            "Status is not falsely marked production-ready",
            status_val != "PRODUCTION_READY" and "PRODUCTION" not in status_val,
            f"Actual status: {status_val}",
        )
        check(
            "Status has valid research classification",
            status_val in ["ROBUST_RESEARCH_CANDIDATE", "PROMISING_BUT_NOT_ROBUST", "REJECTED"],
            f"Unrecognized status: {status_val}",
        )
    else:
        check("Phase 13 status contains valid record", False)
        check("Synthetic data explicitly disabled", False)
        check("Status is not falsely marked production-ready", False)
        check("Status has valid research classification", False)

    # 4. Filter comparison checks
    filter_path = OUT_DIR / "filter_comparison.csv"
    check("Filter comparison exists", filter_path.exists(), f"Missing: {filter_path}")
    if filter_path.exists():
        df_filters = pd.read_csv(filter_path)
        check(
            "Baseline LONG exists in filter comparison",
            "baseline_long" in df_filters["filter_name"].tolist(),
        )
        required_filters = [
            "baseline_long",
            "filter_a_vwap",
            "filter_b1_ema20",
            "filter_b2_ema50",
            "filter_c_atr_low",
            "filter_c_atr_norm",
            "filter_c_atr_high",
            "filter_d_width_lt_05",
            "filter_d_width_05_10",
            "filter_d_width_10_15",
            "filter_d_width_gt_15",
            "filter_e_momentum",
        ]
        actual_filters = set(df_filters["filter_name"].unique())
        missing_filters = set(required_filters) - actual_filters
        check(
            "All required filters evaluated (A, B1, B2, C, D, E)",
            len(missing_filters) == 0,
            f"Missing filters: {missing_filters}",
        )
    else:
        check("Baseline LONG exists in filter comparison", False)
        check("All required filters evaluated", False)

    # 5. Filter interactions check
    inter_path = OUT_DIR / "filter_interactions.csv"
    check("Filter interactions exists", inter_path.exists(), f"Missing: {inter_path}")
    if inter_path.exists():
        df_inter = pd.read_csv(inter_path)
        check("Filter interactions evaluated combination candidates", len(df_inter) >= 2)
    else:
        check("Filter interactions evaluated combination candidates", False)

    # 6. Candidate trade log
    trades_path = OUT_DIR / "candidate_trades.csv"
    check("Candidate trade log exists", trades_path.exists(), f"Missing: {trades_path}")
    if trades_path.exists():
        df_trades = pd.read_csv(trades_path)
        check("Candidate trade log contains recorded trades", len(df_trades) > 0)
        req_trade_cols = {"direction", "entry_datetime", "exit_datetime", "pnl", "mae_atr", "mfe_atr"}
        check(
            "Candidate trade log contains required execution and MAE/MFE fields",
            req_trade_cols.issubset(set(df_trades.columns)),
        )
    else:
        check("Candidate trade log contains recorded trades", False)
        check("Candidate trade log contains required execution and MAE/MFE fields", False)

    # 7. Chronological OOS check
    oos_path = OUT_DIR / "chronological_oos.csv"
    check("Chronological OOS analysis exists", oos_path.exists(), f"Missing: {oos_path}")
    if oos_path.exists():
        df_oos = pd.read_csv(oos_path)
        expected_splits = {"TRAIN", "VALIDATION", "OOS"}
        actual_splits = set(df_oos["split"].unique())
        check(
            "All chronological partitions evaluated (TRAIN, VAL, OOS)",
            expected_splits.issubset(actual_splits),
        )
    else:
        check("All chronological partitions evaluated", False)

    # 8. Cost stress check
    stress_path = OUT_DIR / "cost_stress.csv"
    check("Cost stress analysis exists", stress_path.exists(), f"Missing: {stress_path}")
    if stress_path.exists():
        df_stress = pd.read_csv(stress_path)
        check("Cost stress covers up to 2.0x multiplier", (df_stress["cost_multiplier"] >= 2.0).any())
    else:
        check("Cost stress covers up to 2.0x multiplier", False)

    # 9. Lookahead audit check
    lh_path = OUT_DIR / "lookahead_audit.csv"
    check("Lookahead audit exists", lh_path.exists(), f"Missing: {lh_path}")
    if lh_path.exists():
        df_lh = pd.read_csv(lh_path)
        check(
            "Lookahead audit confirms zero causality leaks",
            (df_lh["status"] == "PASS").all(),
            f"Failed checks: {df_lh[df_lh['status'] != 'PASS']['check_name'].tolist()}",
        )
        check(
            "No OOS threshold leakage recorded",
            "zero_oos_threshold_leakage" in df_lh["check_name"].tolist(),
        )
    else:
        check("Lookahead audit confirms zero causality leaks", False)
        check("No OOS threshold leakage recorded", False)

    # 10. Research report & data quality report
    report_path = OUT_DIR / "phase13_report.md"
    dq_path = OUT_DIR / "data_quality_report.md"
    yearly_path = OUT_DIR / "yearly_analysis.csv"
    mae_path = OUT_DIR / "mae_mfe_analysis.csv"

    check("Data quality report exists", dq_path.exists())
    check("Phase 13 report exists", report_path.exists())
    if report_path.exists():
        rep_text = report_path.read_text(encoding="utf-8")
        check(
            "Report explicitly distinguishes index-level vs stock-level robustness",
            "INDEX-LEVEL EVIDENCE" in rep_text or "Index-Level" in rep_text,
        )
    else:
        check("Report explicitly distinguishes index-level vs stock-level robustness", False)

    check("Yearly analysis exists", yearly_path.exists())
    check("MAE/MFE analysis exists", mae_path.exists())

    print()
    print("=" * 80)
    print(f"PHASE 13 VERIFICATION: {passed}/{checks} PASSED")
    print("=" * 80)

    if passed != checks:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

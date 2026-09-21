"""SignalForge — Phase 12: Manual Verification Suite
===================================================
File: scripts/manual_test_strategy_evolution_phase12_orb.py

Deterministic verification suite for Phase 12 Structural ORB Robustness Audit.
Verifies at minimum:
- runner exists and non-empty
- dataset exists and schema is valid
- Phase 12 status exists and is not falsely marked PRODUCTION_READY
- synthetic data explicitly disabled
- Phase 12 report exists and differentiates index-level vs stock-level evidence
- parameter comparison exists and contains exactly 15 combinations
- candidate trade log exists and contains valid enriched trades
- data quality report exists
- lookahead audit exists and confirms zero causality leaks
- all supplementary research artifacts (yearly, directional, OOS, cost-stress, concentration, MAE/MFE) exist
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
OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase12_orb"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_strategy_evolution_phase12_orb.py"


def main() -> None:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 12 — MANUAL VERIFICATION SUITE")
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
    check(
        "Phase 12 runner exists",
        RUNNER_PATH.exists(),
        f"Missing: {RUNNER_PATH}",
    )
    check(
        "Phase 12 runner is non-empty",
        RUNNER_PATH.exists() and RUNNER_PATH.stat().st_size > 500,
        f"Runner size is {RUNNER_PATH.stat().st_size if RUNNER_PATH.exists() else 0} bytes",
    )

    # 2. Dataset checks
    check(
        "Historical dataset exists",
        DATA_PATH.exists(),
        f"Missing: {DATA_PATH}",
    )

    if DATA_PATH.exists():
        # Read header only for schema verification
        df_head = pd.read_csv(DATA_PATH, nrows=5)
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        actual_cols = set(df_head.columns)
        check(
            "Dataset schema is valid (timestamp, open, high, low, close, volume)",
            required_cols.issubset(actual_cols),
            f"Missing columns: {required_cols - actual_cols}",
        )
    else:
        check("Dataset schema is valid", False, "Dataset file missing")

    # 3. Output directory and status
    status_path = OUT_DIR / "phase12_status.csv"
    check("Phase 12 status exists", status_path.exists(), f"Missing: {status_path}")

    if status_path.exists():
        df_status = pd.read_csv(status_path)
        check("Phase 12 status contains record", len(df_status) >= 1)
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
            status_val in [
                "ROBUST_RESEARCH_CANDIDATE",
                "PROMISING_BUT_NOT_ROBUST",
                "DATA_LIMITED",
                "REJECTED",
                "NOT_VALIDATED",
            ],
            f"Unrecognized status: {status_val}",
        )
    else:
        check("Phase 12 status contains record", False)
        check("Synthetic data explicitly disabled", False)
        check("Status is not falsely marked production-ready", False)
        check("Status has valid research classification", False)

    # 4. Report check
    report_path = OUT_DIR / "phase12_report.md"
    check("Phase 12 report exists", report_path.exists(), f"Missing: {report_path}")
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")
        check(
            "Report explicitly distinguishes index-level vs stock-level robustness",
            ("INDEX-LEVEL EVIDENCE" in report_content)
            or ("Index-Level" in report_content and "Stock-Level" in report_content),
        )
    else:
        check("Report explicitly distinguishes index-level vs stock-level robustness", False)

    # 5. Parameter comparison matrix
    param_path = OUT_DIR / "orb_parameter_comparison.csv"
    check("Parameter comparison exists", param_path.exists(), f"Missing: {param_path}")
    if param_path.exists():
        df_param = pd.read_csv(param_path)
        check(
            "Exactly 15 parameter combinations evaluated (3 windows x 5 modes)",
            len(df_param) == 15,
            f"Found {len(df_param)} combinations instead of 15",
        )
        # Check all expected windows and modes
        expected_windows = {"15m", "30m", "45m"}
        expected_modes = {"immediate", "close_confirm", "volume_confirm", "vwap_confirm", "retest"}
        actual_windows = set(df_param["or_window"].unique())
        actual_modes = set(df_param["breakout_mode"].unique())
        check(
            "All expected windows and modes present in parameter matrix",
            expected_windows == actual_windows and expected_modes == actual_modes,
        )
    else:
        check("Exactly 15 parameter combinations evaluated", False)
        check("All expected windows and modes present in parameter matrix", False)

    # 6. Candidate trade log
    trade_log_path = OUT_DIR / "candidate_trades.csv"
    check("Candidate trade log exists", trade_log_path.exists(), f"Missing: {trade_log_path}")
    if trade_log_path.exists():
        df_trades = pd.read_csv(trade_log_path)
        check(
            "Candidate trade log contains recorded trades",
            len(df_trades) > 0,
            f"Trade count is {len(df_trades)}",
        )
        trade_required_cols = {"direction", "entry_datetime", "exit_datetime", "entry_price", "exit_price", "pnl", "mae_atr", "mfe_atr"}
        check(
            "Candidate trade log contains required execution and MAE/MFE fields",
            trade_required_cols.issubset(set(df_trades.columns)),
            f"Missing fields: {trade_required_cols - set(df_trades.columns)}",
        )
    else:
        check("Candidate trade log contains recorded trades", False)
        check("Candidate trade log contains required execution and MAE/MFE fields", False)

    # 7. Data quality report
    dq_path = OUT_DIR / "data_quality_report.md"
    check("Data quality report exists", dq_path.exists(), f"Missing: {dq_path}")
    if dq_path.exists():
        dq_content = dq_path.read_text(encoding="utf-8")
        check(
            "Data quality report logs zero volume limitation",
            "DATA_LIMITED" in dq_content or "zero-volume" in dq_content,
        )
    else:
        check("Data quality report logs zero volume limitation", False)

    # 8. Lookahead audit
    lookahead_path = OUT_DIR / "lookahead_audit.csv"
    check("Look-ahead audit exists", lookahead_path.exists(), f"Missing: {lookahead_path}")
    if lookahead_path.exists():
        df_lh = pd.read_csv(lookahead_path)
        check(
            "Look-ahead audit confirms all causality checks passed",
            (df_lh["status"] == "PASS").all(),
            f"Failed checks: {df_lh[df_lh['status'] != 'PASS']['check_name'].tolist()}",
        )
    else:
        check("Look-ahead audit confirms all causality checks passed", False)

    # 9. Additional research artifacts
    yearly_path = OUT_DIR / "yearly_analysis.csv"
    direction_path = OUT_DIR / "direction_analysis.csv"
    oos_path = OUT_DIR / "chronological_oos.csv"
    stress_path = OUT_DIR / "cost_stress.csv"
    conc_path = OUT_DIR / "concentration_analysis.csv"
    mae_path = OUT_DIR / "mae_mfe_analysis.csv"

    check("Yearly analysis exists", yearly_path.exists())
    check("Direction analysis exists", direction_path.exists())
    check("Chronological OOS analysis exists", oos_path.exists())
    check("Cost-stress analysis exists", stress_path.exists())
    check("Concentration analysis exists", conc_path.exists())
    check("MAE/MFE analysis exists", mae_path.exists())

    print()
    print("=" * 80)
    print(f"PHASE 12 VERIFICATION: {passed}/{checks} PASSED")
    print("=" * 80)

    if passed != checks:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

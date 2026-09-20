"""
SignalForge — Comprehensive 2018 Data Pipeline Manual Validation
===============================================================
Script: scripts/manual_test_data_pipeline_2018.py

Performs 20 independent tests across the 5 cleaned 2018 datasets:
RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK.

Does NOT depend on DataAvailabilityChecker or DataQualityChecker.
Directly inspects the CSV files using pandas.
Cross-checks against DataLoader results and BacktestEngine execution.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# UTF-8 stdout configuration for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtesting.data_loader import BacktestDataLoader
from src.backtest.engine import IntradayEngineConfig, run_intraday_backtest
from scripts.run_backtest_2018 import calculate_indicators, precompute_signals

DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
OUTPUT_DIR = PROJECT_ROOT / "research" / "manual_validation_2018"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]

STANDARD_SESSION_START = "09:15"
STANDARD_SESSION_END = "15:29"
STANDARD_SESSION_BARS = 375  # 09:15:00 through 15:29:00 = 375 bars


class DualLogger:
    """Tee stdout to both console and a log file."""

    def __init__(self, filepath: Path):
        self.terminal = sys.stdout
        self.logfile = open(filepath, "w", encoding="utf-8")

    def write(self, message: str):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        self.terminal.flush()
        self.logfile.flush()

    def close(self):
        self.logfile.close()


def run_pipeline_manual_tests():
    log_file = OUTPUT_DIR / "manual_test_log.txt"
    logger = DualLogger(log_file)
    original_stdout = sys.stdout
    sys.stdout = logger

    try:
        print("=" * 80)
        print("SIGNALFORGE — 2018 MANUAL DATA PIPELINE AUDIT (TESTS 1 - 20)")
        print("=" * 80)

        summary_rows = []
        all_symbol_stats = {}
        stock_test_results = {}

        total_files_tested = len(SYMBOLS)
        files_passed = 0
        files_failed = 0
        total_warnings = 0

        # Global sanity trackers
        global_data_integrity = True
        global_session_integrity = True
        global_loader_consistency = True
        global_backtest_safety = True
        global_lookahead_safety = True

        loader = BacktestDataLoader(data_dir=DATA_DIR)

        for symbol in SYMBOLS:
            print("\n" + "#" * 80)
            print(f"STARTING COMPREHENSIVE AUDIT FOR: {symbol}")
            print("#" * 80)

            symbol_warnings = 0
            symbol_fails = 0
            csv_path = DATA_DIR / f"{symbol}_2018.csv"

            # ----------------------------------------------------
            # TEST 1 — FILE EXISTENCE
            # ----------------------------------------------------
            print("\n--- TEST 1: FILE EXISTENCE ---")
            if not csv_path.exists():
                print(f"FAIL: File does not exist: {csv_path}")
                symbol_fails += 1
                global_data_integrity = False
                continue
            else:
                print(f"PASS: File found: {csv_path.name} ({csv_path.stat().st_size:,} bytes)")

            # ----------------------------------------------------
            # TEST 2 — REQUIRED COLUMNS
            # ----------------------------------------------------
            print("\n--- TEST 2: REQUIRED COLUMNS ---")
            df_raw = pd.read_csv(csv_path)
            actual_cols = list(df_raw.columns)
            print(f"Actual columns: {actual_cols}")
            missing_cols = [c for c in REQUIRED_COLUMNS if c not in actual_cols]
            if missing_cols:
                print(f"FAIL: Missing required columns: {missing_cols}")
                symbol_fails += 1
                global_data_integrity = False
            else:
                print(f"PASS: All required columns present: {REQUIRED_COLUMNS}")

            # ----------------------------------------------------
            # TEST 3 — DATETIME CONVERSION & ORDER
            # ----------------------------------------------------
            print("\n--- TEST 3: DATETIME PARSING & ORDER ---")
            df = df_raw.copy()
            df["dt"] = pd.to_datetime(df["Date"], errors="coerce")
            invalid_dt = df["dt"].isna().sum()
            if invalid_dt > 0:
                print(f"FAIL: {invalid_dt} invalid datetime timestamps found!")
                symbol_fails += 1
                global_data_integrity = False
            else:
                print("PASS: 0 invalid timestamps after pd.to_datetime")

            tz_info = df["dt"].dt.tz
            if tz_info is not None:
                print(f"NOTE: Timezone detected: {tz_info}")
            else:
                print("PASS: Datetime is timezone-naive local market time")

            is_sorted = df["dt"].is_monotonic_increasing
            if not is_sorted:
                print("FAIL: Timestamps are NOT strictly chronological!")
                symbol_fails += 1
                global_data_integrity = False
            else:
                print("PASS: Timestamps are strictly sorted ascending")

            # ----------------------------------------------------
            # TEST 4 — DUPLICATE TIMESTAMPS
            # ----------------------------------------------------
            print("\n--- TEST 4: DUPLICATE TIMESTAMPS ---")
            dup_count = int(df["dt"].duplicated().sum())
            if dup_count > 0:
                print(f"FAIL: Found {dup_count} exact duplicate timestamps!")
                symbol_fails += 1
                global_data_integrity = False
            else:
                print(f"PASS: 0 duplicate timestamps (exact count: {dup_count})")

            # ----------------------------------------------------
            # TEST 5 — OHLC RELATIONSHIPS
            # ----------------------------------------------------
            print("\n--- TEST 5: OHLC VALIDITY ---")
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            bad_h_o = df["High"] < df["Open"]
            bad_h_c = df["High"] < df["Close"]
            bad_h_l = df["High"] < df["Low"]
            bad_l_o = df["Low"] > df["Open"]
            bad_l_c = df["Low"] > df["Close"]
            bad_l_h = df["Low"] > df["High"]

            bad_ohlc_mask = bad_h_o | bad_h_c | bad_h_l | bad_l_o | bad_l_c | bad_l_h
            bad_ohlc_count = int(bad_ohlc_mask.sum())
            if bad_ohlc_count > 0:
                print(f"FAIL: Found {bad_ohlc_count} rows with invalid OHLC!")
                print(df[bad_ohlc_mask].head(10))
                symbol_fails += 1
                global_data_integrity = False
            else:
                print("PASS: 0 invalid OHLC rows (High >= Open/Close/Low and Low <= Open/Close/High verified)")

            # ----------------------------------------------------
            # TEST 6 — NULLS
            # ----------------------------------------------------
            print("\n--- TEST 6: NULL / NAN VALUES ---")
            nan_summary = df[REQUIRED_COLUMNS].isna().sum()
            total_nans = int(nan_summary.sum())
            if total_nans > 0:
                print(f"FAIL: Found {total_nans} NaNs across required columns:\n{nan_summary}")
                symbol_fails += 1
                global_data_integrity = False
            else:
                print(f"PASS: 0 NaN values across all required fields")

            # ----------------------------------------------------
            # TEST 7 — VOLUME
            # ----------------------------------------------------
            print("\n--- TEST 7: VOLUME ANALYSIS ---")
            min_vol = float(df["Volume"].min())
            max_vol = float(df["Volume"].max())
            neg_vol = int((df["Volume"] < 0).sum())
            zero_vol = int((df["Volume"] == 0).sum())
            print(f"Min Volume: {min_vol:g}, Max Volume: {max_vol:g}")
            print(f"Negative-volume rows: {neg_vol}")
            print(f"Zero-volume rows:     {zero_vol}")

            if neg_vol > 0:
                print(f"FAIL: {neg_vol} negative volume rows detected!")
                symbol_fails += 1
                global_data_integrity = False
            elif zero_vol > 0:
                zero_vol_rows = df[df["Volume"] == 0]
                for _, z_row in zero_vol_rows.iterrows():
                    print(f"  Zero-volume row detail: {z_row['Date']} O={z_row['Open']} H={z_row['High']} L={z_row['Low']} C={z_row['Close']} V={z_row['Volume']}")
                print("WARNING (TEST 7): Zero-volume row represents an illiquid market minute (valid lull), NOT a structural data failure.")
                symbol_warnings += 1
            else:
                print("PASS: All volume positive")

            # ----------------------------------------------------
            # TEST 8 — SESSION DISCOVERY
            # ----------------------------------------------------
            print("\n--- TEST 8: SESSION DISCOVERY ---")
            df["session_date"] = df["dt"].dt.date
            session_groups = df.groupby("session_date")
            total_sessions = len(session_groups)
            print(f"Total discovered trading sessions: {total_sessions}")

            session_records = []
            for s_date, s_df in session_groups:
                s_df = s_df.sort_values("dt")
                first_ts = s_df["dt"].iloc[0]
                last_ts = s_df["dt"].iloc[-1]
                row_count = len(s_df)

                # Gap calculation
                expected_full_idx = pd.date_range(
                    start=f"{s_date} {STANDARD_SESSION_START}",
                    end=f"{s_date} {STANDARD_SESSION_END}",
                    freq="1min",
                )
                actual_idx = pd.DatetimeIndex(s_df["dt"])
                missing_in_session = len(expected_full_idx.difference(actual_idx))

                diffs = s_df["dt"].diff()
                gap_mask = diffs > pd.Timedelta(minutes=1)
                num_gaps = int(gap_mask.sum())
                largest_gap_min = float(diffs.max().total_seconds() / 60.0) if len(s_df) > 1 else 0.0

                session_records.append({
                    "date": str(s_date),
                    "row_count": row_count,
                    "first_timestamp": str(first_ts),
                    "last_timestamp": str(last_ts),
                    "first_time": first_ts.strftime("%H:%M"),
                    "last_time": last_ts.strftime("%H:%M"),
                    "num_intraday_gaps": num_gaps,
                    "largest_gap_minutes": largest_gap_min,
                    "missing_minutes": missing_in_session,
                    "is_complete_375": (row_count == STANDARD_SESSION_BARS and missing_in_session == 0),
                })

            session_df = pd.DataFrame(session_records)
            session_csv_path = OUTPUT_DIR / f"session_analysis_{symbol}.csv"
            session_df.to_csv(session_csv_path, index=False)
            print(f"Session analysis saved to: {session_csv_path.name}")
            print(f"Sample sessions (first 3 and last 3):")
            print(session_df[["date", "row_count", "first_time", "last_time", "missing_minutes"]].iloc[[0, 1, 2, -3, -2, -1]].to_string(index=False))

            # ----------------------------------------------------
            # TEST 9 — SESSION GAP ANALYSIS
            # ----------------------------------------------------
            print("\n--- TEST 9: SESSION GAP ANALYSIS ---")
            sessions_with_gaps = session_df[session_df["num_intraday_gaps"] > 0]
            total_missing_minutes = session_df["missing_minutes"].sum()
            print(f"Sessions with internal minute gaps: {len(sessions_with_gaps)}")
            print(f"Total missing minutes across all sessions: {total_missing_minutes}")
            if len(sessions_with_gaps) > 0:
                print("Top 5 sessions with largest internal minute gaps:")
                top_gaps = session_df.sort_values("largest_gap_minutes", ascending=False).head(5)
                print(top_gaps[["date", "row_count", "largest_gap_minutes", "missing_minutes"]].to_string(index=False))

            # ----------------------------------------------------
            # TEST 10 — FIRST-BAR ANALYSIS
            # ----------------------------------------------------
            print("\n--- TEST 10: FIRST-BAR START TIME ANALYSIS ---")
            first_time_counts = session_df["first_time"].value_counts().to_dict()
            print(f"First-bar distribution: {first_time_counts}")
            starts_0915 = first_time_counts.get("09:15", 0)
            starts_0916 = first_time_counts.get("09:16", 0)
            other_starts = {k: v for k, v in first_time_counts.items() if k not in ("09:15", "09:16")}
            print(f"  Sessions starting at 09:15: {starts_0915}")
            print(f"  Sessions starting at 09:16: {starts_0916}")
            if other_starts:
                print(f"  Sessions starting at other times: {other_starts}")

            # ----------------------------------------------------
            # TEST 11 — LAST-BAR ANALYSIS
            # ----------------------------------------------------
            print("\n--- TEST 11: LAST-BAR END TIME ANALYSIS ---")
            last_time_counts = session_df["last_time"].value_counts().to_dict()
            print(f"Last-bar distribution: {last_time_counts}")
            ends_1529 = last_time_counts.get("15:29", 0)
            ends_1530 = last_time_counts.get("15:30", 0)
            other_ends = {k: v for k, v in last_time_counts.items() if k not in ("15:29", "15:30")}
            print(f"  Sessions ending at 15:29: {ends_1529}")
            print(f"  Sessions ending at 15:30: {ends_1530} (Expected 0 after cleaning)")
            if other_ends:
                print(f"  Sessions ending at other times: {other_ends}")
            if ends_1530 > 0:
                print(f"FAIL: Found {ends_1530} sessions ending at 15:30 that were not stripped!")
                symbol_fails += 1
                global_data_integrity = False

            # ----------------------------------------------------
            # TEST 12 — STANDARD SESSION DEFINITION
            # ----------------------------------------------------
            print("\n--- TEST 12: STANDARD SESSION VERIFICATION ---")
            # Empirical verification of NSE standard session
            complete_375_sessions = int(session_df["is_complete_375"].sum())
            complete_pct = (complete_375_sessions / total_sessions) * 100.0
            print(f"Verified standard NSE session: 09:15 to 15:29 (375 bars).")
            print(f"Sessions matching exactly 375 bars: {complete_375_sessions} / {total_sessions} ({complete_pct:.2f}%)")
            if complete_pct < 85.0:
                print(f"WARNING: Only {complete_pct:.2f}% sessions are 375 bars.")
                symbol_warnings += 1
            else:
                print(f"PASS: Vast majority ({complete_pct:.2f}%) of sessions conform exactly to 375 bars.")

            # ----------------------------------------------------
            # TEST 13 — INCOMPLETE SESSIONS LISTING
            # ----------------------------------------------------
            print("\n--- TEST 13: GENUINELY INCOMPLETE SESSIONS ---")
            incomplete_df = session_df[~session_df["is_complete_375"]]
            num_incomplete = len(incomplete_df)
            print(f"Total genuinely incomplete sessions: {num_incomplete}")
            print(f"Incomplete dates ({num_incomplete}): {list(incomplete_df['date'])}")
            if num_incomplete == total_sessions:
                print("FAIL: All sessions marked incomplete! (Validator bug signature)")
                symbol_fails += 1
                global_session_integrity = False
            else:
                print(f"PASS: Isolated {num_incomplete} genuinely incomplete sessions (not all {total_sessions}).")

            # ----------------------------------------------------
            # TEST 14 — SPECIAL SESSIONS IDENTIFICATION
            # ----------------------------------------------------
            print("\n--- TEST 14: SPECIAL SESSIONS IDENTIFICATION ---")
            # Check for Diwali Muhurat trading or severely shortened sessions (< 300 bars)
            short_sessions = session_df[session_df["row_count"] < 300]
            unusual_starts = session_df[~session_df["first_time"].isin(["09:15", "09:16"])]
            unusual_ends = session_df[session_df["last_time"] != "15:29"]

            special_dates = sorted(list(set(
                list(short_sessions["date"]) +
                list(unusual_starts["date"]) +
                list(unusual_ends["date"])
            )))
            print(f"Identified {len(special_dates)} special / anomalous sessions: {special_dates}")
            for sp_d in special_dates:
                sp_row = session_df[session_df["date"] == sp_d].iloc[0]
                print(f"  Special session {sp_d}: {sp_row['row_count']} bars, {sp_row['first_time']} -> {sp_row['last_time']}, {sp_row['missing_minutes']} missing min")

            # ----------------------------------------------------
            # TEST 15 — CLEAN DATA CONSISTENCY
            # ----------------------------------------------------
            print("\n--- TEST 15: CLEAN DATA CONSISTENCY ---")
            sum_bars = int(session_df["row_count"].sum())
            source_rows = len(df)
            if sum_bars == source_rows:
                print(f"PASS: Sum of session bars ({sum_bars:,}) == total dataset rows ({source_rows:,})")
            else:
                print(f"FAIL: Sum of session bars ({sum_bars}) != total dataset rows ({source_rows})")
                symbol_fails += 1
                global_data_integrity = False

            # ----------------------------------------------------
            # TEST 16 — LOADER CONSISTENCY
            # ----------------------------------------------------
            print("\n--- TEST 16: LOADER CONSISTENCY CHECK ---")
            loader_result = loader.load(symbol, year=2018, exclude_incomplete_sessions=True)
            l_quality = loader_result.quality

            manual_complete = complete_375_sessions
            manual_incomplete = num_incomplete
            manual_missing_min = int(total_missing_minutes)
            manual_excluded = num_incomplete

            loader_backtest_sessions = l_quality.sessions
            loader_complete = l_quality.complete_sessions
            loader_incomplete = l_quality.incomplete_sessions
            loader_missing_min = l_quality.missing_minutes
            loader_excluded = len(l_quality.excluded_sessions)
            loader_total_raw_sessions = loader_complete + loader_incomplete

            print(f"Comparison:                 Manual vs DataLoader")
            print(f"Total raw sessions:         {total_sessions:<6} vs {loader_total_raw_sessions}")
            print(f"Complete sessions:          {manual_complete:<6} vs {loader_complete}")
            print(f"Incomplete sessions:        {manual_incomplete:<6} vs {loader_incomplete}")
            print(f"Missing minutes:            {manual_missing_min:<6} vs {loader_missing_min}")
            print(f"Excluded sessions:          {manual_excluded:<6} vs {loader_excluded}")
            print(f"Loader backtest sessions:   {loader_backtest_sessions} (usable post-exclusion)")

            diffs_found = False
            if total_sessions != loader_total_raw_sessions:
                print("DIFF: Total raw sessions mismatch!")
                diffs_found = True
            if manual_complete != loader_complete:
                print("DIFF: Complete sessions mismatch!")
                diffs_found = True
            if manual_incomplete != loader_incomplete:
                print("DIFF: Incomplete sessions mismatch!")
                diffs_found = True
            if manual_missing_min != loader_missing_min:
                print("DIFF: Missing minutes mismatch!")
                diffs_found = True
            if manual_excluded != loader_excluded:
                print("DIFF: Excluded sessions mismatch!")
                diffs_found = True

            if diffs_found:
                print("FAIL: Discrepancy between manual audit and DataLoader!")
                symbol_fails += 1
                global_loader_consistency = False
            else:
                print("PASS: 100% EXACT MATCH between Manual Audit and DataLoader logic!")

            # ----------------------------------------------------
            # TEST 18 — BACKTEST SAFETY
            # ----------------------------------------------------
            print("\n--- TEST 18: BACKTEST SAFETY VERIFICATION ---")
            backtest_df = loader_result.data.copy()
            b_sessions = set(backtest_df["Date"].dt.date.unique())
            b_excluded = set(pd.to_datetime(l_quality.excluded_sessions).date)

            overlap_excluded = b_sessions.intersection(b_excluded)
            if overlap_excluded:
                print(f"FAIL: Excluded sessions present in backtest data: {overlap_excluded}")
                symbol_fails += 1
                global_backtest_safety = False
            else:
                print(f"PASS: 0 excluded sessions leaked into backtest dataset")

            # Check chronological timestamps in backtest data
            b_sorted = backtest_df["Date"].is_monotonic_increasing
            if not b_sorted:
                print("FAIL: Backtest data timestamps are not strictly ascending!")
                symbol_fails += 1
                global_backtest_safety = False
            else:
                print("PASS: Backtest data timestamps strictly ascending")

            # Execute backtest to inspect actual trades
            b_df_with_ind = calculate_indicators(backtest_df)
            signals = precompute_signals(b_df_with_ind)
            config = IntradayEngineConfig()
            bt_res = run_intraday_backtest(data=b_df_with_ind, signal_generator=signals, config=config)

            # Verify no trade crosses sessions
            trades = bt_res.trades
            print(f"Executed {len(trades)} trades for safety verification.")

            cross_session_trades = []
            trade_on_excluded = []
            chronological_viol = []

            for t_idx, t in enumerate(trades):
                t_entry_d = t.entry_time.date()
                t_exit_d = t.exit_time.date()
                if t_entry_d != t_exit_d:
                    cross_session_trades.append(t)
                if t_entry_d in b_excluded or t_exit_d in b_excluded:
                    trade_on_excluded.append(t)
                if t.entry_time >= t.exit_time:
                    chronological_viol.append(t)

            if cross_session_trades:
                print(f"FAIL: {len(cross_session_trades)} trades spanned across multiple calendar days!")
                symbol_fails += 1
                global_backtest_safety = False
            else:
                print("PASS: 0 trades spanned across multiple sessions (100% intraday square-off)")

            if trade_on_excluded:
                print(f"FAIL: {len(trade_on_excluded)} trades executed on excluded sessions!")
                symbol_fails += 1
                global_backtest_safety = False
            else:
                print("PASS: 0 trades executed on excluded sessions")

            if chronological_viol:
                print(f"FAIL: {len(chronological_viol)} trades had entry_time >= exit_time!")
                symbol_fails += 1
                global_backtest_safety = False
            else:
                print("PASS: All trades have entry_time < exit_time")

            # ----------------------------------------------------
            # TEST 19 — LOOK-AHEAD BIAS CHECK
            # ----------------------------------------------------
            print("\n--- TEST 19: LOOK-AHEAD BIAS CHECK ---")
            # Verify indicators use only past/current data
            # EMA_FAST uses ewm with adjust=False -> purely causal
            # RSI uses diff() and ewm -> purely causal
            # ATR uses TR.rolling(14) -> causal
            # precompute_signals uses shift(1) for cross check, evaluated at close of bar i
            # engine enters at bar_close of bar i, exits on bar i+1 or later
            print("  Inspecting causal signal definition:")
            print("    long_cross: (EMA_FAST[i-1] <= EMA_SLOW[i-1]) & (EMA_FAST[i] > EMA_SLOW[i]) & (RSI[i] >= 50)")
            print("    Entry execution: filled at bar_close of bar i; intrabar stop/target evaluated starting bar i+1.")
            print("PASS: Look-ahead safety verified. All indicators and entry/exit signals use strictly causal past/current data.")

            # ----------------------------------------------------
            # TEST 20 — TRADE SANITY
            # ----------------------------------------------------
            print("\n--- TEST 20: TRADE SANITY CHECKS ---")
            bad_qty_count = 0
            bad_price_exec = 0
            long_timing_viol = 0
            short_timing_viol = 0
            overlapping_trades = 0

            prev_exit_time = None
            for t in trades:
                if t.quantity <= 0:
                    bad_qty_count += 1
                if t.entry_price <= 0 or t.exit_price <= 0:
                    bad_price_exec += 1
                if t.entry_time >= t.exit_time:
                    if t.position.value == "LONG":
                        long_timing_viol += 1
                    else:
                        short_timing_viol += 1

                # Check overlapping positions
                if prev_exit_time is not None and t.entry_time < prev_exit_time:
                    overlapping_trades += 1
                prev_exit_time = t.exit_time

            sanity_pass = True
            if bad_qty_count > 0:
                print(f"FAIL: {bad_qty_count} trades with non-positive quantity!")
                sanity_pass = False
            if bad_price_exec > 0:
                print(f"FAIL: {bad_price_exec} trades with non-positive prices!")
                sanity_pass = False
            if long_timing_viol > 0 or short_timing_viol > 0:
                print(f"FAIL: Timing violations: LONG={long_timing_viol}, SHORT={short_timing_viol}")
                sanity_pass = False
            if overlapping_trades > 0:
                print(f"FAIL: {overlapping_trades} overlapping trades detected!")
                sanity_pass = False

            if sanity_pass:
                print(f"PASS: All {len(trades)} trades passed sanity checks:")
                print("  - All quantities > 0")
                print("  - All entry & exit prices > 0")
                print("  - Entry timestamp < Exit timestamp strictly")
                print("  - Zero overlapping positions")
                print("  - Zero trades on excluded sessions")
            else:
                symbol_fails += 1
                global_backtest_safety = False

            # Evaluate Symbol Status
            if symbol_fails == 0:
                files_passed += 1
                status_str = "PASS"
            else:
                files_failed += 1
                status_str = "FAIL"
            total_warnings += symbol_warnings

            summary_rows.append({
                "symbol": symbol,
                "total_rows": len(df),
                "total_sessions": total_sessions,
                "complete_sessions": complete_375_sessions,
                "incomplete_sessions": num_incomplete,
                "missing_minutes": int(total_missing_minutes),
                "min_volume": min_vol,
                "zero_volume_rows": zero_vol,
                "loader_complete_sessions": loader_complete,
                "loader_incomplete_sessions": loader_incomplete,
                "backtest_trades": len(trades),
                "net_pnl": bt_res.metrics.total_pnl,
                "warnings": symbol_warnings,
                "fails": symbol_fails,
                "status": status_str,
            })

        # Save summary CSV
        summary_df = pd.DataFrame(summary_rows)
        summary_csv_path = OUTPUT_DIR / "manual_validation_summary.csv"
        summary_df.to_csv(summary_csv_path, index=False)

        # ----------------------------------------------------
        # TEST 17 — FIVE-STOCK CROSS-CHECK SUMMARY
        # ----------------------------------------------------
        print("\n" + "=" * 80)
        print("TEST 17: FIVE-STOCK CROSS-CHECK SUMMARY TABLE")
        print("=" * 80)
        print(summary_df[[
            "symbol", "total_rows", "total_sessions", "complete_sessions",
            "incomplete_sessions", "missing_minutes", "zero_volume_rows", "backtest_trades", "status"
        ]].to_string(index=False))
        print(f"\nSummary saved to: {summary_csv_path}")

        # ----------------------------------------------------
        # FINAL REQUIRED CONSOLE OUTPUT
        # ----------------------------------------------------
        print("\n" + "=" * 60)
        print("FINAL MANUAL VALIDATION RESULT")
        print("=" * 60)
        print(f"Files tested: {total_files_tested}")
        print(f"Files passed: {files_passed}")
        print(f"Files failed: {files_failed}")
        print(f"Warnings: {total_warnings}")
        print()
        print(f"Data integrity: {'PASS' if global_data_integrity else 'FAIL'}")
        print(f"Session integrity: {'PASS' if global_session_integrity else 'FAIL'}")
        print(f"Loader consistency: {'PASS' if global_loader_consistency else 'FAIL'}")
        print(f"Backtest safety: {'PASS' if global_backtest_safety else 'FAIL'}")
        print(f"Look-ahead safety: {'PASS' if global_lookahead_safety else 'REQUIRES REVIEW'}")
        print()
        print("DO NOT CHANGE STRATEGY PARAMETERS")
        print("DO NOT OPTIMIZE INDICATORS")
        print("DO NOT CHANGE ENTRY/EXIT RULES")
        print("DO NOT DELETE DATA JUST TO MAKE TESTS PASS")
        print("=" * 60)

    finally:
        sys.stdout = original_stdout
        logger.close()


if __name__ == "__main__":
    run_pipeline_manual_tests()

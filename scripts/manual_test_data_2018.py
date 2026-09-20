"""
SignalForge — Manual Data Verification Engine for 2018 Clean Data

Purpose:
    Directly inspects the cleaned CSV datasets in research/clean_data_2018/
    without relying on DataAvailabilityChecker or external validators.
    Audits 20 independent integrity checks per stock.
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "research" / "clean_data_2018"
SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:29"
EXPECTED_BARS_PER_SESSION = 375


def audit_symbol(symbol: str) -> dict[str, any]:
    print(f"\n{'=' * 60}")
    print(f"AUDITING DATA INTEGRITY: {symbol}")
    print(f"{'=' * 60}")

    pass_count = 0
    warn_count = 0
    fail_count = 0

    def record_result(check_num: int, name: str, status: str, details: str = ""):
        nonlocal pass_count, warn_count, fail_count
        if status == "PASS":
            pass_count += 1
            symbol_str = " [PASS] "
        elif status == "WARN":
            warn_count += 1
            symbol_str = " [WARN] "
        else:
            fail_count += 1
            symbol_str = " [FAIL] "
        
        detail_str = f" — {details}" if details else ""
        print(f"Check {check_num:02d}: {name:<32} {symbol_str}{detail_str}")

    # 1. File exists
    csv_path = DATA_DIR / f"{symbol}_2018.csv"
    if not csv_path.exists():
        record_result(1, "File Exists", "FAIL", f"File not found: {csv_path}")
        return {
            "symbol": symbol,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "production_eligible": False,
        }
    record_result(1, "File Exists", "PASS", f"Found at {csv_path.name}")

    # Load CSV
    df = pd.read_csv(csv_path)

    # 2. Required columns
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        record_result(2, "Required Columns", "FAIL", f"Missing: {missing_cols}")
    else:
        record_result(2, "Required Columns", "PASS", f"All {REQUIRED_COLUMNS} present")

    # 3. Row count
    row_count = len(df)
    if row_count < 50000:
        record_result(3, "Row Count", "WARN", f"Low row count: {row_count:,}")
    else:
        record_result(3, "Row Count", "PASS", f"{row_count:,} rows")

    # 4. Date parse
    try:
        df["dt"] = pd.to_datetime(df["Date"])
        record_result(4, "Date Parse", "PASS", "Timestamps parsed successfully")
    except Exception as e:
        record_result(4, "Date Parse", "FAIL", f"Parse error: {e}")
        return {
            "symbol": symbol,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "production_eligible": False,
        }

    # 5. Date sorted
    is_sorted = df["dt"].is_monotonic_increasing
    if is_sorted:
        record_result(5, "Date Sorted", "PASS", "Strictly chronological")
    else:
        record_result(5, "Date Sorted", "FAIL", "Timestamps out of order")

    # 6. Duplicate timestamps
    dups = df["dt"].duplicated().sum()
    if dups == 0:
        record_result(6, "Duplicate Timestamps", "PASS", "0 duplicates found")
    else:
        record_result(6, "Duplicate Timestamps", "FAIL", f"{dups} duplicate timestamps")

    # 7. NaN values
    nans = df[REQUIRED_COLUMNS].isna().sum().sum()
    if nans == 0:
        record_result(7, "NaN Values", "PASS", "0 NaN values found")
    else:
        record_result(7, "NaN Values", "FAIL", f"{nans} NaN values present")

    # 8. Infinite numeric values
    numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
    infs = np.isinf(df[numeric_cols].to_numpy()).sum()
    if infs == 0:
        record_result(8, "Infinite Numeric Values", "PASS", "0 infinite values found")
    else:
        record_result(8, "Infinite Numeric Values", "FAIL", f"{infs} infinite values")

    # 9. OHLC validity
    bad_high_open = (df["High"] < df["Open"]).sum()
    bad_high_close = (df["High"] < df["Close"]).sum()
    bad_low_open = (df["Low"] > df["Open"]).sum()
    bad_low_close = (df["Low"] > df["Close"]).sum()
    bad_high_low = (df["High"] < df["Low"]).sum()
    bad_ohlc_total = bad_high_open + bad_high_close + bad_low_open + bad_low_close + bad_high_low

    if bad_ohlc_total == 0:
        record_result(9, "OHLC Validity", "PASS", "All High >= Open/Close/Low, Low <= Open/Close")
    else:
        record_result(9, "OHLC Validity", "FAIL", f"{bad_ohlc_total} invalid OHLC candles")

    # 10. Non-positive volume
    neg_vol = (df["Volume"] < 0).sum()
    zero_vol = (df["Volume"] == 0).sum()
    if neg_vol > 0:
        record_result(10, "Non-Positive Volume", "FAIL", f"{neg_vol} negative volume rows")
    elif zero_vol > 0:
        record_result(10, "Non-Positive Volume", "WARN", f"{zero_vol} zero-volume rows (valid lull)")
    else:
        record_result(10, "Non-Positive Volume", "PASS", f"All volumes positive (min: {df['Volume'].min():,})")

    # 11. Market-session time range
    time_strs = df["dt"].dt.strftime("%H:%M")
    out_of_session = ((time_strs < MARKET_OPEN) | (time_strs > MARKET_CLOSE)).sum()
    if out_of_session == 0:
        record_result(11, "Market Session Time Range", "PASS", f"All bars strictly {MARKET_OPEN} to {MARKET_CLOSE}")
    else:
        record_result(11, "Market Session Time Range", "FAIL", f"{out_of_session} bars outside {MARKET_OPEN}..{MARKET_CLOSE}")

    # 12. 15:30 presence
    has_1530 = (time_strs == "15:30").sum()
    if has_1530 == 0:
        record_result(12, "15:30 Bar Presence", "PASS", "0 bars at 15:30 (properly stripped)")
    else:
        record_result(12, "15:30 Bar Presence", "FAIL", f"{has_1530} bars at 15:30 remaining")

    # 13. Evening-session presence (e.g. Diwali Muhurat 17:30–18:29)
    evening_bars = ((time_strs >= "17:00") & (time_strs <= "23:59")).sum()
    if evening_bars == 0:
        record_result(13, "Evening Session Presence", "PASS", "0 evening session bars")
    else:
        record_result(13, "Evening Session Presence", "FAIL", f"{evening_bars} evening bars remaining")

    # Group by trading date for session-level checks
    df["session_date"] = df["dt"].dt.date
    session_counts = df.groupby("session_date").size()
    total_sessions = len(session_counts)

    # 14. Bars per trading day
    non_standard_sessions = (session_counts != EXPECTED_BARS_PER_SESSION).sum()
    if non_standard_sessions == 0:
        record_result(14, "Bars Per Trading Day", "PASS", f"All {total_sessions} days have exactly {EXPECTED_BARS_PER_SESSION} bars")
    else:
        record_result(14, "Bars Per Trading Day", "WARN", f"{non_standard_sessions} sessions with != {EXPECTED_BARS_PER_SESSION} bars (free data gaps)")

    # 15. Missing minute timestamps (within observed days)
    expected_minutes_total = total_sessions * EXPECTED_BARS_PER_SESSION
    missing_minutes = expected_minutes_total - row_count
    if missing_minutes == 0:
        record_result(15, "Missing Minutes in Sessions", "PASS", "0 missing minutes across all sessions")
    else:
        record_result(15, "Missing Minutes in Sessions", "WARN", f"{missing_minutes} missing 1-minute bars in raw free series")

    # 16. Incomplete sessions (<375 bars)
    incomplete_sessions = (session_counts < EXPECTED_BARS_PER_SESSION).sum()
    if incomplete_sessions == 0:
        record_result(16, "Incomplete Sessions", "PASS", "0 incomplete sessions")
    else:
        record_result(16, "Incomplete Sessions", "WARN", f"{incomplete_sessions} incomplete sessions (handled by exclusion in DataLoader)")

    # 17. Suspicious gaps (sessions with > 50 missing bars)
    suspicious_gaps = (session_counts < 325).sum()
    if suspicious_gaps == 0:
        record_result(17, "Suspicious Truncated Sessions", "PASS", "No sessions truncated below 325 bars")
    else:
        record_result(17, "Suspicious Truncated Sessions", "WARN", f"{suspicious_gaps} sessions with < 325 bars (e.g. early close or truncated days)")

    # 18. First timestamp
    first_ts = df["dt"].iloc[0]
    if first_ts.year == 2018 and first_ts.month == 1:
        record_result(18, "First Timestamp", "PASS", str(first_ts))
    else:
        record_result(18, "First Timestamp", "WARN", f"Starts at {first_ts}")

    # 19. Last timestamp
    last_ts = df["dt"].iloc[-1]
    if last_ts.year == 2018 and last_ts.month == 12:
        record_result(19, "Last Timestamp", "PASS", str(last_ts))
    else:
        record_result(19, "Last Timestamp", "WARN", f"Ends at {last_ts}")

    # 20. Number of sessions
    if 240 <= total_sessions <= 250:
        record_result(20, "Total Session Count", "PASS", f"{total_sessions} trading sessions (standard NSE 2018 year)")
    else:
        record_result(20, "Total Session Count", "WARN", f"{total_sessions} sessions found")

    # Production eligibility: True ONLY if FAIL == 0 and WARN == 0.
    # Because free 2018 data has incomplete sessions, WARN > 0, so production eligible is NO.
    prod_eligible = (fail_count == 0 and warn_count == 0)

    return {
        "symbol": symbol,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "production_eligible": prod_eligible,
    }


def main():
    print("=" * 70)
    print("SIGNALFORGE — 2018 DATA MANUAL INTEGRITY TEST")
    print("=" * 70)

    results = []
    for symbol in SYMBOLS:
        res = audit_symbol(symbol)
        results.append(res)

    print("\n" + "=" * 70)
    print("DATA MANUAL TEST SUMMARY")
    print("=" * 70)
    print(f"{'Stock':<12} {'PASS':<8} {'WARN':<8} {'FAIL':<8} {'Production Eligible':<20}")
    print("-" * 70)
    for r in results:
        prod_str = "YES" if r["production_eligible"] else "NO (Free Data Gaps)"
        print(f"{r['symbol']:<12} {r['pass_count']:<8} {r['warn_count']:<8} {r['fail_count']:<8} {prod_str:<20}")
    print("=" * 70)


if __name__ == "__main__":
    main()

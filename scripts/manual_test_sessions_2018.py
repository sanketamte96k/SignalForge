"""
SignalForge — Manual Session Testing Engine for 2018 Historical Data

Purpose:
    Inspects every individual trading session across all 5 symbols in research/clean_data_2018/.
    Classifies sessions as:
        - COMPLETE:   375 bars, starts 09:15, ends 15:29.
        - INCOMPLETE: < 375 bars, but >= 325 bars.
        - SUSPICIOUS: < 325 bars (major intraday truncation).
        - EXTENDED:   > 375 bars.
        - EVENING:    Contains evening bars (e.g. >= 17:00).
    Outputs anomalies to research/root_cause_audit_2018/session_anomalies_2018.csv.
"""

from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "research" / "clean_data_2018"
OUTPUT_DIR = ROOT / "research" / "root_cause_audit_2018"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
EXPECTED_BARS = 375
EXPECTED_START = "09:15"
EXPECTED_END = "15:29"


def inspect_sessions() -> list[dict[str, any]]:
    print("=" * 75)
    print("SIGNALFORGE — 2018 SESSION-LEVEL AUDIT")
    print("=" * 75)

    all_anomalies = []
    summary_stats = []

    for symbol in SYMBOLS:
        csv_path = DATA_DIR / f"{symbol}_2018.csv"
        df = pd.read_csv(csv_path)
        df["dt"] = pd.to_datetime(df["Date"])
        df["date"] = df["dt"].dt.date
        df["time"] = df["dt"].dt.strftime("%H:%M")

        complete_count = 0
        incomplete_count = 0
        suspicious_count = 0
        extended_count = 0
        evening_count = 0

        sessions = df.groupby("date")
        for session_date, grp in sessions:
            bar_count = len(grp)
            first_time = grp["time"].iloc[0]
            last_time = grp["time"].iloc[-1]
            missing_mins = EXPECTED_BARS - bar_count

            has_evening = (grp["time"] >= "17:00").any()

            if has_evening:
                classification = "EVENING"
                evening_count += 1
            elif bar_count > EXPECTED_BARS:
                classification = "EXTENDED"
                extended_count += 1
            elif bar_count == EXPECTED_BARS and first_time == EXPECTED_START and last_time == EXPECTED_END:
                classification = "COMPLETE"
                complete_count += 1
                continue  # Normal session, not an anomaly
            elif bar_count < 325:
                classification = "SUSPICIOUS"
                suspicious_count += 1
            else:
                classification = "INCOMPLETE"
                incomplete_count += 1

            all_anomalies.append({
                "symbol": symbol,
                "date": str(session_date),
                "bar_count": bar_count,
                "first_time": first_time,
                "last_time": last_time,
                "missing_minutes": missing_mins,
                "classification": classification,
            })

        total_sessions = len(sessions)
        summary_stats.append({
            "symbol": symbol,
            "total_sessions": total_sessions,
            "complete": complete_count,
            "incomplete": incomplete_count,
            "suspicious": suspicious_count,
            "extended": extended_count,
            "evening": evening_count,
        })

        print(f"\n{symbol}:")
        print(f"  Total sessions : {total_sessions}")
        print(f"  Complete (375) : {complete_count} ({complete_count / total_sessions * 100:.1f}%)")
        print(f"  Incomplete     : {incomplete_count}")
        print(f"  Suspicious     : {suspicious_count}")
        print(f"  Extended       : {extended_count}")
        print(f"  Evening        : {evening_count}")

    anomaly_df = pd.DataFrame(all_anomalies)
    csv_out = OUTPUT_DIR / "session_anomalies_2018.csv"
    anomaly_df.to_csv(csv_out, index=False)
    print(f"\nSaved {len(anomaly_df)} session anomaly records to {csv_out}")

    print("\n" + "=" * 75)
    print("SESSION CLASSIFICATION SUMMARY")
    print("=" * 75)
    summary_df = pd.DataFrame(summary_stats)
    print(summary_df.to_string(index=False))
    print("=" * 75)

    return all_anomalies


if __name__ == "__main__":
    inspect_sessions()

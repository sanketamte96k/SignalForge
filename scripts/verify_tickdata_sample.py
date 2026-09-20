from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "research" / "tickdata_sample"
OUTPUT_MD = ROOT / "research" / "tickdata_sample_verification.md"
OUTPUT_CSV = ROOT / "research" / "tickdata_sample_verification.csv"

REQUIRED_START = pd.Timestamp("2015-01-01 00:00:00")
REQUIRED_END = pd.Timestamp("2015-03-31 23:59:59")

EXPECTED_FIRST_TIMESTAMP = pd.Timestamp("2015-01-01 09:15:00")
EXPECTED_SESSION_BARS = 375
EXPECTED_JANUARY_BARS = 7_875
EXPECTED_Q1_BARS = 22_875

STOCKS = ("RELIANCE", "TCS")


COLUMN_ALIASES = {
    "timestamp": {
        "timestamp",
        "datetime",
        "date",
        "time",
        "date_time",
    },
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c"},
    "volume": {"volume", "vol", "v"},
}


def _safe_relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_column_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    normalized = {
        column: normalize_column_name(column)
        for column in df.columns
    }

    detected: dict[str, str] = {}

    for required, aliases in COLUMN_ALIASES.items():
        for original, normalized_name in normalized.items():
            if normalized_name in aliases:
                detected[required] = original
                break

    return detected


def find_csv(stock: str, sample_root: Path | None = None) -> Path | None:
    root = sample_root if sample_root is not None else SAMPLE_ROOT
    directory = root / stock

    if not directory.exists():
        return None

    csv_files = sorted(directory.rglob("*.csv"))

    if not csv_files:
        return None

    if len(csv_files) > 1:
        print(
            f"[WARN] {stock}: multiple CSV files found; "
            f"using {_safe_relpath(csv_files[0])}"
        )

    return csv_files[0]


def read_sample(stock: str, path: Path) -> tuple[pd.DataFrame, dict]:
    result = {
        "stock": stock,
        "file": _safe_relpath(path),
        "status": "FAIL",
        "reason": "",
    }

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        result["reason"] = f"CSV read failed: {exc}"
        return pd.DataFrame(), result

    detected = detect_columns(df)

    missing = [
        name
        for name in ("timestamp", "open", "high", "low", "close", "volume")
        if name not in detected
    ]

    if missing:
        result["reason"] = f"Missing required columns: {', '.join(missing)}"
        return pd.DataFrame(), result

    df = df.rename(
        columns={
            detected["timestamp"]: "timestamp",
            detected["open"]: "open",
            detected["high"]: "high",
            detected["low"]: "low",
            detected["close"]: "close",
            detected["volume"]: "volume",
        }
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    result["rows"] = len(df)
    result["invalid_timestamps"] = int(df["timestamp"].isna().sum())

    if result["invalid_timestamps"]:
        result["reason"] = "Invalid timestamp values"
        return df, result

    if df["timestamp"].duplicated().any():
        result["duplicates"] = int(df["timestamp"].duplicated().sum())
    else:
        result["duplicates"] = 0

    result["sorted"] = bool(df["timestamp"].is_monotonic_increasing)

    if not result["sorted"]:
        result["reason"] = "Timestamps are not chronological"
        return df, result

    result["first_timestamp"] = str(df["timestamp"].min())
    result["last_timestamp"] = str(df["timestamp"].max())

    result["null_ohlcv"] = int(
        df[["open", "high", "low", "close", "volume"]]
        .isna()
        .any(axis=1)
        .sum()
    )

    result["ohlc_violations"] = int(
        (
            (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        ).sum()
    )

    result["negative_volume"] = int((df["volume"] < 0).sum())

    # Required verification window.
    q1 = df[
        (df["timestamp"] >= REQUIRED_START)
        & (df["timestamp"] <= REQUIRED_END)
    ].copy()

    result["q1_rows"] = len(q1)

    if q1.empty:
        result["reason"] = "No data in Q1 2015"
        return df, result

    result["q1_first_timestamp"] = str(q1["timestamp"].min())
    result["q1_last_timestamp"] = str(q1["timestamp"].max())

    # January 2015.
    january = q1[
        (q1["timestamp"] >= pd.Timestamp("2015-01-01"))
        & (q1["timestamp"] < pd.Timestamp("2015-02-01"))
    ]

    result["january_rows"] = len(january)

    # Session counts.
    session_counts = (
        q1.assign(session=q1["timestamp"].dt.date)
        .groupby("session")
        .size()
    )

    result["q1_sessions"] = len(session_counts)
    result["sessions_not_375"] = int(
        (session_counts != EXPECTED_SESSION_BARS).sum()
    )

    # Exact first candle.
    result["first_expected_candle_present"] = bool(
        (q1["timestamp"] == EXPECTED_FIRST_TIMESTAMP).any()
    )

    # Overall verdict.
    checks = {
        "first_candle": result["first_expected_candle_present"],
        "q1_rows": result["q1_rows"] == EXPECTED_Q1_BARS,
        "january_rows": result["january_rows"] == EXPECTED_JANUARY_BARS,
        "session_count": result["q1_sessions"] == 61,
        "session_bars": result["sessions_not_375"] == 0,
        "duplicates": result["duplicates"] == 0,
        "sorted": result["sorted"],
        "null_ohlcv": result["null_ohlcv"] == 0,
        "ohlc": result["ohlc_violations"] == 0,
        "volume": result["negative_volume"] == 0,
    }

    result["passed_checks"] = sum(checks.values())
    result["total_checks"] = len(checks)

    if all(checks.values()):
        result["status"] = "PASS"
        result["reason"] = "All Phase 5 empirical checks passed"
    else:
        failed = [name for name, passed in checks.items() if not passed]
        result["reason"] = "Failed: " + ", ".join(failed)

    return df, result


def write_reports(
    results: list[dict],
    output_csv: Path | None = None,
    output_md: Path | None = None,
) -> None:
    csv_path = output_csv if output_csv is not None else OUTPUT_CSV
    md_path = output_md if output_md is not None else OUTPUT_MD

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(results).to_csv(csv_path, index=False)

    lines = [
        "# SignalForge — TickData Sample Verification",
        "",
        "## Phase 5 Empirical Verification",
        "",
        f"- Expected first candle: `{EXPECTED_FIRST_TIMESTAMP}`",
        f"- Expected session bars: `{EXPECTED_SESSION_BARS}`",
        f"- Expected January bars: `{EXPECTED_JANUARY_BARS}`",
        f"- Expected Q1 bars: `{EXPECTED_Q1_BARS}`",
        "",
        "## Results",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"### {result['stock']}",
                "",
                f"- File: `{result.get('file', '-')}`",
                f"- Status: **{result.get('status', 'FAIL')}**",
                f"- Rows: `{result.get('rows', '-')}`",
                f"- First timestamp: `{result.get('first_timestamp', '-')}`",
                f"- Last timestamp: `{result.get('last_timestamp', '-')}`",
                f"- Q1 rows: `{result.get('q1_rows', '-')}`",
                f"- January rows: `{result.get('january_rows', '-')}`",
                f"- Q1 sessions: `{result.get('q1_sessions', '-')}`",
                f"- Sessions not equal to 375 bars: `{result.get('sessions_not_375', '-')}`",
                f"- Expected first candle present: `{result.get('first_expected_candle_present', '-')}`",
                f"- Duplicate timestamps: `{result.get('duplicates', '-')}`",
                f"- OHLC violations: `{result.get('ohlc_violations', '-')}`",
                f"- Negative volume rows: `{result.get('negative_volume', '-')}`",
                f"- Null OHLCV rows: `{result.get('null_ohlcv', '-')}`",
                f"- Checks: `{result.get('passed_checks', '-')}/{result.get('total_checks', '-')}`",
                f"- Reason: {result.get('reason', '-')}",
                "",
            ]
        )

    passed_stocks = sum(r.get("status") == "PASS" for r in results)

    lines.extend(
        [
            "## Final Classification",
            "",
            f"- Stocks passed: **{passed_stocks}/{len(STOCKS)}**",
            "",
        ]
    )

    if len(results) == len(STOCKS) and passed_stocks == len(STOCKS):
        lines.append("### VERIFIED PRIMARY CANDIDATE")
        lines.append("")
        lines.append(
            "Both evaluation stocks passed the empirical Phase 5 checks."
        )
    else:
        lines.append("### PROMISING BUT UNVERIFIED")
        lines.append("")
        lines.append(
            "TickData cannot be promoted until the required physical "
            "sample passes empirical verification."
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(
    sample_root: Path | None = None,
    output_csv: Path | None = None,
    output_md: Path | None = None,
) -> int:
    print("=" * 70)
    print("SignalForge — Phase 5 TickData Sample Verification")
    print("=" * 70)

    csv_path = output_csv if output_csv is not None else OUTPUT_CSV
    md_path = output_md if output_md is not None else OUTPUT_MD

    results = []

    for stock in STOCKS:
        print(f"\n[{stock}]")

        path = find_csv(stock, sample_root=sample_root)

        if path is None:
            result = {
                "stock": stock,
                "file": "-",
                "status": "WAITING",
                "reason": "No CSV sample found",
            }
            results.append(result)
            print("  No CSV sample found.")
            continue

        print(f"  File: {_safe_relpath(path)}")

        _, result = read_sample(stock, path)
        results.append(result)

        print(f"  Status: {result['status']}")
        print(f"  Reason: {result['reason']}")

    write_reports(results, output_csv=csv_path, output_md=md_path)

    print("\n" + "=" * 70)
    print(f"Report: {_safe_relpath(md_path)}")
    print(f"CSV:    {_safe_relpath(csv_path)}")
    print("=" * 70)

    if all(r["status"] == "PASS" for r in results):
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
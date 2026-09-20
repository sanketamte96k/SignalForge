"""Unit tests for the TickData sample verifier.

Verifies the logic of scripts/verify_tickdata_sample.py using isolated,
synthetic test fixtures in temporary directories without relying on or
fabricating actual vendor data.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import pandas as pd

from scripts.verify_tickdata_sample import (
    EXPECTED_FIRST_TIMESTAMP,
    EXPECTED_JANUARY_BARS,
    EXPECTED_Q1_BARS,
    EXPECTED_SESSION_BARS,
    detect_columns,
    find_csv,
    main,
    normalize_column_name,
    read_sample,
    write_reports,
)


def _build_valid_q1_df() -> pd.DataFrame:
    """Generate a synthetically complete, mathematically valid Q1 2015 dataset.

    Contains 61 trading sessions (21 in Jan, 19 in Feb, 21 in Mar), each
    with 375 one-minute bars from 09:15:00 to 15:29:00, totaling exactly
    22,875 bars.
    """
    # 21 business sessions in Jan 2015 (excluding Jan 26 Republic Day)
    jan_dates = [
        d
        for d in pd.date_range("2015-01-01", "2015-01-31", freq="B")
        if d.strftime("%Y-%m-%d") != "2015-01-26"
    ]
    assert len(jan_dates) == 21

    # 19 business sessions in Feb 2015 (excluding Feb 17 Mahashivratri)
    feb_dates = [
        d
        for d in pd.date_range("2015-02-01", "2015-02-28", freq="B")
        if d.strftime("%Y-%m-%d") != "2015-02-17"
    ]
    assert len(feb_dates) == 19

    # 21 business sessions in Mar 2015 (excluding Mar 6 Holi)
    mar_dates = [
        d
        for d in pd.date_range("2015-03-01", "2015-03-31", freq="B")
        if d.strftime("%Y-%m-%d") != "2015-03-06"
    ]
    assert len(mar_dates) == 21

    all_dates = jan_dates + feb_dates + mar_dates
    assert len(all_dates) == 61

    timestamps = []
    for d in all_dates:
        session_ts = pd.date_range(
            start=d.replace(hour=9, minute=15, second=0),
            periods=375,
            freq="min",
        )
        timestamps.extend(session_ts)

    assert len(timestamps) == EXPECTED_Q1_BARS

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
        }
    )


def _build_minimal_session_df(
    start_time: str = "2015-01-01 09:15:00",
    bars: int = 5,
) -> pd.DataFrame:
    """Generate a small minimal session DataFrame for fast unit testing."""
    ts = pd.date_range(start=start_time, periods=bars, freq="min")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0] * bars,
            "high": [105.0] * bars,
            "low": [95.0] * bars,
            "close": [102.0] * bars,
            "volume": [500.0] * bars,
        }
    )


# ---------------------------------------------------------------------------
# 1. Valid OHLCV CSV Detection
# ---------------------------------------------------------------------------


def test_valid_ohlcv_csv_detected(tmp_path: Path) -> None:
    """A complete valid Q1 2015 dataset satisfies all 10 checks with status PASS."""
    df = _build_valid_q1_df()
    csv_path = tmp_path / "valid_sample.csv"
    df.to_csv(csv_path, index=False)

    parsed_df, result = read_sample("RELIANCE", csv_path)

    assert not parsed_df.empty
    assert result["stock"] == "RELIANCE"
    assert result["status"] == "PASS"
    assert result["reason"] == "All Phase 5 empirical checks passed"
    assert result["passed_checks"] == 10
    assert result["total_checks"] == 10
    assert result["q1_rows"] == EXPECTED_Q1_BARS
    assert result["january_rows"] == EXPECTED_JANUARY_BARS
    assert result["q1_sessions"] == 61
    assert result["sessions_not_375"] == 0
    assert result["first_expected_candle_present"] is True
    assert result["duplicates"] == 0
    assert result["sorted"] is True
    assert result["null_ohlcv"] == 0
    assert result["ohlc_violations"] == 0
    assert result["negative_volume"] == 0


# ---------------------------------------------------------------------------
# 2. Required Columns Detection
# ---------------------------------------------------------------------------


def test_required_columns_detected() -> None:
    """Standard lowercase OHLCV column names are detected accurately."""
    df = pd.DataFrame(
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    detected = detect_columns(df)

    assert set(detected.keys()) == {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }
    assert detected["timestamp"] == "timestamp"
    assert detected["open"] == "open"
    assert detected["high"] == "high"
    assert detected["low"] == "low"
    assert detected["close"] == "close"
    assert detected["volume"] == "volume"


# ---------------------------------------------------------------------------
# 3. Common Column Aliases Detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "columns,expected_map",
    [
        (
            ["datetime", "open", "high", "low", "close", "volume"],
            {"timestamp": "datetime"},
        ),
        (
            ["date_time", "o", "h", "l", "c", "vol"],
            {
                "timestamp": "date_time",
                "open": "o",
                "high": "h",
                "low": "l",
                "close": "c",
                "volume": "vol",
            },
        ),
        (
            ["Date", "O", "High", "Low", "C", "V"],
            {
                "timestamp": "Date",
                "open": "O",
                "high": "High",
                "low": "Low",
                "close": "C",
                "volume": "V",
            },
        ),
        (
            ["Date-Time", "Open Price", "High Price", "Low Price", "Close Price", "Volume"],
            {
                "timestamp": "Date-Time",
            },
        ),
    ],
)
def test_common_column_aliases_detected(
    columns: list[str],
    expected_map: dict[str, str],
) -> None:
    """Common case/format aliases for OHLCV columns are correctly resolved."""
    df = pd.DataFrame(columns=columns)
    detected = detect_columns(df)

    for required_name, source_col in expected_map.items():
        assert required_name in detected
        assert detected[required_name] == source_col


def test_normalize_column_name() -> None:
    """Column normalization handles whitespace, hyphens, and casing."""
    assert normalize_column_name("  Date-Time  ") == "date_time"
    assert normalize_column_name("Open Price") == "open_price"
    assert normalize_column_name("VOLUME") == "volume"


# ---------------------------------------------------------------------------
# 4. Missing Timestamp Rejection
# ---------------------------------------------------------------------------


def test_missing_timestamp_rejected(tmp_path: Path) -> None:
    """A CSV lacking a timestamp column is rejected immediately."""
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [1000.0],
        }
    )
    csv_path = tmp_path / "missing_ts.csv"
    df.to_csv(csv_path, index=False)

    parsed_df, result = read_sample("RELIANCE", csv_path)

    assert parsed_df.empty
    assert result["status"] == "FAIL"
    assert "Missing required columns" in result["reason"]
    assert "timestamp" in result["reason"]


# ---------------------------------------------------------------------------
# 5. Missing OHLCV Field Rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing_field", ["open", "high", "low", "close", "volume"])
def test_missing_ohlcv_field_rejected(
    tmp_path: Path,
    missing_field: str,
) -> None:
    """A CSV lacking any one of the OHLCV fields is rejected."""
    df = _build_minimal_session_df()
    df = df.drop(columns=[missing_field])
    csv_path = tmp_path / f"missing_{missing_field}.csv"
    df.to_csv(csv_path, index=False)

    parsed_df, result = read_sample("RELIANCE", csv_path)

    assert parsed_df.empty
    assert result["status"] == "FAIL"
    assert "Missing required columns" in result["reason"]
    assert missing_field in result["reason"]


# ---------------------------------------------------------------------------
# 6. Invalid Timestamps Rejection
# ---------------------------------------------------------------------------


def test_invalid_timestamps_rejected(tmp_path: Path) -> None:
    """Non-datetime strings in the timestamp column are flagged and rejected."""
    df = _build_minimal_session_df(bars=3)
    # Inject unparseable timestamp
    raw_csv = (
        "timestamp,open,high,low,close,volume\n"
        "2015-01-01 09:15:00,100,105,95,102,1000\n"
        "NOT_A_DATE,100,105,95,102,1000\n"
        "2015-01-01 09:17:00,100,105,95,102,1000\n"
    )
    csv_path = tmp_path / "invalid_ts.csv"
    csv_path.write_text(raw_csv, encoding="utf-8")

    _, result = read_sample("RELIANCE", csv_path)

    assert result["status"] == "FAIL"
    assert result["invalid_timestamps"] == 1
    assert result["reason"] == "Invalid timestamp values"


# ---------------------------------------------------------------------------
# 7. Duplicate Timestamps Detection
# ---------------------------------------------------------------------------


def test_duplicate_timestamps_detected(tmp_path: Path) -> None:
    """Duplicate timestamps are counted and cause failure."""
    df = _build_minimal_session_df(bars=4)
    # Duplicate the second row timestamp
    df.iloc[2, df.columns.get_loc("timestamp")] = df.iloc[1]["timestamp"]
    csv_path = tmp_path / "duplicate_ts.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["duplicates"] == 1
    assert result["status"] == "FAIL"
    assert "duplicates" in result["reason"]


# ---------------------------------------------------------------------------
# 8. Unsorted Timestamps Rejection
# ---------------------------------------------------------------------------


def test_unsorted_timestamps_rejected(tmp_path: Path) -> None:
    """Non-chronological timestamps are rejected."""
    df = _build_minimal_session_df(bars=3)
    # Swap first and second rows to violate monotonic ordering
    df = df.iloc[[1, 0, 2]].reset_index(drop=True)
    csv_path = tmp_path / "unsorted_ts.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["status"] == "FAIL"
    assert result["sorted"] is False
    assert result["reason"] == "Timestamps are not chronological"


# ---------------------------------------------------------------------------
# 9. OHLC Violations Detection
# ---------------------------------------------------------------------------


def test_ohlc_violations_detected(tmp_path: Path) -> None:
    """Detects High < Open, High < Close, Low > Open, and Low > Close."""
    raw_csv = (
        "timestamp,open,high,low,close,volume\n"
        "2015-01-01 09:15:00,100,90,80,95,1000\n"   # High < Open (90 < 100)
        "2015-01-01 09:16:00,100,102,80,105,1000\n"  # High < Close (102 < 105)
        "2015-01-01 09:17:00,100,120,105,110,1000\n"  # Low > Open (105 > 100)
        "2015-01-01 09:18:00,110,120,105,100,1000\n"  # Low > Close (105 > 100)
        "2015-01-01 09:19:00,100,105,95,102,1000\n"   # Valid bar
    )
    csv_path = tmp_path / "ohlc_violations.csv"
    csv_path.write_text(raw_csv, encoding="utf-8")

    _, result = read_sample("RELIANCE", csv_path)

    assert result["ohlc_violations"] == 4
    assert result["status"] == "FAIL"
    assert "ohlc" in result["reason"]


# ---------------------------------------------------------------------------
# 10. Negative Volume Detection
# ---------------------------------------------------------------------------


def test_negative_volume_detected(tmp_path: Path) -> None:
    """Rows with negative trade volumes are detected and flagged."""
    df = _build_minimal_session_df(bars=3)
    df.iloc[1, df.columns.get_loc("volume")] = -50.0
    csv_path = tmp_path / "neg_volume.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["negative_volume"] == 1
    assert result["status"] == "FAIL"
    assert "volume" in result["reason"]


# ---------------------------------------------------------------------------
# 11. Q1 2015 Filtering
# ---------------------------------------------------------------------------


def test_q1_2015_filtering_works(tmp_path: Path) -> None:
    """Rows outside Q1 2015 are excluded from q1_rows count."""
    ts_2014 = pd.Timestamp("2014-12-31 15:29:00")
    ts_q1_start = pd.Timestamp("2015-01-01 09:15:00")
    ts_q1_end = pd.Timestamp("2015-03-31 15:29:00")
    ts_2016 = pd.Timestamp("2016-01-01 09:15:00")

    df = pd.DataFrame(
        {
            "timestamp": [ts_2014, ts_q1_start, ts_q1_end, ts_2016],
            "open": [100.0] * 4,
            "high": [105.0] * 4,
            "low": [95.0] * 4,
            "close": [102.0] * 4,
            "volume": [1000.0] * 4,
        }
    )
    csv_path = tmp_path / "spanning_sample.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["rows"] == 4
    assert result["q1_rows"] == 2
    assert result["q1_first_timestamp"] == str(ts_q1_start)
    assert result["q1_last_timestamp"] == str(ts_q1_end)


def test_q1_empty_data_fails_cleanly(tmp_path: Path) -> None:
    """A dataset completely outside Q1 2015 fails with informative reason."""
    df = _build_minimal_session_df(start_time="2016-01-01 09:15:00", bars=5)
    csv_path = tmp_path / "only_2016.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["q1_rows"] == 0
    assert result["status"] == "FAIL"
    assert result["reason"] == "No data in Q1 2015"


# ---------------------------------------------------------------------------
# 12. First Expected Candle Detection
# ---------------------------------------------------------------------------


def test_first_expected_candle_present(tmp_path: Path) -> None:
    """Presence of 2015-01-01 09:15:00 candle is verified."""
    df = _build_minimal_session_df(start_time="2015-01-01 09:15:00", bars=3)
    csv_path = tmp_path / "first_candle_ok.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["first_expected_candle_present"] is True


def test_first_expected_candle_missing(tmp_path: Path) -> None:
    """Missing 2015-01-01 09:15:00 candle is flagged as failure."""
    # Start at 09:16:00 instead of 09:15:00
    df = _build_minimal_session_df(start_time="2015-01-01 09:16:00", bars=3)
    csv_path = tmp_path / "first_candle_missing.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["first_expected_candle_present"] is False
    assert "first_candle" in result["reason"]


# ---------------------------------------------------------------------------
# 13. Session Bar Counting
# ---------------------------------------------------------------------------


def test_session_bar_counting_works(tmp_path: Path) -> None:
    """Sessions with non-375 bars are tracked and cause failure."""
    # Create 374 bars instead of 375 for 2015-01-01
    df = _build_minimal_session_df(
        start_time="2015-01-01 09:15:00",
        bars=EXPECTED_SESSION_BARS - 1,
    )
    csv_path = tmp_path / "short_session.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["q1_sessions"] == 1
    assert result["sessions_not_375"] == 1
    assert "session_bars" in result["reason"]


# ---------------------------------------------------------------------------
# 14. Missing January Data Detection (Zerodha/Kaggle Failure Mode)
# ---------------------------------------------------------------------------


def test_missing_january_data_detected(tmp_path: Path) -> None:
    """Dataset starting on 2015-02-02 has january_rows == 0 and fails."""
    # Start on Feb 2, 2015 (the Kaggle / Zerodha start date)
    df = _build_minimal_session_df(
        start_time="2015-02-02 09:15:00",
        bars=EXPECTED_SESSION_BARS,
    )
    csv_path = tmp_path / "missing_january.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["january_rows"] == 0
    assert result["status"] == "FAIL"
    assert "january_rows" in result["reason"]
    assert "first_candle" in result["reason"]


# ---------------------------------------------------------------------------
# 15. Incorrect Q1 Bar Count Detection
# ---------------------------------------------------------------------------


def test_incorrect_q1_bar_count_detected(tmp_path: Path) -> None:
    """Incomplete Q1 bar counts fail the q1_rows requirement."""
    # Only 5 sessions (1,875 bars) instead of 22,875
    ts_list = []
    for d in pd.date_range("2015-01-01", periods=5, freq="B"):
        ts_list.extend(
            pd.date_range(
                start=d.replace(hour=9, minute=15, second=0),
                periods=EXPECTED_SESSION_BARS,
                freq="min",
            )
        )
    df = pd.DataFrame(
        {
            "timestamp": ts_list,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
        }
    )
    csv_path = tmp_path / "short_q1.csv"
    df.to_csv(csv_path, index=False)

    _, result = read_sample("RELIANCE", csv_path)

    assert result["q1_rows"] == 5 * EXPECTED_SESSION_BARS
    assert result["q1_rows"] != EXPECTED_Q1_BARS
    assert result["status"] == "FAIL"
    assert "q1_rows" in result["reason"]
    assert "session_count" in result["reason"]


# ---------------------------------------------------------------------------
# 16. Missing Sample Produces WAITING (Never PASS)
# ---------------------------------------------------------------------------


def test_missing_sample_produces_waiting(tmp_path: Path) -> None:
    """When sample directory is empty, verifier records WAITING and exits with 1."""
    empty_root = tmp_path / "empty_sample_root"
    empty_root.mkdir()

    output_csv = tmp_path / "test_verification.csv"
    output_md = tmp_path / "test_verification.md"

    # Direct find_csv check
    assert find_csv("RELIANCE", sample_root=empty_root) is None
    assert find_csv("TCS", sample_root=empty_root) is None

    # Run main() pointing to empty temporary directory
    exit_code = main(
        sample_root=empty_root,
        output_csv=output_csv,
        output_md=output_md,
    )

    # Must exit with non-zero failure code
    assert exit_code == 1

    # Verify CSV output marks both stocks as WAITING
    results_df = pd.read_csv(output_csv)
    assert len(results_df) == 2
    assert set(results_df["stock"]) == {"RELIANCE", "TCS"}
    assert all(status == "WAITING" for status in results_df["status"])
    assert all(reason == "No CSV sample found" for reason in results_df["reason"])

    # Verify Markdown contains WAITING and PROMISING BUT UNVERIFIED
    md_content = output_md.read_text(encoding="utf-8")
    assert "### RELIANCE" in md_content
    assert "Status: **WAITING**" in md_content
    assert "### TCS" in md_content
    assert "Stocks passed: **0/2**" in md_content
    assert "### PROMISING BUT UNVERIFIED" in md_content
    assert "VERIFIED PRIMARY CANDIDATE" not in md_content


# ---------------------------------------------------------------------------
# 17. Output Reports Generation
# ---------------------------------------------------------------------------


def test_output_reports_generated(tmp_path: Path) -> None:
    """write_reports outputs valid CSV and Markdown files."""
    output_csv = tmp_path / "output.csv"
    output_md = tmp_path / "output.md"

    sample_results = [
        {
            "stock": "RELIANCE",
            "file": "test/reliance.csv",
            "status": "WAITING",
            "reason": "No CSV sample found",
        },
        {
            "stock": "TCS",
            "file": "test/tcs.csv",
            "status": "FAIL",
            "reason": "Missing required columns",
        },
    ]

    write_reports(sample_results, output_csv=output_csv, output_md=output_md)

    assert output_csv.exists()
    assert output_md.exists()

    csv_data = pd.read_csv(output_csv)
    assert len(csv_data) == 2
    assert list(csv_data["stock"]) == ["RELIANCE", "TCS"]

    md_text = output_md.read_text(encoding="utf-8")
    assert "# SignalForge — TickData Sample Verification" in md_text
    assert "### RELIANCE" in md_text
    assert "### TCS" in md_text
    assert "### PROMISING BUT UNVERIFIED" in md_text


def test_find_csv_hierarchical(tmp_path: Path) -> None:
    """find_csv locates CSVs recursively in stock directories."""
    sample_root = tmp_path / "samples"
    stock_dir = sample_root / "RELIANCE" / "subfolder"
    stock_dir.mkdir(parents=True)
    target_csv = stock_dir / "reliance_1m.csv"
    target_csv.write_text("dummy", encoding="utf-8")

    found = find_csv("RELIANCE", sample_root=sample_root)
    assert found == target_csv


def test_corrupted_csv_handled_gracefully(tmp_path: Path) -> None:
    """Unparseable or binary files produce a clean FAIL result without crashing."""
    bad_csv = tmp_path / "corrupted.csv"
    bad_csv.write_bytes(b"\x00\x01\x02\xff\xfe\x00\x00")

    parsed_df, result = read_sample("RELIANCE", bad_csv)

    assert parsed_df.empty
    assert result["status"] == "FAIL"
    assert "CSV read failed" in result["reason"]

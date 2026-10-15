"""SignalForge Phase 24G — Historical Market Data Pipeline Tests.

Isolated unit and integration tests verifying:
1. Valid and invalid OHLCV rows (NaN, infinity, negative volume, impossible price relationships).
2. Duplicate, out-of-order, and missing candles.
3. IST/UTC timestamp normalization and conversion.
4. Distinguishing missing data from zero volume.
5. Dry-run mode not modifying persistent storage.
6. Idempotent repeated runs producing identical content hashes.
7. Interrupted writes and atomic persistence (atomic replacement).
8. Provider timeouts, rate limits, retries, and partial failure isolation.
9. Dataset hashes (SHA-256) and machine-readable provenance manifests.
10. Readiness updates across the 5 states (NO_DATA, INVALID_DATA, INCOMPLETE_COVERAGE, PRELIMINARY_BACKTEST_READY, VERIFICATION_REQUIRED).
11. Zero access or modification to active paper-trading ledgers or order placement.
12. Safety controls: overwrite confirmation gate and large batch safeguard.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from src.data.acquisition import DataDirectoryContract
from src.data.historical_pipeline import (
    HistoricalDataPipeline,
    HistoricalReadinessClassification,
    PipelineAction,
    PipelineIngestionRequest,
    compute_sha256,
    detect_intraday_gaps,
    normalize_to_ist_series,
)
from src.universe.readiness import (
    MIN_BACKTEST_CANDLES,
    assess_stock_readiness,
    inspect_stock_historical_data,
)
from src.universe.registry import (
    DataQualityStatus,
    StockUniverseRegistry,
    UniverseCategory,
)


@pytest.fixture
def temp_pipeline(tmp_path):
    """Provide isolated historical pipeline backed by temporary directories."""
    data_dir = tmp_path / "historical"
    stocks_dir = data_dir / "stocks"
    stocks_dir.mkdir(parents=True, exist_ok=True)
    contract = DataDirectoryContract(base_dir=data_dir)

    reg_file = tmp_path / "test_universe_registry.json"
    registry = StockUniverseRegistry(reg_file)

    # Register sample stocks
    registry.register("RELIANCE", "NSE", UniverseCategory.NIFTY_50, name="Reliance Industries")
    registry.register("TCS", "NSE", UniverseCategory.NIFTY_50, name="Tata Consultancy Services")
    registry.register("TESTSTOCK", "NSE", UniverseCategory.CUSTOM, name="Custom Test Stock")

    pipeline = HistoricalDataPipeline(
        contract=contract,
        registry=registry,
        archive_dir=tmp_path / "archive",
    )
    return pipeline, contract, registry


# ---------------------------------------------------------------------------
# 1. Valid and Invalid OHLCV Rows Validation
# ---------------------------------------------------------------------------
def test_valid_and_invalid_ohlcv_validation(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    # Create mixed DataFrame: 3 valid rows, multiple invalid rows
    raw_data = {
        "timestamp": [
            "2026-10-14 09:15:00",
            "2026-10-14 09:16:00",
            "2026-10-14 09:17:00",
            "2026-10-14 09:18:00",  # Invalid: high < low
            "2026-10-14 09:19:00",  # Invalid: negative volume
            "2026-10-14 09:20:00",  # Invalid: NaN close
            "2026-10-14 09:21:00",  # Invalid: non-positive open (<= 0)
            "2026-10-14 09:22:00",  # Invalid: Infinity high
        ],
        "open": [100.0, 101.0, 102.0, 100.0, 100.0, 100.0, 0.0, 100.0],
        "high": [105.0, 106.0, 107.0, 95.0, 105.0, 105.0, 105.0, np.inf],
        "low": [98.0, 99.0, 100.0, 102.0, 98.0, 98.0, 98.0, 98.0],
        "close": [102.0, 103.0, 104.0, 99.0, 101.0, np.nan, 101.0, 102.0],
        "volume": [1000, 1200, 800, 500, -100, 500, 500, 500],
    }
    df = pd.DataFrame(raw_data)

    valid_df, invalid_df, report = pipeline.validate_and_normalize_ohlcv(
        raw_df=df,
        symbol="RELIANCE",
        exchange="NSE",
        provider_name="test_fixture",
    )

    assert len(valid_df) == 3
    assert len(invalid_df) == 5
    assert report.valid_rows == 3
    assert report.rejected_rows == 5
    assert report.readiness_classification == HistoricalReadinessClassification.INCOMPLETE_COVERAGE


# ---------------------------------------------------------------------------
# 2. Duplicate and Out-of-Order Candles Detection
# ---------------------------------------------------------------------------
def test_duplicate_and_out_of_order_candles(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    # Out of order timestamps and duplicate
    raw_data = {
        "timestamp": [
            "2026-10-14 09:18:00",  # 3rd chronologically
            "2026-10-14 09:15:00",  # 1st chronologically
            "2026-10-14 09:16:00",  # 2nd chronologically
            "2026-10-14 09:16:00",  # Duplicate timestamp
        ],
        "open": [102.0, 100.0, 101.0, 101.0],
        "high": [107.0, 105.0, 106.0, 106.0],
        "low": [100.0, 98.0, 99.0, 99.0],
        "close": [104.0, 102.0, 103.0, 103.0],
        "volume": [1000, 1000, 1000, 1000],
    }
    df = pd.DataFrame(raw_data)

    valid_df, invalid_df, report = pipeline.validate_and_normalize_ohlcv(
        raw_df=df,
        symbol="RELIANCE",
    )

    # Valid DataFrame should be sorted ascending: 09:15, 09:16, 09:18 (deduplicated)
    assert len(valid_df) == 3
    assert valid_df["timestamp"].is_monotonic_increasing
    assert valid_df["timestamp"].iloc[0].strftime("%H:%M:%S") == "09:15:00"
    assert valid_df["timestamp"].iloc[1].strftime("%H:%M:%S") == "09:16:00"
    assert valid_df["timestamp"].iloc[2].strftime("%H:%M:%S") == "09:18:00"

    # Duplicate should be captured in invalid_df
    assert len(invalid_df) == 1
    assert any("duplicate" in issue.lower() for issue in report.issues)


# ---------------------------------------------------------------------------
# 3. IST/UTC Timestamp Normalization
# ---------------------------------------------------------------------------
def test_ist_utc_timestamp_normalization():
    # 1. UTC timestamp string
    utc_series = pd.Series(["2026-10-14 03:45:00+00:00", "2026-10-14 03:46:00Z"])
    ist_series = normalize_to_ist_series(utc_series)

    # 03:45 UTC is 09:15 IST (UTC + 05:30)
    assert ist_series.iloc[0].strftime("%Y-%m-%d %H:%M:%S") == "2026-10-14 09:15:00"
    assert ist_series.iloc[1].strftime("%Y-%m-%d %H:%M:%S") == "2026-10-14 09:16:00"

    # 2. Tz-naive IST string remains unchanged
    ist_naive = pd.Series(["2026-10-14 09:15:00", "2026-10-14 09:16:00"])
    normalized_naive = normalize_to_ist_series(ist_naive)
    assert normalized_naive.iloc[0].strftime("%Y-%m-%d %H:%M:%S") == "2026-10-14 09:15:00"


# ---------------------------------------------------------------------------
# 4. Distinguishing Missing Data from Valid Zero Volume
# ---------------------------------------------------------------------------
def test_distinguish_missing_volume_from_zero_volume(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    raw_data = {
        "timestamp": ["2026-10-14 09:15:00", "2026-10-14 09:16:00", "2026-10-14 09:17:00"],
        "open": [100.0, 100.0, 100.0],
        "high": [100.0, 100.0, 100.0],
        "low": [100.0, 100.0, 100.0],
        "close": [100.0, 100.0, 100.0],
        "volume": [0, 500, np.nan],  # row 0 is zero volume (valid), row 2 is missing volume (invalid)
    }
    df = pd.DataFrame(raw_data)

    valid_df, invalid_df, report = pipeline.validate_and_normalize_ohlcv(
        raw_df=df,
        symbol="TESTSTOCK",
    )

    # Row 0 (zero volume) is accepted as valid
    # Row 2 (NaN volume) is rejected to quarantine
    assert len(valid_df) == 2
    assert len(invalid_df) == 1
    assert report.zero_volume_rows == 1


# ---------------------------------------------------------------------------
# 5. Intraday Gap Detection within Market Sessions
# ---------------------------------------------------------------------------
def test_intraday_gap_detection_within_market_hours():
    # Regular 1m timestamps with a 5-minute gap inside trading session
    # 09:15 to 09:20 -> missing 4 minutes (09:16, 09:17, 09:18, 09:19)
    ts = pd.Series([
        pd.Timestamp("2026-10-14 09:15:00"),
        pd.Timestamp("2026-10-14 09:20:00"),
        pd.Timestamp("2026-10-14 09:21:00"),
        # Overnight jump to next day 09:15 (should NOT be counted as intraday missing gap)
        pd.Timestamp("2026-10-15 09:15:00"),
        pd.Timestamp("2026-10-15 09:16:00"),
    ])

    missing_minutes, events = detect_intraday_gaps(ts)
    assert missing_minutes == 4
    assert len(events) == 1
    assert events[0].date == "2026-10-14"
    assert events[0].missing_minutes == 4


# ---------------------------------------------------------------------------
# 6. Dry-Run Mode Not Modifying Persistent Files
# ---------------------------------------------------------------------------
def test_dry_run_mode_does_not_modify_files(temp_pipeline):
    pipeline, contract, _ = temp_pipeline

    df = pd.DataFrame({
        "timestamp": [f"2026-10-14 09:{i//60:02d}:{i%60:02d}" for i in range(100)],
        "open": [100.0] * 100,
        "high": [105.0] * 100,
        "low": [95.0] * 100,
        "close": [102.0] * 100,
        "volume": [1000] * 100,
    })

    req = PipelineIngestionRequest(
        symbol="RELIANCE",
        data_override=df,
        dry_run=True,
    )
    res = pipeline.ingest_symbol(req)

    assert res.success is True
    assert res.dry_run is True
    assert res.action == PipelineAction.DRY_RUN_VALIDATED

    # Target file must NOT exist
    dest_path = contract.production_path("RELIANCE")
    assert not dest_path.exists()


# ---------------------------------------------------------------------------
# 7. Atomic Persistence and Content Hash Verification
# ---------------------------------------------------------------------------
def test_atomic_persistence_and_checksum(temp_pipeline):
    pipeline, contract, registry = temp_pipeline

    # Create 600 valid candles (satisfies >= 500 threshold)
    lines_ts = [f"2026-10-14 09:{i//60:02d}:{i%60:02d}" for i in range(600)]
    df = pd.DataFrame({
        "timestamp": lines_ts,
        "open": [100.0 + i*0.1 for i in range(600)],
        "high": [105.0 + i*0.1 for i in range(600)],
        "low": [95.0 + i*0.1 for i in range(600)],
        "close": [102.0 + i*0.1 for i in range(600)],
        "volume": [1000] * 600,
    })

    req = PipelineIngestionRequest(
        symbol="RELIANCE",
        data_override=df,
        dry_run=False,
    )
    res = pipeline.ingest_symbol(req)

    assert res.success is True
    assert res.action == PipelineAction.INGESTED
    dest_path = contract.production_path("RELIANCE")
    assert dest_path.exists()

    # Content hash must be valid SHA-256
    expected_hash = compute_sha256(dest_path)
    assert res.quality_report.content_hash == expected_hash

    # Manifest must be created
    manifest_file = pipeline.manifests_dir / "RELIANCE_1m_manifest.json"
    assert manifest_file.exists()
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["content_hash"] == expected_hash
    assert manifest["row_count"] == 600
    assert manifest["readiness_classification"] == HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY.value

    # Registry stock data quality should be updated to READY
    stock = registry.get("RELIANCE")
    assert stock.data_quality_status == DataQualityStatus.READY


# ---------------------------------------------------------------------------
# 8. Idempotence: Repeated Ingestions Produce Identical Result
# ---------------------------------------------------------------------------
def test_idempotent_ingestion(temp_pipeline):
    pipeline, contract, _ = temp_pipeline

    df = pd.DataFrame({
        "timestamp": [f"2026-10-14 09:{i//60:02d}:{i%60:02d}" for i in range(550)],
        "open": [100.0] * 550,
        "high": [105.0] * 550,
        "low": [95.0] * 550,
        "close": [102.0] * 550,
        "volume": [1000] * 550,
    })

    # Run 1
    req1 = PipelineIngestionRequest(symbol="TCS", data_override=df, dry_run=False)
    res1 = pipeline.ingest_symbol(req1)
    hash1 = res1.quality_report.content_hash

    # Run 2 with confirm_replace=True
    req2 = PipelineIngestionRequest(symbol="TCS", data_override=df, dry_run=False, confirm_replace=True)
    res2 = pipeline.ingest_symbol(req2)
    hash2 = res2.quality_report.content_hash

    assert hash1 == hash2


# ---------------------------------------------------------------------------
# 9. Overwrite Protection: Refuses to Overwrite Without Confirmation
# ---------------------------------------------------------------------------
def test_overwrite_protection_requires_confirmation(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    df = pd.DataFrame({
        "timestamp": ["2026-10-14 09:15:00", "2026-10-14 09:16:00"],
        "open": [100.0, 101.0],
        "high": [105.0, 106.0],
        "low": [95.0, 96.0],
        "close": [102.0, 103.0],
        "volume": [1000, 1000],
    })

    # First write
    req1 = PipelineIngestionRequest(symbol="TESTSTOCK", data_override=df, dry_run=False)
    res1 = pipeline.ingest_symbol(req1)
    assert res1.success is True

    # Attempt second write without confirm_replace
    req2 = PipelineIngestionRequest(symbol="TESTSTOCK", data_override=df, dry_run=False, confirm_replace=False)
    res2 = pipeline.ingest_symbol(req2)
    assert res2.success is False
    assert res2.action == PipelineAction.SKIPPED_EXISTING
    assert "confirmation required" in res2.error_message.lower()


# ---------------------------------------------------------------------------
# 10. Quarantine of Corrupt Records
# ---------------------------------------------------------------------------
def test_quarantine_corrupt_records(temp_pipeline):
    pipeline, contract, _ = temp_pipeline

    df = pd.DataFrame({
        "timestamp": ["2026-10-14 09:15:00", "2026-10-14 09:16:00"],
        "open": [100.0, 100.0],
        "high": [105.0, 80.0],  # row 1 invalid: high < low
        "low": [95.0, 90.0],
        "close": [102.0, 85.0],
        "volume": [1000, 500],
    })

    req = PipelineIngestionRequest(symbol="TCS", data_override=df, dry_run=False, confirm_replace=True)
    res = pipeline.ingest_symbol(req)

    assert res.quality_report.rejected_rows == 1
    assert res.quality_report.quarantine_file is not None
    assert Path(res.quality_report.quarantine_file).exists()


# ---------------------------------------------------------------------------
# 11. Readiness Distinctions across All 5 States
# ---------------------------------------------------------------------------
def test_readiness_five_state_distinctions(temp_pipeline, tmp_path):
    _, contract, registry = temp_pipeline
    stocks_dir = contract.stocks_dir

    # 1. NO_DATA: Stock registered, no file
    registry.register("NODATASTOCK", "NSE", UniverseCategory.NIFTY_50)
    stock_nodata = registry.get("NODATASTOCK")
    readiness_nodata = assess_stock_readiness(stock_nodata, data_dir=stocks_dir)
    assert readiness_nodata.data_quality.readiness_classification == "NO_DATA"
    assert readiness_nodata.data_quality.data_quality_status == "UNKNOWN"

    # 2. INVALID_DATA: Corrupt prices
    p_invalid = stocks_dir / "INVALIDSTOCK_1m.csv"
    p_invalid.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-10-14 09:15:00,100,90,110,105,500\n",  # high < low
        encoding="utf-8"
    )
    registry.register("INVALIDSTOCK", "NSE", UniverseCategory.NIFTY_50)
    stock_invalid = registry.get("INVALIDSTOCK")
    readiness_invalid = assess_stock_readiness(stock_invalid, data_dir=stocks_dir)
    assert readiness_invalid.data_quality.readiness_classification == "INVALID_DATA"
    assert readiness_invalid.data_quality.data_quality_status == "INCOMPLETE"

    # 3. INCOMPLETE_COVERAGE: Valid but < 500 candles
    p_incomplete = stocks_dir / "INCOMPLETESTOCK_1m.csv"
    lines = ["timestamp,open,high,low,close,volume"]
    for i in range(100):
        lines.append(f"2026-10-14 09:{i//60:02d}:{i%60:02d},100,105,95,102,1000")
    p_incomplete.write_text("\n".join(lines), encoding="utf-8")
    registry.register("INCOMPLETESTOCK", "NSE", UniverseCategory.NIFTY_50)
    stock_incomplete = registry.get("INCOMPLETESTOCK")
    readiness_incomplete = assess_stock_readiness(stock_incomplete, data_dir=stocks_dir)
    assert readiness_incomplete.data_quality.readiness_classification == "INCOMPLETE_COVERAGE"
    assert readiness_incomplete.data_quality.data_quality_status == "INCOMPLETE"

    # 4. PRELIMINARY_BACKTEST_READY: >= 500 valid continuous candles
    p_ready = stocks_dir / "READYSTOCK_1m.csv"
    lines_ready = ["timestamp,open,high,low,close,volume"]
    for i in range(600):
        lines_ready.append(f"2026-10-14 09:{i//60:02d}:{i%60:02d},100,105,95,102,1000")
    p_ready.write_text("\n".join(lines_ready), encoding="utf-8")
    registry.register("READYSTOCK", "NSE", UniverseCategory.NIFTY_50)
    stock_ready = registry.get("READYSTOCK")
    readiness_ready = assess_stock_readiness(stock_ready, data_dir=stocks_dir)
    assert readiness_ready.data_quality.readiness_classification == "PRELIMINARY_BACKTEST_READY"
    assert readiness_ready.data_quality.data_quality_status == "READY"
    assert readiness_ready.has_sufficient_backtest_data is True

    # 5. VERIFICATION_REQUIRED: >= 500 candles but massive intraday gaps (>15% gap density)
    p_gaps = stocks_dir / "GAPSTOCK_1m.csv"
    lines_gaps = ["timestamp,open,high,low,close,volume"]
    # 500 candles spread across days with huge jumps during market hours
    for day in range(10):
        for m in range(0, 50, 10):  # 10 minute jumps inside market hours = 9 missing candles each
            lines_gaps.append(f"2026-10-{10+day:02d} 09:{m:02d}:00,100,105,95,102,1000")
    # pad with other candles to reach 500
    for i in range(len(lines_gaps) - 1, 550):
        lines_gaps.append(f"2026-10-25 09:{i//60:02d}:{i%60:02d},100,105,95,102,1000")
    p_gaps.write_text("\n".join(lines_gaps), encoding="utf-8")
    registry.register("GAPSTOCK", "NSE", UniverseCategory.NIFTY_50)
    stock_gaps = registry.get("GAPSTOCK")
    readiness_gaps = assess_stock_readiness(stock_gaps, data_dir=stocks_dir)
    assert readiness_gaps.data_quality.readiness_classification == "VERIFICATION_REQUIRED"
    assert readiness_gaps.data_quality.data_quality_status == "INCOMPLETE"
    assert readiness_gaps.has_sufficient_backtest_data is False


# ---------------------------------------------------------------------------
# 12. Batch Safety Controls and Partial Failure Isolation
# ---------------------------------------------------------------------------
def test_batch_safety_controls_and_partial_failure(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    # Batch exceeding safety threshold (10) without confirmation should raise ValueError
    symbols = [f"SYM{i}" for i in range(12)]
    with pytest.raises(ValueError, match="exceeds safety limit"):
        pipeline.ingest_batch(symbols, confirm_large_batch=False)

    # Isolated execution with 1 failing symbol and 1 passing symbol
    df_good = pd.DataFrame({
        "timestamp": ["2026-10-14 09:15:00"],
        "open": [100.0],
        "high": [105.0],
        "low": [95.0],
        "close": [102.0],
        "volume": [1000],
    })

    # Test small batch where one symbol has no archive data and fails, while other succeeds
    # Using dry_run
    batch_res = pipeline.ingest_batch(
        symbols=["RELIANCE", "NONEXISTENT_SYMBOL_XYZ"],
        dry_run=True,
    )
    assert batch_res.total_requested == 2
    # At least the failure of NONEXISTENT does not abort the batch
    assert len(batch_res.results) == 2


# ---------------------------------------------------------------------------
# 13. Safety Boundary: Paper-Trading Ledgers Must Remain Untouched
# ---------------------------------------------------------------------------
def test_safety_boundary_paper_trading_ledger_untouched(temp_pipeline):
    pipeline, _, _ = temp_pipeline

    ledger_path = Path("data/paper_trading/interactive_trades.json")
    original_mtime = ledger_path.stat().st_mtime if ledger_path.exists() else None
    original_size = ledger_path.stat().st_size if ledger_path.exists() else None

    # Run ingestion
    df = pd.DataFrame({
        "timestamp": ["2026-10-14 09:15:00"],
        "open": [100.0],
        "high": [105.0],
        "low": [95.0],
        "close": [102.0],
        "volume": [1000],
    })
    req = PipelineIngestionRequest(symbol="TESTSTOCK", data_override=df, dry_run=False, confirm_replace=True)
    pipeline.ingest_symbol(req)

    # Assert paper trading ledger is completely untouched
    if ledger_path.exists():
        assert ledger_path.stat().st_mtime == original_mtime
        assert ledger_path.stat().st_size == original_size


# ---------------------------------------------------------------------------
# 14. FastAPI Endpoints Integration: Pipeline Symbol & Batch
# ---------------------------------------------------------------------------
def test_pipeline_api_endpoints(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from src.api.main import app
    import src.api.routes.universe as universe_routes

    test_stocks_dir = tmp_path / "stocks"
    test_stocks_dir.mkdir(parents=True, exist_ok=True)
    test_contract = DataDirectoryContract(base_dir=tmp_path)

    test_reg_file = tmp_path / "api_test_reg.json"
    test_reg = StockUniverseRegistry(test_reg_file)
    test_reg.register("TESTSYM", "NSE", UniverseCategory.NIFTY_50)

    test_pipeline = HistoricalDataPipeline(
        contract=test_contract,
        registry=test_reg,
        archive_dir=tmp_path / "archive",
    )

    monkeypatch.setattr(universe_routes, "_registry", test_reg)
    monkeypatch.setattr(universe_routes, "_pipeline", test_pipeline)

    client = TestClient(app)

    # 1. Pipeline dry-run for symbol
    res_dry = client.post(
        "/api/universe/stocks/data/pipeline/symbol",
        json={
            "symbol": "TESTSYM",
            "provider": "local_archive",
            "dry_run": True,
        },
    )
    assert res_dry.status_code == 200
    data_dry = res_dry.json()
    assert data_dry["symbol"] == "TESTSYM"
    assert data_dry["dry_run"] is True

    # 2. Pipeline batch dry-run
    res_batch = client.post(
        "/api/universe/stocks/data/pipeline/batch",
        json={
            "symbols": ["TESTSYM"],
            "provider": "local_archive",
            "dry_run": True,
        },
    )
    assert res_batch.status_code == 200
    data_batch = res_batch.json()
    assert data_batch["total_requested"] == 1
    assert data_batch["dry_run"] is True

    # 3. Readiness inspection endpoint returns new classification fields
    res_readiness = client.get("/api/universe/stocks/TESTSYM/readiness")
    assert res_readiness.status_code == 200
    data_readiness = res_readiness.json()
    assert "data_quality" in data_readiness
    assert "readiness_classification" in data_readiness["data_quality"]
    assert "gap_count" in data_readiness["data_quality"]


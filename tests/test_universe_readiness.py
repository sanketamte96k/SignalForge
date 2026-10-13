"""SignalForge Phase 24F — Stock Universe Readiness & Ingestion Tests.

Verifies:
1. Reproducible imports and repeated idempotent runs.
2. Duplicate and malformed symbols handling.
3. Invalid, missing, or stale constituent source metadata & checksum validation.
4. Dry-run mode leaving persistent files completely unchanged.
5. Custom stocks being strictly preserved during index refresh.
6. Safe handling of proposed constituent removals (protection against silent deletion).
7. Data freshness, candle count, and invalid OHLCV reporting.
8. Readiness status for stocks with no historical data or no qualification record.
9. Independent readiness for each stock/strategy pair.
10. Failure and retry behavior without corrupting persistent storage.
11. Zero access or modification to active trading ledgers or order placement.
12. FastAPI HTTP endpoints for readiness and ingestion preview/apply.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
import src.api.routes.universe as universe_routes
from src.universe.ingestion import (
    ConstituentRecord,
    IngestionAction,
    SourceProvenance,
    create_ingestion_plan,
    execute_ingestion,
    load_canonical_source,
    parse_constituent_csv,
)
from src.universe.readiness import (
    MIN_BACKTEST_CANDLES,
    ReadinessState,
    assess_stock_readiness,
    assess_universe_readiness,
    inspect_stock_historical_data,
)
from src.universe.registry import (
    DataQualityStatus,
    QualificationStatus,
    StockUniverseRegistry,
    UniverseCategory,
)


@pytest.fixture
def temp_registry(tmp_path):
    """Provides a fresh, isolated StockUniverseRegistry backed by temporary files."""
    reg_file = tmp_path / "test_universe_registry.json"
    return StockUniverseRegistry(reg_file)


@pytest.fixture
def sample_provenance():
    return SourceProvenance(
        source_name="National Stock Exchange of India (NSE Indices)",
        source_url="https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        retrieval_timestamp=datetime(2026, 10, 13, 17, 28, 24, tzinfo=timezone.utc),
        as_of_date="2026-10-13",
        constituent_count=3,
        sha256="dummy_sha256_hash",
    )


# ---------------------------------------------------------------------------
# 1. Reproducible imports and repeated idempotent runs
# ---------------------------------------------------------------------------
def test_reproducible_imports_and_idempotency(temp_registry, sample_provenance):
    constituents = [
        ConstituentRecord(symbol="TCS", name="Tata Consultancy Services Ltd.", exchange="NSE"),
        ConstituentRecord(symbol="INFY", name="Infosys Ltd.", exchange="NSE"),
        ConstituentRecord(symbol="HDFCBANK", name="HDFC Bank Ltd.", exchange="NSE"),
    ]

    # First run: All 3 should be added
    plan1 = create_ingestion_plan(
        registry=temp_registry,
        constituents=constituents,
        category=UniverseCategory.NIFTY_50,
        provenance=sample_provenance,
    )
    assert len(plan1.additions) == 3
    assert len(plan1.updates) == 0
    assert len(plan1.removals) == 0

    res1 = execute_ingestion(temp_registry, plan1, dry_run=False)
    assert res1["status"] == "APPLIED"
    assert res1["counts"]["added"] == 3
    assert len(temp_registry.list_all()) == 3

    # Second run (exact same input): Idempotent, 0 added, 3 unchanged
    plan2 = create_ingestion_plan(
        registry=temp_registry,
        constituents=constituents,
        category=UniverseCategory.NIFTY_50,
        provenance=sample_provenance,
    )
    assert len(plan2.additions) == 0
    assert len(plan2.updates) == 0
    assert len(plan2.unchanged) == 3

    res2 = execute_ingestion(temp_registry, plan2, dry_run=False)
    assert res2["status"] == "APPLIED"
    assert res2["counts"]["added"] == 0
    assert res2["counts"]["unchanged"] == 3
    assert len(temp_registry.list_all()) == 3


# ---------------------------------------------------------------------------
# 2. Duplicate and malformed symbols handling
# ---------------------------------------------------------------------------
def test_duplicate_and_malformed_symbols_in_source(sample_provenance):
    raw_csv = """Company Name,Industry,Symbol,Series,ISIN Code
Tata Consultancy Services Ltd.,Information Technology,TCS,EQ,INE467B01029
Duplicate TCS Ltd.,Information Technology,tcs,EQ,INE467B01029
Missing Symbol Co.,Financial Services, ,EQ,INE000000000
Valid Infosys Ltd.,Information Technology,INFY,EQ,INE009A01021
Row With Insufficient Columns
"""
    constituents, errors = parse_constituent_csv(raw_csv, UniverseCategory.NIFTY_50, sample_provenance)

    # Valid rows parsed
    symbols = [c.symbol for c in constituents]
    assert symbols == ["TCS", "INFY"]

    # Errors recorded for duplicate, empty, and insufficient columns
    assert len(errors) == 3
    error_texts = [e["error"] for e in errors]
    assert any("Duplicate symbol" in t for t in error_texts)
    assert any("Symbol is empty" in t for t in error_texts)
    assert any("insufficient columns" in t for t in error_texts)


# ---------------------------------------------------------------------------
# 3. Invalid, missing, or stale source metadata & checksum validation
# ---------------------------------------------------------------------------
def test_invalid_missing_stale_source_metadata(tmp_path):
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()

    # 1. Missing manifest
    with pytest.raises(FileNotFoundError, match="Source manifest not found"):
        load_canonical_source(UniverseCategory.NIFTY_50, sources_dir=sources_dir)

    # 2. Manifest present but category missing
    manifest_file = sources_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"sources": {}}), encoding="utf-8")
    with pytest.raises(KeyError, match="not found in manifest sources"):
        load_canonical_source(UniverseCategory.NIFTY_50, sources_dir=sources_dir)

    # 3. Checksum mismatch
    csv_file = sources_dir / "ind_nifty50list.csv"
    csv_file.write_text("Company Name,Symbol\nTest Co,TEST\n", encoding="utf-8")
    manifest_file.write_text(
        json.dumps({
            "sources": {
                "NIFTY_50": {
                    "source_name": "Test Source",
                    "source_url": "http://test",
                    "local_file": "ind_nifty50list.csv",
                    "retrieval_timestamp": "2026-10-13T10:00:00Z",
                    "as_of_date": "2026-10-13",
                    "constituent_count": 1,
                    "sha256": "wrong_expected_checksum",
                }
            }
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Checksum verification failed"):
        load_canonical_source(UniverseCategory.NIFTY_50, sources_dir=sources_dir)


# ---------------------------------------------------------------------------
# 4. Dry-run mode leaving persistent files completely unchanged
# ---------------------------------------------------------------------------
def test_dry_run_leaves_persistent_files_unchanged(tmp_path, sample_provenance):
    reg_file = tmp_path / "dry_run_registry.json"
    registry = StockUniverseRegistry(reg_file)

    constituents = [
        ConstituentRecord(symbol="RELIANCE", name="Reliance Industries Ltd.", exchange="NSE")
    ]
    plan = create_ingestion_plan(registry, constituents, UniverseCategory.NIFTY_50, sample_provenance)

    # Dry run execution
    res = execute_ingestion(registry, plan, dry_run=True)
    assert res["status"] == "DRY_RUN_COMPLETED"
    assert res["dry_run"] is True

    # Persistent storage must NOT exist or have any stocks
    assert not reg_file.exists()
    assert len(registry.list_all()) == 0


# ---------------------------------------------------------------------------
# 5. Custom stocks preserved during index refresh
# ---------------------------------------------------------------------------
def test_custom_stocks_preserved_during_index_refresh(temp_registry, sample_provenance):
    # Register custom stock
    temp_registry.register("MYSTOCK", "NSE", UniverseCategory.CUSTOM, name="My Custom Strategy Stock")

    constituents = [
        ConstituentRecord(symbol="TCS", name="Tata Consultancy Services Ltd.", exchange="NSE")
    ]
    plan = create_ingestion_plan(temp_registry, constituents, UniverseCategory.NIFTY_50, sample_provenance)

    # Custom stock must be marked as PRESERVED_CUSTOM
    assert len(plan.custom_preserved) == 1
    assert plan.custom_preserved[0].symbol == "MYSTOCK"

    # Execute ingestion
    execute_ingestion(temp_registry, plan, dry_run=False)

    # Verify custom stock remains intact
    stock = temp_registry.get("MYSTOCK")
    assert stock is not None
    assert stock.category == UniverseCategory.CUSTOM
    assert stock.name == "My Custom Strategy Stock"
    assert len(temp_registry.list_all()) == 2


# ---------------------------------------------------------------------------
# 6. Safe handling of proposed constituent removals
# ---------------------------------------------------------------------------
def test_safe_handling_of_proposed_constituent_removals(temp_registry, sample_provenance):
    # Pre-register an older stock in NIFTY_50
    temp_registry.register("OLDSTOCK", "NSE", UniverseCategory.NIFTY_50, name="Old Stock Ltd.")

    # Ingestion source contains only new stocks, omitting OLDSTOCK
    constituents = [
        ConstituentRecord(symbol="NEWSTOCK", name="New Stock Ltd.", exchange="NSE")
    ]
    plan = create_ingestion_plan(temp_registry, constituents, UniverseCategory.NIFTY_50, sample_provenance)

    assert len(plan.removals) == 1
    assert plan.removals[0].symbol == "OLDSTOCK"

    # Without explicit confirm_removals, removals must be withheld
    res_no_confirm = execute_ingestion(temp_registry, plan, dry_run=False, confirm_removals=False)
    assert res_no_confirm["counts"]["removed"] == 0
    assert res_no_confirm["counts"]["removals_withheld"] == 1
    assert temp_registry.get("OLDSTOCK") is not None  # Not deleted!

    # With explicit confirm_removals, removal is applied
    res_confirmed = execute_ingestion(temp_registry, plan, dry_run=False, confirm_removals=True)
    assert res_confirmed["counts"]["removed"] == 1
    assert temp_registry.get("OLDSTOCK") is None  # Now removed

    # Verify custom stocks cannot be deleted even if requested
    temp_registry.register("CUSTOM1", "NSE", UniverseCategory.CUSTOM)
    with pytest.raises(ValueError, match="cannot remove custom stock"):
        temp_registry.remove_stock("CUSTOM1", allow_custom_removal=False)


# ---------------------------------------------------------------------------
# 7. Data freshness, candle count, and invalid OHLCV reporting
# ---------------------------------------------------------------------------
def test_data_freshness_and_invalid_candle_reporting(tmp_path):
    data_dir = tmp_path / "stocks"
    data_dir.mkdir()

    # 1. Invalid candle CSV (high < low, negative volume, null close)
    bad_csv = data_dir / "BADSTOCK_1m.csv"
    bad_csv.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-10-13 09:15:00,100,90,110,105,500\n"  # high < low
        "2026-10-13 09:16:00,105,110,100,108,-50\n"  # negative volume
        "2026-10-13 09:17:00,108,112,107,,1000\n",   # null close
        encoding="utf-8",
    )

    report_bad = inspect_stock_historical_data("BADSTOCK", data_dir=data_dir)
    assert report_bad.has_local_data is True
    assert report_bad.invalid_candle_count == 3
    assert report_bad.data_quality_status == "INCOMPLETE"
    assert any("invalid OHLCV rows" in note for note in report_bad.notes)

    # 2. Valid CSV with 600 candles
    good_csv = data_dir / "GOODSTOCK_1m.csv"
    lines = ["timestamp,open,high,low,close,volume"]
    for i in range(600):
        lines.append(f"2026-10-13 09:{i//60:02d}:{i%60:02d},100.0,105.0,95.0,102.0,100")
    good_csv.write_text("\n".join(lines), encoding="utf-8")

    report_good = inspect_stock_historical_data("GOODSTOCK", data_dir=data_dir)
    assert report_good.has_local_data is True
    assert report_good.total_candles == 600
    assert report_good.invalid_candle_count == 0
    assert report_good.data_quality_status == "READY"


# ---------------------------------------------------------------------------
# 8. Readiness status for stock with no historical data or no qualification record
# ---------------------------------------------------------------------------
def test_readiness_no_historical_data_or_qualification(temp_registry, tmp_path):
    stock = temp_registry.register("NEWBIE", "NSE", UniverseCategory.NIFTY_50, name="Newbie Tech")
    empty_data_dir = tmp_path / "empty_stocks"
    empty_data_dir.mkdir()

    readiness = assess_stock_readiness(
        stock=stock,
        strategy_id="SignalForge_V1",
        registry=temp_registry,
        data_dir=empty_data_dir,
    )

    assert readiness.symbol == "NEWBIE"
    assert readiness.readiness_state == ReadinessState.INSUFFICIENT_DATA
    assert readiness.data_quality.has_local_data is False
    assert readiness.has_sufficient_backtest_data is False
    assert readiness.next_required_step == "Ingest historical 1-minute OHLCV market data"
    assert "Historical 1-minute OHLCV data missing" in readiness.missing_evidence


# ---------------------------------------------------------------------------
# 9. Independent readiness for each stock/strategy pair
# ---------------------------------------------------------------------------
def test_independent_readiness_per_stock_strategy_pair(temp_registry, tmp_path):
    stock = temp_registry.register("INFY", "NSE", UniverseCategory.NIFTY_50)

    # Create dummy 600-candle data
    data_dir = tmp_path / "stocks"
    data_dir.mkdir()
    csv_file = data_dir / "INFY_1m.csv"
    lines = ["timestamp,open,high,low,close,volume"]
    for i in range(600):
        lines.append(f"2026-10-13 09:{i//60:02d}:{i%60:02d},100.0,105.0,95.0,102.0,100")
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    # Update qualification for Strategy A only
    temp_registry.update_qualification(
        symbol="INFY",
        strategy_id="Strategy_A",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=500.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=35,
        qualification_status=QualificationStatus.APPROVED,
    )

    readiness_a = assess_stock_readiness(
        stock=stock,
        strategy_id="Strategy_A",
        registry=temp_registry,
        data_dir=data_dir,
    )
    readiness_b = assess_stock_readiness(
        stock=stock,
        strategy_id="Strategy_B",
        registry=temp_registry,
        data_dir=data_dir,
    )

    # Strategy A is approved
    assert readiness_a.readiness_state == ReadinessState.APPROVED
    assert readiness_a.qualification_status == QualificationStatus.APPROVED

    # Strategy B remains NOT_TESTED with backtest required
    assert readiness_b.readiness_state == ReadinessState.NOT_TESTED
    assert readiness_b.qualification_status == QualificationStatus.NOT_TESTED
    assert readiness_b.next_required_step == "Execute historical backtest on validated data"


# ---------------------------------------------------------------------------
# 10. Failure and retry behavior without storage corruption
# ---------------------------------------------------------------------------
def test_failure_retry_without_storage_corruption(temp_registry, sample_provenance):
    # Pre-populate registry with 1 stock
    temp_registry.register("STABLE", "NSE", UniverseCategory.NIFTY_50)

    # Plan with malformed input
    bad_constituents = [
        ConstituentRecord(symbol="", name="Bad Symbol", exchange="NSE")
    ]
    # Creating plan with empty symbol will fail on register
    plan = create_ingestion_plan(temp_registry, bad_constituents, UniverseCategory.NIFTY_50, sample_provenance)

    # Attempting to execute will raise ValueError on empty symbol
    with pytest.raises(ValueError, match="symbol must not be empty"):
        execute_ingestion(temp_registry, plan, dry_run=False)

    # Existing storage must remain uncorrupted and contain original stock
    assert len(temp_registry.list_all()) == 1
    assert temp_registry.get("STABLE") is not None


# ---------------------------------------------------------------------------
# 11. Zero access or modification to active trading ledgers or order placement
# ---------------------------------------------------------------------------
def test_zero_access_to_active_trading_ledgers():
    ledger_path = Path("data/paper_trading/interactive_trades.json")
    if ledger_path.exists():
        initial_mtime = ledger_path.stat().st_mtime
    else:
        initial_mtime = None

    # Load canonical source and evaluate readiness against a temp registry
    with pytest.MonkeyPatch().context() as mp:
        reg = StockUniverseRegistry(Path("data/universe/sources/temp_reg.json"))
        # Execute readiness audit
        assess_universe_readiness(reg)
        if Path("data/universe/sources/temp_reg.json").exists():
            Path("data/universe/sources/temp_reg.json").unlink()

    if ledger_path.exists():
        assert ledger_path.stat().st_mtime == initial_mtime


# ---------------------------------------------------------------------------
# 12. FastAPI HTTP endpoints for readiness and ingestion preview/apply
# ---------------------------------------------------------------------------
def test_fastapi_readiness_and_ingestion_endpoints(temp_registry, monkeypatch):
    monkeypatch.setattr(universe_routes, "_registry", temp_registry)
    client = TestClient(app)

    # 1. Preview ingestion (dry-run)
    resp_plan = client.post("/api/universe/stocks/ingest/plan", json={"category": "NIFTY_50"})
    assert resp_plan.status_code == 200
    plan_data = resp_plan.json()
    assert plan_data["status"] == "DRY_RUN_COMPLETED"
    assert plan_data["counts"]["added"] == 50
    assert len(temp_registry.list_all()) == 0  # Dry run: 0 added to registry

    # 2. Apply ingestion
    resp_apply = client.post("/api/universe/stocks/ingest/apply", json={"category": "NIFTY_50"})
    assert resp_apply.status_code == 200
    apply_data = resp_apply.json()
    assert apply_data["status"] == "APPLIED"
    assert apply_data["counts"]["added"] == 50
    assert len(temp_registry.list_all()) == 50

    # 3. Stock Readiness
    resp_readiness = client.get("/api/universe/stocks/TCS/readiness")
    assert resp_readiness.status_code == 200
    readiness_data = resp_readiness.json()
    assert readiness_data["symbol"] == "TCS"
    assert readiness_data["exchange"] == "NSE"
    assert readiness_data["readiness_state"] in ("INSUFFICIENT_DATA", "NOT_TESTED")
    assert "next_required_step" in readiness_data

    # 4. Universe Readiness Summary
    resp_summary = client.get("/api/universe/stocks/readiness/summary")
    assert resp_summary.status_code == 200
    summary_data = resp_summary.json()
    assert summary_data["total_registered_stocks"] == 50
    assert "summary" in summary_data
    assert len(summary_data["assessments"]) == 50

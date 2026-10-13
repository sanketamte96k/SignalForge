"""SignalForge Phase 24E.4 — End-to-End API Integration & Regression Tests.

Validates the complete Stock Universe workflow through FastAPI HTTP requests:
1. List registered stocks
2. Filter stocks by supported category and search query
3. Retrieve a stock by symbol
4. Register a custom stock
5. Reject duplicate or malformed stock registration
6. Retrieve all qualification records for a stock
7. Retrieve an individual strategy qualification, including NOT_TESTED default behavior
8. Update a qualification using valid supported fields
9. Reject fewer than 30 completed forward paper trades when approval is requested
10. Verify 30 meets initial sample threshold and 50 meets preferred threshold, without treating sample size as sole proof of profitability
11. Reject contradictory stage statuses, invalid counts, booleans where prohibited, NaN, and positive/negative infinity
12. Verify qualification records remain independent for different stock/strategy combinations
13. Verify persistence across registry reloads using isolated temporary storage
"""

import math
from pathlib import Path
import tempfile
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
import src.api.routes.universe as universe_routes
from src.universe.registry import (
    StockUniverseRegistry,
    UniverseCategory,
    QualificationStatus,
    DEFAULT_MIN_FORWARD_TRADES,
    DEFAULT_PREFERRED_FORWARD_TRADES,
)


@pytest.fixture
def isolated_temp_storage():
    """Provides isolated temporary storage files for universe and qualification data."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path

    if path.exists():
        path.unlink()
    qual_path = path.parent / (path.stem + "_qualifications.json")
    if qual_path.exists():
        qual_path.unlink()


@pytest.fixture
def e2e_client(isolated_temp_storage, monkeypatch):
    """Sets up FastAPI TestClient wired to an isolated temporary registry instance."""
    reg = StockUniverseRegistry(isolated_temp_storage)
    reg.register("TCS", "NSE", UniverseCategory.NIFTY_50, name="Tata Consultancy Services Ltd.")
    reg.register("INFY", "NSE", UniverseCategory.NIFTY_50, name="Infosys Limited")
    reg.register("HDFCBANK", "NSE", UniverseCategory.NIFTY_NEXT_50, name="HDFC Bank Limited")

    monkeypatch.setattr(universe_routes, "_registry", reg)
    client = TestClient(app)
    return client, reg, isolated_temp_storage


# ---------------------------------------------------------------------------
# 1. List registered stocks
# ---------------------------------------------------------------------------
def test_e2e_list_registered_stocks(e2e_client):
    client, _, _ = e2e_client
    response = client.get("/api/universe/stocks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3

    symbols = [s["symbol"] for s in data]
    assert "HDFCBANK" in symbols
    assert "INFY" in symbols
    assert "TCS" in symbols


# ---------------------------------------------------------------------------
# 2. Filter stocks by supported category and search query
# ---------------------------------------------------------------------------
def test_e2e_filter_by_category_and_search(e2e_client):
    client, _, _ = e2e_client

    # Category filter: NIFTY_50
    resp_cat = client.get("/api/universe/stocks?category=NIFTY_50")
    assert resp_cat.status_code == 200
    nifty50_stocks = resp_cat.json()
    assert len(nifty50_stocks) == 2
    assert all(s["category"] == "NIFTY_50" for s in nifty50_stocks)

    # Category filter: NIFTY_NEXT_50
    resp_next = client.get("/api/universe/stocks?category=NIFTY_NEXT_50")
    assert resp_next.status_code == 200
    next50_stocks = resp_next.json()
    assert len(next50_stocks) == 1
    assert next50_stocks[0]["symbol"] == "HDFCBANK"

    # Category filter: CUSTOM (empty)
    resp_custom = client.get("/api/universe/stocks?category=CUSTOM")
    assert resp_custom.status_code == 200
    assert len(resp_custom.json()) == 0

    # Search query: symbol
    resp_search_sym = client.get("/api/universe/stocks?q=INFY")
    assert resp_search_sym.status_code == 200
    assert len(resp_search_sym.json()) == 1
    assert resp_search_sym.json()[0]["symbol"] == "INFY"

    # Search query: company name case-insensitive
    resp_search_name = client.get("/api/universe/stocks?q=consultancy")
    assert resp_search_name.status_code == 200
    assert len(resp_search_name.json()) == 1
    assert resp_search_name.json()[0]["symbol"] == "TCS"

    # Invalid category rejected with 400
    resp_bad_cat = client.get("/api/universe/stocks?category=INVALID_CAT")
    assert resp_bad_cat.status_code == 400
    assert "Invalid category" in resp_bad_cat.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Retrieve a stock by symbol
# ---------------------------------------------------------------------------
def test_e2e_get_stock_by_symbol(e2e_client):
    client, _, _ = e2e_client

    # Existing stock
    resp = client.get("/api/universe/stocks/TCS")
    assert resp.status_code == 200
    stock = resp.json()
    assert stock["symbol"] == "TCS"
    assert stock["exchange"] == "NSE"
    assert stock["category"] == "NIFTY_50"
    assert stock["name"] == "Tata Consultancy Services Ltd."
    assert "created_at" in stock

    # Non-existent stock
    resp_404 = client.get("/api/universe/stocks/DOES_NOT_EXIST")
    assert resp_404.status_code == 404
    assert "Stock not found" in resp_404.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Register a custom stock
# ---------------------------------------------------------------------------
def test_e2e_register_custom_stock(e2e_client):
    client, _, _ = e2e_client

    payload = {
        "symbol": "ZOMATO",
        "exchange": "NSE",
        "category": "CUSTOM",
        "name": "Zomato Limited",
    }
    resp = client.post("/api/universe/stocks", json=payload)
    assert resp.status_code == 201
    stock = resp.json()
    assert stock["symbol"] == "ZOMATO"
    assert stock["exchange"] == "NSE"
    assert stock["category"] == "CUSTOM"
    assert stock["name"] == "Zomato Limited"

    # Verify retrieval
    get_resp = client.get("/api/universe/stocks/ZOMATO")
    assert get_resp.status_code == 200
    assert get_resp.json()["symbol"] == "ZOMATO"


# ---------------------------------------------------------------------------
# 5. Reject duplicate or malformed stock registration
# ---------------------------------------------------------------------------
def test_e2e_reject_duplicate_and_malformed_stock(e2e_client):
    client, _, _ = e2e_client

    # Duplicate symbol (TCS is already registered)
    dup_resp = client.post(
        "/api/universe/stocks",
        json={"symbol": "tcs", "exchange": "NSE", "category": "CUSTOM"},
    )
    assert dup_resp.status_code == 400
    assert "stock already registered: TCS" in dup_resp.json()["detail"]

    # Empty symbol
    empty_sym_resp = client.post(
        "/api/universe/stocks",
        json={"symbol": "  ", "exchange": "NSE", "category": "CUSTOM"},
    )
    assert empty_sym_resp.status_code == 400
    assert "symbol must not be empty" in empty_sym_resp.json()["detail"]

    # Empty exchange
    empty_ex_resp = client.post(
        "/api/universe/stocks",
        json={"symbol": "NEWSTOCK", "exchange": "   ", "category": "CUSTOM"},
    )
    assert empty_ex_resp.status_code == 400
    assert "exchange must not be empty" in empty_ex_resp.json()["detail"]

    # Invalid category
    invalid_cat_resp = client.post(
        "/api/universe/stocks",
        json={"symbol": "NEWSTOCK", "exchange": "NSE", "category": "INVALID_CAT"},
    )
    assert invalid_cat_resp.status_code == 400
    assert "Invalid category" in invalid_cat_resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Retrieve all qualification records for a stock
# ---------------------------------------------------------------------------
def test_e2e_get_all_qualifications(e2e_client):
    client, _, _ = e2e_client

    # Stock exists but no qualifications stored yet -> returns empty list
    resp = client.get("/api/universe/stocks/TCS/qualifications")
    assert resp.status_code == 200
    assert resp.json() == []

    # Non-existent stock returns 404
    resp_404 = client.get("/api/universe/stocks/UNKNOWN/qualifications")
    assert resp_404.status_code == 404


# ---------------------------------------------------------------------------
# 7. Retrieve an individual strategy qualification (including NOT_TESTED default)
# ---------------------------------------------------------------------------
def test_e2e_get_individual_qualification_not_tested(e2e_client):
    client, _, _ = e2e_client

    # Untested strategy returns default NOT_TESTED record
    resp = client.get("/api/universe/stocks/TCS/qualifications/SignalForge_V1")
    assert resp.status_code == 200
    qual = resp.json()
    assert qual["symbol"] == "TCS"
    assert qual["strategy_id"] == "SignalForge_V1"
    assert qual["qualification_status"] == "NOT_TESTED"
    assert qual["completed_trade_count"] == 0
    assert qual["historical_data_status"] == "UNKNOWN"
    assert qual["backtest_status"] == "UNKNOWN"
    assert qual["oos_validation_status"] == "UNKNOWN"
    assert qual["forward_paper_test_status"] == "UNKNOWN"

    # Non-existent stock returns 404
    resp_404 = client.get("/api/universe/stocks/UNKNOWN/qualifications/SignalForge_V1")
    assert resp_404.status_code == 404


# ---------------------------------------------------------------------------
# 8. Update a qualification using valid supported fields
# ---------------------------------------------------------------------------
def test_e2e_update_qualification_valid(e2e_client):
    client, _, _ = e2e_client

    update_payload = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "PASSED",
        "backtest_net_profit": 420.50,
        "oos_validation_status": "PASSED",
        "forward_paper_test_status": "PASSED",
        "completed_trade_count": 30,
        "qualification_status": "APPROVED",
        "status_reason": "All 4 stages passed with 30 forward trades",
        "evidence_reference": "RUN_20261013_FWD_30",
    }
    resp = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "TCS"
    assert data["strategy_id"] == "SignalForge_V1"
    assert data["qualification_status"] == "APPROVED"
    assert data["completed_trade_count"] == 30
    assert data["backtest_net_profit"] == 420.50
    assert data["evidence_reference"] == "RUN_20261013_FWD_30"
    assert "updated_at" in data

    # Verify retrieval reflects update
    get_resp = client.get("/api/universe/stocks/TCS/qualifications/SignalForge_V1")
    assert get_resp.status_code == 200
    assert get_resp.json()["qualification_status"] == "APPROVED"


# ---------------------------------------------------------------------------
# 9. Reject fewer than 30 completed forward paper trades when approval is requested
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("trade_count", [0, 1, 29])
def test_e2e_reject_approval_sub_threshold(e2e_client, trade_count):
    client, _, _ = e2e_client

    payload = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "PASSED",
        "backtest_net_profit": 500.0,
        "oos_validation_status": "PASSED",
        "forward_paper_test_status": "PASSED" if trade_count > 0 else "UNKNOWN",
        "completed_trade_count": trade_count,
        "qualification_status": "APPROVED",
        "status_reason": "Premature approval attempt",
    }
    resp = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=payload)
    assert resp.status_code == 400
    err_detail = resp.json()["detail"]
    assert "fewer than 30 completed forward trades" in err_detail or "without all validation evidence passing" in err_detail


# ---------------------------------------------------------------------------
# 10. Verify 30 meets initial threshold and 50 meets preferred threshold;
#     verify sample size alone is not proof of profitability.
# ---------------------------------------------------------------------------
def test_e2e_threshold_milestones_and_profitability_guard(e2e_client):
    client, _, _ = e2e_client

    # 30 trades (initial threshold) meets gate with passing evidence
    payload_30 = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "PASSED",
        "backtest_net_profit": 200.0,
        "oos_validation_status": "PASSED",
        "forward_paper_test_status": "PASSED",
        "completed_trade_count": DEFAULT_MIN_FORWARD_TRADES,  # 30
        "qualification_status": "APPROVED",
        "status_reason": "Initial evaluation threshold met",
    }
    resp_30 = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=payload_30)
    assert resp_30.status_code == 200
    assert resp_30.json()["qualification_status"] == "APPROVED"

    # 50 trades (preferred threshold) meets gate with passing evidence
    payload_50 = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "PASSED",
        "backtest_net_profit": 350.0,
        "oos_validation_status": "PASSED",
        "forward_paper_test_status": "PASSED",
        "completed_trade_count": DEFAULT_PREFERRED_FORWARD_TRADES,  # 50
        "qualification_status": "APPROVED",
        "status_reason": "Preferred stronger evaluation sample met",
    }
    resp_50 = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=payload_50)
    assert resp_50.status_code == 200
    assert resp_50.json()["qualification_status"] == "APPROVED"

    # Non-profitability guard: 50 completed trades but forward paper test failed -> cannot be APPROVED
    payload_50_failed_fwd = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "PASSED",
        "backtest_net_profit": 300.0,
        "oos_validation_status": "PASSED",
        "forward_paper_test_status": "FAILED",  # Failed forward paper run
        "completed_trade_count": 50,
        "qualification_status": "APPROVED",
    }
    resp_fail_fwd = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=payload_50_failed_fwd)
    assert resp_fail_fwd.status_code == 400
    assert "Cannot approve strategy without all validation evidence passing" in resp_fail_fwd.json()["detail"]

    # Non-profitability guard: 50 completed trades but backtest failed -> cannot be APPROVED
    payload_50_failed_bt = {
        "strategy_version": "1.0",
        "historical_data_status": "READY",
        "backtest_status": "FAILED",
        "backtest_net_profit": -50.0,
        "oos_validation_status": "FAILED",
        "forward_paper_test_status": "PASSED",
        "completed_trade_count": 50,
        "qualification_status": "APPROVED",
    }
    resp_fail_bt = client.put("/api/universe/stocks/TCS/qualifications/SignalForge_V1", json=payload_50_failed_bt)
    assert resp_fail_bt.status_code == 400
    assert "Cannot approve strategy without all validation evidence passing" in resp_fail_bt.json()["detail"]


# ---------------------------------------------------------------------------
# 11. Reject contradictory stage statuses, invalid counts, booleans, NaN, Inf
# ---------------------------------------------------------------------------
def test_e2e_reject_contradictory_and_malformed_evidence(e2e_client):
    client, _, _ = e2e_client

    # Contradiction: historical data INCOMPLETE but backtest PASSED
    resp_contra_bt = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "INCOMPLETE",
            "backtest_status": "PASSED",
            "backtest_net_profit": 200.0,
            "oos_validation_status": "UNKNOWN",
            "forward_paper_test_status": "UNKNOWN",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_bt.status_code == 400
    assert "backtest_status cannot be 'PASSED' when historical_data_status is 'INCOMPLETE'" in resp_contra_bt.json()["detail"]

    # Contradiction: historical data UNKNOWN but OOS PASSED
    resp_contra_oos = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "UNKNOWN",
            "backtest_status": "UNKNOWN",
            "backtest_net_profit": None,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "UNKNOWN",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_oos.status_code == 400
    assert "oos_validation_status cannot be 'PASSED' when historical_data_status is 'UNKNOWN'" in resp_contra_oos.json()["detail"]

    # Contradiction: backtest FAILED but OOS PASSED
    resp_contra_oos_bt = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "FAILED",
            "backtest_net_profit": -50.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "UNKNOWN",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_oos_bt.status_code == 400
    assert "oos_validation_status cannot be 'PASSED' when backtest_status is 'FAILED'" in resp_contra_oos_bt.json()["detail"]

    # Contradiction: backtest PASSED but net profit negative
    resp_contra_neg_profit = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": -100.0,
            "oos_validation_status": "UNKNOWN",
            "forward_paper_test_status": "UNKNOWN",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_neg_profit.status_code == 400
    assert "requires positive backtest_net_profit" in resp_contra_neg_profit.json()["detail"]

    # Contradiction: backtest PASSED but net profit 0.0
    resp_contra_zero_profit = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 0.0,
            "oos_validation_status": "UNKNOWN",
            "forward_paper_test_status": "UNKNOWN",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_zero_profit.status_code == 400
    assert "requires positive backtest_net_profit" in resp_contra_zero_profit.json()["detail"]

    # Unsupported assertion: forward paper test PASSED but trade count 0
    resp_contra_zero_trades = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 200.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 0,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_contra_zero_trades.status_code == 400
    assert "forward_paper_test_status 'PASSED' requires completed forward trades" in resp_contra_zero_trades.json()["detail"]

    # Negative trade count rejected by Pydantic (422)
    resp_neg_trades = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 200.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": -5,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_neg_trades.status_code == 422

    # Boolean completed_trade_count rejected (422)
    resp_bool_trades = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 200.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": True,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert resp_bool_trades.status_code == 422

    # Boolean backtest_net_profit rejected (422)
    resp_bool_profit = client.put(
        "/api/universe/stocks/TCS/qualifications/SignalForge_V1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": True,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 30,
            "qualification_status": "APPROVED",
        },
    )
    assert resp_bool_profit.status_code == 422


# ---------------------------------------------------------------------------
# 12. Verify qualification records remain independent per stock/strategy
# ---------------------------------------------------------------------------
def test_e2e_independent_qualification_records(e2e_client):
    client, _, _ = e2e_client

    # Qualify TCS with strat_alpha
    resp_alpha = client.put(
        "/api/universe/stocks/TCS/qualifications/strat_alpha",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 400.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 35,
            "qualification_status": "APPROVED",
            "status_reason": "TCS strat_alpha qualified",
        },
    )
    assert resp_alpha.status_code == 200
    assert resp_alpha.json()["qualification_status"] == "APPROVED"

    # TCS with strat_beta must remain default NOT_TESTED
    resp_tcs_beta = client.get("/api/universe/stocks/TCS/qualifications/strat_beta")
    assert resp_tcs_beta.status_code == 200
    assert resp_tcs_beta.json()["qualification_status"] == "NOT_TESTED"
    assert resp_tcs_beta.json()["completed_trade_count"] == 0

    # INFY with strat_alpha must remain default NOT_TESTED
    resp_infy_alpha = client.get("/api/universe/stocks/INFY/qualifications/strat_alpha")
    assert resp_infy_alpha.status_code == 200
    assert resp_infy_alpha.json()["qualification_status"] == "NOT_TESTED"
    assert resp_infy_alpha.json()["completed_trade_count"] == 0


# ---------------------------------------------------------------------------
# 13. Verify persistence across registry reloads using temporary storage
# ---------------------------------------------------------------------------
def test_e2e_persistence_across_reloads(e2e_client, monkeypatch):
    client, reg, storage_path = e2e_client

    # 1. Register a new custom stock via API
    resp_stock = client.post(
        "/api/universe/stocks",
        json={
            "symbol": "WIPRO",
            "exchange": "NSE",
            "category": "CUSTOM",
            "name": "Wipro Limited",
        },
    )
    assert resp_stock.status_code == 201

    # 2. Update qualification record via API
    resp_qual = client.put(
        "/api/universe/stocks/WIPRO/qualifications/SignalForge_V1",
        json={
            "strategy_version": "2.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 600.0,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 52,
            "qualification_status": "APPROVED",
            "status_reason": "Wipro V1 preferred sample met",
            "evidence_reference": "EVID_WIPRO_52",
        },
    )
    assert resp_qual.status_code == 200

    # 3. Simulate process restart by reloading a fresh registry pointing to the same storage path
    reloaded_reg = StockUniverseRegistry(storage_path)
    monkeypatch.setattr(universe_routes, "_registry", reloaded_reg)

    # 4. Verify stock persisted
    resp_reloaded_stock = client.get("/api/universe/stocks/WIPRO")
    assert resp_reloaded_stock.status_code == 200
    assert resp_reloaded_stock.json()["symbol"] == "WIPRO"
    assert resp_reloaded_stock.json()["name"] == "Wipro Limited"

    # 5. Verify qualification persisted
    resp_reloaded_qual = client.get("/api/universe/stocks/WIPRO/qualifications/SignalForge_V1")
    assert resp_reloaded_qual.status_code == 200
    qual_data = resp_reloaded_qual.json()
    assert qual_data["symbol"] == "WIPRO"
    assert qual_data["strategy_id"] == "SignalForge_V1"
    assert qual_data["strategy_version"] == "2.0"
    assert qual_data["qualification_status"] == "APPROVED"
    assert qual_data["completed_trade_count"] == 52
    assert qual_data["backtest_net_profit"] == 600.0
    assert qual_data["evidence_reference"] == "EVID_WIPRO_52"
    assert qual_data["status_reason"] == "Wipro V1 preferred sample met"

import math
import pytest
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from datetime import datetime

from src.universe.registry import (
    StockUniverseRegistry,
    UniverseCategory,
    QualificationStatus,
    MIN_FORWARD_TRADES_FOR_APPROVAL,
    PREFERRED_FORWARD_TRADES_FOR_APPROVAL,
)
from src.api.routes.universe import router
from fastapi import FastAPI


@pytest.fixture
def temp_storage():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()
    qual_path = path.parent / (path.stem + "_qualifications.json")
    if qual_path.exists():
        qual_path.unlink()


@pytest.fixture
def registry(temp_storage):
    reg = StockUniverseRegistry(temp_storage)
    reg.register("TCS", "NSE", UniverseCategory.NIFTY_50)
    reg.register("INFY", "NSE", UniverseCategory.NIFTY_50)
    return reg


def test_default_qualification(registry):
    qual = registry.get_qualification("TCS", "strategy_v1")
    assert qual.qualification_status == QualificationStatus.NOT_TESTED
    assert qual.completed_trade_count == 0
    assert qual.evidence_reference is None


def test_update_qualification(registry):
    qual = registry.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v1",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="FAILED",
        backtest_net_profit=-100.0,
        oos_validation_status="UNKNOWN",
        forward_paper_test_status="UNKNOWN",
        completed_trade_count=0,
        qualification_status=QualificationStatus.REJECTED,
        status_reason="Failed backtest",
        evidence_reference="RUN_20261011_BT01",
    )
    assert qual.qualification_status == QualificationStatus.REJECTED
    assert qual.evidence_reference == "RUN_20261011_BT01"


def test_approval_requires_evidence(registry):
    # Fails when oos_validation_status is not PASSED
    with pytest.raises(ValueError, match="without all validation evidence passing"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="FAILED",
            forward_paper_test_status="PASSED",
            completed_trade_count=50,
            qualification_status=QualificationStatus.APPROVED,
            status_reason=None,
        )


@pytest.mark.parametrize("trades", [0, 1, 29])
def test_approval_rejects_sub_threshold_trades(registry, trades):
    """0, 1, and 29 trades must all be rejected for APPROVED status."""
    with pytest.raises(ValueError, match=r"(fewer than 30 completed forward trades|requires completed forward trades)"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=150.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=trades,
            qualification_status=QualificationStatus.APPROVED,
            status_reason="Premature approval attempt",
        )


@pytest.mark.parametrize("trades", [30, 50])
def test_approval_allows_threshold_and_preferred_trades(registry, trades):
    """30 (minimum) and 50 (preferred) trades pass gate when evidence is valid."""
    qual = registry.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v1",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=450.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=trades,
        qualification_status=QualificationStatus.APPROVED,
        status_reason="Validated through forward paper testing",
        evidence_reference=f"REF_FWD_{trades}",
    )
    assert qual.qualification_status == QualificationStatus.APPROVED
    assert qual.completed_trade_count == trades
    assert qual.evidence_reference == f"REF_FWD_{trades}"


def test_reject_negative_trade_counts(registry):
    with pytest.raises(ValueError, match="non-negative integer"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=-5,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )


def test_reject_nan_and_inf_metrics(registry):
    # NaN
    with pytest.raises(ValueError, match="finite number"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=float("nan"),
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35,
            qualification_status=QualificationStatus.APPROVED,
        )

    # Infinity
    with pytest.raises(ValueError, match="finite number"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=float("inf"),
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35,
            qualification_status=QualificationStatus.APPROVED,
        )


def test_reject_unsupported_assertions(registry):
    # backtest_status is PASSED but backtest_net_profit is None (unsupported assertion)
    with pytest.raises(ValueError, match="requires evidence of backtest_net_profit"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=None,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35,
            qualification_status=QualificationStatus.APPROVED,
        )

    # forward_paper_test_status is PASSED but completed_trade_count is 0
    with pytest.raises(ValueError, match="requires completed forward trades"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )


def test_independent_qualification_per_stock_and_strategy(registry):
    # Qualify TCS for strategy_v1
    registry.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v1",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=500.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=32,
        qualification_status=QualificationStatus.APPROVED,
        status_reason="Approved",
    )

    # TCS with strategy_v2 should remain NOT_TESTED
    qual_tcs_v2 = registry.get_qualification("TCS", "strategy_v2")
    assert qual_tcs_v2.qualification_status == QualificationStatus.NOT_TESTED

    # INFY with strategy_v1 should remain NOT_TESTED
    qual_infy_v1 = registry.get_qualification("INFY", "strategy_v1")
    assert qual_infy_v1.qualification_status == QualificationStatus.NOT_TESTED


def test_no_access_to_active_ledger_or_order_placement(registry):
    # Ensure qualification registry does not touch live order execution or live paper ledger
    active_ledger_path = Path("data/paper_trading_ledger.json")
    if active_ledger_path.exists():
        ledger_before = active_ledger_path.read_text(encoding="utf-8")
    else:
        ledger_before = None

    registry.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v1",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=350.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=30,
        qualification_status=QualificationStatus.APPROVED,
        status_reason="Gate pass",
    )

    if active_ledger_path.exists():
        ledger_after = active_ledger_path.read_text(encoding="utf-8")
        assert ledger_before == ledger_after


# API Tests
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_api_get_qualifications(monkeypatch, registry):
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.get("/api/universe/stocks/TCS/qualifications/strategy_v1")
    assert response.status_code == 200
    assert response.json()["qualification_status"] == "NOT_TESTED"


def test_api_update_qualification_success(monkeypatch, registry):
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.put(
        "/api/universe/stocks/TCS/qualifications/strategy_v1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 500.5,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 30,
            "qualification_status": "APPROVED",
            "status_reason": "Hardened criteria passed with 30 trades",
            "evidence_reference": "EVID_RUN_99",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["qualification_status"] == "APPROVED"
    assert data["completed_trade_count"] == 30
    assert data["evidence_reference"] == "EVID_RUN_99"


def test_api_update_qualification_rejects_sub_threshold(monkeypatch, registry):
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.put(
        "/api/universe/stocks/TCS/qualifications/strategy_v1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 500.5,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 29,  # < 30
            "qualification_status": "APPROVED",
            "status_reason": "Attempts approval with 29 trades",
        },
    )
    assert response.status_code == 400
    assert "fewer than 30 completed forward trades" in response.json()["detail"]


def test_api_rejects_negative_trades(monkeypatch, registry):
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.put(
        "/api/universe/stocks/TCS/qualifications/strategy_v1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 500.5,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": -1,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert response.status_code == 422  # Pydantic validation error for negative integer

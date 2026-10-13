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


def test_configurable_threshold_on_registry(temp_storage):
    """Test registry configured with custom thresholds and per-call overrides."""
    # Custom registry with min 40 trades and preferred 60 trades
    custom_reg = StockUniverseRegistry(
        temp_storage,
        min_forward_trades=40,
        preferred_forward_trades=60,
    )
    custom_reg.register("TCS", "NSE", UniverseCategory.NIFTY_50)

    # 30 trades fails on custom threshold (40 required)
    with pytest.raises(ValueError, match="fewer than 40 completed forward trades"):
        custom_reg.update_qualification(
            symbol="TCS",
            strategy_id="strategy_v1",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=200.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=30,
            qualification_status=QualificationStatus.APPROVED,
        )

    # 40 trades passes
    qual = custom_reg.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v1",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=200.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=40,
        qualification_status=QualificationStatus.APPROVED,
    )
    assert qual.qualification_status == QualificationStatus.APPROVED
    assert qual.completed_trade_count == 40
    assert qual.meets_initial_threshold is True
    assert qual.meets_preferred_threshold is False
    assert qual.is_approved is True

    # Per-call override: allows custom threshold of 25 trades
    qual_override = custom_reg.update_qualification(
        symbol="TCS",
        strategy_id="strategy_v2",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=300.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=25,
        qualification_status=QualificationStatus.APPROVED,
        min_forward_trades=25,
    )
    assert qual_override.qualification_status == QualificationStatus.APPROVED

    # Invalid constructor configuration
    with pytest.raises(ValueError, match="non-negative integer"):
        StockUniverseRegistry(temp_storage, min_forward_trades=-10)
    with pytest.raises(ValueError, match="non-negative integer"):
        StockUniverseRegistry(temp_storage, min_forward_trades=True)


def test_contradictory_evidence_validation(registry):
    """Test contradictory evidence combinations between pipeline stages."""
    # Contradiction: historical data INCOMPLETE but backtest claims PASSED
    with pytest.raises(ValueError, match="backtest_status cannot be 'PASSED' when historical_data_status is 'INCOMPLETE'"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_contra",
            strategy_version="1.0",
            historical_data_status="INCOMPLETE",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="UNKNOWN",
            forward_paper_test_status="UNKNOWN",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )

    # Contradiction: historical data UNKNOWN but OOS claims PASSED
    with pytest.raises(ValueError, match="oos_validation_status cannot be 'PASSED' when historical_data_status is 'UNKNOWN'"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_contra",
            strategy_version="1.0",
            historical_data_status="UNKNOWN",
            backtest_status="UNKNOWN",
            backtest_net_profit=None,
            oos_validation_status="PASSED",
            forward_paper_test_status="UNKNOWN",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )

    # Contradiction: backtest FAILED but OOS claims PASSED
    with pytest.raises(ValueError, match="oos_validation_status cannot be 'PASSED' when backtest_status is 'FAILED'"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_contra",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="FAILED",
            backtest_net_profit=-50.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="UNKNOWN",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )

    # Contradiction: backtest PASSED but net profit is negative
    with pytest.raises(ValueError, match="requires positive backtest_net_profit"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_contra",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=-150.0,
            oos_validation_status="UNKNOWN",
            forward_paper_test_status="UNKNOWN",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )

    # Contradiction: backtest PASSED but net profit is 0.0
    with pytest.raises(ValueError, match="requires positive backtest_net_profit"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_contra",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=0.0,
            oos_validation_status="UNKNOWN",
            forward_paper_test_status="UNKNOWN",
            completed_trade_count=0,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )


def test_threshold_alone_not_proof_of_profitability(registry):
    """50 trades with failed validation cannot be approved."""
    # 50 completed trades, but forward paper test failed
    with pytest.raises(ValueError, match="without all validation evidence passing"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_50_failed",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="FAILED",
            completed_trade_count=50,
            qualification_status=QualificationStatus.APPROVED,
        )

    # 50 completed trades, but backtest failed
    with pytest.raises(ValueError, match="without all validation evidence passing"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_50_failed_bt",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="FAILED",
            backtest_net_profit=-20.0,
            oos_validation_status="FAILED",
            forward_paper_test_status="PASSED",
            completed_trade_count=50,
            qualification_status=QualificationStatus.APPROVED,
        )


def test_malformed_numeric_and_boolean_types(registry):
    """Reject boolean types masquerading as int/float and negative/non-finite values."""
    # Boolean completed_trade_count
    with pytest.raises(ValueError, match="non-negative integer"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_bool",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=True,
            qualification_status=QualificationStatus.IN_PROGRESS,
        )

    # Float completed_trade_count
    with pytest.raises(ValueError, match="non-negative integer"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_float",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=100.0,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35.5,
            qualification_status=QualificationStatus.APPROVED,
        )

    # Boolean backtest_net_profit
    with pytest.raises(ValueError, match="finite number"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_profit_bool",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=True,
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35,
            qualification_status=QualificationStatus.APPROVED,
        )

    # Negative Infinity backtest_net_profit
    with pytest.raises(ValueError, match="finite number"):
        registry.update_qualification(
            symbol="TCS",
            strategy_id="strat_profit_neginf",
            strategy_version="1.0",
            historical_data_status="READY",
            backtest_status="PASSED",
            backtest_net_profit=float("-inf"),
            oos_validation_status="PASSED",
            forward_paper_test_status="PASSED",
            completed_trade_count=35,
            qualification_status=QualificationStatus.APPROVED,
        )


def test_evidence_reference_and_reason_recording(registry):
    """Verify evidence reference and auto-generated status reasons are cleanly stored."""
    qual = registry.update_qualification(
        symbol="TCS",
        strategy_id="strat_clean",
        strategy_version="1.0",
        historical_data_status="READY",
        backtest_status="PASSED",
        backtest_net_profit=500.0,
        oos_validation_status="PASSED",
        forward_paper_test_status="PASSED",
        completed_trade_count=50,
        qualification_status=QualificationStatus.APPROVED,
        status_reason=None,  # Should generate informative approval reason
        evidence_reference="   REF_EVID_WHITESPACE   ",
    )
    assert qual.evidence_reference == "REF_EVID_WHITESPACE"
    assert "Approved: met all qualification gates with 50 completed forward trades" in qual.status_reason
    assert qual.meets_preferred_threshold is True


def test_api_contradictory_evidence_rejected(monkeypatch, registry):
    """API endpoint returns 400 when contradictory evidence is submitted."""
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.put(
        "/api/universe/stocks/TCS/qualifications/strategy_v1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "INCOMPLETE",
            "backtest_status": "PASSED",
            "backtest_net_profit": 500.5,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 30,
            "qualification_status": "APPROVED",
        },
    )
    assert response.status_code == 400
    assert "backtest_status cannot be 'PASSED' when historical_data_status is 'INCOMPLETE'" in response.json()["detail"]


def test_api_rejects_boolean_trades(monkeypatch, registry):
    """API model rejects booleans for completed_trade_count with 422."""
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
            "completed_trade_count": True,
            "qualification_status": "IN_PROGRESS",
        },
    )
    assert response.status_code == 422


def test_api_unregistered_stock(monkeypatch, registry):
    """API returns 404 for non-registered stock symbol."""
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", registry)

    response = client.put(
        "/api/universe/stocks/UNKNOWN_STOCK/qualifications/strategy_v1",
        json={
            "strategy_version": "1.0",
            "historical_data_status": "READY",
            "backtest_status": "PASSED",
            "backtest_net_profit": 500.5,
            "oos_validation_status": "PASSED",
            "forward_paper_test_status": "PASSED",
            "completed_trade_count": 30,
            "qualification_status": "APPROVED",
        },
    )
    assert response.status_code == 404


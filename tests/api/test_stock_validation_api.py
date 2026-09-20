from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import stocks
from src.universe.validation import ValidationStatus
from src.validation.approval import ApprovalResult
from src.validation.stock_validator import StockValidationResult


client = TestClient(app)


def setup_function() -> None:
    stocks._universe = stocks.UniverseManager()


def make_result(
    symbol: str,
    status: ValidationStatus,
) -> StockValidationResult:
    approved = status is ValidationStatus.VALIDATED

    approval = ApprovalResult(
        status=status,
        signal_eligible=approved,
        approved=approved,
        passed_gates=(
            (
                "DATA_AVAILABILITY",
                "DATA_QUALITY",
                "INDICATOR_COMPATIBILITY",
                "HISTORICAL_BACKTEST",
                "CAUSALITY",
                "COST_SLIPPAGE",
                "REGIME_OOS",
            )
            if approved
            else ()
        ),
        failed_gates=(
            ()
            if approved
            else ("REGIME_OOS",)
        ),
        issues=(
            ()
            if approved
            else ("validation failed",)
        ),
    )

    return StockValidationResult(
        symbol=symbol,
        data_availability=None,
        data_quality=None,
        indicator_compatibility=None,
        historical_backtest=None,
        causality=None,
        cost_slippage=None,
        regime_oos=None,
        approval=approval,
    )


class FakeService:
    def __init__(
        self,
        result: StockValidationResult,
    ) -> None:
        self.result = result
        self.calls: list[str] = []

    def validate_from_local_and_update_universe(
        self,
        symbol: str,
    ) -> StockValidationResult:
        self.calls.append(symbol)

        stocks._universe.set_validation_status(
            symbol,
            self.result.status,
        )

        return self.result


def test_validation_status_for_new_stock_is_testing() -> None:
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    assert response.status_code == 201

    response = client.get(
        "/api/stocks/TESTSTOCK/validation",
    )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "TESTSTOCK",
        "status": "TESTING",
        "signal_eligible": False,
        "approved": False,
        "passed_gates": [],
        "failed_gates": [],
        "issues": [],
    }


def test_validate_unknown_stock_returns_not_found() -> None:
    response = client.post(
        "/api/stocks/UNKNOWN/validate",
    )

    assert response.status_code == 404


def test_validated_result_updates_universe(
    monkeypatch,
) -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    result = make_result(
        "TESTSTOCK",
        ValidationStatus.VALIDATED,
    )

    service = FakeService(result)

    monkeypatch.setattr(
        stocks,
        "_build_validation_service",
        lambda: service,
    )

    response = client.post(
        "/api/stocks/TESTSTOCK/validate",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "TESTSTOCK"
    assert body["status"] == "VALIDATED"
    assert body["signal_eligible"] is True
    assert body["approved"] is True

    assert body["passed_gates"] == [
        "DATA_AVAILABILITY",
        "DATA_QUALITY",
        "INDICATOR_COMPATIBILITY",
        "HISTORICAL_BACKTEST",
        "CAUSALITY",
        "COST_SLIPPAGE",
        "REGIME_OOS",
    ]

    assert body["failed_gates"] == []
    assert body["issues"] == []

    assert service.calls == ["TESTSTOCK"]

    status_response = client.get(
        "/api/stocks/TESTSTOCK/validation",
    )

    assert status_response.status_code == 200

    assert status_response.json()["status"] == "VALIDATED"
    assert status_response.json()["signal_eligible"] is True


def test_failed_result_blocks_signal_eligibility(
    monkeypatch,
) -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    result = make_result(
        "TESTSTOCK",
        ValidationStatus.FAILED,
    )

    service = FakeService(result)

    monkeypatch.setattr(
        stocks,
        "_build_validation_service",
        lambda: service,
    )

    response = client.post(
        "/api/stocks/TESTSTOCK/validate",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "FAILED"
    assert body["signal_eligible"] is False
    assert body["approved"] is False
    assert body["passed_gates"] == []
    assert body["failed_gates"] == ["REGIME_OOS"]
    assert body["issues"] == ["validation failed"]

    status_response = client.get(
        "/api/stocks/TESTSTOCK/validation",
    )

    assert status_response.status_code == 200

    assert status_response.json()["status"] == "FAILED"
    assert status_response.json()["signal_eligible"] is False


def test_validation_preserves_seven_gate_contract(
    monkeypatch,
) -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    result = make_result(
        "TESTSTOCK",
        ValidationStatus.VALIDATED,
    )

    monkeypatch.setattr(
        stocks,
        "_build_validation_service",
        lambda: FakeService(result),
    )

    response = client.post(
        "/api/stocks/TESTSTOCK/validate",
    )

    assert response.status_code == 200

    body = response.json()

    expected_gates = {
        "DATA_AVAILABILITY",
        "DATA_QUALITY",
        "INDICATOR_COMPATIBILITY",
        "HISTORICAL_BACKTEST",
        "CAUSALITY",
        "COST_SLIPPAGE",
        "REGIME_OOS",
    }

    assert set(body["passed_gates"]) == expected_gates
    assert len(body["passed_gates"]) == 7

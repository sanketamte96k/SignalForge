from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import stocks


client = TestClient(app)


def setup_function() -> None:
    stocks._universe = stocks.UniverseManager()


def test_search_existing_nifty_stock() -> None:
    response = client.get(
        "/api/stocks/search?q=RELIANCE",
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["results"]) >= 1

    reliance = next(
        item
        for item in body["results"]
        if item["symbol"] == "RELIANCE"
    )

    assert reliance["name"]
    assert reliance["exchange"] == "NSE"
    assert reliance["validation_status"] == "TESTING"
    assert reliance["signal_eligible"] is False


def test_search_is_case_insensitive() -> None:
    response = client.get(
        "/api/stocks/search?q=reliance",
    )

    assert response.status_code == 200

    symbols = [
        item["symbol"]
        for item in response.json()["results"]
    ]

    assert "RELIANCE" in symbols


def test_search_empty_query_returns_validation_error() -> None:
    response = client.get(
        "/api/stocks/search?q=",
    )

    assert response.status_code == 422


def test_add_stock_starts_in_testing() -> None:
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    assert response.status_code == 201

    assert response.json() == {
        "symbol": "TESTSTOCK",
        "name": "Test Stock Industries",
        "exchange": "NSE",
        "instrument_type": "EQUITY",
        "validation_status": "TESTING",
        "signal_eligible": False,
    }


def test_added_stock_can_be_retrieved() -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    response = client.get(
        "/api/stocks/TESTSTOCK",
    )

    assert response.status_code == 200

    assert response.json()["symbol"] == "TESTSTOCK"
    assert response.json()["validation_status"] == "TESTING"
    assert response.json()["signal_eligible"] is False


def test_added_stock_is_searchable() -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    response = client.get(
        "/api/stocks/search?q=Test%20Stock",
    )

    assert response.status_code == 200

    symbols = [
        item["symbol"]
        for item in response.json()["results"]
    ]

    assert "TESTSTOCK" in symbols


def test_duplicate_stock_returns_bad_request() -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    response = client.post(
        "/api/stocks",
        json={
            "symbol": "teststock",
            "name": "Another Test Stock",
        },
    )

    assert response.status_code == 400


def test_existing_nifty_stock_cannot_be_added_again() -> None:
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "RELIANCE",
            "name": "Reliance Industries",
        },
    )

    assert response.status_code == 400


def test_unknown_stock_returns_not_found() -> None:
    response = client.get(
        "/api/stocks/NOT_A_REAL_STOCK",
    )

    assert response.status_code == 404


def test_added_stock_remains_ineligible_until_validation() -> None:
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "TESTSTOCK",
            "name": "Test Stock Industries",
        },
    )

    assert response.status_code == 201

    assert response.json()["validation_status"] == "TESTING"
    assert response.json()["signal_eligible"] is False

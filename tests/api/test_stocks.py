"""Tests for the NIFTY 50 stock scanner API."""

from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_stock_scanner_returns_50_stocks() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["universe"] == "NIFTY 50"
    assert payload["total_stocks"] == 50
    assert len(payload["items"]) == 50


def test_stock_scanner_symbols_are_unique() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    symbols = [
        item["symbol"]
        for item in payload["items"]
    ]

    assert len(symbols) == len(
        set(symbols)
    )


def test_stock_scanner_items_have_required_fields() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    required_fields = {
        "symbol",
        "name",
        "exchange",
        "validation_status",
        "signal_eligible",
        "signal",
        "position",
        "timestamp",
        "price",
        "score",
        "confidence",
        "timeframe_alignment",
        "reason",
    }

    for item in payload["items"]:
        assert required_fields.issubset(
            item.keys()
        )


def test_unvalidated_stocks_cannot_generate_signals() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    for item in payload["items"]:
        assert item["validation_status"] == "TESTING"
        assert item["signal_eligible"] is False
        assert item["signal"] == "NO_TRADE"
        assert item["position"] is None
        assert item["score"] is None
        assert item["confidence"] is None
        assert item["timeframe_alignment"] is None


def test_current_project_has_no_approved_stock_signals() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    assert payload["signal_eligible_stocks"] == 0
    assert payload["buy_count"] == 0
    assert payload["sell_count"] == 0
    assert payload["no_trade_count"] == 50


def test_scanner_response_has_consistent_counts() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    assert (
        payload["buy_count"]
        + payload["sell_count"]
        + payload["no_trade_count"]
        == payload["total_stocks"]
    )

    assert (
        payload["signal_eligible_stocks"]
        <= payload["total_stocks"]
    )


def test_scanner_does_not_create_synthetic_price_data() -> None:
    response = client.get(
        "/api/stocks/scanner"
    )

    payload = response.json()

    for item in payload["items"]:
        if not item["signal_eligible"]:
            assert item["timestamp"] is None
            assert item["price"] is None

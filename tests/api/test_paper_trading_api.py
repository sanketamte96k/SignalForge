"""Tests for SignalForge Paper Trading API routes."""

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import paper_trading


client = TestClient(app)


def test_paper_trading_status_endpoint() -> None:
    """Paper Trading status should return a valid initial state."""

    paper_trading._runner = None
    paper_trading._replay_runner = None

    response = client.get(
        "/api/paper-trading/status"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["active"] is False
    assert payload["has_position"] is False
    assert payload["trade_count"] == 0
    assert payload["starting_capital"] == 100000.0
    assert payload["realized_pnl"] == 0.0
    assert payload["current_equity"] == 100000.0
    assert payload["total_transaction_cost"] == 0.0


def test_paper_trading_report_endpoint() -> None:
    """Paper Trading report should return an empty initial report."""

    paper_trading._runner = None
    paper_trading._replay_runner = None

    response = client.get(
        "/api/paper-trading/report"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["starting_capital"] == 100000.0
    assert payload["ending_equity"] == 100000.0
    assert payload["realized_pnl"] == 0.0
    assert payload["total_transaction_cost"] == 0.0
    assert payload["trade_count"] == 0
    assert payload["winning_trades"] == 0
    assert payload["losing_trades"] == 0
    assert payload["long_trades"] == 0
    assert payload["short_trades"] == 0


def test_paper_trading_trades_endpoint() -> None:
    """Initial Paper Trading trade history should be empty."""

    paper_trading._runner = None
    paper_trading._replay_runner = None

    response = client.get(
        "/api/paper-trading/trades"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_paper_trading_reset_endpoint() -> None:
    """Reset should return a clean Paper Trading state."""

    response = client.post(
        "/api/paper-trading/reset"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["active"] is False
    assert payload["has_position"] is False
    assert payload["trade_count"] == 0
    assert payload["starting_capital"] == 100000.0
    assert payload["realized_pnl"] == 0.0
    assert payload["current_equity"] == 100000.0
    assert payload["total_transaction_cost"] == 0.0


def test_paper_trading_start_endpoint() -> None:
    """Paper Trading replay should return a real report."""

    paper_trading._runner = None
    paper_trading._replay_runner = None

    response = client.post(
        "/api/paper-trading/start"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["starting_capital"] == 100000.0
    assert payload["ending_equity"] >= 0.0
    assert payload["trade_count"] >= 0
    assert payload["winning_trades"] >= 0
    assert payload["losing_trades"] >= 0
    assert payload["long_trades"] >= 0
    assert payload["short_trades"] >= 0
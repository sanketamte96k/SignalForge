"""Tests for the SignalForge stock-data import API."""

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import stocks


client = TestClient(app)


def make_csv(tmp_path: Path) -> Path:
    index = pd.date_range(
        "2024-01-01 09:15",
        periods=3,
        freq="min",
    )

    data = pd.DataFrame(
        {
            "timestamp": index,
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1100, 1200],
        }
    )

    path = tmp_path / "TESTSTOCK.csv"

    data.to_csv(
        path,
        index=False,
    )

    return path


def test_import_stock_data_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stocks._universe.add_instrument(
        symbol="TESTSTOCK",
        name="Test Stock",
        exchange="NSE",
        instrument_type="EQUITY",
    )

    source = make_csv(tmp_path)

    class FakeReadiness:
        symbol = "TESTSTOCK"
        available = True
        ready = False
        missing = False
        path = "data/historical/stocks/TESTSTOCK_1m.csv"
        total_rows = 3
        first_timestamp = pd.Timestamp(
            "2024-01-01 09:15"
        )
        last_timestamp = pd.Timestamp(
            "2024-01-01 09:17"
        )
        required_start = pd.Timestamp(
            "2015-01-01"
        )
        required_end = pd.Timestamp(
            "2024-03-26 15:29"
        )
        covers_required_period = False
        issues = (
            "dataset starts after required start",
            "dataset ends before required end",
        )

    class FakeService:
        def check_data_readiness(self, symbol):
            assert symbol == "TESTSTOCK"
            return FakeReadiness()

    monkeypatch.setattr(
        stocks,
        "_build_validation_service",
        lambda: FakeService(),
    )

    response = client.post(
        "/api/stocks/TESTSTOCK/import",
        files={
            "file": (
                source.name,
                source.read_bytes(),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "TESTSTOCK"
    assert body["filename"] == "TESTSTOCK.csv"
    assert body["imported"] is True
    assert body["total_rows"] == 3
    assert body["readiness"]["symbol"] == "TESTSTOCK"
    assert body["readiness"]["available"] is True
    assert body["readiness"]["ready"] is False


def test_import_stock_data_rejects_non_csv() -> None:
    response = client.post(
        "/api/stocks/TESTSTOCK/import",
        files={
            "file": (
                "data.txt",
                b"not csv",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_import_stock_data_rejects_empty_file() -> None:
    response = client.post(
        "/api/stocks/TESTSTOCK/import",
        files={
            "file": (
                "empty.csv",
                b"",
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_import_stock_data_rejects_unknown_stock(
    tmp_path: Path,
) -> None:
    source = make_csv(tmp_path)

    response = client.post(
        "/api/stocks/UNKNOWNTESTSTOCK/import",
        files={
            "file": (
                source.name,
                source.read_bytes(),
                "text/csv",
            )
        },
    )

    assert response.status_code == 404
    assert "Unknown stock symbol" in (
        response.json()["detail"]
    )

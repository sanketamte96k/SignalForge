from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import watchlists


client = TestClient(app)


def setup_function() -> None:
    watchlists._universe = watchlists.UniverseManager()


def test_list_watchlists_starts_empty() -> None:
    response = client.get("/api/watchlists")

    assert response.status_code == 200
    assert response.json() == {"watchlists": []}


def test_create_watchlist() -> None:
    response = client.post(
        "/api/watchlists",
        json={
            "name": "Momentum",
            "description": "Momentum candidates",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "name": "Momentum",
        "description": "Momentum candidates",
        "symbols": [],
    }


def test_get_watchlist() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    response = client.get(
        "/api/watchlists/Momentum",
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "Momentum",
        "description": "",
        "symbols": [],
    }


def test_add_stock_to_watchlist() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    response = client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )

    assert response.status_code == 200
    assert response.json()["symbols"] == ["TCS"]


def test_remove_stock_from_watchlist() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )

    response = client.delete(
        "/api/watchlists/Momentum/stocks/TCS",
    )

    assert response.status_code == 200
    assert response.json()["symbols"] == []


def test_get_watchlist_stocks() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )
    client.post(
        "/api/watchlists/Momentum/stocks/INFY",
    )

    response = client.get(
        "/api/watchlists/Momentum/stocks",
    )

    assert response.status_code == 200
    assert response.json() == ["TCS", "INFY"]


def test_watchlist_stock_search() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )
    client.post(
        "/api/watchlists/Momentum/stocks/INFY",
    )

    response = client.get(
        "/api/watchlists/Momentum/stocks?search=TCS",
    )

    assert response.status_code == 200
    assert response.json() == ["TCS"]


def test_duplicate_watchlist_returns_bad_request() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    response = client.post(
        "/api/watchlists",
        json={"name": "momentum"},
    )

    assert response.status_code == 400


def test_unknown_watchlist_returns_not_found() -> None:
    response = client.get(
        "/api/watchlists/Momentum",
    )

    assert response.status_code == 404


def test_unknown_stock_returns_not_found() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    response = client.post(
        "/api/watchlists/Momentum/stocks/NOT_A_STOCK",
    )

    assert response.status_code == 404


def test_delete_watchlist() -> None:
    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    response = client.delete(
        "/api/watchlists/Momentum",
    )

    assert response.status_code == 204

    response = client.get(
        "/api/watchlists/Momentum",
    )

    assert response.status_code == 404


def test_watchlist_and_sector_are_independent() -> None:
    from src.api.routes import sectors

    sectors._universe = sectors.UniverseManager()

    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )

    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    client.post(
        "/api/sectors/Technology/stocks/TCS",
    )

    client.delete(
        "/api/watchlists/Momentum",
    )

    response = client.get(
        "/api/sectors/Technology/stocks",
    )

    assert response.status_code == 200
    assert response.json() == ["TCS"]

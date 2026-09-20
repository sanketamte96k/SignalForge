from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import sectors


client = TestClient(app)


def setup_function() -> None:
    sectors._universe = sectors.UniverseManager()


def test_list_sectors_starts_empty() -> None:
    response = client.get("/api/sectors")

    assert response.status_code == 200
    assert response.json() == {"sectors": []}


def test_create_sector() -> None:
    response = client.post(
        "/api/sectors",
        json={
            "name": "Technology",
            "description": "Technology stocks",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "name": "Technology",
        "description": "Technology stocks",
        "symbols": [],
    }


def test_get_sector() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    response = client.get("/api/sectors/Technology")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Technology",
        "description": "",
        "symbols": [],
    }


def test_add_stock_to_sector() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    response = client.post(
        "/api/sectors/Technology/stocks/TCS",
    )

    assert response.status_code == 200
    assert response.json()["symbols"] == ["TCS"]


def test_remove_stock_from_sector() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    client.post(
        "/api/sectors/Technology/stocks/TCS",
    )

    response = client.delete(
        "/api/sectors/Technology/stocks/TCS",
    )

    assert response.status_code == 200
    assert response.json()["symbols"] == []


def test_get_sector_stocks() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    client.post(
        "/api/sectors/Technology/stocks/TCS",
    )
    client.post(
        "/api/sectors/Technology/stocks/INFY",
    )

    response = client.get(
        "/api/sectors/Technology/stocks",
    )

    assert response.status_code == 200
    assert response.json() == ["TCS", "INFY"]


def test_sector_stock_search() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    client.post(
        "/api/sectors/Technology/stocks/TCS",
    )
    client.post(
        "/api/sectors/Technology/stocks/INFY",
    )

    response = client.get(
        "/api/sectors/Technology/stocks?search=INF",
    )

    assert response.status_code == 200
    assert response.json() == ["INFY"]


def test_duplicate_sector_returns_bad_request() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    response = client.post(
        "/api/sectors",
        json={"name": "technology"},
    )

    assert response.status_code == 400


def test_unknown_sector_returns_not_found() -> None:
    response = client.get(
        "/api/sectors/Technology",
    )

    assert response.status_code == 404


def test_unknown_stock_returns_not_found() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    response = client.post(
        "/api/sectors/Technology/stocks/NOT_A_STOCK",
    )

    assert response.status_code == 404


def test_delete_sector() -> None:
    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    response = client.delete(
        "/api/sectors/Technology",
    )

    assert response.status_code == 204

    response = client.get(
        "/api/sectors/Technology",
    )

    assert response.status_code == 404


def test_sector_and_watchlist_are_independent() -> None:
    from src.api.routes import watchlists

    watchlists._universe = watchlists.UniverseManager()

    client.post(
        "/api/sectors",
        json={"name": "Technology"},
    )

    client.post(
        "/api/sectors/Technology/stocks/TCS",
    )

    client.post(
        "/api/watchlists",
        json={"name": "Momentum"},
    )

    client.post(
        "/api/watchlists/Momentum/stocks/TCS",
    )

    client.delete(
        "/api/sectors/Technology",
    )

    response = client.get(
        "/api/watchlists/Momentum/stocks",
    )

    assert response.status_code == 200
    assert response.json() == ["TCS"]

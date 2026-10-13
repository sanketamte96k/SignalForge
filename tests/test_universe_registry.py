import pytest
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from datetime import datetime

from src.universe.registry import StockUniverseRegistry, UniverseCategory, DataQualityStatus
from src.api.routes.universe import router
from fastapi import FastAPI

@pytest.fixture
def temp_storage():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()

@pytest.fixture
def registry(temp_storage):
    return StockUniverseRegistry(temp_storage)

def test_register_stock(registry):
    record = registry.register(
        symbol="RELIANCE", 
        exchange="NSE", 
        category=UniverseCategory.NIFTY_50,
        name="Reliance Industries"
    )
    
    assert record.symbol == "RELIANCE"
    assert record.exchange == "NSE"
    assert record.category == UniverseCategory.NIFTY_50
    assert record.name == "Reliance Industries"
    assert record.data_quality_status == DataQualityStatus.UNKNOWN

def test_prevent_duplicates(registry):
    registry.register("TCS", "NSE", UniverseCategory.NIFTY_50)
    
    with pytest.raises(ValueError, match="already registered"):
        registry.register("TCS", "NSE", UniverseCategory.CUSTOM)

def test_list_and_filter(registry):
    registry.register("INFY", "NSE", UniverseCategory.NIFTY_50)
    registry.register("ZOMATO", "NSE", UniverseCategory.CUSTOM)
    
    all_stocks = registry.list_all()
    assert len(all_stocks) == 2
    
    custom = registry.list_all(category=UniverseCategory.CUSTOM)
    assert len(custom) == 1
    assert custom[0].symbol == "ZOMATO"

def test_persistence(temp_storage):
    reg1 = StockUniverseRegistry(temp_storage)
    reg1.register("HDFC", "NSE", UniverseCategory.NIFTY_50)
    
    reg2 = StockUniverseRegistry(temp_storage)
    assert reg2.get("HDFC") is not None
    assert len(reg2.list_all()) == 1

# API Tests
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_api_add_stock(monkeypatch, temp_storage):
    # Mock the registry in the router
    test_registry = StockUniverseRegistry(temp_storage)
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", test_registry)
    
    response = client.post(
        "/api/universe/stocks",
        json={
            "symbol": "PAYTM",
            "exchange": "NSE",
            "category": "CUSTOM",
            "name": "One 97 Communications"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "PAYTM"
    assert data["category"] == "CUSTOM"

def test_api_get_stock(monkeypatch, temp_storage):
    test_registry = StockUniverseRegistry(temp_storage)
    test_registry.register("ITC", "NSE", UniverseCategory.NIFTY_50)
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", test_registry)
    
    response = client.get("/api/universe/stocks/ITC")
    assert response.status_code == 200
    assert response.json()["symbol"] == "ITC"

def test_api_stock_not_found(monkeypatch, temp_storage):
    test_registry = StockUniverseRegistry(temp_storage)
    import src.api.routes.universe as universe_routes
    monkeypatch.setattr(universe_routes, "_registry", test_registry)
    
    response = client.get("/api/universe/stocks/UNKNOWN")
    assert response.status_code == 404

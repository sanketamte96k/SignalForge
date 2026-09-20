"""Tests for the real NIFTY 50 chart API and RSI series."""

from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_nifty_chart_endpoint_returns_real_candles_and_rsi() -> None:
    """Chart endpoint should expose OHLCV candles and backend RSI(14)."""
    response = client.get(
        "/api/nifty/chart",
        params={"timeframe": "5m", "limit": 200},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "NIFTY 50"
    assert payload["timeframe"] == "5m"
    assert len(payload["candles"]) == 200

    candle = payload["candles"][-1]
    assert candle["timestamp"]
    assert isinstance(candle["open"], float)
    assert isinstance(candle["high"], float)
    assert isinstance(candle["low"], float)
    assert isinstance(candle["close"], float)
    assert isinstance(candle["volume"], float)
    assert isinstance(candle["rsi14"], float)
    assert 0.0 <= candle["rsi14"] <= 100.0


def test_nifty_chart_endpoint_supports_one_minute() -> None:
    """The chart API should also return raw 1-minute candles with RSI."""
    response = client.get(
        "/api/nifty/chart",
        params={"timeframe": "1m", "limit": 50},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["timeframe"] == "1m"
    assert len(payload["candles"]) == 50
    assert isinstance(payload["candles"][-1]["rsi14"], float)


def test_nifty_chart_endpoint_rejects_unsupported_timeframe() -> None:
    """Unsupported chart timeframes must not produce fabricated data."""
    response = client.get(
        "/api/nifty/chart",
        params={"timeframe": "1H", "limit": 50},
    )

    assert response.status_code == 400
    assert "Unsupported chart timeframe" in response.json()["detail"]

"""Tests for SignalForge NIFTY 50 API routes."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import nifty


client = TestClient(app)


def test_latest_nifty_endpoint() -> None:
    """Latest NIFTY endpoint should return validated OHLCV data."""

    response = client.get("/api/nifty/latest")

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "NIFTY 50"
    assert payload["timestamp"]
    assert isinstance(payload["open"], float)
    assert isinstance(payload["high"], float)
    assert isinstance(payload["low"], float)
    assert isinstance(payload["close"], float)
    assert isinstance(payload["volume"], float)


def test_nifty_signal_endpoint() -> None:
    """NIFTY signal endpoint should return a valid strategy state."""

    response = client.get("/api/nifty/signal")

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "NIFTY 50"
    assert payload["signal"] in {
        "BUY",
        "SELL",
        "NO_TRADE",
    }
    assert payload["position"] in {
        "LONG",
        "SHORT",
        None,
    }
    assert payload["timestamp"]
    assert isinstance(payload["price"], float)
    assert payload["strategy"] == "SignalForge"

    if payload["signal"] == "BUY":
        assert payload["position"] == "LONG"

    elif payload["signal"] == "SELL":
        assert payload["position"] == "SHORT"

    else:
        assert payload["position"] is None


def test_nifty_analysis_endpoint() -> None:
    """NIFTY analysis endpoint should return HTTP 200 with complete analysis."""

    response = client.get("/api/nifty/analysis")

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "NIFTY 50"
    assert payload["signal"] in {
        "BUY",
        "SELL",
        "NO_TRADE",
    }
    assert payload["position"] in {
        "LONG",
        "SHORT",
        None,
    }
    assert payload["timestamp"]
    assert isinstance(payload["price"], float)
    assert payload["strategy"] == "SignalForge"


def test_nifty_analysis_signal_parity() -> None:
    """
    /api/nifty/analysis.signal MUST equal /api/nifty/signal.signal.

    Both endpoints must share the same authoritative strategy source of truth.
    """

    signal_res = client.get("/api/nifty/signal")
    analysis_res = client.get("/api/nifty/analysis")

    assert signal_res.status_code == 200
    assert analysis_res.status_code == 200

    sig_payload = signal_res.json()
    ana_payload = analysis_res.json()

    assert ana_payload["symbol"] == sig_payload["symbol"]
    assert ana_payload["signal"] == sig_payload["signal"]
    assert ana_payload["position"] == sig_payload["position"]
    assert ana_payload["timestamp"] == sig_payload["timestamp"]
    assert ana_payload["price"] == sig_payload["price"]
    assert ana_payload["strategy"] == sig_payload["strategy"]


def test_nifty_analysis_structure_and_timeframes() -> None:
    """NIFTY analysis response must expose genuine analysis and MTF states."""

    response = client.get("/api/nifty/analysis")

    assert response.status_code == 200

    payload = response.json()

    # Analysis detail block
    analysis = payload["analysis"]
    assert isinstance(analysis["score"], int)
    assert analysis["score"] >= 0
    assert isinstance(analysis["confidence"], float)
    assert 0.0 <= analysis["confidence"] <= 100.0
    assert isinstance(analysis["timeframe_alignment"], int)
    assert 0 <= analysis["timeframe_alignment"] <= 4
    assert isinstance(analysis["reason"], str)
    assert len(analysis["reason"]) > 0

    # MTF timeframe states: exactly 5m, 10m, 15m, 30m (no invented 1H/4H/1D)
    timeframes = payload["timeframes"]
    assert set(timeframes.keys()) == {"5m", "10m", "15m", "30m"}

    for tf_name, tf_data in timeframes.items():
        assert tf_data["timeframe"] == tf_name
        assert isinstance(tf_data["ready"], bool)

        if tf_data["ready"]:
            assert tf_data["timestamp"] is not None
            assert isinstance(tf_data["close"], float)
            assert isinstance(tf_data["ema20"], float)
            assert isinstance(tf_data["ema50"], float)
            assert isinstance(tf_data["rsi14"], float)
            assert isinstance(tf_data["atr14"], float)
            assert tf_data["trend"] in {"LONG", "SHORT", "NO_TRADE"}


def test_nifty_analysis_rvol_unavailable_when_volume_zero() -> None:
    """RVOL must be null / unavailable when volume data is zero/unsupported."""

    response = client.get("/api/nifty/analysis")

    assert response.status_code == 200

    payload = response.json()

    # 1-minute base candle indicators: not computed by the strategy engine
    indicators = payload["indicators"]
    assert indicators["ema20"] is None
    assert indicators["ema50"] is None
    assert indicators["rsi14"] is None
    assert indicators["atr14"] is None
    assert indicators["rvol20"] is None

    # Timeframe RVOL: must remain None because source volume is 0
    for tf_data in payload["timeframes"].values():
        assert tf_data["rvol20"] is None


def test_nifty_analysis_error_on_empty_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty market data must produce an HTTP 503 rather than fake analysis."""

    nifty._load_nifty_data.cache_clear()
    monkeypatch.setattr(nifty, "load_market_data", lambda _path: pd.DataFrame())

    try:
        response = client.get("/api/nifty/analysis")
        assert response.status_code == 503
        assert "empty" in response.json()["detail"].lower()
    finally:
        nifty._load_nifty_data.cache_clear()


def test_nifty_analysis_error_on_data_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Data load failure must produce an HTTP 503 rather than fake analysis."""

    def mock_failure(_path: object) -> None:
        raise RuntimeError("Disk read error")

    nifty._load_nifty_data.cache_clear()
    monkeypatch.setattr(nifty, "load_market_data", mock_failure)

    try:
        response = client.get("/api/nifty/analysis")
        assert response.status_code == 503
        assert "unable to load" in response.json()["detail"].lower()
    finally:
        nifty._load_nifty_data.cache_clear()

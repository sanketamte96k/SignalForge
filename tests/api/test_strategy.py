"""Tests for Phase 16: Strategy Signal Contract and Endpoints."""

from datetime import datetime
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.models import StrategyConfirmation, StrategyIndicators, StrategySignalResponse
from src.api.routes import nifty, strategy
from src.signals.signal_engine import Signal, SignalResult
from src.strategy.causal_indicators import IndicatorSnapshot
from src.strategy.causal_timeframe_indicators import TimeframeIndicatorState
from src.strategy.context import CausalStrategyContext


client = TestClient(app)


def test_01_health_endpoint_passes() -> None:
    """1. Health endpoint still passes."""
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "SignalForge API"


def test_02_existing_nifty_chart_endpoint_passes() -> None:
    """2. Existing NIFTY chart endpoint still passes."""
    response = client.get("/api/nifty/chart?timeframe=15m&limit=50")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NIFTY 50"
    assert payload["timeframe"] == "15m"
    assert len(payload["candles"]) <= 50
    assert len(payload["candles"]) > 0

    candle = payload["candles"][0]
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    assert "rsi14" in candle


def test_03_strategy_endpoint_returns_valid_schema() -> None:
    """3. Strategy endpoint returns valid schema matching contract."""
    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    payload = response.json()

    # Minimum contract verification
    assert payload["symbol"] == "NIFTY 50"
    assert payload["timeframe"] == "15m"
    assert payload["timestamp"]
    assert payload["signal"] in {"BUY", "SELL", "NO_TRADE"}
    assert isinstance(payload["signal_reason"], str)
    assert payload["status"] in {"LIVE", "HISTORICAL", "UNAVAILABLE"}

    # Indicators structure
    indicators = payload["indicators"]
    assert "ema_fast" in indicators
    assert "ema_slow" in indicators
    assert "rsi" in indicators
    assert "atr" in indicators
    assert "volume" in indicators
    assert "vwap" in indicators

    # Confirmation structure
    confirmation = payload["confirmation"]
    assert "ema" in confirmation
    assert "rsi_momentum" in confirmation
    assert "volume" in confirmation
    assert "multi_timeframe" in confirmation


def test_04_buy_signal_schema_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """4. BUY signal schema validation: SL/targets, indicators, and confirmations."""
    sample_candle = pd.Series(
        {"open": 22000.0, "high": 22050.0, "low": 21990.0, "close": 22040.0, "volume": 1000.0},
        name=pd.Timestamp("2024-03-26 15:15:00"),
    )
    buy_sig_res = SignalResult(
        signal=Signal.BUY,
        score=12,
        confidence=85.0,
        timeframe_alignment=4,
        reason="4/4 timeframes aligned LONG. Momentum confirmed.",
    )
    tf_state = TimeframeIndicatorState(
        timeframe="15m",
        timestamp=pd.Timestamp("2024-03-26 15:15:00"),
        close=22040.0,
        indicators=IndicatorSnapshot(
            ema_fast=22010.0,
            ema_slow=21980.0,
            rsi=65.0,
            atr=25.0,
            rvol=2.0,
        ),
    )
    mock_engine_state = nifty.NiftyEngineState(
        candle=sample_candle,
        position="LONG",
        signal="BUY",
        signal_result=buy_sig_res,
        timeframe_states={"15m": tf_state, "5m": tf_state, "10m": tf_state, "30m": tf_state},
    )

    monkeypatch.setattr(nifty, "_process_recent_history", lambda _data: mock_engine_state)

    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    payload = response.json()

    assert payload["signal"] == "BUY"
    assert payload["confidence"] == 85.0
    assert payload["signal_reason"] == "4/4 timeframes aligned LONG. Momentum confirmed."
    assert payload["entry_price"] == 22040.0
    assert payload["stop_loss"] is not None
    assert payload["target_1"] is not None
    assert payload["target_2"] is not None

    # SL and Target relationship for BUY
    assert payload["stop_loss"] < payload["entry_price"]
    assert payload["entry_price"] < payload["target_1"]
    assert payload["target_1"] < payload["target_2"]

    # Confirmations
    assert payload["confirmation"]["ema"] is True
    assert payload["confirmation"]["rsi_momentum"] is True
    assert payload["confirmation"]["multi_timeframe"] is True


def test_05_sell_signal_schema_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """5. SELL signal schema validation: SL/targets, indicators, and confirmations."""
    sample_candle = pd.Series(
        {"open": 22000.0, "high": 22010.0, "low": 21950.0, "close": 21960.0, "volume": 1200.0},
        name=pd.Timestamp("2024-03-26 15:15:00"),
    )
    sell_sig_res = SignalResult(
        signal=Signal.SELL,
        score=12,
        confidence=80.0,
        timeframe_alignment=4,
        reason="4/4 timeframes aligned SHORT. Momentum confirmed.",
    )
    tf_state = TimeframeIndicatorState(
        timeframe="15m",
        timestamp=pd.Timestamp("2024-03-26 15:15:00"),
        close=21960.0,
        indicators=IndicatorSnapshot(
            ema_fast=21980.0,
            ema_slow=22010.0,
            rsi=38.0,
            atr=20.0,
            rvol=1.8,
        ),
    )
    mock_engine_state = nifty.NiftyEngineState(
        candle=sample_candle,
        position="SHORT",
        signal="SELL",
        signal_result=sell_sig_res,
        timeframe_states={"15m": tf_state, "5m": tf_state, "10m": tf_state, "30m": tf_state},
    )

    monkeypatch.setattr(nifty, "_process_recent_history", lambda _data: mock_engine_state)

    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    payload = response.json()

    assert payload["signal"] == "SELL"
    assert payload["confidence"] == 80.0
    assert payload["entry_price"] == 21960.0
    assert payload["stop_loss"] is not None
    assert payload["target_1"] is not None
    assert payload["target_2"] is not None

    # SL and Target relationship for SELL
    assert payload["target_2"] < payload["target_1"]
    assert payload["target_1"] < payload["entry_price"]
    assert payload["entry_price"] < payload["stop_loss"]

    # Confirmations
    assert payload["confirmation"]["ema"] is True
    assert payload["confirmation"]["rsi_momentum"] is True
    assert payload["confirmation"]["multi_timeframe"] is True


def test_06_no_trade_schema_validation() -> None:
    """6. NO_TRADE schema validation: no execution brackets fabricated."""
    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    payload = response.json()

    if payload["signal"] == "NO_TRADE":
        assert payload["entry_price"] is None
        assert payload["stop_loss"] is None
        assert payload["target_1"] is None
        assert payload["target_2"] is None
        assert payload["confirmation"]["multi_timeframe"] is False
        assert payload["position"] is None


def test_07_unsupported_timeframe_returns_correct_error() -> None:
    """7. Unsupported timeframe returns HTTP 400 with helpful error message."""
    # Test strategy endpoint
    res1 = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=1H")
    assert res1.status_code == 400
    assert "Unsupported strategy timeframe: '1H'" in res1.json()["detail"]
    assert "5m, 10m, 15m, 30m" in res1.json()["detail"]

    # Test nifty signal endpoint
    res2 = client.get("/api/nifty/signal?timeframe=4H")
    assert res2.status_code == 400
    assert "Unsupported strategy timeframe: '4H'" in res2.json()["detail"]

    res3 = client.get("/api/nifty/signal?timeframe=1D")
    assert res3.status_code == 400


def test_08_missing_data_returns_controlled_response() -> None:
    """8. Missing data returns controlled HTTP response instead of uncaught crash."""
    # Unknown symbol
    response = client.get("/api/strategy/signal?symbol=UNKNOWN_SYMBOL_999&timeframe=15m")
    assert response.status_code == 404
    assert "Historical data not available" in response.json()["detail"]

    # Malformed empty symbol
    res_empty = client.get("/api/strategy/signal?symbol=%20&timeframe=15m")
    assert res_empty.status_code == 400
    assert "Symbol cannot be empty" in res_empty.json()["detail"]


def test_09_indicator_values_are_numeric_or_null() -> None:
    """9. Indicator values are numeric/null as appropriate, no fabricated volume/vwap."""
    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    payload = response.json()

    ind = payload["indicators"]
    assert isinstance(ind["ema_fast"], (float, int))
    assert isinstance(ind["ema_slow"], (float, int))
    assert isinstance(ind["rsi"], (float, int))
    assert isinstance(ind["atr"], (float, int))
    assert ind["vwap"] is None

    # NIFTY 50 index has no traded volume in the dataset, so volume confirmation is null
    assert payload["confirmation"]["volume"] is None


def test_10_sl_target_relationship_when_trade_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """10. SL/target relationship is valid whenever a BUY or SELL trade exists."""
    sample_candle = pd.Series(
        {"open": 20000.0, "high": 20050.0, "low": 19950.0, "close": 20000.0, "volume": 100.0},
        name=pd.Timestamp("2024-03-26 15:15:00"),
    )
    tf_state = TimeframeIndicatorState(
        timeframe="5m",
        timestamp=pd.Timestamp("2024-03-26 15:15:00"),
        close=20000.0,
        indicators=IndicatorSnapshot(
            ema_fast=19980.0,
            ema_slow=19950.0,
            rsi=62.0,
            atr=30.0,
            rvol=1.8,
        ),
    )
    buy_state = nifty.NiftyEngineState(
        candle=sample_candle,
        position="LONG",
        signal="BUY",
        signal_result=SignalResult(Signal.BUY, 10, 80.0, 4, "BUY"),
        timeframe_states={"5m": tf_state},
    )

    monkeypatch.setattr(nifty, "_process_recent_history", lambda _data: buy_state)

    res = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=5m")
    assert res.status_code == 200
    data = res.json()

    entry = data["entry_price"]
    sl = data["stop_loss"]
    t1 = data["target_1"]
    t2 = data["target_2"]

    assert sl < entry < t1 < t2
    # Verify risk/reward ratio: T1 is 1.5R and T2 is 2.0R
    risk = entry - sl
    assert pytest.approx(t1 - entry, rel=1e-2) == risk * 1.5
    assert pytest.approx(t2 - entry, rel=1e-2) == risk * 2.0


def test_11_timestamp_is_valid() -> None:
    """11. Timestamp is valid ISO 8601 string."""
    response = client.get("/api/strategy/signal?symbol=NIFTY 50&timeframe=15m")
    assert response.status_code == 200
    ts_str = response.json()["timestamp"]

    parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    assert parsed.year >= 2024


def test_12_no_future_candle_is_used() -> None:
    """12. Strict causality: signal at candle T only uses data <= T."""
    raw_data = nifty._load_nifty_data()
    # Process up to T1
    slice_1 = raw_data.iloc[:500]
    t1 = slice_1.index[-1]
    res_1 = nifty._build_strategy_signal(slice_1, "NIFTY 50", "15m")

    # Assert timestamp matches strictly the last candle of slice
    assert res_1.timestamp == pd.Timestamp(t1).to_pydatetime()


def test_13_existing_endpoints_remain_backward_compatible() -> None:
    """13. Existing endpoints remain backward compatible."""
    # /api/nifty/signal without timeframe parameter
    res = client.get("/api/nifty/signal")
    assert res.status_code == 200
    payload = res.json()

    # All legacy fields present
    assert payload["symbol"] == "NIFTY 50"
    assert payload["signal"] in {"BUY", "SELL", "NO_TRADE"}
    assert payload["position"] in {"LONG", "SHORT", None}
    assert payload["timestamp"]
    assert isinstance(payload["price"], float)
    assert payload["strategy"] == "SignalForge"

    # All new contract fields also present
    assert payload["timeframe"] == "15m"
    assert "signal_reason" in payload
    assert "indicators" in payload
    assert "confirmation" in payload
    assert payload["status"] == "HISTORICAL"

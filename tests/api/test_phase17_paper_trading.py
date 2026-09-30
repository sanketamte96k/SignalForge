"""
Phase 17 Backend Test Suite: Paper Trading Engine & Signal Lifecycle.

Covers all 20 required scenarios:
1. Create valid LONG paper trade
2. Create valid SHORT paper trade
3. Reject NO_TRADE
4. Reject invalid LONG stop
5. Reject invalid SHORT stop
6. Reject duplicate active position
7. Update open trade
8. Stop-loss exit
9. Target exit
10. Manual close
11. Correct LONG P&L
12. Correct SHORT P&L
13. Unrealized P&L
14. Invalid state transition
15. Missing symbol
16. Invalid timeframe
17. Invalid quantity
18. Missing required prices
19. OHLC ambiguity handled deterministically (conservative stop-first)
20. No look-ahead behavior
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import paper_trading


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_service():
    """Ensure clean paper trading state before each test."""
    client.post("/api/paper-trading/reset")
    yield
    client.post("/api/paper-trading/reset")


# 1. Create valid LONG paper trade
def test_01_create_valid_long_paper_trade():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 2,
        "signal_price": 24000.0,
        "strategy_signal": "BUY",
    }
    response = client.post("/api/paper-trading/trades", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["trade_id"].startswith("tr_")
    assert data["symbol"] == "NIFTY 50"
    assert data["side"] == "LONG"
    assert data["timeframe"] == "15m"
    assert data["entry_price"] == 24000.0
    assert data["stop_loss"] == 23900.0
    assert data["target_1"] == 24150.0
    assert data["target_2"] == 24300.0
    assert data["quantity"] == 2
    assert data["status"] == "OPEN"
    assert data["realized_pnl"] == 0.0


# 2. Create valid SHORT paper trade
def test_02_create_valid_short_paper_trade():
    payload = {
        "symbol": "NIFTY 50",
        "side": "SHORT",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 24100.0,
        "target_1": 23850.0,
        "target_2": 23700.0,
        "quantity": 1,
        "signal_price": 24000.0,
        "strategy_signal": "SELL",
    }
    response = client.post("/api/paper-trading/trades", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["side"] == "SHORT"
    assert data["status"] == "OPEN"
    assert data["entry_price"] == 24000.0
    assert data["stop_loss"] == 24100.0


# 3. Reject NO_TRADE
def test_03_reject_no_trade():
    payload = {
        "symbol": "NIFTY 50",
        "side": "BUY",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "NO_TRADE",
    }
    response = client.post("/api/paper-trading/trades", json=payload)
    assert response.status_code == 400
    assert "NO_TRADE" in response.json()["detail"]


# 4. Reject invalid LONG stop (stop_loss >= entry_price)
def test_04_reject_invalid_long_stop():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 24050.0,  # Invalid: higher than entry
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    response = client.post("/api/paper-trading/trades", json=payload)
    assert response.status_code == 400
    assert "Invalid LONG stop loss" in response.json()["detail"]


# 5. Reject invalid SHORT stop (stop_loss <= entry_price)
def test_05_reject_invalid_short_stop():
    payload = {
        "symbol": "NIFTY 50",
        "side": "SHORT",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23950.0,  # Invalid: lower than entry
        "target_1": 23850.0,
        "target_2": 23700.0,
        "quantity": 1,
        "strategy_signal": "SELL",
    }
    response = client.post("/api/paper-trading/trades", json=payload)
    assert response.status_code == 400
    assert "Invalid SHORT stop loss" in response.json()["detail"]


# 6. Reject duplicate active position
def test_06_reject_duplicate_active_position():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    res1 = client.post("/api/paper-trading/trades", json=payload)
    assert res1.status_code == 201

    # Second trade on same symbol & timeframe while first is active
    res2 = client.post("/api/paper-trading/trades", json=payload)
    assert res2.status_code == 409
    assert "Duplicate active position" in res2.json()["detail"]


# 7. Update open trade
def test_07_update_open_trade():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    trade_res = client.post("/api/paper-trading/trades", json=payload).json()
    trade_id = trade_res["trade_id"]

    # Market price moves up without hitting target 1
    update_res = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"current_price": 24080.0},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["status"] == "OPEN"
    assert data["unrealized_pnl"] == 80.0
    assert data["realized_pnl"] == 0.0


# 8. Stop-loss exit
def test_08_stop_loss_exit():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 2,
        "strategy_signal": "BUY",
    }
    trade_res = client.post("/api/paper-trading/trades", json=payload).json()
    trade_id = trade_res["trade_id"]

    # Candle dips to 23880 (breaching 23900 SL)
    update_res = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"open": 23950.0, "high": 23960.0, "low": 23880.0, "close": 23890.0},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["status"] == "STOPPED_OUT"
    assert data["exit_price"] == 23900.0
    assert data["realized_pnl"] == (23900.0 - 24000.0) * 2  # -200.0
    assert data["unrealized_pnl"] == 0.0


# 9. Target exit
def test_09_target_exit():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 3,
        "strategy_signal": "BUY",
    }
    trade_res = client.post("/api/paper-trading/trades", json=payload).json()
    trade_id = trade_res["trade_id"]

    # Target 1 hit
    up1 = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"open": 24100.0, "high": 24200.0, "low": 24080.0, "close": 24180.0},
    ).json()
    assert up1["status"] == "TARGET_1_HIT"

    # Target 2 hit
    up2 = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"open": 24200.0, "high": 24320.0, "low": 24190.0, "close": 24310.0},
    ).json()
    assert up2["status"] == "TARGET_2_HIT"
    assert up2["exit_price"] == 24300.0
    assert up2["realized_pnl"] == (24300.0 - 24000.0) * 3  # 900.0


# 10. Manual close
def test_10_manual_close():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    trade_res = client.post("/api/paper-trading/trades", json=payload).json()
    trade_id = trade_res["trade_id"]

    close_res = client.post(
        f"/api/paper-trading/trades/{trade_id}/close",
        json={"exit_price": 24050.0, "reason": "DISCRETIONARY_EXIT"},
    )
    assert close_res.status_code == 200
    data = close_res.json()
    assert data["status"] == "CLOSED"
    assert data["exit_price"] == 24050.0
    assert data["realized_pnl"] == 50.0
    assert data["exit_reason"] == "DISCRETIONARY_EXIT"


# 11. Correct LONG P&L
def test_11_correct_long_pnl():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 5,
        "strategy_signal": "BUY",
    }
    trade_id = client.post("/api/paper-trading/trades", json=payload).json()["trade_id"]
    closed = client.post(
        f"/api/paper-trading/trades/{trade_id}/close",
        json={"exit_price": 24120.0},
    ).json()
    expected_pnl = (24120.0 - 24000.0) * 5
    assert closed["realized_pnl"] == expected_pnl  # 600.0


# 12. Correct SHORT P&L
def test_12_correct_short_pnl():
    payload = {
        "symbol": "NIFTY 50",
        "side": "SHORT",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 24100.0,
        "target_1": 23850.0,
        "target_2": 23700.0,
        "quantity": 4,
        "strategy_signal": "SELL",
    }
    trade_id = client.post("/api/paper-trading/trades", json=payload).json()["trade_id"]
    closed = client.post(
        f"/api/paper-trading/trades/{trade_id}/close",
        json={"exit_price": 23920.0},
    ).json()
    expected_pnl = (24000.0 - 23920.0) * 4
    assert closed["realized_pnl"] == expected_pnl  # 320.0


# 13. Unrealized P&L
def test_13_unrealized_pnl():
    payload = {
        "symbol": "NIFTY 50",
        "side": "SHORT",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 24100.0,
        "target_1": 23850.0,
        "target_2": 23700.0,
        "quantity": 2,
        "strategy_signal": "SELL",
    }
    trade_id = client.post("/api/paper-trading/trades", json=payload).json()["trade_id"]
    # Market price drops to 23950 (favorable for short)
    updated = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"current_price": 23950.0},
    ).json()
    assert updated["unrealized_pnl"] == (24000.0 - 23950.0) * 2  # 100.0


# 14. Invalid state transition
def test_14_invalid_state_transition():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    trade_id = client.post("/api/paper-trading/trades", json=payload).json()["trade_id"]
    client.post(
        f"/api/paper-trading/trades/{trade_id}/close",
        json={"exit_price": 24050.0},
    )

    # Attempting to close or update an already CLOSED trade must be rejected
    res = client.post(
        f"/api/paper-trading/trades/{trade_id}/close",
        json={"exit_price": 24060.0},
    )
    assert res.status_code == 400
    assert "already in terminal state" in res.json()["detail"]


# 15. Missing symbol
def test_15_missing_symbol():
    payload = {
        "symbol": "",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
    }
    res = client.post("/api/paper-trading/trades", json=payload)
    assert res.status_code == 400
    assert "symbol is required" in res.json()["detail"]


# 16. Invalid timeframe
def test_16_invalid_timeframe():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "1D",  # 1D is unsupported for strategy execution
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
    }
    res = client.post("/api/paper-trading/trades", json=payload)
    assert res.status_code == 400
    assert "Unsupported timeframe" in res.json()["detail"]


# 17. Invalid quantity
def test_17_invalid_quantity():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 0,  # Invalid
    }
    res = client.post("/api/paper-trading/trades", json=payload)
    assert res.status_code == 400
    assert "quantity must be an integer > 0" in res.json()["detail"]


# 18. Missing required prices (e.g. non-positive price)
def test_18_missing_required_prices():
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": -100.0,  # Negative
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
    }
    res = client.post("/api/paper-trading/trades", json=payload)
    assert res.status_code == 400
    assert "positive finite number" in res.json()["detail"]


# 19. OHLC ambiguity handled deterministically (conservative stop-first)
def test_19_ohlc_ambiguity_conservative_stop_first():
    """
    If a candle breaches BOTH Stop Loss and Target, the engine MUST NOT
    assume the favorable outcome; it must evaluate stop-loss first.
    """
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    trade_id = client.post("/api/paper-trading/trades", json=payload).json()["trade_id"]

    # Highly volatile bar: Low is 23850 (below SL) and High is 24350 (above T2)
    updated = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"open": 24000.0, "high": 24350.0, "low": 23850.0, "close": 24200.0},
    ).json()

    assert updated["status"] == "STOPPED_OUT"
    assert updated["exit_price"] == 23900.0
    assert updated["realized_pnl"] == -100.0
    assert "Conservative Resolution" in updated["exit_reason"]


# 20. No look-ahead behavior
def test_20_no_look_ahead_behavior():
    """
    Exit evaluations cannot use candles timestamped earlier than entry timestamp.
    """
    payload = {
        "symbol": "NIFTY 50",
        "side": "LONG",
        "timeframe": "15m",
        "entry_price": 24000.0,
        "stop_loss": 23900.0,
        "target_1": 24150.0,
        "target_2": 24300.0,
        "quantity": 1,
        "strategy_signal": "BUY",
    }
    trade_data = client.post("/api/paper-trading/trades", json=payload).json()
    trade_id = trade_data["trade_id"]
    entry_ts = datetime.fromisoformat(trade_data["entry_timestamp"])

    # Attempt to update with a timestamp 1 hour in the past (before entry)
    past_ts = (entry_ts - timedelta(hours=1)).isoformat()
    res = client.post(
        f"/api/paper-trading/trades/{trade_id}/update",
        json={"current_price": 24100.0, "timestamp": past_ts},
    )
    assert res.status_code == 400
    assert "Look-ahead violation" in res.json()["detail"]


# Additional test: Summary endpoint
def test_summary_metrics():
    # Trade 1: Win 100
    t1 = client.post(
        "/api/paper-trading/trades",
        json={
            "symbol": "NIFTY 50",
            "side": "LONG",
            "timeframe": "15m",
            "entry_price": 24000.0,
            "stop_loss": 23900.0,
            "target_1": 24100.0,
            "target_2": 24200.0,
            "quantity": 1,
        },
    ).json()["trade_id"]
    client.post(
        f"/api/paper-trading/trades/{t1}/close",
        json={"exit_price": 24100.0},
    )

    # Trade 2: Loss 50
    t2 = client.post(
        "/api/paper-trading/trades",
        json={
            "symbol": "NIFTY 50",
            "side": "SHORT",
            "timeframe": "15m",
            "entry_price": 24000.0,
            "stop_loss": 24100.0,
            "target_1": 23900.0,
            "target_2": 23800.0,
            "quantity": 1,
        },
    ).json()["trade_id"]
    client.post(
        f"/api/paper-trading/trades/{t2}/close",
        json={"exit_price": 24050.0},
    )

    # Trade 3: Open
    client.post(
        "/api/paper-trading/trades",
        json={
            "symbol": "NIFTY 50",
            "side": "LONG",
            "timeframe": "15m",
            "entry_price": 24000.0,
            "stop_loss": 23900.0,
            "target_1": 24100.0,
            "target_2": 24200.0,
            "quantity": 1,
        },
    )

    summary = client.get("/api/paper-trading/summary").json()
    assert summary["total_trades"] == 3
    assert summary["open_trades"] == 1
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["gross_pnl"] == 50.0
    assert summary["largest_win"] == 100.0
    assert summary["largest_loss"] == -50.0

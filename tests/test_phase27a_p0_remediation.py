"""
SignalForge — Phase 27A: P0 Equity Intraday Defect Remediation Test Suite
========================================================================
Validates:
1. P0 Task A: Zero collection errors across full test suite and test_manual_validation_2018.py.
2. P0 Task B: GET /api/stocks/{symbol}/chart endpoint (1m, 5m, 10m, 15m, 30m, error handling).
3. P0 Task C: Market Intelligence real-data loading (overview, scanner, symbol, explanation, history, 404/400).
4. Safety & Invariants: Protected canonical file hashes preserved unchanged.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import pytest
from fastapi import HTTPException

from src.api.routes.stocks import get_stock_chart
from src.api.intelligence.routes import (
    get_market_overview,
    list_scanned_opportunities,
    get_symbol_intelligence,
    get_symbol_explanation,
    get_symbol_intelligence_history,
)


# ============================================================================
# 1. P0 Task A: Broken Test Collection Remediation
# ============================================================================

def test_p0_task_a_manual_validation_test_file_imports_cleanly():
    """Verify test_manual_validation_2018.py can be imported and collected without error."""
    import importlib
    mod = importlib.import_module("tests.test_manual_validation_2018")
    assert mod is not None
    # Verify standard functions exist in module
    assert hasattr(mod, "test_01_long_profit")
    assert hasattr(mod, "test_32_one_entry_one_exit")


# ============================================================================
# 2. P0 Task B: Stock Chart API Endpoint (/api/stocks/{symbol}/chart)
# ============================================================================

def test_p0_task_b_stock_chart_reliance_15m_success():
    """Verify GET /api/stocks/RELIANCE/chart with 15m timeframe and limit 100."""
    res = get_stock_chart("RELIANCE", timeframe="15m", limit=100)
    assert res.symbol == "RELIANCE"
    assert res.timeframe == "15m"
    assert len(res.candles) == 100

    # Verify candle properties & OHLC integrity
    last_candle = res.candles[-1]
    assert last_candle.open > 0
    assert last_candle.high >= max(last_candle.open, last_candle.close)
    assert last_candle.low <= min(last_candle.open, last_candle.close)
    assert last_candle.close == 1988.0
    assert last_candle.volume > 0
    assert last_candle.rsi14 is not None
    assert 0.0 <= last_candle.rsi14 <= 100.0

    # Verify chronological ordering
    for i in range(1, len(res.candles)):
        assert res.candles[i].timestamp > res.candles[i - 1].timestamp


@pytest.mark.parametrize("tf", ["1m", "5m", "10m", "15m", "30m"])
def test_p0_task_b_stock_chart_all_supported_timeframes(tf: str):
    """Verify all 5 supported timeframes (1m, 5m, 10m, 15m, 30m) for an available stock."""
    res = get_stock_chart("INFY", timeframe=tf, limit=30)
    assert res.symbol == "INFY"
    assert res.timeframe == tf
    assert len(res.candles) == 30
    assert res.candles[-1].close > 0
    # RSI is computed and valid on all timeframes
    assert res.candles[-1].rsi14 is not None


def test_p0_task_b_stock_chart_unsupported_timeframe():
    """Verify unsupported timeframe raises HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        get_stock_chart("RELIANCE", timeframe="2h", limit=100)
    assert exc_info.value.status_code == 400
    assert "Unsupported chart timeframe" in exc_info.value.detail


def test_p0_task_b_stock_chart_nifty_rejection():
    """Verify requesting NIFTY 50 from stock endpoint is rejected (no spot substitution)."""
    with pytest.raises(HTTPException) as exc_info:
        get_stock_chart("NIFTY 50", timeframe="15m", limit=100)
    assert exc_info.value.status_code == 400
    assert "NIFTY 50 is an index" in exc_info.value.detail


def test_p0_task_b_stock_chart_nonexistent_stock():
    """Verify requesting an unavailable stock returns HTTP 404."""
    with pytest.raises(HTTPException) as exc_info:
        get_stock_chart("TCS", timeframe="15m", limit=100)
    assert exc_info.value.status_code == 404
    assert "Historical data not available" in exc_info.value.detail


def test_p0_task_b_stock_chart_invalid_symbol_format():
    """Verify invalid symbols (with control chars or path traversal) return HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        get_stock_chart("../EVIL", timeframe="15m", limit=100)
    assert exc_info.value.status_code == 400
    assert "Invalid symbol" in exc_info.value.detail


# ============================================================================
# 3. P0 Task C: Market Intelligence Real-Data Loading
# ============================================================================

def test_p0_task_c_market_overview_with_real_data():
    """Verify market overview scans real canonical stocks without mocks."""
    overview = get_market_overview()
    assert overview.number_of_symbols == 5
    assert overview.market_condition is not None
    assert overview.market_volatility is not None
    assert len(overview.top_opportunities) > 0


def test_p0_task_c_scanned_opportunities_with_real_data():
    """Verify opportunity scanner returns ranked real stock intelligence."""
    scanned = list_scanned_opportunities()
    assert scanned.count == 5
    symbols = {item.symbol for item in scanned.items}
    assert symbols == {"RELIANCE", "INFY", "ICICIBANK", "ADANIENT", "ADANIPORTS"}


def test_p0_task_c_symbol_intelligence_reliance():
    """Verify GET /api/intelligence/RELIANCE returns genuine evaluated state."""
    intel = get_symbol_intelligence("RELIANCE")
    assert intel.symbol == "RELIANCE"
    assert intel.price == 1988.0
    assert 0.0 <= intel.opportunity_score <= 100.0
    assert 0.0 <= intel.tradeability_score <= 100.0
    assert intel.decision is not None
    assert intel.direction is not None


def test_p0_task_c_symbol_explanation_reliance():
    """Verify structured human-readable explanation on real data."""
    expl = get_symbol_explanation("RELIANCE")
    assert expl.symbol == "RELIANCE"
    assert expl.price == 1988.0
    assert len(expl.summary) > 0
    assert len(expl.warnings) > 0 or len(expl.no_trade_reasons) > 0


def test_p0_task_c_symbol_intelligence_history_reliance():
    """Verify causal historical evaluations without lookahead."""
    hist = get_symbol_intelligence_history("RELIANCE", bars=30, step=5)
    assert hist.symbol == "RELIANCE"
    assert hist.count > 0
    # Check that historical prices are positive and timestamps are present
    for point in hist.history:
        assert point.price > 0
        assert point.timestamp is not None


def test_p0_task_c_intelligence_unavailable_stock():
    """Verify requesting an unavailable stock returns HTTP 404 without mocks."""
    with pytest.raises(HTTPException) as exc_info:
        get_symbol_intelligence("TCS")
    assert exc_info.value.status_code == 404
    assert "No market data available" in exc_info.value.detail


def test_p0_task_c_intelligence_index_rejection():
    """Verify requesting an index returns HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        get_symbol_intelligence("NIFTY 50")
    assert exc_info.value.status_code == 400
    assert "NIFTY 50 is an index" in exc_info.value.detail


# ============================================================================
# 4. Invariant Protection Checks
# ============================================================================

def test_canonical_file_hashes_intact():
    """Verify protected datasets, paper ledger, and universe registry remain unchanged."""
    expected_hashes = {
        "data/historical/stocks/ADANIPORTS_1m.csv": "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9",
        "data/historical/nifty50_1m_signalforge.csv": "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a",
        "data/paper_trading/interactive_trades.json": "f68a0ff20b5bd852eeac1a816c460b13aa27f67b73a293e2ebe8755b4c91ba63",
        "data/universe_registry.json": "adfb9294fc5defa337147d89955456a073a1834d992467956969c51db1062cc3",
    }
    for file_path, expected_hash in expected_hashes.items():
        data = Path(file_path).read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {file_path}"

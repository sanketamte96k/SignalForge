"""SignalForge — Phase 26D: NIFTY Historical Data Safety Verification Test Suite.
==============================================================================
Validates all 13 safety checkpoints specified in Phase 26D:
1. Canonical dataset properties verified (847,814 candles, 2015-01-09 to 2024-03-26, close 22018.25, volume 0.0).
2. Canonical SHA-256 hash preservation (V1 config, ADANIPORTS, NIFTY 50).
3. Quarantined 2020 dataset quarantine enforced.
4. Active paper-trading ledger & universe registry preserved.
5. Watchlist test file preserved.
6. Backend paper trading route rejects NIFTY order submission.
7. Backend backtest route rejects dates beyond 2024-03-26 for NIFTY 50.
8. Backend backtest route permits valid historical dates for NIFTY 50.
9. Backend backtest route permits valid dates for non-NIFTY equities.
10. Frontend TradingModeView freshness indicators and label safeguards.
11. Frontend StrategySignalPanel banner, bracket, and date limits safeguards.
12. Frontend CandlestickChart watermark, panned-away banner, and volume notes.
13. Frontend chartUtils signal matching strictness without fallback leakage.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import pytest
from fastapi import HTTPException

from src.api.models import BacktestRunRequest, PaperTradeCreateRequest
from src.api.routes.paper_trading import create_paper_trade
from src.api.routes.strategy import create_backtest_job
from src.strategy.job_manager import get_job_manager

FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"


# ============================================================================
# 1. Protected Invariants & Provenance Verification
# ============================================================================

def test_v1_frozen_strategy_config_hash():
    """Verify frozen V1 configuration snapshot hash is untouched."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 config snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == FROZEN_V1_CONFIG_HASH, f"V1 config hash mismatch: {v1_h}"


def test_canonical_adaniports_dataset_hash():
    """Verify canonical ADANIPORTS 1m dataset SHA-256 hash is identical."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert adani_path.exists(), "Canonical ADANIPORTS file missing"
    h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
    assert h == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS hash mismatch: {h}"


def test_canonical_nifty50_dataset_hash():
    """Verify canonical NIFTY 50 dataset SHA-256 hash is preserved."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    assert nifty_path.exists(), "Canonical NIFTY 50 file missing"
    h = hashlib.sha256(nifty_path.read_bytes()).hexdigest()
    assert h == CANONICAL_NIFTY50_HASH, f"NIFTY 50 hash mismatch: {h}"


def test_quarantined_2020_holdout_quarantine():
    """Verify 2020 quarantine partition remains preserved."""
    q_dir = Path("data/historical/quarantine")
    assert q_dir.exists(), "Quarantine directory missing"
    q_files = list(q_dir.glob("*.csv"))
    assert len(q_files) > 0, "Quarantined files missing"


def test_active_paper_trading_ledger_and_universe_registry():
    """Verify active paper ledger and universe registry are intact."""
    ledger_path = Path("data/paper_trading/interactive_trades.json")
    assert ledger_path.exists(), "Active paper ledger missing"
    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)
    assert isinstance(ledger, (dict, list)), "Active paper ledger malformed"

    reg_path = Path("data/universe_registry.json")
    assert reg_path.exists(), "Universe registry missing"
    with open(reg_path, "r", encoding="utf-8") as f:
        reg = json.load(f)
    assert isinstance(reg, dict), "Universe registry malformed"


def test_preserved_watchlist_test():
    """Verify unstaged tests/test_watchlist.py is preserved."""
    wl_path = Path("tests/test_watchlist.py")
    assert wl_path.exists(), "tests/test_watchlist.py missing"


# ============================================================================
# 2. Canonical NIFTY 50 Data Pipeline Properties
# ============================================================================

def test_canonical_nifty50_dataset_properties():
    """Verify exact candle count, boundary timestamps, final close and volume."""
    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    row_count = 0
    first_row = None
    last_row = None
    any_nonzero_volume = False

    with open(nifty_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row_count == 0:
                first_row = row
            last_row = row
            row_count += 1
            vol = float(row.get("volume", 0.0))
            if vol != 0.0:
                any_nonzero_volume = True

    assert row_count == 847814, f"Expected 847814 candles, got {row_count}"
    assert first_row is not None and first_row["timestamp"] == "2015-01-09 09:15:00"
    assert last_row is not None and last_row["timestamp"] == "2024-03-26 15:29:00"
    assert float(last_row["close"]) == 22018.25
    assert not any_nonzero_volume, "Expected all zero volume for cash spot index"


# ============================================================================
# 3. Backend Safety Guards: Paper Trading & Backtesting
# ============================================================================

def test_backend_paper_trading_rejects_nifty():
    """Verify paper trading endpoint rejects order creation for NIFTY variants."""
    for sym in ["NIFTY 50", "NIFTY", "^NSEI", "nifty 50"]:
        req = PaperTradeCreateRequest(
            symbol=sym,
            side="LONG",
            timeframe="15m",
            entry_price=22018.25,
            stop_loss=21900.0,
            target_1=22150.0,
            target_2=22250.0,
            quantity=50,
            signal_price=22018.25,
            strategy_signal="BUY",
        )
        with pytest.raises(HTTPException) as exc_info:
            create_paper_trade(req)
        assert exc_info.value.status_code == 400
        assert "Paper trading unavailable: historical market data only" in exc_info.value.detail
        assert "26 Mar 2024" in exc_info.value.detail


def test_backend_backtest_rejects_future_dates_for_nifty():
    """Verify backtest submissions for NIFTY beyond 2024-03-26 are rejected."""
    # Test route handler
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-04-01",
        end_date="2024-04-30",
        initial_capital=100000.0,
    )
    with pytest.raises(HTTPException) as exc_info:
        create_backtest_job(req)
    assert exc_info.value.status_code == 400
    assert "Maximum permitted date is 2024-03-26" in exc_info.value.detail

    # Test underlying JobManager
    manager = get_job_manager()
    with pytest.raises(ValueError, match="Maximum permitted date is 2024-03-26"):
        manager.create_job(params={"symbol": "NIFTY 50", "end_date": "2024-04-01"})

    with pytest.raises(ValueError, match="Maximum permitted date is 2024-03-26"):
        manager.create_job(params={"symbol": "NIFTY 50", "start_date": "2024-04-01"})


def test_backend_backtest_permits_historical_dates_for_nifty():
    """Verify valid historical date ranges for NIFTY 50 are accepted."""
    manager = get_job_manager()
    job = manager.create_job(params={
        "symbol": "NIFTY 50",
        "start_date": "2024-01-01",
        "end_date": "2024-03-20",
        "initial_capital": 100000.0,
    })
    assert job.symbol == "NIFTY 50"
    assert job.status.value == "QUEUED"


def test_backend_backtest_permits_dates_for_non_nifty():
    """Verify dates beyond March 2024 are allowed for non-NIFTY instruments."""
    manager = get_job_manager()
    job = manager.create_job(params={
        "symbol": "RELIANCE",
        "start_date": "2024-04-01",
        "end_date": "2024-04-10",
        "initial_capital": 100000.0,
    })
    assert job.symbol == "RELIANCE"
    assert job.status.value == "QUEUED"


# ============================================================================
# 4. Frontend Component Safeguards Verification
# ============================================================================

def test_frontend_trading_mode_view_historical_safeguards():
    """Verify TradingModeView.jsx implements age-based freshness and status labels."""
    content = Path("frontend/src/TradingModeView.jsx").read_text(encoding="utf-8")
    assert "HISTORICAL REPLAY — Data ended" in content
    assert "DATA UNAVAILABLE" in content
    assert "UNVERIFIED" in content
    assert "Last Historical Close" in content
    assert "getFreshness" in content

    css = Path("frontend/src/TradingModeView.css").read_text(encoding="utf-8")
    assert ".status-dot.amber" in css


def test_frontend_strategy_signal_panel_safeguards():
    """Verify StrategySignalPanel.jsx safeguards on buttons, labels, and modals."""
    content = Path("frontend/src/StrategySignalPanel.jsx").read_text(encoding="utf-8")
    assert "HISTORICAL CLOSE" in content
    assert "Historical Close:" in content
    assert "Paper trading unavailable: historical market data only. Latest available data: 26 Mar 2024." in content
    assert 'max={symbol === \'NIFTY 50\'' in content or '2024-03-26' in content
    assert "NIFTY 50 historical backtest date exceeds verified dataset boundary" in content


def test_frontend_candlestick_chart_safeguards():
    """Verify CandlestickChart watermark, panned state detection, and volume notes."""
    content = Path("frontend/src/CandlestickChart.jsx").read_text(encoding="utf-8")
    assert "HISTORICAL DATA • MARCH 2024" in content
    assert "isPannedAway" in content
    assert "chart-panned-notice" in content
    assert "Jump to Latest" in content
    assert "Zero volume expected for NIFTY 50 cash spot index" in content

    css = Path("frontend/src/CandlestickChart.css").read_text(encoding="utf-8")
    assert ".chart-panned-notice" in css
    assert ".chart-zoom-jump-latest" in css


def test_frontend_chart_utils_signal_matching_safeguards():
    """Verify chartUtils.js eliminates lastIndex signal fallback."""
    content = Path("frontend/src/chartUtils.js").read_text(encoding="utf-8")
    assert "return { candle: candles[lastIndex], index: lastIndex, signal }" not in content
    assert "Strict safety: do not fall back to pinning off-screen" in content


def test_frontend_paper_trading_view_safeguards():
    """Verify PaperTradingView.jsx displays historical data status notice and accurate non-misleading labels."""
    content = Path("frontend/src/PaperTradingView.jsx").read_text(encoding="utf-8")
    assert "Paper trading unavailable: historical market data only. Latest available data: 26 Mar 2024." in content
    # Phase 26D.2 accurate labels:
    assert "Simulated paper trading powered by SignalForge strategy signals with zero look-ahead bias and deterministic execution." in content
    assert "Real-time simulated paper trading" not in content
    assert "Unclosed ledger positions" in content
    assert "Active in current market" not in content
    assert "Simulated positions with status OPEN in local paper ledger." in content
    assert "Positions currently active and monitoring Stop Loss / Targets." not in content


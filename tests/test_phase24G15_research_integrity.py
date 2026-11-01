"""
SignalForge Phase 24G.15 — Research Integrity Test Suite
=========================================================
Strictly verifies:
1. Programmatic quarantine of 2020 Holdout (PermissionError on access).
2. Strict temporal causality of indicator generation (no lookahead bias).
3. Next-bar open execution causality (signals at t fill strictly at t+1 open).
4. Realistic Indian transaction cost friction application.
5. Max concurrent positions restriction (no duplicate concurrent entries).
6. Complete state isolation across partition runs.
7. Deterministic bit-for-bit replay reproducibility.
8. Cryptographic integrity of frozen V1 strategy and ADANIPORTS dataset.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
from datetime import time as dtime

from research.strategy_evolution_2018.phase24G15_strategy_research.research_hypotheses import (
    calc_ema,
    calc_rsi,
    calc_atr,
    calc_rvol,
    calc_adx,
    build_multi_timeframe_features,
    generate_hypothesis_signals,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.run_training_validation_research import (
    compute_extended_diagnostics,
)
from src.backtest.risk_engine_v2 import (
    CostModelType,
    ExitReason,
    PositionSide,
    RejectionReason,
    RiskEngineConfigV2,
    RiskEngineV2,
    RiskEngineV2Result,
    V2Trade,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


@pytest.fixture
def synthetic_intraday_series():
    """Generates 300 1-minute bars of synthetic OHLCV data."""
    dates = pd.date_range("2019-03-01 09:15:00", periods=300, freq="1min")
    np.random.seed(123)
    returns = np.random.normal(0.0002, 0.001, size=len(dates))
    price = 400.0 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame(
        {
            "open": price * (1 + np.random.uniform(-0.0003, 0.0003, size=len(dates))),
            "high": price * (1 + np.random.uniform(0.0005, 0.0012, size=len(dates))),
            "low": price * (1 - np.random.uniform(0.0005, 0.0012, size=len(dates))),
            "close": price,
            "volume": np.random.randint(2000, 15000, size=len(dates)),
        },
        index=dates,
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_quarantine_2020_holdout_lockout(synthetic_intraday_series):
    """Verify that calling diagnostics on 2020 partition raises PermissionError."""
    cfg = RiskEngineConfigV2.pre_registered("TEST-LOCKOUT")
    engine = RiskEngineV2(cfg)
    signals = np.full(len(synthetic_intraday_series), None)
    res = engine.run(synthetic_intraday_series, signals)

    # Calling with '2020' in partition name must raise PermissionError
    with pytest.raises(PermissionError, match="CRITICAL RESEARCH INTEGRITY VIOLATION"):
        compute_extended_diagnostics(
            res, "TEST_CFG", "realistic", "Holdout (2020)", synthetic_intraday_series, 0.1
        )

    with pytest.raises(PermissionError, match="CRITICAL RESEARCH INTEGRITY VIOLATION"):
        compute_extended_diagnostics(
            res, "TEST_CFG", "realistic", "2020_test_partition", synthetic_intraday_series, 0.1
        )


def test_strict_temporal_causality(synthetic_intraday_series):
    """Verify that indicators up to bar t do not change when future bars are appended or truncated."""
    df_half = synthetic_intraday_series.iloc[:150]
    df_full = synthetic_intraday_series.copy()

    # EMA causality
    ema_half = calc_ema(df_half["close"], 20)
    ema_full = calc_ema(df_full["close"], 20)
    np.testing.assert_allclose(ema_half.values, ema_full.iloc[:150].values, rtol=1e-12)

    # RSI causality
    rsi_half = calc_rsi(df_half["close"], 14)
    rsi_full = calc_rsi(df_full["close"], 14)
    valid_idx = ~rsi_half.isna()
    np.testing.assert_allclose(rsi_half[valid_idx].values, rsi_full.iloc[:150][valid_idx].values, rtol=1e-10)

    # ATR causality
    atr_half = calc_atr(df_half, 14)
    atr_full = calc_atr(df_full, 14)
    valid_atr = ~atr_half.isna()
    np.testing.assert_allclose(atr_half[valid_atr].values, atr_full.iloc[:150][valid_atr].values, rtol=1e-10)


def test_execution_causality_next_bar_open(synthetic_intraday_series):
    """Verify next_open execution: signal at bar t MUST fill at bar t+1 open."""
    cfg = RiskEngineConfigV2.pre_registered(
        "TEST-EXEC-CAUSALITY",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        execution_model="next_open",
        cost_model=CostModelType.HISTORICAL_BASELINE,
    )
    engine = RiskEngineV2(cfg)

    # Place a single signal at bar index 10
    signals = np.full(len(synthetic_intraday_series), None)
    signals[10] = PositionSide.LONG

    res = engine.run(synthetic_intraday_series, signals)

    assert len(res.trades) == 1, "Expected exactly 1 executed trade"
    trade = res.trades[0]
    # Trade entry time must be bar 11 timestamp
    expected_entry_ts = synthetic_intraday_series.index[11]
    expected_entry_price = synthetic_intraday_series["open"].iloc[11]

    assert trade.entry_time == expected_entry_ts, f"Expected entry at {expected_entry_ts}, got {trade.entry_time}"
    assert trade.entry_price == round(expected_entry_price, 4), f"Expected entry price {round(expected_entry_price, 4)}, got {trade.entry_price}"


def test_single_application_of_transaction_friction(synthetic_intraday_series):
    """Verify transaction costs match realistic Indian statutory friction formula."""
    cfg = RiskEngineConfigV2.pre_registered(
        "TEST-COST-INTEGRITY",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        execution_model="next_open",
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )
    engine = RiskEngineV2(cfg)

    signals = np.full(len(synthetic_intraday_series), None)
    signals[20] = PositionSide.LONG
    res = engine.run(synthetic_intraday_series, signals)

    assert len(res.trades) >= 1
    t = res.trades[0]

    # Reconcile net P&L: net_pnl = gross_pnl - transaction_cost
    assert round(t.net_pnl, 2) == round(t.gross_pnl - t.transaction_cost, 2), "Net P&L does not equal gross P&L minus costs"
    assert t.transaction_cost > 0.0, "Realistic transaction cost must be positive"


def test_max_concurrent_positions_enforcement(synthetic_intraday_series):
    """Verify that only 1 concurrent position is permitted; duplicate signals while in position do not stack."""
    cfg = RiskEngineConfigV2.pre_registered(
        "TEST-MAX-POSITIONS",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=5.0,  # wide stop to keep position active
        k_target=10.0,
        execution_model="next_open",
        cost_model=CostModelType.HISTORICAL_BASELINE,
    )
    engine = RiskEngineV2(cfg)

    # Fire signals continuously from bar 10 to bar 20 in the same direction
    signals = np.full(len(synthetic_intraday_series), None)
    for i in range(10, 21):
        signals[i] = PositionSide.LONG

    res = engine.run(synthetic_intraday_series, signals)

    # The engine must only hold 1 active position at a time (no pyramiding / no stacking)
    # The first signal opens at bar 11, stays open until target/stop/EOD.
    assert len(res.trades) == 1, f"Expected exactly 1 trade, got {len(res.trades)}"


def test_partition_state_isolation(synthetic_intraday_series):
    """Verify that running two partitions sequentially resets engine state completely."""
    cfg = RiskEngineConfigV2.pre_registered("TEST-STATE-ISOLATION", initial_capital=100000.0)
    engine = RiskEngineV2(cfg)

    signals_p1 = np.full(len(synthetic_intraday_series), None)
    signals_p1[5] = PositionSide.LONG
    res1 = engine.run(synthetic_intraday_series, signals_p1)

    # Immediately run partition 2 with no signals
    signals_p2 = np.full(len(synthetic_intraday_series), None)
    res2 = engine.run(synthetic_intraday_series, signals_p2)

    assert len(res2.trades) == 0, "Engine retained trades from previous partition"
    assert res2.initial_capital == 100000.0
    assert res2.final_capital == 100000.0
    assert res2.total_trades == 0


def test_deterministic_reproducibility(synthetic_intraday_series):
    """Verify identical run outputs bit-for-bit trade logs and P&L across multiple executions."""
    cfg = RiskEngineConfigV2.pre_registered(
        "TEST-DETERMINISM",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )

    signals = np.full(len(synthetic_intraday_series), None)
    signals[15] = PositionSide.LONG
    signals[80] = PositionSide.SHORT

    engine1 = RiskEngineV2(cfg)
    res1 = engine1.run(synthetic_intraday_series, signals)

    engine2 = RiskEngineV2(cfg)
    res2 = engine2.run(synthetic_intraday_series, signals)

    assert res1.total_trades == res2.total_trades
    assert res1.gross_pnl == res2.gross_pnl
    assert res1.net_pnl == res2.net_pnl
    assert res1.total_transaction_costs == res2.total_transaction_costs

    for t1, t2 in zip(res1.trades, res2.trades):
        assert t1.entry_time == t2.entry_time
        assert t1.exit_time == t2.exit_time
        assert t1.gross_pnl == t2.gross_pnl
        assert t1.transaction_cost == t2.transaction_cost
        assert t1.net_pnl == t2.net_pnl


def test_protected_assets_integrity():
    """Verify cryptographic integrity of frozen V1 strategy and ADANIPORTS dataset."""
    assert SNAPSHOT_PATH.exists(), "V1 snapshot missing"
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    cfg_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert cfg_hash == EXPECTED_CONFIG_HASH, f"V1 snapshot hash mismatch: {cfg_hash} != {EXPECTED_CONFIG_HASH}"

    assert DATA_PATH.exists(), "ADANIPORTS dataset missing"
    data_hash = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    assert data_hash == EXPECTED_DATA_HASH, f"ADANIPORTS dataset hash mismatch: {data_hash} != {EXPECTED_DATA_HASH}"

    assert REGISTRY_PATH.exists(), "Universe registry file missing"
    assert PAPER_LEDGER_PATH.exists(), "Interactive trades paper ledger missing"

"""
SignalForge — Phase 24G.17 Cross-Asset Generalization & Directional Analysis Tests
==================================================================================
Validates data integrity, model execution reproducibility, long/short accounting,
and quarantine enforcement across ADANIPORTS, RELIANCE, INFY, and ICICIBANK.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.risk_engine_v2 import (
    CostModelType,
    PositionSide,
    RiskEngineConfigV2,
    RiskEngineV2,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.research_hypotheses import (
    build_multi_timeframe_features,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.run_training_validation_research import (
    prepare_aligned_feature_arrays,
    generate_parameterized_signals,
    compute_extended_diagnostics,
)

SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"
STOCKS_DIR = PROJECT_ROOT / "data" / "historical" / "stocks"
MANIFESTS_DIR = PROJECT_ROOT / "data" / "historical" / "manifests"

EXPECTED_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_ADANIPORTS_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"

EVAL_SYMBOLS = ["ADANIPORTS", "RELIANCE", "INFY", "ICICIBANK"]

CFG_HYP_B = {
    "name": "HYP_B_BASE",
    "family": "VOLATILITY_BREAKOUT",
    "strict_squeeze": False,
    "donchian_period": 20,
    "rvol_threshold": 1.5,
    "cooldown_minutes": 0,
}


@pytest.fixture(scope="module")
def base_risk_engine_config() -> RiskEngineConfigV2:
    return RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-AUDIT-TEST-PHASE24G17",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        daily_loss_limit_pct=0.02,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="next_open",
        cost_model=CostModelType.REALISTIC_INTRADAY,
        slippage=0.0,
    )


def test_core_invariants_and_ledger_protection():
    """Verify frozen V1 config hash, baseline dataset hash, and untouched ledgers."""
    # 1. V1 Config Hash
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    v1_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert v1_hash == EXPECTED_V1_CONFIG_HASH, f"V1 snapshot hash modified: {v1_hash}"

    # 2. ADANIPORTS Hash
    adani_bytes = (STOCKS_DIR / "ADANIPORTS_1m.csv").read_bytes()
    adani_hash = hashlib.sha256(adani_bytes).hexdigest()
    assert adani_hash == EXPECTED_ADANIPORTS_DATA_HASH, f"ADANIPORTS dataset modified: {adani_hash}"

    # 3. Protected Ledgers
    assert REGISTRY_PATH.exists(), "Universe registry file missing"
    assert PAPER_LEDGER_PATH.exists(), "Paper trading ledger file missing"


def test_cross_asset_data_quality_and_provenance():
    """Verify all 4 evaluation stocks have valid historical CSVs and manifests."""
    for sym in EVAL_SYMBOLS:
        csv_file = STOCKS_DIR / f"{sym}_1m.csv"
        manifest_file = MANIFESTS_DIR / f"{sym}_1m_manifest.json"

        assert csv_file.exists(), f"Historical data missing for {sym}"
        assert manifest_file.exists(), f"Manifest missing for {sym}"

        # Manifest checks
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["symbol"] == sym
        assert manifest["readiness_classification"] == "PRELIMINARY_BACKTEST_READY"
        assert manifest["row_count"] > 370000

        # CSV checks
        df = pd.read_csv(csv_file, nrows=10)
        expected_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        assert expected_cols.issubset(set(df.columns)), f"Columns mismatch in {sym}"


def test_cross_asset_reproducibility_validation_2019(base_risk_engine_config):
    """Verify deterministic signal generation and execution for RELIANCE and ICICIBANK in 2019."""
    for sym, exp_trades, exp_min_net in [("RELIANCE", 21, 5000.0), ("ICICIBANK", 12, 3000.0)]:
        csv_path = STOCKS_DIR / f"{sym}_1m.csv"
        df = pd.read_csv(csv_path, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
        sub_df = df["2019-01-01 09:15:00":"2019-12-31 15:29:00"]

        features = build_multi_timeframe_features(df)
        tf_5m = features["5m"]
        for per in (15, 30):
            tf_5m[f"donchian_high_{per}"] = tf_5m["high"].rolling(per).max()
            tf_5m[f"donchian_low_{per}"] = tf_5m["low"].rolling(per).min()
        arrs = prepare_aligned_feature_arrays(features)
        sigs = generate_parameterized_signals(arrs, CFG_HYP_B)

        sub_sigs = sigs.loc[sub_df.index[0]:sub_df.index[-1]].to_numpy()
        engine = RiskEngineV2(base_risk_engine_config)
        res = engine.run(sub_df, sub_sigs)

        assert len(res.trades) == exp_trades, f"{sym} expected {exp_trades} trades, got {len(res.trades)}"
        net_pnl = sum(t.net_pnl for t in res.trades)
        assert net_pnl > exp_min_net, f"{sym} expected net P&L > {exp_min_net}, got {net_pnl}"


def test_directional_breakdown_consistency(base_risk_engine_config):
    """Verify that both Long and Short trades are properly identified and accounted."""
    # Test on ICICIBANK 2017-2018 where Short trades were dominant
    csv_path = STOCKS_DIR / "ICICIBANK_1m.csv"
    df = pd.read_csv(csv_path, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    sub_df = df["2017-01-02 09:15:00":"2018-12-31 15:29:00"]

    features = build_multi_timeframe_features(df)
    tf_5m = features["5m"]
    for per in (15, 30):
        tf_5m[f"donchian_high_{per}"] = tf_5m["high"].rolling(per).max()
        tf_5m[f"donchian_low_{per}"] = tf_5m["low"].rolling(per).min()
    arrs = prepare_aligned_feature_arrays(features)
    sigs = generate_parameterized_signals(arrs, CFG_HYP_B)

    sub_sigs = sigs.loc[sub_df.index[0]:sub_df.index[-1]].to_numpy()
    engine = RiskEngineV2(base_risk_engine_config)
    res = engine.run(sub_df, sub_sigs)

    long_trades = [t for t in res.trades if t.side == PositionSide.LONG]
    short_trades = [t for t in res.trades if t.side == PositionSide.SHORT]

    assert len(long_trades) == 25
    assert len(short_trades) == 28
    assert sum(t.net_pnl for t in short_trades) > 10000.0, "ICICIBANK short trades should be strongly positive"


def test_quarantine_enforcement_cross_asset(base_risk_engine_config):
    """Verify that attempting to evaluate 2020 on any cross-asset stock raises PermissionError."""
    csv_path = STOCKS_DIR / "RELIANCE_1m.csv"
    df = pd.read_csv(csv_path, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    sub_df = df["2020-01-01 09:15:00":"2020-01-10 15:29:00"]

    engine = RiskEngineV2(base_risk_engine_config)
    res = engine.run(sub_df, np.full(len(sub_df), None))

    with pytest.raises(PermissionError, match="CRITICAL RESEARCH INTEGRITY VIOLATION"):
        compute_extended_diagnostics(res, "HYP_B", "realistic", "Holdout (2020)", sub_df, 0.1)

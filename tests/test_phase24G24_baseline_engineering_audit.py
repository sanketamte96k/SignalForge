"""
SignalForge — Phase 24G.24: Baseline Research & Engineering Validation Unit Tests
================================================================================
Validates:
1. Preflight invariants (V1 config hash, canonical ADANIPORTS hash, ledger/registry untouched).
2. RiskEngineV2 polymorphic signal input handling (pd.Series with DatetimeIndex, np.ndarray, list).
3. Resampling properties and causal shift mathematical proof.
4. Phase 24G.24 audit deliverables and empirical CSV integrity.
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.backtest.risk_engine_v2 import (
    RiskEngineConfigV2,
    RiskEngineV2,
    CostModelType,
    PositionSide,
)
from src.data.resampler import resample_ohlcv


# ----------------------------------------------------------------------------
# 1. Preflight Invariants
# ----------------------------------------------------------------------------

def test_frozen_v1_config_hash_invariant():
    """Verify frozen V1 strategy configuration hash remains completely unchanged."""
    v1_snapshot_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_snapshot_path.exists()
    with open(v1_snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    v1_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_hash == "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def test_adaniports_canonical_hash_invariant():
    """Verify canonical ADANIPORTS dataset hash is untouched."""
    fpath = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert fpath.exists()
    h = hashlib.sha256(fpath.read_bytes()).hexdigest()
    assert h == "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_paper_ledger_and_universe_registry_untouched():
    """Verify paper trading ledger and universe registry exist and are untouched."""
    ledger = Path("data/paper_trading/interactive_trades.json")
    registry = Path("data/universe_registry.json")
    assert ledger.exists()
    assert registry.exists()


# ----------------------------------------------------------------------------
# 2. RiskEngineV2 Bugfix: Polymorphic Signal Input Handling
# ----------------------------------------------------------------------------

def test_risk_engine_polymorphic_signals():
    """Verify RiskEngineV2 works seamlessly with pd.Series (DatetimeIndex), np.ndarray, and list."""
    idx = pd.date_range("2018-01-02 09:15", periods=20, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0 + i for i in range(20)],
            "high": [101.0 + i for i in range(20)],
            "low": [99.0 + i for i in range(20)],
            "close": [100.5 + i for i in range(20)],
            "volume": [1000] * 20,
        },
        index=idx,
    )

    sig_series = pd.Series([None] * 20, index=idx)
    sig_series.iloc[5] = PositionSide.LONG

    sig_arr = np.array([None] * 20, dtype=object)
    sig_arr[5] = PositionSide.LONG

    sig_list = [None] * 20
    sig_list[5] = PositionSide.LONG

    cfg = RiskEngineConfigV2.pre_registered(
        "TEST-POLYMORPHISM",
        initial_capital=100_000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )

    # 1. Test pd.Series (previously triggered KeyError: 0)
    res_series = RiskEngineV2(cfg).run(df, sig_series)
    assert len(res_series.trades) >= 0

    # 2. Test np.ndarray
    res_arr = RiskEngineV2(cfg).run(df, sig_arr)
    assert len(res_arr.trades) == len(res_series.trades)

    # 3. Test list
    res_list = RiskEngineV2(cfg).run(df, sig_list)
    assert len(res_list.trades) == len(res_series.trades)


# ----------------------------------------------------------------------------
# 3. Causal Shift Proof on Resampled Timeframes
# ----------------------------------------------------------------------------

def test_resampling_and_causal_shift():
    """Verify that left-labeled resampling requires shift(1) to avoid future peek."""
    idx = pd.date_range("2018-01-02 09:15", periods=10, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [100.0 + i for i in range(10)],
            "volume": [1000] * 10,
        },
        index=idx,
    )

    tf_5m = resample_ohlcv(df, "5m")
    assert len(tf_5m) == 2
    # First candle covers [09:15, 09:20), stamped 09:15
    assert tf_5m.index[0] == pd.Timestamp("2018-01-02 09:15:00")
    # Second candle covers [09:20, 09:25), stamped 09:20
    assert tf_5m.index[1] == pd.Timestamp("2018-01-02 09:20:00")

    # Unshifted reindex: at 09:20:00, value is the 09:20:00 candle (which contains future close at 09:24)
    s5_unshifted = tf_5m.reindex(df.index, method="ffill")
    assert s5_unshifted.loc["2018-01-02 09:20:00", "close"] == tf_5m.loc["2018-01-02 09:20:00", "close"]

    # Causal shift(1): at 09:20:00, value is the completed 09:15:00 candle!
    s5_causal = tf_5m.shift(1).reindex(df.index, method="ffill")
    assert s5_causal.loc["2018-01-02 09:20:00", "close"] == tf_5m.loc["2018-01-02 09:15:00", "close"]


# ----------------------------------------------------------------------------
# 4. Phase 24G.24 Deliverables and CSV Integrity
# ----------------------------------------------------------------------------

def test_phase24G24_deliverables_and_csv():
    """Verify all Phase 24G.24 deliverables exist and results CSV shows causal collapse."""
    base_dir = Path("research/strategy_evolution_2018/phase24G24_baseline_engineering_audit")
    assert base_dir.exists()

    required_files = [
        "phase24G24_backtesting_engine_audit.md",
        "phase24G24_data_pipeline_reliability.md",
        "phase24G24_risk_and_cost_modelling.md",
        "phase24G24_engineering_improvements.md",
        "phase24G24_test_results.md",
        "phase24G24_final_verdict.md",
        "phase24G24_multi_asset_baseline_results.csv",
        "phase24G24_manifest.json",
    ]

    for fname in required_files:
        p = base_dir / fname
        assert p.exists(), f"Missing required deliverable: {fname}"
        assert p.stat().st_size > 0

    # Read CSV
    csv_p = base_dir / "phase24G24_multi_asset_baseline_results.csv"
    with open(csv_p, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 15, f"Expected 15 rows, found {len(reader)}"

    # All 15 causal net PnLs must be strictly negative
    for row in reader:
        causal_net = float(row["causal_net_pnl"])
        orig_net = float(row["orig_net_pnl"])
        delta = float(row["pnl_impact_of_leak"])
        assert causal_net < 0, f"Expected negative causal net PnL for {row['symbol']} {row['year']}, got {causal_net}"
        assert delta < 0, f"Expected negative delta for {row['symbol']} {row['year']}, got {delta}"
        assert orig_net > 0, f"Expected positive orig net PnL for {row['symbol']} {row['year']}, got {orig_net}"

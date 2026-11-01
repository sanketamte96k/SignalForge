"""
SignalForge Phase 24G.16 — Independent Hypothesis B Audit Test Suite
====================================================================
Strictly verifies:
1. Exact mathematical reproduction of Hypothesis B on Training and Validation.
2. Transaction cost reconciliation (true friction vs narrative artifact).
3. Profit concentration and winner exclusion mechanics.
4. Exact binomial statistical test properties.
5. Cryptographic preservation of frozen V1 baseline and ADANIPORTS dataset.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.backtest.risk_engine_v2 import (
    CostModelType,
    ExitReason,
    PositionSide,
    RiskEngineConfigV2,
    RiskEngineV2,
    calculate_transaction_costs,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.research_hypotheses import (
    build_multi_timeframe_features,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.run_training_validation_research import (
    prepare_aligned_feature_arrays,
    generate_parameterized_signals,
    compute_extended_diagnostics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


@pytest.fixture(scope="module")
def loaded_dataset_and_features():
    """Load historical data and build features once for test module."""
    df_raw = pd.read_csv(DATA_PATH, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    features = build_multi_timeframe_features(df_raw)
    tf_5m = features["5m"]
    for p in (15, 30):
        tf_5m[f"donchian_high_{p}"] = tf_5m["high"].rolling(p).max()
        tf_5m[f"donchian_low_{p}"] = tf_5m["low"].rolling(p).min()
    arrs = prepare_aligned_feature_arrays(features)

    cfg_hyp_b = {
        "name": "HYP_B_BASE",
        "family": "VOLATILITY_BREAKOUT",
        "strict_squeeze": False,
        "donchian_period": 20,
        "rvol_threshold": 1.5,
        "cooldown_minutes": 0,
    }
    signals = generate_parameterized_signals(arrs, cfg_hyp_b)
    return df_raw, signals


def test_hypothesis_b_exact_reproduction(loaded_dataset_and_features):
    """Verify bit-for-bit reproduction of trade counts, gross P&L, costs, and net P&L."""
    df_raw, signals = loaded_dataset_and_features

    cfg_engine = RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-AUDIT-TEST",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        execution_model="next_open",
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )

    # 1. Training (2017–2018)
    slice_train = df_raw["2017-01-02 09:15:00":"2018-12-31 15:29:00"]
    sigs_train = signals.loc[slice_train.index[0]:slice_train.index[-1]].to_numpy()
    engine_train = RiskEngineV2(cfg_engine)
    res_train = engine_train.run(slice_train, sigs_train)

    assert len(res_train.trades) == 67, f"Expected 67 training trades, got {len(res_train.trades)}"
    assert round(res_train.gross_pnl, 2) == 41081.85, f"Training gross P&L mismatch: {res_train.gross_pnl}"
    assert round(res_train.total_transaction_costs, 2) == 29255.82, f"Training costs mismatch: {res_train.total_transaction_costs}"
    assert round(res_train.net_pnl, 2) == 11826.03, f"Training net P&L mismatch: {res_train.net_pnl}"
    assert round(res_train.win_rate_pct, 2) == 73.13, f"Training win rate mismatch: {res_train.win_rate_pct}"
    assert round(res_train.profit_factor, 4) == 1.5756, f"Training profit factor mismatch: {res_train.profit_factor}"

    # 2. Validation (2019)
    slice_val = df_raw["2019-01-01 09:15:00":"2019-12-31 15:29:00"]
    sigs_val = signals.loc[slice_val.index[0]:slice_val.index[-1]].to_numpy()
    engine_val = RiskEngineV2(cfg_engine)
    res_val = engine_val.run(slice_val, sigs_val)

    assert len(res_val.trades) == 14, f"Expected 14 validation trades, got {len(res_val.trades)}"
    assert round(res_val.gross_pnl, 2) == 8019.20, f"Validation gross P&L mismatch: {res_val.gross_pnl}"
    assert round(res_val.total_transaction_costs, 2) == 5885.95, f"Validation costs mismatch: {res_val.total_transaction_costs}"
    assert round(res_val.net_pnl, 2) == 2133.25, f"Validation net P&L mismatch: {res_val.net_pnl}"
    assert round(res_val.win_rate_pct, 2) == 71.43, f"Validation win rate mismatch: {res_val.win_rate_pct}"
    assert round(res_val.profit_factor, 4) == 1.4901, f"Validation profit factor mismatch: {res_val.profit_factor}"


def test_transaction_cost_reconciliation(loaded_dataset_and_features):
    """Verify transaction cost components, side-specific rules, and reconcile the Rs 850 discrepancy."""
    df_raw, signals = loaded_dataset_and_features
    slice_val = df_raw["2019-01-01 09:15:00":"2019-12-31 15:29:00"]
    sigs_val = signals.loc[slice_val.index[0]:slice_val.index[-1]].to_numpy()

    cfg_engine = RiskEngineConfigV2.pre_registered(
        "TEST-COST-REC",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        cost_model=CostModelType.REALISTIC_INTRADAY,
    )
    res_val = RiskEngineV2(cfg_engine).run(slice_val, sigs_val)

    trades = res_val.trades
    assert len(trades) == 14

    tot_turnover = sum(t.cost_breakdown.turnover for t in trades)
    tot_costs = sum(t.cost_breakdown.total_costs for t in trades)
    tot_stt = sum(t.cost_breakdown.stt for t in trades)
    tot_stamp = sum(t.cost_breakdown.stamp_duty for t in trades)
    tot_slippage = sum(t.cost_breakdown.slippage for t in trades)

    # 1. Total costs must match Rs 5,885.95, NOT the narrative Rs 850
    assert round(tot_costs, 2) == 5885.95
    assert tot_costs > 5000.0, "True costs on 14 trades with 5x leverage must exceed Rs 5,000"

    # 2. Total turnover exceeds Rs 1.35 Crore due to 5x leverage
    assert tot_turnover > 13000000.0, f"Expected > Rs 1.3 Crore turnover, got {tot_turnover}"

    # 3. Verify side-specific statutory tax calculations
    for t in trades:
        cb = t.cost_breakdown
        entry_to = t.entry_price * t.quantity
        exit_to = t.exit_price * t.quantity
        sell_to = exit_to if t.side == PositionSide.LONG else entry_to
        buy_to = entry_to if t.side == PositionSide.LONG else exit_to

        # STT = 0.025% on sell side only
        expected_stt = round(sell_to * 0.00025, 4)
        assert abs(cb.stt - expected_stt) < 1e-2

        # Stamp duty = 0.003% on buy side only
        expected_stamp = round(buy_to * 0.00003, 4)
        assert abs(cb.stamp_duty - expected_stamp) < 1e-2


def test_winner_exclusion_stress_test(loaded_dataset_and_features):
    """Verify profit concentration fragility in Validation vs robustness in Training."""
    df_raw, signals = loaded_dataset_and_features
    cfg_engine = RiskEngineConfigV2.pre_registered("TEST-EXCLUSION", cost_model=CostModelType.REALISTIC_INTRADAY)

    # Validation
    slice_val = df_raw["2019-01-01 09:15:00":"2019-12-31 15:29:00"]
    res_val = RiskEngineV2(cfg_engine).run(slice_val, signals.loc[slice_val.index[0]:slice_val.index[-1]].to_numpy())
    df_val_t = pd.DataFrame([{"net_pnl": t.net_pnl} for t in res_val.trades])
    wins_val = df_val_t[df_val_t["net_pnl"] > 0].sort_values("net_pnl", ascending=False)

    # Excluding Top 3 winners flips Validation negative
    ex3_val = df_val_t.drop(wins_val.index[:3])
    ex3_val_net = ex3_val["net_pnl"].sum()
    assert round(ex3_val_net, 2) == -979.05, f"Expected -979.05, got {ex3_val_net}"
    assert ex3_val_net < 0.0, "Validation MUST turn negative when top 3 winners are excluded"

    # Training
    slice_tr = df_raw["2017-01-02 09:15:00":"2018-12-31 15:29:00"]
    res_tr = RiskEngineV2(cfg_engine).run(slice_tr, signals.loc[slice_tr.index[0]:slice_tr.index[-1]].to_numpy())
    df_tr_t = pd.DataFrame([{"net_pnl": t.net_pnl} for t in res_tr.trades])
    wins_tr = df_tr_t[df_tr_t["net_pnl"] > 0].sort_values("net_pnl", ascending=False)

    # Excluding Top 3 winners preserves Training profitability
    ex3_tr = df_tr_t.drop(wins_tr.index[:3])
    ex3_tr_net = ex3_tr["net_pnl"].sum()
    assert round(ex3_tr_net, 2) == 6809.04, f"Expected 6809.04, got {ex3_tr_net}"
    assert ex3_tr_net > 0.0, "Training MUST remain net positive when top 3 winners are excluded"


def test_statistical_binomial_tests():
    """Verify exact binomial test p-values: Validation fails alpha=0.05, Training passes."""
    def binom_p_val(k, n, p=0.5):
        return sum(math.comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(k, n+1))

    # Validation: 10 wins out of 14 trades
    p_val_14 = binom_p_val(10, 14, 0.5)
    assert round(p_val_14, 4) == 0.0898
    assert p_val_14 > 0.05, "Validation win rate is NOT statistically significant at alpha=0.05"

    # Training: 49 wins out of 67 trades
    p_train_67 = binom_p_val(49, 67, 0.5)
    assert p_train_67 < 0.001, "Training win rate is statistically significant at p < 0.001"


def test_protected_assets_and_quarantine_integrity(loaded_dataset_and_features):
    """Verify cryptographic integrity of baseline assets and 2020 quarantine guard."""
    df_raw, signals = loaded_dataset_and_features

    # V1 snapshot hash
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    cfg_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert cfg_hash == EXPECTED_CONFIG_HASH

    # ADANIPORTS dataset hash
    data_hash = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    assert data_hash == EXPECTED_DATA_HASH

    assert REGISTRY_PATH.exists()
    assert PAPER_LEDGER_PATH.exists()

    # Quarantine lockout
    cfg_engine = RiskEngineConfigV2.pre_registered("TEST-LOCKOUT")
    res = RiskEngineV2(cfg_engine).run(df_raw.iloc[:50], np.full(50, None))
    with pytest.raises(PermissionError, match="CRITICAL RESEARCH INTEGRITY VIOLATION"):
        compute_extended_diagnostics(res, "HYP_B", "realistic", "Holdout (2020)", df_raw.iloc[:50], 0.1)

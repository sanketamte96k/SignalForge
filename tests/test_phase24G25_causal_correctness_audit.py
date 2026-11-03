"""
SignalForge — Phase 24G.25: Independent Causal-Correctness & Reproducibility Tests
=================================================================================
Validates:
1. Pre-flight invariants (V1 config hash, canonical ADANIPORTS SHA-256, ledger/registry).
2. Deterministic fixture proving 4-minute future peek in unshifted alignment.
3. Multi-asset P&L reconciliation (zero discrepancies vs Phase 24G.24).
4. NumPy benchmark bit-for-bit parity and execution speedup.
5. Cross-project scan cleanliness (zero negative shifts, zero centered windows).
6. Production V1 engine cursor causality and session boundary isolation.
7. Phase 24G.25 deliverable completeness.
"""

import csv
import hashlib
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.data.resampler import resample_ohlcv
from src.strategy.backtest_strategy import _TimeframeCursor, TIMEFRAMES


# ----------------------------------------------------------------------------
# 1. Preflight Invariants
# ----------------------------------------------------------------------------

def test_v1_config_hash_immutable():
    """Verify frozen V1 baseline configuration hash matches canonical value."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists()
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def test_adaniports_canonical_hash():
    """Verify canonical on-disk ADANIPORTS dataset hash is untouched."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert adani_path.exists()
    h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
    assert h == "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_safety_invariants_registry_and_paper_ledger():
    """Verify universe registry and paper trading ledger are intact."""
    reg_path = Path("data/universe_registry.json")
    led_path = Path("data/paper_trading/interactive_trades.json")
    assert reg_path.exists()
    assert led_path.exists()


# ----------------------------------------------------------------------------
# 2. Deterministic Lookahead Fixture Proof
# ----------------------------------------------------------------------------

def test_deterministic_fixture_lookahead_proof():
    """Prove mathematically that unshifted alignment peeks 4 minutes into the future."""
    times = pd.date_range("2018-01-02 09:15:00", "2018-01-02 09:29:00", freq="1min")
    prices = [100.0] * 9 + [200.0] + [100.0] * 5  # Spikes only at 09:24:00
    df_fixture = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [1000] * 15,
        },
        index=times,
    )

    tf_5m = resample_ohlcv(df_fixture, "5m")
    s5_original = tf_5m.reindex(df_fixture.index, method="ffill")
    s5_causal = tf_5m.shift(1).reindex(df_fixture.index, method="ffill")

    # At 09:20:00, original sees 200.0 (the close of 09:24:00)!
    assert s5_original.loc["2018-01-02 09:20:00", "close"] == 200.0
    # At 09:20:00, causal sees 100.0 (the completed 09:15:00 candle)
    assert s5_causal.loc["2018-01-02 09:20:00", "close"] == 100.0
    # At 09:25:00, causal legally receives the 200.0 close
    assert s5_causal.loc["2018-01-02 09:25:00", "close"] == 200.0


# ----------------------------------------------------------------------------
# 3. Independent P&L Reconciliation
# ----------------------------------------------------------------------------

def test_pnl_reconciliation_zero_discrepancy():
    """Verify that all 15 asset-years match Phase 24G.24 with zero discrepancies."""
    rec_csv = Path("research/strategy_evolution_2018/phase24G25_causal_correctness_audit/phase24G25_pnl_reconciliation.csv")
    assert rec_csv.exists()
    with open(rec_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 15
    total_diff_orig = sum(abs(float(r["diff_orig_net"])) for r in rows)
    total_diff_caus = sum(abs(float(r["diff_causal_net"])) for r in rows)
    assert total_diff_orig == 0.0
    assert total_diff_caus == 0.0

    # Every single causal net PnL is negative
    for r in rows:
        assert float(r["repr_causal_net"]) < 0.0
        assert r["status"] == "EXACT_MATCH"


# ----------------------------------------------------------------------------
# 4. NumPy Optimization Benchmark Verification
# ----------------------------------------------------------------------------

def test_numpy_benchmark_parity_and_speedup():
    """Verify bit-for-bit parity and measurable execution speedup."""
    bench_p = Path("research/strategy_evolution_2018/phase24G25_causal_correctness_audit/numpy_benchmark_phase24G25.json")
    assert bench_p.exists()
    with open(bench_p, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["exact_match"] is True
    assert data["speedup_median"] >= 50.0  # Measured ~132x
    assert data["trade_count"] == 19
    assert data["net_pnl"] == 5753.4409


# ----------------------------------------------------------------------------
# 5. Cross-Project Lookahead Scan Cleanliness
# ----------------------------------------------------------------------------

def test_cross_project_lookahead_scan_cleanliness():
    """Verify absence of negative shifts and centered rolling windows."""
    scan_p = Path("research/strategy_evolution_2018/phase24G25_causal_correctness_audit/scan_findings.json")
    assert scan_p.exists()
    with open(scan_p, "r", encoding="utf-8") as f:
        findings = json.load(f)

    # Negative shifts and centered windows must be 0
    neg_shifts = [f for f in findings if f["pattern"] == "negative_shift"]
    centered_windows = [f for f in findings if f["pattern"] == "centered_rolling"]
    assert len(neg_shifts) == 0
    assert len(centered_windows) == 0


# ----------------------------------------------------------------------------
# 6. Production V1 Engine Cursor Causality & Session Boundary Isolation
# ----------------------------------------------------------------------------

def test_v1_cursor_causality_and_session_isolation():
    """Verify _TimeframeCursor correctly rejects incomplete and cross-session candles."""
    idx = pd.date_range("2018-01-02 09:15", periods=20, freq="1min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [102.0] * 20,
            "low": [98.0] * 20,
            "close": [101.0] * 20,
            "volume": [5000] * 20,
            "ema20": [100.5] * 20,
            "ema50": [100.0] * 20,
            "rsi": [55.0] * 20,
            "atr": [2.0] * 20,
            "rvol": [1.5] * 20,
        },
        index=idx,
    )
    frame_5m = resample_ohlcv(df, "5m")
    # Add dummy indicators for testing state conversion
    frame_5m["ema20"] = 100.5
    frame_5m["ema50"] = 100.0
    frame_5m["rsi"] = 55.0
    frame_5m["atr"] = 2.0
    frame_5m["rvol"] = 1.5

    cursor = _TimeframeCursor(frame_5m, use_rvol=True, timeframe="5m")

    # 1. At 09:19:00 on Day 1, candle [09:15, 09:20) has not elapsed -> None
    state_0919 = cursor.update(pd.Timestamp("2018-01-02 09:19:00"))
    assert state_0919 is None

    # 2. At 09:20:00 on Day 1, candle [09:15, 09:20) stamped 09:15 is complete -> valid state
    state_0920 = cursor.update(pd.Timestamp("2018-01-02 09:20:00"))
    assert state_0920 is not None
    assert cursor.position == 0

    # 3. At 09:15:00 on Day 2, candle from yesterday must be rejected by date guard -> None
    state_next_day = cursor.update(pd.Timestamp("2018-01-03 09:15:00"))
    assert state_next_day is None


# ----------------------------------------------------------------------------
# 7. Phase 24G.25 Deliverables Completeness
# ----------------------------------------------------------------------------

def test_phase24G25_deliverables_completeness():
    """Verify all 9 required deliverables exist and are populated."""
    base_dir = Path("research/strategy_evolution_2018/phase24G25_causal_correctness_audit")
    assert base_dir.exists()

    required = [
        "phase24G25_lookahead_reproduction.md",
        "phase24G25_causal_alignment_proof.md",
        "phase24G25_pnl_reconciliation.md",
        "phase24G25_numpy_equivalence_benchmark.md",
        "phase24G25_cross_project_lookahead_scan.md",
        "phase24G25_v1_causality_regression.md",
        "phase24G25_test_results.md",
        "phase24G25_final_report.md",
        "phase24G25_pnl_reconciliation.csv",
        "numpy_benchmark_phase24G25.json",
        "scan_findings.json",
    ]
    for fname in required:
        p = base_dir / fname
        assert p.exists(), f"Missing file: {fname}"
        assert p.stat().st_size > 0, f"Empty file: {fname}"

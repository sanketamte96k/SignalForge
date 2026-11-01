# SignalForge Phase 24G.15 — Research Integrity & Strategy Test Results

**Date**: November 2026  
**Environment**: Python 3.14.3 / pytest 9.1.1 (Windows)  
**Target Architecture**: SignalForge V2 Modular Risk & Execution Engine (`src/backtest/risk_engine_v2.py`)  
**Status**: `ALL TEST SUITES PASSING (61 / 61 TESTS)`

---

## 1. Executive Summary

This document certifies the formal execution and verification of SignalForge's test suites following the Phase 24G.15 Training and Validation Research Continuation. All 61 automated unit and integration tests across 5 dedicated test modules passed with 100% compliance.

| Test Module | Coverage Scope | Tests | Result | Runtime |
| :--- | :--- | :---: | :---: | :---: |
| [`tests/test_phase24G15_research_integrity.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G15_research_integrity.py) | 2020 Holdout Quarantine, Causal Timing, Next-Open Execution, Cost Model, Replay Determinism, Protected Assets | 8 | **PASS** | 0.76s |
| [`tests/test_phase24G15_strategy_research.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G15_strategy_research.py) | Alternative Hypotheses Indicator Math, Squeeze Conditions, Multi-Timeframe Feature Builder, Signal Invariants | 4 | **PASS** | 1.05s |
| [`tests/test_phase24G14_cost_and_alpha_investigation.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G14_cost_and_alpha_investigation.py) | Indian Transaction Cost Audit, Gross Alpha Decomposition, Re-entry Churn Diagnostics | 5 | **PASS** | 1.15s |
| [`tests/test_risk_engine_v2_audit.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_risk_engine_v2_audit.py) | Adversarial Risk Engine V2 Audit, Boundary Conditions, Negative Price Handling, Leverage Caps | 14 | **PASS** | 0.95s |
| [`tests/test_risk_and_exit_engine_spec.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_risk_and_exit_engine_spec.py) | V2 Specification Acceptance Suite (`SF-SPEC-RISK-2026-V2`), Brackets, Trailing Ratchet, Circuit Breakers | 30 | **PASS** | 1.45s |
| **Total Cumulative Test Suite** | **Comprehensive Engine, Research & Strategy Verification** | **61** | **PASS** | **5.36s** |

---

## 2. Detailed Breakdown: Research Integrity Suite (`test_phase24G15_research_integrity.py`)

The newly implemented research integrity test suite verifies critical scientific and quantitative standards:

### 2.1 `test_quarantine_2020_holdout_lockout`
- **Objective**: Ensure programmatic impossibility of evaluating or reading 2020 holdout data.
- **Verification**: Passing any partition name containing `"2020"` or `"Holdout (2020)"` to the diagnostic calculation engine actively triggers `PermissionError("CRITICAL RESEARCH INTEGRITY VIOLATION: 2020 Holdout is quarantined and cannot be evaluated.")`.
- **Result**: **PASS**.

### 2.2 `test_strict_temporal_causality`
- **Objective**: Guarantee absolute zero lookahead bias in indicator generation.
- **Verification**: Evaluates EMA, RSI, and ATR on a truncated series (bars $0..150$) versus the full series (bars $0..300$). Asserts bit-for-bit numerical invariance up to bar 150 (`rtol=1e-10`).
- **Result**: **PASS**.

### 2.3 `test_execution_causality_next_bar_open`
- **Objective**: Verify that signals emitted at bar $t$ fill strictly at bar $t+1$ open.
- **Verification**: Submits a signal at bar 10. Verifies that trade entry timestamp matches bar 11 timestamp (`2019-03-01 09:26:00`), and executed entry price matches bar 11 open price (`399.6381`).
- **Result**: **PASS**.

### 2.4 `test_single_application_of_transaction_friction`
- **Objective**: Audit cost accounting to confirm realistic Indian statutory friction is applied exactly once per trade.
- **Verification**: Reconciles executed trade ledger: verifies $NetPnL = GrossPnL - TransactionCost$ and confirms non-zero statutory charges (STT, exchange turnover, SEBI, stamp duty, GST).
- **Result**: **PASS**.

### 2.5 `test_max_concurrent_positions_enforcement`
- **Objective**: Prevent multi-position stacking or accidental pyramiding.
- **Verification**: Emits 11 consecutive LONG signals while a position is already open. Verifies that subsequent signals are ignored, maintaining strictly 1 active position and producing exactly 1 completed trade upon exit.
- **Result**: **PASS**.

### 2.6 `test_partition_state_isolation`
- **Objective**: Prevent state leaks across partitions.
- **Verification**: Executes Partition 1 with active trades, then executes Partition 2 with null signals. Confirms that Partition 2 initializes with 0 open positions, initial capital of exactly ₹100,000.00, and an empty trade ledger.
- **Result**: **PASS**.

### 2.7 `test_deterministic_reproducibility`
- **Objective**: Enforce bit-for-bit repeatability across independent runs.
- **Verification**: Executes two independent backtests on identical data and signals. Verifies identical trade counts, gross P&L, transaction costs, net P&L, timestamps, and individual trade records.
- **Result**: **PASS**.

### 2.8 `test_protected_assets_integrity`
- **Objective**: Cryptographic verification of frozen baseline assets.
- **Verification**:
  - Strategy snapshot canonical JSON hash matches `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`.
  - `ADANIPORTS_1m.csv` dataset SHA-256 matches `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`.
  - Universe registry (`data/universe_registry.json`) and paper ledger (`data/paper_trading/interactive_trades.json`) exist and are untouched.
- **Result**: **PASS**.

---

## 3. Cryptographic Verification & Audit Sign-Off

```
TEST SUITE INTEGRITY MANIFEST:
================================================================================
Python Version: 3.14.3
Pytest Version: 9.1.1
Repository Branch: main
Preflight V1 Hash: 920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7 [MATCH]
Preflight Data Hash: fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9 [MATCH]
Paper Trading Ledger: UNTOUCHED
Universe Registry: UNTOUCHED
================================================================================
OVERALL STATUS: ALL 61 TESTS PASSED SUCCESSFULLY
```

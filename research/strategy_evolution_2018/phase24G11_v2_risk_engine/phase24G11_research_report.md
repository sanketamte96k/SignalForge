# SignalForge Phase 24G.11 — Isolated V2 Risk Engine Implementation & Research Gate Report

**Date**: 2026-10-28  
**Phase**: Phase 24G.11  
**Status**: COMPLETE (SIMULATOR RESEARCH CANDIDATE IMPLEMENTED & ACCEPTANCE VALIDATED)  
**Parent Strategy Baseline**: SignalForge V1 (Frozen Hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`)  
**Engine Specification**: `SF-SPEC-RISK-2026-V2` (from Phase 24G.10)  

---

## 1. Executive Summary & Objective

Phase 24G.11 implements the approved Phase 24G.10 risk-and-exit specification into an isolated, deterministic simulation engine candidate (`RiskEngineV2` / `src/backtest/risk_engine_v2.py`). 

### Core Governance Constraints
- **Strict Isolation**: Frozen SignalForge V1 strategy, historical backtest engine, and paper-trading pipelines remain completely unmodified.
- **Simulator Engineering Only**: This phase does **not** qualify a strategy, claim alpha discovery, or authorize paper or live trading.
- **Instrument Safeguards**: `ADANIPORTS` status remains strictly `NOT_TESTED`; `ADANIENT` status remains `VERIFICATION_REQUIRED` (blocked).
- **Anti-Overfitting Protection**: No parameter tuning against 2019 validation or 2020 holdout was performed. All unestablished parameters (DEC-01 through DEC-09) are governed by mandatory configuration assertions requiring explicit test fixtures (`is_test_fixture=True`) or formal pre-registration (`is_pre_registered=True`).

---

## 2. Preflight Verification

Prior to any code modification, preflight invariants were inspected and verified against the established repository state:

| Preflight Item | Required Contract | Actual Verified State | Status |
| :--- | :--- | :--- | :--- |
| **Git Branch & HEAD** | `main` | `main` @ [`12a8c76`](https://github.com/sanketamte96k/SignalForge/commit/12a8c76) | **VERIFIED** |
| **Strategy Config Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **MATCH** |
| **ADANIPORTS SHA-256** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **MATCH** |
| **Working Tree** | Clean | Verified clean at start | **PASS** |
| **Active Paper Ledger** | Untouched | [`data/paper_trading/interactive_trades.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/paper_trading/interactive_trades.json) unmodified | **PASS** |
| **Universe Registry** | Untouched | [`data/universe_registry.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/universe_registry.json) unmodified | **PASS** |
| **ADANIPORTS Status** | `NOT_TESTED` | `NOT_TESTED` preserved | **PASS** |
| **ADANIENT Status** | `VERIFICATION_REQUIRED` | `VERIFICATION_REQUIRED` (Blocked) preserved | **PASS** |

---

## 3. V2 Risk Engine Architecture

The V2 Risk Engine is implemented in [`src/backtest/risk_engine_v2.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/backtest/risk_engine_v2.py) as an isolated, standalone research candidate.

### 3.1 Architectural Structure
- **`ExecutionModel`**: Enum supporting `NEXT_OPEN` (realistic primary execution) and `SAME_CLOSE` (theoretical baseline).
- **`CostModel`**: Enum supporting `REALISTIC_INTRADAY` (statutory Indian fee structure + morning/normal slippage) and `HISTORICAL_BASELINE` (flat 1 bps).
- **`RiskEngineConfigV2`**: Immutable dataclass with built-in parameter validation enforcing:
  - Capital budget $C > 0$.
  - Per-trade risk budget $r \in (0, 0.02]$.
  - Maximum gross leverage $L_{\max} \le 5.0$.
  - ATR multiplier $k_{\text{stop}} > 0$.
  - Target multiple $k_{\text{target}} \ge k_{\text{stop}}$ (when target enabled).
  - Frozen conservative collision rule (`"stop_first"`).
  - Explicit governance validation: requires `is_test_fixture=True` or `is_pre_registered=True`.
- **`PositionV2` & `TradeV2`**: Pure dataclasses tracking active position state, entry/exit timestamps, nominal stop prices, high/low watermarks, exit reason codes, gross/net P&L, and detailed transaction cost breakdowns.
- **`RiskMetricsV2`**: Container for summary backtest metrics and canonical SHA-256 hash of the complete trade ledger.

### 3.2 Mathematical Formulation & Rules Implemented
1. **Position Sizing and Leverage Clamping**:
   $$Q = \min\left( \left\lfloor \frac{R_{\text{trade}}}{D_{\text{stop}}} \right\rfloor, \left\lfloor \frac{C \cdot L_{\max}}{P_{\text{entry}}} \right\rfloor \right)$$
   Where monetary risk budget $R_{\text{trade}} = C \cdot r$ and stop distance $D_{\text{stop}} = \max\left(k_{\text{stop}} \cdot \text{ATR}_t, 0.05, 0.0020 \cdot P_{\text{entry}}\right)$. If $Q < 1$, entry is rejected.
2. **Monotonic Trailing Stop Ratchet**:
   - Long: $P_{\text{stop},\tau} = \max\left(P_{\text{stop},\tau-1}, \text{High}_\tau - k_{\text{trail}} \cdot \text{ATR}_{\tau}\right)$ (enforcing $\Delta P_{\text{stop}} \ge 0$).
   - Short: $P_{\text{stop},\tau} = \min\left(P_{\text{stop},\tau-1}, \text{Low}_\tau + k_{\text{trail}} \cdot \text{ATR}_{\tau}\right)$ (enforcing $\Delta P_{\text{stop}} \le 0$).
   - Activation gated by $R$-multiple threshold ($\text{High}_\tau - P_{\text{entry}} \ge k_{\text{trail\_act}} \cdot D_{\text{stop}}$ for longs).
3. **Opening Gap-Through Stop Evaluation**:
   - Evaluated strictly against previous bar close stop $P_{\text{stop},\tau-1}$ before intrabar ratcheting:
     - Long: If $\text{Open}_\tau \le P_{\text{stop},\tau-1}$, exit triggered immediately at $P_{\text{exit}} = \text{Open}_\tau$ (loss may exceed $1R$).
     - Short: If $\text{Open}_\tau \ge P_{\text{stop},\tau-1}$, exit triggered immediately at $P_{\text{exit}} = \text{Open}_\tau$.
4. **Intrabar Stop & Conservative Collision Precedence**:
   - Long: If $\text{Low}_\tau \le P_{\text{stop},\tau}$, exit triggered at $\min(P_{\text{stop},\tau}, \text{Open}_\tau)$.
   - Collision: If both target and stop are breached in the same bar, the conservative specification rule `collision_resolution = "stop_first"` guarantees stop exit.
5. **Holding Time & Session Boundaries**:
   - Max holding duration: Position closed after $M_{\max}$ bars from entry bar.
   - Mandatory EOD liquidation: All open positions liquidated at 15:29:00 bar open price.
   - Session rollover / Partition boundary: All pending orders purged; positions closed before new session begins.
6. **Risk Circuit Breakers**:
   - Daily Loss Circuit Breaker: Halts new entries for the remainder of the session when cumulative realized + unrealized loss exceeds $\theta_{\text{day}} \cdot C$.
   - Consecutive Loss Cooldown: Enforces a pause of $M_{\text{cooldown}}$ bars after $N_{\text{streak}}$ consecutive losing trades.
7. **Bankruptcy Protection**:
   - If equity $\le 0$, simulation terminates immediately with fatal error.
8. **Realistic Transaction Costs & Slippage**:
   - Brokerage: $\min(0.0003 \cdot \text{Turnover}, 20.00)$ per order.
   - STT: 0.025% on sell turnover.
   - Exchange Turnover: 0.00297% on turnover.
   - SEBI Charges: 0.0001% on turnover.
   - Stamp Duty: 0.003% on buy turnover.
   - GST: 18% on (Brokerage + Exchange + SEBI).
   - Slippage: 5 bps during morning window (09:15–10:00), 2 bps thereafter.

---

## 4. Acceptance Test Matrix (Phase 24G.10 Compliance)

All 15 acceptance test cases defined in [`acceptance_test_matrix.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/acceptance_test_matrix.md) and 15 additional boundary and symmetry tests were implemented in [`tests/test_risk_and_exit_engine_spec.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_risk_and_exit_engine_spec.py).

### Acceptance Test Matrix Results

| Test ID | Name & Description | Primary Invariant Tested | Result |
| :--- | :--- | :--- | :--- |
| **TC-RISK-01** | Standard Intraday Roundtrip | Next-open entry at bar $t+1$, target exit at bar $t+3$, correct sizing and P&L accounting. | **PASSED** |
| **TC-RISK-02** | Stop-Loss Exit on Intrabar Low | Stop hit at nominal stop price when $\text{Low} \le P_{\text{stop}}$ and $\text{Open} > P_{\text{stop}}$. | **PASSED** |
| **TC-RISK-03** | Opening Gap Penetration | Exit at $\text{Open}$ price when market gaps beyond stop; loss exceeds nominal $1R$ budget. | **PASSED** |
| **TC-RISK-04** | Target & Stop Collision Precedence | Stop-first conservative precedence enforced when candle range touches both stop and target. | **PASSED** |
| **TC-RISK-05** | Monotonic Trailing Ratchet | Stop ratchets upward on new highs; strictly does not loosen during subsequent pullbacks. | **PASSED** |
| **TC-RISK-06** | Maximum Holding Duration | Position liquidated at open of bar $t + M_{\max} + 1$ with exit reason `TIME_STOP`. | **PASSED** |
| **TC-RISK-07** | Mandatory EOD Square-Off | Open position liquidated at 15:29:00 bar open; zero overnight carry. | **PASSED** |
| **TC-RISK-08** | Leverage Cap Binding Sizing | Low ATR volatility clamps quantity to leverage ceiling $\lfloor C \cdot L_{\max} / P \rfloor$. | **PASSED** |
| **TC-RISK-09** | Minimum Stop Distance Clamping | Ultra-low ATR clamps stop distance to minimum tick/percentage floor ($\ge 0.0020 \cdot P$). | **PASSED** |
| **TC-RISK-10** | Insufficient Capital Rejection | Entry cleanly rejected when capital budget is insufficient for 1 share ($Q=0$). | **PASSED** |
| **TC-RISK-11** | Daily Loss Circuit Breaker | New entries blocked for remainder of session when cumulative daily loss $\ge \theta_{\text{day}} \cdot C$. | **PASSED** |
| **TC-RISK-12** | Consecutive Loss Streak Cooldown | New entries suppressed for $M_{\text{cooldown}}$ bars after $N_{\text{streak}}$ consecutive losses. | **PASSED** |
| **TC-RISK-13** | Session Rollover & Boundary Purge | Pending orders purged at session boundary; no cross-session carry or execution leakage. | **PASSED** |
| **TC-RISK-14** | Invalid Data & Anomaly Rejection | Bars with $\text{High} < \text{Low}$, non-positive prices, or corrupt data trigger error/skip. | **PASSED** |
| **TC-RISK-15** | Repeat-Run Determinism | Successive backtest runs produce bit-for-bit identical trade logs and identical SHA-256 hash. | **PASSED** |

### Additional Boundary, Symmetry & Regression Tests
- **TC-MATH-01 to 04**: Unit checks on risk budget clamping, leverage bounds, zero-size rejection, and stop distance formula.
- **Short-Side Symmetry Tests**:
  - `test_short_position_lifecycle_next_open`: Short entry at next open, cover at target.
  - `test_short_intrabar_stop_loss_hit`: Short cover at stop when $\text{High} \ge P_{\text{stop}}$.
  - `test_short_opening_gap_through_stop`: Short cover at open when market gaps up above stop.
  - `test_short_trailing_stop_monotonic_downward_ratchet`: Short stop ratchets strictly downward.
  - `test_short_same_candle_collision_stop_first`: Short collision resolves conservatively to stop exit.
- **Edge Cases & Protections**:
  - `test_multi_wave_ratchet_monotonicity`: Stop never loosens through multiple cyclical waves.
  - `test_opening_gap_loss_exceeds_1r`: Verifies realized loss exceeds theoretical $1R$ budget on gap.
  - `test_position_reversal_handling`: Liquidates prior position and enters opposite side at bar open.
  - `test_cost_model_separation_baseline_vs_realistic`: Verifies Indian statutory breakdown against 1 bps flat.

---

## 5. Test Suite Verification & Counts

Exact test commands and verification counts across the SignalForge test suite:

```bash
# 1. V2 Risk Engine Acceptance Suite
pytest tests/test_risk_and_exit_engine_spec.py
# Result: 30 passed in 0.43s

# 2. Causal Timing, Indicators, & Historical Backtest Regression Suite
pytest tests/test_historical_backtest.py tests/test_engine.py tests/test_simulator.py tests/test_causality_validation.py tests/test_causal_candle_execution_timing.py tests/test_causal_indicators.py tests/test_causal_indicator_equivalence.py tests/test_causal_replay_lookahead.py tests/test_causal_replay_parity.py
# Result: 124 passed in 25.05s

# 3. Strategy Correctness, Context, & Data Leakage Suite
pytest tests/test_backtest_correctness_audit.py tests/test_backtest_integration.py tests/test_backtest_strategy.py tests/test_metrics.py tests/test_paper_backtest_parity.py tests/test_strategy_causality.py tests/test_strategy_context.py tests/test_strategy_future_data_leakage.py
# Result: 82 passed in 63.86s

# Total tests passed: 236 tests, 0 failures, 0 warnings
```

---

## 6. V1 Regression & Benchmark Invariance

To guarantee that the frozen V1 baseline was not altered in any way:
1. **Strategy Config Hash**: Re-verified hash of `SignalForgeV1Strategy(config)` remains:
   `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` (exact match).
2. **Historical Backtest Parity on ADANIPORTS**:
   - `same_close` model: 754 trades, Gross P&L: -Rs 271.48, Net P&L: -Rs 271.48 (0 bps baseline).
   - `next_open` model: 754 trades, Gross P&L: -Rs 270.93, Net P&L: -Rs 270.93 (0 bps baseline).
3. **Repository Cleanliness**:
   - Active ledger [`data/paper_trading/interactive_trades.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/paper_trading/interactive_trades.json) untouched.
   - Universe registry [`data/universe_registry.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/universe_registry.json) untouched.
   - Collector states untouched.

---

## 7. Unresolved Parameters Governance Status

All unestablished parameters from the Phase 24G.10 Unresolved Decisions Register remain strictly quarantined from empirical fitting:

| Decision ID | Parameter | Governed Range | Phase 24G.11 Implementation Status |
| :--- | :--- | :--- | :--- |
| **DEC-01** | $k_{\text{stop}}$ (ATR Stop Multiplier) | $[1.0, 3.0]$ | Parameterized in `RiskEngineConfigV2`; requires test fixture or pre-registration. |
| **DEC-02** | $k_{\text{target}}$ (Target Multiplier) | $[1.5, 5.0]$ or `None` | Parameterized; enforces $k_{\text{target}} \ge k_{\text{stop}}$. Optional (`None` supported). |
| **DEC-03** | Trailing Stop Ratchet ($k_{\text{trail}}$) | $[0.5, 2.0]$ | Parameterized; enforces monotonic updates and activation threshold. |
| **DEC-04** | $M_{\max}$ (Max Holding Duration) | $[15, 60]$ bars | Parameterized; liquidated at $M_{\max} + 1$ open if enabled. |
| **DEC-05** | $T_{\text{open\_filter}}$ (Morning Window) | 09:15–10:00 AM | Blackout window hook parameterized; not tuned against holdout. |
| **DEC-06** | $\theta_{\text{day}}$ (Daily Circuit Breaker) | $1.0\% - 3.0\%$ | Validated in test fixtures; stops new entries when tripped. |
| **DEC-07** | $N_{\text{streak}}$ (Consecutive Loss Cooldown) | 2–4 trades | Validated in test fixtures; pauses entries for $M_{\text{cooldown}}$ bars. |
| **DEC-08** | Transaction Cost Model | Baseline vs. Realistic | Fully implemented dual models (`HISTORICAL_BASELINE` vs `REALISTIC_INTRADAY`). |
| **DEC-09** | Intrabar Collision Precedence | `"stop_first"` | Frozen to conservative `"stop_first"`; assertion prevents unapproved values. |

---

## 8. Research Gate Decision & Governance Notice

```
========================================================================================
RESEARCH GATE STATUS: PHASE 24G.11 COMPLETED — ISOLATED SIMULATION ENGINE CANDIDATE
========================================================================================
1. RiskEngineV2 implemented in src/backtest/risk_engine_v2.py as an isolated module.
2. All 15 Phase 24G.10 acceptance tests and 15 boundary/symmetry tests PASS.
3. SignalForge V1 frozen strategy configuration and hash remain UNCHANGED.
4. V1 backtest engine behavior, trade counts, and benchmark metrics remain IDENTICAL.
5. ADANIPORTS qualification remains NOT_TESTED.
6. ADANIENT qualification remains VERIFICATION_REQUIRED and BLOCKED.
7. Engine remains a RESEARCH-ONLY SIMULATION CANDIDATE.
   - NOT approved for paper trading.
   - NOT approved for live execution.
   - Risk controls DO NOT convert negative gross alpha into a profitable strategy.
========================================================================================
```

# SignalForge Phase 24G.12 — Independent V2 Risk Engine Audit Report

**Date**: 2026-10-31  
**Phase**: Phase 24G.12  
**Audit Target**: `src/backtest/risk_engine_v2.py` (Candidate from Phase 24G.11)  
**Parent Specification**: `SF-SPEC-RISK-2026-V2` (Phase 24G.10)  
**Parent Strategy Baseline**: SignalForge V1 (Frozen Hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`)  
**Audit Decision**: **PASS (REMEDIATED FOR SIMULATOR RESEARCH ONLY)**  

---

## 1. Executive Summary & Audit Decision

Phase 24G.12 conducted an exhaustive, adversarial, independent code and accounting audit of the V2 Risk and Exit Engine candidate implemented in Phase 24G.11 (`RiskEngineV2` / [`src/backtest/risk_engine_v2.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/backtest/risk_engine_v2.py)).

### Audit Summary
The engine candidate's core architecture was verified to be strictly isolated from the frozen SignalForge V1 strategy and production paper trading ledgers. However, rigorous adversarial stress-testing identified **four confirmed defects** and **one edge-case inconsistency** in the Phase 24G.11 implementation:
1. **Intrabar Stop-Loss Overwrite by Trailing Ratchet (Causality / Look-Ahead Defect)**: When a bar's extreme breached the initial stop while the opposite extreme triggered a trailing ratchet update, updating the ratchet prior to evaluating stop hits erased the initial stop breach, converting an actual stop-loss into an erroneous winning trailing exit.
2. **Slippage Double-Deduction**: Execution slippage was applied directly to fill prices (reducing gross P&L by $2 \times \text{slippage} \times Q$) and subsequently added into transaction costs in `_execute_exit`, deducting slippage twice from net P&L.
3. **Consecutive Loss Cooldown Omission in `same_close` Reversals**: Reversals executed under the `same_close` execution model omitted updating `consecutive_losses` and checking `cooldown_until`, bypassing streak cooldown protection.
4. **Unhandled Non-Finite (`NaN`/`Inf`) Crash**: Non-finite prices slipped past `(df["Low"] <= 0).any()` data validation and caused unhandled `ValueError: cannot convert float NaN to integer` in `calculate_position_size`.
5. **Inconsistent Slippage on Partition Purge (Step 7)**: Liquidation at the final bar of a partition omitted slippage deduction.

All five defects were remediated with minimal, isolated, surgical fixes. An independent adversarial test suite ([`tests/test_risk_engine_v2_audit.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_risk_engine_v2_audit.py)) containing 14 adversarial tests was added. All 250 tests across the SignalForge test suite pass with zero regressions.

### Final Audit Decision
```
========================================================================================
AUDIT DECISION: PASS (FOR SIMULATOR RESEARCH ONLY)
========================================================================================
- Five confirmed defects identified, documented, and remediated with isolated fixes.
- 44 V2 Risk Engine tests (30 acceptance + 14 adversarial audit tests) PASS.
- 206 V1 historical, causal, indicator, and strategy regression tests PASS.
- SignalForge V1 baseline frozen config hash remains IDENTICAL:
  920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7
- ADANIPORTS qualification remains strictly NOT_TESTED.
- ADANIENT qualification remains VERIFICATION_REQUIRED and BLOCKED.
- RESEARCH SIMULATOR ONLY: No live trading authorization, broker integration,
  or claim of alpha profitability is granted.
========================================================================================
```

---

## 2. Preflight Verification & Governance Contract

All preflight checks were completed prior to code audit:

| Preflight Item | Required Contract | Actual Verified State | Status |
| :--- | :--- | :--- | :--- |
| **Git Branch** | `main` | `main` | **PASS** |
| **Commit Baseline** | `1623300813e5fa5ea4d233237e9e9a6f10f47130` | `1623300813e5fa5ea4d233237e9e9a6f10f47130` | **MATCH** |
| **Working Tree** | Clean (`git status --short` empty) | Clean at preflight start | **PASS** |
| **V1 Strategy Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **MATCH** |
| **ADANIPORTS Status** | `NOT_TESTED` | Preserved untouched in registry | **PASS** |
| **ADANIENT Status** | `VERIFICATION_REQUIRED` | Preserved untouched in registry | **PASS** |
| **Active Paper Ledger** | Untouched | [`data/paper_trading/interactive_trades.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/paper_trading/interactive_trades.json) untouched | **PASS** |
| **Universe Registry** | Untouched | [`data/universe_registry.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/universe_registry.json) untouched | **PASS** |

---

## 3. Independent Code Audit: Behavioral Verification

### 3.1 Position Sizing
- **Zero, Negative, & Boundary Values**: Inputs where $C \le 0$, $r \le 0$, $P \le 0$, $D_{\text{stop}} \le 0$, or $L_{\max} \le 0$ safely return $Q = 0$.
- **Non-Finite Handling**: Non-finite values (`NaN`, `Inf`, `-Inf`) are now explicitly caught by `math.isfinite()` guards, returning $Q = 0$ rather than crashing in `math.floor()`.
- **Quantity Flooring & Clamping**: Quantity is floored to integer units via $\min(Q_{\text{risk}}, Q_{\text{leverage}})$. Stop distance is clamped to at least $\max(\text{tick\_size}, P_{\text{entry}} \times 0.0020)$, preventing division-by-zero or excessive sizing on compressed ATR.
- **Risk Budget vs Friction**: The nominal risk budget $R_{\text{trade}} = C \cdot r$ sizes purely for gross price risk $Q \times D_{\text{stop}} \le R_{\text{trade}}$. Brokerage, statutory charges, and execution slippage are additive upon stop hit, causing the realized net loss to moderately exceed $1R$ (e.g. $1.02R$ to $1.05R$). This behavior is mathematically correct and fully documented.
- **Integer Overflow**: Python arbitrary-precision integers eliminate 32/64-bit integer overflow.

### 3.2 Stops & Execution
- **Intrabar Stop Precedence vs Trailing Ratchet**: Audited and confirmed that updating `TrailingStopRatchet` before checking the pre-existing stop violated conservative stop-first resolution. The engine now evaluates the bar's extreme against the pre-existing stop (`stop_before_bar`) *before* applying intrabar trailing ratchet progression.
- **Gap-Through-Stop Execution**: Opening gap breaches are evaluated at bar open and filled at $\text{Open} \pm \text{Slippage}$ rather than the nominal stop price, faithfully recording tail losses $> 1R$.
- **Conservative Same-Candle Collisions**: When a bar touches both the pre-existing stop and take-profit target, stop-loss precedence is strictly enforced, liquidating at the stop price and ignoring the target.
- **Trailing Stop Monotonicity**: Ratchet is strictly non-decreasing for LONG and non-increasing for SHORT across complex multi-wave oscillations.
- **Maximum Holding Duration**: Positions exceeding $M_{\max}$ bars liquidate at the open of bar $t_{\text{entry}} + M_{\max} + 1$ with reason code `MAX_TIME`.
- **Mandatory 15:29 EOD Liquidation**: All open positions square off at `15:29:00` close with reason code `EOD`, guaranteeing zero overnight exposure.
- **Causality & Look-Ahead**: ATR for sizing is causal to bar $t-1$ close. No future candle data is leaked into signal or execution evaluation.

### 3.3 Risk Limits & Accounting
- **Daily Loss Circuit Breaker**: Running net loss $\Delta C_d(\tau) = \text{Realized P\&L}_d + \text{Unrealized Gross P\&L}$ trips immediately at or below $-C_{d,\text{start}} \cdot \theta_{\text{day}}$. Open positions liquidate at market close with `DAILY_LOSS_HALT`.
- **Session Persistence**: Once tripped, `day_halted` remains active for all subsequent bars in that session and automatically resets on the next calendar day (`current_day_date != cur_date`).
- **Consecutive Loss Cooldown**: Enforces a cooling-off pause ($T_{\text{cooldown}}$ minutes) upon reaching $N_{\text{streak}}$ consecutive losses across both `next_open` and `same_close` models. Reset to 0 occurs upon any profitable trade.
- **Slippage Reconciliation**: Remediated double-deduction. Net P&L reconciliation identity $\text{Net P\&L} = \text{Gross P\&L} - \text{Transaction Costs}$ holds exactly.
- **Deterministic Replay**: Independent simulation runs produce bit-for-bit identical trade logs and matching 64-character SHA-256 canonical hashes.

### 3.4 Data Integrity & Safety
- **Missing Bar Discontinuities**: Intraday timestamp gaps $> 1$ minute cancel pending entry orders with `MISSING_DATA_GAP`.
- **Data Validation**: Input DataFrames with invalid monotonicity, duplicate timestamps, $H < L$, non-positive prices, negative volume, or `NaN`/`Inf` are immediately rejected with clean `ValueError` exceptions.
- **Boundary Purging**: Pending orders at `15:29:00` are cancelled at day rollover (`DAY_ROLLOVER_CANCELLED`). Signals on the final bar of a partition do not generate orphan trades.
- **V1 Strategy & Production Isolation**: Zero broker network calls, zero paper orders, zero modifications to active ledgers (`interactive_trades.json`) or universe registry (`universe_registry.json`).

---

## 4. Confirmed Defects and Isolated Fix Proposals

### Defect 1: Intrabar Stop-Loss Overwrite by Trailing Ratchet
- **Severity**: HIGH (Causality / Look-ahead violation producing positive survivorship bias)
- **Root Cause**: In `RiskEngineV2.run` Step 5, `ratchet.update(candle_high, candle_low)` was invoked at Step C before evaluating intrabar stop-loss hits at Step D.
- **Remediation**: Reordered Step 5 so that the pre-existing stop (`stop_before_bar`) is evaluated first. If `cur_bar_low <= stop_before_bar` (for LONG) or `cur_bar_high >= stop_before_bar` (for SHORT), the position exits at the pre-existing stop. Only if the pre-existing stop was not hit does `ratchet.update` progress the trailing ratchet.
- **Regression Tests**: `test_adversarial_intrabar_stop_breach_before_trailing_ratchet_long` and `test_adversarial_intrabar_stop_breach_before_trailing_ratchet_short`.

### Defect 2: Execution Slippage Double-Deduction
- **Severity**: MEDIUM (Accounting distortion penalizing net P&L)
- **Root Cause**: Fill prices were shifted by `slippage`, reducing `gross_pnl` by $2 \times \text{slippage} \times Q$. Then `_execute_exit` passed `slippage_per_share=self.config.slippage` to `calculate_transaction_costs`, which added $2 \times \text{slippage} \times Q$ to `costs.total_costs`, deducting slippage twice.
- **Remediation**: In `_execute_exit`, when `self.config.slippage > 0`, non-price transaction costs (brokerage + statutory fees) are deducted from `gross_pnl` via `deducted_costs = costs.total_costs - costs.slippage`, while `costs.slippage` remains available in `CostBreakdown` for audit reporting.
- **Regression Test**: `test_adversarial_slippage_accounting_no_double_deduction`.

### Defect 3: Consecutive Loss Streak Cooldown Bypass in `same_close` Reversals
- **Severity**: MEDIUM (Risk-limit enforcement bypass)
- **Root Cause**: In `RiskEngineV2.run` Step 6, `same_close` reversal exits omitted `consecutive_losses` increment and `cooldown_until` validation.
- **Remediation**: Added consecutive loss counter updates, cooldown timer calculation, and `is_cooldown` audit rejection checks to the `same_close` reversal execution block, matching the `next_open` implementation.
- **Regression Test**: `test_adversarial_consecutive_loss_cooldown_same_close_reversal`.

### Defect 4: Data Validation and Position Sizing Crash on NaN/Non-Finite Inputs
- **Severity**: MEDIUM (Robustness failure under corrupted input)
- **Root Cause**: `(df["Low"] <= 0).any()` returned `False` for `NaN` values, allowing non-finite price rows to reach `math.floor()` in `calculate_position_size`, raising unhandled `ValueError`.
- **Remediation**: Added `math.isfinite()` parameter validation in `calculate_position_size` and `calculate_clamped_stop_distance`, and added `df[col].isna().any() or not np.isfinite(df[col]).all()` validation in `_validate_and_prepare_data`.
- **Regression Tests**: `test_position_sizing_non_finite_inputs` and `test_data_validation_rejects_nan_and_inf`.

### Defect 5: Slippage Omission on Final Dataset Purge (Step 7)
- **Severity**: LOW (Inconsistent pricing at partition boundary)
- **Root Cause**: Active positions liquidated at Step 7 used `last_close` without applying `self.config.slippage`.
- **Remediation**: Updated Step 7 to compute `exit_p = last_close - slippage` (LONG) or `last_close + slippage` (SHORT).

---

## 5. Test Suite Verification & Counts

Exact test commands, execution runtimes, and pass/fail counts:

```bash
# 1. V2 Risk Engine Combined Suite (Acceptance + Adversarial Audit)
pytest tests/test_risk_and_exit_engine_spec.py tests/test_risk_engine_v2_audit.py
# Result: 44 passed in 1.24s (30 acceptance + 14 adversarial audit tests)

# 2. Causal Timing, Indicators, & Historical Backtest Regression Suite
pytest tests/test_historical_backtest.py tests/test_engine.py tests/test_simulator.py tests/test_causality_validation.py tests/test_causal_candle_execution_timing.py tests/test_causal_indicators.py tests/test_causal_indicator_equivalence.py tests/test_causal_replay_lookahead.py tests/test_causal_replay_parity.py
# Result: 124 passed in 48.37s

# 3. Strategy Correctness, Context, & Data Leakage Suite
pytest tests/test_backtest_correctness_audit.py tests/test_backtest_integration.py tests/test_backtest_strategy.py tests/test_metrics.py tests/test_paper_backtest_parity.py tests/test_strategy_causality.py tests/test_strategy_context.py tests/test_strategy_future_data_leakage.py
# Result: 82 passed in 120.38s

# Total across all test suites: 250 passed, 0 failures, 0 warnings
```

---

## 6. Unsupported Features & Operational Boundaries

To prevent false capability assumptions, the following features are confirmed **UNSUPPORTED** in the current V2 simulator architecture:

| Feature | Status | Engine Behavior |
| :--- | :--- | :--- |
| **Partial Exits (Scaling Out)** | UNSUPPORTED | All exits liquidate 100% of the active position. |
| **Limit Entry Orders** | UNSUPPORTED | Entries execute at market (`next_open` or `same_close`). |
| **Multi-Asset Portfolio Simulation** | UNSUPPORTED | Single asset series processed per run. |
| **Overnight Short Holding** | PROHIBITED | Mandatory `15:29:00` square-off enforces zero overnight exposure. |
| **Broker RMS Emulation** | UNSUPPORTED | Broker auto-square-off call charges or forced margin liquidation are not simulated. |
| **Live Order Routing** | PROHIBITED | Research simulation only; broker API endpoints are strictly decoupled. |

---

## 7. Governance Sign-Off & Safety Declarations

1. **V1 Baseline Preservation**: Strategy configuration hash remains verified at `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`.
2. **Instrument Safeguards**: `ADANIPORTS` status is strictly maintained as `NOT_TESTED`; `ADANIENT` status is strictly maintained as `VERIFICATION_REQUIRED` (blocked).
3. **Ledger Integrity**: Active paper trading ledger [`data/paper_trading/interactive_trades.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/paper_trading/interactive_trades.json) and universe registry [`data/universe_registry.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/universe_registry.json) remain completely unmodified.
4. **Simulator Only Notice**: The V2 Risk Engine candidate is approved for **simulator research only**. It does not confer trading authorization, paper execution authorization, or live broker connectivity.

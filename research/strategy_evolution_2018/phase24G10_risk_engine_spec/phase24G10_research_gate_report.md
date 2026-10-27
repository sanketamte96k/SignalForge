# SignalForge Phase 24G.10 — Risk and Exit Engine Specification & Research Gate Report

**Date**: 2026-10-27  
**Phase**: Phase 24G.10  
**Status**: COMPLETE (SPECIFICATION AND ACCEPTANCE PLANNING ONLY)  
**Parent Strategy Baseline**: SignalForge V1 (Frozen Hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`)  

---

## 1. Objective and Preflight Verification

Phase 24G.10 was initiated following the Phase 24G.9 failure analysis of SignalForge V1. This phase is **purely architectural specification and acceptance test planning**. No strategy modifications or parameter optimizations were performed.

### Preflight Verification Table

| Preflight Item | Required Contract | Actual Verified State | Status |
| :--- | :--- | :--- | :--- |
| **Git Branch & HEAD** | `main` | `main` @ [`82c6a9a`](https://github.com/sanketamte96k/SignalForge/commit/82c6a9a) | **VERIFIED** |
| **Strategy Config Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **MATCH** |
| **ADANIPORTS SHA-256** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **MATCH** |
| **Working Tree** | Clean | Working tree clean prior to specification drafting | **PASS** |
| **Active Paper Ledger** | Untouched | [`data/paper_trading/interactive_trades.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/paper_trading/interactive_trades.json) unmodified | **PASS** |
| **Universe Registry** | Untouched | [`data/universe_registry.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/universe_registry.json) unmodified | **PASS** |
| **ADANIPORTS Status** | `NOT_TESTED` | `NOT_TESTED` preserved | **PASS** |
| **ADANIENT Status** | `VERIFICATION_REQUIRED` | `VERIFICATION_REQUIRED` (Blocked) preserved | **PASS** |

---

## 2. Specification Deliverables Overview

Phase 24G.10 establishes three foundational architectural documents in [`research/strategy_evolution_2018/phase24G10_risk_engine_spec/`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec):

1. **Production Risk and Exit Engine Specification**: [`risk_and_exit_engine_specification.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/risk_and_exit_engine_specification.md)
   - Formal mathematical formulation for ATR-based initial stop loss, take profit, trailing ratchet stop, max holding duration ($M_{\max}$), daily loss circuit breakers, consecutive loss cooldowns, leverage caps ($L_{\max} \le 5.0$), gap-through fills, and same-candle collision resolution.
   - Comprehensive worked examples and breakdown of simulator guarantees vs broker reality.
2. **Acceptance Test Matrix**: [`acceptance_test_matrix.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/acceptance_test_matrix.md)
   - 15 deterministic acceptance test cases (TC-RISK-01 through TC-RISK-15) covering normal execution, intrabar stops, opening gap penetrations, collision precedence, EOD liquidation, session boundary purges, cooldown triggers, missing data handling, and deterministic replay exactness.
3. **Unresolved Decisions and Pre-Registration Register**: [`unresolved_decisions_register.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/unresolved_decisions_register.md)
   - Documents all unestablished parameters ($k_{\text{stop}}$, $k_{\text{target}}$, $k_{\text{trail}}$, $M_{\max}$, $T_{\text{open\_filter}}$, $\theta_{\text{day}}$, $N_{\text{streak}}$, cost models) as open research decisions requiring pre-registration before empirical testing.

---

## 3. Delineation: Confirmed Defects vs. Proposed Design Choices

To prevent cognitive bias, the table below explicitly separates **empirically proven failure mechanisms** from **proposed engineering solutions**:

| Domain | Confirmed Defect from Phase 24G.9 | Proposed Design Choice in Phase 24G.10 Specification |
| :--- | :--- | :--- |
| **Trade Holding & Exit** | **Confirmed Defect**: 97.74% of all trades drifted passively until 15:29:00 EOD forced liquidation; mean holding duration was 258.3 minutes. | **Design Choice**: Introduce ATR-based initial stop loss ($k_{\text{stop}}$) and maximum holding time limit ($M_{\max}$ bars) to enforce active trade management. |
| **Morning Noise Vulnerability**| **Confirmed Defect**: 62.95% of trades entered between 09:15 and 11:00 AM, generating 90.22% of all cumulative losses (-Rs 256.75). | **Design Choice**: Formulate candidate morning entry blackout window ($T_{\text{open\_filter}}$) to be evaluated via pre-registered experiment. |
| **Severe Volatility Drawdown** | **Confirmed Defect**: March–May 2020 volatility caused an 8-trade losing streak and expanded max drawdown to Rs 159.30 (3.6x 2019 validation drawdown). | **Design Choice**: Introduce daily loss circuit breaker ($\theta_{\text{day}} = 2.0\%$) and consecutive loss cooldown ($N_{\text{streak}} = 3$) to prevent cluster compounding. |
| **Underlying Edge** | **Confirmed Defect**: SignalForge V1 has negative gross alpha across 2017–2020 (-Rs 229.40 at 0 bps transaction fees). | **Engineering Reality**: Risk controls cannot turn negative alpha positive. Any future V2 candidate requires signal logic revision before deployment consideration. |

---

## 4. Acceptance Test Implementation

An automated test suite was constructed in [`tests/test_risk_and_exit_engine_spec.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_risk_and_exit_engine_spec.py) implementing the mathematical formulas and boundary checks defined in the specification.

### Verified Test Cases
1. `test_position_sizing_respects_risk_budget`: Confirms quantity clamps monetary risk to $\le R_{\text{trade}}$.
2. `test_position_sizing_respects_leverage_cap`: Confirms notional exposure never exceeds $C \cdot L_{\max}$.
3. `test_gap_through_stop_uses_open_price`: Confirms exit price reflects opening gap, not nominal stop.
4. `test_same_candle_collision_stop_first_precedence`: Confirms conservative stop-first resolution.
5. `test_trailing_stop_ratchet_monotonicity`: Confirms stop price never loosens on adverse pullback.
6. `test_daily_loss_circuit_breaker_calculation`: Confirms circuit breaker trip on cumulative realized + unrealized loss.

All unit and regression tests pass with zero warnings or errors.

---

## 5. Research Gate Decision & Governance

```
========================================================================================
RESEARCH GATE STATUS: SPECIFICATION COMPLETE (NO STRATEGY MODIFICATION)
========================================================================================
1. Risk and Exit Engine Specification (V2) is formally approved for design and testing.
2. SignalForge V1 frozen strategy configuration and hash remain UNCHANGED.
3. ADANIPORTS qualification remains NOT_TESTED.
4. ADANIENT qualification remains VERIFICATION_REQUIRED and BLOCKED.
5. NO paper-trading or live-money trading authorized.
========================================================================================
```

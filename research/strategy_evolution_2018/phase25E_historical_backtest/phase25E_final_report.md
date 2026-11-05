# SignalForge Phase 25E — Final Historical Tenure-Bounded Backtest Report

**Date:** 2026-11-05  
**Status:** **`PHASE_25E_COMPLETE`**  
**Budget Expenditure:** ₹0.00 (100% compliant)  
**Strategy Config SHA-256:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`  
**Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`  
**Canonical NIFTY 50 SHA-256:** `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a`  

---

## 1. Executive Summary

Phase 25E successfully executed the frozen SignalForge V1 strategy across **all 38 eligible historical constituents** of the NIFTY 50 for 2017–2019, strictly enforcing each company's exact index membership tenure dates, with complete Indian equity intraday transaction friction.

### Primary Audit Conclusions:
1. **Execution Scope:** Exactly **38 stocks attempted** and **38 stocks successfully backtested** (0 blocked). 23 historical constituents remain blocked by insufficient data in the upstream archive.
2. **Zero Positive Research Results:** Under realistic discount-broker friction (Model B: ~5.66 bps round-trip), **0 of 38 stocks (0.0%)** sustained positive net returns across both Training and Validation partitions.
   - **`NEGATIVE_RESEARCH_RESULT`:** **31 stocks (81.6%)**.
   - **`STATISTICALLY_INCONCLUSIVE`:** **4 stocks (10.5%)** (`EICHERMOT`, `MARUTI`).
   - **`INSUFFICIENT_SAMPLE`:** **3 stocks (7.9%)** (`BHEL`, `IDEA` due to 3-month membership tenure; N < 100 trades).
3. **Shared-Capital Portfolio Breakdown:** In the realistic ₹10 Lakh portfolio (10 concurrent positions, ₹100k per trade):
   - **Final Equity:** ₹285,174.66 (**Net P&L: ₹-714,825.34**, -71.48% return).
   - **Total Transaction Friction Paid:** ₹459,066.11 (Brokerage: ₹162,960.00, STT: ₹101,173.21, GST: ₹34,214.90, etc.).
   - **Signal Rejection Rate:** **78.2%** (14612 of 18686 signals rejected due to capacity limits).
4. **Tenure Bounding Impact:** Pruning non-tenure trades eliminated look-ahead bias across all 11 tenure-restricted stocks. For example, BHEL was restricted to 41 legitimate index trades (filtering out 544 post-exit trades).

---

## 2. Deliverables Inventory

| File Path | Description |
| :--- | :--- |
| `phase25E_38stock_individual_results.csv` | Full metrics for all 38 historical stocks across Models A, B, and C |
| `phase25E_training_and_validation_results.csv` | Detailed breakdown comparing Training (2017–2018) vs Validation (2019) |
| `phase25E_membership_window_execution_audit.md` | Verification of exact tenure windows and non-tenure trade pruning |
| `phase25E_fee_cost_breakdown.csv` | Granular statutory and commercial fee accounting per stock |
| `phase25E_shared_capital_portfolio_report.md` | Re-simulation of ₹10 Lakh portfolio across all 38 stocks |
| `phase25E_performance_ranking.md` | Complete stock ranking sorted by Model B net P&L |
| `phase25E_statistical_robustness_report.md` | Regime decay, Wilson confidence intervals, and classification audit |
| `phase25E_results_manifest.json` | Machine-readable results manifest with bit-for-bit provenance |
| `phase25E_38stock_raw_trades_cache.json` | Bit-exact cache of all raw trades across all 38 historical stocks |
| `phase25E_final_report.md` | Comprehensive milestone audit report |
| `tests/test_phase25E_historical_backtest.py` | Automated test suite validating all Phase 25E contracts |

---

## 3. Governance & Safe Trading Protocol

- **Research Budget:** ₹0.00 spent.
- **Invariants Intact:** Frozen V1 configuration, canonical datasets, paper ledger, and universe registry remain unchanged.
- **Derivatives & Live Deployment:** NIFTY Futures and Options remain in separate blocked track (`BLOCKED_NO_DATA`). Live and paper trading deployment remains strictly **`ON_HOLD`**.

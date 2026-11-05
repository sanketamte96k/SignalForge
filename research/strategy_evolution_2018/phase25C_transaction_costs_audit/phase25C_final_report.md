# SignalForge Phase 25C — Final Transaction Cost & Integrity Audit Report

**Date:** 2026-11-05  
**Status:** **`PHASE_25C_COMPLETE`**  
**Budget Expenditure:** ₹0.00 (100% compliant)  
**Strategy Config SHA-256:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`  
**Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`  
**Canonical NIFTY 50 SHA-256:** `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a`  

---

## 1. Executive Summary

Phase 25C reassessed the 34-stock cross-asset results from Phase 25B using **complete, realistic Indian equity intraday transaction costs** rather than optimistic flat rates.

### Primary Audit Conclusions
1. **Fee Erosion & Unprofitability:**  
   Under realistic discount-broker friction (Model B: ~5.66 bps round-trip including brokerage, STT, exchange fees, SEBI charges, stamp duty, GST, slippage, and spread), the frozen V1 strategy is **systematically unprofitable** across the broad NIFTY 50 universe.
   - **32 of 34 stocks** generated negative net P&L.
   - Only **0 stocks** retained positive returns across both Training and Validation.
2. **Shared-Capital Portfolio Drawdown:**  
   In the realistic ₹10 Lakh portfolio (10 concurrent positions, ₹100k per trade), **12477 of 19223 signals (64.9%)** were rejected due to capacity limits. The realized portfolio closed with a net P&L of **₹-16,303.14 (-1.63% return)** with total friction costs reaching **₹12,982.29**.
3. **Survivorship Bias Confirmed:**  
   **5 of the 34 stocks** were never members of the NIFTY 50 during 2017–2019, and **7 stocks** were added mid-period. Modern constituent lists upwardly bias historical sample liquidity and momentum while omitting severely distressed historical members.

---

## 2. Deliverables Inventory

| File Path | Description |
| :--- | :--- |
| `phase25C_34stock_brokerage_inclusive_results.csv` | Comprehensive results for all 34 stocks across 3 cost models |
| `phase25C_stock_cost_breakdown.csv` | Granular per-stock accounting of every single statutory & commercial fee |
| `phase25C_cost_model_specification.md` | Formal specification of Indian equity intraday tax & fee structures |
| `phase25C_survivorship_bias_audit.md` | Audit of 2017–2019 historical index reconstitution vs modern constituent list |
| `phase25C_shared_portfolio_report.md` | Re-simulation of ₹10 Lakh shared portfolio under complete friction |
| `phase25C_statistical_validation_report.md` | Statistical validation, flipped-trade analysis, and friction sensitivity |
| `phase25C_results_manifest.json` | Complete machine-readable results manifest with bit-for-bit provenance |
| `phase25C_final_report.md` | Milestone audit synthesis |
| `tests/test_phase25C_transaction_costs_audit.py` | Automated test suite validating cost formulas, invariants, and portfolio metrics |

---

## 3. Governance & Safe Trading Protocol

- **Research Budget:** ₹0.00 spent.
- **Invariants Intact:** Frozen V1 configuration, canonical datasets, paper ledger, and universe registry remain unchanged.
- **Derivatives & Live Deployment:** NIFTY Futures and Options remain in separate blocked track (`BLOCKED_NO_DATA`). Live and paper trading deployment remains strictly **`ON_HOLD`**.

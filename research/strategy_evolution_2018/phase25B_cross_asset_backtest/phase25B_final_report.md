# SignalForge Phase 25B — Final Cross-Asset Backtest Report

**Date:** 2026-11-05  
**Status:** **`PHASE_25B_COMPLETE`**  
**Budget Expenditure:** ₹0.00 (100% compliant)  
**Strategy Config SHA-256:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`  
**Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`  
**Canonical NIFTY 50 SHA-256:** `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a`  

---

## 1. Executive Summary

Phase 25B executed the frozen SignalForge V1 intraday strategy (`VARIANT_C_ONE_TRADE_PER_SYMBOL_PER_DAY`) across all **34 eligible NIFTY 50 constituent equities** across the approved **2017–2019 historical development (Training) and generalization (Validation) partitions**.

- **Universe Attempted:** 34 stocks (all stocks with local 1-minute historical data).
- **Successfully Evaluated:** **34 of 34 stocks** (100% of eligible universe).
- **Blocked / Ineligible:** 0 stocks blocked among eligible; 16 stocks lack local 1m data (cataloged in Phase 25A).
- **Quarantine Adherence:** 2020 Holdout Partition strictly quarantined (`CONTAMINATED / ZERO ACCESS`).
- **Derivatives Track:** NIFTY Futures and Options remain in separate blocked track (`BLOCKED_NO_DATA`).
- **Deployment Status:** **`ON_HOLD`** pending user review and forward verification.

---

## 2. Research Results Overview

### Classification Breakdown
- **Positive Research Result:** **3 stocks**
- **Negative Research Result:** **24 stocks**
- **Statistically Inconclusive:** **7 stocks**
- **Insufficient Sample:** **0 stocks**

### Shared Portfolio Performance (10 Concurrent Slots, ₹1M Starting Capital)
- **Net Portfolio P&L:** **₹-3,924.40**
- **Portfolio Return:** **-0.39%**
- **Max Portfolio Drawdown:** **₹5,542.78 (0.55%)**
- **Accepted Realized Trades:** **7087**
- **Rejected Trades (Capacity Exhaustion):** **12136 (63.1%)**

---

## 3. Deliverables Inventory

| Deliverable File | Description |
| :--- | :--- |
| `phase25B_34stock_individual_results.csv` | Full metric suite for all 34 individual stocks over combined 2017–2019 |
| `phase25B_training_results_2017_2018.csv` | In-sample performance metrics for 2017–2018 |
| `phase25B_validation_results_2019.csv` | Out-of-sample performance metrics for 2019 |
| `phase25B_combined_portfolio_report.md` | Shared-capital simulation, concurrency limits, and rejection analysis |
| `phase25B_stock_performance_ranking.md` | Complete stock leaderboard and directional asymmetry analysis |
| `phase25B_data_quality_exceptions.md` | OHLC audit, duplicate checks, and corporate action adjustments |
| `phase25B_statistical_validation_report.md` | Wilson CIs, binomial p-values, cost sensitivity, and alpha decay |
| `phase25B_results_manifest.json` | Complete machine-readable results manifest with data provenance |
| `phase25B_final_report.md` | Comprehensive milestone audit report |

---

## 4. Governance & Safety Attestation

- **₹0 Budget Maintained:** Zero external network calls, zero broker account creation, zero paid feeds.
- **Invariant Integrity:** Frozen V1 configuration, canonical ADANIPORTS, canonical NIFTY 50, and paper ledger preserved bit-for-bit.
- **Honest Scoping:** Exactly 34 stocks evaluated; no claim of 50-stock completeness or live trading readiness.

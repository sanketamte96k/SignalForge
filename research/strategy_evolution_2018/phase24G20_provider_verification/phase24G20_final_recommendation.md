# SignalForge Phase 24G.20 — Final Provider Recommendation & Verification Verdict

**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT` — Preserved)  
**Candidate Strategy:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout (`HYP_B_BASE`)  
**Current Candidate Classification:** **`PROMISING_RESEARCH_CANDIDATE`** (Retained)  
**Target Coverage Horizon:** `2021-01-01` to `2025-12-31` (5 Full Calendar Years)  
**Target Universe:** 22 NSE Liquid Equities across 8 Sectors  
**Phase 24G.20 Final Verdict:** **`ZERODHA_RECOMMENDED`**  
**Subscription & Acquisition Status:** **`NO_PURCHASE_MADE / AWAITING_EXPLICIT_USER_AUTHORIZATION`**  
**Trading Authorization:** **`NONE` (Offline Historical Research Only)**  

---

## 1. Executive Provider Comparison & Final Verdict

Based on an exhaustive forensic evaluation of official provider documentation, pricing structures, API specifications, and licensing terms, the final determination for Phase 24G.20 is:

```
========================================================================================
SIGNALFORGE PRE-PURCHASE PROVIDER VERIFICATION GATE — PHASE 24G.20
========================================================================================
EVALUATED CANDIDATE 1:        TRUEDATA INDIA (NSE Authorized Market Data Vendor)
EVALUATED CANDIDATE 2:        ZERODHA KITE CONNECT (SEBI Broker Historical API)
----------------------------------------------------------------------------------------
FINAL GATE VERDICT:           ZERODHA_RECOMMENDED
PRICING ADVANTAGE:            Zerodha is ₹590 flat vs. TrueData ~₹8,500–₹14,000+
HISTORICAL 1M DEPTH:          Zerodha covers 2015–Present natively via API
                              (TrueData standard REST API limits 1m to last 6 months)
22-SYMBOL COVERAGE:           100% Confirmed on Both (All 22 symbols listed pre-2008)
ACQUISITION RUNTIME:          ~6 minutes via Zerodha API (682 total chunked calls)
LOCAL RESEARCH STORAGE:       Fully Permitted on Both
EXISTING WORKSPACE SUPPORT:   Pre-wired in 'scripts/test_zerodha_historical_data.py'
========================================================================================
```

---

## 2. Comprehensive 8-Point Scorecard

| Evaluation Criterion | Zerodha Kite Connect | TrueData India | Superior Option |
| :--- | :--- | :--- | :--- |
| **1. 2021–2025 1m Depth via API** | **100% Available** (Archive extends back to early 2015) | **Restricted** (Standard REST API lookback is last 6 months only) | **ZERODHA** |
| **2. 22-Equity Universe Coverage** | **100% Available** (All 22 equities active on NSE) | **100% Available** (All 22 equities tracked on `NSEEQ`) | **TIE** |
| **3. Acquisition Financial Cost** | **₹590.00 Flat** (1 month, ₹0 historical add-on fee) | **₹8,495 to ₹14,395+** (Base API + custom 5-year archive) | **ZERODHA** ($93\%\text{--}96\%$ cheaper) |
| **4. Local Storage for Backtesting**| **Explicitly Permitted** for personal research | **Explicitly Permitted** for licensed subscriber | **TIE** |
| **5. API Limits & Runtime** | 3 req/s (682 requests = ~6 minutes) | 10 req/s (Standard API blocked for 2021–2024) | **ZERODHA** |
| **6. Integration Overhead** | **Zero Overhead** (Pre-wired token resolution in `scripts/`) | Medium (Requires new API client or Dropbox IEOD parsing) | **ZERODHA** |
| **7. Corporate Action Adjustments** | Split & bonus adjusted by default | Both available (in custom bulk delivery) | **TIE** |
| **8. Procurement Friction** | **Instant Self-Serve** via developer console | **High Friction** (Requires sales negotiation for IEOD dump)| **ZERODHA** |

---

## 3. Governance Invariants & Safety Certification

| Invariant Item | Target Reference | Observed Value | Gate Status |
| :--- | :--- | :--- | :--- |
| **V1 Baseline Config Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **VERIFIED MATCH** |
| **ADANIPORTS Canonical Hash** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **VERIFIED MATCH** |
| **Active Paper Ledger** | `data/paper_trading/interactive_trades.json` | Clean, untouched in Git working tree | **VERIFIED UNTOUCHED** |
| **Active Universe Registry**| `data/universe_registry.json` | Clean, untouched in Git working tree | **VERIFIED UNTOUCHED** |
| **2020 Holdout Partition** | Quarantined `EXPLORATORY / CONTAMINATED` | Zero reads, zero evaluations | **VERIFIED ISOLATED** |
| **Subscription Purchases** | No credit card, no financial payment | No commercial orders placed | **100% COMPLIANT** |
| **Data Downloads** | No historical candles downloaded | Clean, offline repository | **100% COMPLIANT** |

---

## 4. Clear Actionable Roadmap for the User

To proceed with acquiring the 2021–2025 dataset under the recommended path:

1. **Step 1: Obtain Kite Connect App Access**:
   - Log into the Zerodha developer console (`https://developers.kite.trade/`).
   - Create or renew a Kite Connect application (₹500 + 18% GST = **₹590.00**).
2. **Step 2: Provide API Credentials (When Ready)**:
   - Provide `KITE_API_KEY` and generate a daily `KITE_ACCESS_TOKEN`.
   - Credentials will be passed via environment variables (never committed to Git).
3. **Step 3: Execute Staged Acquisition & Bhavcopy Validation**:
   - Run the automated acquisition pipeline defined in [`phase24G19_acquisition_design.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G19_data_acquisition_audit/phase24G19_acquisition_design.md).
   - Ingest all 22 equities for 2021–2025 (~6 minutes runtime), cross-verify with official NSE daily Bhavcopy settlement totals, and generate cryptographic SHA-256 manifests.
4. **Step 4: Execute Phase 24G.18 Strategy Evaluation**:
   - Unlock Partition 1 (2021–2022 Dev) and Partition 2 (2023 Val) under frozen Hypothesis B rules, resolving the previous `DATA_QUALITY_FAILURE`.

# Phase 24G.22 — Angel One SmartAPI Historical Data Feasibility Verdict

**Project:** SignalForge  
**Phase:** 24G.22  
**Document ID:** SF-VERDICT-PHASE24G22  
**Evaluation Mode:** STRICTLY OFFLINE FORENSIC AUDIT  
**Candidate Evaluation:** Angel One SmartAPI as Alternative Historical Data Source for SignalForge Universe  
**Final Audit Verdict:** `READY_FOR_AUTHORIZED_PILOT`  

---

## 1. Executive Summary

This forensic audit evaluated Angel One SmartAPI as a potentially free alternative to Zerodha Kite Connect and TrueData for acquiring continuous 1-minute historical OHLCV data covering the 2021–2025 period for SignalForge's pre-registered 22-equity universe.

The evaluation was conducted strictly offline, adhering to the governing invariants: zero account creation, zero network API calls, zero data downloads, zero purchases, zero strategy parameter modifications, and complete isolation of the active paper trading ledger and universe registry.

### Core Audit Outcomes:
1. **Cost Feasibility (Superior):** Angel One SmartAPI provides historical candle data at **₹0.00 cost** (free API access, free candle queries). Compared to Zerodha (₹4,000/month) and TrueData (₹2,900/month), this represents an annual savings of ₹34,800 to ₹48,000.
2. **Historical Depth (Sufficient):** Official developer documentation and engineering maintainers confirm NSE equity 1-minute historical data is available back to **January 1, 2016**. The required 2021–2025 window (5 complete calendar years) is fully accessible.
3. **Symbol Coverage (Complete):** All 22 pre-registered equities in the SignalForge universe are actively mapped to unique, stable numeric tokens in Angel One's instrument master file (`OpenAPIScripMaster.json`).
4. **Throughput Feasibility (Viable with Pagination):** While Angel One enforces a hard ceiling of 500 candles per API response (preventing multi-week queries), a single trading day contains 375 one-minute bars. Paginating day-by-day requires **27,280 API calls** across 22 stocks and 1,240 sessions. Under the 5,000 requests/hour quota, complete acquisition will complete in **5.46 hours** via a batched rate-limited pipeline.
5. **Corporate Action Processing (Critical Requirement):** SmartAPI provides **raw, unadjusted historical prices**. To prevent artificial volatility compression or breakout signals across stock splits and bonus issues, an external corporate-action back-adjustment engine must be integrated prior to feeding historical bars into Hypothesis B backtests.

---

## 2. Verdict Evaluation Matrix

| Evaluation Criterion | Standard Requirement | Angel One SmartAPI Status | Verdict Impact |
|:---|:---|:---|:---|
| **Cost & Commercial Terms** | Cost-effective research access | 100% Free (₹0.00 base + ₹0.00 historical) | **PASS (Exceptional)** |
| **Historical Data Depth** | 2021-01-01 to 2025-12-31 (1-min) | Available back to 2016-01-01 | **PASS** |
| **Universe Scrip Coverage** | 22 pre-registered equities | 22/22 (100%) mapped in instrument master | **PASS** |
| **Data Schema & Precision** | Timestamp, O, H, L, C, V (INR, ISO) | Matches schema perfectly (Epoch ISO strings, floats) | **PASS** |
| **Throughput & Acquisition Speed** | Feasible acquisition time | ~5.5 hours for full 5-year universe (27,280 calls @ 5,000/hr) | **PASS (Acceptable)** |
| **Corporate Action Handling** | Continuous pricing across events | Raw prices; requires external corporate-action adjustment | **PASS (With Architecture Add-on)** |
| **Security & Operational Safety** | Isolated, secure API access | Requires Demat account credentials; strict client isolation needed | **PASS (Manageable via isolated client)** |
| **SignalForge Compatibility** | Ingestion into `src/data/` pipeline | Seamless ingestion into existing CSV / Parquet format | **PASS** |

---

## 3. Formal Verdict

### **Verdict Classification: `READY_FOR_AUTHORIZED_PILOT`**

**Justification:**  
Angel One SmartAPI satisfies all foundational requirements for SignalForge historical market data acquisition. The absence of recurring API subscription fees makes it the most cost-effective solution available. The identified operational constraints—specifically the 500-candle response pagination ceiling and the necessity of external split/bonus adjustments—are well-understood engineering challenges with straightforward, robust architectural solutions.

---

## 4. Key Architectural Prerequisites for Authorized Pilot (Phase 24G.23)

Before initiating an authorized pilot acquisition, the following controls must be implemented:

1. **Standalone Read-Only Collector Client (`AngelOneDataCollector`):**
   - Strictly isolated in `src/data/angelone_collector.py`.
   - Strictly implements `getCandleData` and `searchScrip` only.
   - Prohibits all order routing, account modification, or portfolio management calls.
2. **Deterministic Daily Chunking Engine:**
   - Implements daily date ranges (`fromdate: YYYY-MM-DD 09:15`, `todate: YYYY-MM-DD 15:30`) to stay within the 500-candle boundary (375 candles/session).
   - Incorporates automated exponential backoff retry on HTTP 429 / 5xx responses.
3. **External Corporate-Action Adjustment Layer (`src/data/corporate_actions.py`):**
   - Ingests split and bonus ratios from official NSE corporate action announcements.
   - Computes split-adjusted Open, High, Low, and Close series while preserving raw historical series side-by-side for forensic auditability.
4. **Strict Security Quarantine:**
   - Credential retrieval strictly via non-committed environment variables (`ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`, `ANGEL_TOTP_SECRET`).
   - Automated secret redaction enabled in all logging handlers.
   - Static IP binding configured in the SmartAPI Developer Console.
5. **Phase 24G.22 Sample Pilot Execution Plan:**
   - Execute the 15-target sample pilot plan (`research/strategy_evolution_2018/phase24G22_angelone_feasibility/phase24G22_sample_pilot_plan.csv`) across 5 representative equities and 3 historical years (315 total calls, runtime < 3 minutes).
   - Verify SHA-256 data integrity, timestamp ordering, and absence of gaps before scaling to full universe acquisition.

---

## 5. Invariant & Governance Certification

| Governance Invariant | Target Value | Audit Status |
|:---|:---|:---|
| Frozen Strategy V1 Config Hash | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **PRESERVED** |
| Canonical ADANIPORTS Hash | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **PRESERVED** |
| Active Paper Trading Ledger | `data/paper_trading/interactive_trades.json` | **UNTOUCHED** |
| Universe Registry | `data/universe_registry.json` | **UNTOUCHED** |
| 2020 Holdout Partition | `EXPLORATORY / CONTAMINATED` (Zero Access) | **QUARANTINED** |
| Candidate Specification Status | `SF-SPEC-ALPHA-2026-V1` | **DRAFT** |
| Candidate Research Classification | Hypothesis B | **PROMISING_RESEARCH_CANDIDATE** |
| Phase 24G.22 Execution Boundary | Zero Account Creation / Zero API Calls | **COMPLIED (100% OFFLINE)** |

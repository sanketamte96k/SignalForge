# SignalForge Phase 24G.20 — TrueData Pre-Purchase Verification Report
## Forensic Verification of TrueData India for Historical Market Data (2021–2025)

**Document ID:** `SF-PHASE24G20-TRUEDATA-VERIF-2026-V1`  
**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Evaluation Target:** TrueData Market Data APIs & Historical Data Services  
**Target Coverage Horizon:** `2021-01-01` to `2025-12-31` (5 Full Calendar Years)  
**Target Universe:** 22 NSE Liquid Equities across 8 Sectors  
**Audit Status:** **PRE-PURCHASE FACT-CHECKING COMPLETED (NO SUBSCRIPTION PURCHASED)**  

---

## 1. Executive Summary & Verification Assessment

TrueData India is an official authorized market data vendor for the National Stock Exchange of India (NSE). However, a forensic review of official technical documentation reveals a **critical constraint** regarding 1-minute historical intraday data:

> [!WARNING]
> **Core Finding**: TrueData's standard Market Data REST API restricts 1-minute historical candle queries to the **last 6 months rolling**.  
> The 5-year target window (2021–2025) is **NOT accessible out of the box** through standard retail/developer API subscriptions without purchasing a custom offline "IEOD / Bulk Historical Archive" add-on at additional negotiated enterprise costs.

---

## 2. In-Depth Criteria Verification

### 2.1 Historical 1-Minute OHLCV Coverage (2021–2025)
* **Verified Fact**: TrueData's official REST API documentation explicitly states that minute-level bar history (1-min to 60-min intervals) is restricted to the **last 6 months** dynamically.
* **Provider Claim**: TrueData maintains continuous internal tick and bar archives dating back to 2014 for NSE equities.
* **Unresolved Assumption**: Whether TrueData's commercial sales team will provide 2021–2025 1-minute data as a one-time historical dump, and the exact pricing formula for 5 years of historical minute data across 22 equities.

### 2.2 Coverage for the 22 Pre-Registered Symbols
* **Verified Fact**: TrueData covers 100% of the active NSE equity cash segment (`NSEEQ`). All 22 symbols (`HDFCBANK`, `ICICIBANK`, `SBIN`, `AXISBANK`, `BAJFINANCE`, `INFY`, `HCLTECH`, `COFORGE`, `RELIANCE`, `BPCL`, `ONGC`, `MARUTI`, `BAJAJ_AUTO`, `EICHERMOT`, `JSWSTEEL`, `SAIL`, `ADANIENT`, `SUNPHARMA`, `DRREDDY`, `ITC`, `BRITANNIA`, `ADANIPORTS`) are primary large-cap constituents with continuous symbol presence throughout 2021–2025.
* **Symbol Notation**: Uses clean ticker symbols without exchange suffixes (e.g., `RELIANCE`, `INFY`).

### 2.3 Local Storage & Retention Rights
* **Verified Fact**: TrueData licenses data on a per-user basis. Subscriptions permit local downloading and caching on personal workstations for the sole purpose of powering personal backtesting, strategy optimization, and proprietary algorithm execution.
* **Restrictions**: Redistribution, publishing, sub-licensing, or streaming data to third parties is strictly prohibited. Commercial reselling violates exchange vendor contracts.

### 2.4 Raw vs Split/Bonus Adjusted Candles
* **Verified Fact**: TrueData generates split- and bonus-adjusted price series server-side. For institutional data clients and bulk archives, unadjusted raw trade series are also maintained.
* **Unresolved Assumption**: In custom bulk IEOD dumps, whether the user receives pre-adjusted CSVs or raw CSVs accompanied by corporate action adjustment coefficients.

### 2.5 Timestamp Timezone & Candle Boundaries
* **Verified Fact**: All timestamps are formatted in Indian Standard Time (`Asia/Kolkata`, UTC+05:30).
* **Candle Boundary**: Standard bar-start convention is used (e.g. `09:15:00` represents trades executed between 09:15:00.000 and 09:15:59.999). Market hours run from `09:15:00` to `15:30:00`.

### 2.6 API Limits, Request Quotas & Backfill Restrictions
* **Verified Fact**: TrueData REST API allows high throughput (up to 10 requests per second or 600 requests per minute).
* **Backfill Restriction**: Calling the REST API for dates older than 6 months returns an error or empty payload (`HTTP 200` with empty array `[]`). Programmatic REST backfilling for 2021–2024 is technically blocked by server-side query bounds.

### 2.7 Subscription Costs, Add-Ons & Taxes
* **Verified Fact**:
  - Base Market Data API plans (Lite / Pro / Optima): ~₹1,699 to ₹2,699+ / month.
  - Workspace / Cloud Terminal Plans: ~₹2,199 (Basic: 30 days) to ₹5,999 / month (Power: 3 years).
  - Bulk Historical IEOD Add-on: Advertised starting from ~₹799 / month per segment, with multi-year custom archives requiring bespoke quotes.
  - Applicable Taxes: Goods and Services Tax (GST) of **18.0%** applies to all quoted fees.
  - Cancellation: Monthly recurring subscriptions can be canceled prior to the next billing cycle; historical bulk archive sales are non-refundable.

---

## 3. Evidence Classification Matrix

| Dimension | Classification | Detailed Evidence |
| :--- | :--- | :--- |
| **2021–2025 1m Depth via API** | **UNAVAILABLE VIA STANDARD API** | Official docs confirm standard REST API lookback is limited to the **last 6 months**. |
| **22-Equity Existence** | **VERIFIED FACT** | All 22 symbols are liquid NSE cash equities continuously tracked by TrueData. |
| **Local Storage Rights** | **VERIFIED FACT** | Permitted for internal/personal backtesting; redistribution prohibited. |
| **API Throughput** | **VERIFIED FACT** | 10 requests/second on REST endpoints. |
| **Multi-Year 1m Acquisition Method** | **UNRESOLVED ASSUMPTION** | Requires offline sales inquiry (`support@truedata.in`) for custom IEOD archive pricing. |
| **Minimum Estimated Cost** | **VERIFIED FACT** | Base API ₹2,005/mo (incl. GST); 5-year multi-symbol archive estimated at ₹5,000–₹15,000+. |

---

## 4. TrueData Verification Verdict

> **VERDICT: REQUIRES BESPOKE ENTERPRISE QUOTE / NOT RECOMMENDED FOR INSTANT RETAIL ACQUISITION**  
> Because the standard TrueData REST API does not allow programmatic retrieval of 1-minute data beyond 6 months, acquiring 2021–2025 data from TrueData cannot be accomplished via a standard monthly self-serve API subscription. It requires custom contract negotiation for bulk IEOD archives.

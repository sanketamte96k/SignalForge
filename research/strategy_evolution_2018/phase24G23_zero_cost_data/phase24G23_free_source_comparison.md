# Phase 24G.23 — Zero-Cost Historical Data Source Comparison

**Project:** SignalForge  
**Phase:** 24G.23  
**Document ID:** SF-PHASE24G23-SOURCE-COMP-2026-V1  
**Target Universe:** 22 Pre-Registered Equities (NSE Cash)  
**Required Frequency:** 1-Minute OHLCV (Continuous Trading Sessions)  
**Required Historical Period:** 2021-01-01 through 2025-12-31 (5 Calendar Years)  
**Budgetary Constraint:** STRICTLY ₹0.00 (Zero Payments, Zero Accounts, Zero Trial Cards)  

---

## 1. Executive Summary & Evaluation Framework

To determine whether SignalForge's multi-year out-of-sample research can proceed without subscription expenditures, this forensic audit evaluated all recognized zero-cost public and developer data sources. 

Each candidate source was analyzed against empirical data criteria:
- **Cost & Budget:** Direct subscription, data add-on, or hidden fees.
- **Registration Requirements:** Account creation, KYC, demat opening, credit cards, or API key generation.
- **Historical Depth & Interval:** Maximum historical lookback at native 1-minute resolution.
- **Coverage of Universe:** Availability across the 22 pre-registered NSE equities.
- **Data Quality & Continuity:** Missing bars, weekend/holiday filtering, session integrity (09:15–15:30 IST).
- **Corporate Action Handling:** Raw nominal prices versus split/bonus-adjusted series.
- **Licensing & Legal Provenance:** Exchange compliance (NSE Data & Analytics regulations), redistribution rights, and personal research permissibility.
- **Governance Classification:** Assigned strictly according to Phase 24G.23 taxonomy:
  - `FREE_AND_USABLE`
  - `FREE_BUT_INSUFFICIENT_COVERAGE`
  - `REGISTRATION_REQUIRED`
  - `PAID`
  - `LICENSE_RESTRICTED`
  - `UNVERIFIED`

---

## 2. Detailed Candidate Source Evaluations

### 2.1 SignalForge Local Historical Archive (`data/historical/stocks/`)
- **Cost:** ₹0.00 (Pre-existing on-disk assets).
- **Registration Requirements:** None (Locally accessible).
- **Earliest Historical Date:** 2017-01-02 09:15:00 IST.
- **Latest Historical Date:** 2021-01-01 15:29:00 IST.
- **Interval:** 1-minute OHLCV.
- **Stock Coverage:** Exactly 5 stocks (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`). Missing 17 stocks.
- **2021–2025 Coverage:** **375 bars total** (1 single day: 2021-01-01). **0 bars for 2022–2025**.
- **Missing-Data Risk:** Very low for 2017–2020 (<140 gap minutes across 4 years); absolute 100% missing data for 2021–2025.
- **Corporate Action Handling:** Raw nominal prices (e.g., ADANIENT demerger on 2018-09-06 shows -28.7% nominal drop).
- **License / Provenance:** Retained from historical research archives; verified deterministic SHA-256 manifests.
- **Classification:** **`FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Perfect 1-minute quality for 2017–2020, but completely exhausted for the 2021–2025 out-of-sample window (0% coverage for 2022–2025; 17 stocks missing).

---

### 2.2 Public GitHub Repository: `ShabbirHasan1/NSE-Data`
- **Cost:** ₹0.00.
- **Registration Requirements:** None (Public Git repository / direct raw download).
- **Earliest Historical Date:** 2017-01-01.
- **Latest Historical Date:** 2020-12-31.
- **Interval:** 1-minute OHLCV.
- **Stock Coverage:** Nifty 50 stocks + Next 100 Midcaps.
- **2021–2025 Coverage:** **0% (Repository historical minute collection terminated on 2020-12-31)**.
- **Missing-Data Risk:** Low for 2017–2020; total for 2021–2025.
- **Corporate Action Handling:** Raw unadjusted candles.
- **License / Provenance:** MIT License / Open-source repo; sourced via broker API (Alice Blue).
- **Classification:** **`FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Identical historical span to SignalForge local archive (terminates at end of 2020). Zero 2021–2025 1-minute stock data.

---

### 2.3 Public GitHub Repository: `technovusin/nifty50-historical-data`
- **Cost:** ₹0.00.
- **Registration Requirements:** None (Public Git repository / Parquet releases).
- **Earliest Historical Date:** 2015-01-01.
- **Latest Historical Date:** 2025-12-31 (Regularly updated).
- **Interval:** 1-minute and 15-second OHLC.
- **Stock Coverage:** **0 Equities (Index-Only: NIFTY 50 and SENSEX)**.
- **2021–2025 Coverage:** 100% for the Index, but **0% for individual stocks**.
- **Missing-Data Risk:** Cleaned index series, but contains **no volume** and no individual scrips.
- **Corporate Action Handling:** N/A (Index values).
- **License / Provenance:** Open-source research archive.
- **Classification:** **`FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Contains only macro benchmark index data (`NIFTY50_INDEX`); cannot test single-stock volatility compression breakouts on equities.

---

### 2.4 Kaggle Public Datasets (e.g., `nifty50_1min_data`, `maverick136`)
- **Cost:** ₹0.00 direct monetary cost.
- **Registration Requirements:** **Mandatory Kaggle account registration** and API key generation (`kaggle.json`) or interactive login.
- **Earliest Historical Date:** Varies (2015 or 2021).
- **Latest Historical Date:** Varies (2022 to 2025).
- **Interval:** 1-minute OHLCV.
- **Stock Coverage:** Claims 50 stocks.
- **2021–2025 Coverage:** Unverified and fragmented across multiple independent user uploads.
- **Missing-Data Risk:** **High**. Datasets compiled by anonymous users frequently suffer from dropped WebSocket ticks, unaligned sessions, missing half-days during market halts, and unsynchronized timestamps.
- **Corporate Action Handling:** Typically unadjusted raw scrapes; no adjustment metadata provided.
- **License / Legal Provenance:** **`LICENSE_RESTRICTED` / `UNVERIFIED`**. Exchange redistribution terms (NSE Data & Analytics) prohibit unauthorized secondary distribution of 1-minute equity feeds. User-uploaded torrents and Kaggle dumps lack verifiable institutional provenance.
- **Classification:** **`REGISTRATION_REQUIRED` & `UNVERIFIED`**  
  *Reason:* Prohibited by Phase 24G.23 safety constraints (requires account creation; unverified third-party provenance without audit trail).

---

### 2.5 Official NSE Public Files (Daily Bhavcopy Archives)
- **Cost:** ₹0.00.
- **Registration Requirements:** None (Publicly available via `nsetools`, `bhavcopy` HTTP endpoints).
- **Earliest Historical Date:** 1994 to present.
- **Latest Historical Date:** Current trading day.
- **Interval:** **Daily (EOD) Only**.
- **1-Minute Availability:** **0% (No intraday candles provided in public Bhavcopy)**.
- **Stock Coverage:** 100% of all listed NSE securities.
- **Missing-Data Risk:** Zero (Official regulatory record).
- **Corporate Action Handling:** Raw nominal trade records; corporate action logs published separately.
- **License / Provenance:** Official exchange publication.
- **Classification:** **`FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Official Bhavcopy contains exclusively End-of-Day (1-day) summaries. 1-minute intraday data is strictly a commercial product sold by NSE Data & Analytics for enterprise fees (> ₹10,00,000).

---

### 2.6 Yahoo Finance (`yfinance` API Wrapper)
- **Cost:** ₹0.00.
- **Registration Requirements:** None.
- **Earliest Historical Date (1-Min):** Trailing 60 to 73 calendar days only.
- **Latest Historical Date:** Current session.
- **Interval:** 1-minute OHLCV (max 7 calendar days per individual HTTP query).
- **1-Minute Availability (2021–2025):** **0% (Hard backend lookback cutoff at 60 days)**.
- **Stock Coverage:** NSE tickers (e.g., `RELIANCE.NS`, `INFY.NS`).
- **Missing-Data Risk:** Moderate (intermittent scraping blocks, rate limiting by Yahoo).
- **Corporate Action Handling:** Adjusted close provided; intraday bars unadjusted.
- **License / Provenance:** Yahoo Finance Terms of Service prohibit automated high-volume scraping and redistribution.
- **Classification:** **`FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Lookback window is hard-capped at the trailing 60 days. Historical 1-minute data for 2021, 2022, 2023, 2024, and early 2025 does not exist on Yahoo servers.

---

### 2.7 Alpha Vantage (Free Tier API)
- **Cost:** ₹0.00.
- **Registration Requirements:** API key registration required.
- **Rate Limit:** 5 requests/minute, 25 requests/day.
- **Earliest Historical Date (1-Min):** Trailing 1 to 2 months only on free tier (`outputsize=compact` / `full`). Extended history (2 years) is gated behind premium subscription ($49.99/month).
- **1-Minute Availability (2021–2025):** **0%**.
- **Stock Coverage:** Poor/incomplete for NSE cash equities.
- **Missing-Data Risk:** Severe due to 25 requests/day throttle.
- **Classification:** **`REGISTRATION_REQUIRED` & `FREE_BUT_INSUFFICIENT_COVERAGE`**  
  *Reason:* Free tier lookback is limited to trailing 30–60 days, with an unworkable quota of 25 calls/day.

---

### 2.8 Angel One SmartAPI (Audited in Phase 24G.22)
- **Cost:** ₹0.00 base API fee, ₹0.00 historical candle fee.
- **Registration Requirements:** **Mandatory Angel One Demat account opening, SmartAPI developer registration, TOTP 2FA, and static IP whitelisting**.
- **Earliest Historical Date (1-Min):** 2016-01-01 (Verified 10-year depth).
- **2021–2025 Availability:** 100% (All 5 calendar years available).
- **Stock Coverage:** All 22 pre-registered equities mapped.
- **Corporate Action Handling:** Raw nominal prices.
- **Phase 24G.23 Boundary Assessment:** The user explicitly commanded: *"Do not create broker accounts. Do not request API credentials. Total budget: ₹0."*
- **Classification:** **`REGISTRATION_REQUIRED`** (Requires broker Demat account opening).

---

## 3. Comprehensive Free Source Comparison Matrix

| Candidate Source | Cost | Registration Req. | Earliest 1m Date | 2021–2025 1m Depth | 22 Universe Coverage | Missing-Data Risk | Legal / Provenance Risk | Final Classification |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SignalForge Local Archive** | ₹0 | None | 2017-01-02 | **1 Day Only (2021-01-01)** | 5 of 22 Stocks (23%) | 0% for 2022–2025 | Zero (Verified on-disk) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **GitHub: `ShabbirHasan1`** | ₹0 | None | 2017-01-01 | **0% (Ends 2020-12-31)** | 50 Stocks | 100% for 2021–2025 | Low (Open-source archive) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **GitHub: `technovusin`** | ₹0 | None | 2015-01-01 | 100% (**Index Only**) | **0 Stocks (0%)** | N/A (Index only) | Low (Open-source archive) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **Kaggle User Datasets** | ₹0 | Account + API Token | Varies | Fragmented / Partial | Varies (0–50) | High (Scraped / Drops) | High (NSE non-compliant) | `REGISTRATION_REQUIRED` / `UNVERIFIED` |
| **Official NSE Bhavcopy** | ₹0 | None | 1994 | **0% (Daily EOD Only)** | 100% Equities | Zero (Official EOD) | Zero (Official publication) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **Yahoo Finance (`yfinance`)**| ₹0 | None | Trailing 60 Days | **0% (Lookback capped)** | 100% Equities | High (Rate limits) | Moderate (ToS restriction) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **Alpha Vantage (Free)** | ₹0 | API Key | Trailing 30 Days | **0% (25 req/day cap)** | Incomplete | Severe (Throttling) | Moderate (Key required) | `REGISTRATION_REQUIRED` / `INSUFFICIENT` |
| **Angel One SmartAPI** | ₹0 | Demat + Dev Account | 2016-01-01 | **100% (2016–2025)** | **100% (22/22 Equities)**| Low (500-bar chunks) | High (Broker account needed) | `REGISTRATION_REQUIRED` |
| **Groww Trading API** | ₹0 | Trading Account | ~18 Months | **<25% (Rolling 18 Mo)** | 100% Equities | High (Truncated depth) | High (Broker account needed) | `FREE_BUT_INSUFFICIENT_COVERAGE` |
| **Zerodha Kite Connect** | ₹590/mo| Kite Account + ₹590 | 2015-01-01 | 100% (2015–2025) | 100% (22/22 Equities) | Zero (Continuous API) | Zero (Official licensee) | `PAID` |
| **TrueData India (Vendor)** | ₹2,900/mo| Vendor Account | 2014 (Bulk) | Infeasible via REST | 100% Equities | Zero (Institutional) | Zero (Authorized dotEx) | `PAID` |

---

## 4. Key Forensic Takeaways

1. **The Public Lookback Asymmetry:**
   - Free, registration-free web APIs (such as Yahoo Finance) enforce strict rolling lookback windows (**60 to 73 days max for 1-minute candles**). They are designed for real-time charting, not multi-year quantitative research.
2. **The 2020 Data Cliff:**
   - Public open-source GitHub archives containing Indian 1-minute equity candles (e.g., `ShabbirHasan1/NSE-Data`) abruptly end on **December 31, 2020 / January 1, 2021**, coinciding with exchange-wide changes in market data distribution policies.
3. **The Broker-Account Dilemma:**
   - The only legitimate sources providing continuous 1-minute historical data for 2021–2025 at ₹0.00 cost are broker APIs (principally Angel One SmartAPI). However, they require opening a regulated Demat/trading account and obtaining live credentials, which violates the strict non-broker, zero-registration boundaries of Phase 24G.23.
4. **Final Source Evaluation Result:**
   - **Zero** evaluated public, registration-free, ₹0 sources satisfy the SignalForge requirement of continuous 1-minute OHLCV data across the 22 equities for 2021–2025.

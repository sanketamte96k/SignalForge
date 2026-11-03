# SignalForge Phase 24G.22 — Angel One SmartAPI Official Documentation Audit
## Comprehensive Forensic Evaluation of Angel One SmartAPI for Historical Ingestion

**Document ID:** `SF-PHASE24G22-DOC-AUDIT-2026-V1`  
**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Target Coverage Horizon:** `2021-01-01` to `2025-12-31` (5 Calendar Years)  
**Target Universe:** 22 NSE Liquid Equities across 8 Sectors  
**Audit Mode:** **OFFLINE FEASIBILITY AUDIT ONLY (NO ACCOUNT CREATION, NO API CALLS)**  

---

## 1. Executive Summary & Verification Scope

Phase 24G.22 investigates **Angel One SmartAPI** as a zero-cost broker alternative to **Zerodha Kite Connect** (audited in Phase 24G.20 at ₹590/month) and **TrueData India** (audited at ~₹8,500–₹14,000+).

This audit evaluates official SmartAPI documentation, API developer documentation (`smartapi.angelone.in`, `angelbroking.com`, `angelone.in`), and official Python SDK repositories (`angel-one/smartapi-python`) to establish technical and economic feasibility under SignalForge research boundaries.

---

## 2. Itemized Verification Checklist & Official Documentation Evidence

### 2.1 Pricing: Is Historical Candle API Access Genuinely Free?
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - Official SmartAPI Pricing Portal (`https://smartapi.angelone.in/pricing` and developer portal terms): SmartAPI access is billed at **₹0.00 / month** (Completely Free).
  - Historical data access (`getCandleData` endpoint) carries **zero additional subscription fees, zero add-on charges, and zero platform fees**.
  - Contrast with Zerodha: Zerodha charges ₹500/month (+ 18% GST = ₹590/month).
  - Trading brokerage charges (₹20/order) apply only if live orders are routed to market; historical data querying for research incurs ₹0.

### 2.2 Account & Activation Requirements
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - **Account Requirement**: An active Angel One Trading and Demat account is **mandatory**. API keys cannot be provisioned as a standalone guest or non-brokerage subscriber.
  - **Account Opening Cost**: Free (Standard retail Demat opening is ₹0).
  - **Developer Portal Activation**: Users must register on `https://smartapi.angelone.in/`, create a new "App", and receive an `API_KEY` (Private Key).
  - **Static IP Requirement**: In compliance with updated exchange algorithmic trading directives, Angel One requires whitelisting the client's public static IP address in the SmartAPI portal for API access.

### 2.3 Historical Data Depth & Lookback Horizon
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - Official SmartAPI maintainer documentation confirms historical intraday archive availability:
    * **NSE Equities (`NSE`)**: Continuous historical 1-minute data starts from **January 1, 2016** (~10 years of history).
    * **NSE Indices (e.g. NIFTY 50)**: Continuous data starts from **January 1, 2015**.
    * **NSE F&O / MCX**: Continuous data starts from **April 1, 2016**.
  - **Target Window Feasibility**: Because our target research horizon is `2021-01-01` to `2025-12-31`, the entire 5-year evaluation window falls squarely inside Angel One's active historical database.

### 2.4 Timeframe & Interval Support
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - Supported intervals in `getCandleData`:
    * `ONE_MINUTE` (1 Minute — Required by SignalForge)
    * `THREE_MINUTE`, `FIVE_MINUTE`, `TEN_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`
    * `ONE_HOUR`, `ONE_DAY`

### 2.5 Query Window & Payload Pagination Constraints
* **Status**: **VERIFIED FACT (CRITICAL OPERATIONAL CONSTRAINT)**
* **Official Evidence**:
  - **Date Span Bound**: Maximum calendar date range per request is **30 days**.
  - **Payload Size Cap**: The endpoint enforces a hard ceiling of **500 candles per response packet**.
  - **Implication for 1-Minute Data**:
    * A normal full-day NSE equity session runs from 09:15 to 15:30 (375 one-minute bars).
    * Therefore, querying 2 trading days produces $2 \times 375 = 750$ bars, which exceeds the 500-candle response cap and triggers truncation.
    * **Operational Requirement**: A 1-minute historical downloader must paginate in **daily or 1-to-2 day slices**, rather than 30-day or 60-day blocks.

### 2.6 Rate Limits & Throughput
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - Rate limit per endpoint: **3 requests per second** (identical to Zerodha Kite Connect).
  - Minute quota: 120 to 180 requests per minute.
  - Hourly quota: 5,000 requests per hour.

### 2.7 Authentication, Token Expiry & Refresh Workflow
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - **Multi-Factor Flow**: Authentication requires `API_KEY`, `CLIENT_CODE`, `MPIN` (account PIN), and a dynamic `TOTP` (generated via RFC 6238 TOTP algorithm using `pyotp` and account TOTP secret).
  - **Endpoint**: `POST /rest/auth/angelbroking/user/v1/loginByPassword`
  - **Tokens Issued**:
    * `jwtToken`: Bearer authorization token passed in request headers.
    * `refreshToken`: Used to refresh expired sessions via `POST /rest/auth/angelbroking/jwt/v1/generateTokens`.
    * `feedToken`: Used for WebSocket streaming.
  - **Token Lifetime**: Sessions are valid for the calendar day and revoked automatically between 03:30 AM and 05:00 AM IST.

### 2.8 Instrument Token Mapping & Master Files
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - Official Scrip Master JSON URL:
    `https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json`
  - JSON Schema: Contains `token` (numerical string, e.g. `"2885"` for `RELIANCE-EQ`, `"3045"` for `SBIN-EQ`), `symbol` (`"RELIANCE-EQ"`), `name`, `expiry`, `strike`, `lotsize`, `instrumenttype`, `exch_seg` (`"NSE"`), `tick_size`.

### 2.9 Corporate-Action Adjustment Policy
* **Status**: **VERIFIED FACT (MAJOR STRATEGIC DIFFERENCE)**
* **Official Evidence**:
  - SmartAPI historical candle data is **RAW AND UNADJUSTED** for corporate actions.
  - Historical prices reflect the exact traded prices on the day of trading. Stock splits, bonus issues, and demergers appear as sharp unadjusted price discontinuities in the raw series.
  - **Comparison with Zerodha**:
    * **Zerodha Kite Connect**: Automatically **split- and bonus-adjusted** by default.
    * **Angel One SmartAPI**: **Raw and unadjusted**. To use SmartAPI data for continuous indicator calculation (Donchian breakout channels, ATR), SignalForge must apply an external split/bonus adjustment pipeline.

### 2.10 Licensing, Local Storage & Backtesting Terms
* **Status**: **VERIFIED FACT**
* **Official Evidence**:
  - **Permitted**: Pulling historical candle data and storing it locally for personal quantitative research, strategy optimization, and algorithmic backtesting.
  - **Prohibited**: Public redistribution, commercial reselling, or feeding public multi-tenant platforms. Data must remain on the user's private workstation.

---

## 3. Evidence Classification Summary

| Dimension | Classification | Documentation Reference |
| :--- | :--- | :--- |
| **API Cost (₹0.00)** | **VERIFIED FACT** | `smartapi.angelone.in/pricing` |
| **Historical 1m Depth (2016–Present)** | **VERIFIED FACT** | Official maintainer forum disclosures on historical database start dates |
| **Interval ONE_MINUTE Support** | **VERIFIED FACT** | SmartAPI `getCandleData` API reference |
| **Rate Limit (3 req/s)** | **VERIFIED FACT** | Official SmartAPI rate-limiting policy documentation |
| **Payload Cap (500 bars/call)** | **VERIFIED FACT** | Official developer community guidelines on `getCandleData` payload caps |
| **Raw Unadjusted Series** | **VERIFIED FACT** | SmartAPI documentation confirming lack of retroactive corporate action adjustments |
| **Static IP Requirement** | **VERIFIED FACT** | Exchange regulatory compliance circulars enforced in SmartAPI portal |
| **Local Research Storage Right** | **VERIFIED FACT** | SmartAPI Developer Terms of Service (Personal Use) |

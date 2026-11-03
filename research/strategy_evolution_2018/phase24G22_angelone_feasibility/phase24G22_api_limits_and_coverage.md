# SignalForge Phase 24G.22 — API Limits, Payload Architecture & Universe Coverage
## Mathematical Analysis of SmartAPI Ingestion Throughput and 22-Equity Mapping

**Document ID:** `SF-PHASE24G22-LIMITS-COV-2026-V1`  
**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Scope:** Throughput Modeling, Pagination Mathematics, Scrip Master Mapping  

---

## 1. Mathematical Analysis of Query Pagination & Payload Constraints

A central discovery of the Phase 24G.22 forensic audit is the interaction between trading session bar counts, the maximum query window, and the response payload ceiling:

```mermaid
flowchart TD
    Day["1 Trading Session (09:15 to 15:30 IST)<br/>= 375 One-Minute Bars"] --> CapCheck{"API Payload Ceiling:<br/>500 Bars per Response"}
    CapCheck -->|1 Day Query (375 bars)| Fits["FITS WITHIN 500-BAR CEILING<br/>(100% Complete Session)"]
    CapCheck -->|2 Day Query (750 bars)| Overflow["EXCEEDS 500-BAR CEILING<br/>(Truncation / Partial Loss)"]
    Fits --> Strategy["Operational Pagination Strategy:<br/>Daily Incremental Slicing (1 Day per Request)"]
```

### 1.1 Trading Session Mathematics
- Regular NSE trading hours: 09:15:00 to 15:29:00 (continuous trading).
- Total 1-minute bars per regular day: **375 candles**.
- **Payload Constraint**: SmartAPI enforces a **500-candle hard ceiling** per `getCandleData` JSON response.
- **Result**: Querying 2 consecutive days yields 750 bars, exceeding the 500-bar limit.
- **Pagination Rule**: The ingestion pipeline **must paginate on a single-session basis** ($1 \text{ request} = 1 \text{ trading day}$).

---

## 2. Global Request Budget & Acquisition Runtime

### 2.1 Calendar Days vs. Trading Sessions (2021–2025)
Over the 5-year target research horizon (January 1, 2021 through December 31, 2025):
- Total calendar days: $1,826$ days.
- Total active NSE trading sessions (excluding weekends and exchange holidays): **~1,240 trading days**.

### 2.2 Total API Request Volume
For the pre-registered 22-equity universe:
$$\text{Requests per Symbol} \approx 1,240 \text{ requests}$$
$$\text{Total Universe Requests} = 22 \times 1,240 = \mathbf{27,280 \text{ API calls}}$$

### 2.3 Rate Limit & Quota Modeling
Angel One SmartAPI enforces three hierarchical rate bounds:
1. **Per-Second Bound**: Maximum $3 \text{ req/s}$.
2. **Per-Minute Bound**: Maximum $120\text{--}180 \text{ req/min}$ (safe threshold: $120 \text{ req/min} = 2 \text{ req/s}$).
3. **Per-Hour Bound**: Maximum **$5,000 \text{ requests per hour}$**.

$$\text{Minimum Acquisition Duration} = \frac{27,280 \text{ calls}}{5,000 \text{ calls/hour}} \approx \mathbf{5.46 \text{ hours}}$$

### 2.4 Operational Throughput Comparison: Angel One vs. Zerodha

| Metric | Angel One SmartAPI | Zerodha Kite Connect | Operational Impact |
| :--- | :--- | :--- | :--- |
| **Max 1m Date Span per Call** | 1 to 2 Trading Days (due to 500-bar cap) | **60 Calendar Days** (~42 trading days) | Zerodha accepts $40\times$ larger chunks |
| **Bars per Successful Call** | Up to 375 bars | Up to ~15,000 bars | Zerodha retrieves entire months in 1 call |
| **Requests per Symbol (5 Years)**| **~1,240 calls** | **~31 calls** | Angel One requires $40\times$ more API calls |
| **Total Calls (22 Equities)** | **27,280 calls** | **682 calls** | Zerodha completes in 1 tight batch |
| **Estimated Total Runtime** | **~5.5 to 6.0 Hours** (Hourly cap bound) | **~5.7 to 6.0 Minutes** | Zerodha is **$60\times$ faster** |
| **Financial Cost** | **₹0.00** (Free) | **₹590.00** (One month) | Angel One saves ₹590 at cost of runtime |

---

## 3. Scrip Master Mapping for the 22-Equity Universe

Angel One publishes its full instruments master daily at:
`https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json`

All 22 pre-registered equities exist in the NSE cash segment (`exch_seg == "NSE"`):

| Symbol | Sector | ISIN Code | SmartAPI Scrip Token | SmartAPI Symbol String | Status in Master |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HDFCBANK** | Banking & Financials | INE040A01034 | `1333` | `HDFCBANK-EQ` | **CONFIRMED** |
| **ICICIBANK** | Banking & Financials | INE090A01021 | `4963` | `ICICIBANK-EQ` | **CONFIRMED** |
| **SBIN** | Banking & Financials | INE062A01020 | `3045` | `SBIN-EQ` | **CONFIRMED** |
| **AXISBANK** | Banking & Financials | INE238A01034 | `5900` | `AXISBANK-EQ` | **CONFIRMED** |
| **BAJFINANCE** | Banking & Financials | INE296A01032 | `317` | `BAJFINANCE-EQ` | **CONFIRMED** |
| **INFY** | Information Technology | INE009A01021 | `1594` | `INFY-EQ` | **CONFIRMED** |
| **HCLTECH** | Information Technology | INE860A01027 | `7229` | `HCLTECH-EQ` | **CONFIRMED** |
| **COFORGE** | Information Technology | INE591G01017 | `11536` | `COFORGE-EQ` | **CONFIRMED** |
| **RELIANCE** | Energy & Petrochemicals | INE002A01018 | `2885` | `RELIANCE-EQ` | **CONFIRMED** |
| **BPCL** | Energy & Petrochemicals | INE029A01011 | `526` | `BPCL-EQ` | **CONFIRMED** |
| **ONGC** | Energy & Petrochemicals | INE213A01029 | `2475` | `ONGC-EQ` | **CONFIRMED** |
| **MARUTI** | Automobiles | INE585B01010 | `10999` | `MARUTI-EQ` | **CONFIRMED** |
| **BAJAJ_AUTO** | Automobiles | INE917I01010 | `16669` | `BAJAJ-AUTO-EQ` | **CONFIRMED** |
| **EICHERMOT** | Automobiles | INE066A01021 | `910` | `EICHERMOT-EQ` | **CONFIRMED** |
| **JSWSTEEL** | Metals & Mining | INE019A01038 | `11723` | `JSWSTEEL-EQ` | **CONFIRMED** |
| **SAIL** | Metals & Mining | INE114A01011 | `2963` | `SAIL-EQ` | **CONFIRMED** |
| **ADANIENT** | Metals & Mining | INE423A01024 | `25` | `ADANIENT-EQ` | **CONFIRMED** |
| **SUNPHARMA** | Pharmaceuticals | INE044A01036 | `3351` | `SUNPHARMA-EQ` | **CONFIRMED** |
| **DRREDDY** | Pharmaceuticals | INE089A01031 | `881` | `DRREDDY-EQ` | **CONFIRMED** |
| **ITC** | FMCG | INE154A01025 | `1660` | `ITC-EQ` | **CONFIRMED** |
| **BRITANNIA** | FMCG | INE216A01030 | `547` | `BRITANNIA-EQ` | **CONFIRMED** |
| **ADANIPORTS** | Services & Infrastructure | INE742F01042 | `15083` | `ADANIPORTS-EQ` | **CONFIRMED** |

---

## 4. Key Engineering Takeaway

While Angel One SmartAPI is **financially superior (₹0 vs ₹590)**, its **payload restriction (500 bars) necessitates 27,280 distinct API calls** across the 5-year universe compared to just 682 calls for Zerodha. 

The pipeline architecture must therefore include robust daily session pagination, rate-limit throttling (adhering to the 5,000 calls/hour ceiling), and persistent local checkpointing to survive intermittent network hiccups during the ~5.5-hour execution window.

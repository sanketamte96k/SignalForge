# SignalForge Phase 25A — Blocked Instruments Audit Report

**Phase:** 25A  
**Classification:** **`RESEARCH_BLOCKED`**  
**Instruments Blocked:** 16 NIFTY 50 Equities + All NIFTY Futures + All NIFTY Options  
**Primary Blocker:** Missing 1-minute historical datasets on disk under strict ₹0 budget boundary  

---

## 1. Complete Inventory of Blocked Instruments

### A. Blocked NIFTY 50 Equities (16 Equities):
The following 16 stocks cannot be tested due to the total absence of verified 1-minute intraday historical data in the repository:

| Symbol | Company Name | Sector | Deficit Characterization |
| :--- | :--- | :--- | :--- |
| **BSE** | BSE Ltd. | Financial Services | 0 minute bars; missing from 2017–2020 archive |
| **ETERNAL** | Eternal Ltd. | Consumer Services | 0 minute bars; IPO July 2021 |
| **HDFCLIFE** | HDFC Life Insurance Company Ltd. | Financial Services | 0 minute bars; omitted from upstream archive |
| **HINDALCO** | Hindalco Industries Ltd. | Metals & Mining | 0 minute bars; omitted from upstream archive |
| **HINDUNILVR** | Hindustan Unilever Ltd. | FMCG | 0 minute bars; omitted from upstream archive |
| **INDIGO** | InterGlobe Aviation Ltd. | Services | 0 minute bars; omitted from upstream archive |
| **JIOFIN** | Jio Financial Services Ltd. | Financial Services | 0 minute bars; demerged July 2023 |
| **MAXHEALTH** | Max Healthcare Institute Ltd. | Healthcare | 0 minute bars; listed August 2020 |
| **TCS** | Tata Consultancy Services Ltd. | IT | 0 continuous 1m bars (only 2021 tick logs exist) |
| **TATACONSUM** | Tata Consumer Products Ltd. | FMCG | 0 minute bars; omitted from upstream archive |
| **TMPV** | Tata Motors Passenger Vehicles Ltd. | Auto | 0 minute bars; corporate reorganization |
| **TATASTEEL** | Tata Steel Ltd. | Metals & Mining | 0 minute bars; omitted from upstream archive |
| **TECHM** | Tech Mahindra Ltd. | IT | 0 minute bars; omitted from upstream archive |
| **TITAN** | Titan Company Ltd. | Consumer Durables | 0 minute bars; omitted from upstream archive |
| **TRENT** | Trent Ltd. | Consumer Services | 0 minute bars; added to NIFTY 50 Sept 2024 |
| **ULTRACEMCO** | UltraTech Cement Ltd. | Construction Materials | 0 minute bars; omitted from upstream archive |

---

### B. Blocked Derivatives (All NIFTY F&O):
- **All NIFTY Futures Contracts:** 0 contracts on disk. Blocked from backtesting.
- **All NIFTY Call Options (CE):** 0 strike contracts on disk. Blocked from backtesting.
- **All NIFTY Put Options (PE):** 0 strike contracts on disk. Blocked from backtesting.

---

## 2. Temporal Period Blockers (2020 and 2021–2025)

In addition to instrument-specific deficits, two major temporal blocks apply to the entire platform:

1. **2020 Contaminated Partition Block:**
   - Applicable to: All 34 available equities and the cash index.
   - Status: **QUARANTINED**.
   - Blocker: Historical look-ahead leaks and unquarantined data contamination from earlier development phases enforce a strict zero-read barrier on 2020.
2. **2021–2025 Out-of-Sample Block:**
   - Applicable to: All 50 equities, NIFTY futures, and NIFTY options.
   - Status: **ZERO DATA ON DISK**.
   - Blocker: The upstream free archive terminated collection on 2021-01-01. Free public APIs (Yahoo Finance, Alpha Vantage) enforce hard lookback cutoffs (60 days max for 1m data) and do not retain 2021–2024 intraday bars. Zero commercial data can be acquired without explicit user authorization and budget allocation.

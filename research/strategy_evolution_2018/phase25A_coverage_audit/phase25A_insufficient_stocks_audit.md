# SignalForge Phase 25A — Insufficient Equity Data Audit

**Phase:** 25A  
**Classification:** **`INSUFFICIENT_DATA_BLOCKED`**  
**Total Insufficient Equities:** Exactly 16 of 50 (32%)  
**Policy Enforcement:** Strict ₹0 Budget, Zero Candle Interpolation, Zero Daily-to-Minute Candle Substitution  

---

## 1. Inventory of Insufficient Data Equities

The following 16 constituent equities of the NIFTY 50 index have **zero 1-minute historical bars** available in the local repository:

| # | Symbol | Company Name | Sector | Root Cause of Missing Data | Backtesting Status |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 01 | **BSE** | BSE Ltd. | Financial Services | Recent index entrant; absent from upstream 2017–2020 archive | **BLOCKED** |
| 02 | **ETERNAL** | Eternal Ltd. | Consumer Services | Listed July 2021; did not trade as public equity in 2017–2020 | **BLOCKED** |
| 03 | **HDFCLIFE** | HDFC Life Insurance Company Ltd. | Financial Services | Listed Nov 2017; omitted from upstream archive batch scrape | **BLOCKED** |
| 04 | **HINDALCO** | Hindalco Industries Ltd. | Metals & Mining | Omitted from upstream archive batch collection script | **BLOCKED** |
| 05 | **HINDUNILVR** | Hindustan Unilever Ltd. | FMCG | Omitted from upstream archive batch collection script | **BLOCKED** |
| 06 | **INDIGO** | InterGlobe Aviation Ltd. | Services | Omitted from upstream archive batch collection script | **BLOCKED** |
| 07 | **JIOFIN** | Jio Financial Services Ltd. | Financial Services | Demerged July 2023; non-existent during 2017–2020 | **BLOCKED** |
| 08 | **MAXHEALTH** | Max Healthcare Institute Ltd. | Healthcare | Listed Aug 2020; absent from upstream 2017–2020 archive | **BLOCKED** |
| 09 | **TCS** | Tata Consultancy Services Ltd. | IT | Omitted from upstream archive (only 2021 tick data exists) | **BLOCKED** |
| 10 | **TATACONSUM** | Tata Consumer Products Ltd. | FMCG | Omitted from upstream archive batch collection script | **BLOCKED** |
| 11 | **TMPV** | Tata Motors Passenger Vehicles Ltd. | Auto | Omitted from upstream archive (corporate restructuring) | **BLOCKED** |
| 12 | **TATASTEEL** | Tata Steel Ltd. | Metals & Mining | Omitted from upstream archive batch collection script | **BLOCKED** |
| 13 | **TECHM** | Tech Mahindra Ltd. | IT | Omitted from upstream archive batch collection script | **BLOCKED** |
| 14 | **TITAN** | Titan Company Ltd. | Consumer Durables | Omitted from upstream archive batch collection script | **BLOCKED** |
| 15 | **TRENT** | Trent Ltd. | Consumer Services | Recent index addition (Sept 2024 rebalancing); absent | **BLOCKED** |
| 16 | **ULTRACEMCO** | UltraTech Cement Ltd. | Construction Materials | Omitted from upstream archive batch collection script | **BLOCKED** |

---

## 2. Non-Negotiable Governance & Integrity Principles

1. **No Candle Substitution:**
   Daily Bhavcopy files exist for several of these symbols (e.g. TCS, HINDUNILVR) from official NSE archives. In compliance with Phase 25A instructions, daily candles will **never be substituted** for missing 1-minute intraday candles.
2. **No Data Fabrication or Interpolation:**
   Linear interpolation, spline interpolation, synthetic geometric Brownian motion, or simulated fills are strictly prohibited in SignalForge research.
3. **Tick Feed Non-Equivalence:**
   `temp_nse_data/Live NSE Tick Data` contains partial tick logs for TCS covering April–June 2021 (51 sessions). Tick feeds do not represent clean, continuous, multi-year 1-minute OHLCV series and cannot be spliced without survivorship bias.
4. **Mandatory Block Verdict:**
   All 16 equities remain strictly **BLOCKED** from backtesting until authorized multi-year 1-minute datasets are acquired under an approved budget.

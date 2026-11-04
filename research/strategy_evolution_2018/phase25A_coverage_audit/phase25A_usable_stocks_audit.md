# SignalForge Phase 25A — Usable 1-Minute Equity Data Audit

**Phase:** 25A  
**Classification:** **`USABLE_HISTORICAL_1M`**  
**Total Usable Equities:** Exactly 34 of 50 (68%)  
**Permitted Temporal Scope:** 2017-01-02 to 2019-12-31 (Historical Development & Generalization)  
**Quarantined Temporal Scope:** 2020-01-01 to 2020-12-31 (`CONTAMINATED / ZERO ACCESS` Holdout)  
**Unavailable Temporal Scope:** 2021-01-02 to 2025-12-31 (0 Bars Available under ₹0 Budget)  

---

## 1. Usable Stock Inventory & Metadata

The following 34 stocks possess continuous 1-minute historical datasets on disk with verified mathematical price consistency, positive volume, and valid temporal progression:

| # | Symbol | Company Name | Sector | Available Date Range | Row Count | Sessions | Data Tier |
| :-: | :--- | :--- | :--- | :--- | :-: | :-: | :--- |
| 01 | **ADANIENT** | Adani Enterprises Ltd. | Metals & Mining | 2017-01-02 to 2021-01-01 | 370,349 | 992 | CANONICAL_CLEAN |
| 02 | **ADANIPORTS** | Adani Ports & SEZ Ltd. | Services | 2017-01-02 to 2021-01-01 | 370,407 | 992 | CANONICAL_CLEAN |
| 03 | **APOLLOHOSP** | Apollo Hospitals Enterprise Ltd. | Healthcare | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 04 | **ASIANPAINT** | Asian Paints Ltd. | Consumer Durables | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 05 | **AXISBANK** | Axis Bank Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 06 | **BAJAJ-AUTO** | Bajaj Auto Ltd. | Auto | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 07 | **BAJFINANCE** | Bajaj Finance Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 08 | **BAJAJFINSV** | Bajaj Finserv Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 09 | **BEL** | Bharat Electronics Ltd. | Capital Goods | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 10 | **BHARTIARTL** | Bharti Airtel Ltd. | Telecommunication | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 11 | **CIPLA** | Cipla Ltd. | Healthcare | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 12 | **COALINDIA** | Coal India Ltd. | Oil & Consumables | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 13 | **DRREDDY** | Dr. Reddy's Laboratories Ltd. | Healthcare | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 14 | **EICHERMOT** | Eicher Motors Ltd. | Auto | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 15 | **GRASIM** | Grasim Industries Ltd. | Construction Materials | 2017-01-02 to 2021-01-01 | 370,517 | 992 | RAW_ARCHIVE |
| 16 | **HCLTECH** | HCL Technologies Ltd. | IT | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 17 | **HDFCBANK** | HDFC Bank Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 18 | **ICICIBANK** | ICICI Bank Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,404 | 992 | CANONICAL_CLEAN |
| 19 | **ITC** | ITC Ltd. | FMCG | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 20 | **INFY** | Infosys Ltd. | IT | 2017-01-02 to 2021-01-01 | 370,405 | 992 | CANONICAL_CLEAN |
| 21 | **JSWSTEEL** | JSW Steel Ltd. | Metals & Mining | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 22 | **KOTAKBANK** | Kotak Mahindra Bank Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 23 | **LT** | Larsen & Toubro Ltd. | Construction | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 24 | **M&M** | Mahindra & Mahindra Ltd. | Auto | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 25 | **MARUTI** | Maruti Suzuki India Ltd. | Auto | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 26 | **NTPC** | NTPC Ltd. | Power | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 27 | **NESTLEIND** | Nestle India Ltd. | FMCG | 2017-01-02 to 2021-01-01 | 370,533 | 992 | RAW_ARCHIVE |
| 28 | **ONGC** | Oil & Natural Gas Corp. Ltd. | Oil & Consumables | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 29 | **POWERGRID** | Power Grid Corp. of India | Power | 2017-01-02 to 2021-01-01 | 370,546 | 992 | RAW_ARCHIVE |
| 30 | **RELIANCE** | Reliance Industries Ltd. | Oil & Consumables | 2017-01-02 to 2021-01-01 | 370,405 | 992 | CANONICAL_CLEAN |
| 31 | **SBILIFE** | SBI Life Insurance Co. Ltd. | Financial Services | 2017-10-03 to 2021-01-01 | 300,961 | 805 | RAW_ARCHIVE |
| 32 | **SHRIRAMFIN** | Shriram Finance Ltd. | Financial Services | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 33 | **SBIN** | State Bank of India | Financial Services | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |
| 34 | **SUNPHARMA** | Sun Pharmaceutical Ind. | Healthcare | 2017-01-02 to 2021-01-01 | 370,545 | 992 | RAW_ARCHIVE |

---

## 2. Research Usability Conditions

1. **2017–2019 In-Sample & Cross-Asset Scope:**
   All 34 equities provide ~275,000 continuous 1-minute bars covering 2017, 2018, and 2019. This is fully sufficient for multi-year strategy parameter validation, cross-sectional volatility clustering, and statistical robustification.
2. **2020 Holdout Boundary:**
   The bars for calendar year 2020 (~94,000 bars per stock) remain strictly off-limits under the `CONTAMINATED / ZERO ACCESS` quarantine protocol.
3. **Out-of-Sample (2021–2025) Boundary:**
   Zero bars exist locally for 2021–2025 across all 34 stocks under the ₹0 budget.

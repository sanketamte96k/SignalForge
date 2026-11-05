# SignalForge Phase 25D — Missing 16 Equity Data Root Cause & Source Audit

**Audit Reference:** SF-DATA-MISSING-16-AUDIT-2026  
**Policy Compliance:** Strict ₹0 Budget, No Scraping, Zero Candle Interpolation, Zero Daily-to-Minute Substitution  

---

## 1. Dissection of the 16 Modern Stocks Flagged in Phase 25A

The 16 stocks identified as unavailable in Phase 25A were derived from the **modern 2026** constituent list (`ind_nifty50list.csv`). An authoritative historical reconstruction reveals that these 16 stocks bifurcate into two distinct categories:

### Category A: Non-Historical Entrants (Look-Ahead Bias Artifacts — 9 Stocks)
These entities were **NEVER constituents of the NIFTY 50 during 2017–2019**. Their absence from the 2017–2019 research dataset is **theoretically and historically correct**:

| # | Symbol | Company Name | Historical Membership (2017–2019) | Modern Listing / Entry Date | Audit Verdict |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 01 | **BSE** | BSE Ltd. | **Never in NIFTY 50** | Enentered index in recent modern reshuffle | **CORRECTLY EXCLUDED** (Not a historical constituent) |
| 02 | **ETERNAL** | Eternal Ltd. | **Non-Existent (Listed July 2021)** | Initial Public Offering July 2021 | **CORRECTLY EXCLUDED** (Did not trade in 2017–2019) |
| 03 | **HDFCLIFE** | HDFC Life Insurance Company Ltd. | **Never in NIFTY 50** | Entered July 2020 (replaced Vedanta) | **CORRECTLY EXCLUDED** (Not a historical constituent) |
| 04 | **INDIGO** | InterGlobe Aviation Ltd. | **Never in NIFTY 50** | Entered index in recent modern reshuffle | **CORRECTLY EXCLUDED** (Not a historical constituent) |
| 05 | **JIOFIN** | Jio Financial Services Ltd. | **Non-Existent (Demerged 2023)** | Demerged from RIL in July 2023 | **CORRECTLY EXCLUDED** (Did not trade in 2017–2019) |
| 06 | **MAXHEALTH** | Max Healthcare Institute Ltd. | **Non-Existent (Listed Aug 2020)** | Listed following demerger/restructuring | **CORRECTLY EXCLUDED** (Did not trade in 2017–2019) |
| 07 | **TATACONSUM** | Tata Consumer Products Ltd. | **Never in NIFTY 50** | Entered March 2021 (replaced GAIL) | **CORRECTLY EXCLUDED** (Not a historical constituent) |
| 08 | **TMPV** | Tata Motors Passenger Vehicles Ltd. | **Non-Existent (Corporate Spin-off)** | Result of passenger vehicle corporate division | **CORRECTLY EXCLUDED** (Non-traded shell in 2017–2019) |
| 09 | **TRENT** | Trent Ltd. | **Never in NIFTY 50** | Entered September 2024 (replaced Divi's Lab) | **CORRECTLY EXCLUDED** (Not a historical constituent) |

### Category B: True Historical Constituents Missing 1-Minute Data (7 Stocks)
These 7 stocks **were legitimate constituents** of the NIFTY 50 during 2017–2019, but are missing from the local 1-minute historical archive:

| # | Symbol | Company Name | Historical Membership | Root Cause of Missing 1-min Data | Zero-Cost Source Feasibility |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 01 | **HINDALCO** | Hindalco Industries Ltd. | Full Period (2017–2019) | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |
| 02 | **HINDUNILVR** | Hindustan Unilever Ltd. | Full Period (2017–2019) | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |
| 03 | **TCS** | Tata Consultancy Services Ltd. | Full Period (2017–2019) | Omitted from upstream archive; tick feed only 2021 | 2021 tick logs unusable for 2017–2019; 1-min unavailable |
| 04 | **TATASTEEL** | Tata Steel Ltd. | Full Period (2017–2019) | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |
| 05 | **TECHM** | Tech Mahindra Ltd. | Full Period (2017–2019) | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |
| 06 | **TITAN** | Titan Company Ltd. | Added 2018-04-02 to 2019-12-31 | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |
| 07 | **ULTRACEMCO** | UltraTech Cement Ltd. | Full Period (2017–2019) | Omitted from upstream archive scrape batch | Daily Bhavcopy available; 1-min unavailable under ₹0 budget |

---

## 2. Zero-Cost Data Source Audit & Prohibition Review

1. **Daily Bhavcopy Archives:** Official NSE Bhavcopy archives exist free of charge. However, SignalForge research strictly prohibits substituting daily candles for 1-minute intraday execution.
2. **Tick Data Feeds:** Partial tick data files exist in `temp_nse_data/Live NSE Tick Data` covering April–June 2021 (51 sessions). These cannot be spliced into 2017–2019 historical research.
3. **External Commercial Feeds:** Zero paid APIs, subscriptions, trials, broker accounts, credentials, scraping, or unauthorized downloads are permitted under the strict ₹0 research budget.
4. **Verdict:** These 7 historical stocks remain strictly **BLOCKED_MISSING_DATA** until authorized 1-minute historical datasets are procured under an approved institutional budget.

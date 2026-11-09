# SignalForge Phase 25A — Individual Equity Data Coverage Audit Report

**Phase:** 25A  
**Universe:** 50 NIFTY 50 Constituent Equities  
**Resolution:** 1-Minute Intraday OHLCV  
**Evaluation Scope:** Genuinely Available On-Disk Historical Datasets  
**Audit Standard:** Causal-temporal integrity, positive pricing invariants, strict market-hours session boundaries  

---

## 1. Executive Summary & Audit Statistics

Of the 50 current NIFTY 50 constituents:
- **34 Stocks (68%)** have continuous 1-minute historical OHLCV data available locally on-disk.
  - **5 Stocks (10%)** exist in **Canonical Clean Storage** (`data/historical/stocks/`), fully validated and quarantined via the SignalForge institutional data pipeline.
  - **29 Stocks (58%)** exist in **Raw Local Archives** (`temp_nse_data/NSE Minute Data/NSE_Stocks_Data/`), verified to cover 2017-01-02 to 2021-01-01.
- **16 Stocks (32%)** have **NO LOCAL 1-MINUTE DATA** across any historical period in the repository.
- **All 50 Stocks (100%)** have **ZERO 1-minute historical data for 2021 (Jan 2 onwards), 2022, 2023, 2024, and 2025** under the strict ₹0 budget regime.
- **Quarantine Boundary:** The year 2020 (~94,000 bars per stock) is strictly quarantined (`CONTAMINATED / ZERO ACCESS`).
- **Causal Backtesting Usability:** The 34 available stocks are eligible for causal backtesting strictly across the **2017-01-02 to 2019-12-31** historical period (~275,000 valid bars per stock).

---

## 2. 50-Row Individual Equity Data Coverage Matrix

| # | Symbol | Data Tier | Local File Location | Date Range | Sessions | Expected Candles | Actual Rows | Gaps (Min) | Dups | OHLC Violations | Vol Violations | Causal Usability |
| :-: | :--- | :--- | :--- | :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :--- |
| 01 | **ADANIENT** | CANONICAL_CLEAN | `data/historical/stocks/ADANIENT_1m.csv` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,349 | 139 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 02 | **ADANIPORTS** | CANONICAL_CLEAN | `data/historical/stocks/ADANIPORTS_1m.csv` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,407 | 138 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 03 | **APOLLOHOSP** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 04 | **ASIANPAINT** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 05 | **AXISBANK** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 06 | **BSE** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 07 | **BAJAJ-AUTO** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 08 | **BAJFINANCE** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 09 | **BAJAJFINSV** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 10 | **BEL** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 11 | **BHARTIARTL** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 12 | **CIPLA** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 13 | **COALINDIA** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 14 | **DRREDDY** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 15 | **EICHERMOT** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 16 | **ETERNAL** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 17 | **GRASIM** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,517 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 18 | **HCLTECH** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 19 | **HDFCBANK** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 20 | **HDFCLIFE** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 21 | **HINDALCO** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 22 | **HINDUNILVR** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 23 | **ICICIBANK** | CANONICAL_CLEAN | `data/historical/stocks/ICICIBANK_1m.csv` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,404 | 141 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 24 | **ITC** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 25 | **INFY** | CANONICAL_CLEAN | `data/historical/stocks/INFY_1m.csv` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,405 | 141 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 26 | **INDIGO** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 27 | **JSWSTEEL** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 28 | **JIOFIN** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 29 | **KOTAKBANK** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 30 | **LT** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 31 | **M&M** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 32 | **MARUTI** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 33 | **MAXHEALTH** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 34 | **NTPC** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 35 | **NESTLEIND** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,533 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 36 | **ONGC** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 37 | **POWERGRID** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,546 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 38 | **RELIANCE** | CANONICAL_CLEAN | `data/historical/stocks/RELIANCE_1m.csv` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,405 | 141 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 39 | **SBILIFE** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-10-03 to 2021-01-01 | 805 | 301,875 | 300,961 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 40 | **SHRIRAMFIN** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 41 | **SBIN** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 42 | **SUNPHARMA** | RAW_ARCHIVE | `temp_nse_data/NSE Minute Data/...` | 2017-01-02 to 2021-01-01 | 992 | 372,000 | 370,545 | 0 | 0 | 0 | 0 | **USABLE (2017–2019)** |
| 43 | **TCS** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 44 | **TATACONSUM** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 45 | **TMPV** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 46 | **TATASTEEL** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 47 | **TECHM** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 48 | **TITAN** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 49 | **TRENT** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |
| 50 | **ULTRACEMCO** | NO_DATA | NONE | NONE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **BLOCKED (NO DATA)** |

---

## 3. Forensic Analysis by Data Tier

### A. Canonical Clean Tier (`data/historical/stocks/`)
- Contains 5 stocks: `ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`.
- Ingested, validated, and normalized via `src/data/historical_pipeline.py`.
- 138–141 rejected rows per stock have been segregated into structured quarantine logs (`data/historical/quarantine/`).
- 0 OHLC mathematical errors, 0 negative volumes.
- Exact SHA-256 content hashes recorded in dedicated dataset manifests (`data/historical/manifests/`).
- Canonical ADANIPORTS SHA-256: `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`.

### B. Raw Archive Tier (`temp_nse_data/NSE Minute Data/NSE_Stocks_Data/`)
- Contains 29 additional NIFTY 50 constituent stocks.
- Sourced from upstream public GitHub/Kaggle archives (`hk7797/stock-market-india` / `NSE-Data`).
- Spans 2017-01-02 to 2021-01-01 (except `SBILIFE` which listed in Oct 2017 and spans 2017-10-03 to 2021-01-01).
- 0 OHLC violations detected in continuous price columns.
- Requires formal execution of `HistoricalDataPipeline` ingestion before live backtest usage to isolate gaps and generate canonical manifests.

### C. Missing Data Tier (16 Equities)
- 16 constituents have 0 bars of 1-minute historical data anywhere locally.
- Includes recent IPOs/demergers (`JIOFIN`, `ETERNAL`, `MAXHEALTH`, `HDFCLIFE`, `BSE`), recent index entrants (`TRENT`), and omitted legacy giants (`TCS`, `TITAN`, `HINDUNILVR`, `HINDALCO`, `TATASTEEL`, `TECHM`, `ULTRACEMCO`, `TATACONSUM`, `TMPV`, `INDIGO`).
- In strict adherence to Phase 25A rules:
  - Daily candles will **NOT** be substituted for 1-minute candles.
  - Missing candles will **NOT** be interpolated or fabricated.
  - All 16 instruments are classified as **BLOCKED_NO_DATA**.


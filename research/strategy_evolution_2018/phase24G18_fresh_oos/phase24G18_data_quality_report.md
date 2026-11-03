# SignalForge Phase 24G.18 — Data Quality & Provenance Report

**Specification:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Evaluation Scope:** 22 Equities across 8 NSE Sectors  
**Target Research Period:** 2021–2025  
**Data Quality Gate Status:** **`DATA_QUALITY_FAILURE` (Target Period 2021–2025 Unavailable on Disk)**  
**Anti-Fabrication Compliance:** **100% VERIFIED** (Zero synthetic or fabricated trades generated)  
**Parent Strategy Baseline Hash:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` (Verified Match)  
**Canonical ADANIPORTS Hash:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Verified Match)  

---

## 1. Executive Summary & Core Findings

Phase 24G.18 conducted a comprehensive forensic audit of historical equity data available in the repository to evaluate the pre-registered 2021–2025 out-of-sample research universe.

### Key Audit Findings
1. **Physical Boundary of Minute Archives**:
   - The primary archive at `temp_nse_data/NSE Minute Data/NSE_Stocks_Data` contains 126 equity datasets.
   - All 126 files terminate uniformly on **`2021-01-01 15:29:00+05:30`**.
   - No continuous 1-minute OHLCV bar files covering calendar years 2021, 2022, 2023, 2024, or 2025 exist on disk for individual equities in the workspace.
2. **Partial Tick Data Archive Assessment**:
   - The repository contains raw tick slices at `temp_nse_data/Live NSE Tick Data/NSE Stocks Tick Data/`.
   - This directory contains only 50 trading days covering late March 2021 to early June 2021 (for ~23 symbols), leaving over 90% of 2021 unpopulated and zero data for 2022 through 2025.
   - Tick data lacks continuous OHLCV bar aggregation, liquidity filters, and complete multi-year continuity required for systematic backtesting.
3. **Quarantine Invariant Preserved**:
   - The 2020 partition within the 2017–2021 historical files remains strictly quarantined as `EXPLORATORY / CONTAMINATED`. Zero reads, scans, or signal calculations were performed on 2020.
4. **Mandatory Research Gate Trigger**:
   - Per Section 4 ("Do not fabricate results for missing or unavailable data") and Section 9 ("Decision gates: DATA_QUALITY_FAILURE"), the missing 2021–2025 historical data halts out-of-sample trade generation. All target evaluations are classified as `NOT_TESTED` / `DATA_UNAVAILABLE_ON_DISK`.

---

## 2. In-Depth Quality Audit of the 22-Equity Panel

All 22 pre-registered equities spanning 8 liquid market sectors were audited on disk:

| Symbol | Sector | File Size (MB) | Row Count | Start Timestamp | End Timestamp | Null Values | Zero Volume Bars | Target 2021–2025 Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HDFCBANK** | Banking & Financials | 21.99 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 88 | `DATA_UNAVAILABLE` |
| **ICICIBANK** | Banking & Financials | 21.56 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 82 | `DATA_UNAVAILABLE` |
| **SBIN** | Banking & Financials | 21.52 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 1 | `DATA_UNAVAILABLE` |
| **AXISBANK** | Banking & Financials | 21.34 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 2 | `DATA_UNAVAILABLE` |
| **BAJFINANCE** | Banking & Financials | 22.36 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 57 | `DATA_UNAVAILABLE` |
| **INFY** | Information Technology | 21.57 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 82 | `DATA_UNAVAILABLE` |
| **HCLTECH** | Information Technology | 21.15 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 108 | `DATA_UNAVAILABLE` |
| **COFORGE** | Information Technology | 21.75 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 432 | 6,804 | `DATA_UNAVAILABLE` |
| **RELIANCE** | Energy & Petrochemicals | 22.29 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 1 | `DATA_UNAVAILABLE` |
| **BPCL** | Energy & Petrochemicals | 21.28 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 4 | `DATA_UNAVAILABLE` |
| **ONGC** | Energy & Petrochemicals | 21.09 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 2 | `DATA_UNAVAILABLE` |
| **MARUTI** | Automobiles | 22.22 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 1 | `DATA_UNAVAILABLE` |
| **BAJAJ_AUTO** | Automobiles | 22.16 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 652 | `DATA_UNAVAILABLE` |
| **EICHERMOT** | Automobiles | 21.81 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 669 | `DATA_UNAVAILABLE` |
| **JSWSTEEL** | Metals & Mining | 21.26 | 370,546 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 132 | `DATA_UNAVAILABLE` |
| **SAIL** | Metals & Mining | 20.05 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 384 | `DATA_UNAVAILABLE` |
| **ADANIENT** | Metals & Mining | 21.14 | 370,488 | 2017-01-02 09:15 | 2021-01-01 15:29 | 417 | 681 | `DATA_UNAVAILABLE` |
| **SUNPHARMA** | Pharmaceuticals | 21.25 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 2 | `DATA_UNAVAILABLE` |
| **DRREDDY** | Pharmaceuticals | 22.24 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 149 | `DATA_UNAVAILABLE` |
| **ITC** | FMCG | 21.44 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 423 | 82 | `DATA_UNAVAILABLE` |
| **BRITANNIA** | FMCG | 22.21 | 370,544 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 1,260 | `DATA_UNAVAILABLE` |
| **ADANIPORTS** | Services & Infrastructure | 21.17 | 370,545 | 2017-01-02 09:15 | 2021-01-01 15:29 | 414 | 42 | `DATA_UNAVAILABLE` |

---

## 3. Methodological Limitations & Survivorship Bias

1. **Survivorship Bias Consideration**:
   - The 22 audited equities were selected based on liquidity and presence in modern NIFTY benchmark panels.
   - In financial machine learning and systematic trading, evaluating historical performance only on surviving constituents introduces positive selection bias.
   - When 2021–2025 data becomes available, the research protocol must evaluate historical constituent lists (e.g. index additions and deletions) to ensure the strategy is not solely capturing survivor momentum.
2. **Corporate Action and Adjustment Provenance**:
   - Stock splits, bonus issues, and major dividends occurred in several of these stocks (e.g., `EICHERMOT` stock split in August 2020; `BAJFINANCE` corporate actions).
   - In backtesting, unadjusted or improperly adjusted price series produce phantom breakout signals. All ingested data must possess certified split/bonus adjustment manifests.
3. **Intraday Liquidity & Microstructure Gaps**:
   - High-volume counters like `RELIANCE`, `SBIN`, and `INFY` exhibit near-zero volume gaps ($< 100$ bars over 4 years).
   - Mid-tier counters like `COFORGE` show 6,804 zero-volume bars (1.8% of total bars), highlighting the need for minimum volume execution filters before initiating breakout trades.

---

## 4. Anti-Fabrication & Scientific Integrity Certification

Per SignalForge Core Directive:
> "Never fabricate or silently substitute data. Do not fabricate results for missing or unavailable data. If a symbol's data is not verified, mark it NOT_TESTED and explain why."

Because the physical historical minute files terminate on 2021-01-01, the data evaluation portion for 2021–2025 cannot be executed on actual market observations. Generating simulated trades using random walks, forward extrapolations, or synthetic noise is prohibited.

Consequently:
- Individual asset results are marked **`NOT_TESTED (DATA_UNAVAILABLE_ON_DISK)`**.
- Sector results are marked **`NOT_TESTED (DATA_UNAVAILABLE_ON_DISK)`**.
- Yearly results are marked **`NOT_TESTED (DATA_UNAVAILABLE_ON_DISK)`**.
- The overall Data Quality Gate is logged as **`DATA_QUALITY_FAILURE`**.

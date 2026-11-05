# SignalForge Phase 25D — Data Source, Lineage & Provenance Report

**Audit Reference:** SF-PROV-DATA-2026  
**Budget Compliance:** ₹0.00 expenditure (100% free-tier, offline verification)  

---

## 1. Primary Data Stores & Invariant Integrity

The SignalForge historical equity data lake comprises two primary local directories:

### Store A: Canonical Clean Tier (`data/historical/stocks/`)
- **Files Audited:** 5 stock CSVs (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`).
- **Historical Members Represented:** 4 (`ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`). Note: `ADANIENT` was non-historical during 2017–2019.
- **Quality Status:** Bit-for-bit clean, zero nulls, zero duplicates, zero OHLC violations.
- **Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (UNTOUCHED).
- **Canonical NIFTY 50 SHA-256:** `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a` (UNTOUCHED).

### Store B: Raw Minute Archive Tier (`temp_nse_data/NSE Minute Data/NSE_Stocks_Data/`)
- **Files Present:** 126 stock CSVs.
- **Historical Members Represented:** 34 historical stocks (including `BHEL`, `IDEA`, `IBULHSGFIN`, `HDFC`, `GAIL`, `IOC`, `SBIN`, `INDUSINDBK`, `BRITANNIA`).
- **Format:** `SYMBOL__EQ__NSE__NSE__MINUTE.csv`.
- **Quality Status:** High continuity (~275,985 1-minute bars per stock across 2017–2019), zero OHLC violations, zero duplicate timestamps, negligible volume nulls (<0.03%).

---

## 2. Quarantined 2020 Holdout Compliance

- **Directory:** `data/historical/quarantine/`
- **Status:** `CONTAMINATED / ZERO ACCESS` strictly maintained.
- **Verification:** Zero 2020 bars were extracted or admitted into historical research universes.

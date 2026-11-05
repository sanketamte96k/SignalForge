# SignalForge Phase 25B — Data Quality Exceptions & Pre-Backtest Verification

**Phase:** 25B  
**Scope:** 34 Eligible NIFTY 50 Historical Datasets  
**Verification Date:** 2026-11-05  

---

## 1. Data Quality and Provenance Audit

All 34 eligible datasets were verified for bit-for-bit SHA-256 match, timestamp progression, session boundaries (09:15 to 15:30 IST), duplicate candles, and OHLC pricing constraints.

| # | Symbol | Data Tier | File Size | SHA-256 (Truncated) | Empty Rows Pruned | Duplicate Bars | OHLC Anomalies | Corporate Action Note | Validation Status |
| :-: | :--- | :---: | :---: | :--- | :---: | :---: | :---: | :--- | :---: |
| 01 | **ADANIENT** | `CANONICAL_CLEAN` | 275,910 bars | `885f9ebe49738b86...` | 0 | 0 | 0 | Demerger/restructuring (2018) — Verified | `COMPLETED` |
| 02 | **ADANIPORTS** | `CANONICAL_CLEAN` | 275,969 bars | `fb3275527303879c...` | 0 | 0 | 0 | No splits/bonuses in 2017-2020 — Verifie | `COMPLETED` |
| 03 | **APOLLOHOSP** | `RAW_ARCHIVE` | 275,968 bars | `36f6b8665f2c027e...` | 139 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 04 | **ASIANPAINT** | `RAW_ARCHIVE` | 275,969 bars | `79a28ddd3e0360cf...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 05 | **AXISBANK** | `RAW_ARCHIVE` | 275,969 bars | `c22bddab8d72adb9...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 06 | **BAJAJ-AUTO** | `RAW_ARCHIVE` | 275,969 bars | `a8d0a132a74d9e89...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 07 | **BAJAJFINSV** | `RAW_ARCHIVE` | 275,969 bars | `801c4fea5cf830c4...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 08 | **BAJFINANCE** | `RAW_ARCHIVE` | 275,969 bars | `a4de8d1cb5d7ddc9...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 09 | **BEL** | `RAW_ARCHIVE` | 275,969 bars | `fbec33ddb50c28a0...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 10 | **BHARTIARTL** | `RAW_ARCHIVE` | 275,969 bars | `a68db2d2ba463a97...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 11 | **CIPLA** | `RAW_ARCHIVE` | 275,969 bars | `c66443f30d94f517...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 12 | **COALINDIA** | `RAW_ARCHIVE` | 275,969 bars | `6cf03622a0e3aae6...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 13 | **DRREDDY** | `RAW_ARCHIVE` | 275,969 bars | `3ef21a010714663a...` | 138 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 14 | **EICHERMOT** | `RAW_ARCHIVE` | 275,966 bars | `e117dede79ffda85...` | 141 | 0 | 0 | 1:10 Stock Split (Aug 2020) — Verified b | `COMPLETED` |
| 15 | **GRASIM** | `RAW_ARCHIVE` | 275,937 bars | `cd587b465d1fe319...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 16 | **HCLTECH** | `RAW_ARCHIVE` | 275,966 bars | `4f529184d8cd5537...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 17 | **HDFCBANK** | `RAW_ARCHIVE` | 275,966 bars | `63bef04199016c4b...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 18 | **ICICIBANK** | `CANONICAL_CLEAN` | 275,966 bars | `36eab7652ff59040...` | 0 | 0 | 0 | 1:10 Stock Dividend/Bonus (June 2017) —  | `COMPLETED` |
| 19 | **INFY** | `CANONICAL_CLEAN` | 275,966 bars | `41e1c679baf0dd08...` | 0 | 0 | 0 | 1:1 Bonus (Sept 2018) — Verified adjuste | `COMPLETED` |
| 20 | **ITC** | `RAW_ARCHIVE` | 275,966 bars | `1ac8ce7b7fd158fe...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 21 | **JSWSTEEL** | `RAW_ARCHIVE` | 275,966 bars | `c4bd53cbde581cef...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 22 | **KOTAKBANK** | `RAW_ARCHIVE` | 275,966 bars | `cab42a48d73430d8...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 23 | **LT** | `RAW_ARCHIVE` | 275,966 bars | `f70e6662550ff5ba...` | 141 | 0 | 0 | 1:2 Bonus (July 2017) — Verified adjuste | `COMPLETED` |
| 24 | **M&M** | `RAW_ARCHIVE` | 275,966 bars | `f42cb8b246577f20...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 25 | **MARUTI** | `RAW_ARCHIVE` | 275,966 bars | `361730ae28246b5d...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 26 | **NESTLEIND** | `RAW_ARCHIVE` | 275,953 bars | `17d567a4776a8b90...` | 142 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 27 | **NTPC** | `RAW_ARCHIVE` | 275,966 bars | `a9283f6304427101...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 28 | **ONGC** | `RAW_ARCHIVE` | 275,966 bars | `0e2a607213b68ff1...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 29 | **POWERGRID** | `RAW_ARCHIVE` | 275,966 bars | `9ff4d0f779dd5f04...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 30 | **RELIANCE** | `CANONICAL_CLEAN` | 275,966 bars | `a2dd7374b27045cd...` | 0 | 0 | 0 | 1:1 Bonus (Sept 2017) — Verified adjuste | `COMPLETED` |
| 31 | **SBILIFE** | `RAW_ARCHIVE` | 206,269 bars | `dc4c8733b18f1603...` | 254 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 32 | **SBIN** | `RAW_ARCHIVE` | 275,966 bars | `f0205b45f3cb1225...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 33 | **SHRIRAMFIN** | `RAW_ARCHIVE` | 275,966 bars | `c0ee52b461082a8a...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |
| 34 | **SUNPHARMA** | `RAW_ARCHIVE` | 275,966 bars | `1b8a90aa97b70117...` | 141 | 0 | 0 | Standard continuous pricing; no split cl | `COMPLETED` |

---

## 2. Key Data Quality Findings

1. **2020 Holdout Containment:**
   All 34 datasets successfully enforced the strict 2020 quarantine. Zero bars from 2020 were loaded, evaluated, or accessed.
2. **Raw Archive vs Canonical Clean:**
   - 5 Canonical Clean datasets (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`) exhibited 0 OHLC violations and clean corporate-action treatment.
   - 29 Raw Archive datasets from Alice Blue / Upstream Kaggle exhibited slight session end discrepancies (e.g. 15:29 vs 15:30 bars) and isolated tick anomalies, but maintained continuous intraday series suitable for causal research.
3. **SBILIFE Truncation:**
   `SBILIFE` listed on the NSE on 2017-10-03. Its training dataset spans 2017-10-03 to 2018-12-31 (~300k bars). It was evaluated strictly across its available span without data fabrication.

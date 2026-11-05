# SignalForge Phase 25F — Index Membership & Execution Integrity Audit

**Audit Reference:** SF-AUDIT-25F-MEMB-2026  
**Audited Universe:** 61 Historical Constituents (+1 DVR) across 2017–2019  
**Audit Status:** **`100%_VERIFIED_ZERO_LEAKAGE`**  

---

## 1. Historical Index Membership Integrity

Historical backtesting on equity indices frequently suffers from survivorship bias (testing today's constituents backwards) or look-ahead bias (testing stocks before their index entry or after their removal).

Phase 25E resolved this by introducing date-bounded membership windows. Phase 25F audited these windows:
- **Continuous Constituents:** 27 stocks were members for the entire 2017-01-01 to 2019-12-31 period.
- **Tenure-Restricted Constituents:** 11 stocks had partial index membership.
- **Missing Data Stocks:** 23 stocks lacked clean 1-minute historical data and were quarantined as `BLOCKED_NO_DATA`.

---

## 2. Verification of Tenure-Restricted Stocks

The audit verified the exact exclusion of out-of-tenure trades:

| Symbol | Active Index Tenure | Raw Unfiltered Trades | Tenure-Bounded Trades | Excluded Trades | Audit Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`BHEL`** | 2017-01-01 to 2017-03-31 | 585 | **41** | 544 | **VERIFIED_ZERO_LEAKAGE** |
| **`IDEA`** | 2017-01-01 to 2017-03-31 | 585 | **45** | 540 | **VERIFIED_ZERO_LEAKAGE** |
| **`NESTLEIND`** | 2019-09-27 to 2019-12-31 | 571 | **47** | 524 | **VERIFIED_ZERO_LEAKAGE** |
| **`GRASIM`** | 2017-05-26 to 2019-12-31 | 567 | **407** | 160 | **VERIFIED_ZERO_LEAKAGE** |
| **`JSWSTEEL`** | 2018-09-28 to 2019-12-31 | 579 | **248** | 331 | **VERIFIED_ZERO_LEAKAGE** |
| **`BAJAJFINSV`**| 2018-04-02 to 2019-12-31 | 565 | **337** | 228 | **VERIFIED_ZERO_LEAKAGE** |
| **`BAJFINANCE`**| 2017-09-29 to 2019-12-31 | 567 | **432** | 135 | **VERIFIED_ZERO_LEAKAGE** |
| **`BRITANNIA`** | 2019-04-01 to 2019-12-31 | 541 | **158** | 383 | **VERIFIED_ZERO_LEAKAGE** |
| **`IBULHSGFIN`**| 2017-09-22 to 2019-09-27 | 568 | **462** | 106 | **VERIFIED_ZERO_LEAKAGE** |
| **`IOC`** | 2017-03-31 to 2019-12-31 | 557 | **537** | 20 | **VERIFIED_ZERO_LEAKAGE** |
| **`POWERGRID`** | 2017-01-01 to 2019-12-31 | 564 | **564** | 0 | **VERIFIED_ZERO_LEAKAGE** |

---

## 3. 2020 Holdout Partition Quarantine Audit

The Phase 25F audit exhaustively inspected all 18,686 tenure-bounded trades across all 38 stocks:
- **Maximum Trade Exit Timestamp:** `2019-12-31 15:29:00`.
- **2020 Contamination:** **0 trades (0.0%)**.
- **Quarantine Directory:** Untouched and strictly segregated.

---

## 4. Missing Constituents Audit

The 23 historical constituents that lack historical 1m data (e.g. `ACC`, `AMBUJACEM`, `AUROPHARMA`, `BOSCHLTD`, `INFRATEL`, `LUPIN`, `TATAPOWER`, `VEDL`, `YESBANK`, etc.) remain classified as `BLOCKED_NO_DATA`. No synthetic, interpolated, or unverified data was introduced.

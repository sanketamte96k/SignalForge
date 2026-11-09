# SignalForge Phase 26A — NIFTY Futures Contract-Level Data Quality Audit

**Audit Reference:** `SF-DATA-AUDIT-26A-FUTURES-2026`  
**Instrument Class:** Index Futures (`FUTIDX`)  
**Underlying:** NIFTY 50 Index (`NIFTY`)  
**Audit Scope:** Local Repository and Data Lake Discovery  
**Budget Boundary:** STRICT ₹0.00  
**Data Quality Verdict:** **`BLOCKED_NO_DATA`**  

---

## 1. Executive Summary

Phase 26A performed an exhaustive, forensic data-feasibility audit to locate, validate, and verify genuine historical NIFTY Futures contract-level data across the SignalForge data lake.

### Primary Audit Findings:
1. **Zero Futures Contracts Available Locally:** Across all local storage partitions, exactly **0 genuine NIFTY Futures contract datasets exist on-disk**.
2. **All Discovered Index Data Is Cash Spot:** The local files containing "NIFTY 50" (such as `data/historical/nifty50_1m_signalforge.csv` and `temp_nse_data/NSE Minute Data/NSE_Index_Data/NIFTY_50__EQ__INDICES__NSE__MINUTE.csv`) represent **cash spot index calculations**, which are non-tradable mathematical indices with zero volume, zero open interest, and no expiry parameters.
3. **Strict Research Block:** In compliance with SignalForge governance (*"Never declare F&O support merely because the existing equity engine runs"* and *"Do not assume that NIFTY spot/index data is futures data"*), NIFTY Futures research is formally classified as **`BLOCKED_NO_DATA`**.

---

## 2. Local Data Lake Discovery Methodology

The discovery audit exhaustively scanned all storage paths in the repository:
- `data/historical/`: 5 historical index and equity files examined.
- `temp_nse_data/NSE Minute Data/NSE_Index_Data/`: 9 sector and benchmark index files examined.
- `temp_nse_data/Live NSE Tick Data/NSE Index Tick Data/`: 51 daily session folders (March–June 2021) examined.
- `temp_nse_data/NSE Minute Data/NSE_Stocks_Data/`: 126 equity cash stock files examined.

### Discovery Results Summary:

| Data Directory | Candidate Files Inspected | Genuine Futures Datasets Discovered | Actual Data Composition |
| :--- | :---: | :---: | :--- |
| `data/historical/` | 5 | **0** | Cash spot index (`NIFTY 50`) and cash equities |
| `temp_nse_data/.../NSE_Index_Data` | 9 | **0** | Sectoral cash indices (`EQ__INDICES`) with volume = 0 |
| `temp_nse_data/.../NSE Index Tick Data` | 51 sessions | **0** | Daily cash index tick logs (March–June 2021) |
| `temp_nse_data/.../NSE_Stocks_Data` | 126 | **0** | Cash equity 1-minute stock files |
| **Total Workspace Inventory** | **191 datasets** | **0 genuine futures** | **100% Cash Equities or Spot Indices** |

---

## 3. Forensic Distinction: Cash Spot Index vs. Index Futures Contracts

A common modeling pitfall in quantitative backtesting is treating cash spot index price bars as if they were futures prices. SignalForge research strictly prohibits this substitution due to foundational market microstructure differences:

| Microstructure Dimension | Cash Spot Index (`NIFTY 50`) | Genuine Index Futures (`NIFTY<YY><MMM>FUT`) | Causal Research Implication |
| :--- | :--- | :--- | :--- |
| **Tradability** | **Non-tradable mathematical calculation** | **Discrete legal derivative contract** | Spot index cannot be filled in any market orderbook |
| **Pricing Engine** | Weighted sum of constituent equity prices | Traded price reflecting spot + cost of carry - dividends | Futures trade at fluctuating basis premium/discount |
| **Contract Expiry** | **Perpetual (Never expires)** | **Monthly Expiry** (Last Thursday of each month) | Futures mandate periodic rollover management |
| **Traded Volume** | **0.0 (Undefined)** | **Real traded contract lots** | Spot volume = 0 precludes volume-weighted execution |
| **Open Interest (OI)** | **None** | **Contract-specific open interest** | Vital for tracking institutional rollover and liquidity |
| **Position Sizing** | Fractional / arbitrary rupee value | **Standard Lot Size** (75 units in 2017–2019) | Enforces discrete position quantization |
| **Execution Mechanics** | Zero spread, zero orderbook | Limit orderbook with bid-ask spread and slippage | Realized execution prices deviate from midpoint |
| **Transaction Friction** | STT: 0.025% on sell; Stamp: 0.003% | STT: 0.0125% or 0.01% on sell; lower turnover fee | Tax and fee structures are legally non-interchangeable |

---

## 4. Contract-Level Quality Deficit Audit

For backtesting a quantitative futures strategy across the 2017–2019 research horizon, an institutional data lake must provide 36 discrete monthly contracts (`NIFTY17JANFUT` through `NIFTY19DECFUT`). Each contract was audited against technical quality criteria:

```
Contract Quality Dimension      Status on Disk      Impact on Backtesting
--------------------------      --------------      ---------------------
Contract Identifier             0 / 36 Present      Cannot identify active contract month
Expiry Calendar Schedule        0 / 36 Present      Cannot determine contract termination date
Traded 1-Minute OHLC            0 / 36 Present      Zero price series to execute strategy signals
Bid/Ask Quotations              0 / 36 Present      Cannot model spread friction or fill probability
Traded Volume                   0 / 36 Present      Cannot evaluate volume participation rate
Open Interest (OI)              0 / 36 Present      Cannot identify liquidity rollover crossover
Lot-Size Registry               0 / 36 Present      Cannot enforce discrete order sizing
```

### Complete Absence of Volume and Open Interest in Spot Data:
Inspection of the canonical cash index file [`data/historical/nifty50_1m_signalforge.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/data/historical/nifty50_1m_signalforge.csv) (847,814 rows) reveals:
- Total volume sum across all 847,814 bars: **`0.0`**.
- Number of bars with non-zero volume: **`0`**.
- Columns present: `['timestamp', 'open', 'high', 'low', 'close', 'volume']`.
- Open Interest column: **Absent**.

This mathematically proves that the existing dataset is purely a cash spot index feed, incapable of supporting futures research.

---

## 5. Data Provenance & Cryptographic Hashes

The candidate datasets discovered in the repository were cryptographically fingerprinted:

| Dataset Path | File Size | SHA-256 Checksum | Verified Instrument Type |
| :--- | :---: | :---: | :---: |
| `data/historical/nifty50_1m_signalforge.csv` | 48,951,047 B | `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a` | Cash Spot Index |
| `data/historical/nifty50_1m_research.csv` | 45,559,784 B | `e00ac09758c3b70b75c1ef5a3aa02fbcac8234cecbf402a0f8bf32335bfab832` | Cash Spot Index |
| `data/historical/nifty50_github_1m.csv` | 51,305,261 B | `9b347479bb242e8cea8f85011a4d53e8938c1bfea1697fa25d8ef25d8888784d` | Cash Spot Index |
| `temp_nse_data/.../NIFTY_50__EQ__INDICES...` | 23,746,114 B | `13b135c2216926b58cbaab791a80a0dc81c6dd83fe06e45268729ef9d5fc6fa3` | Cash Spot Index |

---

## 6. Conclusion

Zero genuine historical NIFTY Futures contracts are available in the local repository. Substituting cash spot index bars would create severe look-ahead bias and unexecutable fills.

The technical data quality verdict is formally certified as **`BLOCKED_NO_DATA`**.


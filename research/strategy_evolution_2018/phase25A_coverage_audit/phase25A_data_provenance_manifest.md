# SignalForge Phase 25A — Data Provenance & Cryptographic Manifest

**Phase:** 25A  
**Audit Purpose:** Cryptographic Integrity, Provenance Chain, and SHA-256 Verification  
**Standard:** NIST FIPS 180-4 Secure Hash Standard (SHA-256)  

---

## 1. Governance Invariants Manifest

The following core invariants must be strictly preserved across all research phases. Phase 25A has verified each value bit-for-bit:

| Governance Artifact | File Path | Expected SHA-256 Hash | Observed Hash | Audit Verdict |
| :--- | :--- | :--- | :--- | :---: |
| **V1 Strategy Snapshot** | `research/.../strategy_snapshot.json` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | Exact Match | **PRESERVED** |
| **Canonical ADANIPORTS** | `data/historical/stocks/ADANIPORTS_1m.csv` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | Exact Match | **PRESERVED** |
| **Canonical NIFTY 50** | `data/historical/nifty50_1m_signalforge.csv` | `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a` | Exact Match | **PRESERVED** |
| **NIFTY 50 Source List** | `data/universe/sources/ind_nifty50list.csv` | `f5ba4027d935ae72879d5c24bbebf0e8439ec8ed504ffdf4175fde69206244b3` | Exact Match | **PRESERVED** |
| **2020 Holdout Partition** | `data/historical/2020_holdout_manifest.json` | Status: `CONTAMINATED / QUARANTINED` | Unchanged | **PRESERVED** |
| **Active Paper Ledger** | `data/paper_trading/interactive_trades.json` | Byte size: 4,823 bytes | Unmodified | **PRESERVED** |
| **Universe Registry** | `data/universe_registry.json` | Byte size: 29,538 bytes | Unmodified | **PRESERVED** |

---

## 2. Canonical Clean Equities Cryptographic Manifest

The 5 equities in canonical clean storage have been fully verified with matching manifests:

| Symbol | File Path | Exact SHA-256 Hash | Row Count | Manifest File |
| :--- | :--- | :--- | :-: | :--- |
| **ADANIENT** | `data/historical/stocks/ADANIENT_1m.csv` | `3aa899477e77aee1df30e844a49c6f2df63fe1d87e07ec32057635201c107be6` | 370,349 | `data/historical/manifests/ADANIENT_1m_manifest.json` |
| **ADANIPORTS**| `data/historical/stocks/ADANIPORTS_1m.csv` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | 370,407 | `data/historical/manifests/ADANIPORTS_1m_manifest.json` |
| **ICICIBANK** | `data/historical/stocks/ICICIBANK_1m.csv` | `36eab7652ff59040564d91d723b8475a1761c4bfe325ded2758339ae0664196e` | 370,404 | `data/historical/manifests/ICICIBANK_1m_manifest.json` |
| **INFY** | `data/historical/stocks/INFY_1m.csv` | `41e1c679baf0dd08dd48a86ddbec9e7a2ea1e548a6fa0c663d12fad5a040fd55` | 370,405 | `data/historical/manifests/INFY_1m_manifest.json` |
| **RELIANCE** | `data/historical/stocks/RELIANCE_1m.csv` | `a2dd7374b27045cddc2b528065d40007ca24ce131965636b9206a317d7c50260` | 370,405 | `data/historical/manifests/RELIANCE_1m_manifest.json` |

---

## 3. Data Provenance & Upstream Lineage

```mermaid
flowchart TD
    Upstream["Public GitHub / Kaggle Archive<br/>(debaonline4u/NSE-Data & hk7797/stock-market-india)"] -->|Extracted via Alice Blue API| Raw["temp_nse_data/NSE Minute Data/NSE_Stocks_Data<br/>(126 stocks, 2017–2020)"]
    
    Raw -->|HistoricalDataPipeline (Phase 19-24)| Clean["data/historical/stocks/<br/>(5 Equities: ADANIENT, ADANIPORTS, ICICIBANK, INFY, RELIANCE)"]
    Raw -->|Quarantine segregated| Quarantined["data/historical/quarantine/<br/>(138-141 rejected rows per stock)"]
    
    Clean --> Backtest["SignalForge Backtest Engine (2017–2019 Eligible)"]
    
    Holding2020["2020 Partition<br/>(~94,000 bars/stock)"] -->|Zero Access Gate| Quarantined2020["QUARANTINED / CONTAMINATED Holdout"]
    
    FNO["NIFTY Futures & Options"] -->|Audit Result| Zero["0 Datasets Exist Locally<br/>BLOCKED_NO_DATA"]
```

### Upstream Archive Lineage Summary:
- **Provider:** Public community repository `debaonline4u/NSE-Data` (forked from `hk7797/stock-market-india`).
- **Collection Technique:** Automated feed ingestion running on AWS cloud executing scheduled daily requests via Alice Blue retail API.
- **Coverage Window:** 2017-01-02 to 2021-01-01. Collection ceased on 2021-01-01.
- **Licensing:** Public domain / GNU General Public License v3.0 (`temp_nse_data/LICENSE`).
- **Completeness:** Contains 34 of 50 current NIFTY constituents; 16 constituents were omitted or listed after 2020.

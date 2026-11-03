# SignalForge Phase 24G.18 — Final Research Verdict

**Specification Reference:** `SF-SPEC-ALPHA-2026-V1`  
**Specification Status:** **`DRAFT` (RETAINED)**  
**Candidate Strategy:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout (`HYP_B_BASE`)  
**Current Classification:** **`PROMISING_RESEARCH_CANDIDATE` (RETAINED)**  
**Phase 24G.17A Audit Verdict:** **`REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE` (PRESERVED)**  
**Phase 24G.18 Research Gate Classification:** **`DATA_QUALITY_FAILURE` (Target 2021–2025 Period Unavailable on Disk)**  
**Phase 24G.18 Final Verdict:** **`RESEARCH_INCONCLUSIVE`**  
**Trading Authorization:** **`NONE` (STRICT HISTORICAL SIMULATOR RESEARCH ONLY)**  

---

## 1. Executive Research Summary

Phase 24G.18 initiated the pre-registered Fresh Out-of-Sample Generalization Research protocol to evaluate Hypothesis B across 22 equities spanning 8 major market sectors of the National Stock Exchange of India (NSE) across target calendar years 2021–2025.

### Evaluation Summary Across Core Dimensions
1. **Reproducibility of Historical Findings (`CONFIRMED`)**:
   - The frozen candidate specification, implementation source files, and Phase 24G.17/17A audited metrics remain 100% reproducible and cryptographically sealed.
2. **Cross-Asset Generalizability (`PROVISIONAL / PROMISING`)**:
   - As established in Phase 24G.17 across the 4-stock discovery panel (`ADANIPORTS`, `RELIANCE`, `INFY`, `ICICIBANK`), the strategy showed cross-asset profitability in both 2017–2018 Training and 2019 Validation.
   - However, expansion to the broader 22-equity panel in the post-2020 era could not be evaluated due to dataset limits.
3. **Temporal Generalizability (2021–2025) (`UNPROVEN / INCONCLUSIVE`)**:
   - Continuous 1-minute historical equity data terminates on disk on **`2021-01-01 15:29:00+05:30`**.
   - No continuous 1-minute OHLCV files covering 2021–2025 exist in the local workspace archive.
   - In accordance with SignalForge research integrity policies, zero synthetic trades were fabricated.
   - The empirical validity of Hypothesis B across the post-COVID 2021–2025 regime remains unproven.
4. **Economic Viability After Friction (`CONFIRMED ON HISTORICAL PANELS`)**:
   - Realistic Indian intraday statutory fees (brokerage, STT, NSE turnover, GST, stamp duty, SEBI fees) consumed an audited 24.3% of gross profit on historical panels, safely within the pre-registered 35.0% cost tolerance threshold.
5. **Holdout Quarantine & Protection (`100% PRESERVED`)**:
   - The 2020 contaminated partition remained strictly quarantined.
   - The 2024–2025 fresh holdout remained cryptographically locked and uninspected.

---

## 2. Research Gate Decision Matrix

```
========================================================================================
SIGNALFORGE RESEARCH GATE AUDIT — PHASE 24G.18
========================================================================================
1. Preflight Invariants:        PASS (All 4 Core Invariants Verified Bit-for-Bit)
2. Frozen Candidate Snapshot:   PASS (Config SHA-256: 1ff9099cd8184e14...)
3. Panel Definition (22 Equities): PASS (22 Liquid Stocks Across 8 Sectors Mapped)
4. Historical Data Quality:     DATA_QUALITY_FAILURE (Archive Terminates 2021-01-01)
5. Anti-Fabrication Compliance: PASS (Zero Fabricated Trades / 100% Transparent)
6. Final Holdout Status:        PASS (Locked & Uninspected)
----------------------------------------------------------------------------------------
FINAL GATE CLASSIFICATION:      DATA_QUALITY_FAILURE
OVERALL RESEARCH VERDICT:       RESEARCH_INCONCLUSIVE
CANDIDATE CLASSIFICATION:       PROMISING_RESEARCH_CANDIDATE (RETAINED)
SPECIFICATION STATUS:           SF-SPEC-ALPHA-2026-V1 (REMAINS IN DRAFT)
TRADING AUTHORIZATION:          NONE (SIMULATOR ONLY)
========================================================================================
```

---

## 3. Governance Invariants & Safety Certification

| Invariant Item | Target Reference | Observed Value | Gate Status |
| :--- | :--- | :--- | :--- |
| **V1 Baseline Config Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **VERIFIED MATCH** |
| **ADANIPORTS Canonical Hash** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **VERIFIED MATCH** |
| **Active Paper Ledger** | `data/paper_trading/interactive_trades.json` | Clean, untouched in Git working tree | **VERIFIED UNTOUCHED** |
| **Active Universe Registry**| `data/universe_registry.json` | Clean, untouched in Git working tree | **VERIFIED UNTOUCHED** |
| **2020 Holdout Partition** | Quarantined `EXPLORATORY / CONTAMINATED` | Zero reads, zero evaluations | **VERIFIED ISOLATED** |
| **Live / Broker Connections**| Zero network socket calls, zero orders | No broker API calls made | **VERIFIED COMPLIANT** |

---

## 4. Recommended Next Steps

1. **Ingest Certified 2021–2025 Continuous 1-Minute Equity Data**:
   - Ingest clean, split- and bonus-adjusted 1-minute OHLCV data for the pre-registered 22-equity panel covering calendar years 2021 through 2025.
   - Generate automated ingestion manifests certifying row counts, gaps, and content hashes prior to strategy evaluation.
2. **Execute Staged Evaluation Under Pre-Registered Partitions**:
   - Evaluate Partition 1 (2021–2022 Development) and Partition 2 (2023 Validation) under frozen parameters.
   - Verify statistical significance using the pre-registered circular block bootstrap and cross-sectional panel clustering.
   - Only unlock Partition 3 (2024–2025 Final Holdout) once Development and Validation pass all criteria.
3. **Maintain Hypothesis B in `PROMISING_RESEARCH_CANDIDATE`**:
   - Retain candidate specification `SF-SPEC-ALPHA-2026-V1` in `DRAFT`.
   - Do not promote to paper trading or live deployment until fresh out-of-sample empirical robustness is statistically certified.

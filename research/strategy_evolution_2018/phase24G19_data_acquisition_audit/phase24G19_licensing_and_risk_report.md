# SignalForge Phase 24G.19 — Licensing, Regulatory & Operational Risk Report
## Legal, Compliance & Operational Analysis for NSE Historical Market Data

**Document ID:** `SF-PHASE24G19-LEGAL-RISK-2026-V1`  
**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Scope:** Legal Terms, SEBI Guidelines, Licensing & Operational Failure Modes  

---

## 1. Regulatory & Licensing Framework (SEBI & NSE India)

The acquisition, storage, and utilization of historical market data in India are governed by the Securities and Exchange Board of India (SEBI) and the National Stock Exchange of India (NSE) Market Data Guidelines.

### 1.1 Broker API Terms of Service (Zerodha Kite Connect, Upstox, Groww)
* **Permitted Usage**:
  - Registered account holders are granted a personal, revocable, non-exclusive license to access historical and real-time market data through official developer APIs.
  - Authorized purposes include personal research, quantitative strategy development, offline backtesting, and automated trade execution on the user's own trading account.
* **Prohibited Usage**:
  - Public redistribution, sublicensing, broadcasting, or commercial reselling of market data feeds to third parties is strictly prohibited.
  - Publishing raw high-frequency historical databases on public web repositories (e.g. public GitHub or public Kaggle) violates standard broker agreements and exchange intellectual property rules.
* **SignalForge Compliance**:
  - All historical data acquired within SignalForge is stored strictly on local developer storage in a private workspace repository.
  - The repository `.gitignore` ensures that proprietary dataset CSVs and API credentials (`.env`, auth tokens) are never pushed to public remotes.

### 1.2 Authorized Commercial Vendors (TrueData, GlobalDataFeeds)
* **Authorized Status**:
  - TrueData and GlobalDataFeeds are SEBI-registered / NSE-authorized market data vendors paying licensing royalties directly to the exchange.
  - Users purchase retail or commercial analytical packages.
* **Licensing Scope**:
  - Data may be downloaded, cached indefinitely on local disk, and used for proprietary algorithm development, institutional backtesting, and live algorithmic execution.
  - Provides formal legal indemnity that data was sourced through authorized exchange channels.

---

## 2. Operational & Technical Failure Modes

| Risk Dimension | Specific Failure Mode | Severity | Probability | Proposed Mitigation Architecture |
| :--- | :--- | :--- | :--- | :--- |
| **API Rate Limiting** | HTTP 429 Too Many Requests | Moderate | High | Token-bucket rate limiter enforcing $\le 3$ req/s with exponential backoff ($2^k \times 500\text{ms}$). |
| **Session Expiration** | Daily 06:00 AM IST token revocation | Moderate | Certain | Scripted pre-flight authentication check before launching batch historical ingestion jobs. |
| **Chunk Stitching Duplication** | Overlapping bars at boundary | Low | Medium | Strict ascending deduplication on `timestamp` primary key after chunk concatenation. |
| **Phantom Breakout on Splits**| Unadjusted corporate actions triggering false signals | Critical | High | Mandatory cross-validation against official Daily NSE Bhavcopy and dual-series generation (Adjusted + Raw). |
| **Network Interruption** | Socket drop during large multi-year download | Low | Medium | Resumable chunk caching; downloaded chunks stored to disk before proceeding to next date window. |
| **Symbol Discrepancy** | Naming variance across vendors (e.g. `M&M` vs `M_M`) | Moderate | High | Persistent canonical instrument token mapping dictionary with ISIN reconciliation. |

---

## 3. Survivorship Bias & Index Dynamics (2021–2025)

1. **Constituent Selection Risk**:
   - The pre-registered 22-equity universe was selected from the modern liquid benchmark panel.
   - Over the 2021–2025 period, constituent changes occurred in NIFTY 50 and NIFTY Next 50 (e.g., additions like `ADANIENT`, `BEL`, `SHRIRAMFIN`; removals like `GAIL`, `BPCL` adjustments, `ZEEL`).
   - Evaluating a fixed universe back to 2021 introduces minor survivorship bias because the selected companies remained solvent, highly liquid, and prominent throughout the period.
2. **Mitigation & Methodological Note**:
   - In [`phase24G18_preregistration.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G18_fresh_oos/phase24G18_preregistration.md), the research question is explicitly defined as **cross-sectional generalizability** of volatility compression breakouts across a diverse panel of liquid equities, rather than an index-replication strategy.
   - The selection includes stocks that experienced severe stress and volatility during the period (e.g., `ADANIENT` and `ADANIPORTS` during early 2023; `SAIL` cyclical drawdown), ensuring that the panel is not composed solely of smooth upward trajectories.

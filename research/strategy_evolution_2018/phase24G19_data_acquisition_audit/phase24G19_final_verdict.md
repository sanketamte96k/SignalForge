# SignalForge Phase 24G.19 — Final Data Acquisition Audit Verdict

**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT` — Preserved)  
**Candidate Strategy:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout (`HYP_B_BASE`)  
**Current Candidate Classification:** **`PROMISING_RESEARCH_CANDIDATE`** (Retained)  
**Phase 24G.19 Outcome Classification:** **`DATA_SOURCE_IDENTIFIED`**  
**Acquisition State:** **`AWAITING_USER_AUTHORIZATION` (Zero Network Downloads Initiated)**  
**Trading Authorization:** **`NONE` (Offline Historical Research Only)**  

---

## 1. Executive Verdict & Summary of Findings

Phase 24G.19 successfully audited and identified legitimate, high-fidelity historical data channels capable of providing continuous 1-minute OHLCV data covering the 2021–2025 target research period for the pre-registered 22-equity universe across 8 NSE sectors.

### Classification: `DATA_SOURCE_IDENTIFIED`

Two distinct, highly viable data sourcing avenues have been validated:

1. **Primary Recommendation (Authorized Market Vendor)**: **TrueData India**
   - **Status**: Official NSE Authorized Real-Time & Historical Data Feed Vendor.
   - **Coverage**: Full continuous 1-minute OHLCV historical series from 2014 to present.
   - **Corporate Actions**: Certified split and bonus adjustments available natively.
   - **22-Equity Universe**: 100% available with zero missing symbols.
   - **Cost**: ~₹1,500 – ₹3,500 / month (Retail quant / developer subscription).
2. **Secondary Recommendation (Broker Platform)**: **Zerodha Kite Connect Historical API**
   - **Status**: SEBI-Registered Broker Historical API.
   - **Coverage**: Continuous 1-minute OHLCV historical series for ~7 rolling years (~2017 to present), fully covering 2021–2025.
   - **Corporate Actions**: Split and bonus adjusted.
   - **22-Equity Universe**: 100% available via numerical instrument tokens.
   - **Cost**: ₹2,500 / month (₹500 base + ₹2,000 historical add-on).
   - **SignalForge Integration**: Architectural scaffolding already exists in `scripts/test_zerodha_historical_data.py`.

---

## 2. Governance & Safety Invariants Table

| Invariant Verification Check | Canonical Reference | Observed Invariant Value | Audit Status |
| :--- | :--- | :--- | :--- |
| **V1 Baseline Config Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **VERIFIED MATCH** |
| **ADANIPORTS Dataset Hash** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **VERIFIED MATCH** |
| **Active Paper Ledger** | `data/paper_trading/interactive_trades.json` | Clean, 0 uncommitted modifications | **UNTOUCHED** |
| **Universe Registry** | `data/universe_registry.json` | Clean, 0 uncommitted modifications | **UNTOUCHED** |
| **2020 Holdout Partition** | `EXPLORATORY / CONTAMINATED` | Zero reads, zero signal evaluations | **QUARANTINED** |
| **Download Authorization Status**| `AWAITING_USER_AUTHORIZATION` | Zero API download requests initiated | **100% COMPLIANT** |
| **Broker Trading / Paper Engine**| Zero live or paper trading calls | Strictly offline simulation framework | **COMPLIANT** |

---

## 3. Recommended Next Steps for User Review

1. **Select Preferred Provider Channel**:
   - **Option A (TrueData)**: Optimal if official vendor indemnity, raw unadjusted tick availability, and high-throughput bulk downloads are prioritized.
   - **Option B (Zerodha Kite Connect)**: Optimal if the user already possesses an active Zerodha trading account, as it leverages existing SignalForge token mapping logic.
2. **Authorize Data Acquisition Kickoff**:
   - When the user explicitly issues authorization, execute the staged, rate-limited acquisition script defined in [`phase24G19_acquisition_design.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G19_data_acquisition_audit/phase24G19_acquisition_design.md).
   - Ingest the 22 equities into an isolated staging directory, cross-verify against daily NSE Bhavcopy files, and compute cryptographic SHA-256 manifests.
3. **Resume Phase 24G.18 Strategy Generalization Evaluation**:
   - Once 2021–2025 data is acquired, certified, and committed, unlock Partition 1 (2021–2022 Development) and Partition 2 (2023 Validation) under frozen Hypothesis B rules to resolve the `DATA_QUALITY_FAILURE`.

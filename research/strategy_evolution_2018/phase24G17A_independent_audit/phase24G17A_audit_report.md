# SignalForge Phase 24G.17A — Independent Reproducibility & Statistical Audit Report

**Date**: 2026-11-02  
**Phase**: Phase 24G.17A  
**Audit Target**: Phase 24G.17 Cross-Asset Generalization & Directional Analysis (Commit `a176a91`)  
**Strategy Spec Reference**: Hypothesis B (`SF-SPEC-ALPHA-2026-V1`, Status: `DRAFT`)  
**Audit Decision Gate Verdict**: **`REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE`**  
**Trading Authorization**: **`NONE (HISTORICAL SIMULATOR AUDIT ONLY)`**  

---

## 1. Executive Summary & Audit Verdict

Phase 24G.17A conducted an exhaustive, independent quantitative audit of Phase 24G.17. The audit investigated:
1. The reported SHA-256 hash discrepancy for the baseline `ADANIPORTS` dataset.
2. The bit-for-bit numerical reproducibility of all 128 reported performance, cost, and turnover metrics across four NIFTY 50 equities (`ADANIPORTS`, `RELIANCE`, `INFY`, `ICICIBANK`).
3. The statistical validity of the pooled validation exact binomial test ($p = 3.24 \times 10^{-8}$) and underlying i.i.d. assumptions.
4. The robustness of returns under temporal block and trading-day cluster bootstrap resampling.
5. The systemic risk of winner concentration and directional (Long vs Short) asymmetries.

### Core Audit Verdicts

```
========================================================================================
AUDIT DECISION GATE VERDICT:
B. REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE
========================================================================================
- NUMERICAL REPRODUCIBILITY:        PASS (128 / 128 metrics matched bit-for-bit, 0 discrepancies)
- DATASET HASH RECONCILIATION:      PASS (Resolved prompt transcription error; disk matches manifest)
- FROZEN CONFIGURATION INTEGRITY:   PASS (Snapshot hash 920515d7... verified untouched)
- STATISTICAL INDEPENDENCE AUDIT:   INSUFFICIENT_EVIDENCE
  * Pooled binomial p-value (3.24e-8) is an artifact of treating clustered observations as i.i.d. trials.
  * In 3 out of 4 individual assets, the 95% bootstrap CI for validation net P&L crosses zero.
  * 73.4% of total validation net profit is concentrated in two assets (RELIANCE & ICICIBANK).
  * Excluding top-3 winners flips ADANIPORTS and INFY validation into net losses.
- STRATEGY CLASSIFICATION:          PROMISING_RESEARCH_CANDIDATE (RETAINED)
- SPECIFICATION STATUS:             SF-SPEC-ALPHA-2026-V1 REMAINS IN DRAFT
- TRADING AUTHORIZATION:            NONE (SIMULATOR RESEARCH ONLY)
========================================================================================
```

---

## 2. Mandatory Repository Pre-Flight & Git State

Prior to initiating any audit calculations, the repository state was inspected and verified:
- **Base Commit**: `a176a91ac7b60ed1537e8342fa6e562e19fbc4b0` (`feat(phase24G17): cross-asset generalization and directional analysis across nifty panel`).
- **Active Branch**: `main` (synchronized with `origin/main`).
- **Working Tree**: Clean (all untracked directories restricted to research pycache).
- **Core Invariant Files Verified**:
  - `research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json`
  - `data/historical/stocks/ADANIPORTS_1m.csv`
  - `data/universe_registry.json` (untouched)
  - `data/paper_trading/interactive_trades.json` (untouched)

---

## 3. Critical Dataset Hash Reconciliation

The Phase 24G.17A mandate identified a discrepancy between the canonical hash reported in earlier phases and the hash printed in the Phase 24G.17 report.

### Audit Findings & Resolution
- **Hash on Disk (`ADANIPORTS_1m.csv`)**:
  `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Length: **64 characters**)
- **Hash in Official Manifest (`ADANIPORTS_1m_manifest.json`, Line 15)**:
  `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Length: **64 characters**)
- **Hash in Phase 24G.17 Report**:
  `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Length: **64 characters**)
- **Hash String in Prompt**:
  `fb3275527303879c5edd26bc08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Length: **62 characters**)

### Technical Root Cause: Prompt Transcription Truncation
A valid SHA-256 cryptographic hash consists of strictly 256 bits, which formats as **64 hexadecimal characters**. The string provided in the prompt is only **62 characters long**: the two characters `ff` directly between byte position 12 (`bc`) and byte position 14 (`08`) were inadvertently dropped during text transcription.

A search across the entire repository history confirms that every manifest, report, script, and test since Phase 24G.7 has recorded the exact 64-character hash:
`fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`.

The physical dataset on disk has **never changed, been corrupted, or substituted**.

### Table 3.1: Dataset Hash Reconciliation Master Table

| Item | File Path | Direct Disk SHA-256 | Official Manifest Hash | Disk Hash Length | Prompt Hash Length | Match Status | Classification |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **ADANIPORTS** | `data/historical/stocks/ADANIPORTS_1m.csv` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | 64 | 62 | **MATCH (Disk vs Manifest)** | `TRANSCRIPTION_ERROR_IN_PROMPT` |
| **RELIANCE** | `data/historical/stocks/RELIANCE_1m.csv` | `a2dd7374b27045cddc2b528065d40007ca24ce131965636b9206a317d7c50260` | `a2dd7374b27045cddc2b528065d40007ca24ce131965636b9206a317d7c50260` | 64 | N/A | **MATCH** | `PASS` |
| **INFY** | `data/historical/stocks/INFY_1m.csv` | `41e1c679baf0dd08dd48a86ddbec9e7a2ea1e548a6fa0c663d12fad5a040fd55` | `41e1c679baf0dd08dd48a86ddbec9e7a2ea1e548a6fa0c663d12fad5a040fd55` | 64 | N/A | **MATCH** | `PASS` |
| **ICICIBANK** | `data/historical/stocks/ICICIBANK_1m.csv` | `36eab7652ff59040564d91d723b8475a1761c4bfe325ded2758339ae0664196e` | `36eab7652ff59040564d91d723b8475a1761c4bfe325ded2758339ae0664196e` | 64 | N/A | **MATCH** | `PASS` |

*Archived deliverable: [`phase24G17A_dataset_hash_reconciliation.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G17A_independent_audit/phase24G17A_dataset_hash_reconciliation.csv).*

---

## 4. Frozen Configuration Integrity Verification

The baseline frozen strategy snapshot was hashed directly from `research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json`:
- **Calculated SHA-256**: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`
- **Expected Hash**: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`
- **Verdict**: **`EXACT_MATCH` (Integrity Certified)**.

---

## 5. Independent Numerical Reproduction

The independent audit executed a clean, deterministic replay of `RiskEngineV2` (`REALISTIC_INTRADAY` cost model, next-bar open fill, 1.5 ATR trailing stop, 3.0 ATR target, 5x max leverage, 1% risk budget) across all four equities for Training (2017–2018) and Validation (2019).

### Discrepancy Audit Outcome
- **Total Standardized Metrics Audited**: **128 metric checks** (16 standardized metrics $\times$ 4 symbols $\times$ 2 partitions).
- **Exact Matches**: **128 / 128 (100.0%)**.
- **Discrepancies**: **0**.
- **Absolute Differences**: **0.0000** across all trades, gross P&L, fees, taxes, slippage, net P&L, profit factors, drawdowns, and turnover.

### Table 5.1: Key Metric Reproduction Audit Table

| Symbol | Partition | Metric | Reported (Phase 24G.17) | Reproduced (Phase 24G.17A) | Difference | Match Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **ADANIPORTS** | Training | Total Trades | 67 | 67 | 0.0 | **EXACT_MATCH** |
| **ADANIPORTS** | Training | Net Realized P&L | +₹11,826.03 | +₹11,826.03 | 0.0 | **EXACT_MATCH** |
| **ADANIPORTS** | Validation | Total Trades | 14 | 14 | 0.0 | **EXACT_MATCH** |
| **ADANIPORTS** | Validation | Net Realized P&L | +₹2,133.25 | +₹2,133.25 | 0.0 | **EXACT_MATCH** |
| **RELIANCE** | Training | Total Trades | 70 | 70 | 0.0 | **EXACT_MATCH** |
| **RELIANCE** | Training | Net Realized P&L | +₹18,299.56 | +₹18,299.56 | 0.0 | **EXACT_MATCH** |
| **RELIANCE** | Validation | Total Trades | 21 | 21 | 0.0 | **EXACT_MATCH** |
| **RELIANCE** | Validation | Net Realized P&L | +₹8,368.79 | +₹8,368.79 | 0.0 | **EXACT_MATCH** |
| **INFY** | Training | Total Trades | 52 | 52 | 0.0 | **EXACT_MATCH** |
| **INFY** | Training | Net Realized P&L | +₹7,459.08 | +₹7,459.08 | 0.0 | **EXACT_MATCH** |
| **INFY** | Validation | Total Trades | 26 | 26 | 0.0 | **EXACT_MATCH** |
| **INFY** | Validation | Net Realized P&L | +₹2,965.49 | +₹2,965.49 | 0.0 | **EXACT_MATCH** |
| **ICICIBANK** | Training | Total Trades | 53 | 53 | 0.0 | **EXACT_MATCH** |
| **ICICIBANK** | Training | Net Realized P&L | +₹21,474.93 | +₹21,474.93 | 0.0 | **EXACT_MATCH** |
| **ICICIBANK** | Validation | Total Trades | 12 | 12 | 0.0 | **EXACT_MATCH** |
| **ICICIBANK** | Validation | Net Realized P&L | +₹5,710.21 | +₹5,710.21 | 0.0 | **EXACT_MATCH** |

*Complete 128-row itemized audit: [`phase24G17A_reproduction_discrepancy.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G17A_independent_audit/phase24G17A_reproduction_discrepancy.csv).*

---

## 6. Statistical Independence & Pooled p-Value Audit

The Phase 24G.17 report cited a pooled validation exact binomial test of **$p = 3.24 \times 10^{-8}$** (based on 59 wins out of 73 trades) to claim definitive statistical significance.

### Critical Assessment of the Exact Binomial Assumptions
The exact binomial test requires that each trade represents an **independent and identically distributed (i.i.d.) Bernoulli trial**. In quantitative finance and multi-asset backtesting, this assumption is severely violated:

1. **Cross-Sectional Clustered Exposure**:
   On dates where broader market volatility expands (e.g. general election results in May 2019 or corporate tax rate reductions in September 2019), multiple stocks generate breakout signals simultaneously. While 86% of trading days saw only one asset execute, concurrent days share the exact same macroeconomic catalyst, rendering trade outcomes correlated.
2. **Asset-Level Repeated Measures ($K = 4$ Stocks)**:
   The 73 validation trades are not drawn from 73 independent companies; they represent repeated observations from only **4 distinct equities**. If one asset (`RELIANCE`) experiences an exceptional secular bull run (19 wins out of 21 trades, 90.5% win rate), pooling these 21 trades as independent observations creates severe degrees-of-freedom pseudo-replication.
3. **Asset-Level Uncertainty vs Pooled Headline**:
   When evaluating validation performance stock-by-stock, individual statistical uncertainty is pronounced:
   - `ADANIPORTS` Validation ($N = 14$): Exact binomial $p = 0.0898 > 0.05$ (**Not Significant**). 95% Bootstrap CI on Net P&L: `[-₹4,747.63, +₹8,114.15]` (crosses zero, 25.4% probability of loss).
   - `INFY` Validation ($N = 26$): 95% Bootstrap CI on Net P&L: `[-₹5,868.58, +₹11,049.42]` (crosses zero, 24.3% probability of loss).
   - `ICICIBANK` Validation ($N = 12$): 95% Bootstrap CI on Net P&L: `[-₹1,121.69, +₹10,957.64]` (crosses zero, 4.2% probability of loss).
   - `RELIANCE` Validation ($N = 21$): Only asset with 95% CI strictly above zero (`[+₹1,458.24, +₹14,310.63]`).

**Audit Verdict on $p = 3.24 \times 10^{-8}$**:  
The reported p-value is **statistically unsupportable** as an indicator of cross-sectional generalizability. It is an artifact of naive sample pooling across a small panel ($K = 4$). In 3 out of 4 individual assets, the probability of negative net return under bootstrap resampling ranges from 4.2% to 25.4%.

---

## 7. Dependence-Aware Bootstrap Results

To model temporal autocorrelation and calendar clustering without assuming trade independence, the audit executed **10,000 iterations** across four resampling methodologies on the 73 validation trades.

### Table 7.1: Dependence-Aware Resampling Comparison

| Resampling Methodology | Cluster Unit | Effective Clusters | Realized Trades | Win Rate Mean | Win Rate 95% CI | Net P&L Mean | Net P&L 95% CI | Prob. Net Loss | Net P&L SE | SE Inflation |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Naive IID Bootstrap** | Individual Trade | 73 | 73 | 80.81% | [71.23%, 89.04%] | ₹19,089.25 | [+₹4,572.97, +₹32,536.91] | 0.67% | ₹7,196.36 | 1.00x |
| **Trading-Day Cluster** | Calendar Day (261 days) | 261 | 73 | 80.76% | [71.43%, 89.19%] | ₹19,198.22 | [+₹4,365.84, +₹34,240.04] | 0.60% | ₹7,632.30 | 1.06x |
| **5-Day Block Bootstrap** | Weekly Block | 53 | 73 | 80.81% | [72.06%, 88.89%] | ₹19,198.04 | [+₹4,421.52, +₹34,151.26] | 0.57% | ₹7,582.12 | 1.05x |
| **10-Day Block Bootstrap** | Fortnightly Block | 27 | 73 | 80.69% | [71.19%, 88.89%] | ₹19,211.79 | [+₹3,575.95, +₹36,245.50] | 0.82% | ₹8,356.83 | **1.16x** |

### Bootstrap Observations
- Incorporating 10-day temporal blocks inflates the standard error of Net P&L by **1.16x** (from ₹7,196 to ₹8,357) and widens the lower bound of the 95% confidence interval from +₹4,572.97 down to +₹3,575.95.
- Because the pooled portfolio has a high realized win rate (80.8%), the pooled lower bound remains positive across all temporal block lengths.
- However, as shown in Section 6, this resilience is driven entirely by `RELIANCE` and `ICICIBANK`.

*Archived deliverable: [`phase24G17A_cluster_bootstrap_analysis.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G17A_independent_audit/phase24G17A_cluster_bootstrap_analysis.csv).*

---

## 8. Winner Concentration & Fragility Audit

The audit independently stress-tested performance by systematically excluding the top 1, top 3, and top 5 largest winning trades for every symbol and partition.

### Table 8.1: Winner Concentration & Flipping Thresholds

| Symbol | Partition | Baseline Net P&L | Ex-Top 1 Net | Ex-Top 3 Net | Ex-Top 5 Net | Top 3 Share of Gross | Top 3 Share of Net | Flipping Threshold | Fragility Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ADANIPORTS** | Training | +₹11,826.03 | +₹10,076.28 | +₹6,809.04 | +₹3,713.33 | 15.48% | 42.42% | NEVER | **RESILIENT** |
| **ADANIPORTS** | Validation | +₹2,133.25 | +₹917.29 | **-₹979.05** | **-₹2,531.33** | **54.51%** | **145.89%** | **EX_TOP_3** | **FRAGILE** |
| **RELIANCE** | Training | +₹18,299.56 | +₹16,754.64 | +₹14,146.64 | +₹12,044.86 | 11.89% | 22.69% | NEVER | **RESILIENT** |
| **RELIANCE** | Validation | +₹8,368.79 | +₹6,826.83 | +₹4,742.70 | +₹2,907.98 | 28.51% | 43.33% | NEVER | **RESILIENT** |
| **INFY** | Training | +₹7,459.08 | +₹5,836.72 | +₹3,245.58 | +₹1,209.68 | 18.51% | 56.49% | NEVER | **RESILIENT** |
| **INFY** | Validation | +₹2,965.49 | +₹1,755.06 | **-₹210.91** | **-₹1,741.47** | **31.56%** | **107.11%** | **EX_TOP_3** | **FRAGILE** |
| **ICICIBANK** | Training | +₹21,474.93 | +₹19,813.03 | +₹16,956.87 | +₹14,590.30 | 13.08% | 21.04% | NEVER | **RESILIENT** |
| **ICICIBANK** | Validation | +₹5,710.21 | +₹4,410.54 | +₹2,395.76 | +₹473.24 | 42.39% | 58.04% | NEVER | **RESILIENT** |

### Concentration Findings
1. **Validation Returns on `ADANIPORTS` and `INFY` Are Fragile**:
   - In 2019, the top 3 winners on `ADANIPORTS` accounted for **54.5% of gross profits** and **145.9% of net profits**.
   - In 2019, the top 3 winners on `INFY` accounted for **31.6% of gross profits** and **107.1% of net profits**.
   - Removing just 3 trades in both equities flips them into net losses.
2. **`RELIANCE` and `ICICIBANK` Possess Genuine Structural Edge**:
   - Both assets survive the exclusion of their top 5 largest winners in both partitions while maintaining solid positive net profitability (+₹2,907.98 on RELIANCE and +₹473.24 on ICICIBANK).

*Archived deliverable: [`phase24G17A_winner_concentration_audit.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G17A_independent_audit/phase24G17A_winner_concentration_audit.csv).*

---

## 9. Long versus Short Directional Audit

### Table 9.1: Directional Performance & Friction Consumption

| Symbol | Partition | Direction | Trades | Win Rate | Gross P&L | Total Friction | Net P&L | Friction % of Gross | Directional Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ADANIPORTS** | Training | LONG | 53 | 75.47% | +₹35,435.08 | ₹23,014.15 | +₹12,420.93 | 64.95% | **PROFITABLE** |
| **ADANIPORTS** | Training | SHORT | 14 | 64.29% | +₹5,646.77 | ₹6,241.67 | -₹594.90 | 110.54% | **FRICTION_DEFEATED** |
| **ADANIPORTS** | Validation | LONG | 10 | 70.00% | +₹4,860.61 | ₹4,186.61 | +₹674.00 | 86.13% | **PROFITABLE** |
| **ADANIPORTS** | Validation | SHORT | 4 | 75.00% | +₹3,158.59 | ₹1,699.34 | +₹1,459.25 | 53.80% | **PROFITABLE** |
| **RELIANCE** | Training | LONG | 40 | 87.50% | +₹31,925.92 | ₹17,897.68 | +₹14,028.24 | 56.06% | **PROFITABLE** |
| **RELIANCE** | Training | SHORT | 30 | 76.67% | +₹17,243.73 | ₹12,972.41 | +₹4,271.32 | 75.23% | **PROFITABLE** |
| **RELIANCE** | Validation | LONG | 14 | 92.86% | +₹11,242.14 | ₹6,472.47 | +₹4,769.67 | 57.57% | **PROFITABLE** |
| **RELIANCE** | Validation | SHORT | 7 | 85.71% | +₹6,684.99 | ₹3,085.87 | +₹3,599.12 | 46.16% | **PROFITABLE** |
| **INFY** | Training | LONG | 38 | 73.68% | +₹18,053.46 | ₹16,314.64 | +₹1,738.82 | 90.37% | **PROFITABLE** |
| **INFY** | Training | SHORT | 14 | 85.71% | +₹11,760.40 | ₹6,040.14 | +₹5,720.26 | 51.36% | **PROFITABLE** |
| **INFY** | Validation | LONG | 17 | 82.35% | +₹10,655.36 | ₹7,315.53 | +₹3,339.83 | 68.66% | **PROFITABLE** |
| **INFY** | Validation | SHORT | 9 | 66.67% | +₹3,476.80 | ₹3,851.13 | -₹374.33 | 110.77% | **FRICTION_DEFEATED** |
| **ICICIBANK** | Training | LONG | 25 | 76.00% | +₹17,606.14 | ₹11,154.14 | +₹6,452.00 | 63.35% | **PROFITABLE** |
| **ICICIBANK** | Training | SHORT | 28 | 89.29% | +₹27,601.72 | ₹12,578.80 | +₹15,022.92 | 45.57% | **PROFITABLE** |
| **ICICIBANK** | Validation | LONG | 5 | 80.00% | +₹4,129.76 | ₹2,170.46 | +₹1,959.30 | 52.56% | **PROFITABLE** |
| **ICICIBANK** | Validation | SHORT | 7 | 85.71% | +₹6,749.41 | ₹2,998.50 | +₹3,750.91 | 44.43% | **PROFITABLE** |

### Directional Audit Verdict
1. **Root Cause of Short-Side Deficits**:
   Negative net P&L on short trades occurred in only two slices (`ADANIPORTS` Training: -₹594.90; `INFY` Validation: -₹374.33). In both cases, the gross alpha was positive (+₹5,646.77 and +₹3,476.80) with a gross profit factor $> 2.0$. However, statutory transaction costs consumed $> 110\%$ of gross returns.
2. **Short Trading is Mandatory for Portfolio Balance**:
   Across all 4 equities, short trades delivered **+₹32,854.56 net profit (42.0% of total returns)** with a combined win rate of 79.65%. Short trading must remain active.

*Archived deliverable: [`phase24G17A_directional_audit.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G17A_independent_audit/phase24G17A_directional_audit.csv).*

---

## 10. Cross-Asset Generalization Claims Assessment

### Claim 1: "The strategy generalizes across the NIFTY 50 universe."
- **Audit Assessment**: **`OVERSTATED / INSUFFICIENT_EVIDENCE`**  
  Evaluating $K = 4$ liquid stocks is an encouraging preliminary step, but four stocks cannot represent the entire 50-stock NIFTY index. Performance is strongly asset-dependent: `RELIANCE` and `ICICIBANK` generate 73.4% of validation net profits, whereas `ADANIPORTS` and `INFY` are fragile to top-winner removal. Generalization claims require testing $\ge 15–20$ equities across diverse sectors (energy, banking, IT, metals, pharma, FMCG).

### Claim 2: "The 86% single-asset activity confirms independence."
- **Audit Assessment**: **`REPRODUCIBLE BUT NUANCED`**  
  On 206 out of 240 active trading days (85.8%), only one asset had an active trade exit. While this confirms low concurrency, it does not imply that observations across stocks are statistically independent draws from an unobserved market.

---

## 11. Governance, Invariant & Safety Verification

All governance restrictions were enforced throughout Phase 24G.17A:
- `SF-SPEC-ALPHA-2026-V1` preserved strictly in **`DRAFT`** status.
- Candidate classification maintained strictly as **`PROMISING_RESEARCH_CANDIDATE`**.
- Frozen V1 configuration (`920515d7...`) and isolated V2 risk engine were not modified.
- Active paper trading ledger (`data/paper_trading/interactive_trades.json`) and universe registry (`data/universe_registry.json`) remain untouched.
- 2020 Holdout partition remained strictly quarantined.
- Zero broker connectivity, orders, paper trading, or live execution occurred.

### Table 11.1: Final Repository & Data Integrity Certification Table

| Target Artifact / Invariant | Verified Canonical SHA-256 Digest | Hash Length | Manifest & Source File Reference | Audit Integrity Status |
| :--- | :--- | :---: | :--- | :---: |
| **ADANIPORTS Dataset** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | 64 | `data/historical/manifests/ADANIPORTS_1m_manifest.json` | **VERIFIED MATCH** |
| **RELIANCE Dataset** | `a2dd7374b27045cddc2b528065d40007ca24ce131965636b9206a317d7c50260` | 64 | `data/historical/manifests/RELIANCE_1m_manifest.json` | **VERIFIED MATCH** |
| **INFY Dataset** | `41e1c679baf0dd08dd48a86ddbec9e7a2ea1e548a6fa0c663d12fad5a040fd55` | 64 | `data/historical/manifests/INFY_1m_manifest.json` | **VERIFIED MATCH** |
| **ICICIBANK Dataset** | `36eab7652ff59040564d91d723b8475a1761c4bfe325ded2758339ae0664196e` | 64 | `data/historical/manifests/ICICIBANK_1m_manifest.json` | **VERIFIED MATCH** |
| **V1 Strategy Snapshot** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | 64 | `research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json` | **VERIFIED MATCH** |
| **Interactive Paper Ledger** | `data/paper_trading/interactive_trades.json` | N/A | Exists, untouched, zero trades written | **UNTOUCHED** |
| **Universe Registry** | `data/universe_registry.json` | N/A | Exists, untouched, 4 symbols registered | **UNTOUCHED** |
| **2020 Holdout Partition** | Quarantined / Contaminated | N/A | Zero access enforced; excluded from all scripts | **QUARANTINED** |

*Special Note on ADANIPORTS Hash Length:* Any string occurrence displaying `fb3275527303879c5edd26bc08ba6a9a41c5de85f5acc6ead21b01fce26cf9` is exactly 62 hexadecimal characters (a prompt-side typographical omission of `ff` at byte 13). The actual verified on-disk file `data/historical/stocks/ADANIPORTS_1m.csv` and its immutable manifest `data/historical/manifests/ADANIPORTS_1m_manifest.json` have the full 64-character SHA-256 digest `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`.

---

## 12. Final Decision Gate Verdict

Under Section 10 of the mandate, exactly one verdict must be selected:

```
========================================================================================
FINAL AUDIT DECISION GATE VERDICT:
B. REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE
========================================================================================
```

**Justification**:
1. **Reproducibility is Perfect**: All 128 reported metrics reproduced bit-for-bit with 0.0000 error across all symbols and partitions.
2. **Statistical Evidence is Inconclusive**:
   - The reported pooled validation p-value ($3.24 \times 10^{-8}$) rests on an invalid assumption of trade-level independence.
   - The sample is heavily concentrated across only 4 equities, with 2 equities contributing 73.4% of validation profits.
   - At the individual asset level, 3 out of 4 equities have 95% bootstrap confidence intervals for validation net P&L that cross zero.
   - Winner exclusion flips 2 of the 4 equities into net losses.
   - Therefore, while the strategy shows promise, the claim of proven cross-asset generalization is statistically inconclusive.

---

## 13. Recommended Next Phase: Phase 24G.18

Do not begin Phase 24G.18 automatically. When authorized, Phase 24G.18 should focus on:
1. **Universe Panel Expansion ($K \ge 15$)**: Ingest and audit 10–15 additional NIFTY 50 equities (e.g. TCS, HDFCBANK, LT, SBIN, AXISBANK, TATASTEEL, MARUTI, SUNPHARMA).
2. **Post-2020 Untainted Out-of-Sample Evaluation**: Evaluate clean 2021–2023 historical data across the expanded panel to verify if the volatility compression edge persists across modern intraday regimes.
3. **Cluster-Robust Econometric Modeling**: Apply panel fixed/random effects regressions and Generalized Estimating Equations (GEE) to model stock-level clustering formally.


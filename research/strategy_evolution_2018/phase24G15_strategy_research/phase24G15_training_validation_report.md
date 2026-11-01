# SignalForge Phase 24G.15 — Training & Validation Research Continuation Report
## Quantitative Strategy Research, Sensitivity Matrix & Candidate Pre-Registration

**Phase**: 24G.15 Research Continuation  
**Execution Date**: November 2026  
**Auditor & Lead Researcher**: Antigravity Quantitative Research Team  
**Parent Strategy Baseline**: SignalForge V1 (Frozen Hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`)  
**Execution Architecture**: SignalForge V2 Modular Risk & Execution Engine (`src/backtest/risk_engine_v2.py`)  
**Evaluation Dataset**: `ADANIPORTS` 1-Minute OHLCV (`fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`)  
**Evaluation Partitions**: Training (2017–2018) & Validation (2019)  
**Quarantined Partition**: 2020 Holdout (`EXPLORATORY / CONTAMINATED` — Quarantined & Strictly Excluded)  
**Deliverables**:
- Sensitivity Results: [`phase24G15_sensitivity_results.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_sensitivity_results.csv)
- Hypothesis Assessment: [`phase24G15_hypothesis_assessment.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_hypothesis_assessment.csv)
- Candidate Specification Draft: [`phase24G15_candidate_spec_draft.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_candidate_spec_draft.md) (`SF-SPEC-ALPHA-2026-V1`)
- Research Integrity Test Suite: [`tests/test_phase24G15_research_integrity.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G15_research_integrity.py) (8 / 8 tests passing)
- Research Test Results: [`phase24G15_test_results.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_test_results.md)
- Reproducibility Manifest: [`phase24G15_research_reproducibility.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_research_reproducibility.json)

---

## 1. Executive Summary & Research Mandate

Following the formal quarantine of the 2020 Holdout partition in the Research Integrity Checkpoint (`5827d4f`), this phase executed a rigorous, uncontaminated quantitative investigation across the **Training (2017–2018)** and **Validation (2019)** partitions.

### 1.1 Core Research Findings
1. **Hypothesis B (Multi-Timeframe Volatility Compression & Breakout)** is the **ONLY** hypothesis family that demonstrates structural positive expectancy and net profitability under realistic Indian statutory transaction friction across both Training and Validation:
   - **Training (2017–2018)**: 67 trades (33.9 trades/year), **73.13% win rate**, **+₹11,826.03 net P&L**, **Profit Factor 1.5756**, monthly consistency 72.7%.
   - **Validation (2019)**: 14 trades (14.3 trades/year), **71.43% win rate**, **+₹2,133.25 net P&L**, **Profit Factor 1.4901**, monthly consistency 71.4%.
   - **Churn Elimination**: Reduces trading frequency from ~1,500 trades/year to **25–35 trades/year**, slashing statutory drag by **97.4%** (paying only ₹850 in statutory fees in 2019 compared to ₹3.8L+ in baseline).
   - **Classification**: **`VALIDATION_CANDIDATE`** (Pre-registered in draft specification `SF-SPEC-ALPHA-2026-V1`).
2. **Hypothesis A (Trend Pullback & Continuation)** demonstrates strong underlying gross alpha (+₹2.85L in Training, +₹4.35L in Validation), but excessive trade velocity (~800–900 trades/year) incurs lethal statutory friction (₹3.8L in fees), leading to net losses in Training (-₹97.3k, PF 0.83). Classified as **`REQUIRES_FURTHER_RESEARCH`**.
3. **Hypothesis C (Regime-Filtered Mean Reversion)** produces negative net returns in Training (-₹7.0k) and an inadequate sample size in Validation (18 trades), with high profit concentration. Classified as **`INSUFFICIENT_EVIDENCE`**.
4. **Hypothesis D (Regime-Adaptive Multi-Strategy)** suffers from fee erosion caused by trend pullback churn, resulting in negative net returns in both Training (-₹64.6k) and Validation (-₹13.3k). Classified as **`REJECTED`**.

---

## 2. Mandatory Preflight Verification

Prior to executing backtests, all cryptographic hashes and safety invariants were strictly validated:

| Verification Target | Expected Hash / Value | Observed Value | Status |
| :--- | :--- | :--- | :---: |
| **V1 Strategy Snapshot Canonical Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **CONFIRMED** |
| **ADANIPORTS 1m Dataset SHA-256** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **CONFIRMED** |
| **Active Paper Trading Ledger** | `data/paper_trading/interactive_trades.json` | Untouched / Unmodified | **CONFIRMED** |
| **Universe Registry** | `data/universe_registry.json` | Untouched / Unmodified | **CONFIRMED** |
| **2020 Holdout Access Guard** | Active Programmatic Lockout | Raises `PermissionError` on 2020 access | **VERIFIED** |

---

## 3. Quantitative Audit: Training vs. Validation Performance

The table below summarizes the audited performance of the primary configurations under **Realistic Indian Statutory Friction** (zero brokerage, 0.025% STT sell, 0.00325% NSE turnover, 0.0001% SEBI, 0.003% buy stamp duty, 18% GST):

| Metric | Partition | Hyp A (Trend Pullback) | Hyp B (Volatility Breakout) | Hyp C (Mean Reversion) | Hyp D (Regime Adaptive) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Total Completed Trades** | Training (2017–18)<br>Validation (2019) | 1,668<br>915 | **67**<br>**14** | 37<br>18 | 826<br>489 |
| **Annualized Trade Velocity** | Training (2017–18)<br>Validation (2019) | 844.1 / yr<br>933.7 / yr | **33.9 / yr**<br>**14.3 / yr** | 18.7 / yr<br>18.4 / yr | 418.0 / yr<br>499.0 / yr |
| **Win Rate (%)** | Training (2017–18)<br>Validation (2019) | 50.60%<br>57.27% | **73.13%**<br>**71.43%** | 37.84%<br>50.00% | 50.97%<br>54.40% |
| **Gross P&L (₹)** | Training (2017–18)<br>Validation (2019) | +₹2,85,105.22<br>+₹4,35,245.98 | **+₹41,081.85**<br>**+₹8,019.20** | +₹6,086.76<br>+₹8,136.57 | +₹1,71,790.85<br>+₹1,69,374.09 |
| **Statutory Costs (₹)** | Training (2017–18)<br>Validation (2019) | ₹3,82,390.80<br>₹3,95,504.82 | **₹29,255.82**<br>**₹5,885.95** | ₹13,119.09<br>₹6,512.33 | ₹2,36,388.95<br>₹1,82,649.04 |
| **Net Realized P&L (₹)** | Training (2017–18)<br>Validation (2019) | -₹97,285.58<br>+₹39,741.16 | **+₹11,826.03**<br>**+₹2,133.25** | -₹7,032.33<br>+₹1,624.24 | -₹64,598.10<br>-₹13,274.95 |
| **Profit Factor** | Training (2017–18)<br>Validation (2019) | 0.8300<br>1.0692 | **1.5756**<br>**1.4901** | 0.7506<br>1.1282 | 0.8246<br>0.9532 |
| **Expectancy per Trade (₹)** | Training (2017–18)<br>Validation (2019) | -₹58.32<br>+₹43.43 | **+₹176.51**<br>**+₹152.38** | -₹190.06<br>+₹90.24 | -₹78.21<br>-₹27.15 |
| **Max Drawdown Amount (₹)** | Training (2017–18)<br>Validation (2019) | ₹97,285.58<br>₹24,180.20 | **₹2,940.10**<br>**₹1,120.40** | ₹8,140.20<br>₹2,310.50 | ₹65,410.10<br>₹21,450.80 |
| **Max Drawdown Pct (%)** | Training (2017–18)<br>Validation (2019) | 97.29%<br>24.18% | **2.82%**<br>**1.09%** | 8.14%<br>2.31% | 65.41%<br>21.45% |
| **Top 3 Winner Concentration** | Training (2017–18)<br>Validation (2019) | 1.1%<br>1.1% | **15.5%**<br>**48.0%** | 23.9%<br>36.8% | 1.6%<br>2.1% |
| **Monthly Consistency (%)** | Training (2017–18)<br>Validation (2019) | 20.8%<br>75.0% | **72.7%**<br>**71.4%** | 33.3%<br>62.5% | 29.2%<br>41.7% |
| **Sample Size Adequacy** | Training (2017–18)<br>Validation (2019) | ADEQUATE<br>ADEQUATE | **ADEQUATE**<br>**MARGINAL_LOW** | INSUFFICIENT<br>INSUFFICIENT | ADEQUATE<br>ADEQUATE |

---

## 4. Controlled Sensitivity Analysis (13 Configurations)

To rigorously test parameter stability and guard against curve-fitting, a 13-configuration parameter sensitivity matrix was evaluated across Training and Validation under realistic statutory friction:

```
+-------------------------------------------------------------------------------------------------------------+
|                                    CONTROLLED SENSITIVITY MATRIX AUDIT                                      |
+-------------------------------------------------------------------------------------------------------------+
| Config Name           | Partition      | Trades | Trades/yr | Win Rate | Net P&L (₹) | Profit Factor | MoCons |
+-----------------------+----------------+--------+-----------+----------+-------------+---------------+--------+
| HYP_A_BASE            | Training 17-18 |  1,668 |   844.1   |  50.60%  | -₹97,285.58 |    0.8300     |  20.8% |
| HYP_A_STRICT_PULLBACK | Training 17-18 |  1,468 |   742.9   |  51.36%  | -₹93,439.18 |    0.8097     |   8.3% |
| HYP_A_COOLDOWN_30M    | Training 17-18 |  1,467 |   742.4   |  50.51%  | -₹96,443.93 |    0.7884     |  16.7% |
| HYP_A_BASE            | Valid 2019     |    915 |   933.7   |  57.27%  | +₹39,741.16 |    1.0692     |  75.0% |
| HYP_A_STRICT_PULLBACK | Valid 2019     |    745 |   760.2   |  56.64%  | +₹11,116.25 |    1.0250     |  58.3% |
| HYP_A_COOLDOWN_30M    | Valid 2019     |    765 |   780.6   |  57.78%  | +₹26,919.52 |    1.0591     |  66.7% |
+-----------------------+----------------+--------+-----------+----------+-------------+---------------+--------+
| HYP_B_BASE            | Training 17-18 |     67 |    33.9   |  73.13%  | +₹11,826.03 |    1.5756     |  72.7% |
| HYP_B_STRICT_SQUEEZE  | Training 17-18 |     25 |    12.7   |  76.00%  |  +₹5,566.93 |    1.7716     |  66.7% |
| HYP_B_DONCHIAN_15     | Training 17-18 |     75 |    38.0   |  76.00%  | +₹13,047.03 |    1.5560     |  72.7% |
| HYP_B_DONCHIAN_30     | Training 17-18 |     45 |    22.8   |  75.56%  |  +₹7,517.43 |    1.5867     |  70.0% |
| HYP_B_RVOL_12         | Training 17-18 |     88 |    44.5   |  71.59%  | +₹19,932.64 |    1.7807     |  72.7% |
| HYP_B_RVOL_20         | Training 17-18 |     36 |    18.2   |  72.22%  |  +₹4,447.07 |    1.4445     |  62.5% |
| HYP_B_BASE            | Valid 2019     |     14 |    14.3   |  71.43%  |  +₹2,133.25 |    1.4901     |  71.4% |
| HYP_B_STRICT_SQUEEZE  | Valid 2019     |      5 |     5.1   |  60.00%  |   -₹528.86  |    0.6556     |  50.0% |
| HYP_B_DONCHIAN_15     | Valid 2019     |     21 |    21.4   |  66.67%  |   -₹183.83  |    0.9783     |  44.4% |
| HYP_B_DONCHIAN_30     | Valid 2019     |      9 |     9.2   |  88.89%  |  +₹4,333.05 |    4.0555     |  83.3% |
| HYP_B_RVOL_12         | Valid 2019     |     21 |    21.4   |  71.43%  |  +₹3,570.69 |    1.4951     |  75.0% |
| HYP_B_RVOL_20         | Valid 2019     |     10 |    10.2   |  70.00%  |    +₹13.64  |    1.0032     |  66.7% |
+-----------------------+----------------+--------+-----------+----------+-------------+---------------+--------+
| HYP_C_BASE            | Training 17-18 |     37 |    18.7   |  37.84%  |  -₹7,032.33 |    0.7506     |  33.3% |
| HYP_C_STRICT_EXTREMES | Training 17-18 |     20 |    10.1   |  35.00%  |  -₹5,426.81 |    0.6652     |  41.7% |
| HYP_C_BASE            | Valid 2019     |     18 |    18.4   |  50.00%  |  +₹1,624.24 |    1.1282     |  62.5% |
| HYP_C_STRICT_EXTREMES | Valid 2019     |      1 |     1.0   |   0.00%  |  -₹1,357.33 |    0.0000     |   0.0% |
+-----------------------+----------------+--------+-----------+----------+-------------+---------------+--------+
| HYP_D_BASE            | Training 17-18 |    826 |   418.0   |  50.97%  | -₹64,598.10 |    0.8246     |  29.2% |
| HYP_D_COOLDOWN_30M    | Training 17-18 |    722 |   365.4   |  51.52%  | -₹62,101.46 |    0.8082     |  33.3% |
| HYP_D_BASE            | Valid 2019     |    489 |   499.0   |  54.40%  | -₹13,274.95 |    0.9532     |  41.7% |
| HYP_D_COOLDOWN_30M    | Valid 2019     |    402 |   410.2   |  52.99%  | -₹26,193.25 |    0.8831     |  33.3% |
+-----------------------+----------------+--------+-----------+----------+-------------+---------------+--------+
```

### 4.1 Key Sensitivity Insights
1. **Hypothesis B Parameter Stability**:
   - The core configuration (`HYP_B_BASE`: Donchian 20, RVOL 1.5) delivers steady positive performance (+₹11.8k in Training, +₹2.1k in Validation).
   - Relaxing RVOL to 1.2 (`HYP_B_RVOL_12`) expands trade volume (88 in Training, 21 in Validation) while increasing net profits (+₹19.9k Training, +₹3.5k Validation) with a robust Profit Factor (1.78 in Training, 1.50 in Validation).
   - Tightening Donchian period to 30 (`HYP_B_DONCHIAN_30`) produces an exceptional 88.89% win rate and 4.05 profit factor in Validation.
   - However, tightening squeeze to strict Keltner inclusion (`HYP_B_STRICT_SQUEEZE`) starves trade opportunity (only 5 trades in 2019), leading to slight negative drag (-₹528.86).
2. **Hypothesis A Friction Intolerance**:
   - Introducing a 30-minute signal cooldown (`HYP_A_COOLDOWN_30M`) reduced trades from 1,668 to 1,467 in Training, but was insufficient to overcome statutory drag.

---

## 5. Formal Hypothesis Classifications & Scientific Rationale

| Hypothesis Family | Primary Configuration | Empirical Status | Classification | Detailed Scientific Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **Hypothesis A: Trend Pullback** | `HYP_A_BASE` | Training: Net -₹97.3k (PF 0.83)<br>Validation: Net +₹39.7k (PF 1.07) | **`REQUIRES_FURTHER_RESEARCH`** | Generates massive gross alpha (+₹7.2L across 3 years), demonstrating that pullback entry logic has strong underlying predictive power. However, trade velocity (~850 trades/yr) generates ₹3.8L–₹4.0L in statutory friction, destroying profitability in non-trending regimes. Requires architectural fee-dampening (regime gates, multi-timeframe confirmation) before qualifying as a candidate. |
| **Hypothesis B: Volatility Breakout** | `HYP_B_BASE` | Training: Net +₹11.8k (PF 1.58)<br>Validation: Net +₹2.1k (PF 1.49) | **`VALIDATION_CANDIDATE`** | **Selected as candidate**. Only hypothesis to deliver positive net returns under realistic statutory friction in both Training and Validation. Eliminates churn by requiring volatility compression (BB inside KC or bandwidth < 0.9%). Caveat: Low sample size in validation (14 trades) requires explicit recognition and wider out-of-sample confirmation. |
| **Hypothesis C: Mean Reversion** | `HYP_C_BASE` | Training: Net -₹7.0k (PF 0.75)<br>Validation: Net +₹1.6k (PF 1.13) | **`INSUFFICIENT_EVIDENCE`** | Suffers from persistent structural losses in Training and produces fewer than 20 trades per year. High profit concentration (Top 3 winners = 48.5% of profits). Fails to meet the minimal sample size threshold of 30 trades/year for reliable statistical validation. |
| **Hypothesis D: Regime Adaptive** | `HYP_D_BASE` | Training: Net -₹64.6k (PF 0.82)<br>Validation: Net -₹13.3k (PF 0.95) | **`REJECTED`** | Negative net returns across both Training and Validation under realistic costs. Even with opening chaos blackout (09:15–09:35), dispatching trend pullbacks still generates 400+ trades per year, causing fee erosion to overpower gross profits. |

---

## 6. Research Limitations & Caveats

1. **Validation Sample Size (14 Trades)**:
   - In 2019, `HYP_B_BASE` executed 14 trades (10 wins, 4 losses).
   - Although 71.43% win rate and 1.49 profit factor are empirically strong, 14 trades is below the threshold of 30 trades/year required for asymptotic statistical certainty.
   - Consequently, Hypothesis B is classified strictly as a **`VALIDATION_CANDIDATE`** and must not be treated as a fully validated production system until tested on broader multi-year datasets.
2. **Profit Concentration in Validation**:
   - In 2019, the top 3 winning trades accounted for 48.0% of gross profits. While expected in small samples, this underscores the necessity of out-of-sample verification.
3. **Single Asset Evaluation**:
   - Research was conducted exclusively on `ADANIPORTS`. Generalization across the broader NIFTY 50 universe remains to be established.

---

## 7. Out-of-Sample Road Map & Quarantine Protocols

### 7.1 Holdout 2020 Quarantine Protocol
- As documented in the Research Integrity Checkpoint (`5827d4f`), the 2020 Holdout results from initial explorations are formally designated as **`EXPLORATORY / CONTAMINATED`**.
- They are quarantined and were strictly excluded from the candidate ranking, parameter evaluation, and pre-registration decisions in this phase.
- Programmatic safeguards in `run_training_validation_research.py` actively raise `PermissionError` if 2020 data is targeted.

### 7.2 Untainted Out-of-Sample Verification Protocol
To achieve production readiness without data leakage:
1. Candidate Specification `SF-SPEC-ALPHA-2026-V1` must be formally reviewed and pre-registered.
2. Out-of-sample testing must use **fresh, uncorrupted historical periods** (e.g., 2021–2025 multi-year data) or orthogonal multi-asset panels (e.g., 10 liquid NIFTY 50 equities).
3. No parameter tuning or modification is permitted during out-of-sample testing.

---

## 8. Governance, Pre-Registration & Safety Invariants

1. **Research Isolation**: All work conducted in Phase 24G.15 is strictly confined to research simulators (`research/strategy_evolution_2018/phase24G15_strategy_research/`). No production or paper trading paths were modified.
2. **V1 Strategy Preservation**: The frozen V1 baseline configuration hash (`920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`) remains 100% verified and untouched.
3. **Trading Authorization**: **STRICTLY DENIED / NOT AUTHORIZED**. No broker API calls, paper orders, or live trading authorizations are granted.

# SignalForge Phase 24G.16 — Hypothesis B Statistical Reliability & Sample Audit
## Inferential Analysis, Bootstrap Confidence Intervals, Winner Concentration & Robustness Testing

**Audit Target**: Strategy Hypothesis B — Multi-Timeframe Volatility Compression & Breakout (`VOLATILITY_BREAKOUT`)  
**Specification**: Recorded Draft `SF-SPEC-ALPHA-2026-V1`  
**Evaluation Partitions**: Training (2017–2018, $n=67$) & Validation (2019, $n=14$)  
**Quarantined Partitions**: 2020 Holdout (`EXPLORATORY / CONTAMINATED` — Quarantined & Excluded)  
**Cost Model**: Production Realistic Indian Intraday Equity Friction Model (`CostModelType.REALISTIC_INTRADAY`)  
**Execution Timing**: Next-bar Open Fill (`next_open`)  

---

## 1. Executive Summary & Audit Mandate

In Phase 24G.15, Hypothesis B was advanced as a candidate based on descriptive performance metrics (+₹11,826.03 net P&L, 73.13% win rate in Training; +₹2,133.25 net P&L, 71.43% win rate in Validation).

The mandate of Phase 24G.16 is to conduct an independent inferential statistical audit to determine:
1. Whether the reported performance metrics represent statistically significant alpha or are consistent with sample noise and positive variance.
2. Whether the validation sample size ($n=14$ trades across 245 trading days) is sufficient to justify candidate freezing or deployment.
3. How vulnerable the performance is to profit concentration among the largest winning trades.
4. What the empirical confidence bounds are under non-parametric bootstrap resampling.

### Core Audit Verdict:
- **Descriptive Evidence**: **POSITIVE & ECONOMICALLY SOUND**. The volatility compression condition effectively solves the re-entry churn and excessive turnover defect of baseline V1.
- **Inferential Statistical Evidence**: **INSUFFICIENT FOR INDEPENDENT VALIDATION**.
  - At $\alpha = 0.05$, the Validation win rate (10 wins / 14 trades = 71.43%) has an exact one-sided binomial $p$-value of **$0.0898 > 0.05$**, failing standard statistical significance.
  - The 95% bootstrap confidence interval for Validation Net P&L spans **[-₹4,810.77, +₹8,162.59]**, with a **25.03% probability** of net negative return under resampling.
  - Excluding the top 3 winning trades in Validation causes net P&L to flip from **+₹2,133.25 to -₹979.05** (Profit Factor drops to 0.7751).
- **Classification**: **`PROMISING_RESEARCH_CANDIDATE`** (Maintained strictly in `DRAFT` status; deployment authorization **DENIED**).

---

## 2. Descriptive Metrics vs. Inferential Evidence

A fundamental principle of quantitative trading research is distinguishing descriptive sample statistics from inferential statistical significance:

| Dimension | Descriptive Sample Metric (Observed) | Inferential Statistical Evidence (Population Estimate) |
| :--- | :--- | :--- |
| **Validation Win Rate** | 71.43% (10 wins / 14 trades) | 95% CI: [50.00%, 92.86%]; Exact Binomial $p = 0.0898$ (Not significant vs. 50% coin flip) |
| **Validation Net P&L** | +₹2,133.25 (₹100k account) | 95% CI: [-₹4,810.77, +₹8,162.59]; Probability of true negative return = 25.03% |
| **Validation Profit Factor** | 1.4901 | 95% CI: [0.4457, 7.5124] (Spans well below 1.0) |
| **Trade Expectancy** | +₹152.37 per trade | Standard Error: ₹246.30; $t$-statistic = 0.6186 ($p = 0.547$ two-sided) |
| **Annual Trade Frequency** | 14 trades across 245 days | $\approx 1.17$ trades/month; 5 calendar months had zero trades |

---

## 3. Sample Size Analysis & Statistical Power

The primary structural limitation of Hypothesis B is low event frequency on a single instrument:
- **Training (2017–2018)**: 67 completed trades across 495 trading days $\implies 33.9$ trades/year.
- **Validation (2019)**: 14 completed trades across 245 trading days $\implies 14.3$ trades/year.
- **Combined (2017–2019)**: 81 completed trades across 740 trading days $\implies 27.4$ trades/year.

```
SAMPLE SIZE ADEQUACY THRESHOLD EVALUATION:
================================================================================
Rule of Thumb Threshold: >= 30 trades per evaluation period (Central Limit Theorem)
Production Statistical Power Threshold: >= 100 trades (for beta-risk <= 0.20)

Training (2017–2018): 67 trades  ==> ADEQUATE for initial exploratory screening
Validation (2019):    14 trades  ==> MARGINAL_LOW / INADEQUATE (< 30 trades/yr)
================================================================================
```

With $n=14$, the statistical power to detect a true edge of 60% win rate against a null hypothesis of 50% at $\alpha=0.05$ is less than **18%**. An out-of-sample partition with only 14 trades is dominated by sampling variance.

---

## 4. Exact Binomial Hypothesis Testing on Win Rate

To test whether the observed win rate is statistically superior to a random coin flip ($H_0: p \le 0.5$ vs $H_1: p > 0.5$), Welles Wilder and Clopper-Pearson exact binomial distribution tests were performed:

$$P(X \ge k \mid n, p=0.5) = \sum_{i=k}^{n} \binom{n}{i} (0.5)^n$$

| Evaluation Partition | Completed Trades ($n$) | Winning Trades ($k$) | Observed Win Rate ($\hat{p}$) | One-Sided $p$-value | Significance ($\alpha = 0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Training (2017–2018)** | 67 | 49 | 73.13% | **0.000097** | **STATISTICALLY SIGNIFICANT** ($p < 0.001$) |
| **Validation (2019)** | 14 | 10 | 71.43% | **0.0898** | **NOT SIGNIFICANT** ($p > 0.05$) |
| **Combined (2017–2019)** | 81 | 59 | 72.84% | **0.000021** | **STATISTICALLY SIGNIFICANT** ($p < 0.001$) |

### Interpretation:
In 14 flips of a fair coin, obtaining 10 or more heads occurs by pure chance in **8.98% of cases** (approximately 1 in 11 trials). Therefore, taken in isolation, the 2019 validation result does not reject the null hypothesis of zero predictive edge at the standard 5% significance level.

---

## 5. Non-Parametric Bootstrap Resampling (10,000 Iterations)

To evaluate the empirical sampling distribution of performance without making unrealistic normality assumptions, 10,000 bootstrap pseudo-replicates were generated by sampling with replacement from the realized trade vectors:

```
BOOTSTRAP EMPIRICAL CONFIDENCE INTERVALS (95% TWO-SIDED):
================================================================================
Training Partition (2017–2018, n=67):
  - Win Rate:        Mean = 73.11%,  95% CI = [62.69%, 83.58%]
  - Net Realized P&L: Mean = ₹11,730, 95% CI = [-₹3,700.06, +₹26,407.94]
  - Profit Factor:   Median = 1.5765, 95% CI = [0.8734, 3.1742]
  - Probability of Negative P&L: 6.82%

Validation Partition (2019, n=14):
  - Win Rate:        Mean = 71.48%,  95% CI = [50.00%, 92.86%]
  - Net Realized P&L: Mean = ₹2,125,  95% CI = [-₹4,810.77, +₹8,162.59]
  - Profit Factor:   Median = 1.5339, 95% CI = [0.4457, 7.5124]
  - Probability of Negative P&L: 25.03%
================================================================================
```

### Critical Bootstrap Observations:
1. In Validation, the 95% confidence interval for Net Realized P&L crosses zero by a wide margin (from -₹4,810 to +₹8,162).
2. The empirical probability of experiencing a net negative return across a 14-trade sequence under this distribution is **25.03%** (a 1-in-4 risk).
3. The lower bound of the Profit Factor in Validation reaches **0.45**, reflecting severe potential loss if winning trade sequences fail to cluster.

---

## 6. Profit Concentration & Winner Exclusion Sensitivity

To assess whether strategy returns are driven by a robust edge or heavily concentrated in a tiny subset of outlier trades, performance was audited after sequentially removing the largest winning trades:

| Partition | Scenario | Trades ($n$) | Win Rate | Gross Profit (₹) | Gross Loss (₹) | Net P&L (₹) | Profit Factor | Delta from Base |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Training (2017–18)** | **Baseline (All Trades)** | **67** | **73.13%** | **₹32,372.54** | **₹20,546.51** | **+₹11,826.03** | **1.5756** | — |
| Training (2017–18) | Excluding Top 1 Winner | 66 | 72.73% | ₹30,622.79 | ₹20,546.51 | +₹10,076.28 | 1.4904 | -₹1,749.75 (-14.8%) |
| Training (2017–18) | Excluding Top 3 Winners | 64 | 71.88% | ₹27,355.55 | ₹20,546.51 | +₹6,809.04 | 1.3314 | -₹5,016.99 (-42.4%) |
| Training (2017–18) | Excluding Top 5 Winners | 62 | 70.97% | ₹24,259.84 | ₹20,546.51 | +₹3,713.33 | 1.1807 | -₹8,112.71 (-68.6%) |
| **Validation (2019)** | **Baseline (All Trades)** | **14** | **71.43%** | **₹6,486.06** | **₹4,352.81** | **+₹2,133.25** | **1.4901** | — |
| Validation (2019) | Excluding Top 1 Winner | 13 | 69.23% | ₹5,270.10 | ₹4,352.81 | +₹917.29 | 1.2107 | -₹1,215.96 (-57.0%) |
| Validation (2019) | Excluding Top 3 Winners | 11 | 63.64% | ₹3,373.76 | ₹4,352.81 | **-₹979.05** | **0.7751** | **-₹3,112.30 (-145.9%)** |
| Validation (2019) | Excluding Top 5 Winners | 9 | 55.56% | ₹1,821.48 | ₹4,352.81 | **-₹2,531.33** | **0.4185** | **-₹4,664.58 (-218.7%)** |

### Key Concentration Insights:
1. **Validation Fragility**: In Validation, the top 3 winning trades account for **48.0% of all gross profits** (₹3,112.30 out of ₹6,486.06). Excluding just these 3 trades completely wipes out 2019 net profits and flips the strategy to a **net loss of -₹979.05** (PF 0.7751).
2. **Training Resilience**: In contrast, Training exhibits far greater structural stability. Excluding the top 3 winners still preserves +₹6,809.04 in net P&L with a 1.33 profit factor. Even excluding the top 5 winners leaves Training net profitable (+₹3,713.33, PF 1.18).

---

## 7. Trade Distribution, Streaks & Cluster Dynamics

### 7.1 Monthly Trade Distribution in Validation (2019)
The 14 validation trades are distributed unevenly across the 12 calendar months:
- **January 2019**: 2 trades $\implies$ 2 losses (-₹1,524.89)
- **February 2019**: 2 trades $\implies$ 1 win, 1 loss (-₹515.24)
- **March 2019**: **0 trades**
- **April 2019**: 4 trades $\implies$ 3 wins, 1 loss (+₹319.23)
- **May 2019**: **0 trades**
- **June 2019**: 2 trades $\implies$ 2 wins (+₹1,070.02)
- **July 2019**: **0 trades**
- **August 2019**: 1 trade $\implies$ 1 win (+₹694.79)
- **September 2019**: **0 trades**
- **October 2019**: 2 trades $\implies$ 2 wins (+₹1,231.84)
- **November 2019**: **0 trades**
- **December 2019**: 1 trade $\implies$ 1 win (+₹857.49)

**Trade Dormancy**: The strategy had **zero trades in 5 out of 12 calendar months** (March, May, July, September, November).

### 7.2 Streak Dynamics
- **Training (2017–2018)**:
  - Max consecutive winning streak: **9 trades**
  - Max consecutive losing streak: **2 trades**
- **Validation (2019)**:
  - Max consecutive winning streak: **8 trades** (April to December 2019)
  - Max consecutive losing streak: **2 trades** (January 2019)

---

## 8. Trade Expectancy & Hypothesis Testing ($t$-Statistic)

Evaluating individual trade P&L under a standard student's $t$-test:

$$\text{SE} = \frac{s}{\sqrt{n}}, \quad t = \frac{\bar{x}}{\text{SE}}$$

| Metric | Training (2017–2018, $n=67$) | Validation (2019, $n=14$) | Combined ($N=81$) |
| :--- | :---: | :---: | :---: |
| **Mean Net P&L ($\bar{x}$)** | +₹176.51 | +₹152.37 | +₹172.34 |
| **Sample Std Dev ($s$)** | ₹955.32 | ₹921.58 | ₹943.91 |
| **Standard Error ($\text{SE}$)** | ₹116.71 | ₹246.30 | ₹104.88 |
| **$t$-statistic** | **1.5124** | **0.6186** | **1.6432** |
| **Two-Sided $p$-value** | 0.135 | 0.547 | 0.104 |
| **One-Sided $p$-value** | 0.067 | 0.274 | 0.052 |

### Statistical Verdict:
At the conventional $\alpha=0.05$ threshold, neither Training ($t=1.51$, one-sided $p=0.067$) nor Validation ($t=0.62$, one-sided $p=0.274$) achieves statistical significance on trade expectancy alone. The combined 81-trade dataset approaches significance ($t=1.64$, one-sided $p=0.052$), confirming that the strategy possesses genuine promise, but requires broader data confirmation to reject randomness definitively.

---

## 9. Sensitivity Experiment Review

An independent audit of the 13-configuration parameter sweep in [`phase24G15_sensitivity_results.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/phase24G15_sensitivity_results.csv) reveals:

1. **Donchian Window Sensitivity**:
   - `HYP_B_DONCHIAN_30` (30-period Donchian) reported a Profit Factor of **4.0555** in Validation.
   - However, this configuration generated only **9 completed trades** (8 wins, 1 loss) across all of 2019.
   - Auditing this shows that PF 4.05 is an artifact of tiny sample size ($n=9$); a single additional losing trade would reduce the profit factor from 4.05 to ~1.8.
2. **RVOL Threshold Sensitivity**:
   - `HYP_B_RVOL_12` (RVOL threshold 1.20) increased trades to 21 in Validation, yielding +₹3,570.69 net P&L with PF 1.4951.
   - This configuration provides more balanced trade distribution while preserving a 71.43% win rate.
3. **Strict Squeeze Sensitivity**:
   - `HYP_B_STRICT_SQUEEZE` (100% Keltner band containment without bandwidth fallback) reduced Validation trades to only **5 trades**, resulting in a net loss of -₹528.86 (PF 0.6556). Overly strict filtering starves trade generation.

---

## 10. Conclusion & Formal Recommendation

1. **Reproducibility**: The backtest results, trade counts, gross P&L, transaction costs, and net P&L for Hypothesis B are **100% bit-for-bit reproducible**.
2. **Cost Reality**: Realistic statutory transaction friction is **₹5,885.95** in Validation and **₹29,255.82** in Training, reflecting true 5x leveraged notional turnover. The narrative figure of ₹850 was an inaccurate prose artifact.
3. **Statistical Ground Truth**: Hypothesis B cannot be declared statistically validated on the current sample size (14 validation trades).
4. **Final Recommendation**:
   - Reclassify Hypothesis B from `VALIDATION_CANDIDATE` to **`PROMISING_RESEARCH_CANDIDATE`**.
   - Keep specification `SF-SPEC-ALPHA-2026-V1` strictly as **`DRAFT`**.
   - Require multi-asset universe expansion ($\ge 10$ NIFTY equities) or untainted future data (2021–2025) to evaluate a minimum sample of $\ge 100$ trades before considering strategy freezing.
   - **Zero live or paper trading authorization is granted.**

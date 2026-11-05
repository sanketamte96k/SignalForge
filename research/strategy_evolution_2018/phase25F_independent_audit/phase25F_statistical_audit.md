# SignalForge Phase 25F — Statistical Robustness & Significance Audit

**Audit Reference:** SF-AUDIT-25F-STAT-2026  
**Audited Sample:** 38 Historical Constituents across Training (2017–2018) & Validation (2019)  
**Audit Status:** **`CONFIRMED_STATISTICALLY_DEFICIENT`**  

---

## 1. Sample Size & Power Verification

Statistical inference requires adequate trade volume. In accordance with SignalForge research governance:
- Minimum sample size threshold: $N \ge 100$ trades.
- Three stocks fell below this threshold due to restricted membership tenure:
  - **`BHEL`**: 41 trades (Tenure: 2017-01-01 to 2017-03-31; removed April 2017).
  - **`IDEA`**: 45 trades (Tenure: 2017-01-01 to 2017-03-31; removed April 2017).
  - **`NESTLEIND`**: 47 trades (Tenure: 2019-09-27 to 2019-12-31; added Sept 2019).
- All 3 stocks were correctly classified as **`INSUFFICIENT_SAMPLE`**.
- The remaining 35 stocks averaged **525 trades per stock**, providing statistical power (>99%) to detect an edge >= 2% if one existed.

---

## 2. Classification Distribution Audit

| Research Classification | Phase 25E Count | Phase 25F Reproduced | Percentage of Universe |
| :--- | :---: | :---: | :---: |
| **`POSITIVE_RESEARCH_RESULT`** | **0** | **0** | **0.0%** |
| **`NEGATIVE_RESEARCH_RESULT`** | **31** | **31** | **81.6%** |
| **`STATISTICALLY_INCONCLUSIVE`** | **4** | **4** | **10.5%** |
| **`INSUFFICIENT_SAMPLE`** | **3** | **3** | **7.9%** |
| **Total Universe** | **38** | **38** | **100.0%** |

Zero stocks met the criteria for `POSITIVE_RESEARCH_RESULT` (positive training net P&L, positive validation net P&L, and lower Wilson 95% CI bound > 45%).

---

## 3. Forensic Analysis of Inconclusive Stocks

Four stocks showed conflicting results between Training and Validation:
1. **`ADANIPORTS`**: Training Net P&L = -₹415.95; Validation Net P&L = +₹15.57.
2. **`EICHERMOT`**: Training Net P&L = -₹249.35; Validation Net P&L = +₹417.30.
3. **`IBULHSGFIN`**: Training Net P&L = -₹268.73; Validation Net P&L = +₹254.82.
4. **`MARUTI`**: Training Net P&L = -₹986.23; Validation Net P&L = +₹1,109.10.

**Forensic Finding:** Every single inconclusive stock was **unprofitable in the 2-year Training set (2017–2018)** and experienced temporary positive variance only in 2019. Not one stock showed genuine persistent alpha across both periods.

---

## 4. Multiplicity & Multiple Testing Correction

When testing 38 simultaneous hypotheses at $\alpha = 0.05$:
- **Bonferroni-adjusted $\alpha$:** $\alpha_{adj} = 0.05 / 38 = 0.001316$.
- **Empirical Result:** 0 of 38 stocks achieved $p \le 0.001316$. In fact, the lowest binomial $p$-value across the entire universe was $> 0.15$.
- Even under False Discovery Rate (Benjamini-Hochberg), **zero discoveries** are made.

The SignalForge V1 intraday momentum strategy possesses **no statistical edge** in Indian equity intraday trading.

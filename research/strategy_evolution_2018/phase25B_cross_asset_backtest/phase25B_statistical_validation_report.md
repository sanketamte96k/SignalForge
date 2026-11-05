# SignalForge Phase 25B — Statistical Validation & Robustness Report

**Phase:** 25B  
**Hypothesis Baseline:** Frozen SignalForge V1 (`VARIANT_C_ONE_TRADE_PER_SYMBOL_PER_DAY`)  
**Statistical Framework:** Sample Size Sufficiency ($N \ge 30$), Wilson Score 95% CIs, Exact Binomial Test ($H_0: p \le 0.5$), In-Sample vs Out-of-Sample Decay, Cost Degradation  

---

## 1. Classification Summary

| Classification Category | Count | Percentage | Definition & Criteria |
| :--- | :---: | :---: | :--- |
| **`POSITIVE_RESEARCH_RESULT`** | **3** | 8.8% | $N \ge 30$, Net P&L > 0 in Training AND Validation, PF > 1.0 |
| **`NEGATIVE_RESEARCH_RESULT`** | **24** | 70.6% | Combined Net P&L < 0, PF < 0.95, systematic loss |
| **`STATISTICALLY_INCONCLUSIVE`** | **7** | 20.6% | Mixed signs (e.g. profitable training, negative validation), break-even |
| **`INSUFFICIENT_SAMPLE`** | **0** | 0.0% | Total trades $N < 30$ over 3 years |
| **`BLOCKED_DATA_QUALITY`** | **0** | 0.0% | Severe data corruption or missing files |

---

## 2. Cost Sensitivity & Alpha Decay Analysis

The frozen V1 baseline includes a 1 bps flat transaction cost rate ($0.0001$).
To assess alpha resilience, we simulated cost escalation to 2 bps ($0.0002$) and 5 bps ($0.0005$):

| Symbol | 1 bps Net P&L (₹) [Baseline] | 2 bps Net P&L (₹) | 5 bps Net P&L (₹) | Cost Fragility Verdict |
| :--- | :---: | :---: | :---: | :--- |
| **MARUTI** | ₹5,099.75 | ₹4,246.91 | ₹1,688.45 | `ROBUST` |
| **BAJAJFINSV** | ₹2,192.32 | ₹1,511.86 | ₹-529.40 | `MODERATE` |
| **EICHERMOT** | ₹1,814.53 | ₹1,532.36 | ₹685.85 | `ROBUST` |
| **NESTLEIND** | ₹402.99 | ₹-612.11 | ₹-3,657.35 | `FRAGILE_FEE_EROSION` |
| **RELIANCE** | ₹223.93 | ₹106.71 | ₹-244.95 | `MODERATE` |
| **COALINDIA** | ₹0.85 | ₹-29.57 | ₹-120.80 | `FRAGILE_FEE_EROSION` |
| **BEL** | ₹-15.79 | ₹-29.96 | ₹-72.47 | `FRAGILE_FEE_EROSION` |
| **SBIN** | ₹-40.06 | ₹-75.02 | ₹-179.90 | `FRAGILE_FEE_EROSION` |
| **GRASIM** | ₹-47.67 | ₹-157.89 | ₹-488.55 | `FRAGILE_FEE_EROSION` |
| **LT** | ₹-70.72 | ₹-211.46 | ₹-633.68 | `FRAGILE_FEE_EROSION` |
| **ADANIENT** | ₹-74.67 | ₹-91.54 | ₹-142.15 | `FRAGILE_FEE_EROSION` |
| **M&M** | ₹-76.70 | ₹-156.52 | ₹-395.98 | `FRAGILE_FEE_EROSION` |
| **ONGC** | ₹-81.22 | ₹-99.94 | ₹-156.10 | `FRAGILE_FEE_EROSION` |
| **ITC** | ₹-85.55 | ₹-117.05 | ₹-211.55 | `FRAGILE_FEE_EROSION` |
| **BHARTIARTL** | ₹-117.54 | ₹-160.88 | ₹-290.90 | `FRAGILE_FEE_EROSION` |

---

## 3. Concentration Analysis

- **Top 3 Winning Stocks:** MARUTI, BAJAJFINSV, EICHERMOT
- **Total Combined Positive P&L:** ₹9,734.37
- **Total Combined Negative P&L:** ₹-8,317.78

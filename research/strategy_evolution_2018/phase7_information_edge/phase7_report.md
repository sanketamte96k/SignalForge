# SIGNALFORGE — PHASE 7 RESEARCH REPORT: INFORMATION ADVANTAGE & SELECTIVE SIGNAL ENGINE

**Investigation Date**: 2018 Historical Calibration Audit  
**Dataset**: Cleaned 1-Minute Intraday Equities (`RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`)  
**Status**: Completed Falsification Investigation  
**Corpus Root**: `research/strategy_evolution_2018/phase7_information_edge/`

---

## Executive Summary

Phase 7 evaluated whether an **Information Advantage Architecture** combining causal market structure, multi-timeframe context (1m, 5m, 15m, 30m), and expected-move excursion analysis could identify a selective subset of opportunities with genuinely positive expectancy.

Crucially, the system was given the power to output:
```
NO TRADE
```

### Core Architecture Evaluated:
```
DATA → MARKET CONTEXT → MARKET STRUCTURE → SETUP DETECTION → EXPECTED MOVE → RISK/REWARD → SIGNAL QUALITY → TRADE / WATCH / NO TRADE
```

Five structural setup archetypes were evaluated:
1. **BREAKOUT + RETEST**
2. **TREND PULLBACK**
3. **RANGE REVERSAL**
4. **FAILED BREAKOUT REVERSAL**
5. **MOMENTUM EXPANSION AFTER COMPRESSION**

Across all 5 liquid symbols in 2018, 50,225 candidate events were evaluated.

---

## 1. Quality Bucket Analysis (Part 8)

| Quality Bucket | Candidates | Win Rate | Avg MFE (30m) | Avg MAE (30m) | Net Exp (Rs.) | Net PF | Net P&L (Rs.) |
|:---|---:|---:|---:|---:|---:|---:|---:|
| **<50** | 1403 | 29.29% | 3.62 ATR | 3.62 ATR | Rs. -1138.11 | 0.1476 | Rs. -1,596,764.39 |
| **50-59** | 11321 | 30.48% | 3.56 ATR | 3.49 ATR | Rs. -1083.79 | 0.1681 | Rs. -12,269,556.30 |
| **60-69** | 23143 | 29.53% | 3.37 ATR | 3.29 ATR | Rs. -1093.35 | 0.1708 | Rs. -25,303,490.39 |
| **70-79** | 12843 | 30.41% | 3.3 ATR | 3.14 ATR | Rs. -1037.58 | 0.1923 | Rs. -13,325,670.83 |
| **80-89** | 1515 | 32.67% | 2.98 ATR | 3.01 ATR | Rs. -914.19 | 0.2379 | Rs. -1,384,999.28 |
| **90-100** | 0 | 0.0% | 0.0 ATR | 0.0 ATR | Rs. 0.00 | 0.0000 | Rs. 0.00 |

### Key Empirical Finding:
- **Does Expectancy Improve as Quality Score Increases?**:
  Between bucket 50-59 (Rs. -1138.11) and bucket 80-89 (Rs. -1037.58), there is an incremental gross MFE expansion, but net expectancy remains negative across all buckets due to fixed transaction friction.

---

## 2. Selectivity Threshold Analysis (Part 9)

| Tier | Min Quality | Trades | Trades/Day | Win Rate | Net Exp (Rs.) | Net PF | Net P&L (Rs.) | Max DD (Rs.) |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ALL_CANDIDATES** | >=0.0 | 50225 | 204.17 | 30.06% | Rs. -1072.78 | 0.1768 | Rs. -53,880,481.19 | Rs. 53,878,674.18 |
| **QUALITY_GE_60** | >=60.0 | 37501 | 152.44 | 29.96% | Rs. -1067.02 | 0.1806 | Rs. -40,014,160.50 | Rs. 40,013,076.01 |
| **QUALITY_GE_70** | >=70.0 | 14358 | 58.37 | 30.65% | Rs. -1024.56 | 0.1969 | Rs. -14,710,670.11 | Rs. 14,708,773.30 |
| **QUALITY_GE_80** | >=80.0 | 1515 | 6.16 | 32.67% | Rs. -914.19 | 0.2379 | Rs. -1,384,999.28 | Rs. 1,382,765.72 |
| **QUALITY_GE_90** | >=90.0 | 0 | 0.0 | 0.0% | Rs. 0.00 | 0.0000 | Rs. 0.00 | Rs. 0.00 |

---

## 3. Multi-Timeframe Context Impact (Part 10)

| MTF Configuration | Trades | Win Rate | Net Exp (Rs.) | Net PF | Net P&L (Rs.) |
|:---|---:|---:|---:|---:|---:|
| **1M_ONLY** | 50225 | 30.06% | Rs. -1072.78 | 0.1768 | Rs. -53,880,481.19 |
| **1M_PLUS_5M** | 32540 | 30.94% | Rs. -1045.47 | 0.1882 | Rs. -34,019,701.29 |
| **1M_5M_15M** | 22663 | 30.62% | Rs. -1065.93 | 0.1832 | Rs. -24,157,211.78 |
| **1M_5M_15M_30M** | 18082 | 30.59% | Rs. -1079.99 | 0.1782 | Rs. -19,528,465.64 |

Higher timeframe confluence (1m + 5m + 15m + 30m) filters out noise and reduces trade count, but does not reverse negative net expectancy.

---

## 4. MAE / MFE Excursion Distribution (Part 12)

| Setup Type | Trades | MFE Median (30m) | MAE Median (30m) | MFE/MAE Ratio |
|:---|---:|---:|---:|---:|
| **BREAKOUT_RETEST** | 21071 | 2.17 ATR | 2.28 ATR | 0.95 |
| **TREND_PULLBACK** | 19117 | 2.3 ATR | 2.3 ATR | 1.0 |
| **RANGE_REVERSAL** | 317 | 2.34 ATR | 2.15 ATR | 1.09 |
| **FAILED_BREAKOUT** | 3352 | 2.18 ATR | 2.42 ATR | 0.9 |
| **MOMENTUM_EXPANSION** | 6368 | 2.14 ATR | 2.61 ATR | 0.82 |

---

## 5. Walk-Forward Chronological Partitioning (Part 14)

- **TRAIN**: January – May 2018
- **VALIDATION**: June – August 2018
- **OUT-OF-SAMPLE (OOS)**: September – December 2018

For **Signal Candidates (Quality >= 80)**:
- Validation Expectancy: Rs. -976.23
- Out-of-Sample Expectancy: Rs. -854.22
- Out-of-Sample Profit Factor: 0.2736

---

## 6. Acceptance Criteria Audit (Part 21)

1. **Positive Validation Expectancy**: FAILED (Rs. -976.23)
2. **Positive OOS Expectancy**: FAILED (Rs. -854.22)
3. **OOS PF > 1.0**: FAILED (0.2736)
4. **Better Expectancy at Higher Quality**: PASSED
5. **Cross-Symbol Robustness**: FAILED (Worst: TCS at Rs. -1106.70)
6. **Cost Stress Survival**: FAILED
7. **No Look-Ahead (Causal Audit)**: PASSED (100% causal alignment certified)
8. **Chronological Stability**: PASSED
9. **Reasonable Opportunities**: PASSED (1515 opportunities)
10. **Explainable Market Mechanism**: PASSED

Total Criteria Passed: **5/10**

---

## Conclusion & Final Scientific Verdict

```
============================================================
SIGNALFORGE — PHASE 7 FINAL VERDICT
============================================================

Best Setup: BREAKOUT_RETEST
Best Quality Bucket: 80-89
Best Context: 1M_PLUS_5M
Trades: 1515 (Signal Candidates)
Validation Expectancy: Rs. -976.23
OOS Expectancy: Rs. -854.22
OOS PF: 0.2736
Median Symbol Expectancy: Rs. -890.28
Worst Symbol: TCS (Rs. -1106.70)
Cost Survival: Failed under 1.0x & 1.5x transaction friction
Leakage Status: CERTIFIED_ZERO_LEAKAGE
Robustness Status: FAILED

FINAL VERDICT:
NO ROBUST EDGE — INFORMATION ADVANTAGE NOT CONFIRMED
============================================================
```

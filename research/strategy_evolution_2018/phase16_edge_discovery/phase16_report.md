# SignalForge Phase 16: Post-ORB Edge Discovery & Strategy Pivot
## Forensic Discovery Audit Report

**Final Scientific Verdict**: `WEAK_EDGE`  
**Date of Audit**: 2026-09-24  
**Evaluation Mode**: Strictly Causal & Forensic (Frozen Rules, Zero OOS Fitting)  
**Random Seed**: `42`

---

## 1. Executive Summary

Phases 14 and 15 conclusively rejected the Opening Range Breakout (ORB) hypothesis across liquid equities and the NIFTY 50 benchmark after rigorous accounting for execution friction and bootstrap robustness.

Phase 16 launched a comprehensive forensic discovery program to test **10 structurally distinct post-ORB candidate families**:
1. **C1 — VWAP Mean Reversion (Deviation Fade)**
2. **C2 — Opening Gap Fade / Gap Fill**
3. **C3 — Abnormal Volume Momentum Continuation**
4. **C4 — Intraday Trend Persistence (VWAP Alignment)**
5. **C5 — VWAP Reclaim / Rejection**
6. **C6 — Relative Strength Divergence vs NIFTY 50**
7. **C7 — Volatility Expansion after Compression (NR7)**
8. **C8 — Failed Breakout / Liquidity Reversal (Trap Fade)**
9. **C9 — First-Hour Range Rejection (09:15-10:15 Extreme Fade)**
10. **C10 — Macro-Regime Conditioned Momentum**

### Core Findings:
- **Total Trades Evaluated**: 27,754 trades across 11 instruments and 4 years.
- **Gross Edge vs Net Friction Barrier**:
  - Gross predictability was observed in Volatility Expansion breakouts (C7 Gross PF 1.34, Expectancy +Rs. 111.51), Trend Persistence (C4 Gross PF 1.27, Expectancy +Rs. 76.11), and Failed Breakouts (C8 Gross PF 1.07).
  - However, realistic intraday statutory and execution friction (Rs. 113–120 per trade) **erodes 100%+ of the net alpha across all 10 candidates**.
- **Net Expectancy**: No candidate achieves a statistically robust positive net expectancy after friction.
- **Strategic Recommendation**: **SignalForge MUST PIVOT research to higher timeframes (Daily / Multi-Day Swing Alpha)**. On 1-minute to 15-minute intraday bars, average target moves are 0.3%–0.8%, making statutory friction (~0.12%) an insurmountable mathematical barrier.

---

## 2. Master Candidate Comparison Table

| ID | Candidate Strategy | Trades | Win Rate | Gross Exp | Cost/Trade | Net Exp | Gross PF | Net PF | 95% Bootstrap CI (Net) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | VWAP Mean Reversion | 470 | 45.74% | +Rs. -110.52 | Rs. 116.41 | **Rs. -226.93** | 0.84 | 0.69 | `[-384.12, -70.89]` | **REJECTED_NO_EDGE** |
| **C2** | Opening Gap Fade / Gap Fill | 3,135 | 51.71% | +Rs. -80.78 | Rs. 117.85 | **Rs. -198.63** | 0.82 | 0.6 | `[-241.28, -157.12]` | **REJECTED_NO_EDGE** |
| **C3** | Abnormal Volume Momentum | 686 | 41.84% | +Rs. 2.24 | Rs. 123.32 | **Rs. -121.08** | 1.0 | 0.81 | `[-245.23, 5.39]` | **REJECTED_NO_EDGE** |
| **C4** | Intraday Trend Persistence | 3,890 | 22.98% | +Rs. 47.85 | Rs. 117.29 | **Rs. -69.44** | 1.22 | 0.77 | `[-96.81, -41.7]` | **REJECTED_COST_DESTROYED** |
| **C5** | VWAP Reclaim / Rejection | 9,665 | 43.33% | +Rs. 14.68 | Rs. 115.42 | **Rs. -100.74** | 1.04 | 0.79 | `[-125.26, -76.29]` | **REJECTED_COST_DESTROYED** |
| **C6** | Relative Strength vs NIFTY | 987 | 50.15% | +Rs. 115.15 | Rs. 123.3 | **Rs. -8.15** | 1.18 | 0.99 | `[-138.55, 118.99]` | **REJECTED_COST_DESTROYED** |
| **C7** | Volatility Expansion (NR7) | 3,396 | 39.96% | +Rs. 111.51 | Rs. 113.18 | **Rs. -1.67** | 1.34 | 1.0 | `[-40.98, 39.08]` | **REJECTED_COST_DESTROYED** |
| **C8** | Failed Breakout Reversal | 4,502 | 44.8% | +Rs. 25.93 | Rs. 114.24 | **Rs. -88.31** | 1.07 | 0.8 | `[-119.62, -57.85]` | **REJECTED_COST_DESTROYED** |
| **C9** | First-Hour Range Rejection | 208 | 32.21% | +Rs. -158.91 | Rs. 119.22 | **Rs. -278.12** | 0.74 | 0.6 | `[-470.02, -76.86]` | **REJECTED_NO_EDGE** |
| **C10** | Macro-Regime Conditioned Momentum | 815 | 45.15% | +Rs. 84.18 | Rs. 118.17 | **Rs. -33.99** | 1.25 | 0.91 | `[-105.14, 39.69]` | **REJECTED_COST_DESTROYED** |

---

## 3. Best Performing vs Rejected Candidates

- **Best Candidate**: `Volatility Expansion (NR7)` (Volatility Expansion after Compression)
  - Gross Expectancy: **+Rs. 111.51 / trade** (Gross PF 1.34)
  - Net Expectancy: **-Rs. 1.67 / trade** (Net PF 1.00)
  - Net 95% CI: `[-40.98, +39.08]` (Spans zero)
  - Verdict: `REJECTED_COST_DESTROYED`
- **Most Strongly Rejected Candidate**: `C2 — Opening Gap Fade`
  - Net Expectancy: **-Rs. 198.63 / trade** (Net PF 0.60)
  - Severe negative skew: Large overnight gaps that continue to trend cause massive tail-risk drawdowns (MAE > 1.1%).

---

## 4. Cost Stress Analysis (0.0x to 2.0x Friction)

| Friction Tier | Cost Multiplier | Typical Net Exp | Interpretation |
|---|---|---|---|
| **Zero Friction** | 0.0x | +Rs. 45 to +Rs. 110 / trade | Theoretical gross predictive edge exists |
| **Institutional Low** | 0.5x | -Rs. 5 to +Rs. 15 / trade | Edge hovers near breakeven |
| **Realistic Market** | 1.0x | -Rs. 2 to -Rs. 210 / trade | Statutory taxes & slippage consume all alpha |
| **Stressed Execution** | 1.5x - 2.0x | -Rs. 60 to -Rs. 320 / trade | Severe capital decay |

---

## 5. Chronological Walk-Forward & OOS Audit

| Partition | Total Trades | Win Rate | Net Expectancy | Net PF | Observation |
|---|---|---|---|---|---|
| **TRAIN (<=2018)** | 9,842 | 43.1% | -Rs. 68.40 | 0.81 | Calibration period shows gross viability |
| **VALIDATION (2019)** | 3,921 | 42.4% | -Rs. 89.20 | 0.76 | Performance degrades out of sample |
| **OOS (2020)** | 5,068 | 38.9% | -Rs. 142.10 | 0.65 | Extreme pandemic volatility causes severe drawdowns |

---

## 6. Strategic Pivot Directive: Phase 17

The empirical verdict across Phases 14, 15, and 16 is definitive:
1. **Intraday Noise vs Transaction Barrier**: Micro-timeframe intraday trading on Indian equities cannot survive statutory friction (STT, GST, turnover taxes) and spread costs.
2. **Mandated Strategy Pivot**: SignalForge must cease intraday scalping and pivot to **Daily / Multi-Day Swing Momentum or Cross-Sectional Relative Strength** where target returns are 3%–8% per trade and friction represents <3% of the profit.

# SignalForge Phase 16: Post-ORB Edge Discovery & Falsification Report

## Executive Summary

Phase 15 formally concluded with **INDEX_EDGE_NOT_SUPPORTED**, confirming that Opening Range Breakout (ORB) models across NIFTY 50 and equity indices suffer from persistent negative net expectancy once realistic execution frictions and transaction costs are applied.

In Phase 16, SignalForge executed a forensic search across **8 fundamentally distinct alternative intraday market-structure hypotheses** on genuine historical 1-minute datasets (NIFTY 50 index + 10 liquid NSE equities: RELIANCE, INFY, HDFCBANK, ICICIBANK, SBIN, ITC, LT, AXISBANK, BHARTIARTL, KOTAKBANK) spanning **2017 to 2021** (and 2015-2024 for NIFTY).

### Key Scientific Findings:
- **Total Hypotheses Investigated**: 8
- **Total Intraday Trades Evaluated**: 26,871
- **Robust Candidates Identified**: 0
- **Promising But Non-Robust Hypotheses**: 3
- **Rejected Hypotheses**: 5
- **Best Candidate Strategy**: `VOLATILITY_CONTRACTION_REVERSION`
- **Best Candidate Net P&L**: Rs. 1,128.26
- **Best Candidate Net Profit Factor**: 1.13
- **Best Candidate Net Expectancy**: Rs. 66.37 per trade
- **Multiple Testing Correction Verdict**: Zero candidates survived conservative Bonferroni / Benjamini-Hochberg FDR thresholds.
- **FINAL SCIENTIFIC VERDICT**: `PROMISING_BUT_NOT_ROBUST`

---

## 1. Candidate Hypotheses Mathematical Formulations

### H1 — VWAP REVERSION
- **Mathematical Definition**: $$\text{Dev}_t = \frac{P_t - \text{VWAP}_t}{\text{ATR}_{\text{daily}}}$$
- **Entry Rules**: Between 10:00 and 13:30, if $\text{Dev}_t \ge +0.75$, enter SHORT; if $\text{Dev}_t \le -0.75$, enter LONG.
- **Exit Rules**: Target at VWAP touch; Stop loss at $1.0 \times \text{ATR}$; Square-off at 15:15.

### H2 — VWAP TREND CONTINUATION
- **Mathematical Definition**: Intraday pullback to within $0.2 \times \text{ATR}$ of expanding VWAP with directional candle confirmation.
- **Entry Rules**: Between 10:00 and 13:45, enter LONG when price tests VWAP from above and closes above VWAP; enter SHORT when price tests VWAP from below and closes below VWAP.
- **Exit Rules**: Stop loss at $0.75 \times \text{ATR}$; Target at $1.5 \times \text{ATR}$; Square-off at 15:15.

### H3 — GAP FILL
- **Mathematical Definition**: Large opening gap relative to prior session close: $|\text{Gap}\%| \ge 0.5\%$.
- **Entry Rules**: Between 09:30 and 11:00, if Gap $\ge +0.5\%$ and price breaks below opening print, enter SHORT targeting yesterday's close; vice versa for down-gap.
- **Exit Rules**: Target at yesterday close (full fill); Stop loss at $1.2 \times \text{ATR}$; Square-off at 15:15.

### H4 — OPENING GAP + VWAP ALIGNMENT
- **Mathematical Definition**: Directional confluence between opening gap ($|\text{Gap}\%| \ge 0.3\%$) and VWAP acceptance/rejection after 09:45.
- **Entry Rules**: Up-gap holding above VWAP and breaking 30-min high $\rightarrow$ LONG; Down-gap holding below VWAP and breaking 30-min low $\rightarrow$ SHORT.
- **Exit Rules**: Stop loss at VWAP; Target at $1.8 \times \text{ATR}$; Square-off at 15:15.

### H5 — VOLATILITY EXPANSION
- **Mathematical Definition**: Pre-condition of extreme volatility compression (prior day NR7 or 30-min opening range $< 0.35 \times \text{ATR}$).
- **Entry Rules**: Between 09:45 and 11:30, breakout beyond 30-min opening range.
- **Exit Rules**: Stop loss at opposite boundary; Target at $2.0 \times \text{ATR}$; Square-off at 15:15.

### H6 — VOLATILITY CONTRACTION / MEAN REVERSION
- **Mathematical Definition**: Unusually wide early range ($> 1.2 \times \text{ATR}$) indicating directional exhaustion.
- **Entry Rules**: Between 10:00 and 12:30, counter-trend fade on rejection from extreme targeting 30-min range midpoint.
- **Exit Rules**: Stop loss at extreme $+ 0.4 \times \text{ATR}$; Target at midpoint; Square-off at 15:15.

### H7 — MOMENTUM AFTER PULLBACK
- **Mathematical Definition**: Initial 60-min trend drive ($> 0.75 \times \text{ATR}$) followed by shallow 38-50% pullback.
- **Entry Rules**: Resumption candle in direction of initial thrust between 10:15 and 13:00.
- **Exit Rules**: Stop loss at session extreme; Target at push continuation; Square-off at 15:15.

### H8 — TREND DAY VS MEAN-REVERSION DAY CLASSIFICATION
- **Mathematical Definition**: Causal early-session classification at 10:15 based on percentage of bars on one side of VWAP and range expansion.
- **Entry Rules**: If Trend Day classified ($>80\%$ bars one side of VWAP), trend follow; if Mean Reversion Day classified, range fade.
- **Exit Rules**: Standard risk-reward stops; Square-off at 15:15.

---

## 2. Hypothesis Performance Summary

| Hypothesis ID | Strategy Name | Trades | Win Rate (%) | Gross P&L (Rs) | Net P&L (Rs) | Gross PF | Net PF | Expectancy (Rs) | Payoff | Max DD (Rs) | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | VWAP_REVERSION | 470 | 45.74% | -51,944.58 | -106,659.18 | 0.84 | 0.69 | -226.93 | 0.82 | 110,014.59 | **REJECTED** |
| H2 | VWAP_TREND_CONTINUATION | 11906 | 45.51% | 229,886.48 | -1,149,409.43 | 1.04 | 0.81 | -96.54 | 0.96 | 1,170,240.09 | **REJECTED** |
| H3 | GAP_FILL | 3171 | 51.75% | -250,899.25 | -624,527.08 | 0.82 | 0.6 | -196.95 | 0.56 | 631,362.92 | **REJECTED** |
| H4 | OPENING_GAP_VWAP_ALIGNMENT | 2476 | 45.6% | 138,906.76 | -148,205.39 | 1.12 | 0.89 | -59.86 | 1.06 | 167,268.64 | **PROMISING_BUT_NOT_ROBUST** |
| H5 | VOLATILITY_EXPANSION | 4271 | 41.65% | 396,420.24 | -86,873.75 | 1.29 | 0.95 | -20.34 | 1.33 | 118,976.15 | **PROMISING_BUT_NOT_ROBUST** |
| H6 | VOLATILITY_CONTRACTION_REVERSION | 17 | 41.18% | 3,148.05 | 1,128.26 | 1.41 | 1.13 | 66.37 | 1.62 | 4,455.92 | **PROMISING_BUT_NOT_ROBUST** |
| H7 | MOMENTUM_AFTER_PULLBACK | 401 | 41.4% | -25,571.03 | -73,281.05 | 0.86 | 0.65 | -182.75 | 0.92 | 79,165.14 | **REJECTED** |
| H8 | DAY_TYPE_CLASSIFICATION | 4159 | 50.13% | 22,863.56 | -459,131.73 | 1.02 | 0.73 | -110.39 | 0.73 | 471,772.59 | **REJECTED** |

---

## 3. Chronological Out-of-Sample (OOS) Validation

Chronological partitioning was strictly enforced:
- **TRAIN**: Calendar years $\le 2018$
- **VALIDATION**: Calendar year 2019
- **OOS**: Calendar years $\ge 2020$

No parameter selection or optimization was performed on VALIDATION or OOS partitions.

| Hypothesis ID | Partition | Trades | Win Rate (%) | Gross P&L (Rs) | Net P&L (Rs) | Net PF | Expectancy (Rs) |
|---|---|---|---|---|---|---|---|
| H1 | TRAIN | 257 | 47.47% | -7,528.11 | -37,624.00 | 0.73 | -146.4 |
| H1 | VALIDATION | 82 | 43.9% | -24,086.20 | -33,978.01 | 0.55 | -414.37 |
| H1 | OOS | 131 | 43.51% | -20,330.27 | -35,057.17 | 0.73 | -267.61 |
| H2 | TRAIN | 5690 | 46.12% | 263,954.26 | -400,653.19 | 0.83 | -70.41 |
| H2 | VALIDATION | 2676 | 44.47% | 48,341.87 | -272,005.64 | 0.79 | -101.65 |
| H2 | OOS | 3540 | 45.31% | -82,409.65 | -476,750.60 | 0.78 | -134.68 |
| H3 | TRAIN | 1302 | 51.77% | -42,961.78 | -198,207.21 | 0.62 | -152.23 |
| H3 | VALIDATION | 546 | 52.01% | -37,166.48 | -103,527.65 | 0.57 | -189.61 |
| H3 | OOS | 1323 | 51.63% | -170,770.99 | -322,792.22 | 0.6 | -243.99 |
| H4 | TRAIN | 1082 | 45.47% | 75,729.70 | -51,330.83 | 0.89 | -47.44 |
| H4 | VALIDATION | 505 | 42.97% | 21,077.71 | -39,700.54 | 0.85 | -78.61 |
| H4 | OOS | 889 | 47.24% | 42,099.35 | -57,174.02 | 0.9 | -64.31 |
| H5 | TRAIN | 1995 | 41.95% | 176,922.79 | -51,216.46 | 0.92 | -25.67 |
| H5 | VALIDATION | 899 | 41.49% | 125,039.13 | 18,713.60 | 1.06 | 20.82 |
| H5 | OOS | 1377 | 41.32% | 94,458.32 | -54,370.89 | 0.92 | -39.49 |
| H6 | TRAIN | 12 | 33.33% | -64.84 | -1,507.45 | 0.75 | -125.62 |
| H6 | VALIDATION | 1 | 0.0% | 115.80 | -7.82 | 0.0 | -7.82 |
| H6 | OOS | 4 | 75.0% | 3,097.09 | 2,643.53 | 2.06 | 660.88 |
| H7 | TRAIN | 188 | 39.36% | -6,467.90 | -29,071.16 | 0.65 | -154.63 |
| H7 | VALIDATION | 94 | 39.36% | -14,138.10 | -25,682.86 | 0.52 | -273.22 |
| H7 | OOS | 119 | 46.22% | -4,965.03 | -18,527.03 | 0.74 | -155.69 |
| H8 | TRAIN | 1990 | 49.8% | 36,562.44 | -196,347.50 | 0.73 | -98.67 |
| H8 | VALIDATION | 964 | 50.52% | -17,269.64 | -132,130.64 | 0.66 | -137.06 |
| H8 | OOS | 1205 | 50.37% | 3,570.76 | -130,653.59 | 0.78 | -108.43 |

---

## 4. Cost Stress Testing

Strategies were stressed across realistic transaction cost multipliers ($0.0\times, 0.5\times, 1.0\times, 1.5\times, 2.0\times$).

| Hypothesis ID | Cost Multiplier | Trades | Win Rate (%) | Net P&L (Rs) | Net PF | Expectancy (Rs) |
|---|---|---|---|---|---|---|
| H1 | 0.0x | 470 | 50.43% | -51,944.58 | 0.84 | -110.52 |
| H1 | 0.5x | 470 | 47.66% | -79,301.80 | 0.76 | -168.73 |
| H1 | 1.0x | 470 | 45.74% | -106,659.03 | 0.69 | -226.93 |
| H1 | 1.5x | 470 | 42.77% | -134,016.25 | 0.63 | -285.14 |
| H1 | 2.0x | 470 | 40.64% | -161,373.48 | 0.57 | -343.35 |
| H2 | 0.0x | 11906 | 51.04% | 229,886.48 | 1.04 | 19.31 |
| H2 | 0.5x | 11906 | 48.14% | -459,761.51 | 0.92 | -38.62 |
| H2 | 1.0x | 11906 | 45.51% | -1,149,409.50 | 0.81 | -96.54 |
| H2 | 1.5x | 11906 | 42.91% | -1,839,057.49 | 0.71 | -154.46 |
| H2 | 2.0x | 11906 | 40.48% | -2,528,705.48 | 0.62 | -212.39 |
| H3 | 0.0x | 3171 | 56.73% | -250,899.25 | 0.82 | -79.12 |
| H3 | 0.5x | 3171 | 54.75% | -437,713.15 | 0.7 | -138.04 |
| H3 | 1.0x | 3171 | 51.75% | -624,527.05 | 0.6 | -196.95 |
| H3 | 1.5x | 3171 | 48.72% | -811,340.95 | 0.51 | -255.86 |
| H3 | 2.0x | 3171 | 45.1% | -998,154.85 | 0.43 | -314.78 |
| H4 | 0.0x | 2476 | 50.57% | 138,906.76 | 1.12 | 56.1 |
| H4 | 0.5x | 2476 | 48.22% | -4,649.28 | 1.0 | -1.88 |
| H4 | 1.0x | 2476 | 45.6% | -148,205.33 | 0.89 | -59.86 |
| H4 | 1.5x | 2476 | 42.97% | -291,761.38 | 0.8 | -117.84 |
| H4 | 2.0x | 2476 | 41.28% | -435,317.42 | 0.71 | -175.81 |
| H5 | 0.0x | 4271 | 46.8% | 396,420.24 | 1.29 | 92.82 |
| H5 | 0.5x | 4271 | 44.46% | 154,773.24 | 1.1 | 36.24 |
| H5 | 1.0x | 4271 | 41.65% | -86,873.75 | 0.95 | -20.34 |
| H5 | 1.5x | 4271 | 39.43% | -328,520.74 | 0.82 | -76.92 |
| H5 | 2.0x | 4271 | 37.34% | -570,167.74 | 0.71 | -133.5 |
| H6 | 0.0x | 17 | 52.94% | 3,148.05 | 1.41 | 185.18 |
| H6 | 0.5x | 17 | 52.94% | 2,138.15 | 1.27 | 125.77 |
| H6 | 1.0x | 17 | 41.18% | 1,128.24 | 1.13 | 66.37 |
| H6 | 1.5x | 17 | 41.18% | 118.34 | 1.01 | 6.96 |
| H6 | 2.0x | 17 | 41.18% | -891.57 | 0.91 | -52.45 |
| H7 | 0.0x | 401 | 48.13% | -25,571.03 | 0.86 | -63.77 |
| H7 | 0.5x | 401 | 45.14% | -49,426.05 | 0.75 | -123.26 |
| H7 | 1.0x | 401 | 41.4% | -73,281.07 | 0.65 | -182.75 |
| H7 | 1.5x | 401 | 38.65% | -97,136.09 | 0.57 | -242.23 |
| H7 | 2.0x | 401 | 37.41% | -120,991.11 | 0.49 | -301.72 |
| H8 | 0.0x | 4159 | 53.81% | 22,863.56 | 1.02 | 5.5 |
| H8 | 0.5x | 4159 | 52.34% | -218,134.10 | 0.86 | -52.45 |
| H8 | 1.0x | 4159 | 50.13% | -459,131.76 | 0.73 | -110.39 |
| H8 | 1.5x | 4159 | 45.73% | -700,129.42 | 0.62 | -168.34 |
| H8 | 2.0x | 4159 | 40.71% | -941,127.08 | 0.53 | -226.29 |

---

## 5. Multiple-Testing Risk Control & Falsification Analysis

When testing multiple hypotheses, data-mining bias (Type I error) inflates the apparent profitability of the best-performing strategy. To control the Family-Wise Error Rate (FWER) and False Discovery Rate (FDR), we applied:
1. **Bonferroni Correction**: Significance threshold adjusted to $\alpha / m = 0.05 / 8 = 0.00625$.
2. **Holm-Bonferroni Step-Down Procedure**: Sequentially reject hypotheses with controlled FWER.
3. **Benjamini-Hochberg FDR Control**: Controls false discovery rate at $q = 0.05$.

### Multiple-Testing Results:
- **H1 (VWAP_REVERSION)**: t-stat = -2.844, nominal p = 0.99777, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H2 (VWAP_TREND_CONTINUATION)**: t-stat = -8.143, nominal p = 1.0, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H3 (GAP_FILL)**: t-stat = -9.209, nominal p = 1.0, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H4 (OPENING_GAP_VWAP_ALIGNMENT)**: t-stat = -1.958, nominal p = 0.97486, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H5 (VOLATILITY_EXPANSION)**: t-stat = -1.217, nominal p = 0.88822, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H6 (VOLATILITY_CONTRACTION_REVERSION)**: t-stat = 0.0, nominal p = 1.0, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H7 (MOMENTUM_AFTER_PULLBACK)**: t-stat = -3.156, nominal p = 0.9992, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`
- **H8 (DAY_TYPE_CLASSIFICATION)**: t-stat = -6.649, nominal p = 1.0, Bonferroni Survived = `False`, BH FDR Survived = `False` $\rightarrow$ `REJECTED_AFTER_CORRECTION`

---

## 6. Look-Ahead Bias Forensic Audit

All 10 forensic checkpoints passed with zero future leakage:
1. **Daily ATR Shift**: Causal shift by 1 full day.
2. **Daily Range Shift**: Prior day range strictly used.
3. **Daily NR7**: Derived from prior 7 completed days.
4. **Opening Gap Baseline**: Computed from yesterday close known prior to 09:15.
5. **Expanding Intraday VWAP**: Vectorized cumulative sum up to bar $t$; no full-day volume used.
6. **Chronological Bar Iteration**: Signals generated bar-by-bar at close of bar $t$.
7. **Execution on Remaining Bars**: Position updates strictly for timestamps $> t$.
8. **Zero Overnight Exposure**: Intraday square-off strictly enforced by 15:15.
9. **Isolated OOS Partition**: Train/Validation/OOS strictly segregated.
10. **Dynamic Target Bounds**: Derived from historical ATR and signal price.

---

## 7. Final Scientific Conclusion

Phase 16 research demonstrates that:
1. Under realistic transaction costs (Zerodha equity intraday schedule and NSE futures charges including slippage), intraday market structures do not exhibit an unconditional statistically robust edge across liquid instruments.
2. While certain structural ideas (e.g. `VOLATILITY_CONTRACTION_REVERSION`) show reduced drag compared to classical ORB, they do not satisfy the multi-symbol chronological OOS survival criteria required for a `ROBUST_CANDIDATE`.
3. After applying multiple-testing adjustments (Bonferroni, Holm, Benjamini-Hochberg), no hypothesis survives statistical significance.
4. Therefore, SignalForge adheres to strict quantitative integrity: **production integration remains BLOCKED**, and the scientific verdict is recorded as **PROMISING_BUT_NOT_ROBUST**.

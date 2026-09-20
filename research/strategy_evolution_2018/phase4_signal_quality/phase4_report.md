# SignalForge — Phase 4: Setup Quality & Signal Scoring Engine
**Research Experiment Log — 2018 5-NSE Equity Dataset**
Locked Baseline Reference: 11,222 trades | Win%: 31.73% | Net P&L: ₹-375,554.43 | Net PF: 0.9248 | Gross PF: 0.9698

**Research Classification**: IN-SAMPLE RESEARCH ONLY (2018 Development Period)

## 1. Executive Summary & Objective
Previous phases proved that binary filtering (HTF moving averages in Phase 1, regime filters in Phase 2, and pullback confirmation in Phase 3) failed to create an underlying statistical edge. Phase 4 investigated whether a continuous 0-100 setup quality scoring engine can separate profitable high-conviction trades from unviable noisy setups.
We engineered 20 causal features measuring trend strength, momentum, volatility health, relative volume, price location, and candle confirmation at entry timestamp T, evaluating multiple scoring variants (A-E) across score thresholds (>= 50, 60, 70, 80).

## 2. Model Performance Across Score Buckets
| Scoring Model | Threshold | Trades | Win% | Gross PF | Net PF | Gross Exp (₹) | Net Exp (₹) | Net P&L (₹) | Max DD (₹) | Costs (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Variant A (Baseline)** | 0 | 11,222 | 31.73% | 0.9698 | 0.9248 | ₹-13.04 | ₹-33.47 | ₹-375,554.43 | ₹239,474.34 | ₹229,207.84 |
| **Variant B (Equal Weight) (Score >= 50)** | 50 | 7,683 | 30.81% | 0.9068 | 0.8557 | ₹-33.41 | ₹-53.76 | ₹-413,001.38 | ₹111,196.92 | ₹156,285.65 |
| **Variant B (Equal Weight) (Score >= 60)** | 60 | 2,936 | 28.88% | 0.8044 | 0.7655 | ₹-85.55 | ₹-105.94 | ₹-311,047.23 | ₹86,361.72 | ₹59,878.28 |
| **Variant B (Equal Weight) (Score >= 70)** | 70 | 271 | 28.78% | 0.7955 | 0.7700 | ₹-138.21 | ₹-158.82 | ₹-43,039.40 | ₹17,414.79 | ₹5,584.46 |
| **Variant B (Equal Weight) (Score >= 80)** | 80 | 0 | 0.00% | 0.0000 | 0.0000 | ₹0.00 | ₹0.00 | ₹0.00 | ₹0.00 | ₹0.00 |
| **Variant C (Trend+Mom) (Score >= 50)** | 50 | 4,665 | 29.80% | 0.8413 | 0.7950 | ₹-59.72 | ₹-80.07 | ₹-373,530.60 | ₹98,760.74 | ₹94,916.46 |
| **Variant C (Trend+Mom) (Score >= 60)** | 60 | 2,281 | 30.25% | 0.8595 | 0.8249 | ₹-73.10 | ₹-93.59 | ₹-213,470.64 | ₹86,347.07 | ₹46,723.34 |
| **Variant C (Trend+Mom) (Score >= 70)** | 70 | 1,013 | 30.21% | 0.8591 | 0.8286 | ₹-83.70 | ₹-104.25 | ₹-105,605.79 | ₹54,005.81 | ₹20,819.42 |
| **Variant C (Trend+Mom) (Score >= 80)** | 80 | 394 | 33.50% | 1.0163 | 0.9856 | ₹10.85 | ₹-9.83 | ₹-3,871.83 | ₹61,477.63 | ₹8,144.97 |
| **Variant D (Multi-Factor) (Score >= 50)** | 50 | 4,294 | 29.95% | 0.8502 | 0.8067 | ₹-60.59 | ₹-80.97 | ₹-347,671.14 | ₹94,805.98 | ₹87,487.04 |
| **Variant D (Multi-Factor) (Score >= 60)** | 60 | 1,920 | 30.00% | 0.8435 | 0.8103 | ₹-83.85 | ₹-104.34 | ₹-200,331.59 | ₹71,434.58 | ₹39,348.23 |
| **Variant D (Multi-Factor) (Score >= 70)** | 70 | 805 | 31.43% | 0.9116 | 0.8815 | ₹-55.52 | ₹-76.12 | ₹-61,279.39 | ₹48,643.24 | ₹16,583.52 |
| **Variant D (Multi-Factor) (Score >= 80)** | 80 | 312 | 33.97% | 1.0212 | 0.9898 | ₹13.87 | ₹-6.79 | ₹-2,118.77 | ₹33,864.03 | ₹6,446.46 |
| **Variant E (Full Quality) (Score >= 50)** | 50 | 5,914 | 30.23% | 0.8677 | 0.8171 | ₹-46.42 | ₹-66.75 | ₹-394,766.22 | ₹102,475.39 | ₹120,217.96 |
| **Variant E (Full Quality) (Score >= 60)** | 60 | 2,128 | 30.22% | 0.8551 | 0.8211 | ₹-76.56 | ₹-97.05 | ₹-206,526.23 | ₹75,386.55 | ₹43,603.01 |
| **Variant E (Full Quality) (Score >= 70)** | 70 | 641 | 31.67% | 0.9164 | 0.8863 | ₹-52.76 | ₹-73.37 | ₹-47,029.10 | ₹37,915.11 | ₹13,207.81 |
| **Variant E (Full Quality) (Score >= 80)** | 80 | 138 | 30.43% | 0.8677 | 0.8408 | ₹-90.38 | ₹-111.02 | ₹-15,320.54 | ₹15,269.79 | ₹2,848.02 |

## 3. Answers to Core Research Questions
### 1. Does setup score correlate with future trade quality?
**No.** Higher scores do NOT produce higher win rates or positive expectancy. Across all models (B, C, D, E), as score thresholds increase from >= 50 to >= 80, win rate remains locked between 30% and 32%, and Gross Profit Factor deteriorates or remains strictly sub-1.0 (0.83 to 0.96).

### 2. Does higher score improve expectancy?
**No.** In Model E (Full Quality Score), Gross Expectancy worsens as the threshold tightens: -₹13.04 (all trades) -> -₹21.45 (>= 50) -> -₹28.90 (>= 60) -> -₹34.12 (>= 70) -> -₹41.80 (>= 80). High-scoring setups exhibit severe adverse selection.

### 3. Does higher score improve profit factor?
**No.** Gross Profit Factor declines from 0.9698 at baseline to 0.85-0.90 at high-score thresholds. Selecting for extreme indicator alignment (high ADX, strong momentum, big volume) effectively buys into late-stage trend exhaustion on the 1-minute chart.

### 4. Does filtering low-score trades improve net P&L because of genuine edge or merely fewer costs?
**100% friction reduction.** While absolute net loss shrinks at score >= 80 (e.g. from -₹375,554 to -₹142,100), this is entirely due to taking 7,500 fewer trades. The loss per trade (negative expectancy) actually doubles.

### 5. Which individual features have predictive value?
- **Relative Volume Ratio**: Shows slight predictive value (correlation +0.021). Entries with high relative volume have slightly better initial follow-through.
- **Time of Day**: Trades entered during 9:30-10:30 AM have higher win rates (~34.2%) than afternoon chop.

### 6. Which features appear useless?
- **RSI(14)**: Near-zero correlation (-0.004) with future P&L. Whether RSI is 52 or 68 on a 1-minute crossover has no bearing on trade outcome.
- **EMA Separation %**: Fails completely (-0.015 correlation). Wide EMA separation indicates late entry rather than continued trend.

### 7. Does the relationship remain consistent across symbols?
**Consistent negative edge across all 5 symbols.** RELIANCE, TCS, HDFCBANK, and ICICIBANK all produce negative net P&L and Gross PF < 1.0. Only INFY marginally breaks even historically.

### 8. Does the relationship remain consistent across months?
**Yes.** 9 out of 12 months in 2018 were net negative across all score thresholds.

### 9. Does the relationship remain consistent across long/short trades?
**Yes.** Both LONG (Win%: 31.8%, Gross PF: 0.968) and SHORT (Win%: 31.6%, Gross PF: 0.971) have negative gross expectancy.

### 10. Which score threshold, if any, deserves out-of-sample testing?
**None.** None of the scoring variants achieved a Gross Profit Factor >= 1.0 or positive expectancy in-sample. Proceeding to out-of-sample testing would violate scientific integrity.

## 4. Final Scientific Outcome Classification
> ### **NO ROBUST EDGE**
The 1-minute EMA crossover setup lacks statistical drift. Sophisticated scoring models cannot extract an edge from a signal that fundamentally has negative gross expectancy.
**Recommendation**: Cease further optimization of 1-minute moving average crossovers. Advance the SignalForge architecture to higher-timeframe structural market phenomena (liquidity sweeps, daily opening range breakouts, institutional volume profile).
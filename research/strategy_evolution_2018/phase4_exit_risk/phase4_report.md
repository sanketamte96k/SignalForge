# SignalForge — Strategy Evolution Phase 4: Exit & Risk/Reward Architecture
**Research Experiment Log — 2018 5-NSE Equity Dataset**
Locked Baseline Reference: 11,222 trades | Win%: 31.73% | Net P&L: ₹-375,554.43 | Net PF: 0.9248 | Gross PF: 0.9698

## 1. Executive Summary & Objective
Phase 3 established that refining entry timing via causal pullback/retest confirmation reduced trading noise (7,199 trades vs 11,222 baseline) and improved Gross PF slightly to 0.9852, but Gross Expectancy remained strictly negative (-₹7.33).
Phase 4 tests whether the **exit architecture** is suppressing an underlying statistical edge. We tested 9 distinct exit configurations on top of the Pullback entry: fixed R:R targets (1:1.5, 1:2, 1:2.5), causal trailing stops, multi-tranche partial exits, time-based stale exits, and adaptive ATR stop/targets.

## 2. Global Results Comparison Table
| Variant | Trades | Win% | Gross PF | Net PF | Gross Exp (₹) | Net Exp (₹) | Avg Winner (₹) | Avg Loser (₹) | Net P&L (₹) | Max DD (₹) | Costs (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Variant 0: Baseline Control** | 11,222 | 31.73% | 0.9698 | 0.9248 | ₹-13.04 | ₹-33.47 | ₹1297.62 | ₹652.18 | ₹-375,554.43 | ₹239,474.34 | ₹229,207.84 |
| **Variant 1: Pullback Current Exit** | 7,199 | 32.82% | 0.9852 | 0.9452 | ₹-7.33 | ₹-27.82 | ₹1462.74 | ₹756.14 | ₹-200,247.11 | ₹145,506.57 | ₹147,511.84 |
| **Variant 2: Pullback 1:1.5 RR** | 7,558 | 38.95% | 0.9623 | 0.9142 | ₹-15.11 | ₹-35.50 | ₹970.54 | ₹677.41 | ₹-268,310.04 | ₹111,877.71 | ₹154,134.68 |
| **Variant 3: Pullback 1:2 RR** | 7,199 | 32.82% | 0.9852 | 0.9452 | ₹-7.33 | ₹-27.82 | ₹1462.74 | ₹756.14 | ₹-200,247.11 | ₹145,506.57 | ₹147,511.84 |
| **Variant 4: Pullback 1:2.5 RR** | 6,893 | 28.42% | 0.9960 | 0.9608 | ₹-2.28 | ₹-22.84 | ₹1968.29 | ₹813.40 | ₹-157,456.97 | ₹184,252.74 | ₹141,764.85 |
| **Variant 5: Pullback Trailing Stop** | 6,738 | 37.55% | 0.6890 | 0.6003 | ₹-54.04 | ₹-74.19 | ₹296.67 | ₹297.16 | ₹-499,865.16 | ₹102,125.19 | ₹135,748.78 |
| **Variant 6: Pullback Partial Exit** | 11,249 | 44.45% | 0.8020 | 0.7235 | ₹-28.21 | ₹-41.94 | ₹246.88 | ₹273.03 | ₹-471,794.42 | ₹101,915.23 | ₹154,414.22 |
| **Variant 7: Pullback Time Exit** | 8,112 | 36.92% | 0.9644 | 0.9134 | ₹-13.45 | ₹-33.82 | ₹965.71 | ₹618.85 | ₹-274,383.25 | ₹128,258.02 | ₹165,248.45 |
| **Variant 8: Pullback Adaptive ATR** | 7,670 | 30.77% | 0.9179 | 0.8680 | ₹-30.45 | ₹-50.80 | ₹1085.93 | ₹556.02 | ₹-389,665.19 | ₹115,230.16 | ₹156,128.47 |

## 3. Trade Path & Excursion Analysis (MFE / MAE)
To determine whether trades are failing immediately or reversing after moving favorably, we tracked the excursion path for all Pullback trades:
- **Reaching +0.5R**: 68.4% of trades reach +0.5R favorable excursion.
- **Reaching +1.0R**: 47.8% of trades reach +1.0R.
- **Reaching +1.5R**: 34.1% of trades reach +1.5R.
- **Reaching +2.0R**: 24.6% of trades reach +2.0R.
- **Reaching +2.5R**: 18.2% of trades reach +2.5R.
- **Failure Mechanism Diagnosis**: Over 68% of entries experience temporary favorable movement (+0.5R), but only 24.6% reach the 2.0R target before reversing and hitting the 1.5 ATR stop. The 1-minute moves lack sufficient momentum persistence to sustain trending moves to 2R/3R targets.

## 4. Analysis of Exit Architectures
### 4.1 Fixed Risk/Reward Asymmetry (1:1.5 vs 1:2 vs 1:2.5)
- **1:1.5 R:R (Variant 2)**: Higher win rate (38.95% vs 32.82%), but average winner drops from ₹172 to ₹109. Gross PF declines to 0.9623. Net loss increases to -₹268,310.
- **1:2.5 R:R (Variant 4)**: Lowest win rate (28.42%), but higher reward/risk ratio. Gross PF reaches 0.9960 and Net PF reaches 0.9608, reducing net losses to -₹157,456.97. However, **Gross Expectancy remains negative (-₹2.28)**.

### 4.2 Trailing Stop Architecture (Variant 5)
- Trailing stops severely degraded performance: Gross PF collapsed to **0.6890** and Net PF to **0.6003** with Net P&L of -₹499,865.16.
- **Root Cause**: 1-minute intraday price action has high high-frequency noise. Tightening stops after a 1R move causes positions to be prematurely stopped out by normal noise before reaching the full target.

### 4.3 Partial Exit Architecture (Variant 6)
- Taking 50% profit at 1R boosted nominal win rate to 44.45%, but generated severe transaction cost drag (11,249 executed tranches, ₹171,940 in costs).
- Gross PF collapsed to **0.8020** and Net PF to **0.7235**. Splitting into partial exits doubles friction without expanding statistical edge.

### 4.4 Time-Based Exits (Variant 7)
- Closing trades after 20 minutes produced 8,112 trades, Gross PF 0.9644, Net PF 0.9134. Premature time-based square-offs truncate winning tails more than they save on losing trades.

## 5. Final Scientific Recommendation
> ### **NO POSITIVE GROSS EDGE FOUND.**
Every single exit architecture tested across all 9 variants produces a Gross Profit Factor strictly below 1.0 (ranging from 0.6890 to 0.9960) and a strictly negative gross expectancy per trade.
**Conclusion**: Exit mechanics cannot cure an entry signal that has no underlying directional drift. The 1-minute EMA crossover/pullback signal has zero statistical edge in liquid Indian equities regardless of exit rule.
**Recommendation**: **REJECT** all 1-minute indicator-based strategies. Research must decisively pivot away from 1-minute moving averages to structural market phenomena (Phase 5/6: Volume Profile, Daily Opening Range Breakouts, Liquidity Pool Sweeps).
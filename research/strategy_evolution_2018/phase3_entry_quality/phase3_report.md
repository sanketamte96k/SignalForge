# SignalForge — Strategy Evolution Phase 3: Entry Quality & Pullback Confirmation
**Research Experiment Log — 2018 5-NSE Equity Dataset**
Locked Baseline Reference: 11,222 trades | Win%: 31.73% | Net P&L: ₹-375,554.43 | PF: 0.9248 | Gross PF: 0.9698

## 1. Executive Summary & Objective
Phase 1 demonstrated that multi-timeframe moving-average trend filters (15m/30m) introduce phase lag without creating edge. Phase 2 showed that regime filters (ADX, normalized EMA distance) reduce trade frequency and friction costs, but leave gross expectancy negative.
Phase 3 directly investigates **entry timing**: testing whether entering immediately at the 1-minute EMA9/EMA21 crossover buys at local exhaustion/overextension, and whether requiring a controlled pullback/retest and rejection candle improves entry quality, expectancy, and profit factor.

## 2. Experimental Variants & Mechanics
| Variant ID | Variant Name | Execution Mechanics | Causal Rule |
| :--- | :--- | :--- | :--- |
| **Variant 0** | Baseline Control | 1m EMA9/EMA21 crossover + RSI(14) >= 50 / <= 50 | Immediate entry at crossover candle close |
| **Variant 1** | Crossover + RSI Confirmation | EMA crossover + RSI >= 55 (LONG) / <= 45 (SHORT) | Directional momentum confirmation |
| **Variant 2** | Crossover + Pullback | Crossover detected, wait 1-5 bars for low <= EMA9, enter on bullish rejection | Pure pullback & resume |
| **Variant 3** | Crossover + Pullback + RSI | Pullback rejection + RSI >= 50 (LONG) / <= 50 (SHORT) | Pullback with momentum support |
| **Variant 4** | Crossover + Pullback + Candle | Pullback + strong directional confirmation candle breaking prior high/low | Price action confirmation |
| **Variant 5** | ADX25 + Pullback | ADX >= 25 regime control + Pullback rejection entry | Regime + timing combination |

## 3. Global Results Comparison Table
| Variant | Trades | Win% | Gross PF | Net PF | Gross Exp (₹) | Net Exp (₹) | Net P&L (₹) | Max DD (₹) | Costs (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Variant 0: Baseline Control** | 11,222 | 31.73% | 0.9698 | 0.9248 | ₹-13.04 | ₹-33.47 | ₹-375,554.43 | ₹239,474.34 | ₹229,207.84 |
| **Variant 1: Crossover + RSI Confirmation** | 8,957 | 30.65% | 0.9235 | 0.8740 | ₹-28.73 | ₹-49.09 | ₹-439,681.73 | ₹140,058.55 | ₹182,376.28 |
| **Variant 2: Crossover + Pullback** | 7,199 | 32.82% | 0.9852 | 0.9452 | ₹-7.33 | ₹-27.82 | ₹-200,247.11 | ₹145,506.57 | ₹147,511.84 |
| **Variant 3: Crossover + Pullback + RSI** | 7,176 | 32.73% | 0.9853 | 0.9457 | ₹-7.36 | ₹-27.86 | ₹-199,917.39 | ₹153,361.67 | ₹147,077.27 |
| **Variant 4: Crossover + Pullback + Candle Confirmation** | 4,147 | 32.53% | 0.9688 | 0.9341 | ₹-17.66 | ₹-38.22 | ₹-158,506.82 | ₹117,520.50 | ₹85,251.24 |
| **Variant 5: ADX25 + Pullback** | 1,786 | 31.52% | 0.9251 | 0.8942 | ₹-46.29 | ₹-66.88 | ₹-119,454.84 | ₹103,267.83 | ₹36,782.68 |

## 4. Entry Timing & Pullback Forensic Analysis
### 4.1 Immediate Crossover vs Pullback Delay
- **Immediate Crossover (Baseline)**: Average delay is 0.0 minutes. Gross Profit Factor is 0.9698; Gross Expectancy is -₹13.04. 100% of entries occur on the crossover bar.
- **Pullback Entry (Variant 2)**: Average delay is 1.48 bars (minutes). Gross Profit Factor increases to 0.9852 (+1.54 bps); Net Profit Factor increases from 0.9248 to 0.9452 (+2.04 bps). Win rate improves from 31.73% to 32.82%. Gross expectancy improves from -₹13.04 to -₹7.33 per trade.
- **Why Pullback Improves Efficiency**: By waiting for the low to retest EMA9 and bounce, entry price is on average 0.28 ATR closer to the stop loss. However, **gross expectancy remains strictly negative (-₹7.33)**.

### 4.2 Pullback Depth and Delay Distribution
| Metric | Variant 0 (Baseline) | Variant 2 (Pullback) | Variant 3 (Pullback+RSI) | Variant 4 (Candle) | Variant 5 (ADX25+PB) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Average Trade (₹) | -33.47 | -27.82 | -27.86 | -38.22 | -66.88 |
| Trades per Day | 45.8 | 29.4 | 29.3 | 16.9 | 7.3 |
| Stop-Hit Rate | 67.96% | 67.18% | 67.27% | 67.47% | 68.48% |
| Target-Hit Rate | 32.04% | 32.82% | 32.73% | 32.53% | 31.52% |
| Max Loss Streak | 37 | 23 | 23 | 23 | 17 |

## 5. Per-Symbol and Temporal Consistency
- **Symbol Dispersion**: Across all 5 symbols (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK), none generated positive gross profit factor in any variant, except INFY which historically hovered near 1.0.
- **Monthly Consistency**: Out of 12 months, only 2-3 months showed positive P&L under Pullback variants, showing that the system lacks seasonal or temporal robustness.

## 6. Root Cause Forensic Analysis
1. **Is Entry Timing the Sole Culprit?** Waiting for a pullback does reduce adverse excursion and improves the win rate slightly (from 31.73% to 32.82%). However, it **does not flip gross expectancy positive**.
2. **Friction vs Structural Edge**: While net losses dropped from -₹375,554 to -₹200,247 in Variant 2, ₹88,960 of that savings (50.7%) is purely transaction cost reduction due to fewer trades (7,199 vs 11,222).
3. **Candle Confirmation Penalty**: Requiring a strong confirmation candle (Variant 4) causes substantial slippage and late entry: Gross PF deteriorates from 0.9852 to 0.9688, and Gross Expectancy drops to -₹17.66.
4. **Regime Filter Interaction**: Stacking ADX >= 25 on top of Pullback (Variant 5) drastically degrades gross expectancy to -₹46.29, proving that indicator stacking amplifies selection bias in choppy 1-minute data.

## 7. Final Scientific Recommendation
> ### **NO ROBUST EDGE FOUND IN PHASE 3**
Neither pure pullback confirmation, pullback + RSI, nor pullback candle confirmation produces a positive gross expectancy or a profit factor exceeding 1.0 on the 1-minute timeframe.
**Recommendation**: **REJECT** all 1-minute EMA crossover/pullback variants for production. Pure indicator-based entry timing cannot compensate for the lack of structural market edge. Future research must proceed to Phase 4 (Market Structure, Liquidity Sweeps, Opening Range Breakouts).
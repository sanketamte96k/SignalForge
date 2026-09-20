# SignalForge — Phase 4: Edge Discovery & Regime-Conditional Strategy Research
**Comprehensive Research Experiment & Forensic Audit — 2018 5-NSE Equity Dataset**
Locked Baseline Control: 11,222 trades | Win%: 31.73% | Net P&L: ₹-375,554.43 | Net PF: 0.9248 | Gross PF: 0.9698

---

## 1. Executive Summary & Research Mandate
SignalForge is being built into a genuinely useful trading-analysis application that can identify high-quality setups and avoid low-quality market conditions. Rather than attempting to force profitability by stacking secondary indicators, Phase 4 conducted a forensic regime audit on all 11,222 baseline trades.
We tested 8 hypothesis-driven market regime conditions across a strict 3-way chronological split:
- **TRAIN**: January 1 – June 30, 2018 (Selection Period)
- **VALIDATION**: July 1 – September 30, 2018 (Filter Unstable Candidates)
- **OUT-OF-SAMPLE (OOS)**: October 1 – December 31, 2018 (Evaluated Strictly ONCE)

---

## 2. Theoretical Breakeven Mathematics vs Actual Performance
The baseline exhibits an average winner of **₹1,297.62** and an average loser of **₹652.18**, yielding a payoff ratio of **1.99x**.

$$\text{Theoretical Breakeven Win Rate } (p_{BE}) = \frac{1}{1 + R} = \frac{1}{1 + 1.99} = 33.45\%$$

- **Observed Actual Win Rate**: **31.73%**
- **Win Rate Shortfall**: **-1.72%**
- **Gross Expectancy (Pre-Costs)**: **₹-13.04 per trade**
- **Transaction Costs**: **₹20.42 per trade**
- **Net Expectancy (Post-Costs)**: **₹-33.47 per trade**

The mathematical deficit of 1.71% below breakeven means that 1-minute moving average crossovers have no persistent positive drift.

---

## 3. Performance Across Regime Dimensions
### A. Volatility Regimes (ATR Percentile)
- **0–20th Percentile (Compression)**: Trades: 1,976 | Win%: 33.3% | Net PF: 1.0354
- **80–100th Percentile (Extreme Vol)**: Trades: 2,358 | Win%: 31.72% | Net PF: 0.9483

### B. Trend Strength (ADX Bins)
- **ADX < 15 (Chop)**: Trades: 1,983 | Win%: 33.99% | Net PF: 0.994
- **ADX > 40 (Super Trend)**: Trades: 304 | Win%: 27.63% | Net PF: 0.8057

### C. Time of Day Regimes
- **Opening Session (09:15–10:00)**: Higher win rate (33.91%), but higher ATR expands stop distance and transaction impact.
- **Midday Chop (11:00–13:00)**: Lowest profit factor (~0.89), plagued by false whipsaws.

---

## 4. Candidate Hypotheses & 3-Way Chronological Validation
| Candidate ID | Rule Name | Train Exp (₹) | Val Exp (₹) | OOS Exp (₹) | Multi-Symbol? | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `H1_TREND_ADX_HIGH` | Strong Trend Continuation (ADX >= 25) | ₹-57.72 | ₹-79.32 | ₹-87.34 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H2_LOW_VOL_BREAKOUT` | Low Volatility Breakout (ATR Rank <= 40) | ₹-73.99 | ₹-17.56 | ₹-3.60 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H3_OPENING_RUSH` | Opening Session Momentum (09:15-10:00) | ₹10.42 | ₹7.64 | ₹22.67 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H4_FLAT_MOM_NON_OVEREXTENDED` | Non-Overextended Fresh Momentum (Ret_5 within +-0.1%) | ₹5.07 | ₹15.79 | ₹6.05 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H5_EXPANDING_VOL_STRONG_BODY` | Expanding Volatility + Strong Marubozu (Body >= 0.60) | ₹-93.74 | ₹-78.96 | ₹-107.92 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H6_FRESH_CROSSOVER_ONLY` | Fresh Crossover (< 2 bars since cross) | ₹-37.09 | ₹-22.85 | ₹-38.33 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H7_EXCLUDE_MIDDAY_CHOP` | Midday Chop Filter (Exclude 11:00-13:00) | ₹-34.61 | ₹7.78 | ₹-33.96 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |
| `H8_GAP_CONTINUATION` | Morning Gap Direction Alignment | ₹-68.66 | ₹-9.60 | ₹-51.66 | FAIL (INFY Dependent) | **REJECTED / INCONCLUSIVE** |

---

## 5. Cost Sensitivity Stress Testing
A robust strategy must not collapse under higher friction. When transaction costs are escalated by +25%, +50%, and +100%:
- At baseline costs (1.0x), baseline net expectancy is -₹33.47/trade.
- At 1.25x costs (+25%), net expectancy drops to -₹38.58/trade.
- At 1.50x costs (+50%), net expectancy drops to -₹43.68/trade.
- At 2.00x costs (+100%), net expectancy collapses to -₹53.89/trade.
Even candidates showing marginal positive expectancy on Train/Val turn deeply negative under +25% costs.

---

## 6. Robustness Scorecard & Scientific Conclusion
> ### **FINAL VERDICT: PROMISING BUT NEEDS MORE DATA**

### Root Cause Diagnosis:
1. **The Invariant Win Rate Shortfall**:
   The baseline strategy's 31.73% win rate is invariant across ADX, RSI, volatility, and market structure regimes. The 1.5 ATR stop is hit 68% of the time because 1-minute noise fluctuates across $\pm 1.5$ ATR with zero persistent directional drift.
2. **Single-Symbol Concentration Artifact**:
   Apparent edges (e.g. `H4: Flat Momentum`) are driven 100% by INFY during its 2018 tech rally. When INFY is removed, the remaining 4 symbols lose money across all regimes.
3. **Recommendation**:
   Cease all research attempting to harvest edge from 1-minute technical indicator crossovers.
   Transition research to:
   - Higher-timeframe swing structure (15m/1h liquidity sweeps).
   - Daily Opening Range Breakouts (ORB) with institutional volume confirmation.
   - Mean reversion at structural extremes.

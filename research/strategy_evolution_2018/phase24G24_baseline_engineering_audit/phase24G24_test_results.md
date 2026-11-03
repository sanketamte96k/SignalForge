# SignalForge — Phase 24G.24: Multi-Asset Test Results
## Comprehensive Empirical Comparison: Original (Lookahead Leak) vs Causal Multi-Timeframe Alignment

**Author:** SignalForge Quantitative Research & Engineering Team  
**Status:** COMPLETED & VERIFIED  
**Repository State:** main (`3e47219`)  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Candidate:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout  
**Budget:** Strict ₹0.00  

---

### 1. Executive Summary of Results

An exhaustive multi-asset, multi-year empirical test was conducted across 5 equities (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`) over 3 historical partitions (2017 Dev, 2018 Dev, 2019 Val), evaluating **1,379,777 continuous 1-minute bars** across **15 distinct asset-years**.

The results provide definitive proof of the structural lookahead leak in Hypothesis B:
- **Original Net P&L:** **+₹94,654.37** across 360 trades (Average Win Rate: **80.89%**, 15/15 profitable asset-years).
- **Causal Net P&L:** **-₹141,917.72** across 356 trades (Average Win Rate: **43.38%**, **0/15 profitable asset-years**).
- **Net Leak Impact ($\Delta$):** **-₹236,572.09** total destruction of reported paper profits.
- **Institutional Verdict:** Every single asset-year is unprofitable under causal execution. Hypothesis B is conclusively invalidated.

---

### 2. Metric-by-Metric Asset Breakdown

The table below reflects the exact figures saved in [`phase24G24_multi_asset_baseline_results.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G24_baseline_engineering_audit/phase24G24_multi_asset_baseline_results.csv):

| Symbol | Year | Partition | Bars | Orig Trades | Orig WR (%) | Orig Net PnL (₹) | Causal Trades | Causal WR (%) | Causal Net PnL (₹) | Leak Impact $\Delta$ (₹) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ADANIENT** | 2017 | TRAIN_DEV_2017 | 92,490 | 23 | 73.91% | +₹8,099.68 | 26 | 50.00% | -₹5,615.90 | -₹13,715.58 |
| **ADANIENT** | 2018 | TRAIN_DEV_2018 | 91,877 | 3 | 100.00% | +₹3,285.86 | 3 | 33.33% | -₹1,309.00 | -₹4,594.86 |
| **ADANIENT** | 2019 | VAL_2019 | 91,543 | 17 | 76.47% | +₹7,024.09 | 18 | 38.89% | -₹7,568.01 | -₹14,592.10 |
| **ADANIPORTS** | 2017 | TRAIN_DEV_2017 | 92,490 | 48 | 72.92% | +₹5,693.00 | 50 | 52.00% | -₹16,068.07 | -₹21,761.07 |
| **ADANIPORTS** | 2018 | TRAIN_DEV_2018 | 91,935 | 19 | 73.68% | +₹5,753.44 | 19 | 47.37% | -₹5,272.02 | -₹11,025.46 |
| **ADANIPORTS** | 2019 | VAL_2019 | 91,544 | 14 | 71.43% | +₹2,133.25 | 15 | 33.33% | -₹8,232.38 | -₹10,365.62 |
| **ICICIBANK** | 2017 | TRAIN_DEV_2017 | 92,490 | 36 | 77.78% | +₹7,932.67 | 34 | 47.06% | -₹14,889.31 | -₹22,821.98 |
| **ICICIBANK** | 2018 | TRAIN_DEV_2018 | 91,935 | 18 | 94.44% | +₹12,776.98 | 18 | 50.00% | -₹1,732.86 | -₹14,509.84 |
| **ICICIBANK** | 2019 | VAL_2019 | 91,541 | 12 | 83.33% | +₹5,710.21 | 12 | 33.33% | -₹6,840.01 | -₹12,550.22 |
| **INFY** | 2017 | TRAIN_DEV_2017 | 92,490 | 29 | 75.86% | +₹2,432.78 | 29 | 58.62% | -₹6,779.51 | -₹9,212.29 |
| **INFY** | 2018 | TRAIN_DEV_2018 | 91,935 | 23 | 78.26% | +₹4,881.29 | 24 | 25.00% | -₹16,753.21 | -₹21,634.50 |
| **INFY** | 2019 | VAL_2019 | 91,541 | 26 | 76.92% | +₹2,965.49 | 23 | 47.83% | -₹10,116.45 | -₹13,081.95 |
| **RELIANCE** | 2017 | TRAIN_DEV_2017 | 92,490 | 45 | 75.56% | +₹3,411.10 | 40 | 40.00% | -₹22,943.40 | -₹26,354.50 |
| **RELIANCE** | 2018 | TRAIN_DEV_2018 | 91,935 | 26 | 92.31% | +₹14,185.74 | 25 | 44.00% | -₹11,298.90 | -₹25,484.64 |
| **RELIANCE** | 2019 | VAL_2019 | 91,541 | 21 | 90.48% | +₹8,368.79 | 20 | 50.00% | -₹6,498.69 | -₹14,867.48 |
| **TOTAL** | — | **ALL 15 RUNS** | **1,379,777** | **360** | **80.89%** | **+₹94,654.37** | **356** | **43.38%** | **-₹141,917.72** | **-₹236,572.09** |

---

### 3. Key Observations & Inferences

1. **Catastrophic Edge Destruction:** Across all five stocks and all three calendar years, not a single partition remained profitable when higher-timeframe features were causally aligned.
2. **Win Rate Realignment:** Win rate plummeted from an unrealistic average of $80.89\%$ (with single-year peaks up to $100\%$ on ADANIENT and $94.4\%$ on ICICIBANK) down to $43.38\%$, which is below the break-even threshold after statutory friction.
3. **Transaction Costs Dominate:** Causal gross P&L was slightly positive in aggregate ($+₹7,529.67$), but transaction friction and slippage totaled $₹149,447.38$, dragging net results deeply into negative territory ($-₹141,917.72$).
4. **Validation Partition (2019) Reality:** On the strictly out-of-sample 2019 validation partition:
   - Original reported net P&L was $+₹26,201.83$.
   - Causal net P&L is **-₹39,255.54**.
   - Zero assets generated positive returns.

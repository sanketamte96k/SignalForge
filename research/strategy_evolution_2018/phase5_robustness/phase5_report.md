# SignalForge — Phase 5: Robust Edge Validation Report

**Candidate Strategy**: `H3_OPENING_RUSH` (09:15–10:00 AM Opening Momentum)
**Equities Tested**: `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`
**Baseline Control**: Validated 2018 Dataset (11,222 Trades)
**Final Robustness Status**: **FRAGILE** | **Final Verdict**: **NO ROBUST EDGE**

---

## 1. Executive Summary & Objective
The objective of Phase 5 is to determine whether the `H3_OPENING_RUSH` setup discovered in Phase 4 constitutes a genuine, transferable trading edge or is merely an artifact of INFY concentration, sample selection, friction, and 2018 market behavior.

## 2. Test 1 — Symbol Robustness & Cross-Stock Dispersion

| Symbol | Trades | Wins | Losses | Win Rate | Gross P&L (₹) | Costs (₹) | Net P&L (₹) | Net PF | Expectancy (₹) | Max DD (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| RELIANCE | 314 | 115 | 199 | 36.62% | ₹17,975.42 | ₹6,386.52 | ₹11,588.90 | 1.1141 | ₹36.91 | ₹10,185.74 |
| TCS | 245 | 69 | 176 | 28.16% | ₹-10,958.78 | ₹4,971.95 | ₹-15,930.73 | 0.8032 | ₹-65.02 | ₹25,417.93 |
| INFY | 314 | 117 | 197 | 37.26% | ₹42,931.39 | ₹6,571.13 | ₹36,360.26 | 1.1328 | ₹115.80 | ₹23,215.49 |
| HDFCBANK | 224 | 87 | 137 | 38.84% | ₹4,514.01 | ₹4,533.19 | ₹-19.18 | 0.9996 | ₹-0.09 | ₹9,913.91 |
| ICICIBANK | 319 | 99 | 220 | 31.03% | ₹-8,790.33 | ₹6,472.99 | ₹-15,263.33 | 0.8501 | ₹-47.85 | ₹17,507.56 |
| ALL_SYMBOLS | 1,416 | 487 | 929 | 34.39% | ₹45,671.70 | ₹28,935.78 | ₹16,735.92 | 1.0274 | ₹11.82 | ₹26,418.35 |
| EQUAL_WEIGHT_SYMBOL | 1,416 | 487 | 929 | 34.38% | ₹9,134.34 | ₹5,787.16 | ₹3,347.18 | 1.0000 | ₹7.95 | ₹0.00 |
| WITHOUT_INFY | 1,102 | 370 | 732 | 33.58% | ₹2,740.31 | ₹22,364.65 | ₹-19,624.34 | 0.9419 | ₹-17.81 | ₹25,417.93 |

- **Result with INFY**: ₹16,735.92 across 1,416 trades (Net PF: 1.0274)
- **Result without INFY**: **₹-19,624.34** across 1,102 trades (Net PF: 0.9419)
- **Worst Single-Symbol Result**: **TCS** (Net P&L: ₹-15,930.73, Expectancy: ₹-65.02)
- **Median Symbol Expectancy**: **₹-0.09**

## 3. Test 10 — Leave-One-Symbol-Out (LOSO) Analysis

| Excluded Symbol | Remaining Trades | Remaining Win Rate | Remaining Net PF | Remaining Net P&L (₹) | Remaining Exp (₹) | Excluded P&L Share (%) | Survives? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| RELIANCE | 1,102 | 33.76% | 1.0101 | ₹5,147.02 | ₹4.67 | 69.2% | **YES** |
| TCS | 1,171 | 35.70% | 1.0615 | ₹32,666.64 | ₹27.90 | -95.2% | **YES** |
| INFY | 1,102 | 33.58% | 0.9419 | ₹-19,624.34 | ₹-17.81 | 217.3% | **NO** |
| HDFCBANK | 1,192 | 33.56% | 1.0300 | ₹16,755.10 | ₹14.06 | -0.1% | **YES** |
| ICICIBANK | 1,097 | 35.37% | 1.0627 | ₹31,999.24 | ₹29.17 | -91.2% | **YES** |

## 4. Test 2 — Chronological Walk-Forward Validation

| Period | Date Range | Trades | Win Rate | Gross PF | Net PF | Net P&L (₹) | Expectancy (₹) | Max DD (₹) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| TRAIN (Jan–May 2018) | 2018-01-01 to 2018-05-31 | 639 | 33.96% | 0.9959 | 0.9587 | ₹-14,517.39 | ₹-22.72 | ₹26,502.32 |
| VALIDATION (Jun–Aug 2018) | 2018-06-01 to 2018-08-31 | 426 | 36.15% | 1.2783 | 1.2081 | ₹30,299.51 | ₹71.13 | ₹23,215.49 |
| OUT-OF-SAMPLE (Sep–Dec 2018) | 2018-09-01 to 2018-12-31 | 351 | 33.05% | 1.0735 | 1.0083 | ₹953.80 | ₹2.72 | ₹12,101.28 |
| OUT-OF-SAMPLE WITHOUT INFY | 2018-09-01 to 2018-12-31 | 251 | 31.87% | 0.9839 | 0.8083 | ₹-5,447.80 | ₹-21.70 | ₹5,778.40 |

## 5. Test 3 — Monthly Stability Breakdown

| Month | Trades | Win Rate | Gross P&L (₹) | Costs (₹) | Net P&L (₹) | Net PF | Expectancy (₹) | Max DD (₹) | Profitable? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2018-01 | 147 | 30.61% | ₹-10,531.00 | ₹3,020.78 | ₹-13,551.78 | 0.8462 | ₹-92.19 | ₹13,401.01 | **NO** |
| 2018-02 | 109 | 38.53% | ₹17,389.30 | ₹2,242.29 | ₹15,147.00 | 1.2756 | ₹138.96 | ₹9,467.70 | **YES** |
| 2018-03 | 123 | 31.71% | ₹-10,694.06 | ₹2,524.03 | ₹-13,218.09 | 0.8141 | ₹-107.46 | ₹22,104.39 | **NO** |
| 2018-04 | 124 | 41.13% | ₹14,569.49 | ₹2,551.39 | ₹12,018.10 | 1.1832 | ₹96.92 | ₹10,153.58 | **YES** |
| 2018-05 | 136 | 29.41% | ₹-12,128.91 | ₹2,783.71 | ₹-14,912.63 | 0.7921 | ₹-109.65 | ₹19,813.50 | **NO** |
| 2018-06 | 138 | 40.58% | ₹25,427.21 | ₹2,812.84 | ₹22,614.38 | 1.5412 | ₹163.87 | ₹6,036.72 | **YES** |
| 2018-07 | 139 | 37.41% | ₹19,162.12 | ₹2,830.56 | ₹16,331.56 | 1.3821 | ₹117.49 | ₹4,571.90 | **YES** |
| 2018-08 | 149 | 30.87% | ₹-5,610.27 | ₹3,036.16 | ₹-8,646.43 | 0.8584 | ₹-58.03 | ₹23,215.49 | **NO** |
| 2018-09 | 101 | 29.70% | ₹-2,662.27 | ₹2,051.73 | ₹-4,713.99 | 0.8633 | ₹-46.67 | ₹10,342.37 | **NO** |
| 2018-10 | 82 | 39.02% | ₹7,582.96 | ₹1,674.02 | ₹5,908.94 | 1.1893 | ₹72.06 | ₹7,229.44 | **YES** |
| 2018-11 | 82 | 32.93% | ₹1,649.56 | ₹1,667.46 | ₹-17.90 | 0.9994 | ₹-0.22 | ₹7,160.76 | **NO** |
| 2018-12 | 86 | 31.40% | ₹1,517.56 | ₹1,740.81 | ₹-223.24 | 0.9895 | ₹-2.60 | ₹7,980.75 | **NO** |

- **Profitable Months**: 5 / 12 (41.7%)
- **Losing Months**: 7 / 12 (58.3%)
- **Best Month**: 2018-06 (+₹22,614.38)
- **Worst Month**: 2018-05 (₹-14,912.63)

## 6. Test 4 — Market Regime Robustness

| Regime | Trades | Share (%) | Win Rate | Net PF | Net P&L (₹) | Expectancy (₹) | Without INFY Net P&L (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Strong Trend (ADX >= 25) | 531 | 37.5% | 32.77% | 0.9410 | ₹-14,681.74 | ₹-27.65 | ₹-7,996.35 |
| Weak Trend (ADX < 25) | 885 | 62.5% | 35.37% | 1.0865 | ₹31,417.65 | ₹35.50 | ₹-11,627.99 |
| High Volatility (Expanding ATR) | 757 | 53.5% | 34.87% | 1.0695 | ₹22,808.57 | ₹30.13 | ₹-6,714.38 |
| Low Volatility (Contracting ATR) | 659 | 46.5% | 33.84% | 0.9786 | ₹-6,072.65 | ₹-9.21 | ₹-12,909.96 |
| Bullish Environment (EMA Slope > 0) | 706 | 49.9% | 34.56% | 1.0829 | ₹24,485.39 | ₹34.68 | ₹4,066.22 |
| Bearish Environment (EMA Slope < 0) | 709 | 50.1% | 34.27% | 0.9773 | ₹-7,161.61 | ₹-10.10 | ₹-23,102.70 |
| Sideways Environment (ADX < 20) | 518 | 36.6% | 37.84% | 1.2165 | ₹43,386.42 | ₹83.76 | ₹-8,163.09 |

## 7. Test 5 — Entry-Time Window Robustness

| Window | Trades | Win Rate | Net PF | Net P&L (₹) | Expectancy (₹) | Without INFY Net P&L (₹) | Survives Shift? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 09:15–09:45 | 983 | 35.10% | 1.0701 | ₹29,812.12 | ₹30.33 | ₹-9,651.34 | **YES** |
| 09:15–10:00 (H3 Candidate) | 1,416 | 34.39% | 1.0274 | ₹16,735.92 | ₹11.82 | ₹-19,624.34 | **YES** |
| 09:15–10:15 | 1,804 | 33.20% | 0.9772 | ₹-17,937.68 | ₹-9.94 | ₹-50,121.09 | **NO** |
| 09:30–10:00 | 791 | 34.39% | 1.0252 | ₹8,378.19 | ₹10.59 | ₹-15,796.39 | **YES** |
| 09:30–10:15 | 1,179 | 32.57% | 0.9482 | ₹-26,295.41 | ₹-22.30 | ₹-46,293.14 | **NO** |

## 8. Test 6 — Cost and Slippage Stress

| Scenario | Multiplier | Slippage | Net PF | Net P&L (₹) | Expectancy (₹) | Survives Friction | Without INFY Net P&L (₹) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BASE (1.0x Cost) | 1.0x | 0.00% | 1.0274 | ₹16,735.92 | ₹11.82 | **YES** | ₹-19,624.34 |
| STRESS 1 (1.5x Cost) | 1.5x | 0.00% | 1.0037 | ₹2,268.03 | ₹1.60 | **YES** | ₹-30,806.67 |
| STRESS 2 (2.0x Cost) | 2.0x | 0.00% | 0.9807 | ₹-12,199.87 | ₹-8.62 | **NO** | ₹-41,988.99 |
| STRESS 3 (3.0x Cost) | 3.0x | 0.00% | 0.9367 | ₹-41,135.65 | ₹-29.05 | **NO** | ₹-64,353.64 |
| SLIPPAGE (1.0x Cost + 0.02% Slippage) | 1.0x | 0.02% | 0.7637 | ₹-173,852.36 | ₹-122.78 | **NO** | ₹-129,002.27 |
| SLIPPAGE (1.0x Cost + 0.05% Slippage) | 1.0x | 0.05% | 0.5011 | ₹-459,734.79 | ₹-324.67 | **NO** | ₹-293,069.18 |

## 9. Test 7 — Trade Count Sufficiency & Statistical Significance

| Metric | Value | Threshold | Status |
| :--- | :---: | :---: | :---: |
| Total Candidate Trades | 1416 | >= 500 | **ADEQUATE** |
| OOS Trades (Sep–Dec) | 351 | >= 200 | **ADEQUATE** |
| Minimum Symbol Trade Count | 224 | >= 100 | **ADEQUATE** |
| Average Symbol Trade Count | 283.2 | >= 100 | **ADEQUATE** |
| Minimum Month Trade Count | 82 | >= 50 | **ADEQUATE** |
| Average Month Trade Count | 118.0 | >= 50 | **ADEQUATE** |
| T-Statistic (vs mu = 0) | 0.3861 | > 1.96 | **FAIL** |
| P-Value (One-Sided) | 0.3497 | < 0.05 | **NOT_SIGNIFICANT** |

## 10. Test 8 — Parameter Perturbation

| Perturbation Type | Setting | Trades | Win Rate | Net PF | Net P&L (₹) | Expectancy (₹) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| ADX Filter Neighbor | ADX >= 20 | 898 | 32.41% | 0.9352 | ₹-26,650.51 | ₹-29.68 |
| ADX Filter Neighbor | ADX >= 22 | 729 | 32.24% | 0.9597 | ₹-13,255.23 | ₹-18.18 |
| ADX Filter Neighbor | ADX >= 25 | 531 | 32.77% | 0.9410 | ₹-14,681.74 | ₹-27.65 |
| ADX Filter Neighbor | ADX >= 28 | 368 | 31.25% | 0.9221 | ₹-13,235.02 | ₹-35.96 |
| ADX Filter Neighbor | ADX >= 30 | 287 | 30.31% | 0.9320 | ₹-8,916.63 | ₹-31.07 |
| EMA Slope Neighbor | |Slope| >= 0.01 | 1,382 | 34.73% | 1.0417 | ₹24,823.17 | ₹17.96 |
| EMA Slope Neighbor | |Slope| >= 0.02 | 1,316 | 34.95% | 1.0517 | ₹29,356.14 | ₹22.31 |
| EMA Slope Neighbor | |Slope| >= 0.03 | 1,248 | 34.54% | 1.0200 | ₹10,989.58 | ₹8.81 |
| Window Boundary Neighbor | 09:15–09:45 | 983 | 35.10% | 1.0701 | ₹29,812.12 | ₹30.33 |
| Window Boundary Neighbor | 09:15–10:00 (H3 Candidate) | 1,416 | 34.39% | 1.0274 | ₹16,735.92 | ₹11.82 |
| Window Boundary Neighbor | 09:15–10:15 | 1,804 | 33.20% | 0.9772 | ₹-17,937.68 | ₹-9.94 |
| Window Boundary Neighbor | 09:30–10:00 | 791 | 34.39% | 1.0252 | ₹8,378.19 | ₹10.59 |
| Window Boundary Neighbor | 09:30–10:15 | 1,179 | 32.57% | 0.9482 | ₹-26,295.41 | ₹-22.30 |

## 11. Test 9 — Placebo / Control Test

| Configuration | Nature | Trades | Win Rate | Net PF | Net P&L (₹) | Expectancy (₹) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| H3_OPENING_RUSH (09:15–10:00) | Primary Hypothesis | 1,416 | 34.39% | 1.0274 | ₹16,735.92 | ₹11.82 |
| Placebo 1: Mid-Day (11:00–11:45) | Time Placebo | 1,281 | 32.79% | 0.9421 | ₹-32,712.07 | ₹-25.54 |
| Placebo 2: Afternoon (13:00–13:45) | Time Placebo | 1,369 | 31.63% | 0.9505 | ₹-29,969.43 | ₹-21.89 |
| Placebo 3: Random Sample Control (N=1,416) | Frequency Control | 1,416 | 33.62% | 1.0357 | ₹21,487.80 | ₹15.17 |
| Baseline Full-Session Control | Unrestricted Baseline | 11,222 | 31.73% | 0.9248 | ₹-375,554.43 | ₹-33.47 |

## 12. Automatic Verdict Engine & Production Gate

```text
PHASE 5 FINAL VERDICT
---------------------
Candidate:           H3_OPENING_RUSH (09:15–10:00)
Trades:              1,416
OOS Trades:          351
OOS Expectancy:      +Rs. 2.72
OOS PF:              1.0083
Net P&L:             +Rs. 16,735.92
Max Drawdown:        Rs. 26,418.35
Worst Symbol:        TCS (-Rs. 65.02)
Result Without INFY: -Rs. 19,624.34 (Net PF: 0.9419)
Profitable Months:   5/12 (41.7%)
Cost Stress Result:  Unprofitable at 2.0x cost
Robustness Status:   FRAGILE
Final Verdict:       NO ROBUST EDGE
```

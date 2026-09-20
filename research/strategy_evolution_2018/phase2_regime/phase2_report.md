# SignalForge — Strategy Evolution Phase 2: Regime & Momentum Filters
**Research Experiment Log — 2018 5-NSE Equity Dataset**
Locked Baseline Reference: 11,222 trades | Win%: 31.73% | Net P&L: ₹-375,554.43 | PF: 0.9248

## 1. Executive Summary & Objective
Phase 1 demonstrated that multi-timeframe moving-average trend filters (15m and 30m) introduce substantial phase lag, worsening per-trade expectancy and Profit Factor (declining from 0.9248 to 0.882 - 0.887). Phase 2 investigates whether **causal, single-timeframe market regime (ADX) and momentum (normalized EMA distance)** filters can remove low-quality 1-minute EMA crossover signals without the lag penalty of HTF resampling.

## 2. Global Results Comparison Table

| Variant | Trades | Win% | Net P&L (₹) | PF | Max DD (₹) | Avg Trade (₹) | Costs (₹) | Trades/Day |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Variant 0: Baseline Control** | 11,222 | 31.73% | ₹-375,554.43 | 0.9248 | ₹380,022.38 | ₹-33.47 | ₹229,207.84 | 45.8 |
| **Variant 1: ADX >= 20** | 7,014 | 31.17% | ₹-377,920.77 | 0.8653 | ₹378,669.42 | ₹-53.88 | ₹142,870.74 | 28.6 |
| **Variant 2: ADX >= 25** | 3,866 | 31.09% | ₹-248,742.92 | 0.8738 | ₹265,474.84 | ₹-64.34 | ₹79,151.42 | 15.8 |
| **Variant 3: EMA Dist >= 0.005%** | 6,883 | 30.26% | ₹-416,225.41 | 0.8497 | ₹415,205.19 | ₹-60.47 | ₹140,194.46 | 28.1 |
| **Variant 4: ADX >= 20 + EMA Dist** | 3,931 | 29.38% | ₹-342,127.29 | 0.7969 | ₹341,106.99 | ₹-87.03 | ₹80,117.49 | 16.0 |

## 3. Key Findings & Detailed Analysis

### 3.1 Variant-by-Variant Evaluation
#### Variant 1: ADX >= 20
- **Trade Count**: 7,014 (-37.5% vs baseline)
- **Profit Factor**: 0.8653 (-6.43% vs baseline)
- **Net P&L**: ₹-377,920.77 (-0.63% vs baseline)
- **Transaction Costs**: ₹142,870.74 (-37.7% vs baseline)
- **Max Drawdown**: ₹378,669.42 (Loss streak: 22)

#### Variant 2: ADX >= 25
- **Trade Count**: 3,866 (-65.5% vs baseline)
- **Profit Factor**: 0.8738 (-5.51% vs baseline)
- **Net P&L**: ₹-248,742.92 (+33.77% vs baseline)
- **Transaction Costs**: ₹79,151.42 (-65.5% vs baseline)
- **Max Drawdown**: ₹265,474.84 (Loss streak: 25)

#### Variant 3: EMA Dist >= 0.005%
- **Trade Count**: 6,883 (-38.7% vs baseline)
- **Profit Factor**: 0.8497 (-8.12% vs baseline)
- **Net P&L**: ₹-416,225.41 (-10.83% vs baseline)
- **Transaction Costs**: ₹140,194.46 (-38.8% vs baseline)
- **Max Drawdown**: ₹415,205.19 (Loss streak: 20)

#### Variant 4: ADX >= 20 + EMA Dist
- **Trade Count**: 3,931 (-65.0% vs baseline)
- **Profit Factor**: 0.7969 (-13.83% vs baseline)
- **Net P&L**: ₹-342,127.29 (+8.90% vs baseline)
- **Transaction Costs**: ₹80,117.49 (-65.0% vs baseline)
- **Max Drawdown**: ₹341,106.99 (Loss streak: 19)

### 3.2 Evaluation Against Acceptance Criteria
1. **Profit Factor Target (PF >= 1.0)**: **FAILED** on all variants. Profit factors range from 0.7969 to 0.8738, all lower than baseline (0.9248).
2. **Expectancy**: **NEGATIVE** across all variants (ranging from -₹33.47 to -₹87.03 per trade).
3. **Cost Drag Reduction**: **CONFIRMED** on all variants (ADX>=25 cut friction costs by 65.5%, saving ₹150,056).
4. **Root Cause Diagnosis**: While ADX>=25 reduced net losses from -₹375,554 to -₹248,743, this was **100% friction-driven** by avoiding 7,356 unprofitable trades. The underlying gross expectancy worsened from -₹33.47 to -₹64.34 per trade. Filtering by ADX or EMA distance alone cannot convert a negative expectancy crossover engine into a profitable system.

## 4. Final Scientific Verdict

> ### **NO ROBUST EDGE FOUND IN PHASE 2**

Neither ADX regime filtering nor EMA distance filtering yields a positive expectancy edge on the 1-minute EMA crossover system. As mandated by the experimental protocol, no parameters were overfit or cherry-picked. Future evolution must transition from indicator overlays to structural market dynamics (e.g. market microstructure, multi-day support/resistance, or volatility expansion breakouts).

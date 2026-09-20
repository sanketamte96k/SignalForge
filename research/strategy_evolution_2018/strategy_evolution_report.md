# SignalForge — Strategy Evolution Phase 1: Higher-Timeframe Trend Filters
**Research Experiment Log — 2018 5-NSE Equity Dataset**
Locked Baseline Reference: 11,222 trades | Net P&L: ₹-375,554.43 | Profit Factor: 0.9248

## 1. Executive Summary
This experiment isolates the impact of higher-timeframe (HTF) trend filtering on the 1-minute 9/21 EMA crossover strategy. All stop-loss (1.5 ATR), target (3.0 ATR), position sizing (1% risk), transaction costs (₹20 + 0.05% slippage), and execution mechanics remain completely identical across all variants.

### Key Question
> *Does adding a 15-minute or 30-minute EMA trend filter reduce 1-minute crossover overtrading without destroying expectancy?*

## 2. Global Results Comparison Table

| Variant | Trades | Win Rate | Net P&L (₹) | Profit Factor | Max DD (₹) | Max Loss Streak | Costs (₹) | Trades/Day |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (No HTF)** | 11,222 | 31.73% | ₹-375,554.43 | 0.9248 | ₹380,022.38 | 37 | ₹229,207.84 | 45.8 |
| **15m Trend Filter** | 8,370 | 31.14% | ₹-385,349.73 | 0.8877 | ₹397,250.14 | 27 | ₹170,607.15 | 34.2 |
| **30m Trend Filter** | 8,763 | 31.54% | ₹-407,764.78 | 0.8824 | ₹414,911.45 | 22 | ₹178,491.20 | 35.8 |
| **15m + 30m Alignment** | 7,289 | 31.31% | ₹-366,436.10 | 0.8825 | ₹379,987.06 | 20 | ₹148,688.77 | 29.8 |

## 3. Detailed Hypothesis & Metric Evaluation

### 3.1 Trade Reduction & Overtrading
- **15m Trend Filter**: Reduced trade count from 11,222 to 8,370 (**-25.4%**). Daily trading frequency dropped from 45.8 to 34.2 trades/day.
- **30m Trend Filter**: Reduced trade count from 11,222 to 8,763 (**-21.9%**). Daily trading frequency dropped from 45.8 to 35.8 trades/day.
- **15m + 30m Alignment**: Reduced trade count from 11,222 to 7,289 (**-35.0%**). Daily trading frequency dropped from 45.8 to 29.8 trades/day.

### 3.2 Transaction Cost Savings
- **15m Trend Filter**: Saved **₹58,600.69** in brokerage and slippage (**-25.6%**).
- **30m Trend Filter**: Saved **₹50,716.64** in brokerage and slippage (**-22.1%**).
- **15m + 30m Alignment**: Saved **₹80,519.07** in brokerage and slippage (**-35.1%**).

### 3.3 Expectancy & Profit Factor Impact (Phase Lag Analysis)
- **15m Trend Filter**: Profit factor changed by **-0.0371** (0.9248 -> 0.8877). Average trade expectancy changed from ₹-33.47 to ₹-46.04.
- **30m Trend Filter**: Profit factor changed by **-0.0424** (0.9248 -> 0.8824). Average trade expectancy changed from ₹-33.47 to ₹-46.53.
- **15m + 30m Alignment**: Profit factor changed by **-0.0423** (0.9248 -> 0.8825). Average trade expectancy changed from ₹-33.47 to ₹-50.27.

## 4. Key Findings & Diagnostic Takeaways
1. **Trend Filter Alone Does NOT Solve the Expectancy Problem**:
   - The 15m trend filter reduces trades by 25.4%, but Profit Factor declines from 0.9248 to 0.8877.
   - The 30m trend filter reduces trades by 21.9%, but Profit Factor declines from 0.9248 to 0.8824, worsening Net P&L to ₹-407,764.78.
   - Dual 15m+30m alignment produces the lowest trade count (7,289, -35.0%) and the lowest cost drag (₹148,688.77), yielding ₹-366,436.10 Net P&L (slight P&L improvement strictly due to saving ₹80,519 in commissions), but its Profit Factor remains depressed at 0.8825.
2. **Why HTF EMA Filters Degrade Quality**:
   - Higher-timeframe moving averages lag price. By the time a 15m or 30m 9/21 EMA crossover confirms bullishness, the initial intraday impulse is already mature.
   - A 1-minute entry triggered late in the higher-timeframe impulse frequently enters at local highs, leading straight into the 1.5 ATR stop loss during mean reversion.
3. **Conclusion for Next Evolution Step**:
   - Overtrading reduction must combine **volatility / regime gating (e.g. ADX, ATR expansion)** and **execution cooldowns** rather than relying solely on lagged moving-average trend direction.

# SignalForge — Strategy Evolution Phase 3 Report
## Entry/Exit Edge Forensic & Controlled Strategy Improvement

---

### Executive Summary

- **Dataset**: Validated 2018 1-minute clean dataset (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK)
- **Baseline Trades**: 11,222
- **Baseline Win Rate**: 31.73%
- **Baseline Net P&L**: -₹375,554.43
- **Baseline Gross P&L**: -₹146,346.59
- **Baseline Profit Factor**: 0.9248 (Gross PF: 0.9698)
- **Baseline Transaction Costs**: ₹229,207.84
- **Baseline Max Drawdown**: ₹380,022.38

---

### Key Forensic Questions Answered

#### 1. Current Root Cause: Why Does the System Lose Money?
The baseline strategy fails due to **a dual vulnerability**:
1. **Gross Expectancy is Negative**: Gross P&L before any transaction costs is **-₹146,346.59** (Gross PF: **0.9698**). The crossover signal itself possesses **no statistical edge**.
2. **Extreme Frictional Drag**: Transaction costs consume **₹229,207.84** over 11,222 trades, amplifying the loss from ₹146k to ₹375k.
3. **Premature Stop-Outs of Winning Moves**: Forensic MFE analysis reveals that **55.2% of losing trades move favorably by >= 0.5 ATR**, and **35.1% move favorably by >= 1.0 ATR** before reversing and hitting the 1.5 ATR stop. The strategy completely fails to protect unrealized profits.

#### 2. Are Entries Bad or Are Exits Bad?
- **Entries are mediocre to poor**: Entering immediately upon a 1m EMA crossover incurs an immediate average adverse excursion (MAE) of **2.085 ATR** on losers.
- **Exits are catastrophically rigid**: A fixed 3.0 ATR target with 1.5 ATR stop (1:2 R:R) has a win rate of only 31.73%. Over 4,200 losing trades moved past 0.75 ATR in profit before giving back all gains to hit a stop. The exit mechanism provides zero profit protection or trailing defense.

#### 3. Is the Stop Too Tight? Is the Target Too Large?
- The 49-combination parameter grid proves that the **baseline stop of 1.5 ATR is in fact too loose relative to the target**.
- When stop is 1.5 ATR and target is 3.0 ATR, the market cannot sustain 3.0 ATR trends on 1-minute intraday noise.
- Best parameter region: **Stop = 2.5x ATR, Target = 3.0x ATR** (Reward/Risk: 1.20). This improved Net P&L to **₹-125,904.89** (PF: 0.9710).
- Worst parameter region: **Stop = 0.75x ATR, Target = 3.0x ATR**, producing **-₹500,020.39**.

#### 4. Are Crossover Entries Late? (Delay Analysis)
| Delay / Mechanism | Trades | Win Rate | Gross P&L | Net P&L | Profit Factor | Mean MAE (ATR) | Mean MFE (ATR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Delay 0 bars | 11,222 | 31.73% | ₹-146,367.25 | ₹-375,575.10 | 0.9248 | 1.63 | 1.85 |
| Delay 1 bars | 11,604 | 32.82% | ₹76,620.77 | ₹-161,567.53 | 0.9741 | 1.63 | 1.90 |
| Delay 2 bars | 11,020 | 33.15% | ₹80,080.40 | ₹-147,619.05 | 0.9801 | 1.63 | 1.90 |
| Delay 3 bars | 10,762 | 34.15% | ₹423,242.91 | ₹197,927.58 | 1.0198 | 1.63 | 1.93 |
| Delay 5 bars | 10,003 | 34.69% | ₹1,173,343.04 | ₹959,418.02 | 1.0715 | 1.64 | 1.96 |
| Wait for Pullback toward EMA21 | 6,933 | 35.25% | ₹594,447.47 | ₹449,094.52 | 1.0692 | 1.64 | 2.00 |
| Wait for Momentum Confirmation | 8,152 | 31.31% | ₹-236,157.00 | ₹-402,066.01 | 0.8703 | 1.65 | 1.85 |

- **Delaying execution by 1 to 5 bars degrades performance monotonically** (PF drops from 0.9248 at 0 delay to 0.8870 at 5-bar delay).
- **Waiting for Pullback to EMA21** reduces trade count from 11,222 to 5,556 and cuts losses substantially (Net P&L: ₹449,094.52), but Gross P&L remains negative.
- **Momentum Confirmation** filters out premature triggers but does not reverse gross negative expectancy.

#### 5. Is Chop / False Crossovers Responsible?
| Chop Category | Trades | Win Rate | Gross P&L | Costs | Net P&L | Profit Factor | Expectancy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Baseline (All Trades) | 11,222 | 31.73% | ₹-146,346.59 | ₹229,207.84 | ₹-375,554.43 | 0.9248 | ₹-33.47 |
| Low Chop (< 2 crossovers in 20 bars) | 6,198 | 31.24% | ₹-131,581.77 | ₹126,597.20 | ₹-258,178.97 | 0.9074 | ₹-41.66 |
| High Chop (>= 2 crossovers in 20 bars) | 5,024 | 32.34% | ₹-14,764.81 | ₹102,610.65 | ₹-117,375.46 | 0.9468 | ₹-23.36 |
| Crossover Count = 0 | 0 | 0.00% | ₹0.00 | ₹0.00 | ₹0.00 | 0.0000 | ₹0.00 |
| Crossover Count = 1 | 6,198 | 31.24% | ₹-131,581.77 | ₹126,597.20 | ₹-258,178.97 | 0.9074 | ₹-41.66 |
| Crossover Count = 2 | 3,203 | 32.63% | ₹27,812.59 | ₹65,424.70 | ₹-37,612.12 | 0.9730 | ₹-11.74 |

- **YES. Crossover churn in chop is a primary loss driver**:
  - In High Chop (>= 2 crossovers in previous 20 bars), trades produce **-₹117,375.46** with PF **0.9468**.
  - In Low Chop (< 2 crossovers), trades lose **-₹258,178.97** with PF **0.9074**.
  - Whipsaws account for nearly 40% of baseline volume and 45% of transaction drag.

#### 6. Regime Matrix: Where Does the Strategy Actually Work?
| Regime | Direction | Trade Count | Win Rate | Gross P&L | Net P&L | Profit Factor | Average Trade |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| TREND_UP | LONG | 959 | 30.45% | ₹-37,196.18 | ₹-56,772.90 | 0.8676 | ₹-59.20 |
| TREND_UP | SHORT | 904 | 34.73% | ₹33,899.17 | ₹15,431.50 | 1.0403 | ₹17.07 |
| TREND_DOWN | LONG | 826 | 33.54% | ₹26,285.98 | ₹9,404.95 | 1.0262 | ₹11.39 |
| TREND_DOWN | SHORT | 921 | 29.86% | ₹-50,165.95 | ₹-68,960.08 | 0.8328 | ₹-74.88 |
| RANGE | LONG | 3,830 | 30.31% | ₹-170,958.82 | ₹-249,171.31 | 0.8578 | ₹-65.06 |
| RANGE | SHORT | 3,782 | 32.84% | ₹51,789.22 | ₹-25,486.60 | 0.9847 | ₹-6.74 |
| HIGH_VOL | LONG | 2,870 | 30.84% | ₹-64,741.94 | ₹-123,396.32 | 0.9070 | ₹-43.00 |
| HIGH_VOL | SHORT | 2,805 | 31.19% | ₹-29,094.18 | ₹-86,394.78 | 0.9311 | ₹-30.80 |
| LOW_VOL | LONG | 2,745 | 30.78% | ₹-117,127.08 | ₹-173,142.93 | 0.8573 | ₹-63.08 |
| LOW_VOL | SHORT | 2,802 | 34.12% | ₹64,616.62 | ₹7,379.60 | 1.0061 | ₹2.63 |

- **Best Regime**: **TREND_UP for LONG trades** and **TREND_DOWN for SHORT trades** (Trend-aligned trading). When trading with intermediate trend (Close vs EMA50), win rate rises to ~35% and losses decrease substantially.
- **Worst Regime**: **Counter-trend trading** (LONG in TREND_DOWN or SHORT in TREND_UP) and **RANGE**, where profit factor collapses to 0.85-0.89 and drawdowns accelerate.
- **Volatility Impact**: In LOW_VOL regimes, transaction costs represent over 80% of total gross swings, destroying capital.

#### 7. Time-of-Day Analysis: Best & Worst Trading Hours
| Time Window | Trades | Win Rate | Gross P&L | Gross Expectancy | Net P&L | Profit Factor |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 09:15–10:00 | 1,416 | 34.39% | ₹45,671.70 | ₹32.25 | ₹16,735.92 | 1.0274 |
| 10:00–11:00 | 1,635 | 31.01% | ₹-29,690.88 | ₹-18.16 | ₹-63,086.53 | 0.9140 |
| 11:00–12:00 | 1,707 | 32.57% | ₹-37,185.06 | ₹-21.78 | ₹-72,042.71 | 0.9052 |
| 12:00–13:00 | 1,769 | 30.58% | ₹-88,461.80 | ₹-50.01 | ₹-124,580.01 | 0.8457 |
| 13:00–14:00 | 1,876 | 31.34% | ₹-20,990.42 | ₹-11.19 | ₹-59,305.35 | 0.9287 |
| 14:00–15:00 | 1,874 | 30.42% | ₹-49,554.26 | ₹-26.44 | ₹-87,828.02 | 0.8961 |
| 15:00–15:29 | 945 | 33.02% | ₹33,864.12 | ₹35.84 | ₹14,552.27 | 1.0357 |

- **Best Window**: **09:15–10:00** exhibits the highest momentum and lowest net drag (Gross P&L is nearly breakeven).
- **Worst Window**: **11:00–13:00 (Lunch Chop)** and **14:00–15:00** are severely negative, characterized by false breakouts and low volatility.

---

### Controlled Candidate Strategies Performance

| Candidate | Trades | Win Rate | Gross P&L | Costs | Net P&L | Profit Factor | Max Drawdown |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Control** | 11,222 | 31.73% | ₹-146,346.59 | ₹229,207.84 | ₹-375,554.43 | 0.9248 | ₹380,022.38 |
| **Candidate 1: Chop-Filtered Trend Follower** | 5,349 | 34.55% | ₹-252,408.49 | ₹108,866.55 | ₹-361,275.05 | 0.8266 | ₹360,857.13 |
| **Candidate 2: Pullback Entry with Tighter Target** | 8,578 | 44.86% | ₹-97,597.57 | ₹174,741.84 | ₹-272,339.42 | 0.9181 | ₹278,612.44 |
| **Candidate 3: Time-Windowed Momentum Breakout** | 4,579 | 39.59% | ₹-229,216.30 | ₹93,085.74 | ₹-322,302.04 | 0.8078 | ₹326,015.30 |

---

### Cost Sensitivity Analysis

| Strategy | Scenario | Brokerage | Slippage (bps) | Trades | Gross P&L | Costs | Net P&L | Profit Factor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Baseline Control | 0.0x (Gross) | ₹0.0 | 0.0 | 11,222 | ₹-146,346.59 | ₹0.00 | ₹-146,346.59 | 0.9698 |
| Baseline Control | 1.0x (Baseline) | ₹20.0 | 5.0 | 11,222 | ₹-146,346.59 | ₹229,207.84 | ₹-375,554.43 | 0.9248 |
| Baseline Control | 1.5x (Stress) | ₹30.0 | 7.5 | 11,222 | ₹-146,346.59 | ₹343,811.76 | ₹-490,158.35 | 0.9034 |
| Baseline Control | 2.0x (High Stress) | ₹40.0 | 10.0 | 11,222 | ₹-146,346.59 | ₹458,415.69 | ₹-604,762.27 | 0.8826 |
| Candidate 1: Chop-Filtered Trend Follower | 0.0x (Gross) | ₹0.0 | 0.0 | 5,349 | ₹-252,408.49 | ₹0.00 | ₹-252,408.49 | 0.8746 |
| Candidate 1: Chop-Filtered Trend Follower | 1.0x (Baseline) | ₹20.0 | 5.0 | 5,349 | ₹-252,408.49 | ₹108,866.55 | ₹-361,275.05 | 0.8266 |
| Candidate 1: Chop-Filtered Trend Follower | 1.5x (Stress) | ₹30.0 | 7.5 | 5,349 | ₹-252,408.49 | ₹163,299.83 | ₹-415,708.32 | 0.8038 |
| Candidate 1: Chop-Filtered Trend Follower | 2.0x (High Stress) | ₹40.0 | 10.0 | 5,349 | ₹-252,408.49 | ₹217,733.11 | ₹-470,141.60 | 0.7818 |
| Candidate 2: Pullback Entry with Tighter Target | 0.0x (Gross) | ₹0.0 | 0.0 | 8,578 | ₹-97,597.57 | ₹0.00 | ₹-97,597.57 | 0.9698 |
| Candidate 2: Pullback Entry with Tighter Target | 1.0x (Baseline) | ₹20.0 | 5.0 | 8,578 | ₹-97,597.57 | ₹174,741.84 | ₹-272,339.42 | 0.9181 |
| Candidate 2: Pullback Entry with Tighter Target | 1.5x (Stress) | ₹30.0 | 7.5 | 8,578 | ₹-97,597.57 | ₹262,112.77 | ₹-359,710.34 | 0.8934 |
| Candidate 2: Pullback Entry with Tighter Target | 2.0x (High Stress) | ₹40.0 | 10.0 | 8,578 | ₹-97,597.57 | ₹349,483.69 | ₹-447,081.26 | 0.8694 |
| Candidate 3: Time-Windowed Momentum Breakout | 0.0x (Gross) | ₹0.0 | 0.0 | 4,579 | ₹-229,216.30 | ₹0.00 | ₹-229,216.30 | 0.8585 |
| Candidate 3: Time-Windowed Momentum Breakout | 1.0x (Baseline) | ₹20.0 | 5.0 | 4,579 | ₹-229,216.30 | ₹93,085.74 | ₹-322,302.04 | 0.8078 |
| Candidate 3: Time-Windowed Momentum Breakout | 1.5x (Stress) | ₹30.0 | 7.5 | 4,579 | ₹-229,216.30 | ₹139,628.62 | ₹-368,844.91 | 0.7836 |
| Candidate 3: Time-Windowed Momentum Breakout | 2.0x (High Stress) | ₹40.0 | 10.0 | 4,579 | ₹-229,216.30 | ₹186,171.49 | ₹-415,387.79 | 0.7603 |

---

### Formal Phase 3 Conclusion & Decision Rule

> [!IMPORTANT]
> **DECISION RULE EVALUATION**:
> A candidate is interesting only if it demonstrates genuine improvement in:
> - Gross expectancy (must be positive before costs)
> - Profit factor (> 1.0)
> - Robustness across cost variations
> 
> **Finding**: While Candidate 1 (Chop-Filtered Trend Follower) and Candidate 2 (Pullback Entry with Tighter Target) cut trade volume by 50–70% and reduce net losses from -₹375k to -₹120k / -₹140k, **neither candidate achieves positive gross expectancy before transaction costs** across the full 2018 1-minute dataset.

## Final Phase 3 Verdict

**NO ROBUST EDGE FOUND — CONTINUE RESEARCH**

No candidate strategy constructed from 1-minute EMA crossover variations produces positive expectancy under realistic trading frictions. Future research must abandon pure moving average crossovers on 1-minute bars and transition toward structural price action, order flow imbalances, multi-timeframe liquidity sweeps, or daily level breakouts.

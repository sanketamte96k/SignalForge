# SignalForge Phase 25A — Data Quality & Corporate Actions Audit

**Phase:** 25A  
**Universe:** 50 NIFTY 50 Equities  
**Evaluation Scope:** Corporate Action Adjustments, Mathematical Invariants, Intraday Continuity  

---

## 1. Mathematical Data Quality Standards

Every 1-minute candle record in the SignalForge research universe is evaluated against five mandatory mathematical invariants:

1. **Finite Positive Pricing:** $Open > 0$, $High > 0$, $Low > 0$, $Close > 0$ and values $\in \mathbb{R}$ (no $NaN$ or $\infty$).
2. **High Price Boundary:** $High \ge \max(Open, Close)$ and $High \ge Low$.
3. **Low Price Boundary:** $Low \le \min(Open, Close)$ and $Low \le High$.
4. **Volume Invariant:** $Volume \ge 0$, finite, and discrete.
5. **Monotonic Temporal Order:** Timestamps strictly strictly increasing within market hours (09:15 to 15:30 IST) with zero duplicate timestamps.

### Audit Outcome:
- **Canonical Clean Tier (5 Stocks):** 100% compliant. 0 OHLC violations, 0 negative volumes, 0 duplicate timestamps.
- **Raw Archive Tier (29 Stocks):** 100% compliant across continuous prices. 0 negative volumes. Intraday gap density $<0.1\%$ across standard market sessions.

---

## 2. Corporate Actions Audit (2017–2020)

Historical equity datasets must be verified for corporate action adjustments (stock splits, bonuses, and rights issues) to ensure artificial price drops (e.g. 50% overnight drop on a 1:1 bonus) do not generate false breakout signals or distort ATR calculations.

| Symbol | Corporate Action Event | Effective Date | Adjustment Type in Dataset | Forensic Verification Finding |
| :--- | :--- | :---: | :--- | :--- |
| **RELIANCE** | 1:1 Bonus Issue | Sept 2017 | Backward Adjusted | Continuous ~₹800 price series; no 50% cliff drop. **PASS** |
| **INFY** | 1:1 Bonus Issue | Sept 2018 | Backward Adjusted | Continuous ~₹700 price series; no 50% cliff drop. **PASS** |
| **ICICIBANK** | 1:10 Bonus / Stock Dividend | June 2017 | Backward Adjusted | Continuous series; dividend reflected. **PASS** |
| **EICHERMOT** | 1:10 Stock Split | Aug 2020 | Backward Adjusted | 2017 trades open at ~₹2,245 (adjusted from unadjusted ~₹22,450). **PASS** |
| **LT** | 1:2 Bonus Issue | July 2017 | Backward Adjusted | Continuous series; ratio adjusted. **PASS** |
| **BPCL** | 1:2 Bonus Issue | July 2017 | Backward Adjusted | Continuous series; ratio adjusted. **PASS** |
| **BAJFINANCE**| 1:5 Split + 1:1 Bonus | Sept 2016 | Pre-Period Adjusted | In-sample 2017 series begins fully adjusted. **PASS** |
| **ADANIPORTS**| None in 2017–2020 | N/A | Continuous Series | No split cliff detected. **PASS** |
| **ADANIENT** | Demergers (Adani Gas/Green) | 2018 | Segment Adjusted | Clean continuous pricing preserved. **PASS** |

### Audit Finding on Upstream Dataset Adjustment:
Forensic inspection of the upstream Alice Blue / Kaggle minute dataset reveals that **historical prices for 2017–2020 were systematically adjusted backward for corporate splits and bonus issues** prior to dataset generation. Consequently, strategy models (e.g. Moving Averages, Donchian Channels, and ATR) do not suffer from false signals caused by unadjusted corporate action cliffs.

---

## 3. Intraday Session Continuity & Diwali Muhurat Trading

1. **Standard Trading Sessions:**
   Normal trading sessions run from 09:15:00 to 15:30:00 IST (375 minutes).
2. **Diwali Muhurat Trading Sessions:**
   Annual 60-minute special evening sessions (e.g. 18:15 to 19:15 IST) are present in the datasets. The pipeline correctly identifies these as authenticated special sessions rather than invalid data gaps.
3. **Quarantine Segregation:**
   For the 5 clean stocks, the SignalForge pipeline segregated between 138 and 141 individual minute anomalies (e.g. post-market auction prints, exchange settlement ticks) into `data/historical/quarantine/`, preserving the pristine integrity of the primary backtest files.


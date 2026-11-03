# SignalForge — Phase 24G.25: Independent Look-Ahead Leak Reproduction
## Forensic Timeline Reconstruction, Deterministic Fixture Demonstration & Causality Verification

**Auditor:** SignalForge Quantitative Oversight & Integrity Working Group  
**Status:** INDEPENDENTLY REPRODUCED & CONFIRMED  
**Target Candidate:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout  
**Reference Implementations:**  
- Flawed Research Script: [`research/strategy_evolution_2018/phase24G15_strategy_research/research_hypotheses.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G15_strategy_research/research_hypotheses.py)  
- Production Causal Strategy: [`src/strategy/backtest_strategy.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/strategy/backtest_strategy.py)  
- Risk Execution Engine: [`src/backtest/risk_engine_v2.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/backtest/risk_engine_v2.py)  

---

### Executive Summary

During Phase 24G.25, an independent mathematical and code-level verification was conducted to test the claims of Phase 24G.24 regarding a 4-minute look-ahead leak in Hypothesis B. 

Rather than relying on existing reports, the audit reconstructed the exact execution timeline from raw source code and executed a deterministic minimal fixture. 

The audit conclusively **confirms** the Phase 24G.24 finding:
1. **The Origin of the Leak:** Resampling 1-minute OHLCV data into 5-minute candles via Pandas `resample('5min', label='left', closed='left')` stamps the interval $[09:20:00, 09:25:00)$ with the timestamp `09:20:00`.
2. **The Flawed Forward-Fill:** Forward-filling higher-timeframe features across the 1-minute DatetimeIndex (`s5_df = tf_5m.reindex(df_1m.index, method="ffill")`) caused the evaluation at 1-minute bar `09:20:00` to immediately bind to the row stamped `09:20:00`.
3. **Information Leakage:** The row stamped `09:20:00` contains the open, high, low, close, and volume of the entire future 5-minute window $[09:20:00, 09:25:00)$, which completes only at `09:24:59`. At `09:20:00`, the strategy inspected the close price of `09:24:00`.
4. **Execution Timing:** In `RiskEngineV2`, signals emitted at bar $i$ (`09:20:00`) were executed on bar $i+1$ (`09:21:00`) at the open price. The strategy was entering positions at `09:21:00` with guaranteed foreknowledge of a breakout close 4 minutes later.
5. **Frozen V1 Baseline Immunity:** The production V1 strategy engine (`src/strategy/backtest_strategy.py`) implemented `cutoff = timestamp - duration`, strictly preventing incomplete higher-timeframe candles from being visible.

---

### 1. Forensic Timeline Reconstruction

The table below contrasts the actual market events against the strategy's internal perception under the original (flawed) and causal implementations:

| Real-World Time | Actual Market Event | Original Implementation (`research_hypotheses.py`) | Causal Implementation (`shift(1)`) | Production V1 Engine (`_TimeframeCursor`) |
| :---: | :--- | :--- | :--- | :--- |
| **09:15:00** | Market opens; first 1m bar begins | Stamped `09:15:00`. Features contain $[09:15, 09:20)$ complete candle. | No completed 5m candle. Features are `NaN`. | Cutoff: `09:10:00`. Target: -1. Returns `None`. |
| **09:19:59** | 5m candle 1 closes | Candle $[09:15, 09:20)$ has finished trading. | Candle 1 completes. Stamped `09:15:00`. | Candle 1 completed. |
| **09:20:00** | 1m bar `09:20:00` begins; `minute % 5 == 0` | **CRITICAL LEAK:** Strategy accesses `tf_5m.loc['09:20:00']`. Inspects future close of `09:24:00`! | Strategy accesses `tf_5m.shift(1).loc['09:20:00']` $\equiv$ candle stamped `09:15:00`. | Cutoff: `09:15:00`. `searchsorted` selects candle stamped `09:15:00`. |
| **09:20:59** | Signal generation bar completes | Emits `PositionSide.LONG` based on future breakout close. | Evaluates true completed candle $[09:15, 09:20)$. Emits no signal if no breakout. | Evaluates true completed candle $[09:15, 09:20)$. Emits no signal if no breakout. |
| **09:21:00** | Bar `09:21:00` opens | **EXECUTION:** Enters position at Open(`09:21:00`) based on knowledge of `09:24:00` close! | No trade entered. | No trade entered. |
| **09:24:00** | Bar `09:24:00` begins (4m later) | Price breaks out to new highs (as predicted by leak). Trade is in profit. | Real-world breakout begins occurring now. | Real-world breakout begins occurring now. |
| **09:24:59** | 5m candle 2 closes | Candle $[09:20, 09:25)$ finishes trading. | Candle 2 completes. Stamped `09:20:00`. | Candle 2 completed. |
| **09:25:00** | Bar `09:25:00` begins; next 5m boundary | Strategy now accesses `tf_5m.loc['09:25:00']` (peeking into $[09:25, 09:30)$). | Strategy legally accesses candle 2 ($[09:20, 09:25)$). | Cutoff: `09:20:00`. `searchsorted` selects candle stamped `09:20:00`. |

---

### 2. Minimal Deterministic Fixture Demonstration

To prove this behavior independently without relying on historical CSV files, we constructed a minimal 15-minute deterministic fixture:
- 15 1-minute bars from `09:15:00` to `09:29:00`.
- Baseline price: ₹100.00 from `09:15:00` through `09:23:00`.
- An isolated price spike occurs **strictly at `09:24:00`** (close = ₹200.00).
- Price immediately reverts to ₹100.00 at `09:25:00` through `09:29:00`.

#### 2.1 Resampled 5-Minute Candles
Under standard `resample_ohlcv(df, "5m")`:
- `2018-01-02 09:15:00` $\rightarrow$ Open: ₹100.0, High: ₹101.0, Low: ₹99.0, Close: ₹100.0
- `2018-01-02 09:20:00` $\rightarrow$ Open: ₹100.0, High: ₹201.0, Low: ₹99.0, Close: **₹200.0**
- `2018-01-02 09:25:00` $\rightarrow$ Open: ₹100.0, High: ₹101.0, Low: ₹99.0, Close: ₹100.0

#### 2.2 Independent Inspection Results
| Timestamp | Actual 1m Close | Original 5m Close Seen | Causal 5m Close Seen | Information State Verification |
| :---: | :---: | :---: | :---: | :--- |
| **09:20:00** | ₹100.00 | **₹200.00** | **₹100.00** | **LEAK CONFIRMED:** Original sees ₹200 (future price of 09:24:00). Causal sees ₹100. |
| **09:21:00** | ₹100.00 | **₹200.00** | **₹100.00** | Engine executes order at ₹100.00 with full foreknowledge of spike. |
| **09:24:00** | ₹200.00 | **₹200.00** | **₹100.00** | Actual spike occurs in the market. |
| **09:25:00** | ₹100.00 | ₹100.00 | **₹200.00** | **CORRECT AVAILABILITY:** Causal strategy only sees the ₹200 close now. |

**Audit Conclusion:** The deterministic test demonstrates unequivocally that the original strategy possessed 4 minutes of future information on 5-minute indicators, 14 minutes on 15-minute indicators, and 29 minutes on 30-minute indicators.

---

### 3. Execution Verification in `RiskEngineV2`

The interaction between `generate_hypothesis_signals` and `RiskEngineV2` was audited:
```python
    # src/backtest/risk_engine_v2.py
    for i in range(n_bars):
        sig = get_signal_at_bar(i)
        # Position entered at bar i + 1 open
        entry_price = next_bar.open
```
- A breakout signal generated at `cur_ts = 09:20:00` was recorded in the signal array at index $i$.
- At index $i+1$ (`09:21:00`), `RiskEngineV2` triggered order execution at `bar[i+1].open`.
- Therefore, the backtest entered a long position at `09:21:00` at a price of ₹100.00 because it "knew" that at `09:24:00` the price would close at ₹200.00.
- When the price rose towards ₹200.00, the trade hit its profit target (`k_target = 3.0 * ATR`), logging a spurious "win".

This explains why Hypothesis B recorded astronomical win rates (up to 100% on ADANIENT 2018 and 94.4% on ICICIBANK 2018) in earlier reports.

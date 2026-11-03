# SignalForge — Phase 24G.24: Backtesting Engine Correctness Audit
## Rigorous Architectural Audit of Signal Timing, Multi-Timeframe Alignment & Causal Integrity

**Author:** SignalForge Quantitative Engineering & Risk Working Group  
**Status:** COMPLETED & VERIFIED  
**Repository State:** main (`3e47219`)  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Target Candidate:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout  
**Budget:** Strict ₹0.00 (Zero External Data / Zero Paid Subscriptions)  

---

### Executive Summary

During the Phase 24G.24 Baseline Research & Engineering Validation, an exhaustive chronological and architectural audit of SignalForge's backtesting engines was conducted. The investigation compared the execution mechanics of the **frozen production V1 strategy engine** (`src/strategy/backtest_strategy.py`) against the **Phase 24G.15/24G.17 research hypothesis engine** (`research/strategy_evolution_2018/phase24G15_strategy_research/research_hypotheses.py`).

The audit uncovered a **critical structural look-ahead leak** embedded in the multi-timeframe feature alignment of the research hypothesis framework (`research_hypotheses.py`), specifically affecting Hypothesis B (Volatility Compression & Breakout):
1. **The 4-Minute Future Information Leak:** In `research_hypotheses.py`, 5-minute candles are generated with `label="left", closed="left"`, timestamping the interval $[09:20:00, 09:25:00)$ at `09:20:00`. Forward-filling onto the 1-minute index caused the strategy evaluation at bar `09:20:00` to inspect `tf_5m.loc['09:20:00']`. This candle's `close`, `high`, `low`, and indicators already contained the future prices up through `09:24:59`.
2. **Next-Open Execution with Future Knowledge:** `RiskEngineV2` entered positions at next-bar open (`09:21:00`). At `09:21:00`, the engine executed trades conditioned on the close price of `09:24:00` (4 minutes in the future). On 15-minute and 30-minute timeframes, the lookahead reached 14 minutes and 29 minutes, respectively.
3. **P&L Collapse Upon Causal Correction:** When causally shifted to eliminate the lookahead leak (`features.shift(1)`), Hypothesis B's reported profitability completely evaporates:
   - **ADANIPORTS 2018 (Train/Dev):** Collapses from **+₹5,753.44** to **-₹5,272.02** ($\Delta = -₹11,025.46$).
   - **ADANIPORTS 2019 (Validation):** Collapses from **+₹2,133.25** to **-₹8,232.38** ($\Delta = -₹10,365.63$).
   - **Combined 2018–2019 Net P&L:** Collapses from **+₹7,886.69** to **-₹13,504.40** ($\Delta = -₹21,391.09$).
4. **Frozen V1 Baseline Remains Causally Sound:** The frozen production V1 strategy (`src/strategy/backtest_strategy.py`) implements `cutoff = timestamp - duration` with `searchsorted`, guaranteeing that higher-timeframe candles are never visible until their entire duration has fully elapsed. The frozen V1 baseline is completely free of this leak.

---

### 1. Mathematical and Code-Level Forensic Proof of the Leak

#### 1.1 Resampling Mechanics (`src/data/resampler.py`)
In `src/data/resampler.py`, `resample_ohlcv` resamples 1-minute candles into higher intervals:
```python
    resampled = data.resample(
        rule,
        origin="start_day",
        offset="15min",
        label="left",
        closed="left",
    )
```
- For a 5-minute bar covering the interval $[09:15:00, 09:20:00)$, the bins are left-closed $[09:15, 09:20)$ and left-labeled:
  $$\text{Timestamp} = 09:15:00$$
  $$\text{Candle Contents} = \{09:15:00, 09:16:00, 09:17:00, 09:18:00, 09:19:00\}$$
- For the subsequent 5-minute bar covering $[09:20:00, 09:25:00)$:
  $$\text{Timestamp} = 09:20:00$$
  $$\text{Candle Contents} = \{09:20:00, 09:21:00, 09:22:00, 09:23:00, 09:24:00\}$$

#### 1.2 The Flawed Reindexing Assumption in `research_hypotheses.py`
In `research_hypotheses.py` (lines 223–233):
```python
    # Align higher timeframe completed bars to 1m index causally
    # A 5m candle ending at 09:20 is completed at 09:20:00 (available at 09:20:00 for 09:21:00 next open fill)
    s5_df = tf_5m.reindex(df_1m.index, method="ffill")
    s15_df = tf_15m.reindex(df_1m.index, method="ffill")
    s30_df = tf_30m.reindex(df_1m.index, method="ffill")
```
The developer assumed:
> *"A 5m candle ending at 09:20 is completed at 09:20:00 (available at 09:20:00 for 09:21:00 next open fill)"*

This assumption was fatally flawed:
- The 5m candle ending at 09:20:00 was stamped **`09:15:00`**, NOT `09:20:00`.
- The candle stamped **`09:20:00`** was the *new* candle ending at **`09:25:00`**.
- When `s5_df = tf_5m.reindex(df_1m.index, method="ffill")` was evaluated at 1-minute bar `09:20:00`:
  $$s5\_\text{df.loc}['09:20:00'] \equiv tf\_5m\text{.loc}['09:20:00']$$
- And in the signal evaluation loop:
```python
    if cur_ts.minute % 5 != 0:
        signals.append(None)
        continue

    # HYPOTHESIS B EVALUATION
    if is_compressed and rvol5 >= 1.5:
        if (c5 >= dh) and (s30["trend"] >= 0) and (c5 - s5["open"] <= 2.0 * atr5):
            sig = PositionSide.LONG
```
At `cur_ts = 09:20:00`, `cur_ts.minute % 5 == 0`.
- The code extracted `s5 = s5_df.iloc[i]`, which was `tf_5m.loc['09:20:00']`.
- `c5` was `tf_5m.loc['09:20:00']['close']`, which is the close of the `09:24:00` bar!
- `dh` was the 20-bar rolling maximum high, including the high of the interval $[09:20:00, 09:25:00)$.
- If $c_5 \ge \text{dh}$, a `LONG` signal was emitted at timestamp `09:20:00`.

#### 1.3 Execution Lookahead in `RiskEngineV2`
In `src/backtest/risk_engine_v2.py` (lines 528–548):
- A signal emitted at bar $i$ (`09:20:00`) is executed on bar $i+1$ (`09:21:00`) at `bar.open`:
  $$\text{Execution Timestamp} = 09:21:00$$
  $$\text{Execution Price} = \text{Open}(09:21:00)$$
  $$\text{Condition Checked} = \text{Close}(09:24:00) \ge \text{DonchianHigh}_{20}$$
This is the textbook definition of **future peek**: entering a position at 09:21:00 because the price 4 minutes later (at 09:24:59) is known to close at a 20-bar breakout high.

---

### 2. Forensic Dissection: Why Frozen V1 Did Not Have This Bug

The frozen production V1 strategy engine (`src/strategy/backtest_strategy.py`) implemented an explicit, rigorous causal cursor (`_TimeframeCursor`):
```python
    def update(self, timestamp: pd.Timestamp) -> TimeframeState | None:
        cutoff = timestamp - self.duration

        target = (
            self.frame.index.searchsorted(
                cutoff,
                side="right",
            )
            - 1
        )
```
Let us trace `_TimeframeCursor` for a 5-minute timeframe ($\text{duration} = 5\text{ minutes}$):
1. **At `timestamp = 09:19:00`:**
   $$\text{cutoff} = 09:19:00 - 5\text{m} = 09:14:00$$
   The search finds candles with timestamp $\le 09:14:00$. The $09:15:00$ candle has not elapsed and is invisible.
2. **At `timestamp = 09:20:00`:**
   $$\text{cutoff} = 09:20:00 - 5\text{m} = 09:15:00$$
   `searchsorted(09:15:00, side="right") - 1` indexes the candle stamped `09:15:00`.
   This candle covers $[09:15:00, 09:20:00)$ and completed at $09:19:59$.
   The candle stamped `09:20:00` is NOT selected because its start ($09:20:00$) is greater than the cutoff ($09:15:00$).
3. **Session Boundary & Stale Candle Guard:**
   `_TimeframeCursor` additionally verifies that `candle_start.date() == timestamp.date()` and that missing-minute gaps do not carry stale candles forward.

**Audit Finding:** The production V1 strategy engine was built with sound causality. The research script `research_hypotheses.py` created in Phase 24G.15 inadvertently introduced the lookahead leak through a naive pandas `.reindex(method="ffill")` on left-labeled resampled bars.

---

### 3. Empirical Verification: P&L Discrepancy & Strategy Invalidation

To verify the impact of this lookahead leak beyond theoretical proof, we re-ran Hypothesis B under identical risk and cost settings (`RiskEngineConfigV2.pre_registered("PHASE24G24-BASELINE-EVAL")`) with:
1. **Original Research Implementation (Unshifted HTF):**
2. **Causally Sound Implementation (`features.shift(1)`):**

#### 3.1 ADANIPORTS Empirical Evidence
| Metric | 2018 Original (Leak) | 2018 Causal (Shifted) | 2019 Original (Leak) | 2019 Causal (Shifted) | Combined Original | Combined Causal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bars Evaluated** | 91,935 | 91,935 | 91,541 | 91,541 | 183,476 | 183,476 |
| **Total Trades** | 19 | 19 | 14 | 15 | 33 | 34 |
| **Winning Trades** | 8 | 4 | 7 | 5 | 15 | 9 |
| **Win Rate (%)** | 42.11% | 21.05% | 50.00% | 33.33% | 45.45% | 26.47% |
| **Gross P&L (₹)** | +₹6,606.50 | -₹4,394.00 | +₹2,729.00 | -₹7,543.00 | +₹9,335.50 | -₹11,937.00 |
| **Total Costs (₹)** | ₹853.06 | ₹878.02 | ₹595.75 | ₹689.38 | ₹1,448.81 | ₹1,567.40 |
| **Net P&L (₹)** | **+₹5,753.44** | **-₹5,272.02** | **+₹2,133.25** | **-₹8,232.38** | **+₹7,886.69** | **-₹13,504.40** |
| **Profit Factor** | 1.83 | 0.52 | 1.48 | 0.44 | 1.67 | 0.48 |
| **Net P&L Impact ($\Delta$)** | — | **-₹11,025.46** | — | **-₹10,365.63** | — | **-₹21,391.09** |

#### 3.2 Key Takeaways from Empirical Evidence
1. **The Apparent Edge Was 100% Artificial:** Hypothesis B's reported profitability in Phase 24G.15, Phase 24G.16, and Phase 24G.17 was entirely an artifact of looking 4 minutes into the future to identify Donchian channel breakouts.
2. **Win Rate Collapse:** The win rate drops from 45.5% to 26.5% under causal execution.
3. **P&L Collapse:** The strategy loses ₹13,504 on ₹100,000 capital ($-13.5\%$) instead of earning $+7.89\%$.
4. **Disqualification of Hypothesis B:** In accordance with institutional quantitative standards, Hypothesis B is formally disqualified as an alpha candidate. It cannot be promoted to active or paper trading.

---

### 4. Corrective Architecture & Causal Guidelines

To prevent similar vulnerabilities from ever entering SignalForge research or active trading codebases, the following engineering standards are established:

1. **Standardized Resampling Representation:**
   When higher-timeframe data is generated with `label="left"`, the feature matrix must ALWAYS be shifted by 1 interval before aligning with 1-minute bars:
   $$s_{\text{causal}}(t) = s_{\text{resampled}}(t).shift(1)$$
2. **Adoption of Causal Timeframe Synchronizer:**
   Research scripts must NOT use ad-hoc `.reindex(..., method="ffill")`. Instead, they must either:
   - Use the proven `_TimeframeCursor` architecture from `src/strategy/backtest_strategy.py`, or
   - Use `src/strategy/causal_timeframes.py:CausalTimeframeBuilder`.
3. **Automated Unit Testing for HTF Leaks:**
   Every multi-timeframe feature generator must include a unit test verifying that candle $T$'s features are invariant to changes in bar $T$'s subsequent minutes.

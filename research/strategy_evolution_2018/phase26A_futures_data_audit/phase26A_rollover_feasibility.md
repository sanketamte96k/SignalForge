# SignalForge Phase 26A — NIFTY Futures Rollover Feasibility & Methodology Audit

**Audit Reference:** `SF-ROLLOVER-AUDIT-26A-2026`  
**Target Instrument:** NIFTY Index Futures (`FUTIDX`)  
**Audit Scope:** Continuous Contract Construction & Rollover Feasibility under ₹0 Budget  
**Rollover Status:** **`ROLLOVER_INFEASIBLE_NO_CONTRACT_DATA`**  

---

## 1. Executive Summary

In quantitative derivatives research, trading individual futures contracts requires managing contract expiration. Because individual contracts expire monthly, long-horizon backtesting requires constructing a **continuous synthetic contract** via an explicit rollover and back-adjustment protocol.

This audit evaluates the theoretical methodologies for NIFTY Futures rollover, establishes the minimum data prerequisites, and assesses the feasibility of executing rollover within SignalForge's current local data lake.

### Feasibility Conclusion:
Because **zero contract-level futures files exist locally**, constructing a genuine continuous NIFTY Futures series is **physically and mathematically infeasible**. No rollover can be simulated without overlapping contract-level OHLCV, volume, and open-interest data.

---

## 2. Futures Rollover Methodologies for Indian Markets

Indian index futures on the National Stock Exchange (NSE) follow a standard monthly expiration cycle terminating on the **last Thursday of each month** (or the preceding trading day if Thursday is a trading holiday).

Three established methodologies exist for triggering contract rollover:

```
Rollover Trigger Mode           Mechanics                                               Prerequisite Data
---------------------           ---------                                               -----------------
1. Calendar-Based Rollover      Roll at fixed time window (e.g., T-1 or T-2 days at     Synchronized Near & Next
                                14:30 PM before expiry Thursday).                       1m price bars.

2. Volume-Crossover Rollover    Roll dynamically when Next-Month traded volume          Synchronized 1m volume
                                surpasses Near-Month volume for 15+ minutes.            for both contracts.

3. Open Interest (OI) Rollover  Roll when Next-Month Open Interest exceeds              Continuous contract-level
                                Near-Month Open Interest during expiry week.            OI feeds.
```

### 2.1 Back-Adjustment Techniques for Continuous Series
When transitioning from the expiring near contract ($C_1$) to the active next contract ($C_2$), a basis price jump occurs: $\Delta P = P_{C_2} - P_{C_1}$.

To eliminate artificial gap artifacts in technical indicator calculations (e.g. EMA, ATR, RSI), three continuous series models exist:
1. **Difference Adjustment (Panama Canal Method):**
   - Adds the cumulative roll gap $\Delta P$ backwards to all historical bars.
   - *Strengths:* Preserves absolute point differences and price volatility (critical for rupee-based trailing stops).
   - *Weaknesses:* Distorts historical percentage returns and can theoretically drive prices negative over long backtests.
2. **Ratio / Proportional Adjustment:**
   - Multiplies historical prices by the ratio $k = \frac{P_{C_2}}{P_{C_1}}$.
   - *Strengths:* Preserves percentage returns and geometric growth rates.
   - *Weaknesses:* Distorts absolute point price moves and rupee ATR calculations.
3. **Unadjusted Raw Contract Stitched Series:**
   - Stitches raw contract prices without back-adjustment, but models explicit rollover transactions (liquidating $C_1$ at market and purchasing $C_2$, paying calendar spread friction).
   - *Requirement:* Mandatory for realistic commercial backtests where trades are closed before expiry or rolled through real spread orders.

---

## 3. Data Prerequisites for Rigorous Futures Rollover

In strict compliance with SignalForge governance (*"Never merge different expiry contracts without explicit and documented rollover logic"* and *"Never fill missing candles through interpolation"*), valid continuous contract construction requires:

```
Essential Data Field            Minimum Standard                        Local Availability in SignalForge
--------------------            ----------------                        ---------------------------------
Near-Month 1m OHLCV             Continuous 1-minute bars up to expiry   0 bars (MISSING)
Next-Month 1m OHLCV             Overlapping 1m bars during roll week    0 bars (MISSING)
Traded Volume per Contract      Minute-level contract volume            0 records (MISSING)
Open Interest (OI) per Contract EOD and intraday contract OI            0 records (MISSING)
Calendar Spread Bid-Ask         Top-of-book quotes for spread order     0 quotes (MISSING)
Historical Lot Size Map         Exact historical lot size schedule      0 records (MISSING)
```

---

## 4. Local Feasibility Audit on SignalForge Data Lake

An audit of the repository confirmed the following structural impediments:

1. **Total Absence of Next-Month ($M_2$) Contracts:**
   Even if an analyst mistakenly attempted to treat the cash spot index as a near-month contract, **no next-month contract exists** to roll into.
2. **Zero Overlapping Liquidity Data:**
   Because no contract-level volume or open-interest files exist, it is impossible to determine whether liquidity migrated 3 days, 2 days, or 1 day prior to expiration.
3. **Inability to Model the Calendar Spread:**
   Institutional futures rollover is executed as a simultaneous calendar spread order (selling near-month at the bid, buying next-month at the ask). In the absence of contract orderbook data, calendar spread execution costs cannot be calculated.

---

## 5. Architectural Recommendations for Future Phases

If genuine NIFTY Futures data is acquired in future phases, the following architecture must be implemented:
1. **Contract Catalog Schema:** Maintain a dedicated SQLite / Parquet table indexing each contract by `contract_symbol`, `expiry_date`, `lot_size`, and `underlying`.
2. **Rollover Execution Engine:** Implement an explicit `RolloverPolicy` class in `src/strategy/` defining rollover triggers (e.g. `CALENDAR_T_MINUS_1_AT_1430`, `VOLUME_CROSSOVER_50PCT`).
3. **Transaction Cost Engine for Spreads:** Extend `src/backtest/indian_market_costs.py` with an `IndexFuturesRolloverCostConfig` incorporating exchange turnover charges for both legs and calendar spread STT concessions.

---

## 6. Final Rollover Verdict

Because zero contract-level datasets exist on disk, futures rollover cannot be simulated or backtested.

The rollover feasibility verdict is officially certified as **`ROLLOVER_INFEASIBLE_NO_CONTRACT_DATA`**.


# SignalForge Phase 25B — Combined Shared-Capital Portfolio Report

**Phase:** 25B  
**Model Architecture:** Chronological Event-Driven Shared Portfolio Simulator  
**Starting Capital:** ₹1,000,000 (10.00 Lakhs)  
**Position Allocation:** ₹100,000 per Trade (10% Maximum Allocation)  
**Max Concurrent Positions:** 10 Simultaneous Open Trades  
**Evaluation Scope:** 2017-01-02 to 2019-12-31  

---

## 1. Portfolio Performance Summary

| Metric | Shared Portfolio (Constrained) | Naive Sum of Unconstrained Stocks | Discrepancy / Impact |
| :--- | :---: | :---: | :--- |
| **Initial Capital** | ₹1,000,000.00 | ₹3,400,000.00 (₹100k × 34) | Capital aggregation constraint |
| **Final Portfolio Equity** | ₹996,075.60 | ₹3,401,416.59 | - |
| **Net Portfolio P&L** | **₹-3,924.40** | **₹1,416.59** | Difference: ₹-5,340.99 |
| **Portfolio Return %** | **-0.39%** | N/A (unconstrained) | Realistic capital-weighted return |
| **Max Portfolio Drawdown (₹)** | **₹5,542.78** | N/A | Peak-to-trough capital depletion |
| **Max Portfolio Drawdown (%)** | **0.55%** | N/A | Risk-adjusted baseline |
| **Total Signals Submitted** | 19223 | 19223 | Raw signals generated across 34 stocks |
| **Accepted Trades** | **7087** (36.9%) | 19223 (100.0%) | Realized portfolio executions |
| **Rejected Trades (Capital/Slots)** | **12136** (63.1%) | 0 (0.0%) | Trades blocked by capacity exhaustion |

---

## 2. Accepted Trades Portfolio Analytics

| Metric | Value |
| :--- | :--- |
| **Win Rate %** | 46.63% (3305 wins / 7087 trades) |
| **Win Rate 95% CI** | [45.48%, 47.80%] |
| **Gross Profit** | ₹49,279.05 |
| **Gross Loss** | ₹51,199.98 |
| **Total Transaction Costs** | ₹2,003.52 |
| **Profit Factor** | 0.96 |
| **Expectancy per Trade** | ₹-0.55 |
| **Long Trades Net P&L** | ₹-3,000.14 (43.2% WR) |
| **Short Trades Net P&L** | ₹-924.26 (49.6% WR) |

---

## 3. Engine Architecture & Limitation Disclosure

The native SignalForge `run_backtest` engine executes in single-stream symbol isolation. It does not natively manage shared cross-asset margining, margin calls, or concurrency contention.
To prevent misleading claims of tradability:
1. We recorded every trade execution from all 34 independent engine runs.
2. We merged and sorted all trade entries and exits chronologically.
3. We simulated a shared-capital constraint with a strict limit of 10 simultaneous positions and ₹100,000 fixed trade size.
4. Exactly **12136 trades (63.1%)** were rejected because available capital was exhausted or 10 positions were already active.

This proves that naive aggregation overstates or distorts real-world portfolio execution.

# SignalForge — Phase 26B: NIFTY Options Execution Feasibility and Cost Audit

**Phase:** 26B  
**Asset Class:** European Index Options (`OPTIDX` — `CE` & `PE`)  
**Underlying:** NIFTY 50 Index  
**Target Research Era:** 2017–2019  
**Execution Feasibility Verdict:** **`EXECUTION_INFEASIBLE_NO_DATA`**  

---

## 1. Executive Summary

Realistic backtesting of options strategies requires substantially higher-dimensional market data than cash equities or futures. Beyond simple OHLC candles, options execution is governed by order book bid-ask spreads, strike-specific liquidity cliffs, statutory transaction taxes, margin mechanics, and expiry settlement rules.

Because SignalForge currently possesses **zero contract-level options data and zero order-book quotes**, options backtesting is certified as **`EXECUTION_INFEASIBLE_NO_DATA`**.

This document outlines the strict execution requirements that must be satisfied before any options backtest can be considered credible.

---

## 2. Bid-Ask Spread Dynamics and Liquidity Cliffs

In options trading, executing at the "last traded price" (LTP) or "candle close" is a fundamental methodological error that leads to gross overstatement of strategy performance.

### Empirical Spread Realities in Indian Index Options:
1. **At-The-Money (ATM) Options:**
   * High liquidity, tight bid-ask spreads: Typically ₹0.25 to ₹1.00 (approx. 0.2% to 0.8% of option premium).
   * Tight market-maker presence allows near-frictionless market order fills for small lot sizes.
2. **Out-of-The-Money (OTM) Options (1 to 2 Standard Deviations):**
   * Wider spreads: Typically ₹2.00 to ₹10.00 (often 10% to 30% of option premium).
   * Market orders incur massive immediate slippage.
3. **Far Out-of-The-Money (OTM) Options (> 2 Standard Deviations):**
   * Severe order book thinning: Bids may sit at ₹0.05 with asks at ₹2.50 to ₹5.00 (spreads exceeding 100% of premium).
   * Crossing the spread immediately inflicts catastrophic losses.
4. **Execution Data Requirement:**
   * Valid backtesting requires tick-level Level-2/Level-3 order book data (top 5 bids and asks with queue sizes) to accurately simulate limit order queueing and market order impact cost.
   * **Current SignalForge Status:** 0 order book quotes available on disk.

---

## 3. Historical Contract Lot Sizing (2017–2019)

Trading options on the National Stock Exchange of India (NSE) requires adherence to discrete, non-fractional contract lot sizes:

```
+---------------------------+------------------------+---------------------------------------+
| Historical Epoch          | NIFTY Options Lot Size | Contract Multiplier                   |
+---------------------------+------------------------+---------------------------------------+
| Prior to October 2015     | 50 units               | Premium × 50                          |
| Oct 2015 – April 2021     | 75 units               | Premium × 75 (2017–2019 Research Era) |
| May 2021 – June 2023      | 50 units               | Premium × 50                          |
| July 2023 – April 2024    | 50 units               | Premium × 50                          |
| Post April 2024           | 25 units               | Premium × 25 (Subsequent Revision)    |
+---------------------------+------------------------+---------------------------------------+
```

* For the **2017–2019 historical research window**, the required contract lot size is **75 units**.
* Every trade must be executed in integer multiples of 75. Fractional option trading is prohibited on Indian exchanges.

---

## 4. Complete Indian Statutory & Brokerage Cost Architecture for Options

Options transaction costs are non-linear and differ radically from cash equities or futures. The statutory and broker charges applicable to intraday and swing options trading in India (2017–2019 rates) are summarized below:

```
+------------------------------------+--------------------------+-----------------------------------------------------------+
| Fee / Statutory Component          | Rate / Calculation Basis | Application Mode                                          |
+------------------------------------+--------------------------+-----------------------------------------------------------+
| Brokerage                          | ₹20 flat per order       | Charged on both Entry and Exit orders                     |
| STT (Securities Transaction Tax)   | 0.050% on Sell Premium   | Charged only on the sell side of option premium           |
| STT on ITM Option Exercise         | 0.125% of Total Intrinsic| Charged on buyer for options settling In-The-Money        |
| NSE Exchange Turnover Charge       | 0.053% of Premium        | Charged on both Buy and Sell premium turnover             |
| SEBI Turnover Charges              | ₹10 per ₹1 Crore (0.0001%)| Charged on premium turnover                               |
| Stamp Duty                         | 0.003% of Buy Premium    | Charged on buy orders only                                |
| GST                                | 18% on (Brokerage + Exch)| Applied to total broker and exchange fees                 |
+------------------------------------+--------------------------+-----------------------------------------------------------+
```

### The "STT Trap" on In-The-Money (ITM) Options Settlement:
During the 2017–2019 period, Section 98 of the Finance (No. 2) Act levied STT on exercised/settled options at **0.125% of the full settlement price of the underlying index**, rather than just the option premium.

**Illustrative Historical STT Trap Hazard:**
* An option trader holds 1 lot (75 units) of NIFTY 10,800 CE.
* At expiry, NIFTY 50 settles at 10,802.00 (the option expires ITM by 2.00 points).
* **Gross Option Payoff:** $2.00 \times 75 = ₹150.00$.
* **STT Levied on Exercise:** $0.125\% \times 10,802.00 \times 75 = ₹1,012.69$.
* **Net Trader P&L:** $₹150.00 - ₹1,012.69 = \mathbf{-₹862.69}$.
* A "winning" trade resulted in an instantaneous loss exceeding 500% of the payoff due to statutory settlement mechanics.

Any backtest lacking exact settlement and exercise logic will miscalculate options expiration P&L by orders of magnitude.

---

## 5. Margin Requirements & Capital Allocation

The capital required to trade options depends fundamentally on directional positioning:

1. **Option Buying (Long CE / Long PE):**
   * Capital required: $100\%$ of Premium $\times$ Lot Size ($C_0 \times 75$).
   * Maximum loss: Strictly capped at total premium paid.
   * No margin calls or variation margin required.
2. **Option Writing / Selling (Short CE / Short PE):**
   * Capital required: Standard Portfolio Analysis of Risk (SPAN) margin + Exposure margin.
   * For 2017–2019, writing 1 lot of NIFTY options required approximately **₹75,000 to ₹1,20,000** in margin capital per lot.
   * Maximum theoretical loss: Unlimited for naked calls; catastrophic for naked puts.
   * Subject to intraday margin calls, peak margin penalties, and extreme overnight gap risk.

---

## 6. Options Execution Feasibility Verdict

| Execution Criterion | Status in SignalForge | Feasibility Assessment |
|---|:---:|---|
| **Contract-level 1m OHLCV Data** | 0 bars | ❌ Impossible |
| **Top-of-Book Bid/Ask Quotes** | 0 quotes | ❌ Cannot calculate real entry/exit slippage |
| **Open Interest & Greeks** | 0 records | ❌ Cannot compute liquidity, gamma, or delta |
| **Historical Lot Size Alignment** | Documented (75) | ⚠️ Ready for implementation once data exists |
| **Statutory Cost Engine for Options** | Modeled in spec | ⚠️ Ready for implementation once data exists |
| **Expiry Settlement Engine** | Unimplemented | ❌ Missing contract settlement prices |

**Final Execution Verdict:** **`EXECUTION_INFEASIBLE_NO_DATA`**

Until clean, verified contract-level options minute data and bid-ask quotes are procured under strict ₹0 budget governance, no options execution or strategy backtesting is permitted.


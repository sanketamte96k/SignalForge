# SignalForge Phase 25A — NIFTY Futures Data Availability Audit Report

**Phase:** 25A  
**Instrument Class:** Index Futures (`FUTIDX`)  
**Underlying:** NIFTY 50 Index (`NIFTY`)  
**Audit Scope:** Genuinely Available Local Data in Repository  
**Budget Boundary:** STRICT ₹0.00  
**Audit Verdict:** **`BLOCKED_NO_DATA`**  

---

## 1. Executive Summary

A comprehensive, forensic audit across all directories, local archives, and scratch repositories in the SignalForge codebase reveals that **zero historical NIFTY futures contract data exists locally**.

No continuous futures series, contract-specific monthly files, expiry calendars, rollover rules, basis/spread logs, or historical lot-size mappings are present.

In strict adherence to Phase 25A safety instructions:
> *"Do not combine different contracts as if they were one continuous tradable instrument without an explicit, documented rollover method."*  
> *"Do not declare F&O support merely because the existing equity engine runs."*

---

## 2. Technical Audit Checklist for Futures

| Requirement Dimension | Parameter Checked | Repository Finding | Compliance / Audit Status |
| :--- | :--- | :--- | :--- |
| **Contract Symbols** | Near, Next, Far month contracts | 0 contracts found | **BLOCKED (0 Datasets)** |
| **Expiry Dates** | Historical last-Thursday expiries | 0 expiry schedules found | **MISSING** |
| **Historical OHLCV** | 1-minute intraday futures bars | 0 bars exist locally | **BLOCKED (0 Bars)** |
| **Contract Continuity** | Continuous back-adjusted series | 0 continuous series | **ABSENT** |
| **Rollover Method** | Volume-based, calendar, or OI-based | No rollover model implemented | **ABSENT** |
| **Lot-Size History** | Historic changes (75 -> 50 -> 25) | No historical lot size registry | **ABSENT** |
| **Bid / Ask Quotes** | Top-of-book BBO for slippage | 0 bid/ask order book feeds | **ABSENT** |
| **Open Interest (OI)** | Intraday and EOD contract OI | 0 OI records available | **ABSENT** |
| **Data Provenance** | Source vendor / exchange feed | None | **UNAVAILABLE** |

---

## 3. Forensic Distinction: Spot Index vs. Index Futures

SignalForge possesses a 1-minute historical dataset for the spot cash index: `data/historical/nifty50_1m_signalforge.csv`.

**Critical Causal Notice:**  
The cash spot index (`NIFTY 50`) is a **non-tradable mathematical index calculation** compiled by NSE Indices from equity prices. It cannot be used as a proxy for NIFTY Futures for the following causal reasons:

1. **Cost of Carry & Basis Spread:** Futures trade at a premium or discount (basis) relative to the cash index, dictated by interest rates and expected constituent dividend yields.
2. **Contract Expiry:** Futures terminate on monthly expiry dates, requiring physical or cash settlement and active position rollover. Spot indices never expire.
3. **Execution Slippage & Liquidity:** Futures execute against a discrete limit order book with fluctuating bid-ask spreads, market impact, and lot-size constraints (e.g. 25, 50, or 75 units per contract). Spot index points cannot be executed directly.
4. **Margin & Financing:** Futures involve initial and mark-to-market margins, overnight leverage, and capital charges that do not exist in equity or cash simulations.

**Conclusion:** Treating spot index bars as tradable futures trades is a catastrophic backtest failure mode. NIFTY Futures research is formally classified as **`BLOCKED_NO_DATA`**.

# SignalForge Phase 25A — NIFTY Options Data Availability Audit Report

**Phase:** 25A  
**Instrument Class:** Index Options (`OPTIDX`) — Call Options (`CE`) & Put Options (`PE`)  
**Underlying:** NIFTY 50 Index (`NIFTY`)  
**Audit Scope:** Genuinely Available Local Data in Repository  
**Budget Boundary:** STRICT ₹0.00  
**Audit Verdict:** **`BLOCKED_NO_DATA`**  

---

## 1. Executive Summary

A forensic inspection of the SignalForge repository confirms that **zero historical NIFTY options data (neither Call Options `CE` nor Put Options `PE`) exists locally**.

No options strike matrices, weekly or monthly expiry chains, intraday implied volatility surfaces, Greeks calculations, bid-ask spreads, or contract-level open interest datasets are present.

In strict adherence to Phase 25A requirements:
> *"Investigate historical options data availability separately for CE and PE."*  
> *"Do not assume index OHLC data can be used as a substitute for options contract prices."*

---

## 2. Separate CE and PE Audit Matrix

| Options Parameter | Call Options (`CE`) Audit | Put Options (`PE`) Audit | Combined Status |
| :--- | :--- | :--- | :--- |
| **Contracts Identified** | 0 contracts | 0 contracts | **BLOCKED (0 Contracts)** |
| **Strikes Covered** | 0 strike levels | 0 strike levels | **MISSING** |
| **Expiries Covered** | 0 weekly/monthly expiries | 0 weekly/monthly expiries | **MISSING** |
| **Historical 1m OHLCV**| 0 bars | 0 bars | **BLOCKED (0 Bars)** |
| **Bid / Ask Spreads** | 0 order-book quotes | 0 order-book quotes | **ABSENT** |
| **Volume & Open Interest**| 0 volume/OI logs | 0 volume/OI logs | **ABSENT** |
| **Implied Volatility (IV)**| 0 IV surface points | 0 IV surface points | **ABSENT** |
| **Option Greeks** | None (Delta, Gamma, Vega, Theta) | None (Delta, Gamma, Vega, Theta) | **ABSENT** |
| **Data Provenance** | None | None | **UNAVAILABLE** |
| **Testing Eligibility** | **BLOCKED_NO_DATA** | **BLOCKED_NO_DATA** | **BLOCKED_NO_DATA** |

---

## 3. Methodological Prohibition: Index Spot as Options Proxy

The repository maintains continuous 1-minute spot cash data for the NIFTY 50 index (`data/historical/nifty50_1m_signalforge.csv`).

**Prohibited Practice:**  
Assuming options can be simulated by applying Black-Scholes formulas to spot index prices without verified contract-level historical prices is strictly disallowed in SignalForge research for the following reasons:

1. **Volatility Skew & Smile:** Real-market options trade at implied volatilities that vary significantly across strike prices and tenors (volatility smile/smirk). A synthetic Black-Scholes calculation based on a single historical volatility constant fabricates prices that diverge wildly from actual executed options market trades.
2. **Illiquidity & Non-Linear Spreads:** Out-of-the-money (OTM) options often experience wide percentage bid-ask spreads (often 10%–50% of option premium) and sparse trading liquidity. Spot index modeling creates fictitious fills at theoretical mid-prices.
3. **Theta Decay Non-Linearity:** Real option time decay accelerates aggressively in final expiry hours, coupled with margin spikes and intraday short squeeze risks that cannot be backtested without actual contract tick/minute series.
4. **Corporate Actions & Strike Adjustments:** Constituent dividend distributions cause non-standard options contract adjustments and discrete jumps in forward pricing.

**Conclusion:** SignalForge possesses zero historical options datasets. NIFTY Options research (CE & PE) is certified as **`BLOCKED_NO_DATA`**.

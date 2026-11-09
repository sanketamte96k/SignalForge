# SignalForge — Phase 26B: NIFTY Options Data Quality and Feasibility Audit

**Phase:** 26B  
**Research Focus:** NIFTY Options (`OPTIDX` CE & PE) Historical Contract-Level Data Audit  
**Underlying:** NIFTY 50 Index  
**Audit Scope:** Local Storage, Historical Data Lake, and Repository Partitions  
**Governance Framework:** Zero External Budget (₹0.00), Deployment `STRICTLY_ON_HOLD`, Frozen Strategy V1  
**Audit Verdict:** **`BLOCKED_NO_DATA`**  

---

## 1. Executive Summary

A comprehensive, forensic audit of all storage partitions in SignalForge (encompassing `data/`, `temp_nse_data/`, `research/`, and historical partitions) confirms that **zero genuine historical NIFTY Options contract-level datasets exist on disk**.

Across 2,386 CSV files, 0 binary data files (parquet/h5/feather), and all candidate datasets:
* **Total Options Files Discovered:** **0**
* **Call Option (`CE`) Contracts Available:** **0**
* **Put Option (`PE`) Contracts Available:** **0**
* **Historical Strike Levels Available:** **0**
* **Contract-Specific Intraday Bars Available:** **0**
* **Historical Bid-Ask Order Book Quotes Available:** **0**
* **Contract-Level Open Interest (OI) Logs Available:** **0**
* **Historical Implied Volatility (IV) Surfaces Available:** **0**

Consequently, options research, quantitative modeling, and strategy backtesting for NIFTY Options are formally certified as **`BLOCKED_NO_DATA`**.

---

## 2. Dissection of Inspected Candidate Datasets

During data discovery, 16 candidate files bearing index or tick nomenclature were forensically examined. Every single candidate was disqualified from options research:

```
+----------------------------------------+---------------------+-------------------+---------------------+
| Candidate Dataset                      | Actual Instrument   | Options Metadata? | Feasibility Status  |
+----------------------------------------+---------------------+-------------------+---------------------+
| nifty50_1m_signalforge.csv             | CASH_SPOT_INDEX     | NONE (No Strike/  | BLOCKED_NOT_OPTIONS |
| nifty50_1m_research.csv                | CASH_SPOT_INDEX     | Expiry/Type/OI)   | BLOCKED_NOT_OPTIONS |
| nifty50_github_1m.csv                  | CASH_SPOT_INDEX     | NONE              | BLOCKED_NOT_OPTIONS |
| nifty50_1m.csv                         | CASH_SPOT_INDEX     | NONE              | BLOCKED_NOT_OPTIONS |
| NIFTY_50__EQ__INDICES__NSE__MINUTE.csv | CASH_SPOT_INDEX     | NONE              | BLOCKED_NOT_OPTIONS |
| NIFTY_BANK, IT, AUTO, FMCG, etc. (x8)  | CASH_SPOT_INDEX     | NONE              | BLOCKED_NOT_OPTIONS |
| Nifty50 Tick Logs (2021-03-26, etc.)   | CASH_INDEX_TICK_LOG | NONE              | BLOCKED_NOT_OPTIONS |
| 8-20 EMA strategy.ipynb                | STRATEGY_NOTEBOOK   | NONE              | BLOCKED_NOT_OPTIONS |
+----------------------------------------+---------------------+-------------------+---------------------+
```

### Forensic Deficiencies of Cash Spot Index Files for Options Research:
1. **No Strike Price Identifier:** Cash indices track the basket value of constituent shares; they have no strike parameter $K$.
2. **No Option Type Flag:** There is no designation of Call (`CE` - European Call) or Put (`PE` - European Put).
3. **No Expiry Date:** Cash index time series are continuous arithmetic constructs without contract expiration or settlement cycles.
4. **Zero Traded Volume (`volume = 0.0`):** An index cannot be bought or sold directly on an exchange; all volume entries in canonical NIFTY 50 files are 0.0.
5. **No Open Interest:** Open interest measures open derivative contracts held by market participants. Cash spot indices have no open interest.
6. **No Bid/Ask Quotes:** Options prices depend fundamentally on order book liquidity and wide bid-ask spreads. Spot indices report only an arithmetic price calculation.

---

## 3. Structural Microstructure Contrast: Equities vs. Futures vs. Options

Options cannot be modeled or treated like linear assets (equities or futures). The table below formalizes the dimensional complexity that makes backtesting impossible without genuine contract data:

| Microstructure Dimension | Cash Equity | Index Futures | Index Options (`CE` / `PE`) |
|---|---|---|---|
| **Payoff Profile** | Linear ($S_t - S_0$) | Linear ($F_t - F_0$) | **Non-Linear** ($\max(S_T - K, 0)$ or $\max(K - S_T, 0)$) |
| **Number of Instruments** | 1 per company | 3 active expiries | **Hundreds of active strikes $\times$ 2 types $\times$ multiple expiries** |
| **Price Determinants** | Corporate value, supply/demand | Spot index, interest rate, dividends | **Spot, strike, time to expiry ($\tau$), volatility ($\sigma$), interest ($r$), dividends ($q$)** |
| **Greeks Sensitivity** | Delta = 1.0; all others = 0 | Delta $\approx$ 1.0; all others = 0 | **Dynamic $\Delta, \Gamma, \Theta, \nu, \rho$ changing every minute** |
| **Time Value Decay** | None | Basis decay to zero | **Accelerating non-linear Theta decay ($\Theta \propto \frac{1}{\sqrt{\tau}}$)** |
| **Volatility Exposure** | Indirect | Indirect | **Direct exposure to Implied Volatility ($\nu$) and Volatility Skew** |
| **Order Book Depth** | Deep for large caps | Consolidated in Near Month | **Fragmented across dozens of out-of-the-money strikes** |
| **Bid-Ask Friction** | Tight (0.5 to 2 bps) | Tight (0.5 to 1.5 bps) | **Extremely wide (2% to 50%+ of option premium for OTM strikes)** |

---

## 4. Methodological Prohibition: Rejection of Synthetic Black-Scholes Generation

A common shortcut in flawed quantitative research is to take historical spot index prices ($S_t$) and synthesize historical option prices using the closed-form Black-Scholes-Merton (BSM) equation:

$$C(S, t) = S_t N(d_1) - K e^{-r(T - t)} N(d_2)$$

$$P(S, t) = K e^{-r(T - t)} N(-d_2) - S_t N(-d_1)$$

SignalForge research **strictly prohibits** synthetic BSM option price generation for backtesting. Any backtest built on synthetic BSM option prices constitutes research falsification for the following verifiable mathematical reasons:

### 1. Volatility Smile and Crash-Phobia Put Skew
Real options markets do not price options with a single constant volatility $\sigma$. Implied volatility varies dramatically across strikes:
* Out-of-the-money (OTM) Put options trade at a steep volatility premium over at-the-money (ATM) options due to institutional demand for downside portfolio insurance (crash-phobia skew).
* Out-of-the-money Call options trade at distinct implied volatilities reflecting upside speculation or covered call writing.
* A single historical volatility input in BSM severely underprices OTM puts, creating fictitious "cheap hedges" or fictitious high profits for option writers that do not reflect actual exchange trading prices.

### 2. Discrete Jump Diffusion and Fat Tails
The Black-Scholes model assumes geometric Brownian motion with continuous paths:
$$dS_t = \mu S_t dt + \sigma S_t dW_t$$
Real Indian markets experience overnight gaps, earnings announcements, macroeconomic shocks, and geopolitical jumps. Option premiums embed jump-risk premia that no continuous BSM model captures.

### 3. Fictitious Fills and Liquidity Illusion
In real trading:
* Deep OTM options have bid-ask spreads that can exceed 50% of the premium.
* Many strikes trade only intermittently (several minutes or hours between trades).
* BSM generates smooth, continuous mid-prices every minute, allowing a simulation algorithm to execute millions of shares at theoretical zero-slippage mid-prices that never existed in the live order book.

### 4. Non-Standard Expiries and Settlement Mechanics
Indian index options settle strictly at the volume-weighted average price (VWAP) of the underlying index between 15:00 and 15:30 on the expiration Thursday. Synthetic pricing ignores expiry settlement dynamics, intraday pin risk, and margin spikes.

---

## 5. Audit Conclusion

SignalForge possesses **zero verified historical NIFTY Options contract-level data**.

Because no genuine contract data exists and synthetic generation is methodologically disallowed, no options backtesting can be performed.

**Official Verdict:** **`BLOCKED_NO_DATA`**  
**Governance Action:** Options research remains halted until genuine contract-level tick/minute datasets are integrated under verified data provenance.


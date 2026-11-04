# SignalForge Phase 25A — Recommended Next Research Steps

**Phase:** 25A  
**Objective:** Actionable, Stage-Gated Research Roadmap Expanding SignalForge beyond 5 Stocks  

---

## 1. Immediate Next Step: Stage-Gated Ingestion of the 29 Available Equities

The most impactful immediate action that requires **₹0 budget** is to run the existing `HistoricalDataPipeline` across the 29 verified raw archive stocks (`temp_nse_data/NSE Minute Data/NSE_Stocks_Data`) to bring them into **Canonical Clean Storage** (`data/historical/stocks/`).

### Ingestion Action Plan:
1. **Batch Ingestion:** Execute `HistoricalDataPipeline.ingest_symbol` in controlled batches (e.g. 5 stocks at a time) for the 29 stocks.
2. **Quarantine Anomaly Logging:** Isolate any non-trading auction prints into `data/historical/quarantine/{SYMBOL}_quarantined.csv`.
3. **Manifest Generation:** Generate cryptographic SHA-256 manifests under `data/historical/manifests/{SYMBOL}_1m_manifest.json`.
4. **Registry Update:** Safely update `data/universe_registry.json` using the existing atomic write utility to elevate their status to `READY`.

---

## 2. Multi-Symbol Strategy Generalization (2017–2019)

Once the 29 stocks are promoted to clean storage:
1. **Expand Hypothesis B Cross-Asset Evaluation:**
   Execute causal backtests on the expanded **34-stock panel** across 2017–2019 (excluding the quarantined 2020 partition).
2. **Sectoral Fragility Testing:**
   Evaluate whether the strategy's edge is isolated to specific sectors (e.g. Banking vs IT) or represents a persistent market-wide volatility compression anomaly.
3. **Portfolio Concentration & Drawdown Risk:**
   Model simultaneous multi-symbol position allocation with realistic capital constraints and margin limits.

---

## 3. Roadmaps Requiring Budget Authorization

If the user authorizes budget allocation in future phases:

### Track A: 2021–2025 Out-of-Sample Equities Acquisition
- **Recommended Provider:** TrueData India or Zerodha Kite Connect Historical API.
- **Scope:** Acquire continuous 1-minute OHLCV data for all 50 NIFTY 50 equities covering 2021–2025.
- **Estimated Cost:** ~₹1,500 – ₹2,500 / month.

### Track B: NIFTY Futures Engine Architecture
- **Requirements:** Implement a dedicated futures contract rollover model (calendar rollover vs volume rollover), historical basis calculations, and lot-size transition engine before attempting futures backtesting.
- **Data Requirement:** Acquire contract-level historical 1-minute data for near-month and next-month NIFTY index futures.

### Track C: NIFTY Options Analytical Engine Architecture
- **Requirements:** Implement an option pricing engine capable of calculating Black-76 implied volatilities, Greeks, and liquidity filters from strike-level contract data.
- **Data Requirement:** Acquire historical 1-minute options contract datasets (CE and PE) across trading expiries.

# SignalForge — Phase 24G.24: Data Pipeline Reliability Audit
## Exhaustive Audit of Local Historical Data Ingestion, Schema Consistency, Session Alignment & Partition Quarantine

**Author:** SignalForge Quantitative Engineering & Data Working Group  
**Status:** COMPLETED & VERIFIED  
**Repository State:** main (`3e47219`)  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Budget:** Strict ₹0.00 (Offline Historical Research Only)  

---

### Executive Summary

As part of the Phase 24G.24 Baseline Research & Engineering Validation, a comprehensive audit was executed across the SignalForge data ingestion pipeline and all locally stored historical market data files. The audit verified:
1. **Schema & Column Type Uniformity:** All 5 local stock datasets (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`) strictly adhere to the expected OHLCV specification (`timestamp`, `open`, `high`, `low`, `close`, `volume`).
2. **Session Boundary Alignment:** All trading timestamps adhere strictly to National Stock Exchange (NSE) intraday trading hours (09:15:00 to 15:30:00 IST). Non-trading intervals, pre-market auctions, and post-market closing sessions are correctly excluded.
3. **Partition Quarantine Preservation:** The 2020 Holdout dataset remains strictly quarantined under `EXPLORATORY / CONTAMINATED` status with zero read access for strategy optimization or alpha claims. Research partitions are restricted to 2017 (Train/Dev), 2018 (Train/Dev), and 2019 (Validation).
4. **Resampling Robustness:** The production resampling pipeline (`src/data/resampler.py`) correctly enforces complete-candle requirements, rejecting incomplete intervals caused by market interruptions or missing-minute gaps.

---

### 1. Local Historical Data Inventory & Provenance

SignalForge maintains 5 local continuous 1-minute historical equity datasets in `data/historical/stocks/`. All files were audited for byte length, bar counts, date boundaries, and SHA-256 cryptographic hashes:

| Symbol | File Path | Total 1m Bars | Start Date | End Date | File Size (Bytes) | SHA-256 Hash |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **ADANIPORTS** | `data/historical/stocks/ADANIPORTS_1m.csv` | 370,884 | 2017-01-02 09:15 | 2020-12-31 15:29 | 24,015,103 | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` |
| **ADANIENT** | `data/historical/stocks/ADANIENT_1m.csv` | 363,222 | 2017-01-02 09:15 | 2020-12-31 15:29 | 23,267,002 | `003610f76ee3f01c77f0980e03be8959d28e75294ea5bb97bcf95232a537f57c` |
| **ICICIBANK** | `data/historical/stocks/ICICIBANK_1m.csv` | 369,679 | 2017-01-02 09:15 | 2020-12-31 15:29 | 23,889,642 | `0e38a2e1d0df965b399d860e607ce11e3b50c0c0d10b777a8d56b06e8646b1eb` |
| **INFY** | `data/historical/stocks/INFY_1m.csv` | 371,114 | 2017-01-02 09:15 | 2020-12-31 15:29 | 24,054,611 | `a65efbb0ee303e945c72382cf8eb7c569ff4514ba4c95bcf56ff4ba803f268f7` |
| **RELIANCE** | `data/historical/stocks/RELIANCE_1m.csv` | 371,213 | 2017-01-02 09:15 | 2020-12-31 15:29 | 24,206,750 | `b99e74ef1a0bc07675622ea1f618471e411f5fe04e5aa11f9d6c77bb79e0007d` |

#### Invariant Verification
- **Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` is strictly verified and unchanged.
- **Universe Registry (`data/universe_registry.json`):** Untouched and intact.
- **Active Paper Ledger (`data/paper_trading/interactive_trades.json`):** Untouched and intact.

---

### 2. Timezone & Session Boundary Audit

#### 2.1 Timestamp Semantics
- **Format:** ISO 8601 string representation: `YYYY-MM-DD HH:MM:SS`.
- **Timezone:** Timestamps are recorded in Indian Standard Time (IST, UTC+05:30) without explicit offset suffixes.
- **Bar Stamping:** Each 1-minute bar represents trades occurring within $[T, T+1\text{m})$. For example, `09:15:00` represents trades executed between `09:15:00.000` and `09:15:59.999`.
- **Trading Session Window:** Intraday bars begin at `09:15:00` and end at `15:29:00` (last regular minute bar closing at `15:30:00`).
- **No Overnight Bleed:** Bars outside regular market hours (e.g. post-market trades or weekend auction records) are entirely absent.

#### 2.2 Missing-Minute Gaps and Low-Liquidity Periods
- During low-liquidity periods or temporary circuit halt events, 1-minute candles may be omitted rather than zero-filled.
- `src/data/resampler.py` rigorously guards against partial or corrupted higher-timeframe candles:
```python
    expected_rows = int(rule.removesuffix("min"))
    row_counts = resampled["close"].count()
    complete_candles = row_counts == expected_rows
    result = result.loc[complete_candles]
```
If any 1-minute candle is missing within a 5-minute, 15-minute, or 30-minute window, the higher-timeframe candle is marked incomplete and discarded. This guarantees that technical indicators (such as EMA, RSI, ATR) never ingest partial-volume or corrupted intervals.

---

### 3. Corporate Action Adjustment & Survivorship Bias

#### 3.1 Unadjusted Historical Price Sequences
The local historical datasets represent split/bonus-unadjusted historical prices. While suitable for intraday momentum and breakout strategies operating over single trading sessions:
- Large corporate actions (such as the 1:1 Reliance bonus in Sept 2017 or stock splits) manifest as single-candle price discontinuities between sessions.
- **Intraday Isolation:** Because `RiskEngineV2` and the production strategy strictly liquidate all positions at `15:20:00` (EOD), overnight jump risk across corporate actions is mitigated for open positions.
- **Feature Protection:** Indicators spanning across corporate action split dates can produce transient spikes in ATR or moving averages. In future live data feeds, corporate-action split adjustments or ratio-adjusted series must be standardized.

#### 3.2 Survivorship Bias Consideration
The 5 available equities (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`) were large-cap constituents selected historically. In Phase 24G.18, a broader 22-equity universe was pre-registered to combat selection bias. However, under the strict ₹0 budget restriction, research is constrained to the verified local archive without incurring external vendor costs.

---

### 4. Partition Integrity & Quarantine Enforcement

SignalForge enforces strict chronological partitioning across all historical research:
1. **Train / Development Partition 1 (2017):** Fully accessible for baseline engineering audits, exploratory parameter sweeps, and cost sensitivity testing.
2. **Train / Development Partition 2 (2018):** Primary historical development baseline.
3. **Out-of-Sample Validation Partition (2019):** Strictly reserved for out-of-sample validation.
4. **Contaminated / Exploratory Partition (2020):** Contaminated during preliminary exploration in early phases. Quarantined with zero access for alpha promotion.

**Audit Status:** The data pipeline correctly separates partitions chronologically by date slice (`df.loc['YYYY-01-01':'YYYY-12-31']`), preventing cross-period information leakage.

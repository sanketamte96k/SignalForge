# SignalForge Phase 24G.19 — Market Data Technical Specification
## Data Integrity, Normalization & Ingestion Standards for NSE 1-Minute Equities

**Document ID:** `SF-PHASE24G19-DATA-SPEC-2026-V1`  
**Specification Reference:** `SF-SPEC-ALPHA-2026-V1` (Status: `DRAFT`)  
**Target Coverage Horizon:** `2021-01-01 09:15:00` to `2025-12-31 15:29:00`  
**Target Universe:** 22 NSE Liquid Equities across 8 Sectors  

---

## 1. Canonical Schema & Temporal Conventions

All historical market data ingested for the SignalForge research environment must strictly conform to the Canonical Intraday Contract:

### 1.1 Bar Schema
The dataset must be persisted with the standard 6-column header:
```csv
timestamp,open,high,low,close,volume
```

| Field Name | Data Type | Physical Meaning | Constraints & Validation |
| :--- | :--- | :--- | :--- |
| **`timestamp`** | `str` / `datetime` | Start time of the 1-minute aggregation interval | Formatted as `YYYY-MM-DD HH:MM:SS` (IST, UTC+05:30) |
| **`open`** | `float64` | Price of the first executed trade in the candle | Strictly positive ($> 0.0$), rounded to 2 decimal places (or tick size) |
| **`high`** | `float64` | Maximum traded price during the 1-minute interval | $\text{High} \ge \max(\text{Open}, \text{Close}, \text{Low})$ |
| **`low`** | `float64` | Minimum traded price during the 1-minute interval | $0.0 < \text{Low} \le \min(\text{Open}, \text{Close}, \text{High})$ |
| **`close`** | `float64` | Price of the last executed trade in the candle | $\text{Low} \le \text{Close} \le \text{High}$ |
| **`volume`** | `float64` / `int64`| Total shares transacted within the 1-minute bar | Non-negative ($\ge 0$). Must be numeric. |

### 1.2 Timezone & Bar Alignment Standards
1. **Timezone**: All timestamps are anchored to Indian Standard Time (`Asia/Kolkata`, UTC+05:30).
2. **Trading Hours**: Standard NSE equity market session operates from `09:15:00` to `15:29:00` (inclusive).
   - Normal full-day trading session comprises exactly 375 one-minute intervals.
   - Pre-open market session (09:00:00 to 09:08:00) and post-close settlement session (15:40:00 to 16:00:00) must be segregated from the continuous intraday execution series.
   - Muhurat trading sessions (special 1-hour festive sessions) must be tagged with explicit metadata.
3. **Bar Boundary Convention**:
   - SignalForge standardizes on the **Bar-Start Convention**:
     - `09:15:00` represents trades executed between `09:15:00.000` and `09:15:59.999`.
     - `15:29:00` represents the final continuous trading minute between `15:29:00.000` and `15:29:59.999`.
   - When ingesting from providers that use Bar-End conventions (e.g. labeling `09:16:00`), timestamps must be normalized deterministically by subtracting 1 minute.

---

## 2. Corporate Action Adjustment Specifications

Between 2021 and 2025, major corporate actions occurred among the pre-registered 22 equities:
- **`RELIANCE`**:
  * Demerger of Jio Financial Services (effective July 20, 2023, price discovery adjustment ~₹261.85);
  * 1:1 Bonus Issue (record date October 28, 2024; ex-bonus factor 0.50).
- **`BPCL`**:
  * 1:1 Bonus Issue (record date June 22, 2024; ex-bonus factor 0.50).
- **`DRREDDY`**:
  * 1:5 Stock Split (subdivision from face value ₹5 to ₹1; record date October 28, 2024; split factor 0.20).
- **`HDFCBANK`**:
  * Amalgamation of HDFC Limited into HDFC Bank (effective July 13, 2023; equity base expanded).

### Dual-Series Requirement
To ensure both indicator validity and economic cost realism:
1. **Adjusted Price Series ($\text{Adj\_OHLC}$)**:
   - Used for indicator calculation (Donchian breakout channels, Average True Range, moving averages).
   - Prevents artificial gap-down signals (e.g. a 50% plunge on a 1:1 bonus day) that would trigger false breakout entries or false stop-loss exits.
2. **Unadjusted Realized Series ($\text{Raw\_OHLC}$)**:
   - Required for accurate statutory fee accounting (STT, NSE turnover charges, brokerage, stamp duty, and SEBI turnover fees).
   - Applying statutory percentages to split-adjusted historical prices from years ago distorts monetary turnover and cash friction.

---

## 3. Missing Data, Zero Volume, and Market Halts

To prevent look-ahead bias and synthetic fill illusions:
1. **Zero-Volume Candlesticks**:
   - If an equity trades during minute $t$, a valid bar with $\text{Volume} > 0$ is produced.
   - If no trades occur in minute $t$, the exchange emits no tick.
   - **Anti-Forward-Fill Rule**: SignalForge strictly prohibits synthetic forward-filling in raw storage. Zero-volume minutes must either be omitted from the physical CSV or explicitly flagged with $\text{Volume} = 0.0$.
   - The strategy backtest engine handles missing bars causally: no entry signal can be executed on a non-existent bar.
2. **Trading Halts & Circuit Limits**:
   - Nationwide market halts (e.g. index circuit breakers) or stock-specific trading suspensions must appear as natural time gaps.
   - Ingestion manifests must record the duration and count of all detected intraday time gaps ($> 1$ minute during 09:15–15:29).

---

## 4. Cross-Verification Against Official Daily NSE Bhavcopy

Every acquired 1-minute dataset must be verified against the official Daily NSE Bhavcopy published by the exchange:

$$\text{Daily High}_{\text{Bhavcopy}} \stackrel{?}{=} \max_{t \in \text{Day}} \text{High}_t$$
$$\text{Daily Low}_{\text{Bhavcopy}} \stackrel{?}{=} \min_{t \in \text{Day}} \text{Low}_t$$
$$\text{Daily Close}_{\text{Bhavcopy}} \stackrel{?}{\approx} \text{Close}_{15:29:00} \quad (\text{Note: Official close is 15:00–15:30 VWAP})$$
$$\text{Daily Volume}_{\text{Bhavcopy}} \stackrel{?}{=} \sum_{t \in \text{Day}} \text{Volume}_t$$

Datasets exhibiting $> 0.5\%$ cumulative discrepancy against official Bhavcopy volume or price boundaries must be flagged and quarantined for manual inspection.

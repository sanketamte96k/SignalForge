# SignalForge — Phase 24G.26: Research Engine & Quantitative Strategy Integration
## Data Loading, Causal Resampling, Signal Generation, Risk Engines & Performance Metrics

**Auditor:** SignalForge Architecture & Systems Engineering Working Group  
**Status:** COMPLETED & VERIFIED  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Target Codebase:** `src/strategy/`, `src/signals/`, `src/backtest/`, `src/data/`  
**Budget:** Strict ₹0.00  

---

### Executive Summary

A comprehensive architectural inspection was performed on SignalForge's quantitative research and backtesting infrastructure. 

The audit mapped:
1. **The Ingestion & Resampling Pipeline:** How 1-minute historical OHLCV data is parsed, validated, and causally resampled into higher timeframes.
2. **The Production Signal Engine:** The rule-based multi-timeframe decision tree (`generate_signal`) evaluating EMA trends, RSI momentum, and volume confirmation.
3. **The Dual Backtesting Architecture:** The distinction between the historical baseline simulator (`src/backtest/simulator.py`) and the institutional next-generation risk engine (`src/backtest/risk_engine_v2.py`).
4. **Integration Disconnects:** While the REST API successfully exposes real-time strategy signals (`GET /api/strategy/signal`), comprehensive multi-year backtests currently run exclusively via CLI scripts (`scripts/run_backtest_2018.py`) rather than being launchable from the frontend dashboard.

---

### 1. Ingestion, Validation & Resampling Pipeline

```
1-Minute Historical CSV
       │
       ▼
src/data/resampler.py: validate_ohlcv()
       │
       ▼
src/data/resampler.py: resample_ohlcv()
  ├── rule: 5m, 10m, 15m, 30m
  ├── label="left", closed="left"
  └── expected_rows verification (drops incomplete bars)
       │
       ▼
src/strategy/backtest_strategy.py: calculate_timeframe_indicators()
  ├── EMA(20), EMA(50)
  ├── RSI(14)
  ├── ATR(14)
  └── RVOL(20)
```

#### Complete-Candle Requirement
In `src/data/resampler.py`, `resample_ohlcv` enforces mathematical completeness:
```python
    expected_rows = int(rule.removesuffix("min"))
    row_counts = resampled["close"].count()
    complete_candles = row_counts == expected_rows
    result = result.loc[complete_candles]
```
If a 5-minute bucket receives only 4 minutes (e.g. during market open delay or trading halt), the candle is rejected. Technical indicators never compute over partial intervals.

---

### 2. Strategy Engine & Rule-Based Signal Generation

#### 2.1 The Multi-Timeframe Alignment Filtration
In [`src/signals/signal_engine.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/signals/signal_engine.py), trading decisions require hierarchical cross-timeframe alignment across four discrete intervals:
1. **Macro Trend (30m & 15m):** Confirms structural trend direction via EMA20 vs EMA50.
2. **Intermediate Setup (10m):** Validates momentum continuity.
3. **Execution Trigger (5m):** Requires candle alignment, RSI momentum confirmation, and volume expansion ($RVOL \ge 1.5$).
4. **Locked Production Long Filter:**
   ```python
   # src/strategy/backtest_strategy.py: _apply_locked_long_filter
   if result.signal == Signal.BUY:
       if all(state.rsi >= 60.0 for state in states):
           return result
       return Signal.NO_TRADE
   ```
   RSI must be $\ge 60.0$ across all timeframes before authorizing a LONG entry.

---

### 3. Dual Backtesting Engines: Simulator vs RiskEngineV2

SignalForge maintains two distinct backtesting implementations:

| Feature / Capability | Baseline Simulator (`src/backtest/simulator.py`) | Next-Gen Risk Engine (`src/backtest/risk_engine_v2.py`) |
| :--- | :--- | :--- |
| **Execution Timing** | Next-bar open (`bar[i+1].open`) | Next-bar open with configurable execution delay |
| **Position Sizing** | Fixed capital allocation / units | Multi-constraint: $Q = \min(Q_{\text{risk}}, Q_{\text{leverage}})$ |
| **Stop-Loss / Targets** | Static ATR brackets ($1.5 \times, 3.0 \times$) | Clamped stops (0.3%–3.0%) with monotonic trailing ratchet |
| **Collision Resolution** | Same-bar extreme breach unhandled | Ultra-conservative `stop_first` rule enforced |
| **EOD Liquidation** | Session close exit | Strict mandatory exit at `15:20:00` IST |
| **Statutory Cost Model**| Fixed basis points slippage | Exact Indian statutory model (Brokerage, STT, Exchange, GST, Stamp) |
| **Circuit Breakers** | None | Intraday daily drawdown halt |

**Key Finding:** `RiskEngineV2` represents institutional-grade simulation, whereas the original `simulator.py` was a prototype. All research since Phase 24G.14 has migrated to `RiskEngineV2`.

---

### 4. Integration Gaps & Product Roadmap Opportunities

1. **Frontend Backtest Runner Gap:**
   Currently, the React frontend displays live strategy signals for any selected stock (`StockAnalysisView.jsx`). However, there is no UI component allowing a user to click "Run Historical Backtest" on a symbol, select a date range, and view an equity curve. Backtests must be initiated via Python CLI scripts.
2. **Strategy Registry Unification:**
   The backend strategy router (`src/api/routes/strategy.py`) evaluates the frozen V1 strategy. Proposed future hypotheses are not yet dynamic plug-and-play modules selectable via API query parameters.
3. **Asynchronous Simulation Queue:**
   Because running a full 3-year backtest on 1-minute data (~275,000 bars) requires 1–3 seconds of CPU time, web-based backtests should be handled asynchronously via background task workers (e.g. Celery or FastAPI BackgroundTasks) with progress polling.

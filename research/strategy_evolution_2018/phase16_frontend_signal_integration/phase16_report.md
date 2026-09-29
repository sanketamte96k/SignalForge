# Phase 16 Report: Signal Engine → Frontend Integration

## Executive Summary
Phase 16 integrates the authoritative SignalForge multi-timeframe strategy engine directly with the FastAPI backend and React frontend dashboard. Prior to this integration, the UI displayed placeholder and unavailable notices across key strategy dimensions ("API timeframe not available", "Indicator details not exposed by the current API.", "Not available" execution brackets). This phase exposed real engine values, added strict timeframe validation, unified chart and strategy indicators, and eliminated placeholder signals without lookahead bias.

---

## What Was Inspected
1. **API Layer**:
   - `src/api/main.py`: App configuration, CORS middleware, router registration.
   - `src/api/models.py`: Pydantic models with `extra="forbid"`.
   - `src/api/routes/nifty.py`: Chart (`/api/nifty/chart`), signal (`/api/nifty/signal`), analysis (`/api/nifty/analysis`), latest (`/api/nifty/latest`).
   - `src/api/routes/stocks.py`: Universe management, readiness, validation endpoints.
2. **Strategy Engine**:
   - `src/strategy/context.py`: `CausalStrategyContext` coordinating sequential 1-minute candle feeding.
   - `src/signals/signal_engine.py`: `generate_signal` combining 30m, 15m, 10m, 5m causal timeframe states.
   - `src/strategy/signal_rules.py`: `trend_direction`, `momentum_support`, `volume_support`, `volatility_is_acceptable`.
   - `src/strategy/risk_engine.py`: `calculate_risk_reward` (1.5 ATR stop, 1.5R Target 1, 2.0R Target 2).
   - `src/data/resampler.py`: `resample_ohlcv` with support for `5m`, `10m`, `15m`, `30m`.
3. **Frontend Dashboard**:
   - `frontend/src/App.jsx`: Main dashboard layout, state synchronization, navigation.
   - `frontend/src/CandlestickChart.jsx`: Lightweight Charts candlestick & RSI visualizer.
   - `frontend/src/api.js`: Client API services.
   - `frontend/src/App.css`: Visual design tokens and layout classes.

---

## Existing Architecture & Root Causes
- **Engine Purity**: The backend already possessed a causal multi-timeframe strategy coordinator (`CausalStrategyContext`). However, `/api/nifty/signal` returned only `{symbol, signal, position, timestamp, price, strategy}`, omitting the calculated indicator states (`ema20`, `ema50`, `rsi14`, `atr14`, `rvol20`), confirmation flags, execution brackets, and timeframe parameters.
- **Frontend Timeframe Disconnect**: The frontend exposed buttons for `5m`, `10m`, `15m`, `30m`, `1H`, `4H`, `1D`, but the backend resampler only supported `5m`, `10m`, `15m`, `30m`. Selecting unsupported timeframes resulted in generic disconnect errors or silent fallbacks.
- **UI Placeholders**: Because indicator and bracket fields were missing from the signal endpoint, the frontend hardcoded "Not Available" and "Indicator details not exposed" strings.

---

## Changes Made
1. **Backend Signal Contract (`src/api/models.py`)**:
   - Added `StrategyIndicators` (`ema_fast`, `ema_slow`, `rsi`, `atr`, `volume`, `vwap`).
   - Added `StrategyConfirmation` (`ema`, `rsi_momentum`, `volume`, `multi_timeframe`).
   - Added `StrategySignalResponse` and updated `NiftySignalResponse` maintaining strict backward compatibility.
2. **Authoritative Backend Engine Route (`src/api/routes/nifty.py`)**:
   - Implemented `_build_strategy_signal(data, symbol, timeframe)` producing genuine strategy indicators and confirmations.
   - Derived execution brackets using the repository's `calculate_risk_reward`:
     - BUY: `stop_loss < entry_price < target_1 < target_2`
     - SELL: `target_2 < target_1 < entry_price < stop_loss`
     - NO_TRADE: `entry_price=null`, `stop_loss=null`, `target_1=null`, `target_2=null` (no fabricated levels).
   - Validated requested timeframe against `SUPPORTED_STRATEGY_TIMEFRAMES = ("5m", "10m", "15m", "30m")` and returned HTTP 400 for unsupported requests.
   - Extended `get_nifty_signal` with `timeframe: str = Query("15m")`.
3. **Strategy Router (`src/api/routes/strategy.py` & `src/api/main.py`)**:
   - Created `/api/strategy/signal` accepting `symbol` and `timeframe`.
   - Included controlled HTTP 404 for nonexistent instruments and HTTP 400 for empty symbols or unsupported timeframes.
4. **Frontend API Client (`frontend/src/api.js`)**:
   - Parameterized `fetchNiftySignal(timeframe = '15m')`.
   - Added `fetchStrategySignal(symbol = 'NIFTY 50', timeframe = '15m')`.
5. **Component Refactoring (`frontend/src/StrategySignalPanel.jsx`)**:
   - Created dedicated `StrategySignalPanel` displaying:
     1. Dominant Signal Badge (BUY / SELL / NO TRADE).
     2. Instrument & Key Price Metrics.
     3. Signal Timestamp & Active Timeframe Tag.
     4. Real Signal Reason from engine.
     5. Real Confidence (when engine evaluates alignment).
     6. Confirmation Factors (EMA, RSI Momentum, Volume, Multi-Timeframe) with honest status pills (`Confirmed`, `Unconfirmed`, `Unavailable`).
     7. Execution Brackets (SL, T1, T2) or explicit "No active setup" on NO_TRADE.
     8. Clean EmptyState for Unsupported Timeframes (`1H`, `4H`, `1D`) with quick switch buttons to `15m` / `5m`.
6. **Frontend Dashboard Integration (`frontend/src/App.jsx`)**:
   - Synchronized `activeTimeframe` with both the Candlestick Chart and Strategy Panel.
   - Replaced old static placeholder DOM with `<StrategySignalPanel />`.

---

## API Contract Specification
```json
{
  "symbol": "NIFTY 50",
  "timeframe": "15m",
  "timestamp": "2024-03-26T15:29:00",
  "signal": "NO_TRADE",
  "signal_reason": "Incomplete or neutral timeframe trend alignment.",
  "entry_price": null,
  "stop_loss": null,
  "target_1": null,
  "target_2": null,
  "confidence": 0.0,
  "indicators": {
    "ema_fast": 22005.12,
    "ema_slow": 21995.40,
    "rsi": 54.20,
    "atr": 22.10,
    "volume": null,
    "vwap": null
  },
  "confirmation": {
    "ema": false,
    "rsi_momentum": false,
    "volume": null,
    "multi_timeframe": false
  },
  "status": "HISTORICAL",
  "position": null,
  "price": 22004.70,
  "strategy": "SignalForge"
}
```

---

## Supported Timeframes
| Timeframe | Chart Supported | Strategy Supported | Aggregation / Source |
|---|---|---|---|
| **1m** | Yes | No (MTF requires >= 5m) | Raw 1-minute historical data |
| **5m** | Yes | Yes (Entry Timing) | Causal 5-minute resampled candle |
| **10m** | Yes | Yes (Confirmation) | Causal 10-minute resampled candle |
| **15m** | Yes | Yes (Primary Trend) | Causal 15-minute resampled candle |
| **30m** | Yes | Yes (Context) | Causal 30-minute resampled candle |
| **1H** | No | No (HTTP 400) | Not supported by engine |
| **4H** | No | No (HTTP 400) | Not supported by engine |
| **1D** | No | No (HTTP 400) | Not supported by engine |

---

## Look-Ahead Protection
- All indicator states are processed strictly sequentially candle-by-candle through `CausalStrategyContext`.
- Higher-timeframe candles are only finalized after their full elapsed interval has closed (e.g. 09:15-09:20 5m candle is only visible at 09:20).
- No future candle is ever queried or introduced into the current signal.

---

## Test Verification Summary
### Backend Tests (`pytest`)
- `tests/api/test_health.py`: 2/2 PASS
- `tests/api/test_nifty.py`: 8/8 PASS
- `tests/api/test_nifty_chart.py`: 3/3 PASS
- `tests/api/test_strategy.py`: 13/13 PASS
  - 1. Health endpoint still passes.
  - 2. Existing NIFTY chart endpoint still passes.
  - 3. Strategy endpoint returns valid schema.
  - 4. BUY signal schema validation.
  - 5. SELL signal schema validation.
  - 6. NO_TRADE schema validation.
  - 7. Unsupported timeframe returns correct error.
  - 8. Missing data returns controlled response.
  - 9. Indicator values are numeric/null as appropriate.
  - 10. SL/target relationship is valid when a trade exists.
  - 11. Timestamp is valid.
  - 12. No future candle is used.
  - 13. Existing endpoints remain backward compatible.
**Total Backend Tests**: 26/26 PASS

### Frontend Tests (`vite-node`)
- `test/state_views.test.js`: 15/15 PASS
- `test/chart_ux.test.js`: 15/15 PASS
- `test/scanner_ux.test.js`: 13/13 PASS
- `test/analysis_workflow.test.js`: 15/15 PASS
- `test/responsive_layout.test.js`: 8/8 PASS
- `test/keyboard_shortcuts.test.js`: 9/9 PASS
- `test/toast_notifications.test.js`: 43/43 PASS
- `test/accessibility_ux.test.js`: 14/14 PASS
- `test/settings_ux.test.js`: 14/14 PASS
- `test/strategy_panel.test.js`: 7/7 PASS
  - 1. Strategy panel renders BUY with brackets and confirmations.
  - 2. Strategy panel renders SELL with brackets and confirmations.
  - 3. Strategy panel renders NO TRADE without fabricated brackets.
  - 4. Loading state with accessible semantics.
  - 5. API error state with retry action.
  - 6. Unsupported timeframe state with quick-switch buttons.
  - 7. Null optional fields do not crash the UI.
**Total Frontend Tests**: 153/153 PASS

---

## Known Limitations
1. **Index Volume**: NIFTY 50 cash index data does not have continuous exchange volume. RVOL and Volume confirmation are correctly reported as `null` (Unavailable) to avoid false penalties or fake confirmation.
2. **Single Stock Intraday History**: The historical sample currently holds full tick/1m data for NIFTY 50 (`nifty50_1m_signalforge.csv`). Single stock histories for non-index equities return controlled 404 responses until their respective historical series are imported.
3. **Higher Timeframes**: `1H`, `4H`, `1D` are intentionally unsupported until Phase 17+ multi-session aggregation rules are approved.

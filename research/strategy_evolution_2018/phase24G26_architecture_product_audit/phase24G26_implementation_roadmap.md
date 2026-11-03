# SignalForge — Phase 24G.26: Implementation Roadmap

## 1. Roadmap Architecture & Objectives

This implementation roadmap defines the engineering schedule to transition SignalForge from an audited research prototype to an enterprise-grade quantitative analysis platform.

### Core Guiding Principles:
1. **Strict ₹0 Budget Adherence:** Zero reliance on paid commercial feeds, external APIs, or proprietary databases.
2. **Safety & Causal Invariants:** Preserves the frozen V1 configuration hash (`920515d7...`), canonical ADANIPORTS hash (`fb327552...`), active paper trading ledger, and the quarantined 2020 holdout partition.
3. **Incremental Test-Driven Delivery:** Every milestone includes automated unit, integration, and regression tests before promotion.

```
+-----------------------------------------------------------------------------------------+
|                               IMPLEMENTATION TIMELINE                                   |
+-----------------------------------------------------------------------------------------+
| Milestone 1: Core Reliability & Security Hardening (Days 1–2)                           |
|   └── Atomic writes, path traversal prevention, centralized Pydantic settings.          |
+-----------------------------------------------------------------------------------------+
| Milestone 2: Asynchronous Research Engine Bridge (Days 3–5)                             |
|   └── Async backtest runner, REST job queue, frontend strategy UI wire-up.              |
+-----------------------------------------------------------------------------------------+
| Milestone 3: Interactive Quantitative Reporting (Days 6–8)                              |
|   └── Equity curves, underwater drawdowns, self-contained HTML tear sheets.             |
+-----------------------------------------------------------------------------------------+
| Milestone 4: Storage Modernization & DevOps (Days 9–12)                                 |
|   └── Parquet/DuckDB data lake, portfolio backtester, Docker containerization.          |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Milestone 1: Core Reliability & Security Hardening

**Estimated Effort:** 2 Days  
**Primary Focus:** Prevent file corruption, eliminate path traversal vulnerabilities, and formalize runtime configuration.

### Tasks & Technical Specifications:
- **Task 1.1: Atomic JSON File Storage Utility**
  - Implement `src/core/io_utils.py` containing `atomic_write_json(path, data)`.
  - Pattern: Write payload to temporary file (`path.with_suffix('.tmp')`), flush/sync to disk, execute atomic `os.replace(temp_path, path)`.
  - Integrate into `src/data/universe_registry.py` and `src/api/routes/paper_trading.py`.
  - *Acceptance Criteria:* Passes concurrent multi-threaded write stress test with 0 corrupted files or JSON decode errors.
- **Task 1.2: Strict Path Traversal Guardrails**
  - Implement `validate_symbol_and_path(symbol: str, base_dir: Path) -> Path` in `src/core/security.py`.
  - Validate symbol matches regex `^[A-Z0-9_-]+$`; assert `resolved_path.is_relative_to(base_dir)`.
  - Integrate across `src/api/routes/stocks.py`, `src/api/routes/strategy.py`, and `src/api/routes/universe.py`.
  - *Acceptance Criteria:* Reject malicious inputs (`../`, `..\`, absolute paths) with HTTP 400 Bad Request.
- **Task 1.3: Centralized Pydantic Configuration Management**
  - Implement `src/core/config.py` inheriting from `pydantic_settings.BaseSettings`.
  - Define `API_HOST`, `API_PORT`, `DATA_ROOT_DIR`, `LOG_LEVEL`, `CORS_ORIGINS`.
  - Update `src/api/main.py` to source CORS and server configuration from settings.
  - *Acceptance Criteria:* App boots cleanly with default local fallback values when no `.env` file is present.

---

## 3. Milestone 2: Asynchronous Research Engine Bridge

**Estimated Effort:** 3 Days  
**Primary Focus:** Connect the fast vector backtester (`scripts/run_backtest_2018.py`) to the FastAPI backend and React frontend.

### Tasks & Technical Specifications:
- **Task 2.1: Asynchronous Backtest Job Manager**
  - Implement `src/strategy/job_manager.py` using Python `asyncio` and thread pools to run backtest simulations without blocking Uvicorn's event loop.
  - Track in-memory task states: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, with progress percentages.
- **Task 2.2: RESTful Backtest Job Endpoints**
  - Add routes to `src/api/routes/strategy.py`:
    - `POST /api/strategy/backtest/run`: Submit symbol, date range, and parameter overrides. Returns `{ "task_id": "uuid" }`.
    - `GET /api/strategy/backtest/status/{task_id}`: Returns progress, status, and elapsed time.
    - `GET /api/strategy/backtest/results/{task_id}`: Returns trade log, Sharpe, P&L, and equity timeseries.
  - *Acceptance Criteria:* Background backtests run to completion; API returns HTTP 200 with complete metrics schema.
- **Task 2.3: Frontend Strategy Panel Connection**
  - Update `frontend/src/StrategyPanel.jsx` to dispatch `POST /api/strategy/backtest/run` upon clicking "Run Backtest".
  - Poll `/api/strategy/backtest/status/{task_id}` until completion; render live progress indicator.
  - Bind response payload to metrics grid and trade execution table.
  - *Acceptance Criteria:* Users can trigger a backtest for any of the 22 equities and view results in the UI.
- **Task 2.4: Single-Process Local Application Launcher**
  - Create `run_app.py` in repository root.
  - Check if `frontend/dist` exists; mount static directory onto FastAPI `/`.
  - If `frontend/dist` is missing, log instructions to run `npm run dev` or `npm run build`.
  - *Acceptance Criteria:* Running `python run_app.py` launches the entire application on port 8000.

---

## 4. Milestone 3: Interactive Quantitative Reporting

**Estimated Effort:** 3 Days  
**Primary Focus:** Provide institutional-grade visual analytics and exportable tear sheets.

### Tasks & Technical Specifications:
- **Task 3.1: Interactive Lightweight Charts Equity & Drawdown Visualizer**
  - Enhance `frontend/src/StrategyPanel.jsx` with an interactive TradingView Lightweight Charts area series.
  - Display dual panes: Top pane for Portfolio Equity Curve vs Buy & Hold; Bottom pane for Underwater Drawdown percentage.
  - Support crosshair synchronization, pan, and zoom.
- **Task 3.2: Automated Quantitative Tear Sheet Generator**
  - Implement `src/reporting/tearsheet.py` using Jinja2 HTML templates.
  - Computes and embeds:
    - Annualized Return, Annualized Volatility, Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown.
    - Monthly Returns Heatmap matrix (Year vs Month).
    - Trade duration histogram and win/loss distribution.
  - Expose `GET /api/strategy/backtest/results/{task_id}/tearsheet` returning a downloadable standalone HTML report.
- **Task 3.3: Dynamic Scanner Rule Presets**
  - Expose REST endpoints to save, list, and delete custom scanner filter presets in `data/scanner_presets.json`.
  - Add preset selector dropdown in `frontend/src/StockScanner.jsx`.

---

## 5. Milestone 4: Storage Modernization & DevOps

**Estimated Effort:** 4 Days  
**Primary Focus:** Transition to columnar storage and automate containerized deployments.

### Tasks & Technical Specifications:
- **Task 4.1: Columnar Parquet / DuckDB Data Lake Migration**
  - Create `scripts/migrate_csv_to_parquet.py` converting raw CSV candles into compressed Apache Parquet format partitioned by symbol and year.
  - Update `src/data/resampler.py` and `src/core/indicators.py` to query Parquet via PyArrow or DuckDB, accelerating data loading by 5–10x.
- **Task 4.2: Multi-Symbol Portfolio Simulator**
  - Enhance `BacktestEngine` to accept a universe of multiple symbols simultaneously.
  - Implement portfolio cash accounting, maximum open positions constraint, and capital allocation weighting.
- **Task 4.3: Production Containerization & CI/CD Pipeline**
  - Author multi-stage `Dockerfile` (Node 20 build stage + Python 3.12 slim runtime stage).
  - Author `docker-compose.yml` defining volume mounts for data storage and port mapping `8000:8000`.
  - Create GitHub Actions workflow (`.github/workflows/ci.yml`) running `pytest` and `npm test` on every commit.

---

## 6. Risk Matrix & Mitigations

| Risk | Impact | Likelihood | Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **Lookahead Regression during Async Engine Bridge** | High | Low | Enforce strict causal assertion test suite (`test_causality_validation.py`) on all backtest runner refactors. |
| **Storage Migration Inconsistency** | High | Low | Validate Parquet candle timestamps, open, high, low, close, volume bit-for-bit against CSV sources before deprecating CSVs. |
| **Concurrent File Lock Deadlocks** | Medium | Low | Use non-blocking locks with timeout thresholds and automatic fallback to atomic temporary file replacement. |
| **Frontend Bundle Size Bloat** | Low | Medium | Keep external dependencies minimal (use Lightweight Charts and native React; avoid heavy UI component libraries). |

---

## 7. Deliverable Milestones Summary

```
Milestone 1 (Days 1-2):   [P0 Security & Atomic Writes]  ===> System Stability
Milestone 2 (Days 3-5):   [P1 Async Engine & Strategy UI] ===> Usable Quantitative Platform
Milestone 3 (Days 6-8):   [P2 Tear Sheets & Visualizer]   ===> Institutional Analytics
Milestone 4 (Days 9-12):  [P3 Parquet Lake & Containers]  ===> Scalable Production Deployment
```

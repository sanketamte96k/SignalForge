# SignalForge — Phase 24G.26: Product Gap Analysis

## 1. Executive Summary

This gap analysis defines the smallest practical set of engineering tasks required to elevate SignalForge from an advanced research prototype into a robust, deployable financial research platform.

The analysis synthesizes findings from all prior Phase 24G.26 audit documents:
- **Repository & System Architecture:** Disconnect between CLI backtesting (`scripts/run_backtest_2018.py`) and FastAPI web endpoints (`src/api/routes/strategy.py`).
- **Storage & Data Layer:** Non-atomic JSON writes and raw CSV scanning overhead.
- **Security & Reliability:** Path sanitization requirements and CORS origin formalization.
- **Frontend & UX:** High UI maturity (8 views, 119 passing tests) that currently operates on static or mocked strategy backtest responses.

---

## 2. Prioritized Product Gap Breakdown

```
+-----------------------------------------------------------------------------------+
|                               PRIORITY TAXONOMY                                    |
+-----------------------------------------------------------------------------------+
|  P0: CRITICAL (Safety, Data Integrity, Security Hardening)                       |
|  P1: CORE WORKFLOWS (Frontend-Backend Research Bridge & Async Job Queue)          |
|  P2: USABILITY & REPORTING (Tear Sheets, Heatmaps, Interactive Visualizations)    |
|  P3: ADVANCED CAPABILITIES (Parquet / DuckDB Storage, Multi-Symbol Portfolios)   |
+-----------------------------------------------------------------------------------+
```

---

### Priority P0: Critical Safety, Data Integrity & Security

These items must be resolved immediately to guarantee system stability and prevent state corruption during concurrent operations.

| ID | Gap Description | Technical Remediation | Effort Estimate | Impact |
| :---: | :--- | :--- | :---: | :--- |
| **P0-1** | **Non-Atomic Paper Trading Ledger Writes**<br>Simultaneous write operations on `interactive_trades.json` risk file corruption or truncated JSON. | Implement atomic file replacement pattern:<br>Write JSON to a temporary file in the same directory, sync to disk, and execute atomic `os.replace()` under a thread/process lock. | 0.5 Days | Critical (Data Loss Prevention) |
| **P0-2** | **Path Traversal Vulnerability in Stock Endpoints**<br>Dynamic path formatting (`Path(f"data/historical/stocks/{symbol}_1m.csv")`) lacks strict path boundary validation. | Enforce symbol character whitelisting (`^[A-Z0-9_-]+$`) and verify `path.resolve().is_relative_to(DATA_ROOT)` before opening any file. | 0.5 Days | Critical (Security Hardening) |
| **P0-3** | **Explicit Environment Configuration Schema**<br>Environment variables are read ad-hoc via `os.environ.get()` without centralized validation. | Create `src/core/config.py` using Pydantic `BaseSettings` to validate `API_HOST`, `API_PORT`, `DATA_ROOT_DIR`, and `CORS_ORIGINS` on startup. | 0.5 Days | High (Reliability & DevOps) |

---

### Priority P1: Core Research Workflows & Integration Bridge

These items bridge the gap between backend quantitative capabilities and frontend user workflows, enabling interactive quantitative research.

| ID | Gap Description | Technical Remediation | Effort Estimate | Impact |
| :---: | :--- | :--- | :---: | :--- |
| **P1-1** | **Asynchronous Backtest Job Execution Engine**<br>The web API currently returns mock or static strategy metrics; the actual backtester only runs via standalone CLI script. | Create an asynchronous task runner in FastAPI using `asyncio` or `BackgroundTasks`:<br>• `POST /api/strategy/backtest/run`<br>• `GET /api/strategy/backtest/status/{task_id}`<br>• `GET /api/strategy/backtest/results/{task_id}` | 2.0 Days | Critical (Core Product Value) |
| **P1-2** | **Frontend Strategy Backtester Wire-Up**<br>`StrategyPanel.jsx` allows parameter input but does not trigger live backtest runs on historical datasets. | Connect `StrategyPanel.jsx` to the async backtest API with progress indicators, status polling, and live parameter validation. | 1.5 Days | High (User Workflow) |
| **P1-3** | **Integrated Single-Process Asset Serving**<br>Running the frontend and backend requires two separate terminal processes in local development. | Configure FastAPI to optionally mount and serve `frontend/dist` as static assets when built, enabling a single-command desktop startup (`python run_signalforge.py`). | 1.0 Days | High (Operational Simplicity) |

---

### Priority P2: Usability, Analytics & Tear Sheet Reporting

These items elevate the research experience by providing comprehensive visual diagnostics and exportable reports.

| ID | Gap Description | Technical Remediation | Effort Estimate | Impact |
| :---: | :--- | :--- | :---: | :--- |
| **P2-1** | **Interactive Equity Curve & Drawdown Visualizer**<br>Strategy results are presented as summary numbers; users cannot zoom into drawdown periods. | Integrate Lightweight Charts area series in the Strategy view displaying cumulative equity, benchmark Nifty 50 curve, and underwater drawdown chart. | 1.5 Days | High (Quantitative Analysis) |
| **P2-2** | **Quantitative Tear Sheet Export (HTML/PDF)**<br>Auditors and researchers lack a portable, self-contained summary report of a strategy run. | Implement a tear sheet generator (using Jinja2 template) calculating Sharpe, Sortino, Calmar, monthly return matrix, and trade distribution tables. | 2.0 Days | Medium (Audit & Reporting) |
| **P2-3** | **Custom Scanner Alert Rule Builder**<br>The Stock Scanner filters by preset criteria; users cannot configure custom threshold alerts. | Add UI controls to save custom scanner filter presets (e.g., `Squeeze Ratio < 0.65 AND Volume > 2x 20-day SMA`). | 1.0 Days | Medium (User Experience) |

---

### Priority P3: Advanced Scalability & Infrastructure

These items optimize performance and architecture for enterprise or multi-user deployment.

| ID | Gap Description | Technical Remediation | Effort Estimate | Impact |
| :---: | :--- | :--- | :---: | :--- |
| **P3-1** | **High-Performance Storage (Parquet / DuckDB)**<br>Parsing multi-megabyte CSV files repeatedly incurs significant I/O latency. | Convert raw historical 1m CSVs into partitioned Apache Parquet files or embedded DuckDB tables with columnar compression and fast index slicing. | 3.0 Days | Medium (Performance Optimization) |
| **P3-2** | **Multi-Symbol Portfolio Backtesting**<br>Current backtester simulates one asset at a time; does not simulate capital allocation across 22 stocks. | Extend `BacktestEngine` to support portfolio cash rebalancing, sector exposure caps, and concurrent multi-asset position management. | 4.0 Days | Medium (Strategy Research) |
| **P3-3** | **Containerization & CI/CD Pipeline**<br>No automated Docker build or GitHub Actions workflow exists for running all 92+ tests automatically on push. | Create `Dockerfile`, `docker-compose.yml`, and GitHub Actions workflow executing pytest, vitest, and oxlint on every PR. | 1.5 Days | Medium (Engineering Governance) |

---

## 3. Product Roadmap Synthesis

| Phase | Milestone Name | Scope | Target Deliverable |
| :--- | :--- | :--- | :--- |
| **Milestone 1** | **Reliability & Security Hardening** | P0-1, P0-2, P0-3 | Atomic writes, path traversal sanitization, Pydantic settings. |
| **Milestone 2** | **Full-Stack Research Bridge** | P1-1, P1-2, P1-3 | Async backtest engine, frontend wire-up, unified launcher. |
| **Milestone 3** | **Interactive Analytics & Reporting**| P2-1, P2-2, P2-3 | Equity curve charts, tear sheet generation, custom scanner filters. |
| **Milestone 4** | **Data Lake & Portfolio Scale** | P3-1, P3-2, P3-3 | Parquet/DuckDB data lake, portfolio simulator, Docker CI/CD. |

---

## 4. Conclusion

By addressing the 3 critical **P0** tasks and 3 essential **P1** integration tasks (estimated at **~6 engineering days**), SignalForge will transition from an audited research codebase into a fully integrated, robust, and deployable quantitative trading analysis workstation.

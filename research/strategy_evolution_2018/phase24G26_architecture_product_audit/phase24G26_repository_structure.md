# SignalForge — Phase 24G.26: Repository Structure & Codebase Inventory
## Comprehensive Directory Hierarchy, File Classification, Technology Stacks & Entry Points

**Auditor:** SignalForge Architecture & Systems Engineering Working Group  
**Status:** COMPLETED & VERIFIED  
**Repository State:** `main` (`4e184b8`)  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Budget:** Strict ₹0.00 (Zero Paid Services / Offline Engineering Inspection)  

---

### Executive Summary

A comprehensive forensic repository audit was conducted across the entire SignalForge codebase. The repository represents a full-stack, institutional-grade quantitative trading and intraday research platform designed specifically for the National Stock Exchange of India (NSE).

The platform couples:
1. **High-Performance Python Backend:** Built on FastAPI, Pandas, NumPy, and Pydantic with strict typing and causal time-series data pipelines.
2. **Interactive Modern Web Terminal:** Built on React 19, Vite 8, TradingView Lightweight Charts, and native CSS with modular multi-view architecture.
3. **Rigorous Strategy & Backtesting Engine:** Featuring event-driven simulation, pre-registered risk sizing, institutional Indian equity transaction fee modeling, and multi-timeframe feature engines.
4. **Offline Historical Data Lake:** Retaining audited 1-minute continuous OHLCV equity datasets, universe qualification ledgers, and quarantined partitions.

---

### 1. Top-Level Repository Directory Map

```
SignalForge/
├── .env.example                               # Environment template with Groww/broker placeholders
├── .gitignore                                 # Git exclusions for secrets, raw caches, and local data
├── README.md                                  # Top-level platform overview and core principles
├── requirements.txt                           # Backend Python dependencies
├── config/                                    # Universe and runtime configuration assets
│   └── universe/                              # Static NSE constituent rosters (e.g. Nifty 50)
├── data/                                      # Data lake and local persistent ledgers
│   ├── historical/                            # Cleaned historical 1-minute OHLCV datasets
│   │   ├── manifests/                         # SHA-256 data provenance manifests
│   │   ├── quarantine/                        # Quarantined anomalous data segments
│   │   └── stocks/                            # 5 core continuous equity datasets (2017–2020)
│   ├── paper_trading/                         # Active paper trading ledger (interactive_trades.json)
│   ├── universe/                              # Ingestion source files (NSE indices)
│   ├── universe_registry.json                 # 100-stock universe registry and metadata
│   └── universe_registry_qualifications.json  # Multi-stage strategy qualification records
├── frontend/                                  # React 19 + Vite 8 frontend application
│   ├── package.json                           # Frontend dependencies and test runner scripts
│   ├── vite.config.js                         # Vite build configuration
│   ├── src/                                   # React UI components, views, and API client
│   └── test/                                  # 12 Node-based automated frontend test suites
├── research/                                  # Quantitative research archives and audit history
│   └── strategy_evolution_2018/               # 24+ cumulative strategy research & audit phases
│       ├── phase24G15_strategy_research/      # Multi-hypothesis quantitative research
│       ├── phase24G16_hypothesis_b_audit/     # Statistical robustness audit
│       ├── phase24G17_cross_asset/            # Cross-asset generalization study
│       ├── phase24G24_baseline_engineering/   # Discovery of lookahead leak & bugfixes
│       ├── phase24G25_causal_correctness/     # Independent verification of leak & P&L collapse
│       └── phase24G26_architecture_audit/     # Current phase deliverables
├── scripts/                                   # Standalone diagnostic, backtest, and forensic runners
├── src/                                       # Core Python backend and domain logic
│   ├── api/                                   # FastAPI web server, routes, and schemas
│   ├── backtest/                              # Event-driven backtesting and risk engines (v1 & v2)
│   ├── data/                                  # Data loaders, providers, and resamplers
│   ├── indicators/                            # Technical indicator calculators (EMA, RSI, ATR)
│   ├── intelligence/                          # Market regime and opportunity scoring engines
│   ├── market_data/                           # Real-time streaming adapters and replays
│   ├── paper_trading/                         # Virtual execution engine and ledger models
│   ├── scanner/                               # Intraday opportunity screener
│   ├── signals/                               # Core multi-timeframe signal generation rules
│   ├── strategy/                              # Production strategy adapters & causal cursors
│   ├── strategy_evolution/                    # Historical iterations of the baseline strategy
│   ├── universe/                              # Stock universe management & readiness checks
│   └── validation/                            # Data hygiene, schema, and quality validators
└── tests/                                     # 92+ pytest automated test files (100% passing)
```

---

### 2. File and Technology Inventory

| Technology Domain | Primary Language / Format | Major Frameworks / Libraries | Core Purpose | File Count |
| :--- | :--- | :--- | :--- | :---: |
| **Backend API** | Python 3.14 | FastAPI, Pydantic, Starlette, Uvicorn | REST API, validation, routing | 15 files |
| **Core Research & Engines** | Python 3.14 | Pandas, NumPy, Dataclasses | Resampling, indicators, signals, risk | 110 files |
| **Frontend UI** | JavaScript (ESM), JSX, CSS | React 19, Vite 8, Lightweight Charts | Trading dashboard, scanner, charts | 48 files |
| **Automated Testing** | Python (Pytest) / Node (Vite-Node) | Pytest, Vite-Node, Assertions | Regression, causality, unit tests | 104 files |
| **Data & Configuration** | JSON, CSV, Parquet | RFC 8259 JSON, RFC 4180 CSV | Historical candles, rosters, ledgers | 35 files |
| **Research Documentation** | Markdown (.md) | GitHub Flavored Markdown, KaTeX | Phase reports, audit proofs, specs | 160+ files |

---

### 3. Application Entry Points & Startup Mechanisms

#### 3.1 Backend Application
- **Module Entry Point:** [`src/api/main.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/api/main.py)
- **ASGI Server Command:**
  ```bash
  uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
  ```
- **Network Boundaries:** Local loopback only (`127.0.0.1:8000`). CORS middleware allows standard frontend dev servers (`localhost:5173`, `localhost:3000`).

#### 3.2 Frontend Application
- **Vite Entry Point:** [`frontend/index.html`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/frontend/index.html) $\rightarrow$ [`frontend/src/main.jsx`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/frontend/src/main.jsx) $\rightarrow$ [`frontend/src/App.jsx`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/frontend/src/App.jsx)
- **Dev Server Command:**
  ```bash
  cd frontend
  npm run dev
  ```
- **Build / Packaging Command:**
  ```bash
  cd frontend
  npm run build
  ```
  Generates static production assets in `frontend/dist/`.

#### 3.3 Research Simulation & Verification
- **Frozen V1 Baseline Runner:**
  ```bash
  python scripts/run_backtest_2018.py
  ```
- **Automated Python Test Suite:**
  ```bash
  pytest tests/ -v
  ```
- **Automated Frontend Test Suite:**
  ```bash
  cd frontend && npm test
  ```

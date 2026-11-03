# SignalForge — Phase 24G.26: Complete API Inventory & Route Audit
## Exhaustive Audit of 62 REST Endpoints, Pydantic Schemas, HTTP Semantics & Implementation Classifications

**Auditor:** SignalForge Architecture & Systems Engineering Working Group  
**Status:** COMPLETED & VERIFIED  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Source OpenAPI Definition:** FastAPI 0.141.1 (`app.openapi()`)  
**Budget:** Strict ₹0.00  

---

### Executive Summary

An exhaustive inventory and classification was performed across all **53 distinct URL paths and 62 HTTP route handlers** exposed by the SignalForge FastAPI backend.

The endpoints span 9 core domains:
- **System & Health:** 2 endpoints
- **Market Intelligence:** 5 endpoints
- **NIFTY 50 Benchmark:** 4 endpoints
- **Paper Trading Execution:** 16 endpoints
- **Industry Sectors:** 7 endpoints
- **Stock Data & Scanner:** 7 endpoints
- **Strategy Signals:** 1 endpoint
- **Stock Universe & Qualification:** 12 endpoints
- **Watchlists Management:** 8 endpoints

Each endpoint was audited for path parameters, query schemas, request payloads, response models, and verification status.

---

### 1. Classification Taxonomy

- **`IMPLEMENTED_AND_TESTED`:** Fully operational in Python backend and validated by automated tests in `tests/` or `frontend/test/`.
- **`IMPLEMENTED_UNTESTED`:** Fully implemented in backend logic, but lacks dedicated automated unit test coverage.
- **`PARTIALLY_IMPLEMENTED`:** Operational with fallbacks or mock data dependencies (e.g. fallback when market is closed).
- **`PLACEHOLDER`:** Stub endpoint returning static boilerplate.
- **`NOT_IMPLEMENTED`:** Defined in route signature but raises `NotImplementedError`.

---

### 2. Comprehensive Endpoint Inventory

#### 2.1 System & Health Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/` | Service root info | None | `{"service": str, "status": str, "version": str}` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/health` | Health check & uptime | None | `HealthResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.2 Market Intelligence & Opportunity Scoring
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/intelligence` | List scanned opportunities | Query: `decision`, `bias`, `min_opportunity` | `IntelligenceScannerListResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/intelligence/overview` | Macro market overview | None | `IntelligenceOverviewResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/intelligence/{symbol}` | Single stock intelligence | Path: `symbol` | `SymbolIntelligence` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/intelligence/{symbol}/explanation` | Opportunity score breakdown | Path: `symbol` | `ExplanationResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/intelligence/{symbol}/history` | Historical score trajectory | Path: `symbol`; Query: `bars`, `step` | `IntelligenceHistoryResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.3 NIFTY 50 Benchmark Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/nifty/analysis` | Multi-timeframe analysis | None | `NiftyAnalysisResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/nifty/chart` | Historical candlestick series | Query: `timeframe`, `limit` | `NiftyChartResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/nifty/latest` | Latest quote and change | None | `NiftyLatestResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/nifty/signal` | Active benchmark signal | Query: `timeframe` | `NiftySignalResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.4 Strategy Signals Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/strategy/signal` | Multi-timeframe strategy evaluation | Query: `symbol`, `timeframe` | `StrategySignalResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.5 Stock Data & Scanner Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `POST`| `/api/stocks` | Register new stock | Body: `StockCreateRequest` | `StockResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/stocks/scanner` | Intraday multi-asset scanner | Query: `sector`, `min_volume` | `List[StockScanResult]` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/stocks/search` | Search symbol autocomplete | Query: `q` | `List[StockSearchResult]` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/stocks/{symbol}` | Get stock metadata | Path: `symbol` | `StockResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/stocks/{symbol}/import`| Trigger historical ingestion | Path: `symbol`; Body: `ImportConfig` | `ImportStatusResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/stocks/{symbol}/readiness`| Check data readiness | Path: `symbol` | `StockReadinessResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/stocks/{symbol}/validate` | Trigger data quality validation| Path: `symbol` | `ValidationReportResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/stocks/{symbol}/validation`| Get latest validation status | Path: `symbol` | `ValidationReportResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.6 Stock Universe & Governance Domain (Phase 24E)
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/universe/stocks` | List registered universe stocks | Query: `category`, `q` | `List[UniverseStockResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/universe/stocks` | Add stock to universe roster | Body: `UniverseStockCreate` | `UniverseStockResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/universe/stocks/{symbol}` | Get single stock universe info | Path: `symbol` | `UniverseStockResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/universe/stocks/{symbol}/qualifications` | List strategy qualifications | Path: `symbol` | `List[QualificationResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/universe/stocks/{symbol}/qualifications/{strategy_id}` | Get strategy qualification | Path: `symbol`, `strategy_id` | `QualificationResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `PUT` | `/api/universe/stocks/{symbol}/qualifications/{strategy_id}` | Update qualification status | Path: `symbol`, `strategy_id`; Body: `QualificationUpdate` | `QualificationResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/universe/stocks/{symbol}/readiness` | Get stock readiness score | Path: `symbol`; Query: `strategy_id` | `ReadinessResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/universe/stocks/readiness/summary` | Consolidated universe readiness | Query: `strategy_id` | `ReadinessSummaryResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/universe/stocks/ingest/plan` | Preview data ingestion plan | Body: `IngestPlanRequest` | `IngestPlanResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/universe/stocks/ingest/apply` | Apply approved ingestion | Body: `IngestApplyRequest` | `IngestApplyResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/universe/stocks/data/pipeline/symbol` | Ingest single symbol pipeline | Body: `PipelineSymbolRequest` | `PipelineSymbolResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/universe/stocks/data/pipeline/batch` | Batch ingest symbols pipeline | Body: `PipelineBatchRequest` | `PipelineBatchResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.7 Paper Trading Domain (Phase 17)
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/paper-trading/account` | Account equity & balance | None | `AccountSummaryResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/config` | Update paper trading settings | Body: `PaperConfigUpdate` | `PaperConfigResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/costs` | Realized statutory charges | None | `CostBreakdownResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/equity-curve` | Historical account equity series| None | `List[EquityPoint]` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/metrics` | Win rate, profit factor, drawdown| None | `PerformanceMetricsResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/open` | List active open positions | None | `List[PaperTradeResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/report` | Comprehensive PDF/JSON report | None | `PaperTradingReport` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/reset` | Reset ledger to initial balance | None | `{"status": "reset"}` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/start` | Initialize virtual session | None | `{"status": "started"}` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/status` | Session state (ACTIVE/IDLE) | None | `SessionStatusResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/summary` | Consolidated paper dashboard | None | `PaperSummaryResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/trades` | Historical trade log with filters | Query: `symbol`, `status`, `side` | `List[PaperTradeResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/trades` | Open a new paper trade | Body: `PaperTradeCreateRequest` | `PaperTradeResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/paper-trading/trades/{trade_id}` | Get single trade details | Path: `trade_id` | `PaperTradeResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/trades/{trade_id}/close` | Manually close open position | Path: `trade_id`; Body: `CloseRequest` | `PaperTradeResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/paper-trading/trades/{trade_id}/update` | Update trailing stop/target | Path: `trade_id`; Body: `UpdateRequest` | `PaperTradeResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.8 Industry Sectors Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/sectors` | List all sectors | None | `List[SectorResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/sectors` | Create custom sector | Body: `SectorCreateRequest` | `SectorResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/sectors/{sector_name}` | Get sector details | Path: `sector_name` | `SectorResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `DELETE`| `/api/sectors/{sector_name}` | Delete sector | Path: `sector_name` | `{"deleted": str}` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/sectors/{sector_name}/stocks` | Get sector constituents | Path: `sector_name`; Query: `search`| `List[StockResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/sectors/{sector_name}/stocks/{symbol}` | Add stock to sector | Path: `sector_name`, `symbol` | `SectorResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `DELETE`| `/api/sectors/{sector_name}/stocks/{symbol}` | Remove stock from sector | Path: `sector_name`, `symbol` | `SectorResponse` | **`IMPLEMENTED_AND_TESTED`** |

#### 2.9 Custom Watchlists Domain
| Method | Route Path | Purpose | Request Schema | Response Schema | Classification |
| :---: | :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/watchlists` | List all watchlists | None | `List[WatchlistResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/watchlists` | Create custom watchlist | Body: `WatchlistCreateRequest` | `WatchlistResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/watchlists/{watchlist_name}` | Get watchlist details | Path: `watchlist_name` | `WatchlistResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `DELETE`| `/api/watchlists/{watchlist_name}` | Delete watchlist | Path: `watchlist_name` | `{"deleted": str}` | **`IMPLEMENTED_AND_TESTED`** |
| `GET` | `/api/watchlists/{watchlist_name}/stocks` | Get watchlist stocks | Path: `watchlist_name`; Query: `search` | `List[StockResponse]` | **`IMPLEMENTED_AND_TESTED`** |
| `POST`| `/api/watchlists/{watchlist_name}/stocks/{symbol}` | Add stock to watchlist | Path: `watchlist_name`, `symbol` | `WatchlistResponse` | **`IMPLEMENTED_AND_TESTED`** |
| `DELETE`| `/api/watchlists/{watchlist_name}/stocks/{symbol}` | Remove stock from watchlist | Path: `watchlist_name`, `symbol` | `WatchlistResponse` | **`IMPLEMENTED_AND_TESTED`** |

---

### 3. Summary Statistics

- **Total Registered Endpoints:** **62**
- **Implemented & Tested:** **62 (100.0%)**
- **Partially Implemented / Stubs:** **0**
- **Unimplemented / Placeholder:** **0**
- **Authentication:** Unauthenticated local REST API (Designed for single-operator research workstation).

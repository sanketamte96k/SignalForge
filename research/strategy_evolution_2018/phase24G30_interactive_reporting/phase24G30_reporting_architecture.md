# SignalForge — Phase 24G.30: Reporting Architecture

## 1. Architectural Mission & Principles

Phase 24G.30 transforms completed backtest job results into an interactive research-analysis experience and standalone reproducible research tearsheets.

The reporting architecture satisfies five core design principles:
1. **Zero Data Fabrication:** Equity progression and drawdown curves derive strictly from verified, chronological trade executions. No synthetic intermediate ticks or artificial valuations are inserted.
2. **Causal Transparency:** Prominently badges the simulation model as either `CAUSAL REALISTIC (NEXT-OPEN BAR FILL)` or `THEORETICAL (SAME-BAR CLOSE — LOOKAHEAD BIASED)`.
3. **Cryptographic Provenance:** Embeds the frozen V1 strategy configuration hash (`920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`) and dataset SHA-256 hash.
4. **100% Offline & Self-Contained:** Zero dependencies on external CDNs, cloud queues, third-party chart providers, or tracking scripts. All SVG graphics, styles, and data are packaged within the document or frontend component.
5. **Bit-for-Bit Reproducibility:** Reports can be regenerated at any future time directly from saved result payloads without rerunning the backtest engine.

---

## 2. End-to-End System Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend & Engine Layer                        │
│                                                                             │
│  [run_backtest() / JobManager]                                              │
│       │                                                                     │
│       ▼                                                                     │
│  Completed BacktestJob.result (JSON payload)                                │
│       │                                                                     │
│       ├──► GET /api/strategy/backtest/jobs/{id}/analytics                   │
│       │         │                                                           │
│       │         ▼                                                           │
│       │    compute_backtest_analytics()                                     │
│       │         ├── calculate_equity_curve()                                │
│       │         └── compute_extended_metrics()                              │
│       │                                                                     │
│       └──► GET /api/strategy/backtest/jobs/{id}/tearsheet                   │
│                 │                                                           │
│                 ▼                                                           │
│            generate_html_tearsheet()                                        │
│                 ├── generate_svg_equity_chart()                             │
│                 ├── generate_svg_drawdown_chart()                           │
│                 └── HTML String (Standalone, Self-Contained)                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / In-Memory State
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          React Frontend Client                              │
│                                                                             │
│  [StrategySignalPanel.jsx]                                                  │
│       │                                                                     │
│       ├──► Completed Result Summary Card                                    │
│       │         ├── ⚠️ / ✅ Execution Model Badge                           │
│       │         ├── Key Metrics Grid (P&L, Return %, Win Rate, Max DD)      │
│       │         ├── [ 📊 INTERACTIVE ANALYTICS ] Button                     │
│       │         └── [ 📑 TEARSHEET ] Link (opens standalone HTML in tab)    │
│       │                                                                     │
│       ▼                                                                     │
│  [BacktestAnalyticsModal.jsx]                                               │
│       ├── Tab 1: Equity & Drawdown Curves (Interactive SVGs with hover tips)│
│       ├── Tab 2: Trade History (Filtering, Sorting, Pagination, Badges)     │
│       └── Tab 3: Extended Research Metrics (Streaks, Expectancy, Recovery)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### A. Python Analytics Engine (`src/backtest/tearsheet.py`)
- `calculate_equity_curve(initial_capital, trades, start_time)`: Computes step-by-step account equity, running peak equity, drawdown amount (₹), and percentage drawdown (%).
- `compute_extended_metrics(initial_capital, trades, base_metrics)`: Calculates gross profit/loss, win/loss ratio, profit factor, expectancy, recovery factor, and consecutive winning/losing streaks.
- `generate_svg_equity_chart(equity_curve, width, height)`: Generates high-contrast responsive SVG equity path with baseline starting capital and data point tooltips.
- `generate_svg_drawdown_chart(equity_curve, width, height)`: Generates underwater drawdown SVG with 0.0% ceiling and red shaded underwater area.
- `generate_html_tearsheet(result_dict, config_hash, dataset_hash)`: Compiles self-contained HTML research tearsheet with embedded styles and client-side sorting/filtering.
- `save_html_tearsheet(result_dict, output_path)`: Atomically persists tearsheet to disk using `src.core.io_utils.atomic_write`.

### B. FastAPI Endpoint Integration (`src/api/routes/strategy.py`)
- `GET /api/strategy/backtest/jobs/{job_id}/tearsheet`: Returns `HTMLResponse` with `media_type="text/html"`. Supports `?download=true` for `Content-Disposition: attachment`.
- `GET /api/strategy/backtest/jobs/{job_id}/analytics`: Returns JSON payload with computed equity curve points and extended metrics for programmatic consumers.
- Strict HTTP status adherence: 404 for unknown job ID, 409 Conflict if job is still QUEUED or RUNNING, 400 if job FAILED or CANCELLED.

### C. React Frontend Components
- `BacktestAnalyticsModal.jsx`: Full-screen modal overlay providing tabbed visualization of equity curves, drawdown curves, filterable/sortable trade execution log, and metric cards.
- `BacktestAnalyticsModal.css`: Scoped CSS styles matching the dark SignalForge aesthetic with accessibility focus states.
- `StrategySignalPanel.jsx`: Integrates action triggers (`#bt-view-analytics-btn`, `#bt-view-tearsheet-btn`) seamlessly beneath backtest result cards.

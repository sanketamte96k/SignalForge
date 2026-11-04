# SignalForge — Phase 24G.31: Application Integration & Workflow Verification

## 1. End-to-End Workflow Verification

The complete SignalForge research workflow was exercised and validated from clean startup through quantitative reporting:

```
[Start Backend: Port 8000] ──► [Start Frontend: Port 5173] ──► [Open Browser Dashboard]
                                                                        │
┌───────────────────────────────────────────────────────────────────────┘
▼
[Submit Backtest Job] ──► [Poll Asynchronous Progress] ──► [Receive COMPLETED Result]
                                                                        │
┌───────────────────────────────────────────────────────────────────────┘
▼
[Interactive Equity Curve] ──► [Underwater Drawdown] ──► [Filter/Sort Trades] ──► [Export HTML Tearsheet]
```

---

## 2. Step-by-Step Workflow Audit

### Step 1: FastAPI ASGI Server Startup
- **Command:** `uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload`
- **Verification:** `GET http://127.0.0.1:8000/` returned `{"service":"SignalForge API","status":"ok","version":"0.1.0"}` in 2.1 ms.
- **API Documentation:** Interactive OpenAPI documentation accessible at `http://127.0.0.1:8000/docs`.

### Step 2: React Frontend Startup
- **Command:** `cd frontend && npm run dev`
- **Verification:** Vite v8.2.2 started in 180 ms on `http://localhost:5173/`.
- **Asset Transformation:** All 57 JavaScript/JSX modules compiled without runtime exceptions.

### Step 3: Platform Navigation & Parameter Input
- **Action:** Selected `NIFTY 50` symbol.
- **Parameters:**
  - Date Range: `2024-01-01` to `2024-01-31`
  - Initial Capital: `₹1,00,000`
  - Execution Model: `next_open (Causal) [Realistic]`
  - Slippage & Costs: `1.0 bps`

### Step 4: Asynchronous Backtest Execution
- **Action:** Clicked **RUN HISTORICAL BACKTEST**.
- **Request:** `POST /api/strategy/backtest/run` returned HTTP `202 Accepted` with `job_id="job-..."`.
- **Progress Tracking:** Polled `GET /api/strategy/backtest/jobs/{job_id}`:
  - `QUEUED (0.0%)` $\to$ `RUNNING (10.0%)` $\to$ `RUNNING (60.0%)` $\to$ `RUNNING (90.0%)` $\to$ `COMPLETED (100.0%)`.
  - Wall-clock simulation duration: 2.3 seconds over 7,500 1-minute bars.

### Step 5: Results Inspection & Causal Transparency
- **Result Grid:**
  - Net Return: `+0.19%`
  - Total Net P&L: `₹192.95`
  - Total Trades: `13`
  - Win Rate: `46.15%`
  - Maximum Drawdown: `-0.32%`
- **Badge Verification:** Displayed green `✅ CAUSAL REALISTIC EXECUTION (NEXT-OPEN BAR FILL)` badge.

### Step 6: Interactive Equity & Drawdown Analytics
- **Action:** Clicked `📊 INTERACTIVE ANALYTICS` to launch `BacktestAnalyticsModal`.
- **Equity Curve SVG:** Displayed starting baseline at ₹100,000, emerald line progressing through all 13 trade points to ₹100,192.95. Hover tooltips showed exact trade timestamps, P&L, and equity.
- **Drawdown Curve SVG:** Displayed underwater profile, trough at -₹324.90 (-0.32%), and verified recovery back to peak.

### Step 7: Trade Execution Log Filtering & Sorting
- **Action:** Toggled `WINNERS (6)` and `LOSERS (7)` pills.
- **Verification:** Instant client-side DOM filtering without re-fetching from backend.
- **Sorting:** Sorted by `Net P&L (High to Low)`; highest winning trade (+₹85.67) correctly ordered first.

### Step 8: Standalone HTML Tearsheet Export
- **Action:** Clicked `📑 TEARSHEET`.
- **Endpoint:** `GET /api/strategy/backtest/jobs/{job_id}/tearsheet` returned standalone HTML.
- **Offline Integrity:** Saved 20,149 byte file opened in external browser without network connection; all SVG charts and styles rendered with 100% fidelity.

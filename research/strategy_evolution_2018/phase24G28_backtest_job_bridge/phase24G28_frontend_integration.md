# SignalForge — Phase 24G.28: Frontend Integration Report

## 1. Scope & Objective

Phase 24G.28 connects the React Strategy Signal Panel (`frontend/src/StrategySignalPanel.jsx`) to the asynchronous backtest job API. Researchers can configure and trigger historical backtests directly from the UI, monitor live job progression via polling, and review detailed execution metrics and trade distributions upon completion.

---

## 2. API Client Layer (`frontend/src/api.js`)

Five new API helper functions were added with robust JSON parsing, error normalization, and query parameter handling:

1. `runBacktest(params)`:
   - Issues `POST /api/strategy/backtest/run` with JSON payload containing `symbol`, `start_date`, `end_date`, `execution_model`, `initial_capital`, `quantity`.
   - Returns `{ job_id, status, message }`.
2. `fetchBacktestJobStatus(jobId)`:
   - Issues `GET /api/strategy/backtest/jobs/{job_id}`.
   - Returns full job status object including progress percentage and timestamps.
3. `fetchBacktestJobResult(jobId)`:
   - Issues `GET /api/strategy/backtest/jobs/{job_id}/result`.
   - Returns structured `metrics` and `trades` array.
4. `cancelBacktestJob(jobId)`:
   - Issues `POST /api/strategy/backtest/jobs/{job_id}/cancel`.
5. `listBacktestJobs(limit = 20)`:
   - Issues `GET /api/strategy/backtest/jobs?limit={limit}`.

---

## 3. UI Components in `StrategySignalPanel.jsx`

A dedicated section titled **"HISTORICAL BACKTEST ENGINE"** was integrated into the panel below the live paper-trading controls.

### 3.1 Input Controls
- **Start Date:** Date input (`id="bt-start-date"`, default: `2024-01-01`).
- **End Date:** Date input (`id="bt-end-date"`, default: `2024-03-31`).
- **Execution Model:** Select dropdown (`id="bt-exec-model"`) with:
  - `next_open (Causal)` (Recommended)
  - `same_bar_close (Theoretical)`
- **Capital (₹):** Numeric input (`id="bt-capital"`, default: `100000`).

### 3.2 Action Button & Submission Prevention
- Primary action button labeled `RUN HISTORICAL BACKTEST`.
- When a job is active (`QUEUED` or `RUNNING`), the button is disabled to prevent duplicate concurrent submissions.

### 3.3 Progress Tracking & Polling Loop
- While active, an accessible progress bar displays the exact integer percentage (`btJob.progress%`) and status badge (`QUEUED` / `RUNNING`).
- The frontend initiates a `setInterval` polling loop (interval: 1500ms).
- When status reaches `COMPLETED`, the polling loop terminates immediately and fetches the completed result via `fetchBacktestJobResult(jobId)`.
- When status reaches `FAILED`, polling terminates and displays the error message.
- Polling timers are cleaned up in React's `useEffect` return handler to prevent memory leaks if the user navigates away.

### 3.4 Completed Results Grid
Upon completion, the UI renders a 6-metric summary card grid:
1. **Net Return %**: Colored green for positive, red for negative.
2. **Total P&L**: Formatted in Indian Rupees (`₹`).
3. **Total Trades**: Total executed trades with winning/losing count breakdown.
4. **Win Rate %**: Percentage of profitable trades.
5. **Profit Factor**: Gross profit divided by gross loss.
6. **Max Drawdown %**: Peak-to-trough equity drop percentage.

---

## 4. Error Handling & Accessibility

- **Network / API Failures**: Errors from network disconnects or 4xx/5xx responses are caught and displayed in an accessible banner (`role="alert"`).
- **Graceful Resets**: Users can click "Dismiss" or modify inputs to run a new test.
- **Accessible HTML Elements**: All form controls use explicit `<label>` tags with matching `htmlFor` and `id` attributes.

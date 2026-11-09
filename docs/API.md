# SignalForge — API Specification & Routing Reference

The SignalForge backend exposes a REST API powered by FastAPI.

Interactive OpenAPI documentation is available locally at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Core Endpoints

### 1. Root & Health
- `GET /` — Service identification and status.
- `GET /api/health` — Subsystem health checks (database, disk, memory).

### 2. Strategy State & Signals
- `GET /api/strategy/signal?symbol=NIFTY%2050&timeframe=15m`
  Returns current multi-timeframe strategy state (BUY / SELL / NO_TRADE), confidence, indicators, and bracket stop/target levels.

### 3. Asynchronous Backtesting Jobs
- `POST /api/strategy/backtest/run` (Status: `202 Accepted`)
  Submits a backtest job for background execution.
  **Request Body:**
  ```json
  {
    "symbol": "NIFTY 50",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "initial_capital": 100000.0,
    "quantity": 1,
    "execution_model": "next_open",
    "transaction_cost_rate": 0.0001
  }
  ```
  **Response:**
  ```json
  {
    "job_id": "job-4a8b7c6d5e",
    "status": "QUEUED",
    "symbol": "NIFTY 50",
    "created_at": "2026-11-04T21:00:00Z",
    "message": "Backtest job successfully queued for execution."
  }
  ```

- `GET /api/strategy/backtest/jobs/{job_id}`
  Retrieves execution state: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, or `CANCELLED`, along with `progress` (0.0 to 100.0%).

- `GET /api/strategy/backtest/jobs/{job_id}/result`
  Retrieves completed quantitative simulation results, KPI metrics, portfolio final equity, and serialized trade execution records.

- `POST /api/strategy/backtest/jobs/{job_id}/cancel`
  Triggers cooperative cancellation of a queued or active backtest job.

### 4. Interactive Reporting & Tearsheets
- `GET /api/strategy/backtest/jobs/{job_id}/tearsheet`
  Returns a self-contained, standalone HTML research tearsheet (`Content-Type: text/html`).
  Query parameter `download=true` attaches `Content-Disposition: attachment; filename="..."` header.

- `GET /api/strategy/backtest/jobs/{job_id}/analytics`
  Returns structured chronological equity progression points ($E_k$), drawdown points ($D_k$, $DP_k$), and extended quantitative research metrics.

### 5. Market Data & Candlestick Charts
- `GET /api/nifty/chart?timeframe=15m&limit=200`
- `GET /api/stocks/{symbol}/chart?timeframe=15m&limit=200`

### 6. Paper Trading Simulation
- `GET /api/paper-trading/trades`
- `POST /api/paper-trading/trades`
- `POST /api/paper-trading/trades/{trade_id}/close`


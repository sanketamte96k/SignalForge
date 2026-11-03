# SignalForge — Phase 24G.28: Architecture & API Contract Report

## 1. Overview & Objective

The objective of Phase 24G.28 is to implement a robust, asynchronous-style backtest job interface connecting the React `StrategySignalPanel` frontend to the FastAPI backend and the underlying CLI backtest engine (`src/backtest/engine.py`).

Prior to this phase, backtests could only be executed via CLI scripts (`python -m src.backtest.engine`), while the frontend Strategy Panel only presented instantaneous historical signals and live paper-trading interactions. Phase 24G.28 provides a non-blocking full-stack bridge allowing researchers and traders to run multi-month historical backtests directly from the web interface without blocking the FastAPI HTTP event loop.

---

## 2. API Endpoints & Route Specifications

All endpoints are registered under the `/api/strategy` router prefix in `src/api/routes/strategy.py`.

### 2.1 Submit Backtest Job
- **Method & Path:** `POST /api/strategy/backtest/run`
- **Status Code:** `202 Accepted`
- **Request Body (`BacktestRunRequest`):**
  ```json
  {
    "symbol": "NIFTY 50",
    "start_date": "2024-01-01",
    "end_date": "2024-03-31",
    "execution_model": "next_open",
    "initial_capital": 100000.0,
    "quantity": 1,
    "transaction_cost_rate": 0.0005
  }
  ```
- **Validation Rules (via Pydantic):**
  - `symbol`: String matching allowed symbol patterns (`^[A-Z0-9_\-&]+(\.[A-Z0-9]+)?$`).
  - `start_date`: Valid `YYYY-MM-DD` date string.
  - `end_date`: Valid `YYYY-MM-DD` date string (`>= start_date`).
  - `execution_model`: Literal `"next_open"` (causal recommended) or `"same_bar_close"` (theoretical).
  - `initial_capital`: Float `> 0` (default: `100000.0`).
  - `quantity`: Integer `>= 1` (default: `1`).
  - `transaction_cost_rate`: Float `>= 0` (default: `0.0005`).
- **Response Body (`BacktestJobCreatedResponse`):**
  ```json
  {
    "job_id": "4a7f28bc-5b43-4dc9-98e6-e17f7c00688a",
    "status": "QUEUED",
    "message": "Backtest job submitted successfully."
  }
  ```

---

### 2.2 Get Job Status & Progress
- **Method & Path:** `GET /api/strategy/backtest/jobs/{job_id}`
- **Status Codes:**
  - `200 OK`: Job found.
  - `404 Not Found`: Job ID does not exist in memory.
- **Response Body (`BacktestJobStatusResponse`):**
  ```json
  {
    "job_id": "4a7f28bc-5b43-4dc9-98e6-e17f7c00688a",
    "status": "RUNNING",
    "progress": 60,
    "symbol": "NIFTY 50",
    "start_date": "2024-01-01",
    "end_date": "2024-03-31",
    "execution_model": "next_open",
    "created_at": "2026-11-03T21:45:00.123456+05:30",
    "started_at": "2026-11-03T21:45:00.250000+05:30",
    "completed_at": null,
    "error_message": null
  }
  ```

---

### 2.3 Get Job Results
- **Method & Path:** `GET /api/strategy/backtest/jobs/{job_id}/result`
- **Status Codes:**
  - `200 OK`: Job completed successfully with result payload.
  - `409 Conflict`: Job is still `QUEUED` or `RUNNING`.
  - `400 Bad Request`: Job ended with status `FAILED` or `CANCELLED`.
  - `404 Not Found`: Unknown job ID.
- **Response Body (`BacktestJobResultResponse`):**
  ```json
  {
    "job_id": "4a7f28bc-5b43-4dc9-98e6-e17f7c00688a",
    "status": "COMPLETED",
    "metrics": {
      "total_trades": 18,
      "winning_trades": 11,
      "losing_trades": 7,
      "win_rate": 61.11,
      "total_pnl": 4250.75,
      "net_return_pct": 4.25,
      "profit_factor": 1.84,
      "max_drawdown": 1250.0,
      "max_drawdown_pct": 1.25,
      "sharpe_ratio": 1.62,
      "initial_capital": 100000.0,
      "final_capital": 104250.75
    },
    "trades": [
      {
        "trade_id": "TRADE-1",
        "symbol": "NIFTY 50",
        "direction": "BUY",
        "entry_time": "2024-01-08T09:30:00+05:30",
        "exit_time": "2024-01-08T15:15:00+05:30",
        "entry_price": 21650.0,
        "exit_price": 21740.0,
        "quantity": 1,
        "pnl": 90.0,
        "pnl_pct": 0.41,
        "exit_reason": "EOD_EXIT",
        "transaction_cost": 21.69
      }
    ]
  }
  ```

---

### 2.4 List Recent Backtest Jobs
- **Method & Path:** `GET /api/strategy/backtest/jobs?limit=20`
- **Status Code:** `200 OK`
- **Query Parameters:** `limit` (int, default: 20, max: 50).
- **Response Body:** Array of `BacktestJobStatusResponse` objects ordered by creation time descending.

---

### 2.5 Cancel Backtest Job
- **Method & Path:** `POST /api/strategy/backtest/jobs/{job_id}/cancel`
- **Status Codes:**
  - `200 OK`: Job marked cancelled.
  - `404 Not Found`: Job ID does not exist.
- **Response Body:** `BacktestJobStatusResponse` with updated status.

---

## 3. Data Transfer & Pydantic Validation

All inputs and outputs are strongly typed via Pydantic v2 schemas in `src/api/models.py`:
- Inputs enforce boundary constraints (e.g., `gt=0` for capital, `ge=1` for quantity).
- Date formats are validated string representations to maintain cross-platform serializability.
- Dataclasses returned by `src.backtest.simulator` (`Trade`, `BacktestMetrics`) are safely transformed to dictionary structures avoiding any circular references or non-serializable objects.

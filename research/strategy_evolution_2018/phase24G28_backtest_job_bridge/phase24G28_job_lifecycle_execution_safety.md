# SignalForge — Phase 24G.28: Job Lifecycle & Execution Safety Report

## 1. State Machine & Lifecycle Management

The `BacktestJobManager` (`src/strategy/job_manager.py`) manages backtest executions through an explicit finite state machine:

```
  [ SUBMITTED ]
        |
        v
    ( QUEUED )
        |
   Worker Picks Job
        |
        v
    ( RUNNING ) -------- ( User Cancels ) --------> [ CANCELLED ]
      /      \
     /        \
  Success    Exception / Missing Data
   /            \
  v              v
[ COMPLETED ]  [ FAILED ]
```

### State Definitions
- **`QUEUED`**: The request has been validated and accepted by the API. The job is placed in memory and submitted to the worker pool.
- **`RUNNING`**: A worker thread from `ThreadPoolExecutor` has acquired the job and commenced computation. Progress is updated monotonically.
- **`COMPLETED`**: Backtest completed normally. Simulation metrics and trade records are recorded in the job object. Progress is locked at 100%.
- **`FAILED`**: An unhandled engine error, file missing error, or zero-candle boundary condition occurred. An informative error message is recorded without crashing the server.
- **`CANCELLED`**: The user requested cancellation before completion. If execution has not begun, the job is aborted immediately.

---

## 2. Execution Concurrency & Thread Isolation

Historical backtesting involves heavy numerical routines (1-minute resamplers, ATR/EMA computations, signal generation, and simulation iterations across tens of thousands of candles).

If executed synchronously within FastAPI route handlers, this computation would block Python's asynchronous event loop (`asyncio`), freezing all incoming HTTP requests, WebSocket updates, and live monitoring loops.

### Architecture Choice: ThreadPoolExecutor
- `BacktestJobManager` encapsulates a dedicated `ThreadPoolExecutor(max_workers=2, thread_name_prefix="bt-worker")`.
- Route handler `POST /api/strategy/backtest/run` is non-blocking: it creates the job record, registers it under a mutex lock, schedules `job_manager._run_job_worker(job_id)` on the thread pool, and immediately returns HTTP `202 Accepted`.
- Number of workers is strictly bounded to `max_workers=2` to ensure local CPU utilization does not starve system processes on local developer machines under the ₹0 zero-cost environment.

---

## 3. Thread Safety & Synchronization

The manager uses `threading.Lock` across all job record modifications:
- Job insertion, status querying, progress updates, cancellation, and eviction all acquire `self._lock`.
- Worker threads capture snapshot references to immutable execution arguments (`BacktestConfig`), preventing mutable race conditions.
- No files are mutated during backtest execution: the underlying `run_backtest()` function reads canonical CSVs in read-only mode and performs all simulation in local memory.

---

## 4. Deterministic Bounded Memory & Eviction Policy

To conform with the strict ₹0 budget and avoid external dependencies (e.g. Redis, Celery, PostgreSQL):
- Jobs are retained in an in-memory dictionary `self._jobs: Dict[str, BacktestJob]`.
- Maximum capacity is capped at `max_jobs = 50`.
- When capacity is reached and a new job is submitted:
  - An eviction scan locates the oldest `COMPLETED`, `FAILED`, or `CANCELLED` jobs.
  - The oldest finished jobs are evicted first (FIFO).
  - Active jobs (`QUEUED` or `RUNNING`) are protected from eviction.
- This bounds the memory footprint deterministically to a few megabytes even after continuous backtesting sessions.

---

## 5. Honest Progress Reporting

SignalForge strictly prohibits fabricating fake timer-based or simulated progress percentages.
Progress is staged to actual operational milestones inside `_run_job_worker`:
1. **10%**: Data loading initiated (fetching & parsing 1-minute historical candles).
2. **20%**: Multi-timeframe indicator computation (EMA, ATR, Volatility bands).
3. **40%**: Signal generation over historical dataframe.
4. **60%**: Simulation engine initiated.
5. **75%**: Simulation engine at midpoint / processing order fills.
6. **90%**: Simulation completed; metric evaluation & Sharpe/drawdown calculation.
7. **100%**: Results fully packaged and serialized.

---

## 6. Protection of Safety Invariants

- **Read-Only Backtests**: Backtests do not connect to broker APIs, do not place live orders, and do not mutate `data/paper_trading/interactive_trades.json`.
- **Strategy Preservation**: Backtest execution uses the frozen causal Hypothesis B (`next_open` causal fill).
- **Holdout Isolation**: The 2020 holdout partition remains strictly quarantined; jobs requesting 2020 data fail safely with error status.

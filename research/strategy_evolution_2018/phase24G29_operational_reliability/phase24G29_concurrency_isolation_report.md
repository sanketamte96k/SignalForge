# SignalForge — Phase 24G.29: Concurrency & Result Isolation Report

## 1. Concurrency Architecture

The `BacktestJobManager` delegates execution to an internal `ThreadPoolExecutor` configured with:
- `max_workers = 2`
- `thread_name_prefix = "BacktestWorker"`

This concurrency limit is deliberately chosen for local single-process workstations under a ₹0 budget. It allows simultaneous backtest evaluations while reserving sufficient CPU cycles for the FastAPI ASGI server and React frontend without system starvation.

---

## 2. Result & Data Isolation Audit

### 2.1 Independent Slicing & Explicit Copying
Historical market data is loaded as a pandas DataFrame and immediately sliced and copied per job:
```python
if start_date or end_date:
    data = data.loc[start_date:end_date].copy()
else:
    data = data.copy()
```
Because `.copy()` creates an independent DataFrame in memory, modifications, indicators, and index cursors from one worker thread cannot leak into or alter another thread's dataset.

### 2.2 Independent Strategy Configuration & Function Closures
Each job instantiates its own `StrategyConfig` dataclass and builds its own signal evaluation closures via `create_signal_function(data, config)`. There are zero global or module-level shared mutable parameters between concurrent jobs.

### 2.3 Verification of Concurrent Job Isolation
During testing, two concurrent jobs were submitted with different date ranges and capital allocations:
- **Job A:** `NIFTY 50`, `2024-01-01` to `2024-01-15`, Initial Capital: ₹100,000.
- **Job B:** `NIFTY 50`, `2024-02-01` to `2024-02-15`, Initial Capital: ₹200,000.

Both jobs executed concurrently across worker threads:
- Job A produced metrics and trades reflecting exactly the 10 trading sessions of Jan 2024.
- Job B produced metrics and trades reflecting exactly the 11 trading sessions of Feb 2024.
- Initial capital and equity curves remained strictly isolated with zero cross-talk.

---

## 3. Failure & Exception Isolation

When one concurrent job encounters an unrecoverable error (e.g., requesting a non-existent symbol or an empty date window), the exception is trapped inside that worker's `try/except` block:
- The failing job transitions to `FAILED` with its specific error message recorded in `job.error`.
- The peer concurrent job continues running unaffected and completes normally with `COMPLETED` status.
- The thread pool remains healthy and ready for subsequent submissions.

---

## 4. File-System Interactions

Backtest executions are strictly read-only simulations:
- Canonical datasets (`data/historical/*.csv`) are opened in read-only mode.
- Neither temporary files nor result dumps are written to disk; all job state is maintained in-memory within `BacktestJobManager._jobs`.
- The active paper trading ledger (`data/paper_trading/interactive_trades.json`) and universe registry (`data/universe_registry.json`) are untouched during backtesting.

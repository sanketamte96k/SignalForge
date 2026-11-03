# SignalForge — Phase 24G.28: Known Limitations & Recovery Behavior

## 1. Local Single-Process Scope

Phase 24G.28 operates strictly within the zero-cost (₹0 budget) boundaries of a local development environment. It purposely avoids enterprise distributed infrastructure such as Celery, Redis, Apache Kafka, or persistent database tables.

### Implications of Local Architecture
1. **Volatile In-Memory Job Storage:**
   - Backtest job records, progress state, and result structures reside entirely in-memory within the Python process heap (`BacktestJobManager._jobs`).
   - If the FastAPI process is restarted, terminated, or crashes, all prior job records are lost.
2. **Single-Node Execution:**
   - Worker threads run on the same machine as the API server using Python's `ThreadPoolExecutor`.
   - Concurrency is bounded to 2 threads to prevent CPU starvation on local laptops or development workstations.

---

## 2. Process Restart & Client Recovery Behavior

When an in-memory job manager is used without an external database, client-side resilience is essential:

1. **Lost Job Detection (HTTP 404):**
   - If the frontend is actively polling a job ID (`job-xyz`) and the backend server restarts, subsequent poll requests return `404 Not Found`.
   - The frontend's polling logic catches the 404 response, halts further polling, and displays an informative notification:
     *"Job no longer found on server (server may have restarted). Please resubmit."*
2. **Deterministic Resubmission:**
   - Because the underlying historical CSV datasets are immutable and read-only, submitting the exact same parameters after a server restart executes cleanly from the beginning and reproduces the identical result.

---

## 3. Storage Eviction & Memory Bounds

To prevent memory leaks over days of continuous local research:
- Memory capacity is clamped at `max_jobs = 50`.
- Once 50 jobs accumulate in memory, the oldest terminal jobs (`COMPLETED`, `FAILED`, `CANCELLED`) are evicted using a FIFO strategy.
- Active jobs (`QUEUED`, `RUNNING`) are immune to eviction.
- Any attempt by a client to fetch results for an evicted job returns `404 Not Found`.

---

## 4. Historical Dataset Bounds & Quarantine Protections

1. **Holdout Partition Isolation (2020 Data):**
   - In accordance with SignalForge research governance, the 2020 holdout partition is strictly quarantined as `EXPLORATORY / CONTAMINATED`.
   - Any backtest request specifying dates overlapping the 2020 partition will either find no matching valid candles or be rejected before execution.
2. **Missing Instrument Data:**
   - If a backtest is requested for a symbol without local historical 1-minute data in `data/historical/stocks/`, the job terminates cleanly with status `FAILED` and error message indicating missing candle dataset. It does not crash the server or corrupt other jobs.

# SignalForge — Phase 24G.29: Known Limitations & Operational Boundaries

## 1. Local Workstation Architecture (₹0 Budget)

SignalForge intentionally operates without enterprise cloud dependencies (e.g. Celery, Redis clusters, AWS SQS, managed Postgres):

1. **Volatile Process Memory:**
   - Jobs are stored in the memory space of the running Python process.
   - Restarting the FastAPI service erases active and completed job history.
   - The frontend handles this gracefully by detecting HTTP 404 and notifying the researcher.
2. **Fixed Concurrency Bounds:**
   - Worker concurrency is strictly clamped to `max_workers = 2`.
   - Submitting more than 2 jobs places additional requests in `QUEUED` state until an active worker completes.
   - This design prevents developer workstations from experiencing UI lag or system unresponsiveness.
3. **Capacity Clamping:**
   - The job history retains up to 50 jobs.
   - Older terminal jobs (`COMPLETED`, `FAILED`, `CANCELLED`) are purged using FIFO rules.
   - Running jobs are never purged.

---

## 2. Python Threading & Cooperative Cancellation Boundaries

1. **Non-Instantaneous Thread Interruption:**
   - In Python, threads cannot be abruptly force-terminated from user space without risking interpreter crash or memory leak.
   - Cancellation takes effect at the next cooperative checkpoint (5 checkpoints throughout the pipeline).
   - If cancellation occurs during numerical calculation, the worker cleanly aborts prior to writing results.
2. **Read-Only Invariance:**
   - Backtest jobs cannot modify paper trading positions or live order ledgers.
   - Historical backtesting remains strictly analytical research.

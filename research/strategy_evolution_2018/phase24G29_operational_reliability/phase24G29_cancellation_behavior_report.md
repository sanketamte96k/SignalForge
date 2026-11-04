# SignalForge — Phase 24G.29: Cancellation Behavior & Cooperative Checkpoints Report

## 1. Operating System & Python Threading Realities

In Python (CPython), running threads cannot be safely force-terminated from an external controller without corrupting interpreter state, leaking file descriptors, or leaving locks in deadlocked conditions.

SignalForge adheres strictly to reality-first engineering: cancellation is never faked or assumed to be an instantaneous kill of arbitrary bytecode. Instead, cancellation is implemented via **thread-safe cooperative checkpoints**.

---

## 2. Cancellation Lifecycle & Checkpoint Architecture

When a client issues `POST /api/strategy/backtest/jobs/{job_id}/cancel`:
1. `BacktestJobManager.cancel_job(job_id)` is invoked under `self._lock`.
2. If the job is `QUEUED`:
   - If scheduled in `ThreadPoolExecutor`, `job._future.cancel()` is attempted.
   - Status is set to `CANCELLED`.
   - `job.error = "Job cancelled by user before execution."`
   - When the worker thread subsequently picks up the job, it immediately encounters Checkpoint 1 and exits without computation.
3. If the job is `RUNNING`:
   - Status is updated to `CANCELLED`.
   - `job.error = "Job cancelled by user during execution."`
   - The worker thread will exit at the next cooperative checkpoint.

---

## 3. Cooperative Checkpoints in Worker Execution

The worker function `_execute_job()` incorporates 5 strategic cancellation checkpoints:

| Checkpoint # | Operational Stage | Purpose |
| :--- | :--- | :--- |
| **Checkpoint 1** | Entry / Pre-Execution | Avoids reading historical CSV files if cancelled while queued. |
| **Checkpoint 2** | Post-Data Load | Aborts before running date slicing and candle validation. |
| **Checkpoint 3** | Post-Date Slicing | Aborts before indicator calculation and signal generation. |
| **Checkpoint 4** | Post-Signal Build | Aborts before running simulation engine over candles. |
| **Checkpoint 5** | Pre-Persistence / Pre-Result | Aborts immediately after simulation completes, preventing results from being attached to `job.result` or status from being flipped to `COMPLETED`. |

---

## 4. Guarantee Against Partial Results

A critical finding of Phase 24G.29 is the elimination of race conditions where an active job was cancelled during execution, but the worker thread proceeded to overwrite `job.status = COMPLETED` and attached results.

With the hardened cooperative checkpoints:
1. `job.result` is only assigned under `self._lock` if `job.status != JobStatus.CANCELLED`.
2. If cancelled at any point, `job.result` remains strictly `None`.
3. The `except Exception` handler checks `if job.status == JobStatus.CANCELLED:` and refuses to overwrite the status with `FAILED`.
4. Subsequent calls to `GET /api/strategy/backtest/jobs/{job_id}/result` return HTTP `400 Bad Request` with detail explaining that the job was cancelled.

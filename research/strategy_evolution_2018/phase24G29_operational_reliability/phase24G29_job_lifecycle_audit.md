# SignalForge — Phase 24G.29: Job Lifecycle & Eviction Safety Audit

## 1. Objective & Scope

This audit rigorously inspects the backtest job state machine (`src/strategy/job_manager.py`) to verify that all lifecycle states (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`) transition deterministically, thread-safely, and without memory corruption or unauthorized eviction.

---

## 2. State Machine Transitions

```
                    +-------------------+
                    |     SUBMITTED     |
                    +-------------------+
                              |
                              v
                    +-------------------+
                    |      QUEUED       |
                    +-------------------+
                       /             \
       (Worker Picks) /               \ (User Cancels)
                     v                 v
           +-------------------+  +-------------------+
           |      RUNNING      |  |     CANCELLED     |
           +-------------------+  +-------------------+
              /        |       \
 (Completion)/ (Error) |        \(User Cancels at Checkpoint)
            v          v         v
     +-----------+ +--------+ +-----------+
     | COMPLETED | | FAILED | | CANCELLED |
     +-----------+ +--------+ +-----------+
```

### Verified Properties
1. **Thread-Safe State Modification:**
   All mutations to `job.status`, `job.progress`, `job.result`, `job.error`, and `job.completed_at` are guarded by `with self._lock:` inside `src/strategy/job_manager.py`.
2. **Terminal Invariance:**
   Once a job reaches a terminal state (`COMPLETED`, `FAILED`, `CANCELLED`), subsequent cancellation attempts safely return `False`, preventing invalid state regressions.
3. **HTTP Contract Consistency:**
   - Querying a nonexistent job ID via `GET /api/strategy/backtest/jobs/{job_id}` returns HTTP `404 Not Found`.
   - Querying results for a job still in progress (`QUEUED` or `RUNNING`) returns HTTP `409 Conflict`.
   - Querying results for a failed job returns HTTP `400 Bad Request` with error details.
   - Querying results for a cancelled job returns HTTP `400 Bad Request` with cancellation details.

---

## 3. Storage Eviction & Protection of Active Jobs

### 3.1 Bounded Capacity Contract
The manager retains up to `_max_retained_jobs` (default: 50). When capacity is reached and a new job is registered, `_prune_oldest_jobs()` is invoked under `self._lock`.

### 3.2 Implemented Eviction Rules
1. **Active Job Immunity:**
   Only jobs in `terminal_statuses = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}` are eligible for eviction.
   Jobs in `QUEUED` or `RUNNING` status are **strictly excluded** from pruning.
2. **FIFO Pruning:**
   Eligible terminal jobs are sorted by `created_at` in ascending order. The oldest completed or failed records are evicted first.
3. **No Forced Eviction Under Full Load:**
   If all retained jobs are actively executing (e.g., during stress testing), no active job is evicted. Capacity expands transiently until terminal states are reached.

---

## 4. Identifier Uniqueness

Job IDs are generated using UUIDv4 hex strings:
`job_id = f"job-{uuid.uuid4().hex[:12]}"`
- Entropy: $16^{12} \approx 2.81 \times 10^{14}$ unique combinations.
- Collision testing over 1,000 consecutively generated IDs demonstrated 0 collisions.

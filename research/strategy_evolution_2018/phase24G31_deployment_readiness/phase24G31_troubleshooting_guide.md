# SignalForge — Phase 24G.31: Operational Troubleshooting & Deployment Recovery Guide

## 1. Overview & Objective

This troubleshooting guide documents reproducible procedures for diagnosing and recovering from operational, networking, dependency, and state failure modes in SignalForge local development and workstation deployment environments.

---

## 2. Failure Mode Taxonomy & Remediation

### 2.1 Backend Environment & Dependency Issues

#### Symptom: `ModuleNotFoundError: No module named 'fastapi'` or `pydantic`
- **Root Cause:** Script executed in system Python rather than the virtual environment, or `pip install -r requirements.txt` was bypassed.
- **Diagnostics:**
  ```bash
  which python   # Linux/macOS
  Get-Command python | Select-Object Source  # Windows PowerShell
  ```
- **Remediation:**
  ```bash
  python -m venv .venv
  # Windows
  .\.venv\Scripts\Activate.ps1
  # Linux/macOS
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

#### Symptom: `ImportError: cannot import name 'atomic_write' from 'src.core.io_utils'`
- **Root Cause:** `PYTHONPATH` does not include project root directory.
- **Remediation:**
  Ensure commands are executed from the repository root:
  ```bash
  export PYTHONPATH=.  # Linux/macOS
  $env:PYTHONPATH = "." # Windows PowerShell
  ```

---

### 2.2 Server Port & Process Conflicts

#### Symptom: `OSError: [Errno 98] Address already in use` (Linux) / `[WinError 10048]` (Windows)
- **Root Cause:** A orphaned background `uvicorn` or `vite` instance is holding port 8000 (backend) or port 5173 (frontend).
- **Diagnostics & Remediation (Windows):**
  ```powershell
  # Check backend port 8000
  netstat -ano | findstr :8000
  taskkill /PID <PID> /F

  # Check frontend port 5173
  netstat -ano | findstr :5173
  taskkill /PID <PID> /F
  ```
- **Diagnostics & Remediation (Linux/macOS):**
  ```bash
  lsof -ti:8000 | xargs kill -9
  lsof -ti:5173 | xargs kill -9
  ```

---

### 2.3 Frontend & Build Failures

#### Symptom: `vite: command not found` or `@vitejs/plugin-react` missing
- **Root Cause:** Node packages were not installed or `frontend/node_modules` was corrupted.
- **Remediation:**
  ```bash
  cd frontend
  rm -rf node_modules package-lock.json
  npm install
  npm run build
  cd ..
  ```

#### Symptom: Frontend Displays Network Error / Failed to Fetch
- **Root Cause:** Backend API is not running on port 8000 or CORS origin is blocked.
- **Diagnostics:**
  Verify backend health check:
  ```bash
  curl http://127.0.0.1:8000/api/health
  # Expected: {"status":"healthy"}
  ```
- **Remediation:** Ensure backend was started with `uvicorn src.api.main:app --host 127.0.0.1 --port 8000`.

---

### 2.4 Backtest Job Lifecycle Failures

#### Symptom: Frontend Polling Loop Terminated with `HTTP 404: Job not found`
- **Root Cause:** Backend was restarted while a backtest was running or queued, clearing the ephemeral in-memory `BacktestJobManager` registry.
- **Expected Behavior:** By design, the React frontend detects 404 responses from `GET /api/strategy/backtest/status/{job_id}`, logs an error message, stops polling, and enables the "Run Historical Backtest" button.
- **Remediation:** Click **RUN HISTORICAL BACKTEST** to initiate a new job.

#### Symptom: Job Fails with `Historical 1m market data file not found`
- **Root Cause:** The requested symbol or date range relies on historical CSV data that is not present in `data/historical/stocks/`.
- **Diagnostics:**
  Check whether canonical files exist:
  ```bash
  ls data/historical/stocks/
  ```
- **Remediation:** Ensure local historical files (e.g. `ADANIPORTS_1m.csv`, `RELIANCE_1m.csv`) are placed in `data/historical/stocks/`.

---

## 3. Operational Recovery Runbook

| Failure Tier | Severity | Recovery Procedure |
| :--- | :--- | :--- |
| **Worker Crash** | Medium | Restart backend server; in-memory jobs reset gracefully to clean state. |
| **Data Corruption** | High | Atomic writes prevent partial writes; restore from immutable backup if disk faults occur. |
| **Out of Memory** | High | Restart processes; verify maximum 1 concurrent backtest worker limit. |
| **Vite Cache Stale** | Low | Run `npm run build` or delete `frontend/node_modules/.vite/`. |

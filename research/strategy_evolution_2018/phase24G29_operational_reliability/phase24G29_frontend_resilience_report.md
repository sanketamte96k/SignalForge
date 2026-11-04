# SignalForge — Phase 24G.29: Frontend Resilience & Labeling Report

## 1. Scope & Objective

This report details the hardening of the Strategy Signal Panel UI (`frontend/src/StrategySignalPanel.jsx`) under real-world operating conditions: network interruptions, server restarts while polling, user cancellations, and transparent labeling of theoretical vs causal execution.

---

## 2. Hardened Polling & Resilience Behavior

### 2.1 Server Restart Detection (HTTP 404)
In an in-memory job management architecture, restarting the FastAPI backend terminates all active jobs and purges the job dictionary.
- **Previous Behavior:** The frontend polling loop caught 404 errors as generic transient network errors and continued polling indefinitely every second.
- **Hardened Behavior:** The polling handler explicitly checks for `404` or `not found` errors. Upon detection, it immediately halts polling (`clearInterval`) and alerts the researcher:
  *"Job no longer found on server (server may have restarted). Please resubmit."*

### 2.2 Consecutive Network Failure Protection
If connectivity to the backend is severed during a running backtest:
- The UI tracks consecutive network errors.
- If 5 consecutive poll requests fail, polling is terminated and an error banner is presented:
  *"Connection lost while polling backtest progress. Please verify backend status."*
- This prevents zombie polling loops from draining browser resources.

---

## 3. UI Cancellation Controls

The Strategy Signal Panel now exposes an interactive cancellation workflow:
1. When a job is in `QUEUED` or `RUNNING` status, an explicit `CANCEL BACKTEST` button (`id="bt-cancel-btn"`) is rendered alongside the progress bar.
2. Clicking the button invokes `cancelBacktestJob(backtestJobId)`.
3. The button displays a disabled `CANCELLING...` state while the request is in-flight to prevent duplicate clicks.
4. Upon backend acknowledgement, the status transitions to `CANCELLED` and displays a confirmation notification.

---

## 4. Truth-in-Execution Labeling (Causal vs Theoretical)

In strict accordance with SignalForge research governance:
**The UI must never present theoretical execution as causal.**

### 4.1 Input Dropdown Labeling
The execution model selector explicitly marks lookahead bias:
- `next_open (Causal) [Realistic]`
- `same_close (Theoretical) [Lookahead Biased]`

### 4.2 Simulation Results Prominent Badge
When results are rendered in the panel:
- If `same_close` was evaluated:
  A prominent warning badge is rendered:
  `⚠️ THEORETICAL EXECUTION (LOOKAHEAD BIASED / NON-CAUSAL)`
- If `next_open` was evaluated:
  A verified causal badge is rendered:
  `✅ CAUSAL REALISTIC EXECUTION (NEXT-OPEN BAR FILL)`

This guarantees that researchers and traders reviewing visual outputs cannot confuse lookahead-biased backtests with deployable causal strategies.

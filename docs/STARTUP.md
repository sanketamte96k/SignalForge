# SignalForge — Local Startup Guide

## 1. Quick Start (Development Workflow)

SignalForge consists of a **FastAPI backend** (port 8000) and a **React/Vite frontend** (port 5173).

### Step 1: Start Backend (Terminal 1)
Activate your Python environment and start the ASGI server:

```bash
# Windows
.\.venv\Scripts\Activate.ps1
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload

# Linux / macOS
source .venv/bin/activate
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```
**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Verify backend health in a browser or curl:
```bash
curl http://127.0.0.1:8000/
# Output: {"service":"SignalForge API","status":"ok","version":"0.1.0"}
```

---

### Step 2: Start Frontend (Terminal 2)
In a separate terminal, launch the Vite dev server:

```bash
cd frontend
npm run dev
```
**Expected Output:**
```
  VITE v8.2.2  ready in 180 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

### Step 3: Open Platform Dashboard
Open your browser to:
```
http://localhost:5173/
```

### Complete End-to-End Research Verification Walkthrough:
1. Navigate to the **Strategy & Backtesting** panel on the right sidebar.
2. Ensure **Symbol** is set to `NIFTY 50`.
3. Set **Start Date** to `2024-01-01` and **End Date** to `2024-01-31`.
4. Ensure **Execution Model** is `next_open (Causal) [Realistic]`.
5. Click **RUN HISTORICAL BACKTEST**.
6. Observe progress progression: `SIMULATING BACKTEST (10%... -> 100%)`.
7. Inspect completed KPI results:
   - Net Return: `+0.19%`
   - Total P&L: `₹192.95`
   - Total Trades: `13`
   - Win Rate: `46.15%`
   - Max Drawdown: `-0.32%`
8. Click **📊 INTERACTIVE ANALYTICS** to open the modal:
   - View interactive SVG Equity Curve and Underwater Drawdown Curve.
   - Inspect the **Trade History** tab with interactive filtering (`ALL`, `WINNERS`, `LOSERS`).
9. Click **📑 TEARSHEET** to open the standalone self-contained HTML research tearsheet in a new tab.

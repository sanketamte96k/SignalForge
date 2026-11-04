# SignalForge — Troubleshooting & Recovery Guide

## 1. Common Issues & Solutions

### A. Backend Startup: `ModuleNotFoundError: No module named 'fastapi'`
- **Cause:** Python virtual environment is either not activated or dependencies were installed globally.
- **Solution:**
  ```bash
  # Windows
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt

  # Linux / macOS
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### B. Port Conflict: `OSError: [Errno 98] Address already in use` or `10048`
- **Cause:** Another process or previous uvicorn server is bound to port 8000 or port 5173.
- **Solution:**
  ```bash
  # Windows: Find process and terminate
  netstat -ano | findstr :8000
  taskkill /PID <PID> /F

  # Linux / macOS:
  lsof -ti:8000 | xargs kill -9
  ```

### C. Frontend Polling: `HTTP 404: Backtest job 'job-...' not found`
- **Cause:** In-memory job state was cleared due to backend server restart.
- **Solution:** The frontend automatically detects 404 responses and terminates the polling loop. Simply re-click **RUN HISTORICAL BACKTEST** to initiate a new job.

### D. Backtest: `FileNotFoundError: Historical 1m market data file not found`
- **Cause:** Local historical dataset has not been downloaded or is placed in a non-standard directory.
- **Solution:** Ensure historical CSVs are placed under `data/historical/stocks/{SYMBOL}_1m.csv` or `data/historical/nifty50_1m_signalforge.csv`.

### E. Frontend Vite Build: `Error: Cannot find module '@vitejs/plugin-react'`
- **Cause:** Incomplete `npm install` inside `frontend/`.
- **Solution:**
  ```bash
  cd frontend
  rm -rf node_modules package-lock.json
  npm install
  npm run build
  cd ..
  ```

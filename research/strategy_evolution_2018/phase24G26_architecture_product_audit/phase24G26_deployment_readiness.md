# SignalForge — Phase 24G.26: Deployment Readiness & Operational Audit

## 1. Executive Summary

This audit assesses the operational readiness of SignalForge for both local standalone research workstation deployment and future cloud/server hosting. 

Currently, SignalForge is architected as an **intranet/local-first dual-process application**:
- **Backend:** Python 3.14 / FastAPI running on `http://127.0.0.1:8000` via Uvicorn.
- **Frontend:** React 19 / Vite SPA running on `http://localhost:5173` with Lightweight Charts.
- **Data Tier:** Local file-based storage (`data/historical/stocks/*.csv` and `data/paper_trading/*.json`).

SignalForge is **fully operational in local development/research mode**, but requires targeted architectural hardening before it can be deployed as an autonomous, multi-user, or cloud-hosted production platform.

---

## 2. Component Readiness Matrix

| System Component | Classification | Current State | Required Changes for Deployment |
| :--- | :---: | :--- | :--- |
| **Backend API (FastAPI / Uvicorn)** | `READY_WITH_CHANGES` | Fully functional REST routes, Pydantic validation, CORS configured for localhost ports. | • Add dynamic `PORT` and `HOST` env var binding.<br>• Implement structured JSON logging.<br>• Add static file mount for frontend production build. |
| **Frontend SPA (React 19 / Vite)** | `READY_WITH_CHANGES` | 8 complete views, 119 passing tests, modern responsive layout, full keyboard shortcuts. | • Add `VITE_API_BASE_URL` environment fallback.<br>• Configure build output to be served by FastAPI or Nginx.<br>• Add offline/reconnection banner for WebSocket/API drops. |
| **Storage & Data Layer** | `READY_WITH_CHANGES` | CSV market data and JSON paper ledgers. Fast local read access. | • Implement atomic file writes (`write_temp_and_replace`).<br>• Add file locking (`portalocker` or SQLite migration) to prevent multi-process corruption. |
| **Research & Backtest Engine** | `READY_WITH_CHANGES` | Deterministic, vector-accelerated backtest engine (`scripts/run_backtest_2018.py`). | • Wrap CLI execution into an asynchronous background task queue (FastAPI BackgroundTasks or Celery/RQ) with progress polling. |
| **Paper Trading Engine** | `READY_WITH_CHANGES` | Complete session manager and order simulator in `src/api/routes/paper_trading.py`. | • Isolate ledger writes with mutex lock.<br>• Provide ledger backup and snapshot rotation. |
| **External Data Collector** | `NOT_READY` | Intentionally deactivated under strict ₹0 budget constraints. | • Implement official broker WebSocket adapter (when budget authorized).<br>• Add circuit breakers and exponential backoff reconnection. |

---

## 3. Environment & Secrets Management Audit

### 3.1 Existing Environment Configuration
- `.env.example` is maintained in the root directory:
  ```env
  GROWW_API_KEY=your_groww_api_key_here
  GROWW_API_SECRET=your_groww_api_secret_here
  GROWW_API_BASE_URL=https://api.groww.in/v1
  GROWW_REQUEST_TIMEOUT=30.0
  ```
- `.gitignore` properly excludes `.env`, `*.pyc`, `__pycache__`, `node_modules`, and local build artifacts (`frontend/dist`).
- A local `.env` file exists for local testing, with no live trading credentials active.

### 3.2 Missing Environment Variables for Production
To make the application 12-factor compliant, the following environment variables should be formalized in `src/core/config.py`:
1. `APP_ENV`: Deployment environment (`development`, `staging`, `production`).
2. `API_HOST`: Bind address (default: `127.0.0.1` locally; `0.0.0.0` in container).
3. `API_PORT`: Port number (default: `8000`).
4. `CORS_ORIGINS`: Comma-separated list of allowed web origins.
5. `DATA_ROOT_DIR`: Configurable path to historical data lake and paper ledgers.
6. `SERVE_STATIC_FRONTEND`: Boolean flag indicating whether FastAPI should serve `frontend/dist`.

---

## 4. Operational Startup Procedures

### 4.1 Local Development (Current Standard)

#### Backend Process:
```powershell
# From repository root
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend Process:
```powershell
# From frontend directory
cd frontend
npm run dev
# Vite runs at http://localhost:5173
```

### 4.2 Single-Process Production Mode (Recommended Architecture)

For seamless local or cloud deployment without managing two separate development servers, FastAPI can be configured to serve the compiled Vite static assets:

1. **Build Frontend:**
   ```bash
   cd frontend && npm run build
   # Outputs optimized SPA to frontend/dist
   ```
2. **Mount Static Assets in `src/api/main.py`:**
   ```python
   from fastapi.staticfiles import StaticFiles
   from pathlib import Path

   frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
   if frontend_dist.exists():
       app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
   ```
3. **Run Production Server:**
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 2
   ```

---

## 5. Containerization & Production Topology

```
+-------------------------------------------------------------+
|                      Client Browser                         |
+-------------------------------------------------------------+
                              | HTTPS (:443)
                              v
+-------------------------------------------------------------+
|                 Reverse Proxy (Nginx / Caddy)               |
|      - TLS Termination                                      |
|      - Rate Limiting                                        |
|      - Security Headers (CSP, HSTS, X-Frame-Options)        |
+-------------------------------------------------------------+
         |                                           |
         | /api/*                                    | /* (Static SPA)
         v                                           v
+-----------------------------+             +-----------------+
| Uvicorn / FastAPI Backend   |             | Static Storage  |
| - 2-4 ASGI Worker Processes |             | (Vite dist)     |
| - Pydantic Request Parsing  |             +-----------------+
+-----------------------------+
         |
         +---> Local File Store / SQLite / DuckDB
               ├── data/historical/stocks/ (Read-only historical CSV/Parquet)
               └── data/paper_trading/ (Read/Write paper ledger)
```

### 5.1 Dockerfile Implementation Blueprint
```dockerfile
# Multi-stage build for SignalForge
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS production
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/src/
COPY data/ /app/data/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## 6. Health Checks & Observability

### Current Health Endpoints:
- `GET /` — Basic service status and version banner (`{"service": "SignalForge API", "status": "ok", "version": "0.1.0"}`).
- `GET /api/health` — Returns system operational status.

### Production Observability Requirements:
1. **Liveness & Readiness Probes:**
   - `GET /api/health/live`: Basic process heartbeat (returns HTTP 200).
   - `GET /api/health/ready`: Checks accessibility of `data/historical/stocks/` and write permissions on `data/paper_trading/`.
2. **Resource Metrics:**
   - Expose Prometheus endpoint (`/metrics`) tracking request latency percentiles, error rates (5xx), active paper positions, and backtest memory utilization.
3. **Audit Logging:**
   - Log all paper trading executions, strategy parameter modifications, and scan queries with correlation IDs and timestamps.

---

## 7. Deployment Readiness Conclusion

SignalForge achieves a readiness rating of **DEPLOYABLE_FOR_LOCAL_RESEARCH**. With the implementation of atomic write safety, static SPA bundling, and asynchronous backtest job queues, it can advance directly to **PRODUCTION_CONTAINER_READY**.

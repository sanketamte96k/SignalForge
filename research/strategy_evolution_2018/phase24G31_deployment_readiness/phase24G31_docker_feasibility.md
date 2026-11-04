# SignalForge — Phase 24G.31: Local Container Feasibility & Docker Evaluation

## 1. Feasibility Assessment

An audit of SignalForge's architecture demonstrates that the application is well-suited for containerized execution via local Docker and Docker Compose.

### Feasibility Criteria
- **Stateless ASGI Engine:** FastAPI backend coordinates jobs in-memory without mandatory local socket IPC.
- **Zero Paid Infrastructure:** Requires no cloud queues (RabbitMQ, SQS), distributed brokers (Redis, Celery), or external SQL database clusters.
- **Unified Port Architecture:** A single container can compile the frontend into static assets and serve both the API and client bundle on port 8000, or operate alongside the Vite dev server on port 5173.

---

## 2. Multi-Stage Container Design (`Dockerfile`)

```dockerfile
# Stage 1: Compile React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/universe_registry*.json ./data/
COPY data/universe/ ./data/universe/
COPY --from=frontend-builder /build/dist ./frontend/dist

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/ || exit 1
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Key Advantages:
1. **Minimal Attack Surface:** Alpine builder discarded in final image; runtime base is `python:3.12-slim`.
2. **Immutable Research Artifact:** The resulting Docker image packages the exact bytecode, dependencies, and frontend assets for long-term reproducible execution.
3. **Automated Health Monitoring:** Embedded `HEALTHCHECK` probes `GET /` every 30 seconds.

---

## 3. Docker Compose Orchestration (`docker-compose.yml`)

```yaml
services:
  signalforge:
    build:
      context: .
      dockerfile: Dockerfile
    image: signalforge:latest
    container_name: signalforge-local
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - APP_ENV=production
    volumes:
      # Mount local data directory as read-only to guarantee historical data safety
      - ./data:/app/data:ro
```

### Execution Commands:
```bash
# Build and start containerized SignalForge
docker compose up -d --build

# Verify container logs
docker compose logs -f

# Stop container
docker compose down
```

### Verdict:
Docker support is verified as feasible, self-contained, and valuable for developers on non-Windows workstations who prefer containerized isolation without installing local Node/Python tooling.

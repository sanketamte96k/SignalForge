# SignalForge — Production Multi-Stage Container Definition
# ========================================================
# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.12-slim AS runtime

# System runtime flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

# Install security updates & pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source & core assets
COPY src/ ./src/
COPY data/universe_registry*.json ./data/
COPY data/universe/ ./data/universe/
COPY data/historical/2020_holdout_manifest.json ./data/historical/2020_holdout_manifest.json

# Copy compiled frontend dist bundle into web root
COPY --from=frontend-builder /build/dist ./frontend/dist

# Expose internal API & dashboard port
EXPOSE 8000

# Health check probing root endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Launch FastAPI ASGI server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

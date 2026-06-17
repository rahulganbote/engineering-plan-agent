# ── Stage 1: Build the React frontend SPA ─────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy frontend package list and lockfile
COPY frontend/package*.json ./
RUN npm ci

# Copy the rest of the frontend source code and compile
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Run Python backend and serve React static files ──────────────────
FROM python:3.11-slim

# HuggingFace Spaces runs containers as UID 1000 — create a matching user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (leverages Docker cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (.dockerignore excludes .venv, secrets, logs, caches)
COPY --chown=appuser:appuser . .

# Copy compiled frontend assets from Stage 1 into /app/frontend/dist
COPY --chown=appuser:appuser --from=frontend-builder /build/dist /app/frontend/dist

# Runtime directories — must be writable by appuser
RUN mkdir -p logs logs/exports secrets \
    && chown -R appuser:appuser /app

USER appuser

# Expose port (default 7860 to match previous config, overridable on Cloud Run)
ENV PORT=7860
ENV HOME=/home/appuser

EXPOSE 7860

# Container healthcheck — FastAPI's health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -sf "http://localhost:${PORT}/health" || exit 1

CMD ["./start.sh"]

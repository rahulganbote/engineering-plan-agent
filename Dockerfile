# ────────────────────────────────────────────────────────────────────────────
# Dockerfile — EM Copilot (BRD → Engineering Plan multi-agent system)
#
# Single-container deployment running TWO processes:
#   • FastAPI backend (uvicorn)  — the 7-agent pipeline, internal port 8000
#   • Streamlit UI               — public port 7860 (HuggingFace Spaces standard)
#
# Both processes are launched by start.sh. Streamlit reaches the API over
# localhost since they share the container network namespace.
#
# Targets:
#   HuggingFace Spaces (Docker SDK) — set `app_port: 7860` in the Space README
#   Local Docker                    — `docker build -t em-copilot . && \
#                                       docker run -p 7860:7860 --env-file secrets/.env em-copilot`
# ────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# HuggingFace Spaces runs containers as UID 1000 — create a matching user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System dependencies:
#   build-essential — for any C-extension wheels that need compiling
#   curl            — used by start.sh's health-check loop
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (separate layer → Docker build-cache reuse)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (.dockerignore excludes .venv, secrets, logs, caches)
COPY --chown=appuser:appuser . .

# Runtime directories — must be writable by appuser
#   logs/         — JSONL + plain-text execution logs
#   logs/exports/ — local CSV bundle fallback when Sheets creds are absent
#   secrets/      — empty on HF Spaces (env vars injected directly); used locally
RUN mkdir -p logs logs/exports secrets \
    && chown -R appuser:appuser /app

USER appuser

# HuggingFace Spaces routes external traffic to this port (match `app_port`)
ENV PORT=7860
ENV API_PORT=8000
# Streamlit + HF: silence telemetry, keep the home dir writable
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    HOME=/home/appuser

EXPOSE 7860

# Container healthcheck — Streamlit's own endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -sf "http://localhost:${PORT}/_stcore/health" || exit 1

# start.sh launches uvicorn (bg) + streamlit (fg)
CMD ["./start.sh"]

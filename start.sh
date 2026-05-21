#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# start.sh — single-container launcher for EM Copilot
#
# This app is two processes:
#   1. FastAPI backend  (uvicorn) — the agent pipeline, on port 8000 (internal)
#   2. Streamlit UI     — on $PORT (default 7860, HuggingFace Spaces requirement)
#
# HuggingFace Spaces exposes ONE port. We run the API in the background, wait
# for it to pass a health check, then run Streamlit in the foreground (its
# process keeps the container alive). Streamlit talks to the API over
# localhost — both processes share the container's network namespace.
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PORT="${PORT:-7860}"
API_PORT="${API_PORT:-8000}"

echo "──────────────────────────────────────────────"
echo " EM Copilot — starting"
echo "   FastAPI backend : 0.0.0.0:${API_PORT}  (internal)"
echo "   Streamlit UI    : 0.0.0.0:${PORT}      (public)"
echo "──────────────────────────────────────────────"

# ── 0. Materialize the Google service-account key (optional — for Sheets) ───
# HuggingFace Spaces can't host the JSON key file, so it is injected as a
# base64-encoded secret (GOOGLE_SA_B64). Decode it back to the path the app
# expects BEFORE the API starts. A missing/bad secret is non-fatal — the
# pipeline falls back to the local-CSV export.
if [ -n "${GOOGLE_SA_B64:-}" ]; then
    mkdir -p secrets
    if echo "${GOOGLE_SA_B64}" | base64 -d > secrets/google_service_account.json 2>/dev/null; then
        export GOOGLE_SERVICE_ACCOUNT_JSON="secrets/google_service_account.json"
        echo "✓ Google service-account key decoded — Sheets export enabled."
    else
        rm -f secrets/google_service_account.json
        echo "✗ GOOGLE_SA_B64 is set but failed to decode — using CSV fallback."
    fi
else
    echo "• GOOGLE_SA_B64 not set — Sheets export uses the local-CSV fallback."
fi

# ── 1. FastAPI backend in the background ────────────────────────────────────
uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${API_PORT}" \
    --log-level info &
API_PID=$!

# ── 2. Wait for the API to become healthy (max ~40s) ────────────────────────
echo "Waiting for FastAPI backend to report healthy..."
for i in $(seq 1 40); do
    if curl -sf "http://localhost:${API_PORT}/health" > /dev/null 2>&1; then
        echo "✓ FastAPI backend is healthy."
        break
    fi
    if ! kill -0 "${API_PID}" 2>/dev/null; then
        echo "✗ FastAPI backend process died during startup. Aborting."
        exit 1
    fi
    sleep 1
done

# ── 3. Streamlit UI in the foreground (keeps the container alive) ───────────
# Streamlit reads API_BASE_URL from the environment; default localhost:8000
# is correct since both processes are in the same container.
export API_BASE_URL="${API_BASE_URL:-http://localhost:${API_PORT}}"

streamlit run streamlit_app.py \
    --server.port="${PORT}" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --server.enableXsrfProtection=false \
    --server.enableCORS=false

# If Streamlit exits, take the API down with it so the container stops cleanly.
echo "Streamlit exited — shutting down FastAPI backend (pid ${API_PID})."
kill "${API_PID}" 2>/dev/null || true

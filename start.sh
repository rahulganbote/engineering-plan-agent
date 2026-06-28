#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# start.sh - single-container launcher for EM Copilot (React UI)
#
# This script decodes Google Sheets SA credentials if GOOGLE_SA_B64 is present,
# then launches the FastAPI backend directly in the foreground.
# FastAPI serves both the REST API and the React static UI at the root path.
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PORT="${PORT:-7860}"

echo "──────────────────────────────────────────────"
echo " EM Copilot - starting"
echo "   FastAPI Application on port ${PORT}"
echo "──────────────────────────────────────────────"

# ── 0. Materialize the Google service-account key (optional - for Sheets) ───
if [ -n "${GOOGLE_SA_B64:-}" ]; then
    mkdir -p secrets
    if echo "${GOOGLE_SA_B64}" | base64 -d > secrets/google_service_account.json 2>/dev/null; then
        export GOOGLE_SERVICE_ACCOUNT_JSON="secrets/google_service_account.json"
        echo "✓ Google service-account key decoded - Sheets export enabled."
    else
        rm -f secrets/google_service_account.json
        echo "✗ GOOGLE_SA_B64 is set but failed to decode - using CSV fallback."
    fi
else
    echo "• GOOGLE_SA_B64 not set - Sheets export uses the local-CSV fallback."
fi

# ── 1. Run FastAPI Application in the foreground ───────────────────────────
# Use exec to replace the shell process for proper Docker signal forwarding
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --log-level info

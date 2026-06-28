"""
src/api/main.py
═══════════════
FastAPI gateway — exposes the LangGraph pipeline to the React UI
and other external channels.
"""

from __future__ import annotations

# Load env vars BEFORE any module that reads them at import time.
from dotenv import load_dotenv

load_dotenv("secrets/.env")
load_dotenv(".env")

import os as _os

from src.core.config import settings as _settings

_os.environ.setdefault("LANGCHAIN_TRACING_V2", str(_settings.langchain_tracing_v2))
_os.environ.setdefault("LANGCHAIN_PROJECT", _settings.langchain_project or "em-copilot-brd-agent")
if _settings.langchain_api_key:
    _os.environ.setdefault("LANGCHAIN_API_KEY", _settings.langchain_api_key)

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# SlowAPI imports for rate limiting
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

# Re-exports for backwards compatibility (especially for tests/unit/test_api.py)
from src.api.routes.system import list_providers  # noqa: F401
from src.api.state import _push_event, _run_events, _run_export, _run_owner, _runs  # noqa: F401
from src.api.tasks import _run_export_handlers_background, _run_pipeline_task  # noqa: F401

# ── App lifecycle ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("EM Copilot API starting up")

    # Wire cache backend + observability sink
    try:
        from src.core.cache import init_default_backend_from_env

        init_default_backend_from_env()
    except Exception as e:
        log.warning(f"cache backend init failed: {e}")

    try:
        from src.api.state import _push_event
        from src.core.events import set_event_sink

        def _bridge(event: dict) -> None:
            rid = event.pop("run_id", None)
            if not rid:
                return  # event outside any run — drop
            _push_event(rid, event)

        set_event_sink(_bridge)
    except Exception as e:
        log.warning(f"event sink wiring failed: {e}")

    yield
    log.info("EM Copilot API shutting down")


app = FastAPI(
    title="EM Copilot — BRD to Engineering Plan API",
    description=(
        "7-agent LangGraph system that transforms BRDs into engineering artifacts. "
        "Hub-and-spoke architecture with Pinecone RAG, Critic revision loop, and HITL gate."
    ),
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Structured 429 with Retry-After header. Mirrors the /approve 409 contract
    so the React frontend's apiClient.ts surfaces detail.next_step in the toast.
    """
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(settings.rate_limit_retry_after_sec)},
        content={
            "detail": {
                "code": "rate_limited",
                "message": "Pipeline runs are capped to protect against runaway cost.",
                "next_step": (
                    "Wait a few hours and try again, or reach out at support@emcopilot.ai for an extended demo."
                ),
            },
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://emcopilot.ai",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=_os.environ.get("SESSION_SECRET_KEY", "em-copilot-secret-key-32-chars-long!"),
    session_cookie="em_copilot_session",
)

# ── Router Registration ───────────────────────────────────────────────────────
from src.api.routes.approval import router as approval_router
from src.api.routes.auth import router as auth_router
from src.api.routes.exports import router as exports_router
from src.api.routes.runs import router as runs_router
from src.api.routes.system import router as system_router

app.include_router(auth_router)
app.include_router(runs_router)
app.include_router(approval_router)
app.include_router(exports_router)
app.include_router(system_router)

# ── Static Frontend Mount ─────────────────────────────────────────────────────
frontend_dist_dir = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "frontend", "dist"
)
_os.makedirs(frontend_dist_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=frontend_dist_dir, html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=True,
        reload_dirs=["src"],
        log_level="info",
    )

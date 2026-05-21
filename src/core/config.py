"""
src/core/config.py
══════════════════
Application configuration via pydantic-settings.

All configuration is loaded from environment variables or .env file.
Using pydantic-settings instead of raw os.getenv() provides:
    - Type validation at startup (fail fast if a required key is missing)
    - IDE autocomplete on settings fields
    - Single source of truth for all config values
    - Automatic .env file loading

Usage:
    from src.core.config import settings

    # Access any setting:
    model = settings.openai_model
    api_key = settings.pinecone_api_key
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "secrets" / ".env")

class Settings(BaseSettings):
    """
    All application settings loaded from environment variables.

    Fields are grouped by integration. Required fields have no default —
    the app will fail at startup with a clear error if they are missing.
    Optional fields have sensible defaults for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # OPENAI_API_KEY and openai_api_key both work
        extra="ignore",         # ignore unknown env vars (don't raise errors)
    )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key:       str              # required — no default
    openai_model:         str = "gpt-4o"
    openai_model_mini:    str = "gpt-4o-mini"   # used for Critic scoring + injection scan
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 1024

    # ── Pinecone ──────────────────────────────────────────────────────────────
    pinecone_api_key:     str              # required — no default
    pinecone_index:       str = "brd-knowledge-base"
    rag_top_k:            int = 4
    rag_similarity_threshold: float = 0.45

    # ── LangSmith (observability — primary for demo day) ──────────────────────
    langchain_tracing_v2: str = "true"    # enables auto-instrumentation
    langchain_api_key:    str = ""        # optional in dev, required for tracing
    langchain_project:    str = "em-copilot-brd-agent"

    # ── LangFuse (secondary observability — rubric coverage) ──────────────────
    langfuse_secret_key:  str = ""
    langfuse_public_key:  str = ""
    langfuse_host:        str = "https://cloud.langfuse.com"

    # ── ElevenLabs (voice HITL) ───────────────────────────────────────────────
    elevenlabs_api_key:   str = ""
    elevenlabs_agent_id:  str = ""

    # ── Google Sheets (write action) ─────────────────────────────────────────
    google_service_account_json: str = "./secrets/google_service_account.json"
    google_sheet_id:      str = ""

    # ── FastAPI ───────────────────────────────────────────────────────────────
    fastapi_host:         str = "0.0.0.0"
    fastapi_port:         int = 8000
    api_base:             str = "http://localhost:8000"

    # ── Pipeline behaviour ────────────────────────────────────────────────────
    max_critic_revisions: int   = 2
    max_agent_retries:    int   = 2
    pipeline_timeout_sec: int   = 300   # 5 min hard limit

    # ── Security ──────────────────────────────────────────────────────────────
    max_brd_file_size_mb: int   = 10
    injection_llm_confidence_threshold: float = 0.85

    # ── Jira ──────────────────────────────────────────────────────────────
    jira_base_url:        str = ""
    jira_email:           str = ""
    jira_api_token:       str = ""
    jira_project_key:     str = ""
    jira_issue_type:      str = "Epic"   # REST fallback path; MCP path always creates Epic
    jira_label_prefix:    str = "em-copilot"

    # ── Email (audit) ─────────────────────────────────────────────────────────
    smtp_host:            str = ""
    smtp_port:            int = 587
    smtp_user:            str = ""
    smtp_pass:            str = ""
    audit_email:          str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    lru_cache(maxsize=1) means the .env file is read once at startup,
    not on every function call. Thread-safe.

    Usage:
        from src.core.config import get_settings
        settings = get_settings()
    """
    return Settings()


# Module-level singleton for convenience
# Import this directly: from src.core.config import settings
settings = get_settings()

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
from pathlib import Path

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "secrets" / ".env")


class Settings(BaseSettings):
    """
    All application settings loaded from environment variables.

    Fields are grouped by integration. Required fields have no default -
    the app will fail at startup with a clear error if they are missing.
    Optional fields have sensible defaults for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # OPENAI_API_KEY and openai_api_key both work
        extra="ignore",  # ignore unknown env vars (don't raise errors)
    )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_model_mini: str = "gpt-4o-mini"  # used for Critic scoring + injection scan
    openai_default_model: str = ""
    openai_mini_model: str = ""
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 1024

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-3-5-sonnet-latest"
    anthropic_mini_model: str = "claude-3-5-haiku-20241022"

    # ── Pinecone ──────────────────────────────────────────────────────────────
    pinecone_api_key: str = ""
    pinecone_index: str = "brd-knowledge-base"
    rag_top_k: int = 6
    rag_similarity_threshold: float = 0.45

    # ── LangSmith (observability - primary for demo day) ──────────────────────
    langchain_tracing_v2: str = "true"  # enables auto-instrumentation
    langchain_api_key: str = ""  # optional in dev, required for tracing
    langchain_project: str = "em-copilot-brd-agent"

    # ── LangFuse (secondary observability) ──────────────────
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── ElevenLabs (voice HITL) ───────────────────────────────────────────────
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""

    # ── OpenRouter (Llama 3.3 70B paid model with cost limits. Powers guest
    # mode.) ──────────────────────────────────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct"
    openrouter_model_mini: str = "meta-llama/llama-3.3-70b-instruct"

    # ── Guest Quotas ─────────────────────────────────────────────────────────
    rate_limit_guest_run_per_day: str = "3/day"
    rate_limit_exempt_emails: str = ""

    # ── Tavily (web search tool) ──────────────────────────────────────────────
    tavily_api_key: str = ""
    # Free-tier monthly cap is 1000 queries. The tool tracks invocations and
    # disables itself (returns degraded ToolResult) when this budget is reached
    # within the current calendar month. Reset at month boundary via the helper.
    # Set to 0 to disable budget enforcement (unlimited).
    tavily_monthly_budget: int = 1000

    # ── GitHub (metrics tool) ─────────────────────────────────────────────────
    github_token: str = ""

    # ── Google Sheets (write action) ─────────────────────────────────────────
    google_service_account_json: str = "./secrets/google_service_account.json"
    google_sheet_id: str = ""

    # ── FastAPI ───────────────────────────────────────────────────────────────
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    api_base: str = "http://localhost:8000"

    # ── Pipeline behaviour ────────────────────────────────────────────────────
    max_critic_revisions: int = 2
    max_agent_retries: int = 2
    pipeline_timeout_sec: int = 600  # 10 min hard limit
    agent_timeout_sec: int = 90  # Per-agent bulkhead - Phase 9
    anthropic_agent_timeout_sec: int = (
        180  # Anthropic is 3-5× slower than OpenAI; per-family override    # Per-agent bulkhead - Phase 9
    )
    enable_provider_fallback: bool = True

    # ── Security ──────────────────────────────────────────────────────────────
    max_brd_file_size_mb: int = 5
    injection_llm_confidence_threshold: float = 0.85

    # ── Rate limits (slowapi syntax: "N/period") ──────────────────────────────
    # Override via env in production. Examples: "10/day", "100/hour", "5/minute".
    # The /run-pipeline endpoint applies BOTH limits (per-day AND per-week).
    # /approve gets a separate, looser limit (single-shot per run typical).
    # Keyed by authenticated user email (falls back to IP for unauth requests).
    rate_limit_run_pipeline_per_day: str = "5/day"
    rate_limit_run_pipeline_per_week: str = "10/week"
    rate_limit_approve_per_hour: str = "10/hour"
    # Retry-After header value (seconds) returned with every 429.
    # Conservative default: 1 hour. Operators can tune via env.
    rate_limit_retry_after_sec: int = 3600
    voice_webhook_secret: str = ""  # Token used by ElevenLabs webhook to authenticate voice approvals
    max_pipeline_run_budget_usd: float = 2.00  # Hard budget limit per pipeline run (dollars)
    # Gate for diagnostic routes like GET /debug/config-status. False in
    # production so the endpoint 404s and doesn't advertise the voice webhook
    # setup. Set to True locally or during voice-auth debugging.
    debug_endpoints_enabled: bool = False

    # ── Jira ──────────────────────────────────────────────────────────────
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    jira_issue_type: str = "Epic"  # REST fallback path; MCP path always creates Epic
    jira_label_prefix: str = "em-copilot"

    # ── Slack (pipeline failure alerts) ───────────────────────────
    slack_webhook_url: str = ""  # Incoming Webhook URL; empty = alerts off

    # ── Email (audit) ─────────────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    audit_email: str = ""

    @model_validator(mode="after")
    def resolve_model_defaults(self) -> "Settings":
        if self.openai_default_model:
            self.openai_model = self.openai_default_model
        if self.openai_mini_model:
            self.openai_model_mini = self.openai_mini_model
        return self


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

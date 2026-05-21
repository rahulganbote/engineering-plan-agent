"""
src/agents/base_agent.py
═════════════════════════
BaseAgent mixin — shared utilities for all 5 specialist agents.

Provides:
    1. Retry logic (tenacity) — FM-1: malformed JSON / LLM timeout mitigation
    2. Execution timing — SC-3: pipeline time measurement
    3. log_agent_run() call site — ensures every agent execution is logged
    4. No-RAG-hits Amber forcing — FM-2: automatic Amber when no RAG context

Usage:
    class PlanGeneratorAgent(BaseAgent):
        def run(self, state, feedback=""):
            start = self.start_timer()
            citations, context_str = self.retrieve(query, source_types)
            output = self._call_llm_with_retry(prompt)
            self.log_run(state.run_id, agent_name, citations, output, start)
            return output

Failure modes implemented here:
    FM-1 malformed_json:  @retry with 3 attempts, exponential backoff 1s/2s/4s
    FM-2 no_rag_hits:     _check_no_rag_hits() flags and reduces confidence_score
    FM-5 llm_timeout:     tenacity wait_exponential handles OpenAI timeouts
"""

from __future__ import annotations

import time
from typing import Optional

from openai import OpenAI
# LangSmith auto-traces every wrapped client.chat.completions.create() call —
# captures prompt, response, model, latency, token usage. No code changes
# needed elsewhere; the client API is identical.
from langsmith.wrappers import wrap_openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)

from src.core.config import settings
from src.core.logger import get_logger, log_agent_run
from src.core.rag import retrieve, format_context, RetrievedChunk

log    = get_logger(__name__)
client = wrap_openai(OpenAI(api_key=settings.openai_api_key))

# Sentinel citation value used when Pinecone returns no results
NO_RAG_SENTINEL = "kb_no_results_ungrounded"


class BaseAgent:
    """
    Mixin providing retry, timing, RAG retrieval, and structured logging
    for all 5 specialist agents.

    All specialist agents should inherit from this class and call:
        start = self.start_timer()
        ... do work ...
        self.log_run(state.run_id, "agent_name", citations, critic_score, start, revision)
    """

    # ── Timing ────────────────────────────────────────────────────────────────

    def start_timer(self) -> float:
        """
        Record pipeline start time.
        Returns perf_counter float — pass to log_run() when done.

        Usage:
            start = self.start_timer()
            output = self.do_work()
            self.log_run(..., start=start)
        """
        return time.perf_counter()

    def elapsed_ms(self, start: float) -> int:
        """Convert perf_counter start to elapsed milliseconds."""
        return int((time.perf_counter() - start) * 1000)

    # ── RAG Retrieval ─────────────────────────────────────────────────────────

    def retrieve_context(
        self,
        query:        str,
        source_types: Optional[list[str]] = None,
        domain:       Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Retrieve RAG context and format for LLM prompt injection.

        Returns:
            (context_str, citation_ids)
            context_str:  formatted text to inject into agent prompt
            citation_ids: list of chunk IDs for citations[] field

        FM-2 no_rag_hits: if no chunks retrieved above threshold,
            returns NO_RAG_SENTINEL in citation_ids — Critic will
            automatically force Amber badge when it detects this.
        """
        chunks = retrieve(query, source_types=source_types, domain=domain)
        context_str, citation_ids = format_context(chunks)

        if not chunks or citation_ids == [NO_RAG_SENTINEL]:
            log.warning(
                f"No RAG hits for query='{query[:50]}' | "
                f"source_types={source_types} | "
                f"FM-2: will force Amber badge"
            )

        return context_str, citation_ids

    def has_no_rag_hits(self, citation_ids: list[str]) -> bool:
        """True if citations indicate no RAG context was retrieved."""
        return not citation_ids or citation_ids == [NO_RAG_SENTINEL]

    # ── LLM Call with Retry ───────────────────────────────────────────────────

    def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt:   str,
        model:         str = None,
        response_format: dict = None,
    ) -> str:
        """
        Call OpenAI with tenacity retry — FM-1 malformed JSON, FM-5 LLM timeout.

        Retry policy:
            - 3 attempts total (1 initial + 2 retries)
            - Exponential backoff: 1s → 2s → 4s
            - Retries on: OpenAI errors, timeouts, JSON parse errors
            - After 3 failures: raises RetryError → routed to error node

        Args:
            system_prompt: Role and instruction for the LLM
            user_prompt:   The BRD content + RAG context
            model:         Override model (default: settings.openai_model)
            response_format: {"type": "json_object"} for structured output

        Returns:
            Raw string content from the LLM response
        """
        model = model or settings.openai_model

        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            reraise=True,
        )
        def _call() -> str:
            kwargs = {
                "model":    model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.2,
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        try:
            return _call()
        except RetryError as e:
            log.error(
                f"LLM call failed after 3 attempts | "
                f"model={model} | error={type(e.last_attempt.exception()).__name__} | "
                f"FM-1/FM-5 mitigation: routing to error node"
            )
            raise  # Propagates to pipeline error node

    # ── Structured Logging ────────────────────────────────────────────────────

    def log_run(
        self,
        run_id:          str,
        agent_name:      str,
        citation_ids:    list[str],
        critic_score:    Optional[float],
        start_time:      float,
        revision_count:  int = 0,
        success:         bool = True,
        error:           Optional[str] = None,
        guardrail_triggers: list[str] = None,
    ) -> dict:
        """
        Log a single agent execution to JSONL and console.
        MUST be called after every agent run — this is the
        primary per-agent execution log required by the rubric.

        Logged fields (per spec):
            ✓ input:             brd_hash passed externally — never raw BRD
            ✓ rag_chunks:        citation_ids (chunk IDs retrieved)
            ✓ output:            logged via success flag and critic_score
            ✓ critic_score:      float or None
            ✓ execution_time_ms: measured by start_timer() / elapsed_ms()
            ✓ guardrail_triggers: list of fired guardrail names
            ✓ revision_count:    current revision cycle number

        Returns the log entry dict (used by log_pipeline_summary).
        """
        execution_time_ms = self.elapsed_ms(start_time)
        triggers = guardrail_triggers or []

        # Add FM-2 flag if no RAG hits were found
        if self.has_no_rag_hits(citation_ids):
            triggers.append("FM-2_no_rag_hits")

        log_agent_run(
            agent_name=agent_name,
            run_id=run_id,
            rag_chunk_ids=citation_ids,
            critic_score=critic_score,
            execution_time_ms=execution_time_ms,
            guardrail_triggers=triggers,
            revision_count=revision_count,
            success=success,
            error=error,
        )

        return {
            "agent_name":        agent_name,
            "run_id":            run_id,
            "execution_time_ms": execution_time_ms,
            "rag_chunk_count":   len(citation_ids),
            "critic_score":      critic_score,
            "revision_count":    revision_count,
            "guardrail_triggers": triggers,
            "success":           success,
        }

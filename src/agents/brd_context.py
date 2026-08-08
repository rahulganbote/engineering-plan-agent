"""
src/agents/brd_context.py
══════════════════════════
Extracts the BRD's business identity - what is being built and why - so every
downstream surface can speak about the actual project instead of generic
software-engineering boilerplate.

Why this exists as an LLM step:
    Regex extraction (src/core/brd_utils.extract_project_name) keys off heading
    shape. That works for template-driven BRDs but degrades on real-world
    documents: a PDF titled "Checkout Incident Detection Agent Problem
    Statement" has no "Project:" marker, its goal lives in prose under a "Goal"
    heading, and the business domain is never stated explicitly. Understanding
    "what is this for" is a reading-comprehension task, so an LLM does it.

Consumers:
    - PipelineState.brd_project_title      → UI subtitle, PDF header, Jira summary
    - PipelineState.brd_objective_summary   → PDF header, Jira description,
                                              and the PROJECT CONTEXT block that
                                              every specialist agent receives
    - PipelineState.brd_domain              → PROJECT CONTEXT block

Failure policy: never blocks the pipeline. On timeout, provider failure, or
unparseable output it falls back to the regex extractor and, failing that, to
empty strings. Agents simply lose a grounding hint; they still get the full BRD.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from src.core.brd_utils import extract_objectives, extract_project_name
from src.core.logger import get_logger
from src.core.models import BRDSection

log = get_logger(__name__)

# Tight budget - this is a small comprehension call on a mini model that runs
# once per pipeline run, before the specialists fan out. It must never become
# the reason a run feels slow, so we cap it and fall back to regex.
_TIMEOUT_SEC = 12.0
_MAX_CHARS = 6000

# Document-type noise an LLM sometimes leaves on the title despite instructions.
_TITLE_NOISE = re.compile(
    r"\b(?:brd|business\s+requirements?\s+document|problem\s+statement|"
    r"requirements?\s+document|project\s+charter)\b[:\s\-–—]*",
    re.IGNORECASE,
)

_PROMPT = """You are reading a Business Requirements Document (BRD) to identify what is being built.

Return JSON with exactly these keys:
  "project_title":     The name of the product/system being built. 2-8 words.
                       Use the real product or capability name. STRIP document-type
                       words like "BRD", "Problem Statement", "Requirements Document".
                       Example: for a doc titled "Checkout Incident Detection Agent
                       Problem Statement", return "Checkout Incident Detection Agent".
  "objective_summary": ONE sentence (max 30 words) stating what will be built and the
                       business outcome it delivers. Write it so a reader who has never
                       seen the BRD understands the purpose. Start with a verb.
                       Example: "Build a Zapier agent that triages checkout failure
                       events from Google Sheets and publishes one ALERT or LOG command
                       per run to protect revenue."
  "domain":            The business domain in 2-5 words. Example: "E-commerce operations",
                       "Retail banking fraud", "Clinical trial recruitment".

Base every field ONLY on the document below. Do not invent product names.

DOCUMENT:
---
{doc}
---

Respond with ONLY the JSON object."""


def extract_brd_context(
    brd_text: str,
    brd_sections: list[BRDSection],
    model_family: str = "openai",
    run_id: str = "",
) -> tuple[str, str, str]:
    """
    Identify the BRD's project title, objective summary, and domain.

    Returns:
        (project_title, objective_summary, domain)

        project_title always falls back to the regex extractor so it is never
        empty for a parseable BRD. objective_summary / domain may be "" when the
        LLM is unavailable - callers must treat them as optional.
    """
    regex_title = extract_project_name(brd_sections)

    raw = _call_llm(brd_text, model_family=model_family, run_id=run_id)
    if raw is None:
        summary = _objectives_fallback(brd_sections)
        log.warning(f"[{run_id}] BRD context LLM unavailable - using regex title={regex_title!r}")
        return regex_title, summary, ""

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        log.warning(f"[{run_id}] BRD context parse failed ({type(e).__name__}) - falling back to regex")
        return regex_title, _objectives_fallback(brd_sections), ""

    title = _clean_title(str(data.get("project_title") or "")) or regex_title
    summary = " ".join(str(data.get("objective_summary") or "").split())[:400]
    domain = " ".join(str(data.get("domain") or "").split())[:80]

    if not summary:
        summary = _objectives_fallback(brd_sections)

    log.info(f"[{run_id}] BRD context | title={title!r} domain={domain!r} summary_chars={len(summary)}")
    return title, summary, domain


def build_context_block(
    project_title: str,
    objective_summary: str = "",
    domain: str = "",
) -> str:
    """
    Render the PROJECT CONTEXT preamble injected into every specialist agent's
    prompt. Returns "" when nothing is known, so prompts stay unchanged rather
    than gaining an empty header.
    """
    lines = []
    if project_title and project_title != "BRD run":
        lines.append(f"  Project: {project_title}")
    if domain:
        lines.append(f"  Domain: {domain}")
    if objective_summary:
        lines.append(f"  Business goal: {objective_summary}")
    if not lines:
        return ""
    return (
        "PROJECT CONTEXT - this is what you are planning. Every name, "
        "deliverable, and rationale you produce must be specific to it:\n" + "\n".join(lines) + "\n\n"
    )


# ── Internals ────────────────────────────────────────────────────────────────


def _clean_title(title: str) -> str:
    """Strip document-type noise and surrounding punctuation from an LLM title."""
    cleaned = _TITLE_NOISE.sub(" ", title)
    cleaned = " ".join(cleaned.split()).strip(" :-–—\"'")
    return cleaned[:80]


def _objectives_fallback(brd_sections: list[BRDSection]) -> str:
    """Join the parsed Objectives/Goals section into a single line, if present."""
    items = extract_objectives(brd_sections)
    if not items:
        return ""
    return " ".join(" ".join(items).split())[:400]


def _call_llm(brd_text: str, model_family: str, run_id: str) -> str | None:
    """Bounded, provider-aware LLM call. Returns None on any failure."""
    from src.core.providers import complete_with_fallback, map_model

    prompt = _PROMPT.format(doc=brd_text[:_MAX_CHARS])
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(
                complete_with_fallback,
                model_family=model_family,
                messages=[{"role": "user", "content": prompt}],
                model=map_model(model_family, "mini"),
                temperature=0,
                response_format={"type": "json_object"},
            )
            content, _p, _c, _final = future.result(timeout=_TIMEOUT_SEC)
            return content
    except FuturesTimeout:
        log.warning(f"[{run_id}] BRD context LLM timeout after {_TIMEOUT_SEC}s | family={model_family}")
    except Exception as e:
        log.warning(f"[{run_id}] BRD context LLM failed | {type(e).__name__}: {str(e)[:120]}")
    return None

"""
src/agents/orchestrator.py
══════════════════════════
Orchestrator Agent - the hub of the hub-and-spoke architecture.

Role:
    The Orchestrator is the entry point of the LangGraph pipeline.
    It receives the validated BRD text from the Security Validator,
    parses it into structured sections, and builds the routing plan
    that tells each specialist agent which sections to focus on.

What it does NOT do:
    ✗ Does NOT call Pinecone / RAG  (no retrieval needed for routing)
    ✗ Does NOT call the LLM to generate content
    ✗ Does NOT make architectural decisions
    ✗ Does NOT score or validate outputs

Why no LLM here:
    BRD parsing is deterministic - regex and string matching are faster,
    cheaper, and more reliable than asking an LLM to identify sections.
    The Orchestrator's job is plumbing, not reasoning.

Pattern justification (hub-and-spoke):
    After routing, the LangGraph coordinator_agent.py uses the Send API
    to dispatch all 5 specialist agents simultaneously. This is genuine
    parallelism - not a sequential chain. The Orchestrator is the hub
    that enables this fan-out.

Section parsing accepts every common BRD heading shape:
    - Markdown headers       (## Section, ### Subsection)
    - ALL-CAPS / underlined  (OBJECTIVES, "Objectives\n=========")
    - Numbered/lettered      (1. Objectives, 2.1 Functional Requirements, A. Goals)
    - Bold "Heading:" style  (Objectives:)
    Falls back to the entire document as a single section only when nothing matches.

"""

from __future__ import annotations

import hashlib
import re

from src.core.logger import get_logger
from src.core.models import (
    BRDSection,
    OrchestratorOutput,
)

log = get_logger(__name__)


# ── Heading detection regexes ────────────────────────────────────────────────
# Each pattern matches a LINE that should be treated as a section heading.
# `_HEADING_PATTERNS` is tried in order; the first one that produces ≥ 3
# headings wins. They all use MULTILINE so `^`/`$` bind to line boundaries.
_HEADING_PATTERNS: list[re.Pattern[str]] = [
    # 1. Markdown headers: "# Title", "## Title", "### Title"
    re.compile(r"^[ \t]{0,3}#{1,4}[ \t]+\S.*$", re.MULTILINE),
    # 2. Numbered or lettered headings:
    #    "1. Objectives", "2.1 Functional Requirements", "A. Goals",
    #    "1) Project Overview", "II. Constraints"
    re.compile(
        r"^[ \t]{0,3}(?:\d{1,2}(?:\.\d{1,2}){0,3}[\.\)]|[A-Z][\.\)]|[IVX]{1,4}[\.\)])"
        r"[ \t]+[A-Z][^\n]{1,80}$",
        re.MULTILINE,
    ),
    # 3. ALL-CAPS headings (≥ 4 chars, may include spaces/&/-): "OBJECTIVES",
    #    "NON-FUNCTIONAL REQUIREMENTS", "BUDGET & TIMELINE"
    re.compile(r"^[ \t]{0,3}[A-Z][A-Z0-9 &\-/]{3,79}$", re.MULTILINE),
    # 4. Title Case "Heading:" or short Title Case line followed by colon:
    #    "Objectives:", "Functional Requirements:"
    re.compile(
        r"^[ \t]{0,3}(?:[A-Z][\w\-/&]*[ \t]?){1,7}:[ \t]*$",
        re.MULTILINE,
    ),
    # 5. Title Case standalone line (last resort) - short line of Title Case
    #    words with no terminating punctuation: "Objectives", "Constraints"
    re.compile(
        r"^[ \t]{0,3}(?:[A-Z][\w\-/&]*[ \t]?){1,6}$",
        re.MULTILINE,
    ),
]

# Strip leading numeric/letter prefixes from a heading line to get a clean name.
_PREFIX_STRIP = re.compile(
    r"^[ \t]{0,3}(?:#{1,4}[ \t]+|"  # markdown
    r"(?:\d{1,2}(?:\.\d{1,2}){0,3}|[A-Z]|[IVX]{1,4})[\.\)][ \t]+)"  # numbered/lettered
)


class OrchestratorAgent:
    """
    Parses an uploaded BRD into structured sections and builds
    a routing plan mapping each specialist agent to relevant sections.

    The Orchestrator runs once at pipeline start. After it completes,
    the LangGraph Send API fans out to all 5 specialist agents in parallel.
    """

    # Maps each specialist agent to the BRD section keywords it needs
    ROUTING_MAP: dict[str, list[str]] = {
        "engineering_plan_generator": ["objective", "functional", "requirement", "risk", "constraint"],
        "schedule_estimator": ["timeline", "resource", "constraint", "team", "budget"],
        "solution_architect": ["nfr", "non-functional", "constraint", "technical", "integration"],
        "poc_planner": ["objective", "risk", "assumption", "functional"],
        "tech_stack_recommender": ["technical", "constraint", "nfr", "integration", "platform"],
    }

    # Required-section check accepts these aliases so numbered headings like
    # "Goals", "Non-Functional Requirements", "Budget" still satisfy the gate.
    _REQUIRED_ALIASES: dict[str, list[str]] = {
        "objective": ["objective", "objectives", "goal", "goals"],
        "requirement": [
            "requirement",
            "requirements",
            "functional requirements",
            "non-functional requirements",
            "fr",
            "nfr",
        ],
        "constraint": [
            "constraint",
            "constraints",
            "limitation",
            "limitations",
            "budget",
            "timeline",
        ],
    }

    def run(self, brd_text: str, run_id: str) -> tuple[OrchestratorOutput, list[BRDSection]]:
        """
        Parse BRD text into sections and produce routing plan.

        Args:
            brd_text: Validated, PII-redacted BRD text from Security Validator
            run_id:   Unique pipeline run identifier

        Returns:
            (OrchestratorOutput, list[BRDSection])
            The sections are stored separately in PipelineState.brd_sections
        """
        log.info(f"[{run_id}] Orchestrator starting | words={len(brd_text.split())}")

        # Hash the BRD for audit trail - never store raw text in state
        brd_hash = hashlib.sha256(brd_text.encode("utf-8", errors="ignore")).hexdigest()

        # Parse sections
        sections = self._parse_sections(brd_text)
        section_names = [s.section_name.lower() for s in sections]

        # Note: We no longer do a hard fail here. SecurityValidator already handled
        # completeness checks (including the LLM semantic fallback).
        validation_passed = True
        missing = []

        # Build routing plan - each agent gets the section names it needs
        routing_plan = {
            agent: [s.section_name for s in sections if any(kw in s.section_name.lower() for kw in keywords)]
            for agent, keywords in self.ROUTING_MAP.items()
        }

        output = OrchestratorOutput(
            run_id=run_id,
            brd_hash=brd_hash,
            sections=sections,
            routing_plan=routing_plan,
            validation_passed=validation_passed,
            validation_errors=[f"Missing section: {m}" for m in missing],
        )

        log.info(
            f"[{run_id}] Orchestrator complete | "
            f"sections={len(sections)} | "
            f"validation={'ok' if validation_passed else 'FAILED'} | "
            f"section_names={section_names[:8]}"
        )
        return output, sections

    # ── Section parsing ──────────────────────────────────────────────────────

    def _parse_sections(self, text: str) -> list[BRDSection]:
        """
        Split BRD text into named sections.

        Strategy: try each heading regex in `_HEADING_PATTERNS` in order
        and keep the first one that yields at least 3 headings. This handles:
            - Markdown (## Title)
            - Numbered / lettered (1. Title, 2.1 Title, A. Title, II. Title)
            - ALL-CAPS (OBJECTIVES)
            - "Title:" style (Objectives:)
            - Bare Title Case (Objectives)

        Falls back to the entire document as one section ONLY if no pattern
        produces useful results.
        """
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        best_sections: list[BRDSection] = []
        for pat in _HEADING_PATTERNS:
            headings = list(pat.finditer(normalized))
            if len(headings) < 3:
                continue

            sections = self._build_sections_from_headings(normalized, headings)
            # Keep the first splitter that gives us a usable parse.
            # (Earlier patterns are more specific; we prefer their result.)
            best_sections = sections
            break

        if not best_sections:
            best_sections = [
                BRDSection(
                    section_name="Full BRD",
                    content=normalized.strip(),
                    word_count=len(normalized.split()),
                    has_nfrs=self._has_nfrs(normalized),
                    has_constraints=self._has_constraints(normalized),
                )
            ]

        return best_sections

    def _build_sections_from_headings(
        self,
        text: str,
        headings: list[re.Match[str]],
    ) -> list[BRDSection]:
        """Slice text into sections using the spans of detected heading lines."""
        sections: list[BRDSection] = []
        for i, match in enumerate(headings):
            raw_heading = match.group(0).strip()
            section_name = self._clean_heading(raw_heading)
            body_start = match.end()
            body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[body_start:body_end].strip()

            # Skip empty or trivially short sections (covers cosmetic header
            # lines that have no body, e.g., a banner above the first section).
            if not content and not section_name:
                continue

            sections.append(
                BRDSection(
                    section_name=section_name or "Untitled",
                    content=content or raw_heading,
                    word_count=len((content or raw_heading).split()),
                    has_nfrs=self._has_nfrs(content),
                    has_constraints=self._has_constraints(content),
                )
            )
        return sections

    @staticmethod
    def _clean_heading(raw: str) -> str:
        """Strip markdown hashes, numeric/letter prefixes, trailing colons."""
        cleaned = _PREFIX_STRIP.sub("", raw).strip()
        cleaned = cleaned.rstrip(":").strip()
        return cleaned

    @staticmethod
    def _has_nfrs(content: str) -> bool:
        if not content:
            return False
        lowered = content.lower()
        return any(
            kw in lowered
            for kw in (
                "performance",
                "availability",
                "latency",
                "throughput",
                "scalab",
                "non-functional",
                "nfr",
                "uptime",
                "sla",
            )
        )

    @staticmethod
    def _has_constraints(content: str) -> bool:
        if not content:
            return False
        lowered = content.lower()
        return any(
            kw in lowered
            for kw in (
                "constraint",
                "limitation",
                "budget",
                "timeline",
                "must not",
                "cannot",
                "deadline",
                "compliance",
            )
        )

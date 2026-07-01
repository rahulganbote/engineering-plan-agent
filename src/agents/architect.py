"""
src/agents/architect.py
════════════════════════
Solution Architect Agent - specialist spoke.

RAG: source_types=["arch_pattern", "standard"]
Contract: ArchitectureOutput

The agent is intentionally independent: it reads BRD sections and optional
Orchestrator/Critic feedback from PipelineState, then returns one typed artifact
to the Orchestrator Aggregator. It does not call other specialist agents.

Diagram generation:
    The agent asks the LLM to emit a Mermaid `graph LR/TD` block that visualizes
    the component data flow. The Mermaid source is the canonical artifact -
    it round-trips to Jira (native code block), Confluence, GitHub README, and
    any other surface that speaks Mermaid. For the React UI, we also
    render the Mermaid to SVG via kroki.io and cache it on diagram_svg so the
    UI can render the diagram natively.

    Failure modes are handled gracefully:
        - LLM omits diagram_mermaid       → both fields stay None; UI shows
                                            "(no diagram generated)"
        - Kroki call fails or times out   → diagram_svg stays None; UI falls
                                            back to client-side mermaid.js
"""

from __future__ import annotations

import json

import requests

from src.agents.base_agent import BaseAgent
from src.core.logger import get_logger
from src.core.models import (
    ArchitectureOutput,
    Component,
    NFRMapping,
    PipelineState,
)

log = get_logger(__name__)

# ── Kroki rendering config ───────────────────────────────────────────────────
KROKI_URL = "https://kroki.io/mermaid/svg"
KROKI_TIMEOUT_SEC = 15  # Per-attempt budget. 8s was too tight - kroki.io
# occasionally serves a 10-12s response. 15 × 2 retries
# = 30s worst case, still well under the 90s bulkhead.
KROKI_MAX_RETRIES = 2

SYSTEM_PROMPT = """You are a senior Solution Architect. Produce a grounded,
actionable architecture from the BRD and knowledge-base context.

Rules:
1. Select one architecture pattern and justify it against BRD NFRs and constraints.
2. Include 3-8 components with responsibility, technology, and interfaces.
3. Include ordered data_flow steps.
4. Include nfr_mappings with citation values from AVAILABLE CITATION IDs.
5. Flag missing NFRs or ambiguous integration constraints.
6. Produce diagram_mermaid - a valid Mermaid `graph LR` (preferred) or `graph TD`
   block that visualizes the major components and their primary data flow.
   - Use ONLY ASCII node ids (e.g. Client, ApiGateway, OrderSvc, Db, Queue).
   - Put human-readable labels in square brackets, e.g. ApiGateway[API Gateway].
   - Use arrows like A --> B or A -- "REST" --> B for labeled edges.
   - Keep it under 14 nodes - a high-level overview an EM can scan in 10 seconds.
   - Do NOT wrap the diagram in markdown fences (no ```mermaid). Just the raw
     `graph LR\\n  …` text inside the JSON string field.
   - Avoid characters that break Mermaid: parentheses inside labels, smart
     quotes, or unescaped colons. Prefer hyphens.
7. Output ONLY valid JSON - no markdown fences around the JSON, no explanation."""

SCHEMA = """{
  "pattern": "string",
  "pattern_justification": "string",
  "components": [
    {
      "name": "string",
      "responsibility": "string",
      "technology": "string",
      "interfaces": ["REST API"]
    }
  ],
  "data_flow": ["ordered data movement step"],
  "nfr_mappings": [
    {
      "nfr": "string",
      "architecture_decision": "string",
      "citation": "chunk_id from context"
    }
  ],
  "deployment_model": "string",
  "diagram_mermaid": "graph LR\\n  Client --> ApiGateway[API Gateway]\\n  ApiGateway --> AppSvc[Application Service]\\n  AppSvc --> Db[(Database)]",
  "confidence_score": 0.0,
  "assumptions": ["string"],
  "flagged_ambiguities": ["string"]
}"""


class SolutionArchitectAgent(BaseAgent):
    """Creates the architecture artifact as an independent specialist spoke."""

    def run(self, state: PipelineState, feedback: str = "") -> ArchitectureOutput:
        start = self.start_timer()
        log.info(f"[{state.run_id}] SolutionArchitect start | revision={state.revision_count}")

        brd_text = self._brd_text(state)
        query = f"architecture pattern nfr scalability availability integration {brd_text[:300]}"
        context_str, citation_ids = self.retrieve_context(
            query=query,
            source_types=["arch_pattern", "standard"],
        )

        guardrail_triggers = []
        if self.has_no_rag_hits(citation_ids):
            log.info(f"[{state.run_id}] No RAG hits for SolutionArchitect. Calling Tavily for live web grounding...")
            # ── Privacy boundary ────────────────────────────────────────────────
            # Tavily is third-party. Query MUST be derived metadata (section names
            # + bounded concept keywords), NOT raw BRD content. Use the helper:
            from src.integrations.tavily import build_tavily_query, tavily_search

            safe_query = build_tavily_query("best architecture pattern", state.brd_sections)
            web_results = tavily_search(safe_query)
            context_str = f"ORGANIZATION KNOWLEDGE BASE: (Empty/No matching records found)\n\nWEB GROUNDING (TAVILY SEARCH):\n{web_results.content}"
            guardrail_triggers.append("tavily_web_grounding_used")
            # Record the tool invocation regardless of outcome so the Critic can
            # cross-check that a tavily_web_grounding citation appears in the output.
            if "tavily_search" not in state.tools_used:
                state.tools_used.append("tavily_search")
            if not web_results.used_fallback:
                citation_ids = ["tavily_web_grounding"] + web_results.sources

        raw = self._generate(brd_text, context_str, citation_ids, feedback)
        output = self._parse(raw, state.run_id, citation_ids)

        # Render Mermaid → SVG via Kroki. Non-blocking: SVG stays None on failure,
        # and the UI falls back to client-side mermaid.js rendering.
        if output.diagram_mermaid:
            output.diagram_svg = self._render_kroki(output.diagram_mermaid, state.run_id)

        self.log_run(
            run_id=state.run_id,
            agent_name="solution_architect",
            citation_ids=citation_ids,
            critic_score=None,
            start_time=start,
            revision_count=state.revision_count,
            guardrail_triggers=guardrail_triggers,
        )
        log.info(
            f"[{state.run_id}] SolutionArchitect done | "
            f"pattern={output.pattern} components={len(output.components)} "
            f"mermaid={bool(output.diagram_mermaid)} svg={bool(output.diagram_svg)}"
        )
        return output

    def _brd_text(self, state: PipelineState) -> str:
        return "\n\n".join(f"## {s.section_name}\n{s.content}" for s in state.brd_sections)

    def _generate(
        self,
        brd_text: str,
        context_str: str,
        citation_ids: list[str],
        feedback: str,
    ) -> str:
        feedback_block = f"\nCRITIC FEEDBACK - address all points:\n{feedback}\n" if feedback else ""
        cites = "\n".join(f"  - {c}" for c in citation_ids)
        return self._call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"{feedback_block}"
                f"AVAILABLE CITATION IDs:\n{cites}\n\n"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                f"BRD:\n{brd_text}\n\n"
                f"Output ONLY JSON:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _parse(self, raw: str, run_id: str, citation_ids: list[str]) -> ArchitectureOutput:
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error(f"[{run_id}] SolutionArchitect parse error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

        try:
            first_cite = citation_ids[0] if citation_ids else "arch_patterns_chunk_0"
            components = [
                Component(
                    name=c.get("name", "Application Service"),
                    responsibility=c.get("responsibility", "Owns core business workflow"),
                    technology=c.get("technology", "Python/FastAPI"),
                    interfaces=c.get("interfaces", ["REST API"]),
                )
                for c in d.get("components", [])
            ]
            nfr_mappings = []
            for n in d.get("nfr_mappings", []):
                cite = n.get("citation", first_cite)
                if cite not in citation_ids:
                    cite = first_cite
                nfr_mappings.append(
                    NFRMapping(
                        nfr=n.get("nfr", "Availability and reliability"),
                        architecture_decision=n.get(
                            "architecture_decision",
                            "Use managed services, health checks, and retry-safe APIs.",
                        ),
                        citation=cite,
                    )
                )

            diagram_mermaid = self._sanitize_mermaid(d.get("diagram_mermaid"))

            return ArchitectureOutput(
                run_id=run_id,
                citations=citation_ids or [first_cite],
                confidence_score=float(d.get("confidence_score", 0.72)),
                assumptions=d.get("assumptions", []),
                flagged_ambiguities=d.get("flagged_ambiguities", []),
                pattern=d.get("pattern", "Modular monolith with service boundaries"),
                pattern_justification=d.get(
                    "pattern_justification",
                    "Selected to keep delivery scope controlled while preserving clear module boundaries.",
                ),
                components=components or self._default_components(),
                data_flow=d.get(
                    "data_flow",
                    [
                        "User submits request through web/API entry point",
                        "Application service validates and processes request",
                        "Persistence layer stores transaction state and audit trail",
                    ],
                ),
                nfr_mappings=nfr_mappings or [self._default_nfr(first_cite)],
                deployment_model=d.get("deployment_model", "Cloud-managed container deployment"),
                diagram_mermaid=diagram_mermaid or self._default_mermaid(components or self._default_components()),
                # diagram_svg populated after construction by run() via _render_kroki
            )
        except Exception as e:
            log.error(f"[{run_id}] SolutionArchitect build error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

    # ── Mermaid helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_mermaid(raw: str | None) -> str | None:
        """
        Strip common LLM-emitted wrappers from the Mermaid source.
        The agent prompt forbids markdown fences but LLMs add them ~5% of the time.
        """
        if not raw or not isinstance(raw, str):
            return None
        text = raw.strip()
        # Remove ```mermaid … ``` or ``` … ``` wrappers
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        # Confirm it looks like a Mermaid diagram
        head = text.split("\n", 1)[0].lower()
        if not any(
            head.startswith(k)
            for k in (
                "graph ",
                "flowchart ",
                "sequencediagram",
                "classdiagram",
                "statediagram",
                "erdiagram",
                "journey",
                "c4context",
                "c4container",
            )
        ):
            return None
        return text

    @staticmethod
    def _default_mermaid(components: list[Component]) -> str:
        """
        Build a minimal fallback Mermaid graph from the components list so the
        UI always has *something* to render even if the LLM omits the diagram.
        """
        if not components:
            return (
                "graph LR\n"
                "  Client --> ApiGateway[API Gateway]\n"
                "  ApiGateway --> AppSvc[Application Service]\n"
                "  AppSvc --> Db[(Persistence Layer)]"
            )
        lines = ["graph LR", "  Client --> N0"]
        prev = "N0"
        for i, c in enumerate(components):
            # ASCII-only node id; label in brackets, hyphenated to avoid colons
            safe_label = (c.name or f"Component {i + 1}").replace('"', "'").replace(":", " -")
            node = f"N{i}"
            lines.append(f"  {node}[{safe_label}]")
            if i > 0:
                lines.append(f"  {prev} --> {node}")
            prev = node
        return "\n".join(lines)

    # ── Kroki render ─────────────────────────────────────────────────────────

    @classmethod
    def _render_kroki(cls, mermaid_src: str, run_id: str) -> str | None:
        """
        POST raw Mermaid source to kroki.io and return SVG text.
        Returns None on any error - caller treats that as "use mermaid.js fallback".
        """
        if not mermaid_src or not mermaid_src.strip():
            return None
        last_err: str | None = None
        for attempt in range(1, KROKI_MAX_RETRIES + 1):
            try:
                r = requests.post(
                    KROKI_URL,
                    data=mermaid_src.encode("utf-8"),
                    headers={"Content-Type": "text/plain"},
                    timeout=KROKI_TIMEOUT_SEC,
                )
                if r.status_code == 200 and r.text.lstrip().startswith("<"):
                    log.info(f"[{run_id}] Kroki render ok | bytes={len(r.text)}")
                    return r.text
                last_err = f"HTTP {r.status_code}: {r.text[:120]}"
            except requests.RequestException as e:
                last_err = f"{type(e).__name__}: {str(e)[:120]}"
            log.warning(f"[{run_id}] Kroki attempt {attempt}/{KROKI_MAX_RETRIES} failed | {last_err}")
        log.warning(f"[{run_id}] Kroki render skipped - UI will fall back to mermaid.js | {last_err}")
        return None

    # ── Defaults / fallbacks ─────────────────────────────────────────────────

    def _default_components(self) -> list[Component]:
        return [
            Component(
                name="Web/API Gateway",
                responsibility="Receives user and system requests and enforces request validation.",
                technology="FastAPI",
                interfaces=["REST API"],
            ),
            Component(
                name="Application Service",
                responsibility="Coordinates business workflow and domain logic.",
                technology="Python service",
                interfaces=["Internal service calls", "Database client"],
            ),
            Component(
                name="Persistence Layer",
                responsibility="Stores application data, audit trail, and generated artifacts.",
                technology="Managed relational database",
                interfaces=["SQL"],
            ),
        ]

    def _default_nfr(self, citation: str) -> NFRMapping:
        return NFRMapping(
            nfr="Security, availability, and maintainability",
            architecture_decision=(
                "Use validated API boundaries, managed persistence, structured logging, "
                "and conservative deployment topology."
            ),
            citation=citation,
        )

    def _fallback(self, run_id: str, citation_ids: list[str], error: str) -> ArchitectureOutput:
        log.warning(f"[{run_id}] SolutionArchitect fallback | {error[:80]}")
        cite = citation_ids[0] if citation_ids else "arch_patterns_chunk_0"
        comps = self._default_components()
        return ArchitectureOutput(
            run_id=run_id,
            citations=citation_ids or [cite],
            confidence_score=0.2,
            assumptions=["Fallback architecture - agent parse error"],
            flagged_ambiguities=["Architecture output could not be parsed"],
            pattern="Modular monolith with clear service boundaries",
            pattern_justification=(
                "Fallback chooses a conservative pattern that minimizes distributed-system risk "
                "while allowing later extraction of services."
            ),
            components=comps,
            data_flow=[
                "Client sends request to API Gateway",
                "Application Service processes validated request",
                "Persistence Layer stores state and audit records",
            ],
            nfr_mappings=[self._default_nfr(cite)],
            deployment_model="Cloud-managed container deployment",
            diagram_mermaid=self._default_mermaid(comps),
            # diagram_svg left None; run() will try Kroki on this fallback Mermaid too
        )


from src.agents.registry import register_specialist

register_specialist("solution_architect", SolutionArchitectAgent)

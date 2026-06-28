"""
src/core/models.py
══════════════════
Pydantic v2 output contracts for all 7 agents in the EM Copilot pipeline.

Design principle:
    Every agent output inherits from AgentOutputBase, which enforces that
    citations (RAG chunk IDs) are always present. This is the single most
    important field in the system - citations enforce strict grounding of
    all output facts.

    The pipeline state (PipelineState) is the single object passed through
    the LangGraph StateGraph. Each agent reads from it and writes its output
    back to the corresponding field.

Usage:
    from src.core.models import PipelineState, EngineeringPlanOutput
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

# ──────────────────────────────────────────────────────────────────────────────
# Shared Enums
# ──────────────────────────────────────────────────────────────────────────────


class QualityBadge(str, Enum):
    """
    Quality badge assigned by the Critic agent after scoring.
    Displayed in the UI after pipeline completion.

    Thresholds:
        GREEN : overall_score >= 4.0  AND  all dimensions above threshold
        AMBER : overall_score >= 3.0  OR   one dimension below threshold
        RED   : overall_score <  3.0  OR   two+ dimensions below threshold
    """

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class RiskLevel(str, Enum):
    """Standardized risk levels used across plan, PoC, and Critic outputs.

    Four levels, mirrored after standard impact/likelihood matrices used in
    risk management. CRITICAL added so security/compliance-heavy BRDs (PCI,
    HIPAA, SOC 2, etc.) can flag worst-case scenarios without forcing the
    LLM to under-state them as "high".
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HITLDecision(str, Enum):
    """
    Human-in-the-loop decision recorded via React UI approve/reject button.
    Set by the FastAPI POST /approve/{run_id} endpoint.
    """

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    DOWNLOAD_PDF = "download_pdf"


# ──────────────────────────────────────────────────────────────────────────────
# Base class - enforces citations on every specialist agent output
# ──────────────────────────────────────────────────────────────────────────────


class AgentOutputBase(BaseModel):
    """
    Abstract base for all 5 specialist agent outputs.

    The citations field is the most important field in this system.
    Every agent must return at least one Pinecone chunk ID it used
    to ground its output. This is validated at the Pydantic level -
    an empty citations list raises a ValidationError before the
    agent output can be stored in PipelineState.

    Why enforce citations at schema level (not just prompt level):
        Prompts can be ignored by LLMs. Schema validation cannot.
        This guarantees grounding is structural, not aspirational.
    """

    agent_name: str
    run_id: str

    # ── The most important field - do NOT remove or make Optional ─────────────
    citations: list[str] = Field(
        ...,
        min_length=1,
        description=("Pinecone chunk IDs retrieved and used to ground this output. Required on every agent output."),
    )

    confidence_score: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    flagged_ambiguities: list[str] = Field(default_factory=list)

    @field_validator("citations")
    @classmethod
    def citations_must_not_be_empty(cls, v: list[str]) -> list[str]:
        """
        Runtime guard - raises ValidationError if citations list is empty.
        This fires on every agent output before it enters PipelineState.
        """
        if not v:
            raise ValueError("citations must contain at least one Pinecone chunk ID. Agent output is not grounded.")
        return v


class ToolResult(BaseModel):
    """
    Structured response contract from external tools (Tavily search / GitHub metrics).
    Enforces shape validation, keeps track of fallback status, sources, and trust level.
    """

    content: str
    used_fallback: bool
    sources: list[str] = Field(default_factory=list)
    trust_level: str  # e.g., "high" | "medium" | "low"


# ──────────────────────────────────────────────────────────────────────────────
# Agent 1: Orchestrator
# ──────────────────────────────────────────────────────────────────────────────


class BRDSection(BaseModel):
    """
    A single parsed section from the uploaded BRD document.
    Created by the Orchestrator after the Security Validator passes the text.
    """

    section_name: str
    content: str
    word_count: int
    has_nfrs: bool = False  # True if section mentions performance/availability
    has_constraints: bool = False  # True if section mentions constraints/limitations


class OrchestratorOutput(BaseModel):
    """
    Orchestrator output - does NOT inherit AgentOutputBase because the
    Orchestrator does not call RAG or generate content. It only parses,
    validates structure, and builds the routing plan.

    Design decision: Orchestrator is the hub of the hub-and-spoke pattern.
    It fans out to all 5 specialist agents simultaneously via LangGraph
    Send API. It never generates text or calls Pinecone.
    """

    agent_name: str = "orchestrator"
    run_id: str

    # Security: BRD content is hashed, never stored raw in state
    brd_hash: str

    sections: list[BRDSection]

    # Maps each specialist agent to the BRD sections it should focus on
    routing_plan: dict[str, list[str]]

    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)
    retry_count: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Agent 2: Engineering Plan Generator
# ──────────────────────────────────────────────────────────────────────────────


class Milestone(BaseModel):
    """A single deliverable checkpoint within a project phase."""

    name: str
    week: int  # absolute week number from project start
    deliverable: str
    owner_role: str  # e.g. "Tech Lead", "EM", "QA Engineer"


class Risk(BaseModel):
    """
    A project risk with structured likelihood/impact scoring.
    The citation field links each risk back to the RAG source that informed it.
    """

    description: str
    likelihood: RiskLevel
    impact: RiskLevel
    mitigation: str
    citation: str  # Pinecone chunk ID that informed this risk


class Phase(BaseModel):
    """A top-level project phase (e.g. Discovery, Build, Testing, Launch)."""

    name: str
    duration_weeks: int
    objectives: list[str]
    milestones: list[Milestone]


class EngineeringPlanOutput(AgentOutputBase):
    """
    Output of the Engineering Plan Generator agent.

    Uses the Reflection pattern internally:
        Step 1 - Generate draft plan from BRD + RAG context
        Step 2 - Self-critique draft (reflection_notes)
        Step 3 - Produce final structured output

    reflection_notes captures what the agent identified as gaps
    in its own draft - useful for the Critic to review.
    """

    agent_name: str = "engineering_plan_generator"
    phases: list[Phase]
    risks: list[Risk]

    # role → headcount, e.g. {"Senior Engineer": 2, "QA": 1}
    team_composition: dict[str, int]
    total_duration_weeks: int

    # Reflection pattern output - what the agent flagged in its own draft
    reflection_notes: str


# ──────────────────────────────────────────────────────────────────────────────
# Agent 3: Schedule Estimator
# ──────────────────────────────────────────────────────────────────────────────


class SprintRow(BaseModel):
    """A single sprint entry in the project schedule."""

    sprint: int
    week_range: str  # e.g. "W1–W2"
    deliverables: list[str]
    team_members: list[str]
    effort_days: float


class ScheduleOutput(AgentOutputBase):
    """
    Output of the Schedule Estimator agent.

    Calibrated against RAG-retrieved historical project timelines
    (project_timelines.csv in the knowledge base). The comparable_projects
    field records which historical projects were used for calibration.
    """

    agent_name: str = "schedule_estimator"
    sprints: list[SprintRow]
    total_effort_days: float
    critical_path: list[str]
    buffer_weeks: int

    # Pinecone chunk IDs of similar projects used for estimation
    comparable_projects: list[str]


# ──────────────────────────────────────────────────────────────────────────────
# Agent 4: Solution Architect
# ──────────────────────────────────────────────────────────────────────────────


class Component(BaseModel):
    """A named architectural component with its responsibilities and interfaces."""

    name: str
    responsibility: str
    technology: str
    interfaces: list[str]  # e.g. ["REST API", "gRPC", "Kafka topic"]


class NFRMapping(BaseModel):
    """
    Maps a BRD Non-Functional Requirement to an architecture decision.
    Forces the architect to explicitly address each NFR rather than
    generating a generic architecture.
    """

    nfr: str  # e.g. "availability >= 99.9%"
    architecture_decision: str  # how the architecture satisfies this NFR
    citation: str  # Pinecone chunk that informed this decision


class ArchitectureOutput(AgentOutputBase):
    """
    Output of the Solution Architect agent.

    Pattern selection is grounded in the RAG knowledge base (arch_patterns.txt).
    The pattern_justification must explain WHY this pattern over alternatives -
    this is what the Critic checks for actionability.
    """

    agent_name: str = "solution_architect"
    pattern: str  # e.g. "Event-driven microservices"
    pattern_justification: str  # must reference NFRs and constraints
    components: list[Component]
    data_flow: list[str]  # ordered sequence of data movement
    nfr_mappings: list[NFRMapping]
    deployment_model: str  # e.g. "Cloud (AWS EKS)", "Serverless", "Hybrid"

    # ── Diagram (Architecture & PoC design, demo polish) ─────────────
    # diagram_mermaid is the canonical source - generated by the LLM, lossless,
    # and re-renderable downstream (Jira native, Confluence, GitHub README, etc.)
    # diagram_svg is the Kroki-rendered SVG cached for direct UI display.
    # Either may be None if the LLM omitted the diagram or Kroki rendering failed.
    diagram_mermaid: str | None = None
    diagram_svg: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Agent 5: PoC Planner
# ──────────────────────────────────────────────────────────────────────────────


class SuccessCriterion(BaseModel):
    """A measurable criterion for PoC success - must be specific and testable."""

    metric: str  # e.g. "Pipeline completion rate"
    target_value: str  # e.g. ">= 80%"
    measurement_method: str  # e.g. "Automated test suite over 100 runs"


class PoCOutput(AgentOutputBase):
    """
    Output of the PoC Planner agent.

    The PoC hypothesis identifies the RISKIEST assumption in the BRD
    that needs validation before full build begins. This is more valuable
    than a feature-complete PoC - it de-risks the most expensive unknowns.
    """

    agent_name: str = "poc_planner"
    poc_hypothesis: str  # the single riskiest assumption to validate
    scope_in: list[str]
    scope_out: list[str]
    duration_weeks: int
    success_criteria: list[SuccessCriterion]
    team_size: int
    risk_if_poc_fails: str  # what happens to the project if PoC fails


# ──────────────────────────────────────────────────────────────────────────────
# Agent 6: Tech Stack Recommender
# ──────────────────────────────────────────────────────────────────────────────


class StackOption(BaseModel):
    """
    A single technology stack option with structured trade-offs.
    Always 2-3 options - never just one recommendation without alternatives.
    The citation links back to the org's tech decision log in Pinecone.
    """

    name: str
    components: dict[str, str]  # layer → technology
    scalability_rating: int  # 1–5
    team_familiarity_rating: int  # 1–5
    integration_risk: RiskLevel
    estimated_monthly_cost_usd: float
    pros: list[str]
    cons: list[str]
    citation: str  # Pinecone chunk from tech_decision_log


class TechStackOutput(AgentOutputBase):
    """
    Output of the Tech Stack Recommender agent.

    Uses an external tool call (GitHub API) to retrieve team velocity data
    that calibrates the team_familiarity_rating for the recommended option.
    Always produces 2-3 options - enforced by Pydantic min/max constraints.
    """

    agent_name: str = "tech_stack_recommender"
    options: list[StackOption] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Always 2-3 options. Never fewer, never more.",
    )
    recommended_option: str  # must match one of the option names above
    recommendation_rationale: str  # must reference team familiarity + cost + risk


# ──────────────────────────────────────────────────────────────────────────────
# Agent 7: Critic
# ──────────────────────────────────────────────────────────────────────────────


class DimensionScore(BaseModel):
    """
    Score for a single Critic dimension.
    Used to track evaluation improvements.
    """

    score: float = Field(..., ge=0.0, le=5.0)
    threshold: float  # minimum passing score for this dimension
    passed: bool
    evidence: str  # specific justification for this score
    improvement_suggestion: str  # actionable fix sent back to the agent


class ConsistencyIssue(BaseModel):
    """
    A cross-agent inconsistency detected by the Critic.
    Example: Schedule says 8 weeks but Architect designed 14 components.
    This is only possible because one Critic sees ALL outputs simultaneously.
    """

    agents_involved: list[str]
    conflict_description: str
    severity: RiskLevel


class HallucinationFlag(BaseModel):
    """
    A claim in an agent output that is not grounded in BRD or RAG context.
    The Critic's hallucination detection function populates this list.
    """

    agent: str
    claim: str
    status: str  # "supported" | "partially_supported" | "unsupported"
    supporting_chunk_id: str | None = None


class CriticOutput(BaseModel):
    """
    Output of the Critic agent - scores all 5 specialist agents collectively.

    Design: Critic does NOT inherit AgentOutputBase because it scores others,
    it does not generate grounded content itself.

    The 4 validation dimensions and their thresholds:
        groundedness:  >= 3.75  (75% of claims cited)
        completeness:  >= 5.0   (100% of BRD sections addressed)
        consistency:   >= 5.0   (zero cross-agent contradictions)
        actionability: >= 4.0   (EM can act on output immediately)

    critic_scores_history in PipelineState tracks this across revisions
    to produce the before/after improvement table.
    """

    agent_name: str = "critic"
    run_id: str
    revision_number: int  # 0 = first eval, 1 = after revision 1, 2 = final
    target_agents: list[str]

    # The 4 validation dimensions
    groundedness: DimensionScore
    completeness: DimensionScore
    consistency: DimensionScore
    actionability: DimensionScore

    overall_score: float = Field(..., ge=0.0, le=5.0)
    badge: QualityBadge

    # Cross-agent checks - only possible with single shared Critic
    consistency_issues: list[ConsistencyIssue] = Field(default_factory=list)
    hallucination_flags: list[HallucinationFlag] = Field(default_factory=list)

    # Per-agent revision instructions sent back through the loop
    agent_feedback: dict[str, str] = Field(default_factory=dict)
    requires_revision: bool


# ──────────────────────────────────────────────────────────────────────────────
# LangGraph Pipeline State
# ──────────────────────────────────────────────────────────────────────────────


class PipelineState(BaseModel):
    """
    The single shared state object that flows through the LangGraph StateGraph.

    Every node in the graph receives this state, reads what it needs,
    writes its output to the appropriate field, and returns the updated state.
    LangGraph handles state persistence and thread safety.

    Security note:
        brd_raw_hash stores sha256(brd_text) - never the raw BRD content.
        Raw content lives only in brd_sections[].content during the run.

    Eval tracking:
        critic_scores_history accumulates scores across revision cycles.
        This is what generates the before/after improvement table shown
        in the UI eval dashboard.
    """

    run_id: str
    brd_name: str = ""
    processing_time_sec: float = 0.0
    total_input_tokens: int = 0  # Sum across all LLM calls in this run
    total_output_tokens: int = 0  # ── displayed alongside processing time
    model_family: str = "openai"
    enable_fallback: bool = True
    total_cost_usd: float = 0.0

    fallback_occurred: bool = False
    fallback_from: str = ""
    fallback_to: str = ""
    brd_raw_hash: str  # sha256 of original BRD - for audit, never log raw

    # Populated by Orchestrator after Security Validator passes
    brd_sections: list[BRDSection] = Field(default_factory=list)

    # ── Specialist agent outputs (populated as pipeline progresses) ───────────
    plan_output: EngineeringPlanOutput | None = None
    schedule_output: ScheduleOutput | None = None
    arch_output: ArchitectureOutput | None = None
    poc_output: PoCOutput | None = None
    stack_output: TechStackOutput | None = None
    critic_output: CriticOutput | None = None

    # ── Control flow ──────────────────────────────────────────────────────────
    revision_count: int = 0
    hitl_decision: HITLDecision = HITLDecision.PENDING
    hitl_rejection_count: int = 0
    hitl_rejection_notes: list[str] = Field(default_factory=list)
    hitl_latest_note: str = ""
    hitl_em_ratings: list[dict] = Field(
        default_factory=list,
        description=(
            "Human HITL ratings from EM at each gate. "
            "Method 5 eval: {rejection_count, decision, reviewer, em_rating(1-5), notes}"
        ),
    )
    pipeline_status: str = "initializing"
    errors: list[str] = Field(default_factory=list)

    # ── Autonomous tool-call tracking ────────────────────────────────────────
    # Records which external tools were invoked during this run. The Critic
    # uses this to detect a specific class of hallucination: agent invokes a
    # tool but the output contains no citation traceable to that tool's
    # sources (e.g., GitHub velocity numbers reported without a github_api:*
    # citation, or Tavily-grounded claims without a tavily_web_grounding
    # citation). Populated by the integration wrappers via state.tools_used.append().
    tools_used: list[str] = Field(
        default_factory=list,
        description=(
            "Names of external tools invoked during this run "
            "(e.g., 'tavily_search', 'get_github_velocity'). "
            "Critic cross-references with citations to flag unciteed tool usage."
        ),
    )

    # ── Evaluation tracking ─────────
    critic_scores_history: list[dict] = Field(
        default_factory=list,
        description=(
            "Appended after each Critic evaluation. "
            "Used to generate before/after score comparison table in UI. "
            "Format: {revision, groundedness, completeness, consistency, actionability, overall, badge}"
        ),
    )

    class Config:
        arbitrary_types_allowed = True

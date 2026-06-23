# EM Copilot — System Design Reference
**Use this file to onboard Claude Code without feeding the whole project.**
Start every session: "Read Plan.md, Design.md, and State.md. Then [task]."

---

## System Overview

**Product:** EM Copilot — BRD to Engineering Plan Multi-Agent AI System
**Pattern:** Central Orchestrator Hub-and-Spoke (Orchestrator + 5 specialist agents + 1 Critic)
**Protocol:** All specialist messages, Critic feedback, revisions, and HITL decisions route through the Orchestrator. Specialist agents never call each other. Critic never talks to agents directly.

---

## System Design
```
BRD upload
  → Security Validator
  → Orchestrator Hub
      - parses BRD
      - builds routing plan
      - owns PipelineState
      - dispatches specialist tasks
  → Specialist Agents
      - Engineering Plan Generator
      - Schedule Estimator
      - Solution Architect
      - PoC Planner
      - Tech Stack Recommender
  → Orchestrator Aggregator
      - collects all outputs
      - validates Pydantic contracts
      - forwards complete bundle to Critic
  → Critic
      - groundedness
      - completeness
      - consistency
      - actionability
      - cross-agent contradictions
  → Orchestrator Decision Router
      - if Green: HITL approval
      - if Amber/Red and revision_count < 2: dispatch only affected agents
      - if max revisions reached: flag to EM with Amber/Red
  → HITL approval
  → Export Run Summary /log/demo artifacts in Google Sheets
  → Push artifacts to Jira
  -> HITL rejection - end of pipeline.     #audit email
    
```
  
```
Layer 1: BRD Ingestion & Parsing     → Parse uploaded BRDs, extract sections, classify requirements, tag metadata. Security Validator → Doc Parser → FastAPI
Layer 2: Knowledge Augmentation (RAG)    → Ground all agent outputs in past BRDs, templates, patterns, org standards → Pinecone (text-embedding-3-large · dim=10124· top-k=4 · cosine 0.72)
Layer 3: Multi-Agent Generation     → Orchestrator dispatches 5 independent specialist agents and aggregates their outputs
Layer 4: Validation & Evaluation  →  Orchestrator forwards complete bundle to Critic; Critic scores, checks contradictions, and returns feedback to Orchestrator
Layer 5: HITL              → Gate (approve/reject) → if appproved, export & ingest the BRD and all 5 artifacts. If rejected send email with notes from rejection along with BRD and all 5 artifacts.
Layer 6: Output Delivery   → Google Sheets · Google Docs · Mermaid · Markdown · Jira
```

## Architecture — 7 Layers

```
Layer 1: BRD Ingestion     → Security Validator → Doc Parser → FastAPI
Layer 2: RAG               → Pinecone (text-embedding-3-large · top-k=4 · cosine 0.72)
Layer 3: Multi-Agent       → Orchestrator Hub → 5 Specialist Agents → Orchestrator Aggregator
Layer 4: Validation        → Orchestrator → Critic → Orchestrator Decision Router
Layer 5: HITL              → Gate (approve/reject) → if appproved, export Run Summary in Google Sheets & Push the BRD and all 5 artifacts to Jira. If rejected send email with notes + Critic — quality assessment from rejection along with BRD and all 5 artifacts.
Layer 6: Output Delivery   → Google Sheets · Mermaid · Kroki · Jira
Layer 7: Governance        → LangSmith · LangFuse · JSONL logs · security
```

##	Multi-Agents Architecture & Output Contracts 
# Agent	→ Group	→ Primary Responsibility
Agent 1: Orchestrator	→ Orchestration: Route BRD sections to specialist agents; manage state; handle errors and retries.
Agent 2: Engineering Plan Generator	→ Planning: Phases, risks, milestones, team composition. Uses a Reflection self-review step.
Agent 3: Schedule Estimator	→ Planning: Effort estimates, timelines, resource allocation. Aligns to the plan's phases.
Agent 4: Solution Architect	→ Design:  High-level system design, components, data flow, NFR mapping.
Agent 5: PoC Planner → Design: PoC scope, measurable success criteria, modular boundaries.
Agent 6: Tech Stack Recommender	→ Design: 2–3 stack options with trade-offs (scalability, team familiarity, integration risk, cost).
Agent 7: Critic	→ Validation: Score outputs on completeness, consistency, actionability, groundedness. Enforce the revision loop. 

---

## Project Structure

```
engineering-plan-agent/
├── Plan.md                    ← 5-day sprint plan + rubric tracker
├── Design.md                  ← THIS FILE — system design reference
├── State.md                   ← daily progress log
├── README.md                  ← portfolio README
├── requirements.txt
├── Dockerfile
├── .env.example
├── streamlit_app.py           ← UI entry point (NOT YET BUILT)
│
├── src/
│   ├── core/
│   │   ├── models.py          ← ALL Pydantic contracts (✅ COMPLETE)
│   │   ├── config.py          ← pydantic-settings from .env (✅ COMPLETE)
│   │   ├── logger.py          ← JSONL logging + success criteria (✅ COMPLETE)
│   │   └── rag.py             ← Pinecone ingest + retrieve (✅ COMPLETE)
│   ├── agents/
│   │   ├── orchestrator.py    ← BRD parser + routing (✅ COMPLETE)
│   │   ├── critic.py          ← Rubric scoring + revision loop (✅ COMPLETE)
│   │   ├── plan_generator.py  ← BUILT
│   │   ├── schedule.py        ← BUILT
│   │   ├── architect.py       ← BUILT (includes Mermaid + Kroki tool)
│   │   ├── poc_planner.py     ← BUILT
│   │   ├── tech_stack.py      ← BUILT (includes GitHub API tool)
│   │   └── pipeline.py        ← BUILT (LangGraph StateGraph)
│   ├── api/
│   │   └── main.py            ← FastAPI 5 endpoints (✅ COMPLETE)
│   ├── security/
│   │   └── validator.py       ← 7-check security layer (✅ COMPLETE)
│   └── integrations/
│       ├── sheets.py          ← Google Sheets write action (✅ COMPLETE)
│       ├── email.py           ← audit email if rejected (❌ NOT BUILT, optional)
│       └── voice.py           ← ElevenLabs for Voice Interface (✅ COMPLETE)
│
├── knowledge_base/            ← 6 RAG source docs (✅ COMPLETE)
├── eval/                      ← Test BRDs (partial)
├── scripts/
│   └── ingest_kb.py           ← Pinecone KB population (✅ COMPLETE)
└── tests/
    └── unit/test_security.py  ← Security unit tests (✅ COMPLETE)
```

---

## Communication Protocol (Hub-and-Spoke)

```
Step 1: Security Validator → Orchestrator Hub
          validated BRD text + BRD hash

Step 2: Orchestrator Hub → Specialist Agents
          task + run_id + routing_plan + iteration_count + optional critic feedback

Step 3: Specialist Agents → Orchestrator Aggregator
          draft outputs only; specialists do not communicate with each other

Step 4: Orchestrator Aggregator → Critic
          complete artifact bundle after Pydantic validation

Step 5: Critic → Orchestrator Decision Router
          quality scores + badge + agent-specific feedback + consistency findings

Step 6: Orchestrator Decision Router decides:
          Green → HITL approval
          Amber/Red + revision_count < 2 → dispatch only affected agents
          Max revisions reached → flag to EM with Amber/Red and stop revising
```

**Rules:**
- Specialist agents NEVER communicate directly with each other.
- Critic NEVER communicates directly with specialist agents.
- Every revision request is mediated by the Orchestrator.
- The Orchestrator owns `PipelineState`, routing, aggregation, retry policy, and max loop enforcement.

---

## Key Models (src/core/models.py)

All agents output Pydantic models inheriting from `AgentOutputBase`:
```python
class AgentOutputBase(BaseModel):
    agent_name: str
    run_id: str
    citations: list[str]   # REQUIRED — min 1 RAG chunk ID
    confidence_score: float
    assumptions: list[str]
    flagged_ambiguities: list[str]
```

| Agent | Output Model | Key Fields |
|-------|-------------|-----------|
| Orchestrator | OrchestratorOutput | brd_hash · sections · routing_plan |
| Plan Generator | EngineeringPlanOutput | phases · risks · milestones · reflection_notes |
| Schedule | ScheduleOutput | sprints · total_effort_days · critical_path |
| Architect | ArchitectureOutput | pattern · components · nfr_mappings · diagram_svg |
| PoC Planner | PoCOutput | poc_hypothesis · scope_in · success_criteria |
| Tech Stack | TechStackOutput | options (2-3) · recommended_option |
| Critic | CriticOutput | groundedness · completeness · consistency · actionability · badge |

**PipelineState** is the single object flowing through LangGraph StateGraph.

---

## RAG Configuration

```python
PINECONE_INDEX = "brd-knowledge-base"
VECTOR_DIM     = 1024          # text-embedding-3-large
METRIC         = "cosine"
TOP_K          = 4
THRESHOLD      = 0.85
REGION         = "us-east-1"   # free tier only
```

**6 Knowledge Base Sources:**
| File | source_type | Used by |
|------|-------------|---------|
| brd_fintech_payment_portal.txt | brd | Plan Generator, PoC Planner |
| brd_platform_idp.txt | brd | Plan Generator, PoC Planner |
| arch_patterns.txt | arch_pattern | Solution Architect |
| plan_templates.txt | plan_template | Plan Generator, Schedule |
| project_timelines.csv | timeline | Schedule Estimator |
| tech_decision_log.txt | tech_log | Tech Stack Recommender |
| org_engineering_standards.txt | tech_log | Organization's Stadard Tech Stack |

---

## Critic Rubric Thresholds

| Dimension | Threshold | What earns full score |
|-----------|-----------|----------------------|
| Groundedness | ≥ 3.75 | ≥75% of claims have RAG citation |
| Completeness | ≥ 5.0 | 100% BRD sections addressed |
| Consistency | ≥ 5.0 | Zero cross-agent contradictions |
| Actionability | ≥ 4.0 | EM can act immediately |
| **Overall GREEN** | ≥ 4.0 | All dimensions above threshold |

---

## HITL Gate Flow

```
Critic → badge assigned
    ↓
HITL Gate
├── APPROVE → update Dashboard google sheet, export all formats, push to Jira → notify. Voice approval - decision recorded in 11ElevanLabs
└── REJECT → update Dashboard google sheet, rejection_source="hitl" → audit email (all artifacts + both scores). Voice approval - decision recorded in 11ElevanLabs
            → UI: "Email sent for further review"
→ pipeline ends
```

---

## External Tool Calls

| Tool | Used by | Purpose | Auth |
|------|---------|---------|------|
| Pinecone | All 5 agents | RAG retrieval | API key |
| OpenAI | All agents + Critic | LLM generation | API key |
| Kroki.io | Solution Architect | Mermaid → SVG diagram | None (free) |
| GitHub API | Tech Stack | Velocity data | None (public) |
| Tavily | Solution Architect, Tech Stack | Live web grounding fallback | API key |
| Google Sheets | Pipeline export | Write artifacts | Service account |
| Jira | Pipeline export | Formatted report | Service account |
| ElevenLabs | HITL | Voice approval | API key (optional) |

---

## Security Layer (7 checks, in order)

1. File format + size (Python, ~0ms)
2. Document parse (pypdf/docx, ~50ms)
3. Content length min 50 words (Python)
4. Prompt injection — Layer 1: regex patterns (Python, ~1ms)
5. Prompt injection — Layer 2: LLM semantic scan (gpt-4o-mini, ~800ms)
6. PII detection + redaction (Python regex — WARNING not BLOCK)
7. BRD completeness check (keyword matching)

**BRD Storage Decision:** Option A — RAM only, never persisted. Only SHA256 hash logged.

---

## Environment Variables Required

```bash
# Core (required)
OPENAI_API_KEY=
PINECONE_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=em-copilot-brd-agent

# Google (for export)
GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/google_service_account.json
GOOGLE_SHEET_ID=

# Optional
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
```

---

## FastAPI Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /run-pipeline | Upload BRD, start pipeline (background task) |
| GET | /status/{run_id} | SSE stream of live agent progress |
| POST | /approve/{run_id} | HITL decision (approved/rejected) |
| GET | /results/{run_id} | Fetch final artifacts + scores |
| GET | /health | Health check |

---

## How to Run Locally

```bash
# Terminal 1
uvicorn src.api.main:app --reload --port 8000

# Terminal 2
streamlit run streamlit_app.py

# Open: http://localhost:8501
```

## Open-Set Tool Extensibility

To avoid rigid, closed-loop agent behaviors, EM Copilot is designed with **open-set tool extensibility**. Specialist agents can access external capabilities through three distinct integration patterns:

1. **REST Tool Pattern (Direct HTTP Requests)**:
   - Used for **Tavily Web Search**. When the internal RAG system returns no document chunks (`has_no_rag_hits`), the agent executes a direct REST call using `requests.post` to Tavily for live web grounding.
2. **LangChain `@tool` Pattern (Annotated Python Functions)**:
   - Used for the **GitHub API**. The `get_github_velocity` tool is declared using LangChain's `@tool` decorator, encapsulating calls to fetch repository statistics, calculate weekly star velocity, and compute issue close rates.
3. **Model Context Protocol (MCP) Pattern (Subprocess Server integration)**:
   - Used for **Jira Export**. The orchestrator utilizes a Model Context Protocol integration running over a subprocess to create, update, and manage Jira stories/epics.

### Resilient Execution & Shape Validation
- **Conservative Timeouts**: All tool calls are bound to a strict **3.0s timeout** to prevent external API latency from dragging down execution.
- **Circuit Breaking & Retry**: Decorated with `@resilient(policy=TOOL_CALL_POLICY)`, allowing up to **2 attempts** (1 retry) with exponential backoff and jitter.
- **Strict Schema Enforcement**: JSON contracts are validated via Pydantic (`TavilyResponse`, `GitHubRepoResponse`, `GitHubSearchResponse`) to immediately detect shape deviation.
- **Graceful Degradation**: If a tool fails (validation error, network outage, or timeout), the error is caught, logged, and a safe offline fallback string is returned. The agent proceeds using alternative context instead of failing the pipeline.

### Input/Output Security Boundary (Injection Guard)
To prevent prompt injection from propagating into agent generation contexts:
- **Scans on External Outputs**: Every external text snippet (RAG vector chunk, Tavily search result, or GitHub repository description) is scanned using the public helper `check_external_injection(text)`.
- **Dynamic Censorship**: If a regex prompt injection signature is detected:
  - Malicious RAG chunks are dropped entirely.
  - Flagged Tavily search snippets are skipped from the formatting list.
  - Malicious GitHub fields are redacted (e.g. `[Redacted due to security policy]`) or the entire tool response is blocked.

---

## Distributed Resilience & Caching (Phases 1–10)

Production-grade fault tolerance and cost control. The layer mirrors industry-standard distributed-systems libraries (Hystrix / Polly / resilience4j) but is implemented in <250 lines to keep the surface area small and the dependency footprint zero.

### Decorator Stack (call-site composition)

```
┌─────────────────────────────────────────┐
│ @cached(policy=CACHE_POLICY, key_fn=K)  │   ← Phase 1+2+5: cache hit short-circuits
│ ┌─────────────────────────────────────┐ │
│ │ @resilient(policy=POL, breaker=BRK) │ │   ← Phase 1+3: timeout · retry · breaker
│ │ ┌─────────────────────────────────┐ │ │
│ │ │ provider call (OpenAI/Pinecone) │ │ │
│ │ └─────────────────────────────────┘ │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

Order matters: `@cached` runs **outside** `@resilient`, so a cache hit avoids the breaker entirely. On a miss, the resilient layer applies hard timeout (ThreadPoolExecutor), jittered exponential backoff retry, and per-instance circuit breaker.

### Per-Instance State, Shared Code

The pattern is *shared code, never shared state*. `src/core/resilience.py` exports `CallPolicy` (frozen dataclass), `CircuitBreaker` class, and the `@resilient` factory — that's it. Each agent class and each external service **owns its own breaker instance**, registered in a module-level dict keyed by class name:

```python
_LLM_BREAKERS: dict[str, CircuitBreaker] = {}
_LLM_BREAKER_LOCK = threading.Lock()

def _get_llm_breaker(agent_class_name: str) -> CircuitBreaker:
    with _LLM_BREAKER_LOCK:
        if agent_class_name not in _LLM_BREAKERS:
            _LLM_BREAKERS[agent_class_name] = CircuitBreaker(...)
        return _LLM_BREAKERS[agent_class_name]
```

A failing `PlanGeneratorAgent` cannot open the `ScheduleEstimatorAgent` breaker. RAG retrieval and embedding calls have their own breakers in `rag.py`.

### Cache Backends (Pluggable via Protocol)

| Backend | Purpose | Activation |
|---|---|---|
| `InMemoryCache` | L1 — LRU + TTL, per-process | Always |
| `RedisCache` | L2 — pickle+gzip, shared across replicas | `REDIS_URL` env var set |
| `TieredCache` | Composes L1 + L2 (read L1 first, back-fill on L2 hit, write-through) | Auto when both present |
| `SemanticBackend` | Pinecone cosine similarity (`namespace="llm-cache"`, threshold 0.95) | Critic opt-in |

`init_default_backend_from_env()` runs at FastAPI startup and selects the backend based on environment. The Redis layer degrades gracefully: a failed healthcheck or mid-flight error logs once and falls back to L1.

### Per-Agent Policy Manifest

`BaseAgent` declares:

```python
class BaseAgent:
    CACHE_POLICY:      CachePolicy = CACHE_LLM
    RESILIENCE_POLICY: CallPolicy  = OPENAI_POLICY
```

Subclasses override these to tune TTL, timeout, retry count, or breaker thresholds without touching `_call_llm_with_retry`. The Critic, for example, opts into the `SemanticBackend` by setting its `CACHE_POLICY` accordingly. This is the Phase 5 extensibility win — adding a new agent with custom resilience characteristics is a two-line change.

### Specialist Registry (Phase 4)

`src/agents/registry.py` exposes `register_specialist(name, cls)` and `get_specialist(name)`. Each specialist module calls `register_specialist()` at import time, and `pipeline._run_agent()` dispatches via lookup instead of an `if/elif` chain. Adding a new specialist requires no edits to `pipeline.py`.

### Per-Agent Bulkhead (Phase 9)

`node_dispatch_specialists` submits agents to a `ThreadPoolExecutor` and consumes via `as_completed(futures, timeout=AGENT_TIMEOUT_SEC)`. If the budget elapses, the bulkhead cancels pending futures, emits `bulkhead_timeout` events, and proceeds with whatever completed. Stragglers cannot drag down the rest of the pipeline.

### Observability Bus (Phase 10)

`src/core/events.py` exports `set_event_sink(fn)` and `emit(event_type, **fields)`. The cache and resilience layers emit:

- `cache_hit` / `cache_miss` (with backend name, key prefix)
- `retry` (attempt number, exception type)
- `breaker_open` / `breaker_short_circuit` / `breaker_half_open`
- `bulkhead_timeout` (agent name, budget)

The bus best-effort attaches the current thread's `run_id` (via thread-local from `base_agent`) so events correlate to a specific run. FastAPI wires the sink at startup and fans events into the SSE stream consumed by the Streamlit UI. The bus never raises — observability cannot break the caller.

### Why Custom Instead of Hystrix-Py / pybreaker / aiocache

| Library | Why not chosen |
|---|---|
| `pybreaker` | Only does the breaker — no integrated retry/timeout/cache stack |
| `tenacity` | Retry-only; we previously used it and removed it in Phase 1 |
| `aiocache` | Async-first; our codebase is sync (ThreadPoolExecutor parallelism) |
| `cachetools` | LRU only; no TTL, no semantic, no pluggable backend |
| Hystrix-Py | Unmaintained; heavyweight |

The custom layer is ~600 lines total (resilience + cache + events) and has zero non-stdlib dependencies (except optional `redis`, only imported when `REDIS_URL` is set).

---

## Test Commands

```bash
# Unit tests
pytest tests/ -v

# KB population
python scripts/ingest_kb.py

# KB health check
python scripts/ingest_kb.py --check-only

# Retrieval test
python scripts/ingest_kb.py --test-only
```

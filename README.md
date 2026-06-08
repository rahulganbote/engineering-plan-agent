---
title: EM Copilot
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: BRD to Engineering Plan Multi-Agent System
---

# EM Copilot — BRD to Engineering Plan Agent

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.28-green)](https://github.com/langchain-ai/langgraph)
[![Pinecone](https://img.shields.io/badge/RAG-Pinecone-purple)](https://pinecone.io)
[![LangSmith](https://img.shields.io/badge/Observability-LangSmith-orange)](https://smith.langchain.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io)
[![Jira](https://img.shields.io/badge/Jira%20Epic-MCP%20%2B%20REST-0052CC)](https://www.atlassian.com/software/jira)
[![ElevenLabs](https://img.shields.io/badge/Voice%20HITL-ElevenLabs-1F1F1F)](https://elevenlabs.io)
[![Slack](https://img.shields.io/badge/Alerts-Slack-4A154B)](https://slack.com)

> **EM Copilot** is a state-of-the-art, 7-Agent system built using LangGraph. It transforms a raw Business Requirements Document (BRD) into an audit-ready engineering bundle: plan, project schedule, Kroki-rendered system architecture diagram, PoC definition, and tech stack options. The bundle is dynamically evaluated by a Critic Agent, reviewed via a Human-in-the-Loop (HITL) gate (supporting Voice AI commands or UI actions), and deployed directly to Jira Cloud, Google Sheets, and downloadable PDF report cards.

---

## Table of Contents
1. [Business Use Case & Solution](#business-use-case--solution)
2. [Core Pillars](#core-pillars)
3. [Architectural Overview](#architectural-overview)
4. [Agent Design Patterns](#agent-design-patterns)
5. [Tech Stack Justification](#tech-stack-justification)
6. [Security & Validation Pipeline](#security--validation-pipeline)
7. [Vector DB & RAG Integration](#vector-db--rag-integration)
8. [Distributed Resilience & Cache Layer](#distributed-resilience--cache-layer)
9. [Evaluation Framework](#evaluation-framework)
10. [Integrations & External Channels](#integrations--external-channels)
11. [Token Usage & Execution Cost](#token-usage--execution-cost)
12. [Project Directory Structure](#project-directory-structure)
13. [Quick Start Guide](#quick-start-guide)
14. [Failure Modes & Mitigations](#failure-modes--mitigations)
15. [Observability & Tracing](#observability--tracing)
16. [License](#license)
17. [Author](#author)


---

## Business Use Case & Solution

### The Challenge
Engineering Managers (EMs) face a persistent bottleneck in translating complex Business Requirements Documents (BRDs) into structured technical plans, schedules, and architecture diagrams. This manual process is time-consuming and frequently results in:
*   **Delivery Delays:** Weeks spent drafting sprint scopes, mapping timelines, and aligning teams.
*   **Misalignment:** Gaps between business intent (BRD requirements) and engineering implementation.
*   **Inconsistent Scoping:** Ad-hoc architectures and planning criteria that vary wildly across engineering squads.

### The EM Copilot Solution
**EM Copilot** addresses these bottlenecks by building a multi-Agent workflow that ingests raw BRDs and produces a complete, audit-ready engineering bundle. The system matches the business opportunity in five key areas:

*   **Faster Turnaround:** RAG-augmented specialist Agents reference past projects and templates, eliminating the need to write generic boilerplate drafts from scratch.
*   **Standardized, Validated Planning:** A Critic Agent checks all planning outputs for completeness, consistency, and alignment before they are exposed to the user.
*   **Grounded Intelligence:** Integrating a Pinecone RAG vector store ensures architectural decisions and project guidelines are grounded in organization standards and historical project data.
*   **Evaluated Outputs:** Validated outputs for quality and scored based on 5 criterion to detect Hallucination, checking for citation, so Artifacts carry clear Green / Amber / Red quality badges based on exact evaluation criteria.
*   **EM Enablement:** Generates decision-ready artifacts complete with source citations, allowing the EM to serve as an editor and approver rather than starting from a blank page.

---

## Core Pillars

| Capability | Engineering Implementation |
|---|---|
| **7-Agent LangGraph Pipeline** | Parallel execution via `ThreadPoolExecutor` (Orchestrator + 5 Specialists + Critic) |
| **Pydantic-Enforced Output Contracts** | Zero untyped LLM handoffs, schema conformance validated at every transition |
| **Deterministic Security Layer** | 7-check security pipeline (length, extension, regex, semantic scan, PII redact) |
| **Pinecone RAG Vector Search** | Dynamic retrieval with document citation mapping and diversity checks |
| **Critic Revision Loop** | LLM-as-Judge - Self-correction mechanism (capped at 2 loops) with 3 failure-mode caps (Hallucination Guard, Uncited Claim Cap, Sentinel Fallback Cap) |
| **Distributed Resilience Layer** | Per-instance circuit breakers, jittered exponential backoff, hard timeouts (ThreadPoolExecutor), per-agent bulkheads with cancellation — modeled on Hystrix/Polly/resilience4j |
| **Two-Tier Cache (L1 + L2)** | In-process LRU+TTL (L1) + optional Redis L2 (pickle+gzip, graceful degradation), Pinecone-backed semantic cache for the Critic |
| **Specialist Registry & Policy Manifest** | Decoupled dispatch via `register_specialist()`; per-agent `CACHE_POLICY` / `RESILIENCE_POLICY` class attributes for per-call-site tuning |
| **Visual Architecture Renderer** | LLM Mermaid syntax validated & rendered to SVG via Kroki API with local JS fallback | 
| **ElevenLabs Voice HITL Gate** | Conversational human approval webhook accepting numeric ratings and text feedback | 
| **Jira Epic Creation via MCP** | Creates a Jira **Epic** through an `mcp-atlassian` MCP server (stdio transport); automatic fallback to the REST API + ADF body if MCP is unavailable |
| **Google Sheets Logging** | Comprehensive audit export used to power a historical insights dashboard, with local CSV fallback for air-gapped runs |
| **Slack Failure Alert** | Incoming-webhook alert on any pipeline error so the EM sees failed runs in real time |
| **BRD Pinecone Ingestion** | Upon approval, the BRD is ingested in Pinecone |
| **ReportLab PDF Exporter** | One-click downloadable PDF summary enclosing all generated planning artifacts |
| **LangSmith Telemetry** | Full trace visualization covering model tokens, prompts, inputs, and latency |

---

## Architectural Overview

```
                         ┌─────────────────────────────────────────────────┐
                         │         SECURITY VALIDATION LAYER               │
BRD Upload ──► FastAP ──►│  File check → Parse → Injection Guard (regex)   │
(Streamlit)     POST     │  → Injection Guard (LLM) → PII Redact → BRD ✓   │
            run-pipeline └─────────────────────────────────────────────────┘
                                              │ validated BRD text
                                              ▼
                                    Orchestrator Agent
                                    (hub — parses, routes sections)
                                              │
                                              ▼
            ┌─────────────────────────────────────────────────────────────────────────┐
            │ ThreadPoolExecutor │ (parallel dispatch) │             │                │
            ▼                    ▼                     ▼             ▼                ▼
    Plan Generator    Schedule Estimator  Solution Architect  PoC Planner  Tech Stack Recommender
    (RAG + Reflect)   (RAG + Timelines)   (RAG + Diagram)   (RAG + Timelines) (RAG + Org Stds)
            │                     │    (Mermaid+Kroki) │                 │           │ 
            ▼                     ▼                    ▼                 ▼           ▼ 
            └─────────────────────└────────────────────────┘─────────────────└───────────┘
                                    │                       
                                    ▼       ◄──── all 5 outputs together  
                             Critic Agent  
                            (LLM-as-judge + FM-1/2/3 caps)
                                    │
                     ┌──────────────┴───────────────┐
                     │  score < threshold?          │
                     │  revision_count < 2?         │
                     ▼ yes                          ▼ no
              ↻ Targeted revision           HITL Approval Gate
              (only flagged Agents)         (Button OR Voice via ElevenLabs)
                                                    │
                        ┌───────────────────────────┼───────────────────────────┐
                        │                           │                           │
                        ▼ Approved                  ▼ Rejected                  ▼
          Sheets + Jira Epic (MCP) + Pinecone   Sheets audit row only              (wait)
```

---

## Agent Design Patterns

### 1. Parallel Dispatch (Hub-and-Spoke)
Instead of sequentially chaining Agent calls, the Orchestrator splits the incoming BRD sections and routes them to all five specialist Agents concurrently using Python's `ThreadPoolExecutor`. This reduces total wall-clock execution time by **~3×** (~50 seconds compared to >2.5 minutes sequentially).

### 2. Multi-Agent Aggregate Criticism
The Critic node serves as a secondary routing hub. Rather than verifying each Agent individually, it acts on the aggregated `PipelineState` containing all 5 specialist outputs. This global view enables it to catch cross-specialist contradictions, such as the *Schedule Estimator* planning a 12-week project while the *Solution Architect* designs 25 separate microservices for a 2-engineer team.

### 3. Targeted Revision Loop
If the Critic flags issues, the pipeline does not rerun from scratch. Instead, it runs a selective revision loop (max 2 cycles). The loop only invokes the specialist Agents that were flagged with a quality score below the acceptable threshold.

### 4. Deterministic Failure-Mode Caps (FM-1/2/3)
To prevent the LLM Critic from being overly optimistic (a common LLM-as-Judge failure mode), three deterministic rules override the Critic's scoring logic:
*   **FM-1 (Hallucination Guard):** Deducts `0.3` points from the overall score for every citation that does not match retrieved vector database keys.
*   **FM-2 (Uncited Claim Cap):** Caps the overall score at `3.9` (Amber) if any specialist Agent fails to reference at least one vector chunk.
*   **FM-3 (Sentinel Fallback Cap):** If an Agent fails or experiences an API timeout, the pipeline falls back to safe mock structures with a low confidence score (`≤ 0.30`). The Critic immediately caps the overall quality rating to `3.9` (Amber) and flags a `ConsistencyIssue` in the UI to prevent silent failures.

### 5. Specialist Registry (Decoupled Dispatch)
Specialist agents register themselves at import time via `register_specialist("plan_generator", PlanGeneratorAgent)`. The pipeline's `_run_agent()` looks up the class via `get_specialist(name)` instead of a hardcoded `if/elif` chain. Adding a new specialist becomes a two-line change (one register call + one entry in the dispatch list) instead of touching multiple files.

### 6. Per-Agent Policy Manifest
Each `BaseAgent` subclass declares two class-level attributes — `CACHE_POLICY: CachePolicy` and `RESILIENCE_POLICY: CallPolicy`. The shared `_call_llm_with_retry` reads `self.CACHE_POLICY` / `self.RESILIENCE_POLICY`, so individual agents can tune TTL, timeout, retry count, or circuit-breaker thresholds without touching base infrastructure. Defaults come from `CACHE_LLM` / `OPENAI_POLICY`.

### 7. Two-Tier Cache with Graceful Degradation
The cache layer composes `InMemoryCache` (L1: LRU + TTL, always on) with optional `RedisCache` (L2: pickle+gzip, ~70% size reduction). `TieredCache` checks L1 first, falls through to L2, and back-fills L1 on L2 hits. When `REDIS_URL` is unset, only L1 runs. When Redis fails mid-flight, the pipeline degrades to L1 only, logs the degradation, and recovers automatically on the next successful call.

### 8. Per-Instance Circuit Breakers (Isolation)
Each agent class and each external service owns its own `CircuitBreaker`. A module-level registry keyed by class name (`_get_llm_breaker(class_name)`) ensures that one agent's failures cannot open another's breaker. RAG retrieval and embedding calls have separate breakers from LLM calls. This is the same isolation pattern Hystrix/resilience4j use for production fault tolerance — shared CODE, never shared STATE.

---

## Tech Stack Justification

| Category | Technology | Engineering Reason |
|---|---|---|
| **Agent State** | LangGraph v0.2.28 | State Graph model with native routing, cycle tracking, and async interrupts |
| **Vector DB** | Pinecone Serverless | Fully managed index with fast cosine-similarity search over technical standards |
| **Embeddings** | `text-embedding-3-large` (1024) | High dimensionality with customized text projection for dense architectural guides |
| **Models** | GPT-4o (specialists) + GPT-4o-mini (critic) | Balance between specialist reasoning quality and critic execution cost |
| **Web Server** | FastAPI | Async endpoints, Server-Sent Events (SSE) for UI streaming, and non-blocking exports |
| **Frontend UI** | Streamlit | Rapid UI prototyping displaying real-time execution graphs and progress logs |
| **Voice Interface** | ElevenLabs Conversational AI | Webhook integration executing natural language HITL discussion & approvals |
| **Tool Integration** | Model Context Protocol (MCP) | Standardized Agent-to-Tool transport; the Jira Epic push runs through an `mcp-atlassian` server spawned over stdio |
| **Resilience Primitives** | Custom `src/core/resilience.py` (mirrors Hystrix / Polly / resilience4j) | Small surface area, no external dependency; per-instance state with frozen `CallPolicy` |
| **Cache Backends** | `InMemoryCache` / `RedisCache` / `TieredCache` / `SemanticBackend` (Pinecone) | Pluggable `CacheBackend` Protocol — chosen at runtime via `init_default_backend_from_env()` |
| **Event Bus** | Lightweight `src/core/events.py` emitter | Best-effort event fan-out for `cache_hit`, `cache_miss`, `retry`, `breaker_open`, `bulkhead_timeout`; surfaced into Streamlit SSE stream |

---

## Security & Validation Pipeline

Before any LLM node processes a user-uploaded document, the file passes through a strict, sequential 7-check security pipeline:
1.  **Format Restriction:** Restricts file extensions to `.txt`, `.pdf`, and `.docx`.
2.  **Size Guard:** Enforces a hard 10MB limit (preventing Denial of Service / resource exhaustion).
3.  **Word Check:** Ensures the document contains at least 50 words to avoid parsing empty text.
4.  **Regex Injection Guard:** Scans for 15 known LLM jailbreak and injection strings (e.g., `"ignore all previous instructions"`).
5.  **Semantic Injection Guard:** A lightweight GPT-4o-mini scan to detect sophisticated, multi-paragraph prompt injections.
6.  **PII Sanitizer:** Identifies and redacts Social Security Numbers, Credit Cards, email addresses, and phone numbers with placeholders (e.g., `[REDACTED-SSN]`).
7.  **Completeness Check:** Inspects the parsed text structure to confirm key sections (Objectives, Requirements, Constraints, Risks, NFRs) are present.

---

## Vector DB & RAG Integration

The vector database stores organization-specific architectural patterns, planning templates, and historical schedules.
*   **Ingestion:** The ingestion tool `scripts/ingest_kb.py` parses documents from `knowledge_base/`, splits them using a dynamic recursive character text splitter, embeds them via `text-embedding-3-large` (1024 dimensions), and writes them to Pinecone with metadata tags (`source_type`, `chunk_id`).
*   **Retrieval:** During execution, each specialist Agent retrieves relevant context using a similarity search. A similarity threshold of `0.45` is enforced.
*   **Citation Tracking:** Specialists must return exact citations (`source_file` + `chunk_id`) for any technical standard referenced in their plan. The Critic enforces that these references are present and match valid chunks.

---

## Distributed Resilience & Cache Layer

EM Copilot ships with a production-grade resilience and caching layer modeled on the Hystrix / Polly / resilience4j family of distributed-systems libraries. The goal is simple: **no single external dependency (OpenAI, Pinecone, Redis) should be able to take the pipeline down**, and repeated work (Critic revisions, retried agents, redundant queries) should not pay the LLM cost twice.

### Decorator Composition

Every external call site composes two decorators in a strict order:

```python
@cached(policy=self.CACHE_POLICY, key_fn=_llm_key, name="llm.chat")
@resilient(policy=self.RESILIENCE_POLICY, breaker=breaker, name="llm.chat")
def _call(...):
    return client.chat.completions.create(...)
```

`@cached` runs **outside** `@resilient`, so a cache hit short-circuits before the breaker even sees the call. On a cache miss, `@resilient` applies the timeout, the retry policy, and the circuit breaker. The pattern is applied at three layers: LLM calls in `BaseAgent`, RAG retrieval and embeddings in `rag.py`, and (configurably) the Critic.

### Two-Tier Cache

| Layer | Backend | When it runs | Notes |
|---|---|---|---|
| **L1** | `InMemoryCache` (LRU + TTL) | Always | Per-process; survives only the container lifetime |
| **L2** | `RedisCache` (pickle+gzip) | When `REDIS_URL` is set | Shared across replicas; ~70% size reduction on LLM responses |
| **Semantic** | `SemanticBackend` (Pinecone, `namespace="llm-cache"`, cosine threshold `0.95`) | Critic opt-in only | Catches near-equivalent queries even when text differs slightly |

The Critic opts into the semantic cache by default because revision loops produce highly-similar critique prompts; specialists do not, to protect free-tier Pinecone quota. The single Pinecone index is shared with the RAG corpus via separate namespaces — no extra index to provision.

### Per-Agent Bulkhead

`pipeline.py` dispatches specialists through a `ThreadPoolExecutor` and consumes them via `as_completed(futures, timeout=AGENT_TIMEOUT_SEC)`. A slow agent cannot drag down the rest: when the budget elapses, pending futures are cancelled, the timed-out agent's slot is filled with the Sentinel Fallback (which the Critic caps at FM-3 Amber), and the pipeline continues. Default budget is `90s` per agent (tunable via `AGENT_TIMEOUT_SEC`).

### Per-Instance Circuit Breakers

Each agent class has its own breaker, keyed by class name in a module-level registry. RAG retrieval and embeddings have separate breakers from LLM calls. When a breaker opens after N consecutive failures, subsequent calls fast-fail with `CircuitOpenError` (which the agent catches and routes to its Sentinel Fallback) until the cooldown elapses and the breaker enters half-open state. **One failing dependency cannot cascade to take down others.**

### Observability Bus

A lightweight `src/core/events.py` emitter publishes structured events — `cache_hit`, `cache_miss`, `retry`, `breaker_open`, `breaker_short_circuit`, `bulkhead_timeout` — onto a thread-local channel keyed by `run_id`. FastAPI wires the sink at startup and fans events into the SSE stream, so the Streamlit UI sees them in real time alongside Agent progress chips. The bus is best-effort and never raises, so observability cannot break the caller.

### Graceful Degradation Matrix

| Failure | Behavior | Recovery |
|---|---|---|
| Redis unreachable | Logged once, L1 only | Auto-restored on next successful call |
| OpenAI 429 / 503 | Retry with jittered backoff, breaker after N failures | Half-open after cooldown |
| Pinecone timeout | Embedding/retrieval breaker opens; agents proceed with cached or empty RAG | Half-open after cooldown |
| Agent exceeds bulkhead budget | Pending futures cancelled; Sentinel Fallback returned; Critic caps at FM-3 Amber | Next run unaffected |
| MCP Jira server down | REST fallback (Phase 7 idempotency label prevents double-write) | None needed |

---

## Evaluation Framework

Our evaluation suite (`eval/run_eval.py`) verifies pipeline updates across 5 key dimensions:

```
                  ┌───────────────────────────────────────────┐
                  │          5-WAY EVALUATION SYSTEM          │
                  └─────────────────────────┬─────────────────┘
                                            │
         ┌───────────────────┬──────────────┼──────────────────┬──────────────────┐
         ▼                   ▼              ▼                  ▼                  ▼
     Rule-Based         LLM-as-Judge    Execution          BERTScore          Human HITL
    (Structural)       (Rubric Score)    (Schema)       (Semantic Diff)     (User Rating)
```

1.  **Method 1: Rule-Based Evaluation**
    *   *Metric:* Deterministic structural assertions (minimum milestone count, 100% of milestones having assigned owners, citation formats).
    *   *Dataset:* Run on all test files (`test_brd_simple.txt`, `test_brd_medium.txt`, `test_brd_complex.txt`, etc.).
2.  **Method 2: LLM-as-Judge**
    *   *Metric:* 0-5 scores for Groundedness (citations presence), Completeness, Consistency, and Actionability.
    *   *Dataset:* Calibration set anchored via `critic_calibration_set.json`.
3.  **Method 3: Execution-Based**
    *   *Metric:* Pydantic validation pass rate (100% target), Kroki SVG rendering checks, and pipeline execution time (<300s SLA).
4.  **Method 4: Reference-Based (BERTScore)**
    *   *Metric:* Semantic similarity matching (BERTScore F1) of generated text fields against golden ground-truth files (`expected_output_simple.json`, `expected_output_medium.json`).
5.  **Method 5: Human HITL**
    *   *Metric:* 1-5 rating scores and text feedback logs submitted at the HITL approval step.

### Evaluation Results (v0 to v1 Improvement)

The Critic loop drives a significant quality improvement, as demonstrated in our test runs:

| Version | Groundedness | Completeness | Consistency | Actionability | Overall Score | Badge |
|---|---|---|---|---|---|---|
| **v0 (Initial)** | 2.40 | 3.80 | 4.10 | 3.20 | **3.38 / 5.00** | 🟡 Amber |
| **v1 (Post-Critic)** | 3.90 | 4.80 | 4.60 | 4.00 | **4.33 / 5.00** | 🟢 Green |
| **Net Delta** | **+1.50** | **+1.00** | **+0.50** | **+0.80** | **+0.95** | **+1 Badge** |

For a complete breakdown of evaluation methods and the LangSmith trace logs, see [EVAL_RESULTS.md](file:///Users/rahul/Library/CloudStorage/OneDrive-Personal/Rahul/InterviewKickstart/AgenticAI/Capstone_Project/BRD_to_Engineering_Agent/engineering-plan-agent/docs/EVAL_RESULTS.md).

---

## Integrations & External Channels

The pipeline exposes four automated output integrations triggered only upon human approval:
*   **Google Sheets Export:** Writes the complete state (summary, phases, schedule, stack) as a multi-tab row log using `gspread` to power a centralized historical insights dashboard. If credentials or network connection are missing, it falls back to writing CSV bundles locally in `logs/exports/<run_id>/`.
*   **Jira Epic Integration (MCP):** On approval, creates a Jira **Epic** by calling an `mcp-atlassian` MCP server over stdio transport (MCP handshake → `list_tools` → `jira_create_issue`). If the server cannot be spawned, it falls back to a direct REST call. Either path builds the Epic description in Atlassian Document Format (ADF), containing the Critic's quality scores, architectural components, NFR mappings, and a link to the rendered Kroki architecture diagram.
*   **Kroki.io SVG Render:** Converts Mermaid markup into a rendered SVG schema. If Kroki is down, the Streamlit frontend falls back gracefully to local client-side `mermaid.js` rendering.
*   **PDF Exporter (ReportLab):** Generates a structured PDF document containing the full engineering plan, phase breakdowns, and critic badges on a local endpoint (`/download/{run_id}`).

---

## Token Usage & Execution Cost

Below is the token usage and cost breakdown for a single full execution of the EM Copilot pipeline (using a standard 5-section BRD):

### Models in Use & Rate Limits
*   **Specialist Agents:** `gpt-4o` (optimal reasoning & schema compliance)
    *   Max Response Tokens: 4096 per response
    *   Rate Limit: 150,000 input tokens/minute (Tier 1 standard)
*   **Orchestrator & Critic:** `gpt-4o-mini` (fast, highly cost-effective)
    *   Max Response Tokens: 4096 per response
    *   Rate Limit: 200,000 input tokens/minute

### Detailed Token & Cost Breakdown per Call
| Phase / Agent | Model | Input Tokens | Output Tokens | Total Tokens | Cost (USD) |
|---|---|---|---|---|---|
| **Security Validator** | `gpt-4o-mini` | ~1,000 | ~100 | ~1,100 | ~$0.0002 |
| **Orchestrator Hub** | `gpt-4o-mini` | ~1,500 | ~500 | ~2,000 | ~$0.0005 |
| **Plan Generator** | `gpt-4o` | ~5,000 | ~2,500 | ~7,500 | ~$0.0625 |
| **Schedule Estimator** | `gpt-4o` | ~4,000 | ~1,500 | ~5,500 | ~$0.0425 |
| **Solution Architect** | `gpt-4o` | ~6,000 | ~3,000 | ~9,000 | ~$0.0750 |
| **PoC Planner** | `gpt-4o` | ~4,000 | ~1,500 | ~5,500 | ~$0.0425 |
| **Tech Stack** | `gpt-4o` | ~4,000 | ~1,500 | ~5,500 | ~$0.0425 |
| **Critic Agent** | `gpt-4o-mini` | ~10,000 | ~1,000 | ~11,000 | ~$0.0021 |
| **Total per Run** | — | **~39,500** | **~11,600** | **~51,100** | **~$0.31** |

> [!TIP]
> A full run costs approximately **$0.31 USD** end-to-end. This parallel execution is managed well within standard Tier 1 OpenAI rate limits (supporting up to 3 parallel pipeline runs per minute).

---

## Project Directory Structure

```
engineering-plan-agent/
│
├── README.md                       ← system documentation
├── requirements.txt                ← locked dependencies
├── Dockerfile                      ← Docker build configuration
├── .env.example                    ← environment configuration keys template
│
├── src/                            ← application source code
│   ├── core/
│   │   ├── models.py               ← Pydantic schemas and pipeline state contracts
│   │   ├── config.py               ← configuration settings loader
│   │   ├── rag.py                  ← vector store ingestion and retrieval logic (cached + resilient)
│   │   ├── cache.py                ← CachePolicy, backends (InMemory / Redis / Tiered / Semantic), @cached
│   │   ├── resilience.py           ← CallPolicy, CircuitBreaker, @resilient, sensible defaults
│   │   ├── events.py               ← observability event bus (cache_hit / retry / breaker_open ...)
│   │   └── logger.py               ← JSONL logger with criteria trackers
│   ├── agents/
│   │   ├── base_agent.py           ← shared agent class wrapping LLM calls (per-agent breaker registry)
│   │   ├── registry.py             ← specialist dispatch registry (register/get_specialist)
│   │   ├── orchestrator.py         ← BRD parser and specialist dispatcher
│   │   ├── plan_generator.py       ← reflection-based project plan creator
│   │   ├── schedule.py             ← effort and sprint schedule estimator
│   │   ├── architect.py            ← Mermaid diagram generator and Kroki client
│   │   ├── poc_planner.py          ← PoC planner defining success metrics
│   │   ├── tech_stack.py           ← technology options analyzer
│   │   ├── critic.py               ← quality auditor and revision loop controller
│   │   └── pipeline.py             ← LangGraph orchestrator state graph
│   ├── api/
│   │   └── main.py                 ← FastAPI web server endpoints
│   ├── security/
│   │   └── validator.py            ← 7-check security sanitization layers
│   └── integrations/
│       ├── sheets.py               ← Google Sheets gspread connector (idempotent on run_id)
│       ├── jira.py                 ← Jira Cloud REST client (idempotency label: em-copilot-run-<id>)
│       ├── jira_mcp.py             ← MCP-client Jira Epic integration (mcp-atlassian)
│       ├── export_registry.py      ← pluggable export-handler registry
│       ├── pdf_export.py           ← ReportLab PDF generator
│       ├── voice.py                ← ElevenLabs webhook connector
│       └── email.py                ← email notification handler
│
├── knowledge_base/                 ← RAG engineering standards text assets
├── eval/                           ← test BRD scenarios & run_eval.py
├── scripts/                        ← administrative deployment helper scripts
├── tests/                          ← unit & integration tests
├── docs/                           ← system architecture design, architectural diagrams, sprint implementation schedule, progress log & scripts
└── logs/                           ← execution telemetry and export files
```

---

## Quick Start Guide

### 1. Installation

Clone this repository, initialize your virtual environment, and install dependencies:
```bash
git clone https://github.com/morya99/engineering-plan-agent.git
cd engineering-plan-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Create your environment configuration:
```bash
cp .env.example secrets/.env
```
Fill out the keys in `secrets/.env`. Standard required keys are:
*   `OPENAI_API_KEY`
*   `PINECONE_API_KEY`


For observability and integrations, configure:
```env
# LangSmith Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=em-copilot-brd-agent

# External Services (Optional)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@domain.com
JIRA_API_TOKEN=your_jira_token
JIRA_PROJECT_KEY=SCRUM
JIRA_ISSUE_TYPE   # Task or "Epic"
JIRA_LABEL_PREFIX     # optional; defaults to em-copilot

GOOGLE_SHEET_ID=your_sheet_id
# Place google service account credentials in secrets/google_service_account.json

ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_AGENT_ID=your_agent_id
```

For the optional distributed cache & resilience tuning:
```env
# Optional — Distributed Cache & Resilience (Phases 8-9)
REDIS_URL=rediss://default:<password>@<host>:<port>   # enables L2 cache; absent = L1 only
AGENT_TIMEOUT_SEC=90                                   # per-agent bulkhead budget
SEMANTIC_CACHE_THRESHOLD=0.95                          # Critic semantic match threshold
```
Without `REDIS_URL`, the cache layer runs L1-only (in-process LRU+TTL) and the pipeline behaves exactly as before. With Redis configured, cache state survives container restarts and is shared across replicas. See `docs/DEPLOYMENT_HUGGINGFACE.md` for the Upstash setup walkthrough.

### 3. Database Ingestion (One-Time Setup)

Ingest organization standards into Pinecone:
```bash
python scripts/ingest_kb.py
```

### 4. Running the Application

Start the backend API server and the Streamlit frontend in separate terminals:

```bash
# Terminal 1 — Backend API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — UI
streamlit run streamlit_app.py
```
Access the application UI by visiting `http://localhost:8501`.

---

## Failure Modes & Mitigations

*   **API Timeouts & Transient Errors:** Covered by the `@resilient(policy=...)` decorator — jittered exponential backoff, hard timeout enforced via `ThreadPoolExecutor`, and per-instance circuit breakers that open after N consecutive failures and half-open after a cooldown. Replaces the earlier `tenacity` wrapper.
*   **JSON Parse Failures:** Specialized Agents perform schema recovery prompts on parse failure. If recovery fails, `_fallback()` returns a placeholder model, flagging low confidence (`0.20`), triggering Critic's **FM-3** Amber downgrading.
*   **Agent Bulkhead Timeout:** If any specialist exceeds `AGENT_TIMEOUT_SEC` (default 90s), the pipeline cancels the pending future, fills its slot with the Sentinel Fallback, emits a `bulkhead_timeout` event, and continues with the rest. The Critic then caps the overall badge at FM-3 Amber.
*   **Circuit Breaker Open:** When a service's breaker is open, subsequent calls fast-fail with `CircuitOpenError` instead of hitting the dead dependency. Each agent class and each external service (LLM, embeddings, Pinecone) owns its own breaker, so one failing dependency cannot poison the others.
*   **Redis Unavailable:** The two-tier cache degrades to L1 only — graceful, logged once (`[cache] Redis healthcheck failed (...); using L1 only`), recovers automatically on the next successful call. The pipeline behavior is identical to a Redis-less deployment.
*   **Missing Integrations Credentials:** If Google Sheets or Jira credentials are not found, the endpoints skip execution gracefully with warning logs. They write a local fallback zip/CSV copy to `logs/exports/` and allow the pipeline to proceed without throwing exceptions.
*   **MCP Server Unavailable:** If the `mcp-atlassian` server cannot spawn or the `jira_create_issue` call fails, `/approve` automatically falls back to the REST Jira client — the Epic is still created (idempotent on `em-copilot-run-<id>` label so no double-write), and the fallback reason is logged.
*   **Unavailable Third-Party Endpoints:** If Kroki.io fails during SVG generation, the frontend defaults to client-side JS Rendering. If the GitHub API is unavailable, the Tech Stack Agent ignores velocity signals and notes the dependency failure in its logs.

---

## Observability & Tracing

Full observability is configured through **LangSmith**. Every database call, Agent dispatch, and LLM text generation is traced via our LangSmith-wrapped OpenAI client:

```python
from openai import OpenAI
from langsmith.wrappers import wrap_openai
from src.core.config import settings

client = wrap_openai(OpenAI(api_key=settings.openai_api_key))
```

This captures prompt structures, latency figures, model versions, and token usage records under the `em-copilot-brd-agent` LangSmith project dashboard. Detailed local logs are simultaneously captured as structured JSONL in `logs/pipeline.jsonl`.

Beyond LangSmith, the pipeline emits structured **resilience events** — `cache_hit`, `cache_miss`, `retry`, `breaker_open`, `breaker_short_circuit`, `bulkhead_timeout` — onto a thread-local bus (`src/core/events.py`) keyed by `run_id`. FastAPI wires the sink at startup and fans these events into the per-run SSE stream, so the Streamlit UI surfaces them in real time alongside Agent progress chips. The bus is best-effort and never raises, so observability cannot break the caller. Cache hit-rate is queryable at runtime via `cache_stats()` for capacity planning.

---

## 📜 License
MIT License - Feel free to use this project for learning and inspiration.


---

## 🧑‍💻 Author
Name: Rahul Ganbote
GitHub: @rahulganbote
---

*© 2026 Rahul Ganbote · All rights reserved.*
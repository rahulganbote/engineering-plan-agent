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

> **EM Copilot** is an multi-agent AI system that transforms raw Business Requirements Documents (BRDs) into an audit-ready engineering plan package.

---

## Executive Summary (TL;DR)

* **What it is:** A production-grade, RAG-augmented multi-agent system that automates the translation of Business Requirements Documents (BRDs) into audit-ready engineering deliverables (System Architecture, Project Schedules, Tech Stacks, and PoC specifications) grounded in organizational standards.
* **The ROI:** Redefines the standard planning lifecycle, reducing scoping and drafting time from weeks to minutes (~50s execution) with a low operational cost (~$0.31 per run).
* **Enterprise Grade:** Built on LangGraph with Pinecone RAG for knowledge grounding, type-safe schemas, a 7-stage security sanitization pipeline (inc. PII redacting), isolated resilience, a dual-tier (L1/L2) cache, and full execution observability via LangSmith.
* **Integrations:** Closes the feedback loop via Slack alerts, a voice/UI Human-in-the-Loop (HITL) gate, and direct export handlers (Google Sheets, ReportLab PDF, and Jira Epic creation via MCP).

---

🔗 **Live Demo:** [EM-Copilot on Google Cloud](https://em-copilot-809545615573.us-east4.run.app/)

---

## Table of Contents
1. [Executive Summary (TL;DR)](#executive-summary-tldr)
2. [Business Use Case & Solution](#business-use-case--solution)
3. [Architectural Overview](#architectural-overview)
4. [System Design & Core Engineering Pillars](#system-design--core-engineering-pillars)
   * [Core Capabilities Matrix](#core-capabilities-matrix)
   * [Agent Design Patterns](#agent-design-patterns)
   * [Security & Validation Pipeline](#security--validation-pipeline)
   * [Distributed Resilience & Caching](#distributed-resilience--caching)
   * [Observability & Tracing](#observability--tracing)
5. [Screenshots](#screenshots)
6. [Tech Stack Justification](#tech-stack-justification)
7. [Vector DB & RAG Integration](#vector-db--rag-integration)
8. [Evaluation Framework](#evaluation-framework)
9. [Integrations & External Channels](#integrations--external-channels)
10. [Token Usage & Execution Cost](#token-usage--execution-cost)
11. [Project Directory Structure](#project-directory-structure)
12. [Quick Start Guide](#quick-start-guide)
13. [License](#license)
14. [Author](#author)


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

## System Design & Core Engineering Pillars

This section outlines the architectural foundation, security validations, and resilience strategies that govern the EM Copilot system.

### 1. Core Capabilities Matrix

| Capability | Engineering Implementation |
|---|---|
| **7-Agent LangGraph Pipeline** | Parallel execution via `ThreadPoolExecutor` (Orchestrator + 5 Specialists + Critic) |
| **Type-Safe Schema Contracts** | Schema conformance validated at every transition to ensure structural integrity |
| **7-Stage Security Pipeline** | Automated checks including format, size, regex guard, LLM injection guard, and PII redacting |
| **Pinecone RAG Vector Search** | Dynamic context retrieval with document citation mapping and diversity filters |
| **Critic Revision Loop** | LLM-as-Judge self-correction (capped at 2 loops) with deterministic failure-mode quality caps |
| **Distributed Resilience** | Per-instance circuit breakers, jittered exponential backoff, bulkhead isolation, and sentinel fallbacks |
| **Dual-Tier Hybrid Caching** | Local L1 (InMemory LRU+TTL) and distributed L2 (Redis) with semantic cache fallback for Critic queries |
| **Specialist Registry & Policy Manifest** | Decoupled dynamic agent registration; policy manifests allow per-agent timeout/cache configuration |
| **Visual Architecture Renderer** | LLM Mermaid syntax generation validated and rendered to SVG via Kroki API with local JS fallback | 
| **ElevenLabs Voice HITL Gate** | Conversational approval webhook accepting natural language feedback and scoring inputs | 
| **Jira Epic Integration via MCP** | MCP-native Atlassian server (stdio transport) with automatic fallback to Jira Cloud REST API |
| **Google Sheets Logging** | Centralized audit row export powering historical insights with local CSV fallback |
| **Slack Failure Alerting** | Webhook alerts trigger on critical execution errors for real-time alerting |
| **BRD Pinecone Ingestion** | Post-approval BRD vector indexing to keep the RAG knowledge base automatically up to date |
| **ReportLab PDF Exporter** | Automated compilation of all planning artifacts into a downloadable executive summary PDF |
| **LangSmith Telemetry** | Full trace visualization covering model tokens, prompts, inputs, and latency |

### 2. Agent Design Patterns

#### Parallel Dispatch (Hub-and-Spoke)
Instead of sequentially chaining Agent calls, the Orchestrator splits the incoming BRD sections and routes them to all five specialist Agents concurrently using Python's `ThreadPoolExecutor`. This reduces total wall-clock execution time by **~3×** (~50 seconds compared to >2.5 minutes sequentially).

#### Multi-Agent Aggregate Criticism
The Critic node serves as a secondary routing hub. Rather than verifying each Agent individually, it acts on the aggregated `PipelineState` containing all 5 specialist outputs. This global view enables it to catch cross-specialist contradictions, such as the *Schedule Estimator* planning a 12-week project while the *Solution Architect* designs 25 separate microservices for a 2-engineer team.

#### Targeted Revision Loop
If the Critic flags issues, the pipeline does not rerun from scratch. Instead, it runs a selective revision loop (max 2 cycles). The loop only invokes the specialist Agents that were flagged with a quality score below the acceptable threshold.

#### Deterministic Quality Caps
To prevent the LLM Critic from being overly optimistic, the scoring pipeline enforces three deterministic quality overrides (hallucination penalties, uncited claim limits, and sentinel fallback caps). These rules are detailed under the [Evaluation Framework](#evaluation-framework) section.

#### Specialist Registry (Decoupled Dispatch)
Specialist agents register themselves at import time via `register_specialist("plan_generator", PlanGeneratorAgent)`. The pipeline's `_run_agent()` looks up the class via `get_specialist(name)` instead of a hardcoded `if/elif` chain. Adding a new specialist becomes a two-line change (one register call + one entry in the dispatch list) instead of touching multiple files.

### 3. Security & Validation Pipeline

Before any LLM node processes a user-uploaded document, the file passes through a strict, sequential 7-check security pipeline:
1.  **Format Restriction:** Restricts file extensions to `.txt`, `.pdf`, and `.docx`.
2.  **Size Guard:** Enforces a hard 10MB limit (preventing Denial of Service / resource exhaustion).
3.  **Word Check:** Ensures the document contains at least 50 words to avoid parsing empty text.
4.  **Regex Injection Guard:** Scans for 15 known LLM jailbreak and injection strings (e.g., `"ignore all previous instructions"`).
5.  **Semantic Injection Guard:** A lightweight GPT-4o-mini scan to detect sophisticated, multi-paragraph prompt injections.
6.  **PII Sanitizer:** Identifies and redacts Social Security Numbers, Credit Cards, email addresses, and phone numbers with placeholders (e.g., `[REDACTED-SSN]`).
7.  **Completeness Check:** Inspects the parsed text structure to confirm key sections (Objectives, Requirements, Constraints, Risks, NFRs) are present.

### 4. Distributed Resilience & Caching

EM Copilot incorporates a production-grade resilience and caching architecture modeled on distributed-systems patterns (like Hystrix and resilience4j). The system guarantees that no single external dependency failure (OpenAI, Pinecone, Redis, or MCP) can crash the pipeline, while caching ensures cost-efficiency by preventing duplicate LLM execution.

#### Two-Tier Caching System
*   **L1 (In-Memory):** A fast, per-process LRU cache with TTL for immediate local retrieval.
*   **L2 (Redis):** Distributed cache (gzipped/serialized with ~70% size reduction) to persist and share states across container instances.
*   **Semantic Cache:** Powered by Pinecone (cosine threshold `0.95`) specifically for the Critic's evaluation revisions, recognizing similar inputs even when text varies slightly.
*   **Decorator Flow:** The `@cached` decorator wraps the `@resilient` wrapper, meaning cache hits short-circuit before hitting timeouts or circuit breakers.
*   **Dynamic Cache Policies:** Configurable per agent class via class-level `CACHE_POLICY` manifests to customize TTL and backend choice.

#### Fault Tolerance & Isolation
*   **Circuit Breakers:** Isolated per agent and external service class in a module-level registry. A failure in one agent (e.g., OpenAI rate limit) or external service (e.g., Pinecone timeout) does not cascade or trip other breakers.
*   **Bulkheads:** Enforced per-agent execution timeouts. Parallel agent execution is managed concurrently via `ThreadPoolExecutor`. If an agent hangs, its thread is cancelled and returns a Sentinel Fallback (flagging a low confidence score), allowing the rest of the pipeline to complete successfully.
*   **Dynamic Call Policies:** Declared on each agent subclass via a `RESILIENCE_POLICY` manifest to fine-tune retry counts, timeouts, and breaker cooldowns.
*   **Graceful Degradation:** The pipeline automatically downgrades to L1 cache if Redis is offline, falls back to direct REST APIs if the Atlassian MCP server is down, and renders architecture diagrams client-side if the Kroki API fails.

#### Event-Driven Observability
*   A thread-safe, best-effort event emitter publishes resilience events (e.g., `cache_hit`, `retry`, `breaker_open`, `bulkhead_timeout`). These are streamed live to the Streamlit UI via Server-Sent Events (SSE) without affecting pipeline execution.

#### Failure Mitigation Matrix
The system maps infrastructure faults and LLM cognitive errors directly to specific resilience strategies:

| Failure Mode | Mitigation & Recovery Mechanism |
|---|---|
| **API Down / Timeout** | Jittered backoff retries → isolated Circuit Breaker opens to fast-fail calls |
| **Redis Outage** | Gracefully degrades to local L1 in-memory cache; auto-recovers |
| **Integration Down** | Outages (Sheets/Jira) fall back to exporting local CSV/ZIP backups |
| **MCP Server Offline** | Dynamic fallback directly to Jira Cloud REST APIs with idempotency hashes |
| **Kroki Rendering Down** | UI automatically renders architectural charts client-side via `mermaid.js` |
| **JSON Parse Failures** | Dynamic self-correction retries → safe mock sentinel fallback (badges Critic Amber) |
| **Slow Agent (Bulkhead)** | ThreadPool executor halts hung agents after 90s timeout, using sentinel fallbacks |

### 5. Observability & Tracing

*   **Global Execution Tracing:** Integrates **LangSmith** to capture prompt structures, token counts, execution latency, and exact model responses. Detailed audit logs are simultaneously persisted locally as structured JSONL in `logs/pipeline.jsonl`.
*   **Real-Time Event Bus:** Emitters publish structured runtime events (`cache_hit`, `retry`, `breaker_open`, `bulkhead_timeout`) on a thread-local channel. These events are streamed to the UI via FastAPI Server-Sent Events (SSE) for real-time latency and state monitoring.

---

## Tech Stack Justification

| Category | Technology | Engineering Reason |
|---|---|---|
| **Agent State** | LangGraph v0.2.28 | State Graph model with native routing, cycle tracking, and async interrupts |
| **Vector DB** | Pinecone Serverless | Fully managed index with fast cosine-similarity search over technical standards |
| **Embeddings** | `text-embedding-3-large` (1024) | High dimensionality with customized text projection for dense architectural guides |
| **Models** | GPT-4o (specialists) + GPT-4o-mini (critic) | Balance between specialist reasoning quality and critic execution cost |
| **Web Server** | FastAPI | Async endpoints, Server-Sent Events (SSE) for UI streaming, and non-blocking exports |
| **Frontend UI** | Streamlit | Rapid internal prototyping & dashboard (easily swappable with a React/Next.js frontend backing the FastAPI server) |
| **Voice Interface** | ElevenLabs Conversational AI | Webhook integration executing natural language HITL discussion & approvals |
| **Tool Integration** | Model Context Protocol (MCP) | Standardized Agent-to-Tool transport; the Jira Epic push runs through an `mcp-atlassian` server spawned over stdio |
| **Resilience Primitives** | Custom `src/core/resilience.py` (mirrors Hystrix / Polly / resilience4j) | Small surface area, no external dependency; per-instance state with frozen `CallPolicy` |
| **Cache Backends** | `InMemoryCache` / `RedisCache` / `TieredCache` / `SemanticBackend` (Pinecone) | Pluggable `CacheBackend` Protocol — chosen at runtime via `init_default_backend_from_env()` |
| **Event Bus** | Lightweight `src/core/events.py` emitter | Best-effort event fan-out for `cache_hit`, `cache_miss`, `retry`, `breaker_open`, `bulkhead_timeout`; surfaced into Streamlit SSE stream |

---

## Vector DB & RAG Integration

The vector database stores organization-specific architectural patterns, planning templates, and historical schedules.
*   **Ingestion:** The ingestion tool `scripts/ingest_kb.py` parses documents from `knowledge_base/`, splits them using a dynamic recursive character text splitter, embeds them via `text-embedding-3-large` (1024 dimensions), and writes them to Pinecone with metadata tags (`source_type`, `chunk_id`).
*   **Retrieval:** During execution, each specialist Agent retrieves relevant context using a similarity search. A similarity threshold of `0.45` is enforced.
*   **Citation Tracking:** Specialists must return exact citations (`source_file` + `chunk_id`) for any technical standard referenced in their plan. The Critic enforces that these references are present and match valid chunks.

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
    *   *Metric:* 0-5 scores for Groundedness (citations presence), Completeness, Consistency, and Actionability, calibrated via `critic_calibration_set.json`.
    *   *Deterministic Quality Caps:* To override optimistic LLM self-ratings, the Critic enforces three rules:
        *   **FM-1 (Hallucination Guard):** Deducts `0.3` points for every citation not matching valid keys in the Pinecone vector database.
        *   **FM-2 (Uncited Claim Cap):** Caps the overall score at `3.9` (Amber) if any specialist agent fails to reference at least one vector database chunk.
        *   **FM-3 (Sentinel Fallback Cap):** Caps the overall score at `3.9` (Amber) and flags a `ConsistencyIssue` in the UI if an agent fails or times out, forcing a mock fallback.
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

## Screenshots of Demo
See [screenshots/README.md](docs/screenshots/README.md) for sample run with screenshots and detailed annotations.

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



## 📜 License
MIT License - Feel free to use this project for learning and inspiration.


---

## 🧑‍💻 Author
**Rahul Ganbote** — [LinkedIn](https://www.linkedin.com/in/rahul-ganbote-040a7b/) · [GitHub @rahulganbote](https://github.com/rahulganbote)

---

*© 2026 Rahul Ganbote · All rights reserved.*

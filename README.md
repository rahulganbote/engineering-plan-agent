# EM Copilot - BRD to Engineering Plan Agent

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.28-green)](https://github.com/langchain-ai/langgraph)
[![Pinecone](https://img.shields.io/badge/RAG-Pinecone-purple)](https://pinecone.io)
[![LangSmith](https://img.shields.io/badge/Observability-LangSmith-orange)](https://smith.langchain.com)
[![Jira](https://img.shields.io/badge/Jira%20Epic-MCP%20%2B%20REST-0052CC)](https://www.atlassian.com/software/jira)
[![ElevenLabs](https://img.shields.io/badge/Voice%20HITL-ElevenLabs-1F1F1F)](https://elevenlabs.io)
[![React](https://img.shields.io/badge/UI-React%2019%20%2B%20Vite-61DAFB)](https://react.dev)
[![Anthropic](https://img.shields.io/badge/Multi--Provider-OpenAI%20%2B%20Anthropic-D97757)](https://www.anthropic.com)
[![Tavily](https://img.shields.io/badge/Search-Tavily-orange)](https://tavily.com)

> EM Copilot is a Multi-Agent AI system that transforms raw Business Requirements Documents (BRDs) into an audit-ready engineering plan package, and presented to you for review. Upon HITL (Human in the Loop) approval, it pushes the artifacts into Jira. 

🔗 **Live:** [emcopilot.ai](https://emcopilot.ai) 
🔗 **Loom walkthrough:** *(coming soon)*

---

## Executive Summary (TL;DR)

* **What it is:** A production-grade, RAG-augmented multi-agent AI system that automates the translation of Business Requirements Documents (BRDs) into audit-ready engineering deliverables viz. System Architecture, Project Schedules, Tech Stacks, and PoC specifications that are grounded in organizational technology standards via Pinecone RAG.
* **The ROI:** Reduces planning scoping and drafting from days to under two minutes. 
    - Latency:
        **OpenAI (n=13):** p50 ~26s · p95 ~72s 
        **Anthropic (n=9):** p50 ~86s · p95 ~102s (~2.2× latency)
    - Cost (median): 
        **~$0.08 per run on OpenAI** 
        **~$0.20 per run on Anthropic** (~2.5× cost; ~20-50% higher token rate).
* **Enterprise Grade:** Multi-Agent Orchestration built on LangGraph with Pinecone RAG for knowledge grounding, Pydantic contracts, a multi-stage BRD sanitization security (PII redaction, format validation, and prompt injection protection), isolated resilience, a dual-tier (L1/L2) cache, multi-provider LLM with intelligent failover, and full execution observability via LangSmith. 
* **AI Governance**: **$2.00 per-run budget ceiling**, Quality Gate (F3-Score across 5 dimensions for audit-readiness scoring, Green/Amber/Red badge), **Human-in-the-Loop (HITL)** review & approval.
* **Resilience & Guardrails:** Pre-defined Contracts, Intelligent LLM Failover, Per-agent Circuit Breakers, Bulkhead Isolation (per-provider + per-family + global), per-tenant data isolation and an innovative **idempotent approval** that makes decision gate safe to retry without creating duplicate artifacts.
* **Tools & Integrations:** Tavily Search, Voice AI (ElevenLabs) support for HITL, and direct export handlers (Google Sheets, ReportLab PDF, and Jira Epic creation via MCP), and Slack alerts.

---

🔗 **Live Demo:** [EM-Copilot on Google Cloud](https://em-copilot-809545615573.us-east4.run.app/)

---

## Table of Contents
1. [Executive Summary (TL;DR)](#executive-summary-tldr)
2. [Problem & Solution](#problem--solution)
3. [Architecture](#architecture)
4. [Tech Stack Justification](#tech-stack-justification)
5. [Vector DB & RAG Integration](#vector-db--rag-integration)
6. [Evaluation Framework](#evaluation-framework)
7. [Rate Limiter and Security](#rate-limiter-and-security)
8. [Screenshots of Demo](#screenshots-of-demo)
9. [Multi-Provider Strategy](#multi-provider-strategy)
10. [Decisions Journal & Trade-offs](#decisions-journal--trade-offs)
11. [Operational Metrics & SLOs](#operational-metrics--slos)
12. [Production Considerations & Risk Registry](#production-considerations--risk-registry)
13. [Quick Start](#quick-start)
14. [Project Layout (Brief)](#project-layout-brief)
15. [License & Author](#license--author)


---

## Problem & Solution

### The Challenge

Engineering Managers face a persistent bottleneck in translating complex Business Requirements Documents (BRDs) into structured technical plans, schedules, and architecture diagrams. The manual process is time-consuming and frequently results in:

* **Delivery delays** - days lost drafting sprint scopes, mapping timelines, and aligning teams.
* **Misalignment** - gaps between business intent (BRD requirements) and engineering implementation.
* **Inconsistent scoping** - ad-hoc architectures and planning criteria that vary wildly across engineering squads, making cross-team comparison and audit difficult.

### The EM Copilot Solution

EM Copilot ingests raw BRDs and produces a complete, audit-ready engineering bundle through a multi-agent workflow. The system delivers across five dimensions:

* **Faster turnaround.** RAG-augmented specialist agents reference past projects and templates, eliminating boilerplate drafting from scratch - measured median per run is ~26s on OpenAI and ~70s on Anthropic.
* **Standardized, validated planning.** A Critic Agent checks all five specialist outputs for completeness, consistency, and alignment before they reach the EM, and enforces deterministic quality caps (FM-1/2/3) on top of the LLM-judge score.
* **Grounded intelligence.** Pinecone RAG ensures architectural decisions and project guidelines are grounded in organization standards and historical project data, with explicit citation tracking per specialist output.
* **Evaluated outputs.** Outputs are scored across five criteria - Groundedness, Completeness, Consistency, Actionability, and Hallucination resistance - so every artifact carries a clear Green / Amber / Red quality badge tied to verifiable metrics, not vibes.
* **EM enablement.** The system generates decision-ready artifacts with source citations and a voice/UI approval gate, allowing the EM to serve as an editor and approver rather than a drafter staring at a blank page.


---

## Architecture Overview

```
                         ┌─────────────────────────────────────────────────┐
                         │         SECURITY VALIDATION LAYER               │
 BRD Upload ──► FastAPI──►│  File check → Parse → Injection Guard (regex)   │
  (React SPA)    POST     │  → Injection Guard (LLM) → PII Redact → BRD ✓   │
             run-pipeline └─────────────────────────────────────────────────┘
                                               │ validated BRD text
                                               ▼
                                     Orchestrator (Pass 1)
                                  (Fan-out initial drafting)
                                               │
                                               ▼
             ┌─────────────────────────────────────────────────────────────────────────┐
             │ Parallel dispatch  │                     │             │                │
             ▼                    ▼                     ▼             ▼                ▼
      Plan Draft       Schedule Draft       Architect Draft       PoC Draft       Stack Draft
             │                     │                    │             │                │
             ▼                     ▼                    ▼             ▼                ▼
             └─────────────────────└────────────────────┘─────────────└────────────────┘
                                               │
                                               ▼
                                     Orchestrator (Pass 2)
                                  (Arbitration & Alignment)
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       │  Are EM alignment directives present?         │
                       ▼ yes                                           ▼ no
              ↻ Targeted Alignment Rerun                           (skip rerun)
              (Only violating Specialists)                             │
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               │
                                               ▼
                                          Critic Agent
                                (LLM-judge + FM-1/2/3 quality caps)
                                               │
                                ┌──────────────┴──────────────┐
                                ▼                             ▼
                       [Score < Threshold]            [Quality Passed]
                        & [Revision < 2]                      │
                               │                              ▼
                      ↻ Targeted Self-Revision               HITL Decision Gate
                      (Only flagged Specialists)       (Approve & Export / Reject)
```

Three architectural patterns matter more than the rest:

* **Two-Pass Targeted Alignment Loop**: Rather than chaining agents sequentially, the pipeline splits into two distinct passes. Pass 1 drafts all deliverables concurrently. If the EM submits custom directives during **Arbitration**, Pass 2 performs a targeted rerun *only* on the violating specialists, reusing the other drafts to save cost and latency.
* **Targeted Critic Self-Correction**: After alignment, the Critic evaluates final outputs. If dimension scores fall below threshold limits, up to 2 self-correction cycles are triggered, rerunning only the flagged agents.
* **Deterministic Quality Caps over LLM-Judge**: LLM judges are systematically optimistic. Three deterministic rules (uncited claims, hallucinated citations, sentinel fallbacks) cap the overall score independent of the LLM's self-rating to guarantee audit quality.

The full architecture diagram with security boundaries, observability events, and integration channels lives at [docs/Design.md](./docs/Design.md).

---

## Tech Stack Justification

| Category | Technology | Engineering Reason |
|---|---|---|
| **Agent State** | LangGraph v0.2.28 | State Graph model with native routing, cycle tracking, and async interrupts |
| **Vector DB** | Pinecone Serverless | Fully managed index with fast cosine-similarity search over technical standards |
| **Embeddings** | `text-embedding-3-large` (1024) | High dimensionality with customized text projection for dense architectural guides |
| **Models** | GPT-4o (specialists) + GPT-4o-mini (critic) | Balance between specialist reasoning quality and critic execution cost |
| **Web Server** | FastAPI | Async endpoints, Server-Sent Events (SSE) for UI streaming, and non-blocking exports |
| **Frontend UI** | React 19 + Vite | Premium single-page application with SSE telemetry stream, live SVG rendering, and theme picker |
| **Voice Interface** | ElevenLabs Conversational AI | Webhook integration executing natural language HITL discussion & approvals |
| **Tool Integration** | Model Context Protocol (MCP) | Standardized Agent-to-Tool transport; the Jira Epic push runs through an `mcp-atlassian` server spawned over stdio |
| **Resilience Primitives** | Custom `src/core/resilience.py` (mirrors Hystrix / Polly / resilience4j) | Small surface area, no external dependency; per-instance state with frozen `CallPolicy` |
| **Cache Backends** | `InMemoryCache` / `RedisCache` / `TieredCache` / `SemanticBackend` (Pinecone) | Pluggable `CacheBackend` Protocol - chosen at runtime via `init_default_backend_from_env()` |
| **Event Bus** | Lightweight `src/core/events.py` emitter | Best-effort event fan-out for `cache_hit`, `cache_miss`, `retry`, `breaker_open`, `bulkhead_timeout`; surfaced into Streamlit SSE stream |

---

## Vector DB & RAG Integration

The vector database stores organization-specific architectural patterns, planning templates, and historical schedules.
*   **Ingestion:** The ingestion tool `scripts/ingest_kb.py` parses documents from `knowledge_base/`, splits them using a dynamic recursive character text splitter, embeds them via `text-embedding-3-large` (1024 dimensions), and writes them to Pinecone with metadata tags (`source_type`, `chunk_id`).
*   **Retrieval:** During execution, each specialist Agent retrieves relevant context using a similarity search. A similarity threshold of `0.45` is enforced.
*   **Citation Tracking:** Specialists must return exact citations (`source_file` + `chunk_id`) for any technical standard referenced in their plan. The Critic enforces that these references are present and match valid chunks.

---

## Evaluation Framework

Five-method evaluation suite (`eval/run_eval.py`):

1. **Rule-based** - deterministic structural assertions (milestone count, owner coverage, citation format)
2. **LLM-as-Judge** - 0–5 scores for Groundedness, Completeness, Consistency, Actionability
3. **Execution-based** - Pydantic schema pass rate, Kroki render checks, total pipeline time SLA
4. **Reference-based** - BERTScore F1 against golden output files
5. **Human HITL** - 1–5 EM rating + free-text notes

**Deterministic quality caps** override optimistic LLM-judge scores:

- **FM-1 Hallucination Guard:** -0.3 per citation not matching the Pinecone index
- **FM-2 Uncited Claim Cap:** caps overall at 3.9 (below the 4.0 Green threshold) if any specialist fails to cite at least one chunk
- **FM-3 Sentinel Fallback Cap:** caps overall at 3.9 (below the 4.0 Green threshold) if any specialist times out and falls back

**Result of the Critic loop (v0 → v1):** Overall **3.38 → 4.33** (+0.95 lift after one revision cycle; ~28% relative improvement on the 5-point scale). Full breakdown in [docs/EVAL_RESULTS.md](./docs/EVAL_RESULTS.md).

---

## Rate Limiter and Security
The API enforces rate limits to prevent runaway LLM costs and protect against abuse. Powered by `slowapi`, the `/run-pipeline` endpoint applies dual limits per user (`x/day` and `y/week`). Limits are keyed by the authenticated user's email and return a standard `429 Too Many Requests` response with a configurable `Retry-After` header (defaulting to 3600 seconds). Additionally, a hard budget cap of `$2.00` per run (`MAX_PIPELINE_RUN_BUDGET_USD`) is enforced to immediately abort any run exceeding this financial threshold. These parameters can be customized in production via environment variables.

---

## Screenshots of Demo
** TO-DO: Update screenshots from new UI in the [screenshots/README.md](docs/screenshots/README.md) **   

---

## Multi-Provider Strategy

To prevent single-provider vendor lock-in and mitigate outages, rate-limiting, or latency spikes, EM Copilot abstracts the model layer using a pluggable `LLMProvider` protocol. This allows seamless runtime switching between OpenAI and Anthropic, making it straightforward to measure performance and cost trade-offs empirically.

| Dimension | OpenAI (`gpt-4o` / `gpt-4o-mini`) | Anthropic (`claude-sonnet-4-5` / `claude-haiku-4-5`) |
|---|---|---|
| **End-to-end latency (p50)** | ~26s (n=13, measured) | ~86s (n=9, measured) |
| **End-to-end latency (p95)** | ~72s (n=13, measured) | ~102s (n=9, measured) |
| **Cost per run (median)** | ~$0.08 (n=13, measured) | ~$0.20 (n=9, measured; ~2.5× OpenAI on observed data) |
| **Output tokens per run (mean)** | ~5,100 | ~11,300 (n=9; Anthropic is ~2.2× more verbose for the same prompt) |
| **Critic GREEN-rate (standard BRDs)** | ~70% | ~75% (anecdotal, broader benchmarking pending) |
| **Per-agent bulkhead timeout** | 90s | 180s |
| **Best for** | Latency-sensitive demos; high-throughput; tight cost budgets | Complex BRDs needing deeper reasoning; consistency-critical drafts where the 2× cost is justified |

---

## Decisions Journal & Trade-offs

A consolidated log of core architectural compromises. Detailed records are maintained under [docs/ADR/](./docs/ADR/).

| Decision | Alternatives | Why | Trade-off |
|---|---|---|---|
| **LangGraph state** | LCEL chains; raw asyncio | Native support for loop cycles (Pass 1 ↔ arbitration ↔ Pass 2 ↔ Critic revision) and node observability. | Heavier runtime dependency; lock-in to LangChain ecosystem. |
| **Multi-provider failover** | Single LLM provider | Production redundancy (OpenAI ↔ Anthropic failover) to handle provider-side outages. | Two separate prompt layouts and budget cost-tables to maintain. |
| **Async `/approve` + SSE** | Synchronous approve endpoint | External tool calls (Jira/Sheets) and ElevenLabs voice tasks easily exceed the 20s API timeout threshold. | UI must listen for the final SSE event to hydrate export links. |
| **Hard $2.00 per-run budget** | Soft warning logs | Prevents runaway LLM loops or excessively large uploads from consuming billing budgets. | Aborts legitimate very large BRDs; accepted as visible error over budget leak. |

---

## Operational Metrics & SLOs

What I would commit to in a sprint plan if this graduated to a team-owned service.

| SLI | Current (measured) | Proposed SLO | Reasoning |
|---|---|---|---|
| Latency p50/p95 - OpenAI | ~26s / ~72s (n=13) | 99% < 120s | Within ElevenLabs voice budget |
| Latency p50/p95 - Anthropic | ~86s / ~102s (n=9) | 95% < 130s | ~3× wall-clock; ~2.2× output verbosity |
| Cost / run - OpenAI median | ~$0.08 (n=13) | < $0.15 / 30-day rolling | Tracked via pricing table + Tavily counter |
| Cost / run - Anthropic median | ~$0.20 (n=9) | < $0.30 / 30-day rolling | ~2.5× OpenAI on observed data |
| Critic GREEN-rate | ~70% standard BRDs | 80% standard / 60% niche-tech | Measured against `eval/` golden set |
| Pipeline error rate | < 2% | < 1% production | Excludes user-driven rejections |
| `/approve` sync return | < 1s | < 5s p95 | Async refactor; SLO leaves cold-start slack |
| Voice-approval idempotency | 100% same-decision retries | 100% (no degradation) | Locked by 4 unit tests |

**Alerting:** cost regression via daily cron over `logs/pipeline.jsonl`; latency via LangSmith p95 widget; GREEN-rate via weekly `eval/run_eval.py` PR-blocking check; tool-call degradation via 1h ratio of `tool_call_degraded` to `tool_call_started`.

---

## Production Considerations & Risk Registry

High-priority operational considerations and mitigations for production readiness.

| Consideration | Likelihood | Impact | Current Mitigation | Next Step |
|---|---|---|---|---|
| **Local state loss on restart** | Med | Med | Single-instance constraint (`--max-instances=1`) on Cloud Run. | **Migrate `_runs` and `_run_owner` maps to Upstash Redis.** |
| **API billing overruns** | Med | Med | Hard $2.00 budget ceiling per run. | **Implement daily global budget caps and per-user rate limits.** |
| **PII leak via Tavily Search** | Med | Med | Regex redact + section slice searches (avoids sending full BRD). | **Deploy LLM-based Layer 5 privacy filter pre-network query.** |
| **Jira connection drops** | Low | Med | Graceful degradation: marks Jira status as `"skipped"` / `"local_fallback"`. | **Implement background job queue with automated retry-loops.** |
| **LLM judge bias (Critic)** | Med | Low | Deterministic cap rules overrides to catch false-greens. | **Expand and calibrate the golden dataset `eval/` on niche BRDs.** |

---

## Quick Start

```bash
git clone https://github.com/rahulganbote/engineering-plan-agent.git
cd engineering-plan-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm ci && cd ..

cp .env.example secrets/.env  # then fill in required keys
python scripts/ingest_kb.py    # one-time RAG ingest

# Terminal 1
uvicorn src.api.main:app --reload --port 8000
# Terminal 2
cd frontend && npm run dev
# Visit http://localhost:5173
```

**Required keys (minimum to run):** `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`), `PINECONE_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` + `SESSION_SECRET_KEY`.

**Recommended for production parity:** `LANGCHAIN_API_KEY` (observability), `VOICE_WEBHOOK_SECRET` (voice auth), `MAX_PIPELINE_RUN_BUDGET_USD` (cost ceiling), `REDIS_URL` (L2 cache), `TAVILY_API_KEY` + `TAVILY_MONTHLY_BUDGET` (web grounding fallback), `MAX_CRITIC_REVISIONS` (maximum self-revision loops for quality criteria, default is `2`; set to `0` to disable and save tokens/time).

Full configuration reference: [.env.example](./.env.example) - every variable is documented with its purpose and default.

**Tests:**

```bash
.venv/bin/pytest tests/unit/ -q          # ~73 unit tests, no LLM calls
python tests/smoke_test.py               # ~80 smoke tests across 14 groups
cd frontend && npm test                  # Vitest + Playwright E2E
```

**Adding a new API route?** The Vite dev proxy at [`frontend/vite.config.ts`](./frontend/vite.config.ts) forwards only specific URL prefixes to FastAPI (`/api`, `/status`, `/approve`, `/cancel`, `/events`, etc.). New routes must either reuse an existing prefix or add a matching proxy entry — otherwise the frontend request hits Vite (not FastAPI) and returns a non-JSON 404 that surfaces as an "API Failure" toast. Production (Cloud Run) has no proxy so this trap only surfaces in local dev; catches everyone once.

---

## Project Layout (Brief)

```
src/
├── core/         models, config, providers, pricing, resilience, cache, events
├── agents/       base + 5 specialists + critic + orchestrator + pipeline
├── api/main.py   FastAPI endpoints (mounts React SPA at /)
├── security/     7-stage validator + Google OAuth helpers
└── integrations/ sheets, jira (REST + MCP), pdf, voice, slack, tavily, github

frontend/        React 19 + Vite + TypeScript + Tailwind v4 SPA
tests/           unit (pytest) + smoke (custom registry) + Playwright E2E
eval/            5-method evaluation suite + golden BRDs
docs/            Design.md, EVAL_RESULTS.md, screenshots, ADRs
```

---

## License & Author

**MIT License** 

**Rahul Ganbote** - [LinkedIn](https://www.linkedin.com/in/rahul-ganbote-040a7b/) · [GitHub @rahulganbote](https://github.com/rahulganbote)

---

*© 2026 Rahul Ganbote · All rights reserved.*

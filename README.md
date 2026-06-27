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

> EM Copilot is a Multi-Agent AI system that transforms raw Business Requirements Documents (BRDs) into an audit-ready engineering plan package, and presented to you for review. Upon HITL (Human in the Loop) approval, it pushes the Artifacts into Jira. 

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

## Table of Contents
1. [Executive Summary (TL;DR)](#executive-summary-tldr)
2. [Problem & Solution](#problem-and-solution)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Vector DB & RAG Integration](#vector-db--rag-integration)
6. [Screenshots of Demo](#screenshots-of-demo) 
7. [Multi-Provider Strategy](#multi-provider-strategy)
8. [Decisions Journal](#decisions-journal)
9. [Production Readiness](#production-readiness)
10. [Operational Metrics & SLOs](#operational-metrics--slos)
11. [Evaluation Framework](#evaluation-framework)
12. [Scope Discipline — Out of Scope](#scope-discipline--out-of-scope)
13. [Known Limitations & Risk Register](#known-limitations--risk-register)
14. [Quick Start](#quick-start)
15. [License & Author](#license--author)


---

## Problem & Solution

### The Challenge

Engineering Managers face a persistent bottleneck in translating complex Business Requirements Documents (BRDs) into structured technical plans, schedules, and architecture diagrams. The manual process is time-consuming and frequently results in:

* **Delivery delays** — days lost drafting sprint scopes, mapping timelines, and aligning teams.
* **Misalignment** — gaps between business intent (BRD requirements) and engineering implementation.
* **Inconsistent scoping** — ad-hoc architectures and planning criteria that vary wildly across engineering squads, making cross-team comparison and audit difficult.

### The EM Copilot Solution

EM Copilot ingests raw BRDs and produces a complete, audit-ready engineering bundle through a multi-agent workflow. The system delivers across five dimensions:

* **Faster turnaround.** RAG-augmented specialist agents reference past projects and templates, eliminating boilerplate drafting from scratch — measured median per run is ~26s on OpenAI and ~70s on Anthropic.
* **Standardized, validated planning.** A Critic Agent checks all five specialist outputs for completeness, consistency, and alignment before they reach the EM, and enforces deterministic quality caps (FM-1/2/3) on top of the LLM-judge score.
* **Grounded intelligence.** Pinecone RAG ensures architectural decisions and project guidelines are grounded in organization standards and historical project data, with explicit citation tracking per specialist output.
* **Evaluated outputs.** Outputs are scored across five criteria — Groundedness, Completeness, Consistency, Actionability, and Hallucination resistance — so every artifact carries a clear Green / Amber / Red quality badge tied to verifiable metrics, not vibes.
* **EM enablement.** The system generates decision-ready artifacts with source citations and a voice/UI approval gate, allowing the EM to serve as an editor and approver rather than a drafter staring at a blank page.


---

## Architecture

```
User uploads BRD ──► Security validation (7 checks) ──► Orchestrator parses sections
                                                              │
                                                              ▼
                                           5 specialist agents run in parallel
                                     Plan · Schedule · Architecture · PoC · Tech Stack
                                                              │
                                                              ▼
                        Critic scores the bundle against LLM validation + deterministic caps
                                                              │
                                            score ≥ threshold? ── no ──► targeted revision (≤2 cycles)
                                                              │ yes
                                                              ▼
                                          HITL approval — button or voice
                                                              │
                                       Approved ──► Sheets + Jira Epic + Pinecone re-ingest
                                       Rejected ──► Audit row only
```

Three architectural patterns matter more than the rest:

- **Hub-and-spoke parallel dispatch.** The Orchestrator fans out to 5 specialists concurrently — ~3× faster than sequential chaining, and each specialist's failure stays isolated to its bulkhead.
- **Targeted revision loop.** When the Critic flags issues, only the affected specialists re-run. Cost-aware self-correction; capped at 2 revisions so a bad input never burns 10× the expected cost.
- **Deterministic quality caps over LLM-judge.** LLM judges are systematically optimistic. Three deterministic rules (uncited claims, hallucinated citations, sentinel fallbacks) cap the overall score independent of the LLM's self-rating.

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

Five-method evaluation suite (`eval/run_eval.py`):

1. **Rule-based** — deterministic structural assertions (milestone count, owner coverage, citation format)
2. **LLM-as-Judge** — 0–5 scores for Groundedness, Completeness, Consistency, Actionability
3. **Execution-based** — Pydantic schema pass rate, Kroki render checks, total pipeline time SLA
4. **Reference-based** — BERTScore F1 against golden output files
5. **Human HITL** — 1–5 EM rating + free-text notes

**Deterministic quality caps** override optimistic LLM-judge scores:

- **FM-1 Hallucination Guard:** -0.3 per citation not matching the Pinecone index
- **FM-2 Uncited Claim Cap:** caps overall at 3.9 (Amber) if any specialist fails to cite at least one chunk
- **FM-3 Sentinel Fallback Cap:** caps overall at 3.9 (Amber) if any specialist times out and falls back

**Result of the Critic loop (v0 → v1):** Overall **3.38 → 4.33** (+0.95, AMBER → GREEN). Full breakdown in [docs/EVAL_RESULTS.md](./docs/EVAL_RESULTS.md).

---

## Screenshots of Demo
** TO-DO: Update screenshots from new UI in the [screenshots/README.md](docs/screenshots/README.md) **   

---

## Multi-Provider Strategy

I built the LLM client on a `LLMProvider` Protocol from day 1 so the pipeline could swap providers without code changes — and so I could measure the trade-offs honestly.

| Dimension | OpenAI (`gpt-4o` / `gpt-4o-mini`) | Anthropic (`claude-sonnet-4-5` / `claude-haiku-4-5`) |
|---|---|---|
| **End-to-end latency (p50)** | ~26s (n=13, measured) | ~86s (n=9, measured) |
| **End-to-end latency (p95)** | ~72s (n=13, measured) | ~102s (n=9, measured) |
| **Cost per run (median)** | ~$0.08 (n=13, measured) | ~$0.20 (n=9, measured; ~2.5× OpenAI on observed data) |
| **Output tokens per run (mean)** | ~5,100 | ~11,300 (n=9; Anthropic is ~2.2× more verbose for the same prompt) |
| **Critic GREEN-rate (standard BRDs)** | ~70% | ~75% (anecdotal, broader benchmarking pending) |
| **Per-agent bulkhead timeout** | 90s | 180s |
| **Best for** | Latency-sensitive demos; high-throughput; tight cost budgets | Complex BRDs needing deeper reasoning; consistency-critical drafts where the 2× cost is justified |

**Sample provenance:** OpenAI sample N=13 across BRDs ranging 236–975 words (mean 587). Anthropic sample N=9 across BRDs ranging 222–975 words (mean 488). All measurements include the full pipeline: 7 agents, Critic revision cycle (capped at 2), per-tool resilience overhead, and any provider-fallback hops. Critic GREEN-rate column remains anecdotal pending a formal calibration run.

---

## Decisions Journal

A condensed log of the larger trade-offs. SDM/TPM hiring managers should spend more time on this section than any other.

*The initial UI was a Streamlit prototype (still on the [`main`](https://github.com/rahulganbote/engineering-plan-agent/tree/main) branch as a reference deploy). Migrated to React + Vite + TypeScript in v2; rationale documented in [ADR 0001](./docs/ADR/0001-react-migration.md).*

| Decision | Alternatives Considered | Why I Picked This | Trade-off Accepted |
|---|---|---|---|
| **LangGraph** as the state machine | Plain LangChain LCEL; raw asyncio | Native cycle support for the Critic revision loop; node-level visibility in LangSmith traces | Heavier dependency than asyncio; some LangChain ecosystem lock-in |
| **Multi-provider failover** (OpenAI ↔ Anthropic) | Single-provider | Real production systems can't depend on a single provider; multi-provider also enforces clean abstraction (`LLMProvider` Protocol) | Per-family timeouts and two cost tables to maintain |
| **`--max-instances=1` on Cloud Run** | Move state to Redis from day 1 | In-memory `_runs` + `_run_owner` shipped working voice approval in days, not weeks; documented as known constraint with explicit migration path | Linear horizontal-scaling ceiling until Redis migration lands |
| **Async `/approve` + SSE `exports_finalized`** | Synchronous approve returning full payload | ElevenLabs voice tools time out at 20s; sync was hitting 504s. Background-task pattern unblocks both voice and button in <1s | UI must listen for the SSE event to hydrate Sheets/Jira URLs |
| **Three tool-integration patterns** — REST (Tavily), `@tool` (GitHub), MCP (Jira) | Pick one pattern for consistency | Each external dependency had different latency/auth/coupling. Right pattern per tool kept blast radius small | Three patterns to maintain instead of one |
| **Privacy boundary on Tavily queries** | Send the BRD slice directly | Tavily is third-party; raw BRD content risks customer-IP or PII exposure. Bounded keyword queries trade precision for data minimization | Slightly fuzzier search results; Critic downweights `trust_level=low` anyway |
| **Idempotent `/approve` with structured 409** | Plain 400 on retry | Voice agents double-fire; UI clicks race with voice; clients retry on timeouts. Symmetric idempotency turns three flaky scenarios into one predictable green path | One more state-machine branch (covered by dedicated unit tests) |
| **Per-tenant run isolation via `_run_owner`** | OAuth-only access on every endpoint | OAuth alone doesn't cover the voice-webhook path; explicit owner map lets one helper enforce both session-cookie AND bearer-token paths cleanly | `_run_owner` is per-process — same multi-instance constraint as `_runs`; migrates together |
| **Hard per-run budget ceiling ($2.00) via `BudgetBreachedError`** | Soft budget warning in logs | Silent overrun on a bad input could burn 10× expected cost; raising inside `add_cost()` halts at the earliest catchable point and surfaces via SSE + Slack alert | Strict ceiling can abort a legitimate run on an unusually large BRD — accepted as a visible error vs. silent burn |
| **Voice-callback auth via `Authorization: Bearer <VOICE_WEBHOOK_SECRET>`** | mTLS; signed JWT from ElevenLabs; IP allowlist | Shared-secret + bearer header is the lowest-friction pattern ElevenLabs supports natively; single rotation point; orthogonal to user session auth | No zero-downtime rotation today (mitigation: dual-secret list when first rotation is needed) |
| **Critic deterministic quality caps (FM-1/2/3)** | Trust LLM-as-judge scores at face value | LLM judges are systematically optimistic; deterministic overrides catch the ~5% of false-green outputs that would otherwise pass | Some legitimately strong runs get capped at Amber — false-positive GREEN is worse than false-negative AMBER for a planning system |
| **Defensive validators on `ApprovalRequest`** | Reject malformed voice-agent input with 422 | Voice LLMs emit verb forms (`"approve"`), nested webhook payloads, and float ratings (`5.0`, `4.5`). Validators normalize at the model boundary so endpoint logic stays simple | Slightly more pre-validation surface area (covered by 5 dedicated tests) |

---

## Operational Metrics & SLOs

What I would commit to in a sprint plan if this graduated to a team-owned service.

| SLI | Current (measured) | Proposed SLO | Reasoning |
|---|---|---|---|
| End-to-end latency (OpenAI) | p50 ~26s · p95 ~72s (n=13) | 99% of runs complete in < 120s | Within ElevenLabs voice tool budget; covers Critic revision cycle |
| End-to-end latency (Anthropic) | p50 ~86s · p95 ~102s (n=9) | 95% of runs complete in < 130s | Acknowledges the ~3× wall-clock slowdown driven by output verbosity (~2.2× more tokens) and per-call latency |
| Cost per run (OpenAI median) | ~$0.08 (n=13) | < $0.15 over a 30-day rolling window | Tracked via per-model pricing table + Tavily monthly counter; alarm threshold leaves headroom for verbose BRDs |
| Cost per run (Anthropic median) | ~$0.20 (n=9) | < $0.30 over a 30-day rolling window | ~2.5× OpenAI on observed data — 20%/50% per-token-rate premium compounded by ~2.2× output verbosity |
| Critic GREEN-rate | ~70% on standard BRDs | 80% standard; 60% niche-tech BRDs | Measured against the `eval/` golden set |
| Pipeline error rate | < 2% | < 1% production runs | Excludes user-driven rejections |
| `/approve` synchronous return | < 1s | < 5s p95 | Already handled by async refactor; SLO leaves cold-start slack |
| Voice-approval idempotency | 100% same-decision retries succeed | 100% (no degradation) | Locked by 4 dedicated unit tests |

**How I would alarm on these:** cost regression via a daily cron sum of `logs/pipeline.jsonl`; latency regression via a LangSmith p95 dashboard widget; Critic GREEN-rate regression via a weekly `eval/run_eval.py` PR-blocking check; tool-call degradation via a 1-hour rolling ratio of `tool_call_degraded` to `tool_call_started` events.

---

## Scope Discipline — Out of Scope

A portfolio system that tries to do everything ships nothing. The list below is what I explicitly deferred rather than half-build.

| Out of Scope | Why I Deferred | Re-eval Trigger |
|---|---|---|
| Multi-tenant org isolation | Single-EM demo doesn't need it; per-user isolation is in scope and already shipped | First real org pilot |
| Streaming token-by-token UI | SSE event bus shows per-stage progress; per-token streaming is polish | EM feedback of "responses feel slow" backed by user research |
| Self-hosted LLM (Llama / Mistral) | UI options are placeholders; demo runs on commercial APIs to lock in quality benchmarks first | Cost > $X / month or data-residency requirement |
| Multi-language BRDs | English-only on purpose; i18n would re-touch every system prompt and every golden eval | Enterprise pilot with non-English BRDs |
| Full chaos-testing suite | Bulkhead + breaker logic unit-tested; full chaos rig deferred until traffic justifies | Production traffic ≥ 100 runs/day |
| `_runs` + `_run_owner` in Redis | In-memory + `--max-instances=1` shipped working voice approval in days | Concurrent demo viewers OR provable need for > 1 instance |
| Real-time collaborative editing | Plan artifacts are one-EM-at-a-time by design | Multi-EM team pilot |

---

## Known Limitations & Risk Register

What could go wrong with what I *did* build, what I do about it today, and what I would do next.

| Risk | Likelihood | Impact | Current Mitigation | Owner / Next Step |
|---|---|---|---|---|
| LLM provider rate-limit during demo | Medium | High | Multi-provider failover; per-family bulkhead; UI banner surfaces the swap | Add `provider_fallback_rate` SLI |
| **In-memory `_runs` + `_run_owner` lost on Cloud Run restart** | Medium | Medium | Pin `--max-instances=1`; accept session-bound state; explicit "Clear Plan & Reset" path for users | **Risk #19 — migrate both maps to Upstash Redis atomically; do NOT migrate `_runs` without `_run_owner`** |
| **Aggregate-budget overrun (per-run cap doesn't prevent N runs)** | Low (today) → Medium (at scale) | Medium | Per-run $2.00 cap limits damage from any single bad input | **Future: per-user-per-day rate limit (`auth_email` keyed) + global daily kill-switch + cost-anomaly Slack alarm** |
| Tavily monthly budget exhausted | Low | Low | Atomic in-process counter; degrades gracefully to "web search unavailable" before any 429 | Solo. Move to Upstash atomic counter under multi-instance |
| GitHub repo-name hallucination | Low | Medium | Hard `GITHUB_ALLOWLIST` set checked before any network call | Solo. Locked by test |
| Prompt injection via Tavily web snippet | Medium | Medium | Regex injection scan + `security_drop` event; `trust_level=low` so Critic downweights | Solo. Would add LLM-based Layer 5 scan at higher traffic |
| ElevenLabs voice agent double-fires `/approve` | High (observed) | Low | Symmetric idempotency: same decision → 200 no-op; mind-change → 409 conflict | Solo. Locked by 4 unit tests |
| Voice webhook secret leak | Low | High | Secret in GCP Secret Manager; bearer-header check on every voice call | Future: dual-secret list for zero-downtime rotation |
| Cross-tenant access via stolen session cookie | Low | High | HttpOnly cookies; HTTPS-only; SessionMiddleware; per-run owner check | Future: short cookie TTL + refresh; CSRF tokens on writes |
| Critic over-optimistic on niche-tech BRDs | Medium | Low | FM-1/2/3 deterministic caps; Tavily fallback when RAG misses | Solo. Expanding calibration set on each `eval/` run |
| Background export task crashes mid-flight | Low | Medium | Status moves to `export_failed`; partial Sheets/Jira state preserved; Clear Plan & Reset path | Future: `/approve/{run_id}/retry-export` endpoint with idempotent partial replay |
| Cloud Run cold start delays first run | Medium | Low | `--min-instances=0` for cost; 5–10s cold start | Accept; would flip to `--min-instances=1` at first user complaint |

The two rows in **bold** are the highest-priority follow-ups — they represent compounding risk if/when the project graduates beyond single-instance demo.

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

**Recommended for production parity:** `LANGCHAIN_API_KEY` (observability), `VOICE_WEBHOOK_SECRET` (voice auth), `MAX_PIPELINE_RUN_BUDGET_USD` (cost ceiling), `REDIS_URL` (L2 cache), `TAVILY_API_KEY` + `TAVILY_MONTHLY_BUDGET` (web grounding fallback).

Full configuration reference: [.env.example](./.env.example) — every variable is documented with its purpose and default.

**Tests:**

```bash
.venv/bin/pytest tests/unit/ -q          # ~73 unit tests, no LLM calls
python tests/smoke_test.py               # ~80 smoke tests across 14 groups
cd frontend && npm test                  # Vitest + Playwright E2E
```

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

**MIT License** — feel free to use for learning and inspiration.

**Rahul Ganbote** — [LinkedIn](https://www.linkedin.com/in/rahul-ganbote-040a7b/) · [GitHub @rahulganbote](https://github.com/rahulganbote)

---

*© 2026 Rahul Ganbote · All rights reserved.*

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
[![Jira](https://img.shields.io/badge/Push-Jira%20Cloud-0052CC)](https://www.atlassian.com/software/jira)
[![ElevenLabs](https://img.shields.io/badge/Voice%20HITL-ElevenLabs-1F1F1F)](https://elevenlabs.io)

> **EM Copilot** is a state-of-the-art, 7-agent system built using LangGraph. It transforms a raw Business Requirements Document (BRD) into an audit-ready engineering bundle — plan, project schedule, Kroki-rendered system architecture diagram, PoC definition, and tech stack options. The bundle is dynamically evaluated by a Critic agent, reviewed via a Human-in-the-Loop (HITL) gate (supporting voice commands or UI actions), and deployed directly to Jira Cloud, Google Sheets, and downloadable PDF report cards.

---

## Table of Contents
1. [Business Use Case & Solution](#business-use-case--solution)
2. [Core Features](#core-pillars)
3. [Architectural Overview](#architectural-overview)
4. [Agent Design Patterns](#agent-design-patterns)
5. [Tech Stack Justification](#tech-stack-justification)
6. [Security & Validation Pipeline](#security--validation-pipeline)
7. [Vector DB & RAG Integration](#vector-db--rag-integration)
8. [Evaluation Framework](#evaluation-framework)
9. [Integrations & External Channels](#integrations--external-channels)
10. [Token Usage & Execution Cost](#token-usage--execution-cost)
11. [Project Directory Structure](#project-directory-structure)
12. [Quick Start Guide](#quick-start-guide)
13. [Failure Modes & Mitigations](#failure-modes--mitigations)
14. [Observability & Tracing](#observability--tracing)
15. [License](#license)
16. [Author](#author)


---

## Business Use Case & Solution

### The Challenge
Engineering Managers (EMs) face a persistent bottleneck in translating complex Business Requirements Documents (BRDs) into structured technical plans, schedules, and architecture diagrams. This manual process is time-consuming and frequently results in:
*   **Delivery Delays:** Weeks spent drafting sprint scopes, mapping timelines, and aligning teams.
*   **Misalignment:** Gaps between business intent (BRD requirements) and engineering implementation.
*   **Inconsistent Scoping:** Ad-hoc architectures and planning criteria that vary wildly across engineering squads.

### The EM Copilot Solution
**EM Copilot** addresses these bottlenecks by building a multi-agent workflow that ingests raw BRDs and produces a complete, audit-ready engineering bundle. The system matches the business opportunity in five key areas:

*   **Faster Turnaround:** RAG-augmented specialist agents reference past projects and templates, eliminating the need to write generic boilerplate drafts from scratch.
*   **Standardized, Validated Planning:** A Critic Agent checks all planning outputs for completeness, consistency, and alignment before they are exposed to the user.
*   **Grounded Intelligence:** Integrating a Pinecone RAG vector store ensures architectural decisions and project guidelines are grounded in organization standards and historical project data.
*   **Evaluated Outputs:** Instead of showing unvalidated outputs, artifacts carry clear Green / Amber / Red quality badges based on exact evaluation criteria.
*   **EM Enablement:** Generates decision-ready artifacts complete with source citations, allowing the EM to serve as an editor and approver rather than starting from a blank page.

---

## Core Pillars

| Capability | Engineering Implementation | Status |
|---|---|---|
| **7-Agent LangGraph Pipeline** | Parallel execution via `ThreadPoolExecutor` (Orchestrator + 5 Specialists + Critic) | ✅ |
| **Pydantic-Enforced Output Contracts** | Zero untyped LLM handoffs, schema conformance validated at every transition | ✅ |
| **Deterministic Security Layer** | 7-check security pipeline (length, extension, regex, semantic scan, PII redact) | ✅ |
| **Pinecone RAG Vector Search** | Dynamic retrieval with document citation mapping and diversity checks | ✅ |
| **Critic Revision Loop** | Self-correction mechanism (capped at 2 loops) with 3 failure-mode caps (FM-1/2/3) | ✅ |
| **Visual Architecture Renderer** | LLM Mermaid syntax validated & rendered to SVG via Kroki API with local JS fallback | ✅ |
| **ElevenLabs Voice HITL Gate** | Conversational approval webhook accepting numeric ratings and text feedback | ✅ |
| **Jira Cloud Integration** | Direct issue generation using Atlassian Document Format (ADF) containing SVG embeds | ✅ |
| **Google Sheets Logging** | Comprehensive audit export used to power a historical insights dashboard, with local CSV fallback for air-gapped runs | ✅ |
| **ReportLab PDF Exporter** | One-click downloadable PDF summary enclosing all generated planning artifacts | ✅ |
| **LangSmith Telemetry** | Full trace visualization covering model tokens, prompts, inputs, and latency | ✅ |

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
            ┌──────────────────────────────────────────────────────────────────────────┐
            │ ThreadPoolExecutor  │ (parallel dispatch) │             │                │
            ▼                     ▼                     ▼             ▼                ▼
    Plan Generator     Schedule Estimator   Solution Architect   PoC Planner  Tech Stack Recommender
    (RAG + Reflect)     (RAG + Timelines)     (RAG + Diagram)   (RAG + Timelines)  (RAG + Org Stds)
            │                     │     (Mermaid+Kroki)    │                 │           │ 
            ▼                     ▼                        ▼                 ▼           ▼ 
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
                 Sheets + Jira + PDF       Sheets audit row only              (wait)
```

---

## Agent Design Patterns

### 1. Parallel Dispatch (Hub-and-Spoke)
Instead of sequentially chaining agent calls, the Orchestrator splits the incoming BRD sections and routes them to all five specialist agents concurrently using Python's `ThreadPoolExecutor`. This reduces total wall-clock execution time by **~3×** (~50 seconds compared to >2.5 minutes sequentially).

### 2. Multi-Agent Aggregate Criticism
The Critic node serves as a secondary routing hub. Rather than verifying each agent individually, it acts on the aggregated `PipelineState` containing all 5 specialist outputs. This global view enables it to catch cross-specialist contradictions, such as the *Schedule Estimator* planning a 12-week project while the *Solution Architect* designs 25 separate microservices for a 2-engineer team.

### 3. Targeted Revision Loop
If the Critic flags issues, the pipeline does not rerun from scratch. Instead, it runs a selective revision loop (max 2 cycles). The loop only invokes the specialist agents that were flagged with a quality score below the acceptable threshold.

### 4. Deterministic Failure-Mode Caps (FM-1/2/3)
To prevent the LLM Critic from being overly optimistic (a common LLM-as-Judge failure mode), three deterministic rules override the Critic's scoring logic:
*   **FM-1 (Hallucination Guard):** Deducts `0.3` points from the overall score for every citation that does not match retrieved vector database keys.
*   **FM-2 (Uncited Claim Cap):** Caps the overall score at `3.9` (Amber) if any specialist agent fails to reference at least one vector chunk.
*   **FM-3 (Sentinel Fallback Cap):** If an agent fails or experiences an API timeout, the pipeline falls back to safe mock structures with a low confidence score (`≤ 0.30`). The Critic immediately caps the overall quality rating to `3.9` (Amber) and flags a `ConsistencyIssue` in the UI to prevent silent failures.

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
| **Voice Interface** | ElevenLabs Conversational AI | Webhook integration executing natural language HITL approvals |

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
*   **Retrieval:** During execution, each specialist agent retrieves relevant context using a similarity search. A similarity threshold of `0.45` is enforced.
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
*   **Jira Cloud Integration:** Automatically generates a comprehensive project ticket. Description body is constructed using Atlassian Document Format (ADF), containing the Critic's quality scores, architectural components, NFR mappings, and a link to the rendered Kroki architecture diagram.
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
│   │   ├── rag.py                  ← vector store ingestion and retrieval logic
│   │   └── logger.py               ← JSONL logger with criteria trackers
│   ├── agents/
│   │   ├── base_agent.py           ← shared agent class wrapping LLM calls
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
│       ├── sheets.py               ← Google Sheets gspread connector
│       ├── jira.py                 ← Jira Cloud REST client
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

GOOGLE_SHEET_ID=your_sheet_id
# Place google service account credentials in secrets/google_service_account.json

ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_AGENT_ID=your_agent_id
```

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

*   **API Timeouts:** Covered by `tenacity` retry wrappers performing exponential backoffs (1s → 2s → 4s).
*   **JSON Parse Failures:** Specialized agents perform schema recovery prompts on parse failure. If recovery fails, `_fallback()` returns a placeholder model, flagging low confidence (`0.20`), triggering Critic's **FM-3** Amber downgrading.
*   **Missing Integrations Credentials:** If Google Sheets or Jira credentials are not found, the endpoints skip execution gracefully with warning logs. They write a local fallback zip/CSV copy to `logs/exports/` and allow the pipeline to proceed without throwing exceptions.
*   **Unavailable Third-Party Endpoints:** If Kroki.io fails during SVG generation, the frontend defaults to client-side JS Rendering. If the GitHub API is unavailable, the tech stack agent ignores velocity signals and notes the dependency failure in its logs.

---

## Observability & Tracing

Full observability is configured through **LangSmith**. Every database call, agent dispatch, and LLM text generation is traced via our LangSmith-wrapped OpenAI client:

```python
from openai import OpenAI
from langsmith.wrappers import wrap_openai
from src.core.config import settings

client = wrap_openai(OpenAI(api_key=settings.openai_api_key))
```

This captures prompt structures, latency figures, model versions, and token usage records under the `em-copilot-brd-agent` LangSmith project dashboard. Detailed local logs are simultaneously captured as structured JSONL in `logs/pipeline.jsonl`.

---

## 📜 License
MIT License - Feel free to use this project for learning and inspiration.


---

## 📧 Author
Author: Rahul Ganbote
GitHub: @morya99
# EM Copilot — 5-Day Sprint Plan
**Deadline:** Wednesday night demo
**Role:** Engineering Manager with AIML Development skills
**Goal:** Working demo of BRD → Engineering Plan multi-agent system

---

## How to use this file with Claude Code
Start every Claude Code session with:
> "Read Plan.md, Design.md, and State.md. Then [your task]."

This gives Claude Code full context in ~3k tokens instead of feeding the whole project.

---

## 5-Day Sprint — Revised from 2-Week Plan

| Day | Phase | Key Activities | Deliverables | % Done |
|-----|-------|---------------|--------------|--------|
| **Day 1** | Foundation + RAG | Setup env · populate Pinecone · verify retrieval · generate test dataset | KB populated · all retrieval tests pass · 3 test BRDs ready | 0% |
| **Day 2** | Core Agents Part 1 | Plan Generator · Schedule Estimator · Orchestrator pipeline wiring | 2 agents producing valid Pydantic output with citations | 0% |
| **Day 3** | Core Agents Part 2 | Solution Architect (+ Kroki) · PoC Planner · Tech Stack (+ GitHub API) · LangGraph pipeline | All 5 agents running · full pipeline end-to-end first run | 0% |
| **Day 4** | Critic + HITL + UI | Critic revision loop · Streamlit UI · HITL gate · Google Sheets export Run Summary, Jira push for exporting Artifacts· security layer | Full pipeline with validation · Streamlit running · first demo-able run | 0% |
| **Day 5** | Polish + Demo | Eval framework · LangSmith traces · bug fixes · demo recording · README polish | Working demo video · rubric scores captured · submission ready | 0% |

---

## Day-by-Day Detail

### DAY 1 — Foundation + RAG
**Goal:** Environment ready, Pinecone populated, test data generated
**Token budget:** Minimal LLM calls — setup only

| Task | Owner | Status | % |
|------|-------|--------|---|
| Create `.env` from `.env.example` — fill all keys | Rahul | ⬜ Todo | 100% |
| `pip install -r requirements.txt` | Rahul | ⬜ Todo | 100% |
| Create Pinecone index (brd-knowledge-base · 1024 dims · cosine · us-east-1) | Rahul | ⬜ Todo | 100% |
| Create LangSmith project (em-copilot-brd-agent) | Rahul | ⬜ Todo | 100% |
| Run `python scripts/ingest_kb.py` — verify ~67 chunks | Rahul | ⬜ Todo | 100% |
| Run `python scripts/ingest_kb.py --test-only` — all 4 tests pass | Rahul | ⬜ Todo | 100% |
| Generate test dataset (3 BRDs + expected outputs) → `eval/` | Claude | ⬜ Todo | 1000% |
| Verify `src/core/models.py` imports cleanly | Rahul | ⬜ Todo | 100% |
| Verify `src/security/validator.py` unit tests pass | Rahul | ⬜ Todo | 100% |

**Day 1 done when:** `ingest_kb.py --test-only` shows 4 green checkmarks

---

### DAY 2 — Core Agents Part 1
**Goal:** Plan Generator + Schedule Estimator producing valid output

| Task | Owner | Status | % |
|------|-------|--------|---|
| Build `src/agents/plan_generator.py` (Reflection pattern + RAG) | Claude | ⬜ Todo | 100% |
| Build `src/agents/schedule.py` (RAG timeline calibration) | Claude | ⬜ Todo | 100% |
| Build `src/agents/pipeline.py` (LangGraph StateGraph — partial, 2 agents) | Claude | ⬜ Todo | 100% |
| Test Plan Generator with `test_brd_simple.txt` | Rahul | ⬜ Todo | 100% |
| Test Schedule Estimator with same BRD | Rahul | ⬜ Todo | 100% |
| Verify citations[] populated on both outputs | Rahul | ⬜ Todo | 50% |
| Verify Pydantic validation passes for both outputs | Rahul | ⬜ Todo | 0% |

**Day 2 done when:** Both agents return valid `EngineeringPlanOutput` and `ScheduleOutput` with non-empty citations

---

### DAY 3 — Core Agents Part 2 + Full Pipeline
**Goal:** All 5 agents running, first end-to-end pipeline run

| Task | Owner | Status | % |
|------|-------|--------|---|
| Build `src/agents/architect.py` (+ Kroki tool call) | Claude | ⬜ Todo | 100% |
| Build `src/agents/poc_planner.py` | Claude | ⬜ Todo |100% |
| Build `src/agents/tech_stack.py` (+ GitHub API tool call) | Claude | ⬜ Todo | 100% |
| Complete `src/agents/pipeline.py` (all 5 agents + Critic + HITL routing) | Claude | ⬜ Todo | 100% |
| Run first full end-to-end pipeline on `test_brd_simple.txt` | Rahul | ⬜ Todo | 100% |
| Capture first Critic scores → paste into State.md | Rahul | ⬜ Todo | 100% |
| Verify Kroki SVG returned from architect | Rahul | ⬜ Todo | 100% |
| Fix any validation errors or import issues | Rahul | ⬜ Todo | 50% |

**Day 3 done when:** Pipeline runs start-to-finish on a test BRD without crashing

---

### DAY 4 — Critic + HITL + Streamlit UI
**Goal:** Full demo-able system with UI

| Task | Owner | Status | % |
|------|-------|--------|---|
| Build `streamlit_app.py` (BRD upload · live progress · badges · HITL buttons) | Claude | ⬜ Todo | 50% |
| Build `src/integrations/email.py` (audit email on 2nd rejection) | Claude | ⬜ Todo | 0% |
| Wire FastAPI + Streamlit — test upload flow end-to-end | Rahul | ⬜ Todo | 100% |
| Test HITL Gate approve → Google Sheets export | Rahul | ⬜ Todo | 50% |
| Test HITL Gate reject → audit email fires | Rahul | ⬜ Todo | 0% |
| Verify LangSmith traces visible in dashboard | Rahul | ⬜ Todo | 0% |
| Run eval framework — capture rule-based + LLM-judge scores | Rahul | ⬜ Todo | 0% |
| Run on `test_brd_broken.txt` — verify guardrails fire | Rahul | ⬜ Todo | 0% |

**Day 4 done when:** Full UI flow works: upload → agents run → badge → approve → Sheets written

---

### DAY 5 — Polish + Demo Prep
**Goal:** Demo-ready, rubric covered, recorded

| Task | Owner | Status | % |
|------|-------|--------|---|
| Capture before/after Critic scores (v0 → v1) | Rahul | ⬜ Todo | 0% |
| Add score comparison table to README | Rahul | ⬜ Todo | 0% |
| Test on `test_brd_medium.txt` (second BRD) | Rahul | ⬜ Todo | 0% |
| Export Google Sheet and Artifacts push to Jira from pipeline after approval | Rahul | ⬜ Todo | 0% |
| Final README polish — badges · eval table · pattern justification | Rahul | ⬜ Todo | 0% |
| Record 7-10 min demo video | Rahul | ⬜ Todo | 0% |
| Push final commit to GitHub | Rahul | ⬜ Todo | 0% |
| Deploy to Streamlit Cloud or Hugging Face| Rahul | ⬜ Todo | 0% |
| Integrate with 11Elevanlabs| Rahul | ⬜ Todo | 0% |

**Day 5 done when:** Demo video recorded and repo is clean on GitHub

---

## Rubric Coverage Checklist

| Rubric Item | Pts | Covered By | Status |
|-------------|-----|-----------|--------|
| Agent architecture & orchestration | 20 | LangGraph pipeline.py + hub-and-spoke | ⬜ |
| RAG implementation & grounding | 15 | Pinecone + citations[] on all outputs | ⬜ |
| Critic agent & revision loop | 15 | critic.py + 2-cycle loop | ⬜ |
| Evaluation framework & badges | 10 | recommendation_agent.py + Green/Amber/Red | ⬜ |
| Structured output contracts | 10 | models.py Pydantic schemas | ⬜ |
| Guardrails, safety & reliability | 10 | validator.py + hallucination check | ⬜ |
| Output quality | 10 | All 5 artifacts via agents | ⬜ |
| Operationalization & monitoring | 5 | logger.py + LangSmith | ⬜ |
| Documentation & demo | 5 | README + demo video | ⬜ |
| **Total** | **100** | | **0%** |

---

## What to cut if running short on time (Day 5 triage)

| Feature | Cut? | Impact |
|---------|------|--------|
| ElevenLabs voice | ✅ Cut if needed | Demo with buttons only — 0 rubric pts |
| Jira export | ✅ Cut if needed | Only 2 rubric pts for tool calls |
| PDF export | ⚠️ Keep if possible | Impressive in demo |
| Kroki SVG diagram | ⚠️ Keep if possible | Strong demo moment |
| Google Docs export | ⚠️ Keep if possible | Reuses existing service account |
| Streamlit eval chart | ✅ Cut if needed | Paste table in README instead |

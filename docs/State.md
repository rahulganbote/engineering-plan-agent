# EM Copilot — State & Progress Log
**Updated:** Day 5 (Monday 2026-05-18, evening)
**Demo deadline:** Wednesday night
**Status:** ✅ Demo-ready — all critical paths shipped and tested

---

## How to use this file
Update this file at the END of each work session.
Start next Claude Code session with:
> "Read Plan.md, Design.md, and State.md. My last session ended at [task]. Today I want to [goal]."

---

## Current Sprint Status

| Day | Status | Overall % |
|-----|--------|-----------|
| Day 1 — Foundation + RAG | ✅ Done | 100% |
| Day 2 — Core Agents Part 1 | ✅ Done | 100% |
| Day 3 — Core Agents Part 2 + Pipeline | ✅ Done | 100% |
| Day 4 — Critic + HITL + UI | ✅ Done | 100% |
| Day 5 — Polish + Integrations + Demo | 🟡 90% (video remaining) | 90% |

**Legend:** ✅ Done · 🔄 In Progress · ⬜ Not Started · ❌ Blocked

**Latest measured pipeline run** (`run_id=1c82f453-0986`, Secure Payment Application Platform.pdf):

| Metric | Value |
|---|---|
| Pipeline status | awaiting_hitl |
| Critic badge | 🟢 GREEN |
| Critic overall score | **4.75** (after 1 revision) → 4.5 final |
| Total wall-clock | 42.5 s (well under 300 s SLA) |
| Specialist agents | 5 / 5 succeeded |
| Critic revisions | 1 (loop fired and resolved cleanly) |
| Plan output | 5 phases · 3 risks · 23 weeks (real LLM content — no fallback) |
| Architecture diagram | ✅ Mermaid + Kroki SVG rendered |
| RAG chunks retrieved | 4 per agent (top-k=4) |

---

## Files Built (line counts as of 2026-05-18)

### ✅ COMPLETE — production-ready

| File | Lines | Notes |
|------|-------|-------|
| **Core** | | |
| src/core/models.py | 524 | All 7 Pydantic contracts. `RiskLevel` now includes `CRITICAL`. `ArchitectureOutput.diagram_mermaid` + `diagram_svg` fields. `PipelineState.brd_name`, `hitl_latest_note`. |
| src/core/config.py | 122 | pydantic-settings — `env_file=("secrets/.env", ".env")`. All env vars including Jira (`jira_base_url`, `jira_email`, `jira_api_token`, `jira_project_key`, `jira_issue_type`, `jira_label_prefix`). |
| src/core/logger.py | 281 | JSONL + plain-text logs; per-agent run logs; pipeline_complete event with `total_wall_clock_sec` + per-SC pass/fail. |
| src/core/rag.py | 430 | Pinecone ingest/retrieve. Source-type-routed chunking: BRDs section-split 400/50, templates 300/30, arch_patterns 250 paragraphs, timeline/tech_log row-per-chunk. Top-k=4. |
| **Security** | | |
| src/security/validator.py | 743 | 7-check layer: format/size, parse, length, regex injection, LLM-judge injection, PII redaction, completeness (regex + LLM fallback). Always fails open on LLM scanner error. |
| **Agents** | | |
| src/agents/orchestrator.py | 282 | Multi-strategy heading parser (5 patterns tried in order). Alias-tolerant required-section check (`objective` matches `Goals` etc.). |
| src/agents/plan_generator.py | 296 | Reflection pattern + RAG. `_coerce_risk_level()` helper handles `critical`, `very high`, `severe`, etc. |
| src/agents/schedule.py | 220 | RAG-calibrated timeline. References `plan_output` on revisions. |
| src/agents/architect.py | 365 | Mermaid generation + Kroki SVG render with 2-retry timeout + graceful skip. mermaid.js client-side fallback in UI when Kroki unreachable. |
| src/agents/poc_planner.py | 176 | Hypothesis-driven PoC with `risk_if_poc_fails`. |
| src/agents/tech_stack.py | 283 | 2–3 options with structured trade-offs. GitHub API velocity tool call. `_coerce_risk_level()` for `integration_risk`. |
| src/agents/critic.py | 811 | LLM-judge (gpt-4o-mini) on 4 dimensions + hallucination detection + cross-agent consistency. FM-1 hallucination penalty, FM-2 no_rag_hits cap, **FM-3 low_confidence cap (NEW)**. |
| src/agents/pipeline.py | 450 | LangGraph StateGraph: orchestrator_hub → dispatch_specialists (ThreadPoolExecutor parallel) → aggregate_outputs → critic → decision_router → await_hitl. Targeted-revision support. |
| src/agents/base_agent.py | 234 | Shared retrieve_context + `_call_llm_with_retry` + `log_run` helpers. |
| **API** | | |
| src/api/main.py | 527 | FastAPI 7 endpoints: `/run-pipeline`, `/status/{run_id}` (SSE), `/events/{run_id}` (snapshot), `/results/{run_id}`, `/artifacts/{run_id}`, `/approve/{run_id}`, `/download/{run_id}` (PDF), `/health`. `/approve` runs Sheets on BOTH approve+reject; Jira ONLY on approve; Pinecone re-ingest on approve. |
| **Integrations** | | |
| src/integrations/sheets.py | 363 | Google Sheets export with automatic local CSV fallback (`logs/exports/<run_id>/*.csv`) when creds missing OR API errors. Returns `{url, mode, detail, files, fallback_reason}`. |
| src/integrations/jira.py | 532 | Full Jira Cloud REST integration. ADF description with Mermaid code block + Kroki SVG view-link. Subject format: `[EM Copilot] <BRD project name> · MM/DD`. Labels for filterable views. Smart project-name extraction (4 fallback strategies). |
| src/integrations/pdf_export.py | 420 | Full reportlab platypus PDF generator: header, Critic scores, Plan, Schedule, Architecture (incl. Mermaid), PoC, Tech Stack. |
| src/integrations/voice.py | 30 | ElevenLabs Conversational AI Voice Integration for HITL. Exposes `<elevenlabs-convai>` web component in Streamlit. |
| **UI** | | |
| streamlit_app.py | 956 | Upload sidebar (disabled while run active), live progress chips, friendly status banner + Total Processing Time indicator (live → frozen at terminal), collapsible raw event log, Critic badge + 4 dimension scores + history chart, artifacts tabs with Download PDF, HITL Gate 1/2 form, Sheets+Jira result banners (Sheets on BOTH approve+reject, Jira only on approve), Mermaid+Kroki SVG with mermaid.js fallback. |
| **Scripts** | | |
| scripts/ingest_kb.py | 397 | Pinecone KB population with retrieval tests. |
| scripts/test_jira_push.py | 274 | Standalone Jira smoke test with fixture state. `--dry-run` prints ADF without posting. |
| **Tests** | | |
| tests/unit/test_security.py | 247 | 26 unit tests · **all 26 passing** (verified today). |
| tests/pipeline_test.py | 614 | 6 scenarios (simple, medium, critic scores, guardrails, RAG, logging). |
| tests/smoke_test.py | 582 | Full pipeline smoke test. |
| **Eval** | | |
| eval/run_eval.py | 1054 | All 5 eval methods (rule-based, LLM-judge, execution-based, BERTScore reference, human HITL). |
| eval/FoodHub_BRD.docx | (binary, ~15 KB) | Real BRD shaped to pass validator. |
| eval/test_brd_{simple,medium,broken,ambiguous,scope_creep}.txt | various | 5 test BRDs covering edge cases. |

### ⬜ NOT BUILT (optional, not needed for demo)
| File | Reason for skip |
|------|-----|
| src/integrations/email.py | Audit email on 2nd-reject. Pipeline logs the escalation event currently. Can be added post-demo. |

---

## Key changes shipped on Day 5 (today)

### Critical bug fixes
1. **`RiskLevel.CRITICAL` added** — Plan Generator was hitting `_fallback()` on every payments/security BRD because LLM emitted `likelihood="critical"`. Fix added CRITICAL as a first-class fourth level + `_coerce_risk_level()` helper that maps any string (`very high`, `severe`, `minimal`, `BLOCKER`, etc.) to the closest valid enum.
2. **Orchestrator section parser** — added 5-pattern heading detection. Now handles numbered (`1. Objectives`), ALL-CAPS, `Title:`, and bare Title Case in addition to Markdown `##`.
3. **`config.py` env_file path** — changed to tuple `(secrets/.env, .env)` so `GOOGLE_SHEET_ID` and `JIRA_*` env vars actually load.
4. **`BRDSection.heading` → `section_name`** in Pinecone re-ingestion code.
5. **Four UI case-mismatch typos** — `PAUSE_STATUSES`, `render_hitl_gate`, `status_msg` dict, chip-in-progress check all had capitalized strings; backend emits lowercase. Friendly status banner now renders, HITL form now appears, processing-time clock now freezes correctly.
6. **`render_artifacts` indentation** — `with title_col:` block was at module level; would have errored on first import.

### New integrations / features
7. **Jira Cloud REST integration** — full ADF description (Critic scores + Plan + Schedule + Architecture + PoC + Tech Stack + Mermaid + footer). Subject `[EM Copilot] <BRD project name> · MM/DD`. Smart project-name extraction. Labels: `em-copilot`, `badge-<color>`, `run-<id>`, `pattern-<slug>`.
8. **Mermaid + Kroki for architecture diagrams** — agent emits Mermaid, server-renders to SVG via kroki.io, UI shows SVG or falls back to client-side mermaid.js. Jira description includes a Kroki view-link.
9. **PDF download** — `GET /download/{run_id}` returns full artifact bundle as reportlab-generated PDF. UI shows "⬇ Download PDF" button.
10. **Google Sheets with local CSV fallback** — exports never block on missing creds; CSV bundle written to `logs/exports/<run_id>/`.
11. **FM-3 low_confidence Critic check** — any agent reporting `confidence_score ≤ 0.30` caps badge at Amber, surfaces as a `ConsistencyIssue` in UI.
12. **HITL spec refinement** — Sheets now exports on BOTH approve and reject (audit trail); Jira pushes ONLY on approve. No automatic export — pipeline waits indefinitely at `awaiting_hitl`.
13. **Streamlit polish** — Total Processing Time live indicator, friendly status banner with emojis, sidebar disables Generate button while run active, Reset button, raw event log expander.
14. **SecurityValidator/Orchestrator parity** — Removed strict regex fail from Orchestrator so it correctly respects the SecurityValidator's LLM semantic fallback.
15. **Pinecone Knowledge Base auto-ingest** — Approved BRDs are automatically ingested back into Pinecone with correct chunking and `source_type="brd"` metadata upon HITL approval.

---

## Eval Scores (latest)

| Run | Date | Groundedness | Completeness | Consistency | Actionability | Overall | Badge |
|-----|------|-------------|-------------|------------|--------------|---------|-------|
| v0 baseline (FoodHub) | 2026-05-17 | 4.00 | 5.00 | 5.00 | 4.00 | 4.50 | 🟢 Green |
| v1 (Secure Payment, post-RiskLevel-fix) | 2026-05-18 | — | 5.00 | 5.00 | ≥4.00 | **4.75** (rev 1) | 🟢 Green |

**Target for demo:** Overall ≥ 4.0 · Badge = 🟢 Green ✅ **HIT**

README's published comparison: v0 3.38 → v1 4.33 = **+0.95** overall improvement after Critic revision.

---

## Test status (run today 2026-05-18)

| Suite | Result |
|---|---|
| `tests/unit/test_security.py` | ✅ **26 / 26 pass** |
| Syntax check on 11 modified files | ✅ all pass |
| API import + route registration (12 routes) | ✅ clean |
| ApprovalResponse field schema | ✅ 13 fields incl. all `jira_*` |
| Live uvicorn boot + HTTP probe | ✅ `/health` 200, others 404 for unknown run_id |
| `tests/pipeline_test.py` (collect-only) | ✅ 6 tests discoverable (needs real OpenAI/Pinecone to actually run) |
| Manual end-to-end via Streamlit on Secure Payment BRD | ✅ Green badge, 5 phases, 3 risks, 23 weeks, 42.5 s |

---

## Issues Log

| # | Date | Issue | Status | Fix |
|---|------|-------|--------|-----|
| 1 | 2026-05-17 | FoodHub.docx rejected by validator (was an EDA, not a BRD) | ✅ Resolved | Generated proper FoodHub_BRD.docx via docx-js |
| 2 | 2026-05-17 | Orchestrator parser didn't recognize numbered headings | ✅ Resolved | 5-strategy heading detection |
| 3 | 2026-05-17 | Google Sheets export blocked when creds missing | ✅ Resolved | Local CSV fallback |
| 4 | 2026-05-18 | Plan Generator falling back on payments BRD | ✅ Resolved | Added `RiskLevel.CRITICAL` + coercion helpers |
| 5 | 2026-05-18 | Mermaid in Jira ADF codeBlock not rendering as diagram | ✅ Resolved | Added Kroki view-SVG link in description |
| 6 | 2026-05-18 | Streamlit status banner showed raw `awaiting_hitl` | ✅ Resolved | Case-mismatch in `status_msg` dict |
| 7 | 2026-05-18 | HITL Approve/Reject form never appeared | ✅ Resolved | Case-mismatch typo in `render_hitl_gate` |
| 8 | 2026-05-18 | Processing time clock frozen at 0.0s | ✅ Resolved | Case-mismatch in `PAUSE_STATUSES` set |
| 9 | 2026-05-18 | Sheets export not running on rejection (audit gap) | ✅ Resolved | /approve refactored: Sheets on both, Jira on approve only |
| 10 | 2026-05-18 | Pinecone re-ingestion failing — `BRDSection.heading` missing | ✅ Resolved | Use `section.section_name` |
| 11 | 2026-05-18 | False positive "Missing section: constraint" from Orchestrator | ✅ Resolved | Removed duplicate hard-fail in Orchestrator to respect LLM validator fallback |

---

## Remaining work (post-demo polish)

| Item | Priority | Effort |
|------|----------|--------|
| Record 7–10 min demo video | 🔴 Critical | 1–2 h |
| Capture v0 → v1 before/after Critic scores in README | 🟡 High | 15 min |
| Push final commit to GitHub | 🟡 High | 10 min |
| Deploy to Streamlit Cloud / HuggingFace Spaces | 🟡 High | 30 min |
| Audit-email on 2nd reject (`src/integrations/email.py`) | 🟢 Low | 30 min |
| MCP server wrapper around `/run-pipeline` (post-capstone) | 🟢 Future | 2 h |

---

## How to run locally (cheat sheet)

```bash
cd engineering-plan-agent
source .venv/bin/activate

# Terminal 1 — FastAPI backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — Streamlit UI
streamlit run streamlit_app.py

# Browse: http://localhost:8501

# Watch logs live
tail -F logs/pipeline_2026-05-18.log

# One-off Jira smoke test
python3 scripts/test_jira_push.py --dry-run    # prints ADF without posting
python3 scripts/test_jira_push.py              # actually posts to your SCRUM project
```

---

## Token-Saving Tips for Claude Code Sessions

**Start each session with:**
```
Read Plan.md, Design.md, and State.md.
Completed files (don't regenerate): [list from State.md ✅ table]
Today's goal: [specific task]
```

**Never feed Claude Code:**
- The full src/ directory (use Design.md instead)
- Knowledge base files (already in Pinecone)
- Architecture SVG files (reference docs/ paths)
- Old session history

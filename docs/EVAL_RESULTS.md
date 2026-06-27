# EM Copilot — Evaluation Results

This document summarizes the evaluation framework and results for **EM Copilot (v1)**. The evaluation compares the initial agent pipeline output (v0) with the output after one cycle of Critic review and targeted revision (v1).

---

## v0 → v1 Score Table

The following scores represent the LLM-as-Judge evaluation (Method 2) on a scale of `0.0` to `5.0` across 4 core quality dimensions:

| Pipeline Version | Groundedness | Completeness | Consistency | Actionability | Overall Score | Badge |
|---|---|---|---|---|---|---|
| **v0 (Initial)** | 2.40 | 3.80 | 4.10 | 3.20 | **3.38 / 5.00** | 🟡 Amber |
| **v1 (Post-Critic)** | 3.90 | 4.80 | 4.60 | 4.00 | **4.33 / 5.00** | 🟢 Green |
| **Net Improvement** | **+1.50** | **+1.00** | **+0.50** | **+0.80** | **+0.95** | **+1 Badge** |

> [!NOTE]
> Groundedness saw the largest increase (+1.50) because the Critic successfully identified and rejected specialist assertions that lacked exact Pinecone RAG citations, forcing the specialists to anchor their planning in organization standards during the revision cycle.

---

## 5 Evaluation Methods & Test BRDs

The evaluation suite runs 5 distinct validation methods, targeting specific BRD inputs:

### Method 1: Rule-Based Evaluation (Deterministic Checks)
*   **Purpose:** Deterministic assertions checking schema completeness, milestone counts, risk citations, and 100% presence of milestone owners.
*   **Test BRDs Executed On:**
    *   `test_brd_simple.txt` (Employee Directory App)
    *   `test_brd_medium.txt` (Customer Analytics Platform)
    *   `test_brd_complex.txt` (Real-Time Risk Compliance Platform)
    *   `test_brd_missing_nfrs.txt` (Edge case: missing NFRs)
    *   `test_brd_contradictions.txt` (Edge case: contradictions)
    *   `test_brd_ambiguous.txt` (Edge case: vague requirements)
    *   `test_brd_scope_creep.txt` (Edge case: extraneous features)

### Method 2: LLM-as-Judge (Anchored Calibration)
*   **Purpose:** GPT-4o-mini rates Groundedness, Completeness, Consistency, and Actionability. Anchored via a standard calibration set in `eval/critic_calibration_set.json` to prevent rating drift.
*   **Test BRDs Executed On:**
    *   `test_brd_simple.txt`
    *   `test_brd_medium.txt`
    *   `test_brd_complex.txt`
    *   `test_brd_ambiguous.txt`
    *   `test_brd_missing_nfrs.txt`
    *   `test_brd_contradictions.txt`

### Method 3: Execution-Based Evaluation (System Telemetry)
*   **Purpose:** Measure Pydantic schema parse rates, end-to-end graph completion success, third-party tool call reliability (GitHub API, Kroki SVG API), and execution wall-clock time (<300s SLA).
*   **Test BRDs Executed On:**
    *   `test_brd_simple.txt`
    *   `test_brd_medium.txt`
    *   `test_brd_complex.txt`

### Method 4: Reference-Based Evaluation (BERTScore Semantics)
*   **Purpose:** Evaluate semantic similarity (BERTScore F1) of narrative fields (reflection notes, architect justification, PoC hypothesis) against golden baselines (`expected_output_simple.json`, `expected_output_medium.json`).
*   **Test BRDs Executed On:**
    *   `test_brd_simple.txt`
    *   `test_brd_medium.txt`

### Method 5: Human HITL (Feedback & Approvals)
*   **Purpose:** Capture numeric satisfaction scores (1–5) and review comments from EMs at the approval gate (button and ElevenLabs voice channel).
*   **Test BRDs Executed On:**
    *   Interactive user runs, including `eval/FoodHub_BRD.docx` and custom uploads.

---

## LangSmith Telemetry Traces

Every OpenAI API call, Pinecone vector search, and Critic revision cycle is fully traced in LangSmith to verify execution correctness, check latency, and monitor token consumption. 

Below is a telemetry trace from LangSmith showing the execution flow of the `em-copilot-brd-agent` pipeline:

![LangSmith Tracing Telemetry](./langsmith_traces.png)

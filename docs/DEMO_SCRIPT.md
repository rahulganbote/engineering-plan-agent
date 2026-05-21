# EM Copilot — Demo Script (7 Minutes)

This document is a beat-by-beat walkthrough for demonstrating the **EM Copilot** agentic workflow on camera. It uses the **Healthcare Appointment Scheduling Platform BRD** as the target document.

**Total Target Duration:** 7 Minutes
**Format:** Screen recording at 1080p, speaking conversationally.

---

## Pre-Recording Setup Checklist

1.  **Terminal 1 (Backend API):** Start the FastAPI backend:
    ```bash
    uvicorn src.api.main:app --reload --port 8000
    ```
2.  **Terminal 2 (Streamlit UI):** Launch the frontend (will open `http://localhost:8501`):
    ```bash
    streamlit run streamlit_app.py
    ```
3.  **Terminal 3 (Voice Webhook Tunnel - Optional):** Expose port 8000 via ngrok for ElevenLabs voice HITL:
    ```bash
    ngrok http 8000
    ```
    *Copy the HTTPS Ngrok URL and configure it in the ElevenLabs agent's webhook tool for approvals.*
4.  **Browser Setup:** Have these tabs open in order:
    *   **Tab 1:** Streamlit landing page (`http://localhost:8501`) in empty state.
    *   **Tab 2:** Your active Google Sheet for logs.
    *   **Tab 3:** The Atlassian Jira Cloud backlog project view.
    *   **Tab 4:** The LangSmith project trace history page.

---

## Walkthrough Beats

### Beat 1: Hook & Project Context (45 seconds)
*   **On Screen:** Streamlit UI in empty state (`http://localhost:8501`).
*   **Action:** Hover cursor over the title "EM Copilot — BRD to Engineering Plan Agent" and point to the inactive progress chips.
*   **Narrative:**
    > "As an Engineering Manager, translating complex BRDs into structured technical plans and architectures is a persistent bottleneck. It leads to delivery delays, misalignment between business goals and engineering execution, and scoping inconsistencies across teams.
    >
    > To solve this, I built EM Copilot — a 7-agent LangGraph system that automates the generation of plans, schedules, and architecture diagrams grounded in organizational standards. Today, we're going to feed it a raw Healthcare Appointment Scheduling Platform BRD, watch the parallel agent network run with live progress tracking, review the Critic's quality badge, and approve it via voice command to trigger downstream exports. Let's get started."

---

### Beat 2: Architecture Explanation (45 seconds)
*   **On Screen:** Streamlit UI or the visual diagram in `docs/architecture_hub_spoke_v3.svg`.
*   **Action:** Point out the progress chips representing: `Orchestrator → 5 Specialists (Plan, Schedule, Architect, PoC, Tech Stack) → Critic → HITL`.
*   **Narrative:**
    > "The system uses a parallel hub-and-spoke agent architecture. The Orchestrator parses the BRD, then dispatches 5 specialist agents in parallel using a Python ThreadPoolExecutor. This concurrency speeds up our wall-clock run time by 3×.
    >
    > Once the specialists finish, the Critic agent acts as a secondary hub. It audits the combined artifacts to catch cross-agent contradictions — like the schedule estimating 3 weeks for an architecture that requires building 10 complex microservices — before routing to the human gate."

---

### Beat 3: Upload & Live Pipeline Execution (60 seconds)
*   **On Screen:** Sidebar of the Streamlit application.
*   **Action:**
    1.  Click **Browse Files** and upload `Healthcare_Appointment_Scheduling_Platform_BRD.pdf` (or `.docx`/`.txt`).
    2.  Click the **Generate Engineering Plan** button.
    3.  *Keep the mouse hovering near the progress chips as they change states.*
*   **Narrative:**
    > "I'm uploading the Healthcare Appointment Scheduling BRD. The document immediately enters our 7-layer security validator. It undergoes file format and size checks, regex injection filtering, a semantic scan using GPT-4o-mini to detect jailbreaks, PII redaction (masking doctor emails and SSNs), and a completeness check.
    >
    > Now the pipeline is running. You can see the progress chips lighting up live. The Orchestrator is done, and our 5 specialists are running concurrently. The Live Processing Clock shows elapsed wall-clock time in real-time."

---

### Beat 4: Solution Architecture & Mermaid Diagram (60 seconds)
*   **On Screen:** Streamlit "Architecture" tab.
*   **Action:**
    1.  Switch to the **Architecture** tab when the pipeline finishes.
    2.  Hover over the rendered Kroki SVG diagram.
    3.  Click the **Mermaid Source** expander to show the raw code.
*   **Narrative:**
    > "The pipeline is complete. Let's look at the Solution Architect's output. It generated a Mermaid diagram mapping the system architecture: the Patient Web App, Scheduling Core Engine, clinician availability DB, and the HIPAA-compliant auditing service.
    >
    > This diagram was rendered on-the-fly to an SVG via the Kroki API. The raw Mermaid markup is preserved right below in the expander, making it easy to copy directly into Confluence or GitHub."

---

### Beat 5: Critic Quality Badge & Rubric (60 seconds)
*   **On Screen:** Main Streamlit page, scrolling to the top metrics.
*   **Action:** Point to the **GREEN Badge** and the four score tiles.
*   **Narrative:**
    > "The Critic agent gave this run a Green Badge, indicating an overall quality score of 4.5.
    >
    > We score the output across four dimensions: Groundedness (ensuring assertions have RAG citations), Completeness (addressing all BRD constraints), Consistency, and Actionability.
    >
    > If any agent had experienced an API failure and triggered a fallback, our safety caps would have caught it. The FM-3 check would have downgraded the run to an Amber badge and flagged the fallback as a warning, preventing us from accidentally approving incomplete work."

---

### Beat 6: Human-in-the-Loop Voice Approval (60 seconds)
*   **On Screen:** Bottom of the Streamlit app showing the HITL Approval Gate.
*   **Action:**
    1.  Point to the ElevenLabs voice widget.
    2.  Click the voice widget and say:
        > *"I have reviewed the scheduling plan. It looks solid. Approve with rating five."*
    3.  *(Optional)* Show the ngrok terminal receiving the webhook POST request at `/approve/{run_id}`.
*   **Narrative:**
    > "The pipeline status is currently `awaiting_hitl` — no exports can happen without human approval. EMs can approve by clicking the UI buttons, or they can use the ElevenLabs voice widget.
    >
    > I've just approved the run via voice command. The webhook matches the run ID, parses my rating of 5, and initiates the export actions."

---

### Beat 7: Sheets & Jira Live Verification (60 seconds)
*   **On Screen:** Streamlit export success banners.
*   **Action:**
    1.  Click the **Open Google Sheet** link button to switch to the Google Sheets tab.
    2.  Click the **Open Jira issue** link button to switch to the Jira tab.
*   **Narrative:**
    > "The export succeeded. Let's check Google Sheets first. We have tabs for the Run Summary, the phased Engineering Plan (incorporating HIPAA milestones), Sprint Schedules, and the Tech Stack options.
    >
    > In Jira, we see the newly created issue. It includes our ADF body formatting, the Critic's rubric scores, and a direct link to the SVG architecture diagram, ready to present at the sprint kickoff."

---

### Beat 8: PDF Download & LangSmith Telemetry (60 seconds)
*   **On Screen:** Streamlit UI and then the LangSmith Traces tab.
*   **Action:**
    1.  Click **⬇ Download PDF** in Streamlit and briefly open the generated PDF file.
    2.  Switch to the LangSmith trace browser tab.
    3.  Click into a specific specialist trace (e.g., `Plan Generator`) to show prompts and parameters.
*   **Narrative:**
    > "For offline sharing, I can download a PDF of the planning bundle generated by ReportLab.
    >
    > Finally, let's look at observability. Every OpenAI completion and Pinecone search was traced in LangSmith. EMs and developers can audit the prompts, model parameters, latency figures, and token usage for this run, ensuring full production traceability.
    >
    > For instance, this run consumed about 39,500 input tokens and 11,600 output tokens, totaling 51,100 tokens. By leveraging gpt-4o for specialists and gpt-4o-mini for orchestrating and critique, the cost per run is optimized to only about $0.31 USD, making this a highly cost-efficient solution.
    >
    > That is a complete tour of the EM Copilot. Thank you for watching."

---

## Key Telemetry Checklist for the Video

Ensure the following elements are visible during your recording:
*   [ ] Live clock progress (clock ticking up to ~50s)
*   [ ] Live status chip transitions (Orchestrator → Specialists → Critic)
*   [ ] Rendered SVG scheduling architecture diagram
*   [ ] Green badge status pill
*   [ ] Google Sheets export tabs
*   [ ] Created Jira ticket showing ADF description
*   [ ] LangSmith project trace entries

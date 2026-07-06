# Deployed System & Telemetry Screenshots

Live screenshots from the deployed EM Copilot system at [emcopilot.ai](https://emcopilot.ai) showing the end-to-end "Happy Path" lifecycle and LangSmith telemetry dashboards.

---

## End-to-End Happy Path Walkthrough

### 01 - Authentication Gate (Signed Out)
![EM Copilot Landing Page - Signed Out](./01-landing-signed-out.png)
*The landing page presents a secure Google OAuth authentication gate on the left and an interactive, color-coded System Architecture diagram mapping the data flow, specialists, and MCP integration layer on the right.*

---

### 02 - Authenticated Workspace
![EM Copilot Landing Page - Signed In](./02-landing-signed-in.png)
*Once signed in via Google OAuth, the left sidebar expands to reveal model provider selection (OpenAI / Anthropic dropdown) and the main BRD document uploader.*

---

### 03 - Document Upload & Validation
![File selected and ready to run](./03-file-uploaded-ready.png)
*Uploading a valid document (such as `Secure Payment Application.pdf`) stages the file, validates its format and size, and enables the primary **Generate Engineering Plan** trigger.*

---

### 04 - Pipeline execution: Specialists Drafting
![Pipeline execution: Specialists Drafting](./04-pipeline-run-in-progress.png)
*During initial execution, the multi-agent system runs concurrent Specialists Drafting. The UI timeline stepper blinks blue on the active stage and displays the progress status of each specialist agent in real time.*

---

### 05 - Pipeline execution: Specialists Alignment
![Pass 2 alignment in progress](./05-pipeline-pass2-aligning.png)
*During subsequent alignment execution, if custom EM directives are found during arbitration, the Orchestrator runs Specialists Alignment in parallel. The UI timeline stepper blinks blue on the active stage and displays the directives being aligned.*

---

### 06 - Execution Complete (Decision Notification)
![Execution complete awaiting decision](./06-pipeline-complete-awaiting-decision.png)
*When all agents and Critic assessments finish, a slim Action Required banner alerts the EM that action is required. The timeline stepper lights up green through all stages, displaying final execution statistics: 193 seconds processing time, a Critic score of **4.55 / 5.0**, and exact input/output token counts.*

---

### 07 - Scroll-to-Decision Gate Panel
![Decision gate controls](./07-decision-gate-active.png)
*Clicking the banner scrolls the EM directly to the Decision Gate panel. The reviewer's role is prefilled, and the EM can assign a numeric rating (1-5), insert review notes, and submit final approval or rejection.*

---

### 08 - Output Delivery: Plan Details
![Engineering plan deliverables](./09-plan-tab-deliverables.png)
*The generated **Plan** tab outlines the project duration, calculated confidence percentage, full cross-functional team composition count, and sprint-by-sprint phases/milestones.*

---

### 09 - Output Delivery: Architecture Blueprint SVG
![Architecture tab rendered SVG](./08-architecture-blueprint-svg.png)
*Under the **Architecture** tab, the system displays the Kroki-rendered system blueprint SVG mapping all microservices and database instances.*

---

## Observability & Telemetry

### 10 - LangSmith Node-by-Node Execution Trace
![LangSmith trace - node execution](./04-langsmith-trace-nodes.png)
*Detailed call graphs in LangSmith capture exact latencies and outputs at every node transition: `orchestrator_hub` $\rightarrow$ concurrent specialists dispatch $\rightarrow$ aggregation $\rightarrow$ Critic audit.*

---

### 11 - LangSmith Multi-Agent Tracing Workspace
![LangSmith tracing list](./05-langsmith-tracing-list.png)
*The LangSmith project board showing run tracking, execution parameters, and model payload diagnostics.*

---

### 12 - Latency & Reliability Monitoring
![LangSmith monitoring - latency and error rate](./06-langsmith-monitoring.png)
*Real-time performance metrics tracking P50/P99 latency curves and system error rates.*

---

### 13 - Financial Cost & Token Volume Dashboard
![LangSmith cost and tokens](./07-langsmith-cost-tokens.png)
*Cost tracking dashboards auditing token usage volumes and precise billing metrics.*

# ADR 0001: Frontend Architecture Transition from Streamlit to React.js

## Status
Accepted

## Context
The initial implementation of the EM Copilot user interface utilized Streamlit to achieve rapid prototyping. However, as the platform evolved to support concurrent users, idempotent Human-in-the-Loop (HITL) processes, and complex UI states, Streamlit’s execution model presented several architectural challenges:
1. **Coupled UI & Server State**: Streamlit executes server-side and re-runs the entire script on user interaction. This leads to redundant code execution, state synchronization issues, and difficulty managing asynchronous background tasks.
2. **Performance Overhead**: Frequent page refreshes and UI re-draws degrade the user experience, especially during long-running LangGraph multi-agent pipeline executions.
3. **Restricted Customization**: Complex visual indicators (timeline grids, custom scoring badge representations, and slide-to-verify panels) are difficult or impossible to style natively in Streamlit without fragile HTML/CSS hacks.

To scale the platform and support a premium, responsive user experience, a fully decoupled, client-side single-page application (SPA) architecture was proposed.

## Decision
Transition the EM Copilot frontend to a React.js single-page application built with Vite, TypeScript, and TailwindCSS. The React client communicates with the FastAPI backend over a clean, versioned REST API and Server-Sent Events (SSE) for real-time progress logging.

### Key Architectural Choices:
1. **Decoupled Client-Server**: The frontend is built as a static client-side application. The FastAPI backend serves these static assets from the `/dist` directory in production but operates strictly as a headless API service.
2. **Real-time Event Streaming**: Leverage Server-Sent Events (SSE) to push progress updates from the active LangGraph pipeline nodes directly to a retro-style terminal view on the frontend, avoiding polling.
3. **Modular Feature Directory Layout**: Structure the React codebase cleanly by dividing features, hooks, context states, and shared UI components:
   - `src/components/`: Stateless atomic UI primitives.
   - `src/features/`: Domain-specific components (Ingestion, Workspace, Critic, HITL).
   - `src/context/`: Global state containers (WorkspaceContext, AuthContext).
   - `src/hooks/`: Reusable hooks (useSSE, useLocalStorage).
4. **Resilient HTTP Client**: Use Axios with custom request interceptors and error logging.

## Consequences
- **Positive**: Complete separation of concerns between UI rendering and pipeline execution logic. Improved response times, zero unnecessary server-side UI script runs, and maximum flexibility for rich visuals.
- **Positive**: Seamless integration with the existing FastAPI backend with minimal api routing adjustments.
- **Negative**: Requires separate build packaging (Vite build) and serving of static files, increasing deployment pipeline complexity.

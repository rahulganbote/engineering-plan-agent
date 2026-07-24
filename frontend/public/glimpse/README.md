# Landing "See It in Action" glimpse carousel

`IngestionLanding.tsx` cross-fades through the screenshots below. Drop cropped
PNGs here using these exact filenames. Recommended crop: just the dark-mode
**Agentic Workflow Progress** diagram (no browser chrome, no recording toolbar),
roughly 16:9, ~1600×900.

| Filename | Pipeline state to capture |
|---|---|
| `01-upload.png` | Upload BRD panel / file ready |
| `02-orchestrator.png` | Status: EXECUTING: ORCHESTRATOR PARSING |
| `03-drafting.png` | Status: EXECUTING: DRAFTING (specialists active) |
| `04-evaluating.png` | Status: EXECUTING: EVALUATING (Critic active) |
| `05-decision.png` | Status: AWAITING YOUR DECISION (HITL gate) |
| `06-jira.png` | Jira Epic created — `[EM Copilot] Business Requirements Document` issue |

Until a file exists, that slide is skipped automatically. If none are present,
the card falls back to the ambient icon pulse — nothing breaks.

NOTE: the PNGs currently in this folder are generated on-brand **stand-ins**
(rendered workflow states), not real product captures. Overwrite any of them
with a real screenshot using the same filename to replace it — no code change
needed.

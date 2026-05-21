# Deploying EM Copilot to HuggingFace Spaces

EM Copilot is a **two-process app** — a FastAPI backend (the 7-agent pipeline)
and a Streamlit UI. HuggingFace Spaces exposes a single port, so both processes
run inside one Docker container: `start.sh` launches uvicorn in the background,
waits for its health check, then runs Streamlit in the foreground.

This guide assumes the repo is already on GitHub and clean (`.gitignore` excludes
`.venv/`, `secrets/`, `logs/`).

---

## 1. Files involved (already in the repo)

| File | Role |
|---|---|
| `Dockerfile` | Builds a `python:3.11-slim` image, installs deps, runs `start.sh` |
| `start.sh` | Launches uvicorn (port 8000, internal) + Streamlit (port 7860, public) |
| `.dockerignore` | Keeps `.venv/`, `secrets/`, `logs/`, caches out of the image |
| `requirements.txt` | Pinned dependencies |

No code changes needed — these are deployment-ready.

---

## 2. Create the Space

1. Go to https://huggingface.co/new-space
2. Fill in:
   - **Owner**: your HF username
   - **Space name**: `em-copilot` (or anything)
   - **License**: MIT (or your choice)
   - **Select the SDK**: **Docker** → **Blank** template
   - **Hardware**: **CPU basic** (free tier — sufficient; the pipeline is
     I/O-bound on OpenAI/Pinecone calls, not CPU-bound)
   - **Visibility**: Public or Private (Private still works for a demo link)
3. Click **Create Space**.

---

## 3. Add the Space README frontmatter

HuggingFace reads a YAML frontmatter block at the **very top** of the Space's
`README.md` to configure the Space. Your project `README.md` doesn't have it yet.

**Prepend this block to the top of `README.md`** (before the `# EM Copilot` line):

```yaml
---
title: EM Copilot
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: BRD to Engineering Plan multi-agent system
---
```

`app_port: 7860` tells HF to route external traffic to the Streamlit port —
it must match the `PORT` env var in the `Dockerfile` (7860).

GitHub renders this frontmatter as a small table at the top of the README — a
little cosmetic, harmless. If you'd rather keep GitHub clean, maintain the HF
Space as a separate remote and only prepend the frontmatter there.

---

## 4. Push the code to the Space

A HuggingFace Space is a git repo. Add it as a remote and push:

```bash
cd /path/to/engineering-plan-agent

# Add the Space as a git remote (replace <user> with your HF username)
git remote add hf https://huggingface.co/spaces/<user>/em-copilot

# HuggingFace asks for a username + an access token as the password.
# Create a token at https://huggingface.co/settings/tokens (role: write)

git push hf main
```

HF detects the `Dockerfile` and starts building automatically. Watch the build
logs in the Space's **Logs** tab. First build takes ~3–5 minutes (installing
deps). You'll see uvicorn start, the `✓ FastAPI backend is healthy.` line from
`start.sh`, then Streamlit boot.

---

## 5. Add secrets (env vars) to the Space

The container has **no** `secrets/.env` file — `.dockerignore` excludes it.
HuggingFace injects secrets directly as environment variables, which
`pydantic-settings` reads automatically (it falls back to `os.environ` when the
`.env` file is absent).

In the Space → **Settings** → **Variables and secrets** → add each as a **Secret**:

### Required (pipeline won't run without these)

| Secret name | Value |
|---|---|
| `OPENAI_API_KEY` | your OpenAI key |
| `PINECONE_API_KEY` | your Pinecone key |

### Strongly recommended (observability)

| Secret name | Value |
|---|---|
| `LANGCHAIN_API_KEY` | your LangSmith key |
| `LANGCHAIN_TRACING_V2` | `true` |
| `LANGCHAIN_PROJECT` | `em-copilot-brd-agent` |

### Optional integrations (each degrades gracefully if absent)

| Secret name | Effect when set | When absent |
|---|---|---|
| `GOOGLE_SHEET_ID` | Sheets export target | Falls back to local CSV bundle |
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` | Jira push on approve | Silently skipped |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID` | Voice HITL widget | Widget hidden; button HITL still works |

**Use the "Secret" type, not "Variable"** — secrets are encrypted and not shown
in build logs. Anything non-sensitive (like `LANGCHAIN_TRACING_V2=true`) can be a
plain Variable.

After adding/changing secrets, the Space **restarts automatically**.

### Google Service Account caveat

Sheets export needs a JSON key *file* at `secrets/google_service_account.json`,
not an env var. On HF Spaces you have two choices:

- **Simplest (recommended for the demo):** don't configure Sheets on HF. The
  pipeline's local-CSV fallback handles it — approvals still complete, artifacts
  still export (to the container's `logs/exports/`, viewable via the UI).
- **Full Sheets on HF (built in):** `start.sh` decodes a base64-encoded key on
  boot — no code changes needed. Encode your JSON key (macOS `base64 -i` emits a
  single line):

  ```bash
  base64 -i secrets/google_service_account.json
  ```

  Add the output as a Space **Secret** named `GOOGLE_SA_B64`, and also add
  `GOOGLE_SHEET_ID`. On startup `start.sh` writes the key back to
  `secrets/google_service_account.json` before the API launches. A missing or
  malformed `GOOGLE_SA_B64` is non-fatal — the pipeline falls back to local CSV.

---

## 6. Knowledge base — one-time Pinecone population

The Space's container does **not** run `scripts/ingest_kb.py` automatically.
Pinecone is a hosted service, so the knowledge base persists independently of
the Space. Populate it **once from your local machine** (or any machine with the
same `PINECONE_API_KEY`):

```bash
# Locally, with secrets/.env configured:
python scripts/ingest_kb.py
# ~67 chunks ingested; 4 retrieval tests pass
```

Once ingested, every deployment — local or HF — queries the same Pinecone index.
You only re-run this if you change the `knowledge_base/` files.

---

## 7. Verify the deployment

When the build finishes, the Space shows the Streamlit UI in an embedded frame.

1. The header should show **"API connected · v1.1.0"** (green) — proves
   `start.sh` brought up both processes and Streamlit reached the API.
2. Upload `eval/FoodHub_BRD.docx` (it's in the repo) → **Generate Engineering Plan**.
3. Watch the progress chips → Critic badge → HITL gate.
4. Approve → Sheets/CSV + (if configured) Jira banners appear.

If the header shows **"API offline"**, check the Space **Logs** tab:
- `start.sh` should print `✓ FastAPI backend is healthy.` — if it doesn't,
  uvicorn failed to boot (usually a missing required secret like `OPENAI_API_KEY`).

---

## 8. The voice-HITL caveat on HF

The ElevenLabs **widget** renders fine on HF (it's a client-side web component).
But the voice agent's webhook needs to call back to your `/approve/{run_id}`
endpoint. On HF that endpoint is internal-only (port 8000, not exposed).

Two options:
- **Demo voice locally** with ngrok, and use
  HF only for the button-driven HITL flow.
- **Expose the API on HF**: change `app_port` to 8000 and add an Nginx reverse
  proxy — significant extra work, not worth it for a capstone demo.

Recommended: HF Space demonstrates the full pipeline + button HITL; record the
voice-HITL beat from your local ngrok setup.

---

## 9. Common build failures

| Symptom in Logs tab | Cause | Fix |
|---|---|---|
| `permission denied: ./start.sh` | `start.sh` lost its executable bit | `git update-index --chmod=+x start.sh && git commit && git push hf main` |
| `ModuleNotFoundError` | A dep missing from `requirements.txt` | Add it, commit, push |
| Build OK but "API offline" | Required secret missing | Add `OPENAI_API_KEY` + `PINECONE_API_KEY` in Settings |
| `Address already in use :7860` | Rare HF restart race | Restart the Space from Settings |
| Container builds then exits immediately | `start.sh` aborted — API died on startup | Logs show the uvicorn traceback; usually a bad/missing key |
| Slow first request | Cold start + Pinecone index warmup | Normal — first run ~60s, subsequent runs faster |

---

## 10. Updating a deployed Space

Every `git push hf main` triggers a rebuild. To redeploy after code changes:

```bash
git add -A
git commit -m "Update"
git push hf main          # HF rebuilds automatically
```

To restart without a code change (e.g., after adding a secret), use the Space's
**Settings → Factory reboot** button.

---

## Quick reference — the whole flow

```bash
# One-time
huggingface.co/new-space  → Docker SDK → CPU basic
prepend YAML frontmatter to README.md
git remote add hf https://huggingface.co/spaces/rganbote/em-copilot
python scripts/ingest_kb.py          # populate Pinecone once

# Deploy
git push hf main

# Configure (in Space Settings → Variables and secrets)
OPENAI_API_KEY, PINECONE_API_KEY        (required)
LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT   (recommended)
JIRA_*, GOOGLE_SHEET_ID, ELEVENLABS_*   (optional)

# Verify
Open the Space → header shows "API connected" → upload a BRD → run
```

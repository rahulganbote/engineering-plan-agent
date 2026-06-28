# EM Copilot - Timeouts, Budgets & TTLs Reference

> Single source of truth for every timeout, retry budget, circuit-breaker
> threshold, and cache TTL in the system. If a value changes in code, update
> the corresponding row here so the table stays in sync.

**Last reconciled:** 2026-06-09

---

## 1. Pipeline-level

| Variable | Value | Source | Purpose |
|---|---|---|---|
| `settings.pipeline_timeout_sec` | **300 s** (5 min) | `src/core/config.py:84` | Overall pipeline SLA target. **Observational, not enforced** - logger flags runs that exceed it as "⚠️ SLA breach" but no `signal.alarm` cancels the run. |
| `settings.agent_timeout_sec` | **90 s** | `src/core/config.py:85` | Per-agent bulkhead budget (Phase 9). Hard cap enforced by `as_completed(timeout=...)` in the dispatcher. |
| `_bulkhead_budget` | reads `agent_timeout_sec` | `src/agents/pipeline.py:148` | Actual `as_completed` value at dispatch. |

---

## 2. Per-call resilience policies (`@resilient`)

Sensible-default `CallPolicy` instances. Each agent reads its policy via the
class-level `RESILIENCE_POLICY` attribute (Phase 5 manifest pattern).

| Policy | timeout_sec | max_attempts | backoff (min → max) | Jitter | Source |
|---|---|---|---|---|---|
| `OPENAI_POLICY` | **30.0** | 3 | 1.0 → 8.0 | ±50% | `resilience.py:66` |
| `PINECONE_POLICY` | **10.0** | 2 | 0.5 → 2.0 | ±50% | `resilience.py:67` |
| `EMBEDDING_POLICY` | **15.0** | 3 | 0.5 → 4.0 | ±50% | `resilience.py:68` |
| `HTTP_POLICY` | **10.0** | 2 | 0.5 → 2.0 | ±50% | `resilience.py:69` |
| `CallPolicy()` field defaults | 30.0 | 3 | 1.0 → 8.0 | True | `resilience.py:56` |

**Worst-case per call** (all retries fire): `timeout_sec × max_attempts + Σ backoff`.

- OpenAI: 30 × 3 + (1 + 2 + 4) ≈ **97 s**
- Embedding: 15 × 3 + (0.5 + 1 + 2) ≈ **48.5 s**
- Pinecone: 10 × 2 + 0.5 ≈ **20.5 s**

---

## 3. Circuit breakers (per-instance, per-service)

Each agent class and each external service owns its own breaker - no shared state.

| Breaker | fail_threshold | reset_sec | Source |
|---|---|---|---|
| LLM per agent class (`_LLM_BREAKERS["AgentClassName"]`) | 5 | 30.0 | `base_agent.py:124-125` |
| `_RAG_BREAKER` (Pinecone retrieve) | 4 | 20.0 | `rag.py:107` |
| `_EMBED_BREAKER` (embeddings) | 5 | 30.0 | `rag.py:108` |

When OPEN, subsequent calls raise `CircuitOpenError` immediately (no timeout
elapsed). The next call after `reset_sec` transitions OPEN → HALF_OPEN and
allows one probe; success closes the breaker, failure re-opens.

---

## 4. Cache TTLs

| Policy | ttl_sec | Namespace | Source |
|---|---|---|---|
| `CACHE_LLM` | **3,600 s** (1 h) | `llm` | `cache.py:65` |
| `CACHE_RAG` | **1,800 s** (30 min) | `rag` | `cache.py:66` |
| `CACHE_EMBEDDING` | **86,400 s** (24 h) | `embed` | `cache.py:67` |
| `CachePolicy()` field defaults | 3,600 s | `default` | `cache.py:58` |
| `RedisCache.socket_timeout` | **1.0 s** (connect + read) | - | `cache.py:310` |
| `RedisCache.healthcheck` | uses `socket_timeout` | - | `cache.py:565` (via `init_default_backend_from_env`) |
| `TieredCache` L1 backfill TTL | **3,600 s** (1 h, hardcoded) | inherits L2's namespace | `cache.py:401` |

> `RedisCache.socket_timeout = 1.0 s` is intentionally tight. If Redis L2 is
> more than 1 second away (network glitch, instance overloaded), the cache
> degrades to L1 only - Redis was never supposed to be on the critical path.

---

## 5. External integrations

| Variable | Value | Source | Purpose |
|---|---|---|---|
| `KROKI_TIMEOUT_SEC` | **15 s** | `architect.py:48` | Per-attempt Kroki SVG render. **Bumped from 8 s on 2026-06-09 after repeated timeouts.** Worst case 15 × 2 = 30 s. |
| `KROKI_MAX_RETRIES` | **2** | `architect.py:49` | |
| `MCP_TIMEOUT_SEC` | **45 s** | `jira_mcp.py:77` | mcp-atlassian stdio call (Jira Epic create + read-back). Wider because MCP handshake + tool list + call is multi-step. |
| Kroki preview probe in jira_mcp | **8 s** | `jira_mcp.py:448` | Separate `requests.get(...)` to validate the Kroki SVG URL we paste into the Jira description. |
| `JIRA_TIMEOUT_SEC` | **10 s** | `jira.py:50` | Jira REST fallback (when MCP unavailable). |
| `_SLACK_TIMEOUT_SEC` | **10 s** | `slack.py:33` | Slack incoming-webhook alert (only fires on pipeline error). |
| `google_auth.py` token exchange | **10 s** | `google_auth.py:122` | OAuth `POST /token` to Google. |
| `google_auth.py` userinfo | **10 s** | `google_auth.py:135` | `GET /userinfo` after token exchange. |
| `gspread` Sheets write | (library default ~60 s) | `sheets.py` | Not explicitly capped - gspread uses its own internal timeouts. |

---

## 6. UI / API layer

| Variable | Value | Source | Purpose |
|---|---|---|---|
| Streamlit `components.html(height=)` for Mermaid iframe | 520 px | `streamlit_app.py:680` | Visual sizing only - not a timeout, but the iframe stays open for that height. |
| FastAPI SSE keep-alive interval | (Starlette default) | `src/api/main.py` | Heartbeat to keep Streamlit's SSE connection open during long runs. |

---

## 7. How they compose

The bulkhead at 90 s is the hard cap a single specialist can spend. Inside
it, multiple per-call timeouts and retries compete for the budget.

```
Pipeline run
└── settings.pipeline_timeout_sec = 300 s   (observational only)
    └── Bulkhead per specialist: settings.agent_timeout_sec = 90 s
        └── Inside each specialist (worst case if everything retries):
            ├── 1× Embedding query   ≈ 48 s    (EMBEDDING_POLICY × 3)
            ├── 1× Pinecone retrieve ≈ 21 s    (PINECONE_POLICY × 2)
            ├── 1× LLM specialist    ≈ 97 s    (OPENAI_POLICY × 3)   ← exceeds budget!
            └── (Architect only) Kroki ≈ 30 s  (KROKI_TIMEOUT × 2)

        Critic at the end:
        └── 1× LLM judge call        ≈ 97 s    (OPENAI_POLICY × 3)

On HITL approval:
├── Sheets write     (gspread internal timeout)
├── Jira MCP          ≤ 45 s         (MCP_TIMEOUT_SEC)
├── Jira REST fallback ≤ 10 s        (JIRA_TIMEOUT_SEC)
└── Slack alert       ≤ 10 s         (on failure only)
```

### Notable interactions

1. **OpenAI worst-case (~97 s) exceeds the bulkhead (90 s).** In practice
   retries rarely fire - if you start seeing repeated `bulkhead_timeout` events
   correlated with `retry` events on OPENAI_POLICY, either OpenAI is degraded
   or you should bump `agent_timeout_sec` higher (or cut `max_attempts` to 2).

2. **Kroki + LLM in the Architect specialist.** A worst-case Architect run is
   `LLM (97s) + Kroki (30s) = 127s` - would trip the bulkhead. In practice the
   LLM completes in ~15-25 s and Kroki in ~1-2 s, so the typical run is well
   under 30 s.

3. **Cache hits skip all of the above.** `@cached` runs OUTSIDE `@resilient`,
   so a hit pays zero retry / timeout / breaker cost. The Critic revision loop
   benefits most: revision-2 prompts are highly similar to revision-1, so the
   semantic cache catches them.

4. **`pipeline_timeout_sec = 300` is not enforced.** It's only used in the
   logger for `✅ within SLA` vs `⚠️ SLA breach` messages. The actual upper
   bound on a single run is the sum of all bulkheads. Worst case:
   `5 specialists × 90 s + Critic × 90 s = 540 s` - beyond the SLA target.
   If you want a hard pipeline-level cancel, wrap `run_pipeline()` in your
   own `concurrent.futures` timeout.

---

## 8. Tuning recipes

| Symptom | Knob to turn |
|---|---|
| OpenAI returning lots of 429/503 | Bump `OPENAI_POLICY.max_attempts` from 3 → 4, OR widen `backoff_max` |
| Bulkhead trips frequently with `retry` events | Bump `settings.agent_timeout_sec` from 90 → 120 |
| Pinecone slow in a new region | Bump `PINECONE_POLICY.timeout_sec` from 10 → 20 |
| Kroki rendering still failing | Bump `KROKI_TIMEOUT_SEC` from 15 → 30, OR self-host the kroki container as a sidecar |
| Redis L2 cache constantly degrading to L1 | Bump `RedisCache.socket_timeout` from 1.0 → 2.0 - but if Redis is that slow, fix the network instead |
| Cache hits never happen for same-BRD reruns | Check `CACHE_LLM.ttl_sec` (default 1 h) - was the rerun > 1 h after the first run? |
| Embedding cache too aggressive (stale vectors after model swap) | Drop `CACHE_EMBEDDING.ttl_sec` from 24 h → 1 h, OR change the cache key to include the model version |

---

## 9. Change log

| Date | Change |
|---|---|
| 2026-06-09 | `KROKI_TIMEOUT_SEC` bumped 8 → 15 s after repeated `ReadTimeout` failures. |
| 2026-06-07 | Phase 9 introduced `settings.agent_timeout_sec` (90 s) and the bulkhead pattern in `node_dispatch_specialists`. |
| 2026-06-07 | Phase 8 introduced `RedisCache.socket_timeout = 1.0 s` for L2 cache degradation. |
| 2026-06-07 | Phase 1 introduced all `CallPolicy` defaults and per-instance breakers. |

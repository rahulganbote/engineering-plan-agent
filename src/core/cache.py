"""
src/core/cache.py
═════════════════════════════════════════════════════════════════════════════
Pluggable cache abstraction for any external service call. Composes with
`src/core/resilience.py` — a cache HIT skips the resilience layer entirely
(zero retry/timeout/breaker cost).

Modes
─────
    "off"      — no-op (use to disable per call site without removing the decorator)
    "exact"    — SHA-256 of the call args; hit only on byte-identical inputs
    "semantic" — embed + nearest-neighbour search (reserved for Phase 6;
                 falls back to "exact" until Phase 6 ships the Pinecone-backed
                 SemanticBackend)

Backends
────────
    InMemoryCache  — default, thread-safe LRU + TTL, zero infra
    RedisCache     — reserved for Phase 8; activates automatically when REDIS_URL
                     is set (Protocol is defined; implementation TBD)

Design
──────
Per-caller policies, no shared mutation. The module exposes ONE process-default
backend (lazy InMemoryCache), but each `@cached(...)` site may pass its own
backend instance — that's the extensibility hook for Redis or a custom store.

Usage
─────
    @cached(policy=CACHE_LLM, backend=None)   # uses process default
    @resilient(policy=OPENAI_POLICY)
    def call_llm(system, user): ...
"""

from __future__ import annotations

import functools
import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from src.core.events import emit as _emit
from src.core.logger import get_logger

log = get_logger(__name__)

try:
    import redis
except ImportError:
    redis = None


# ── Policy ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CachePolicy:
    """Frozen per-call-site policy. Callers may construct their own."""

    mode: Literal["off", "exact", "semantic"] = "exact"
    ttl_sec: int = 3600
    namespace: str = "default"
    semantic_threshold: float = 0.93  # reserved for Phase 6
    max_entries: int = 4096  # InMemory only


# Sensible defaults per call site
CACHE_LLM = CachePolicy(mode="exact", ttl_sec=3600, namespace="llm")
CACHE_RAG = CachePolicy(mode="exact", ttl_sec=28800, namespace="rag")
CACHE_EMBEDDING = CachePolicy(mode="exact", ttl_sec=86400, namespace="embed")


# ── Backend protocol ─────────────────────────────────────────────────────────


class CacheBackend(Protocol):
    def get(self, key: str, namespace: str) -> Any | None: ...
    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: int = 3600,
        namespace: str = "default",
        *,
        ttl: int | None = None,
    ) -> None: ...
    def clear(self, namespace: str = "") -> None: ...
    def stats(self) -> dict: ...


# ── In-memory backend (LRU + TTL) ────────────────────────────────────────────


class InMemoryCache:
    """
    Thread-safe LRU + TTL cache. Default backend.

    Behaviour:
      • Bounded by max_entries (FIFO eviction by insertion order; reinsertion
        on access moves the entry to the end — LRU semantics).
      • Each entry carries its own absolute expiry; lazy expiry on get().
    """

    def __init__(self, max_entries: int = 4096):
        self._max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()  # key → (expires_at, value)
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @staticmethod
    def _nskey(key: str, namespace: str) -> str:
        return f"{namespace}::{key}"

    def get(self, key: str, namespace: str) -> Any | None:
        nskey = self._nskey(key, namespace)
        with self._lock:
            entry = self._store.get(nskey)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._store[nskey]
                self._misses += 1
                return None
            # LRU touch
            self._store.move_to_end(nskey)
            self._hits += 1
            return value

    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: int = 3600,
        namespace: str = "default",
        *,
        ttl: int | None = None,
    ) -> None:
        if ttl is not None:
            ttl_sec = ttl
        nskey = self._nskey(key, namespace)
        with self._lock:
            if nskey in self._store:
                del self._store[nskey]
            self._store[nskey] = (time.time() + ttl_sec, value)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
                self._evictions += 1

    def clear(self, namespace: str = "") -> None:
        with self._lock:
            if not namespace:
                self._store.clear()
            else:
                prefix = f"{namespace}::"
                for k in [k for k in self._store if k.startswith(prefix)]:
                    del self._store[k]

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "backend": "memory",
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }


# ── Process-default backend (lazy, swappable) ────────────────────────────────

_default_backend: CacheBackend | None = None
_default_lock = threading.Lock()

# Phase 6: registry of SemanticBackend instances keyed by namespace
_SEMANTIC_BACKENDS: dict[str, SemanticBackend] = {}


def get_semantic_backend(namespace: str) -> SemanticBackend | None:
    """Return the SemanticBackend for the given namespace, or None."""
    return _SEMANTIC_BACKENDS.get(namespace)


def get_default_backend() -> CacheBackend:
    """Get or lazy-create the process-default cache backend."""
    global _default_backend
    with _default_lock:
        if _default_backend is None:
            _default_backend = InMemoryCache(max_entries=4096)
        return _default_backend


def reset_default_backend(backend: CacheBackend | None = None) -> None:
    """Override the process-default backend (for tests, or Phase 8 Redis swap)."""
    global _default_backend
    with _default_lock:
        _default_backend = backend


def cache_stats() -> dict:
    """Get aggregate hit/miss stats from the default backend (for /health or UI)."""
    return get_default_backend().stats()


# ── Key derivation ───────────────────────────────────────────────────────────


def hash_args(*args, **kwargs) -> str:
    """
    Stable SHA-256 of positional + keyword args. Caller may pass a custom
    key_fn to the @cached() decorator if it needs to exclude unhashable parts
    (e.g. `self` or callbacks).
    """
    try:
        payload = json.dumps([args, kwargs], sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        payload = repr((args, kwargs))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


# ── Decorator ────────────────────────────────────────────────────────────────


def cached(
    policy: CachePolicy = CachePolicy(),
    key_fn: Callable[..., str] | None = None,
    backend: CacheBackend | None = None,
    name: str = "",
):
    """
    Wrap a callable with caching. Cache hits skip the wrapped function entirely.

    Composes BEFORE @resilient — a hit pays zero retry / timeout / breaker cost.
    """

    def decorator(fn: Callable) -> Callable:
        call_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if policy.mode == "off":
                return fn(*args, **kwargs)

            be = backend or get_default_backend()
            key = key_fn(*args, **kwargs) if key_fn else hash_args(*args, **kwargs)

            # ── Semantic mode (Phase 6) ─────────────────────────────────────
            # Route to SemanticBackend.semantic_get/set when:
            #   1. policy.mode == "semantic"
            #   2. the backend exposes semantic_get (i.e. is a SemanticBackend)
            # Falls back to exact cache if the backend doesn't support semantic.
            if policy.mode == "semantic" and getattr(be, "semantic_get", None) is not None:
                # Derive a human-readable query text from the first string arg
                query_text = None
                for a in args:
                    if isinstance(a, str) and len(a) > 10:
                        query_text = a[:2000]
                        break
                if query_text:
                    hit = be.semantic_get(
                        query_text,
                        namespace=policy.namespace,
                        threshold=policy.semantic_threshold,
                    )
                    if hit is not None:
                        log.debug(f"[cache:{policy.namespace}] SEMANTIC HIT {call_name}")
                        _emit("cache_hit", namespace=policy.namespace, call=call_name, mode="semantic", key=key[:8])
                        return hit
                    log.debug(f"[cache:{policy.namespace}] SEMANTIC MISS {call_name}")
                    _emit("cache_miss", namespace=policy.namespace, call=call_name, key=key[:8])
                    result = fn(*args, **kwargs)
                    try:
                        be.semantic_set(query_text, result, namespace=policy.namespace)
                    except Exception as e:
                        log.warning(f"[cache:{policy.namespace}] semantic_set failed: {e}")
                    return result
                # No usable string arg found — fall through to exact cache

            # ── Exact mode (and semantic fallback) ──────────────────────────
            hit = be.get(key, policy.namespace)
            if hit is not None:
                log.debug(f"[cache:{policy.namespace}] HIT  {call_name} key={key[:8]}…")
                _emit("cache_hit", namespace=policy.namespace, call=call_name, mode=policy.mode, key=key[:8])
                return hit

            # ── Miss — call the wrapped function ────────────────────────────
            log.debug(f"[cache:{policy.namespace}] MISS {call_name} key={key[:8]}…")
            _emit("cache_miss", namespace=policy.namespace, call=call_name, key=key[:8])
            result = fn(*args, **kwargs)

            # ── Store on the way back ───────────────────────────────────────
            try:
                be.set(key, result, policy.ttl_sec, policy.namespace)
            except Exception as e:
                log.warning(f"[cache:{policy.namespace}] set failed: {e}")

            return result

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8 — Production-grade backends (Redis + Tiered)
# ═══════════════════════════════════════════════════════════════════════════

import gzip as _gzip
import os as _os
import pickle as _pickle


class RedisCache:
    """
    Redis-backed L2 cache. Activates when REDIS_URL env var is set.

    Serialisation: pickle + gzip (LLM responses are large strings, RAG results
    are Pydantic objects — pickle round-trips them faithfully, gzip cuts wire
    size ~70%). For multi-tenant shared Redis you'd swap to JSON; here both
    ends are trusted code so pickle is safe and convenient.

    Failure handling: any RedisError or connection problem is logged and the
    operation returns None / silently skips. The TieredCache wrapper then
    degrades to L1-only — the system keeps working.
    """

    def __init__(self, url: str, key_prefix: str = "em-copilot", socket_timeout: float = 1.0):
        try:
            import redis  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "RedisCache requires the `redis` package. Add `redis>=5.0` to requirements.txt and reinstall."
            ) from e
        self._redis = redis.from_url(
            url,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_timeout,
            decode_responses=False,
        )
        self._prefix = key_prefix
        self._hits = 0
        self._misses = 0
        self._errors = 0

    def _full_key(self, key: str, namespace: str) -> str:
        return f"{self._prefix}:{namespace}:{key}"

    def get(self, key: str, namespace: str) -> Any | None:
        try:
            raw = self._redis.get(self._full_key(key, namespace))
            if raw is None:
                self._misses += 1
                return None
            value = _pickle.loads(_gzip.decompress(raw))
            self._hits += 1
            return value
        except Exception as e:
            self._errors += 1
            if redis and isinstance(e, redis.RedisError):
                log.warning(f"[cache:redis] get failed ({type(e).__name__}); degrading")
            else:
                log.exception("[cache:redis] unexpected logic/serialization error in get")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: int = 3600,
        namespace: str = "default",
        *,
        ttl: int | None = None,
    ) -> None:
        if ttl is not None:
            ttl_sec = ttl
        try:
            payload = _gzip.compress(_pickle.dumps(value), compresslevel=3)
            self._redis.set(self._full_key(key, namespace), payload, ex=max(1, ttl_sec))
        except Exception as e:
            self._errors += 1
            if redis and isinstance(e, redis.RedisError):
                log.warning(f"[cache:redis] set failed ({type(e).__name__}); skipping")
            else:
                log.exception("[cache:redis] unexpected logic/serialization error in set")

    def clear(self, namespace: str = "") -> None:
        try:
            pattern = f"{self._prefix}:{namespace}:*" if namespace else f"{self._prefix}:*"
            for k in self._redis.scan_iter(pattern):
                self._redis.delete(k)
        except Exception as e:
            if redis and isinstance(e, redis.RedisError):
                log.warning(f"[cache:redis] clear failed ({type(e).__name__})")
            else:
                log.exception("[cache:redis] unexpected logic error in clear")

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }


class TieredCache:
    """
    Two-tier read-through / write-through cache.
        L1 (InMemoryCache)  — in-process, sub-millisecond, per-replica
        L2 (RedisCache)     — shared across replicas, ~1–10 ms

    GET:
        1. L1 hit  → return immediately.
        2. L1 miss → check L2.  L2 hit → backfill L1 → return.
        3. L2 miss → return None (caller computes + sets).

    SET: write to BOTH layers (write-through). L2 failure is logged but doesn't
    block the write to L1 — local cache always works even if Redis is down.
    """

    def __init__(self, l1: CacheBackend, l2: CacheBackend):
        self._l1 = l1
        self._l2 = l2

    def get(self, key: str, namespace: str) -> Any | None:
        v = self._l1.get(key, namespace)
        if v is not None:
            return v
        v = self._l2.get(key, namespace)
        if v is not None:
            # Backfill L1 with a default TTL — keeps the hot path local
            try:
                self._l1.set(key, v, 3600, namespace)
            except Exception:
                pass
        return v

    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: int = 3600,
        namespace: str = "default",
        *,
        ttl: int | None = None,
    ) -> None:
        if ttl is not None:
            ttl_sec = ttl
        try:
            self._l1.set(key, value, ttl_sec, namespace)
        except Exception as e:
            log.warning(f"[cache:tier] L1 set failed: {e}")
        try:
            self._l2.set(key, value, ttl_sec, namespace)
        except Exception as e:
            log.warning(f"[cache:tier] L2 set failed: {e}")

    def clear(self, namespace: str = "") -> None:
        try:
            self._l1.clear(namespace)
        except Exception:
            pass
        try:
            self._l2.clear(namespace)
        except Exception:
            pass

    def stats(self) -> dict:
        return {"backend": "tiered", "l1": self._l1.stats(), "l2": self._l2.stats()}


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6 — Semantic cache via Pinecone
# ═══════════════════════════════════════════════════════════════════════════


class SemanticBackend:
    """
    Pinecone-backed semantic cache. Uses cosine similarity on query embeddings
    to find "near-enough" cached LLM responses, avoiding redundant LLM calls
    for semantically equivalent queries even when the text differs slightly.

    Uses a separate namespace ("llm-cache" by default) within the existing
    Pinecone index so it does not collide with the RAG corpus.

    Protocol shape: exposes get/set/clear/stats (CacheBackend Protocol) plus
    semantic_get / semantic_set so @cached can detect and route to them.

    NOTE: On free-tier Pinecone this WILL create vectors in the index.
    Check your free-tier quota before enabling (typically 100k vectors on Starter).
    A warning is logged at construction time.
    """

    def __init__(
        self,
        embed_fn,
        pinecone_index,
        namespace: str = "llm-cache",
        threshold: float = 0.95,
    ):
        self._embed_fn = embed_fn
        self._index = pinecone_index
        self._namespace = namespace
        self._threshold = threshold
        self._hits = 0
        self._misses = 0
        log.warning(
            f"[cache:semantic] SemanticBackend initialised | "
            f"namespace={namespace} threshold={threshold} | "
            "NOTE: will write vectors to Pinecone — check free-tier quota."
        )

    # ── CacheBackend Protocol stubs (unused; semantic path takes priority) ───

    def get(self, key: str, namespace: str) -> Any | None:
        """Stub — @cached routes semantic-mode calls to semantic_get instead."""
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: int = 3600,
        namespace: str = "default",
        *,
        ttl: int | None = None,
    ) -> None:
        """Stub — @cached routes semantic-mode calls to semantic_set instead."""
        pass

    def clear(self, namespace: str = "") -> None:
        pass  # Pinecone namespace deletion is not trivially safe on free tier

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "semantic_pinecone",
            "namespace": self._namespace,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }

    # ── Semantic interface ───────────────────────────────────────────────────

    def semantic_get(self, query_text: str, namespace: str, threshold: float) -> Any | None:
        """
        Embed query_text and search Pinecone for a cached response above threshold.
        Returns the cached value if found, else None.
        """
        ns = namespace or self._namespace
        th = threshold if threshold is not None else self._threshold
        try:
            vec = self._embed_fn([query_text])[0]
            results = self._index.query(
                vector=vec,
                top_k=1,
                namespace=ns,
                include_metadata=True,
            )
            if results.matches and results.matches[0].score >= th:
                match = results.matches[0]
                cached_value = match.metadata.get("cached_value")
                if cached_value is not None:
                    import json as _json

                    try:
                        value = _json.loads(cached_value)
                    except Exception:
                        value = cached_value
                    log.debug(f"[cache:semantic] HIT ns={ns} score={match.score:.3f}")
                    self._hits += 1
                    return value
            self._misses += 1
            return None
        except Exception as e:
            log.warning(f"[cache:semantic] semantic_get error: {e}")
            self._misses += 1
            return None

    def semantic_set(self, query_text: str, value: Any, namespace: str) -> None:
        """
        Embed query_text and upsert the cached value into Pinecone.
        The value is JSON-serialised and stored in metadata.
        """
        ns = namespace or self._namespace
        try:
            import hashlib as _hashlib
            import json as _json

            vec = self._embed_fn([query_text])[0]
            vec_id = "sem-cache-" + _hashlib.sha256(query_text.encode()).hexdigest()[:24]
            try:
                cached_value = _json.dumps(value)
            except Exception:
                cached_value = str(value)
            # Pinecone metadata values must be strings / numbers / bools
            # Truncate if needed (metadata limit is ~40KB per vector)
            if len(cached_value) > 38000:
                log.warning("[cache:semantic] value too large for metadata; skipping set")
                return
            self._index.upsert(
                vectors=[
                    {
                        "id": vec_id,
                        "values": vec,
                        "metadata": {"cached_value": cached_value, "query": query_text[:500]},
                    }
                ],
                namespace=ns,
            )
            log.debug(f"[cache:semantic] SET ns={ns} id={vec_id[:16]}…")
        except Exception as e:
            log.warning(f"[cache:semantic] semantic_set error: {e}")


def init_default_backend_from_env() -> None:
    """
    Wire the process-default backend from env vars at startup.
        REDIS_URL set            → TieredCache(InMemoryCache, RedisCache)
        REDIS_URL unset          → InMemoryCache only
        EM_SEMANTIC_CACHE=1      → also attaches SemanticBackend (Phase 6)

    Call this once at FastAPI startup. Idempotent.
    """
    url = (_os.environ.get("REDIS_URL") or "").strip()
    if not url:
        log.info("[cache] using InMemoryCache (no REDIS_URL)")
        reset_default_backend(InMemoryCache(max_entries=4096))
    else:
        try:
            l1 = InMemoryCache(max_entries=4096)
            l2 = RedisCache(url=url)
            try:
                l2.set("__healthcheck__", "ok", 60, "_cache")
            except Exception as e:
                if redis and isinstance(e, redis.RedisError):
                    log.warning(f"[cache] Redis healthcheck failed ({type(e).__name__}); using L1 only")
                else:
                    log.exception("[cache] Redis healthcheck failed with unexpected error")
                reset_default_backend(l1)
                return
            log.info(f"[cache] using TieredCache (L1=InMemory, L2=Redis @ {url.split('@')[-1]})")
            reset_default_backend(TieredCache(l1=l1, l2=l2))
        except Exception as e:
            log.warning(f"[cache] Redis init failed ({type(e).__name__}); using InMemoryCache")
            reset_default_backend(InMemoryCache(max_entries=4096))

    # Phase 6: attach SemanticBackend when EM_SEMANTIC_CACHE=1
    if (_os.environ.get("EM_SEMANTIC_CACHE") or "").strip() == "1":
        try:
            from src.core.rag import _embed, _get_index

            sem = SemanticBackend(
                embed_fn=_embed,
                pinecone_index=_get_index(),
                namespace="llm-cache",
            )
            # Store on a module-level so agents can retrieve it by namespace
            _SEMANTIC_BACKENDS["llm-cache"] = sem
            log.info("[cache] SemanticBackend attached (namespace=llm-cache)")
        except Exception as e:
            log.warning(f"[cache] SemanticBackend init failed ({type(e).__name__}); semantic cache disabled")

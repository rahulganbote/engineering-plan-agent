"""
src/api/state.py
════════════════
Run storage and telemetry push helper.

State is backed by Upstash Redis when REDIS_URL is configured, allowing
horizontal scaling of the FastAPI process on Cloud Run. When REDIS_URL is
unset or unreachable, gracefully falls back to per-process in-memory storage
(single-instance mode — safe for local dev and portfolio-scale traffic).

Design notes
────────────
• One shared Redis client at module import (all proxies reuse it) so we don't
  multiply Upstash connection pressure by the number of proxies.
• Every write sets a TTL — Redis is persistent, and abandoned runs would
  otherwise accumulate forever. Event list writes additionally LTRIM to bound
  per-run size.
• _run_export uses Redis HASH (HSET/HGET) rather than get-modify-set on a JSON
  blob, so concurrent field updates from different Cloud Run instances don't
  clobber each other.
"""

from __future__ import annotations

import json
import os
import time

import redis

from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)

REDIS_URL = (os.environ.get("REDIS_URL") or "").strip()

# ── TTL policy ─────────────────────────────────────────────────────────────────
# 24h is generous — long enough that a paused HITL decision doesn't lose state,
# short enough that abandoned runs don't inflate storage.
_RUN_TTL_SECONDS = 60 * 60 * 24
# Cap per-run SSE event list to avoid pathological growth (looped pipelines,
# stuck agents, etc.). 5000 events is far above a normal run's ~150.
_MAX_EVENTS_PER_RUN = 5000


# ── Shared Redis client ────────────────────────────────────────────────────────
# One connection pool for the whole module. Every proxy reads/writes via this.
_REDIS_CLIENT: redis.Redis | None = None
if REDIS_URL:
    try:
        # Per-operation socket_timeout stays tight (1s) so a stuck Redis call
        # doesn't hang the request path. But the INITIAL connect timeout is
        # given 5s of headroom — Cloud Run cold starts + Upstash TLS handshake
        # can push the first ping past 1s under load, causing spurious
        # fallback-to-in-memory on healthy Redis instances.
        _REDIS_CLIENT = redis.from_url(
            REDIS_URL,
            socket_timeout=1.0,
            socket_connect_timeout=5.0,
        )
        _REDIS_CLIENT.ping()
        log.info("[state:redis] Connected to Upstash Redis (shared client for all state proxies)")
    except Exception as e:
        log.error(f"[state:redis] Redis unreachable, falling back to in-memory: {e}")
        _REDIS_CLIENT = None
        # Best-effort operator signal — emit an event if the bus is initialized.
        try:
            from src.core.events import emit

            emit("redis_fallback_used", reason=str(type(e).__name__), detail=str(e)[:200])
        except Exception:
            pass


class RedisDictProxy:
    """
    Dict-like view backed by Redis SET/GET (single serialized value per key).
    Falls back to a plain dict if the shared Redis client is None.
    """

    def __init__(self, key_prefix: str, serializer=None, deserializer=None, return_sub_proxy: bool = False):
        self.key_prefix = key_prefix
        self.serializer = serializer or (lambda x: json.dumps(x))
        self.deserializer = deserializer or (lambda x: json.loads(x))
        self.return_sub_proxy = return_sub_proxy
        self.redis = _REDIS_CLIENT
        self.local_dict: dict = {}

    def _full_key(self, key: str) -> str:
        return f"state:{self.key_prefix}:{key}"

    def __getitem__(self, key: str):
        if self.redis:
            full_k = self._full_key(key)
            if self.return_sub_proxy:
                # Sub-proxy is backed by a Redis HASH, checked via EXISTS on the
                # hash key. We return the proxy even if the hash is empty so
                # setters can lazily create fields.
                return RedisSubDictProxy(self, key)
            if not self.redis.exists(full_k):
                raise KeyError(key)
            raw = self.redis.get(full_k)
            return self.deserializer(raw)

        # In-memory path
        if self.return_sub_proxy:
            return LocalSubDictProxy(self.local_dict, key)
        return self.local_dict[key]

    def __setitem__(self, key: str, value):
        if self.redis:
            full_k = self._full_key(key)
            if self.return_sub_proxy:
                # This proxy stores each entry as a Redis HASH so that later
                # `_proxy[key]["field"] = v` (via RedisSubDictProxy → HSET)
                # doesn't collide with a STRING-typed key here. Delete any
                # prior key (guards against previous serializer runs) then
                # HSET all fields at once.
                self.redis.delete(full_k)
                if isinstance(value, dict) and value:
                    payload = {k: json.dumps(v) for k, v in value.items()}
                    self.redis.hset(full_k, mapping=payload)
                    self.redis.expire(full_k, _RUN_TTL_SECONDS)
            else:
                self.redis.set(full_k, self.serializer(value), ex=_RUN_TTL_SECONDS)
        else:
            self.local_dict[key] = value

    def __delitem__(self, key: str):
        if self.redis:
            full_k = self._full_key(key)
            if not self.redis.exists(full_k):
                raise KeyError(key)
            self.redis.delete(full_k)
        else:
            del self.local_dict[key]

    def __contains__(self, key: str) -> bool:
        if self.redis:
            return bool(self.redis.exists(self._full_key(key)))
        return key in self.local_dict

    def get(self, key: str, default=None):
        """
        Read a snapshot value. IMPORTANT: even when return_sub_proxy=True,
        .get() returns a plain dict (or `default`) — NOT a sub-proxy. This
        keeps the return value JSON-serializable, which matters for callers
        that inline the value into an API response.

        For mutation patterns like `proxy[key]["field"] = value`, use
        `proxy[key]` (bracket access) which returns the sub-proxy.
        """
        if self.return_sub_proxy:
            if self.redis:
                sub = RedisSubDictProxy(self, key)
                snap = sub._hgetall()
                return snap if snap else default
            snap = self.local_dict.get(key)
            if not snap:
                return default
            return dict(snap)
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: str, default=None):
        if self.redis:
            full_k = self._full_key(key)
            if self.return_sub_proxy:
                # HASH-typed key — read snapshot then delete.
                sub = RedisSubDictProxy(self, key)
                snap = sub._hgetall()
                if not snap:
                    # Also delete in case an empty HASH-key was left over.
                    self.redis.delete(full_k)
                    return default
                self.redis.delete(full_k)
                return snap
            raw = self.redis.get(full_k)
            if raw is None:
                return default
            self.redis.delete(full_k)
            return self.deserializer(raw)
        return self.local_dict.pop(key, default)


class RedisSubDictProxy:
    """
    Hash-backed sub-dictionary view. Field-level HSET/HGET so concurrent
    updates from multiple Cloud Run instances don't clobber each other.
    """

    def __init__(self, parent_proxy: RedisDictProxy, key: str):
        self._parent = parent_proxy
        self._key = key
        self._hash_key = parent_proxy._full_key(key)

    def _hgetall(self) -> dict:
        raw_map = self._parent.redis.hgetall(self._hash_key) if self._parent.redis else {}
        out: dict = {}
        for k_bytes, v_bytes in raw_map.items():
            k = k_bytes.decode("utf-8") if isinstance(k_bytes, (bytes, bytearray)) else k_bytes
            v_raw = v_bytes.decode("utf-8") if isinstance(v_bytes, (bytes, bytearray)) else v_bytes
            try:
                out[k] = json.loads(v_raw)
            except (TypeError, ValueError):
                out[k] = v_raw
        return out

    def _get_data(self) -> dict:
        """Compatibility with older callers that expected a full dict snapshot."""
        return self._hgetall()

    def __len__(self) -> int:
        return int(self._parent.redis.hlen(self._hash_key)) if self._parent.redis else 0

    def __bool__(self) -> bool:
        return len(self) > 0

    def __getitem__(self, item):
        raw = self._parent.redis.hget(self._hash_key, item)
        if raw is None:
            raise KeyError(item)
        raw_str = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            return json.loads(raw_str)
        except (TypeError, ValueError):
            return raw_str

    def __setitem__(self, item, value):
        self._parent.redis.hset(self._hash_key, item, json.dumps(value))
        # Refresh TTL on every write — a live run keeps its export state fresh.
        self._parent.redis.expire(self._hash_key, _RUN_TTL_SECONDS)

    def __contains__(self, item) -> bool:
        return bool(self._parent.redis.hexists(self._hash_key, item))

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def update(self, other: dict):
        if not other:
            return
        payload = {k: json.dumps(v) for k, v in other.items()}
        self._parent.redis.hset(self._hash_key, mapping=payload)
        self._parent.redis.expire(self._hash_key, _RUN_TTL_SECONDS)


class LocalSubDictProxy:
    """
    Helper mirroring RedisSubDictProxy for in-memory fallback.

    Semantics parity note: `__contains__` and read-only `get` do NOT create
    the key. Only `__setitem__` and `update` create the underlying entry.
    This matches RedisSubDictProxy (hexists / hget are non-mutating).
    """

    def __init__(self, local_dict: dict, key: str):
        self._local_dict = local_dict
        self._key = key

    def _get_data_readonly(self) -> dict:
        """Non-mutating read — returns empty dict if entry doesn't exist yet."""
        return self._local_dict.get(self._key) or {}

    def _get_data_mutating(self) -> dict:
        """Lazy-create the entry so mutation can proceed."""
        if self._key not in self._local_dict:
            self._local_dict[self._key] = {}
        return self._local_dict[self._key]

    # Kept for backward compat with any external caller that reached in here.
    # Prefer the two specific accessors above.
    def _get_data(self) -> dict:
        return self._get_data_mutating()

    def __getitem__(self, item):
        data = self._get_data_readonly()
        if item not in data:
            raise KeyError(item)
        return data[item]

    def __setitem__(self, item, value):
        self._get_data_mutating()[item] = value

    def __contains__(self, item) -> bool:
        return item in self._get_data_readonly()

    def get(self, item, default=None):
        return self._get_data_readonly().get(item, default)

    def update(self, other: dict):
        self._get_data_mutating().update(other)

    def __len__(self) -> int:
        return len(self._get_data_readonly())

    def __bool__(self) -> bool:
        return len(self) > 0


class RedisListProxy:
    """
    Dict of lists, each list backed by a Redis LIST. Falls back to in-memory
    dict of lists when Redis is unreachable.
    """

    def __init__(self, key_prefix: str):
        self.key_prefix = key_prefix
        self.redis = _REDIS_CLIENT
        self.local_dict: dict[str, list] = {}

    def _full_key(self, key: str) -> str:
        return f"state:{self.key_prefix}:{key}"

    def __getitem__(self, key: str):
        if self.redis:
            return RedisListHelper(self.redis, self._full_key(key))
        if key not in self.local_dict:
            self.local_dict[key] = []
        return self.local_dict[key]

    def __setitem__(self, key: str, value):
        if self.redis:
            full_k = self._full_key(key)
            self.redis.delete(full_k)
            if value:
                self.redis.rpush(full_k, *value)
                self.redis.expire(full_k, _RUN_TTL_SECONDS)
        else:
            self.local_dict[key] = value

    def __delitem__(self, key: str):
        if self.redis:
            full_k = self._full_key(key)
            if not self.redis.exists(full_k):
                raise KeyError(key)
            self.redis.delete(full_k)
        else:
            del self.local_dict[key]

    def __contains__(self, key: str) -> bool:
        if self.redis:
            return bool(self.redis.exists(self._full_key(key)))
        return key in self.local_dict

    def get(self, key: str, default=None):
        if self.redis:
            # Always return a helper — no upfront EXISTS check. An LRANGE
            # against a missing key returns `[]`, which is the same behavior
            # a caller would get from a real empty list. Avoids an extra
            # Redis roundtrip per `.get()` call (matters in SSE hot loops).
            # The `default` argument is preserved for API compatibility but
            # will only be returned in the in-memory fallback path.
            return RedisListHelper(self.redis, self._full_key(key))
        return self.local_dict.get(key, default)

    def pop(self, key: str, default=None):
        if self.redis:
            full_k = self._full_key(key)
            if not self.redis.exists(full_k):
                return default
            helper = RedisListHelper(self.redis, full_k)
            items = list(helper)
            self.redis.delete(full_k)
            return items
        return self.local_dict.pop(key, default)


class RedisListHelper:
    """
    Emulates a subset of list semantics on top of a Redis LIST.
    Each append renews the TTL and LTRIMs to the configured cap.
    """

    def __init__(self, r_client: redis.Redis, full_key: str):
        self.r_client = r_client
        self.full_key = full_key

    def append(self, value):
        self.r_client.rpush(self.full_key, value)
        # Bound growth AND refresh TTL — two ops but both cheap.
        self.r_client.ltrim(self.full_key, -_MAX_EVENTS_PER_RUN, -1)
        self.r_client.expire(self.full_key, _RUN_TTL_SECONDS)

    def __len__(self) -> int:
        return self.r_client.llen(self.full_key)

    def __getitem__(self, index):
        if isinstance(index, slice):
            start = index.start or 0
            stop = index.stop
            if stop is None:
                stop = -1
            elif stop > 0:
                stop = stop - 1
            raw_list = self.r_client.lrange(self.full_key, start, stop)
            return [raw.decode("utf-8") for raw in raw_list]
        raw = self.r_client.lindex(self.full_key, index)
        if raw is None:
            raise IndexError("list index out of range")
        return raw.decode("utf-8")

    def __iter__(self):
        raw_list = self.r_client.lrange(self.full_key, 0, -1)
        for raw in raw_list:
            yield raw.decode("utf-8")


# ── Proxy instances ────────────────────────────────────────────────────────────
_runs = RedisDictProxy(
    key_prefix="runs",
    serializer=lambda x: x.model_dump_json(),
    deserializer=lambda x: PipelineState.model_validate_json(x),
)
_run_events = RedisListProxy(key_prefix="events")
_run_export = RedisDictProxy(key_prefix="export", return_sub_proxy=True)
_run_owner = RedisDictProxy(key_prefix="owner")
_run_cancel_flags = RedisDictProxy(
    key_prefix="cancel_flags",
    serializer=lambda x: json.dumps(bool(x)),
    deserializer=lambda x: json.loads(x),
)


def _push_event(run_id: str, data: dict) -> None:
    if run_id not in _run_events:
        _run_events[run_id] = []
    log.info(f"[_push_event] run_id={run_id} type={data.get('type')} data={data}")
    try:
        seq = len(_run_events[run_id])
        payload = {**data, "seq": seq, "ts": time.time()}
        _run_events[run_id].append(json.dumps(payload))
    except Exception as e:
        log.error(f"[_push_event] failed to serialize: {e}")

"""
src/api/consent.py
═══════════════════
Consent persistence for signed-in users, so a returning user isn't shown the
Terms/Privacy modal on every relogin.

Two separate stores, on purpose:
  • _consent_index (Redis-backed, 1-year TTL) - a fast O(1) "has this email
    already accepted the CURRENT terms_version" lookup, keyed by email.
    Uses the same RedisDictProxy machinery as run state and rate limiting
    (src/api/state.py), so it gets the same graceful in-memory degradation
    if Redis is unreachable.
  • logs/consent.jsonl - the append-only audit trail (unchanged), one record
    per pipeline run, kept for compliance/audit purposes.

Why not just scan the JSONL to answer "has this email consented"? Cloud Run
instances don't share a local filesystem - each instance would only see the
consent history written by requests it happened to handle itself, so a
JSONL scan can't work as authoritative state once you're running more than
one instance. The Redis-backed index is the same shared-state fix already
used for _runs/_run_export/rate limiting.

Guests are intentionally excluded from the fast index: every guest session
is anonymous and one-off, so guests continue to see the consent modal every
session, matching existing behavior.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from src.api.state import RedisDictProxy

CURRENT_TERMS_VERSION = "2026-07-01"

# 1 year: long enough that normal returning users never see a re-prompt
# between visits, short enough that abandoned/stale entries don't accumulate
# in Redis forever. A terms_version bump invalidates old entries immediately
# regardless of TTL, since has_consented() compares against CURRENT_TERMS_VERSION.
_CONSENT_TTL_SECONDS = 60 * 60 * 24 * 365

_consent_index = RedisDictProxy(key_prefix="consent", ttl_seconds=_CONSENT_TTL_SECONDS)


def has_consented(email: str) -> bool:
    """O(1) check: has this email already accepted the current terms version?"""
    if not email:
        return False
    return _consent_index.get(email) == CURRENT_TERMS_VERSION


def record_consent(email: str, is_guest: bool, brd_hash: str) -> None:
    """
    Record a consent acceptance: update the fast per-email index (skipped for
    guests - see module docstring) and append to the audit trail.
    """
    if not is_guest and email:
        _consent_index[email] = CURRENT_TERMS_VERSION

    consent_dir = Path("logs")
    consent_dir.mkdir(exist_ok=True)
    consent_file = consent_dir / "consent.jsonl"

    consent_record = {
        "email": "guest" if is_guest else email,
        "is_guest": is_guest,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "brd_hash": brd_hash,
        "terms_version": CURRENT_TERMS_VERSION,
    }

    with open(consent_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(consent_record) + "\n")

"""
src/agents/registry.py
═══════════════════════
Specialist agent registry - Phase 4.

Each specialist module calls register_specialist() at import time.
pipeline.py uses get_specialist() to dispatch agents without a hardcoded
if/elif chain.
"""

from __future__ import annotations

SPECIALISTS: dict[str, type] = {}


def register_specialist(name: str, cls: type) -> None:
    """Register a specialist agent class under the given name."""
    SPECIALISTS[name] = cls


def get_specialist(name: str) -> type:
    """Return the specialist class for name, raising KeyError if unknown."""
    try:
        return SPECIALISTS[name]
    except KeyError:
        raise KeyError(f"Unknown specialist agent: '{name}'. Registered: {list(SPECIALISTS)}")

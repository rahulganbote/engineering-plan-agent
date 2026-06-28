"""
src/integrations/export_registry.py
═════════════════════════════════════
Export-handler registry - Phase 7.

Each integration module calls register_export() at module level.
The /approve endpoint iterates EXPORTS filtered by decision to collect results,
replacing the hardcoded Sheets → Jira → PDF → Slack sequence.

Handler signature:  handler(state: PipelineState) -> dict
on_decision values: "approve" | "reject" | "both" | "error"
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from src.core.models import PipelineState

# Registry: name → {handler, on_decision}
EXPORTS: dict[str, dict] = {}


def register_export(
    name: str,
    handler: Callable[[PipelineState], dict],
    on_decision: Literal["approve", "reject", "both", "error"],
) -> None:
    """Register an export handler under name."""
    EXPORTS[name] = {"handler": handler, "on_decision": on_decision}


def get_handlers_for_decision(
    decision: Literal["approve", "reject", "error"],
) -> list[tuple[str, Callable[[PipelineState], dict]]]:
    """Return (name, handler) pairs matching the given decision."""
    results = []
    for name, entry in EXPORTS.items():
        od = entry["on_decision"]
        if od == "both" or od == decision:
            results.append((name, entry["handler"]))
    return results

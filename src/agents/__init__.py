"""
src/agents
══════════
All 7 agents in the EM Copilot multi-agent pipeline.

Agent inventory:
    orchestrator.py    — Parses BRD, builds routing plan, manages state
    plan_generator.py  — Generates phased engineering plan (Reflection pattern)
    schedule.py        — Estimates sprint schedule from RAG timeline data
    architect.py       — Designs system architecture grounded in RAG patterns
    poc_planner.py     — Scopes the PoC to validate riskiest assumption
    tech_stack.py      — Recommends 2-3 stack options with trade-offs + GitHub tool
    critic.py          — Scores all 5 outputs, runs revision loop, assigns badges

Import pattern:
    from src.agents.critic import CriticAgent
    from src.agents.plan_generator import PlanGeneratorAgent
"""

# Phase 4: Import specialist modules at package load so they register in the registry.
from src.agents import architect, plan_generator, poc_planner, schedule, tech_stack  # noqa: F401

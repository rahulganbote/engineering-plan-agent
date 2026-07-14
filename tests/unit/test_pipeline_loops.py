# tests/unit/test_pipeline_loops.py
from src.agents.pipeline import (
    route_after_critic,
    route_after_decision,
    route_after_orchestrator,
)


def test_route_after_orchestrator():
    state = {"run_id": "test", "brd_raw_hash": "hash", "pipeline_status": "drafting", "errors": []}
    assert route_after_orchestrator(state) == "node_pass1_drafting"


def test_route_after_critic_no_error():
    state = {"run_id": "test", "brd_raw_hash": "hash", "pipeline_status": "evaluating", "errors": []}
    assert route_after_critic(state) == "decision_router"


def test_route_after_decision_exported():
    state = {"run_id": "test", "brd_raw_hash": "hash", "pipeline_status": "exported", "errors": []}
    assert route_after_decision(state) == "await_hitl"

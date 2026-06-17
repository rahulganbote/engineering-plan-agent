import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.main import _runs, _run_events, _push_event, _wire_resilience_and_cache
from src.agents.pipeline import run_pipeline
import asyncio

async def test():
    # Wire events
    await _wire_resilience_and_cache()
    
    brd_text = "Sample BRD content for payment processor. Needs secure payment gateway."
    brd_hash = "mock_hash"
    run_id = "test-run-999"
    
    print("Running pipeline...")
    state = run_pipeline(brd_text, brd_hash, run_id, "test_brd.txt")
    print(f"Pipeline completed with status: {state.pipeline_status}")
    
    events = _run_events.get(run_id, [])
    print(f"Total events captured: {len(events)}")
    for i, ev in enumerate(events):
        print(f"[{i}] {ev}")

if __name__ == "__main__":
    asyncio.run(test())

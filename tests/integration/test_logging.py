"""
Integration test to verify download logging, approval appending, and email-id column.
"""

import csv
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def seed_mock_run(run_id: str):
    from src.api.main import _runs
    from src.core.models import CriticOutput, DimensionScore, PipelineState, QualityBadge

    dim_score = DimensionScore(
        score=3.5, threshold=3.0, passed=True, evidence="Good quality", improvement_suggestion="None"
    )

    critic = CriticOutput(
        run_id=run_id,
        revision_number=0,
        target_agents=[],
        groundedness=dim_score,
        completeness=dim_score,
        consistency=dim_score,
        actionability=dim_score,
        overall_score=3.5,
        badge=QualityBadge.AMBER,
        requires_revision=False,
    )

    state = PipelineState(
        run_id=run_id,
        brd_raw_hash="mock_hash",
        brd_name="mock_test.txt",
        pipeline_status="awaiting_hitl",
        critic_output=critic,
    )

    _runs[run_id] = state


def test_api_endpoints():
    print("--- Testing API Endpoints In-Process ---")
    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    run_id = f"test-run-{uuid.uuid4().hex[:6]}"
    print(f"Using run_id: {run_id}")

    # 1. Inject mock pipeline state
    seed_mock_run(run_id)

    # 2. Get artifacts
    artifacts_url = f"/artifacts/{run_id}"
    print(f"GET {artifacts_url}")
    res = client.get(artifacts_url)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    state_data = res.json()
    assert state_data["pipeline_status"] == "awaiting_hitl"
    print("Get Artifacts OK (status: awaiting_hitl)")

    # 3. Log download
    download_url = f"/log-download/{run_id}"
    payload_download = {"email": "downloader@example.com"}
    print(f"POST {download_url} with payload {payload_download}")
    res = client.post(download_url, json=payload_download)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    print("Log Download OK:", res.json())

    # 4. Approve run
    approve_url = f"/approve/{run_id}"
    payload_approve = {
        "decision": "approved",
        "reviewer": "Test Reviewer",
        "notes": "Approved standard run",
        "em_rating": 5,
        "email": "approver@example.com",
    }
    print(f"POST {approve_url} with payload {payload_approve}")
    res = client.post(approve_url, json=payload_approve)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    approve_res = res.json()
    print("Approve OK. Export Mode:", approve_res.get("export_mode"), "Detail:", approve_res.get("export_detail"))

    # If it fell back to local, let's verify the CSV file directly
    if approve_res.get("export_mode") == "local":
        verify_local_csv(run_id)
    else:
        print("Note: Export was sent to Google Sheets (url: {}).".format(approve_res.get("sheet_url")))
        print("To verify local CSV fallback explicitly, running mock direct test next...")
    return True


def verify_local_csv(run_id: str):
    csv_path = ROOT / "logs/exports" / run_id / "run_summary.csv"
    assert csv_path.exists(), f"CSV fallback file does not exist at {csv_path}"
    print(f"Reading CSV file at: {csv_path}")

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Validate headers
    headers = rows[0]
    print("CSV Headers:", headers)
    assert "email-id" in headers, "Missing 'email-id' header"
    email_idx = headers.index("email-id")
    decision_idx = headers.index("hitl_decision")

    # Validate rows: we expect at least two data rows if both actions went to local
    data_rows = rows[1:]
    print(f"Found {len(data_rows)} data rows:")
    for idx, row in enumerate(data_rows):
        print(f"  Row {idx + 1}: decision={row[decision_idx]} email={row[email_idx]}")

    # Check row values
    assert any(
        row[decision_idx] == "download_pdf" and row[email_idx] == "downloader@example.com" for row in data_rows
    ), "Could not find download_pdf row with downloader@example.com"
    assert any(row[decision_idx] == "approved" and row[email_idx] == "approver@example.com" for row in data_rows), (
        "Could not find approved row with approver@example.com"
    )
    print("Local CSV Verification SUCCESS!")


def test_forced_local_sheets_export():
    print("\n--- Testing write_artifacts_to_sheet Direct local fallback ---")
    from unittest.mock import patch

    from src.core.models import CriticOutput, DimensionScore, HITLDecision, PipelineState, QualityBadge
    from src.integrations.sheets import write_artifacts_to_sheet

    run_id = f"test-run-direct-{uuid.uuid4().hex[:6]}"
    state = PipelineState(run_id=run_id, brd_raw_hash="directhash", brd_name="test_direct.txt")
    state.pipeline_status = "awaiting_hitl"
    dim_score = DimensionScore(
        score=3.5, threshold=3.0, passed=True, evidence="Good quality", improvement_suggestion="None"
    )
    state.critic_output = CriticOutput(
        run_id=run_id,
        revision_number=0,
        target_agents=[],
        groundedness=dim_score,
        completeness=dim_score,
        consistency=dim_score,
        actionability=dim_score,
        overall_score=3.5,
        badge=QualityBadge.AMBER,
        requires_revision=False,
    )

    # Mock _credentials_status to force local fallback
    with patch("src.integrations.sheets._credentials_status", return_value=(False, "Forced local testing")):
        # 1. Simulate download log
        state.hitl_decision = HITLDecision.DOWNLOAD_PDF
        res1 = write_artifacts_to_sheet(state, email="downloader_direct@example.com")
        assert res1["mode"] == "local"

        # 2. Simulate approval log
        state.hitl_decision = HITLDecision.APPROVED
        res2 = write_artifacts_to_sheet(state, email="approver_direct@example.com")
        assert res2["mode"] == "local"

    # Now verify the generated CSV
    csv_path = ROOT / "logs/exports" / run_id / "run_summary.csv"
    assert csv_path.exists(), f"CSV fallback file does not exist at {csv_path}"
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    headers = rows[0]
    email_idx = headers.index("email-id")
    decision_idx = headers.index("hitl_decision")
    data_rows = rows[1:]

    print(f"Direct export fallback: found {len(data_rows)} data rows:")
    for idx, row in enumerate(data_rows):
        print(f"  Row {idx + 1}: decision={row[decision_idx]} email={row[email_idx]}")

    assert len(data_rows) == 2, f"Expected exactly 2 rows, found {len(data_rows)}"
    assert data_rows[0][decision_idx] == "download_pdf" and data_rows[0][email_idx] == "downloader_direct@example.com"
    assert data_rows[1][decision_idx] == "approved" and data_rows[1][email_idx] == "approver_direct@example.com"
    print("Direct local fallback Verification SUCCESS!")


if __name__ == "__main__":
    try:
        api_tested = test_api_endpoints()
        test_forced_local_sheets_export()
        if api_tested:
            print("\nAll integration checks (API and Direct export fallback) passed successfully!")
        else:
            print("\nDirect export fallback check passed successfully! (API check skipped)")
    except AssertionError as e:
        print(f"\nAssertion error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

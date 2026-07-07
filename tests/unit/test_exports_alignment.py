# tests/unit/test_exports_alignment.py
from src.core.models import (
    AlignmentDirective,
    AlignmentMemo,
    CriticOutput,
    DimensionScore,
    PipelineState,
    QualityBadge,
)
from src.integrations.jira import _build_adf_description
from src.integrations.jira_mcp import _build_markdown_description
from src.integrations.pdf_export import build_artifacts_pdf


def _create_mock_state(alignment_memo=None):
    critic = CriticOutput(
        run_id="test-run",
        revision_number=0,
        target_agents=[],
        groundedness=DimensionScore(score=5.0, threshold=4.0, passed=True, evidence="", improvement_suggestion=""),
        completeness=DimensionScore(score=5.0, threshold=4.0, passed=True, evidence="", improvement_suggestion=""),
        consistency=DimensionScore(score=5.0, threshold=4.0, passed=True, evidence="", improvement_suggestion=""),
        actionability=DimensionScore(score=5.0, threshold=4.0, passed=True, evidence="", improvement_suggestion=""),
        overall_score=5.0,
        badge=QualityBadge.GREEN,
        requires_revision=False,
    )

    state = PipelineState(
        run_id="test-run-123",
        brd_raw_hash="hash-abc",
        brd_name="test.txt",
        critic_output=critic,
        alignment_memo=alignment_memo,
    )
    return state


def test_pdf_export_with_alignment_directives():
    memo = AlignmentMemo(
        overall_strategy="Align tech stack with architecture components.",
        directives=[
            AlignmentDirective(
                agent_name="solution_architect",
                directive="Use PostgreSQL instead of MongoDB",
                reasoning="Relational DB fits the transactional nature",
                evidence="BRD Section 3.1",
            )
        ],
    )
    state = _create_mock_state(alignment_memo=memo)

    pdf_bytes = build_artifacts_pdf(state)
    assert len(pdf_bytes) > 0


def test_pdf_export_with_empty_directives():
    memo = AlignmentMemo(overall_strategy="All drafts consistent", directives=[])
    state = _create_mock_state(alignment_memo=memo)

    pdf_bytes = build_artifacts_pdf(state)
    assert len(pdf_bytes) > 0


def test_pdf_export_with_null_memo():
    state = _create_mock_state(alignment_memo=None)

    pdf_bytes = build_artifacts_pdf(state)
    assert len(pdf_bytes) > 0


def test_jira_mcp_markdown_export():
    memo = AlignmentMemo(
        overall_strategy="Global database strategy",
        directives=[
            AlignmentDirective(
                agent_name="solution_architect",
                directive="Use standard PostgreSQL",
                reasoning="Consistency check",
                evidence="BRD Requirement 4",
            )
        ],
    )

    # 1. With memo and directives
    state = _create_mock_state(alignment_memo=memo)
    desc = _build_markdown_description(state)
    assert "Engineering Manager Alignment Directives" in desc
    assert "Global database strategy" in desc
    assert "Solution Architect" in desc
    assert "Use standard PostgreSQL" in desc
    assert "Consistency check" in desc
    assert "BRD Requirement 4" in desc

    # 2. With empty directives
    state_empty = _create_mock_state(alignment_memo=AlignmentMemo(overall_strategy="None", directives=[]))
    desc_empty = _build_markdown_description(state_empty)
    assert "All Pass 1 drafts aligned" in desc_empty

    # 3. With null memo
    state_null = _create_mock_state(alignment_memo=None)
    desc_null = _build_markdown_description(state_null)
    assert "Engineering Manager Alignment Directives" not in desc_null


def test_jira_rest_adf_export():
    memo = AlignmentMemo(
        overall_strategy="Global DB Strategy",
        directives=[
            AlignmentDirective(
                agent_name="tech_stack_recommender",
                directive="Switch to FastAPI",
                reasoning="Performance",
                evidence="BRD Page 5",
            )
        ],
    )

    # 1. With memo and directives
    state = _create_mock_state(alignment_memo=memo)
    adf = _build_adf_description(state)

    assert adf["type"] == "doc"

    found_heading = False
    found_strategy = False
    found_directive = False

    for block in adf["content"]:
        if block.get("type") == "heading" and block.get("content"):
            if "Engineering Manager Alignment Directives" in block["content"][0].get("text", ""):
                found_heading = True
        elif block.get("type") == "paragraph" and block.get("content"):
            text_runs = [run.get("text", "") for run in block["content"]]
            combined = "".join(text_runs)
            if "Global DB Strategy" in combined:
                found_strategy = True
        elif block.get("type") == "bulletList" and block.get("content"):
            for item in block["content"]:
                if item.get("type") == "listItem" and item.get("content"):
                    for p in item["content"]:
                        if p.get("type") == "paragraph" and p.get("content"):
                            item_text = p["content"][0].get("text", "")
                            if "Tech Stack Recommender" in item_text and "Switch to FastAPI" in item_text:
                                found_directive = True

    assert found_heading
    assert found_strategy
    assert found_directive

    # 2. With empty directives
    state_empty = _create_mock_state(alignment_memo=AlignmentMemo(directives=[]))
    adf_empty = _build_adf_description(state_empty)
    found_aligned_text = False
    for block in adf_empty["content"]:
        if block.get("type") == "paragraph" and block.get("content"):
            combined = "".join([run.get("text", "") for run in block["content"]])
            if "All Pass 1 drafts aligned" in combined:
                found_aligned_text = True
    assert found_aligned_text

    # 3. With null memo
    state_null = _create_mock_state(alignment_memo=None)
    adf_null = _build_adf_description(state_null)
    for block in adf_null["content"]:
        if block.get("type") == "heading" and block.get("content"):
            assert "Engineering Manager Alignment Directives" not in block["content"][0].get("text", "")

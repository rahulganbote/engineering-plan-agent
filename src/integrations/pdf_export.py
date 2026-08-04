"""
src/integrations/pdf_export.py
═══════════════════════════════
Renders the full PipelineState as a portable PDF using reportlab.platypus.

Public surface:
    build_artifacts_pdf(state: PipelineState) -> bytes
        Returns a complete PDF document as bytes. Called from the FastAPI
        GET /download/{run_id} endpoint and from the React UI "Download PDF"
        button (via that endpoint).

Sections in the rendered PDF:
    1. Header  - run ID, badge, exported timestamp
    2. Critic  - overall score, 4 dimension scores with PASS/FAIL
    3. Plan    - phases, milestones table, risks table
    4. Schedule - sprints table, critical path
    5. Architecture - pattern, justification, components table, NFR mappings,
                       Mermaid source (as fixed-width code block for copy-paste)
    6. PoC      - hypothesis, scope_in/out, success criteria
    7. Tech Stack - options table with trade-offs

Design choices:
    - Letter page size, narrow margins (36 pt) so wide tables fit
    - System fonts only (no font registration) - Helvetica family
    - Long-text fields are paragraph-wrapped so 2-page-wide rows wrap properly
    - The Mermaid diagram is rendered as a TEXT code block, not an embedded
      SVG/PNG, to avoid runtime dependence on Kroki at PDF-generation time.
      The React UI already shows the rendered SVG separately.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.core.models import PipelineState

# ── Style helpers ────────────────────────────────────────────────────────────


def _styles():
    base = getSampleStyleSheet()
    # Add a tighter body style + a Mermaid/code style
    base.add(
        ParagraphStyle(
            name="Small",
            parent=base["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#374151"),
        )
    )
    base.add(
        ParagraphStyle(
            name="Mono",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#111827"),
            leftIndent=8,
            rightIndent=8,
            backColor=colors.HexColor("#F3F4F6"),
            borderColor=colors.HexColor("#D1D5DB"),
            borderWidth=0.5,
            borderPadding=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="H2",
            parent=base["Heading2"],
            textColor=colors.HexColor("#1F3864"),
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="H3",
            parent=base["Heading3"],
            textColor=colors.HexColor("#2E75B6"),
            spaceBefore=10,
            spaceAfter=4,
        )
    )
    return base


_DEFAULT_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#FAFBFC")]),
    ]
)


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────


def build_artifacts_pdf(state: PipelineState) -> bytes:
    """Render the PipelineState as a complete PDF. Returns bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=42,
        bottomMargin=36,
        title=f"EM Copilot - {state.run_id}",
        author="EM Copilot",
    )
    styles = _styles()
    story: list[Any] = []

    _add_header(story, styles, state)
    _add_critic(story, styles, state)
    _add_alignment_directives(story, styles, state)
    _add_plan(story, styles, state)
    _add_schedule(story, styles, state)
    _add_architecture(story, styles, state)
    _add_poc(story, styles, state)
    _add_tech_stack(story, styles, state)

    doc.build(story)
    return buffer.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Section builders
# ──────────────────────────────────────────────────────────────────────────────


def _add_header(story, styles, state: PipelineState) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    badge = state.critic_output.badge.value.upper() if state.critic_output else "N/A"
    overall = state.critic_output.overall_score if state.critic_output else 0.0

    story.append(Paragraph("EM Copilot - Engineering Artifacts", styles["Title"]))
    story.append(
        Paragraph(
            "<font color='#6B7280'>Multi-agent BRD-to-engineering-plan pipeline</font>",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 6))

    meta_table = Table(
        [
            ["Run ID", state.run_id],
            ["Exported", ts],
            ["Pipeline status", state.pipeline_status],
            ["Critic badge", f"{badge}  ·  {overall:.2f} / 5.0"],
            ["Revisions", str(state.revision_count)],
            ["HITL decision", state.hitl_decision.value],
        ],
        colWidths=[1.4 * inch, 5.6 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 8))


def _add_critic(story, styles, state: PipelineState) -> None:
    critic = state.critic_output
    if not critic:
        return
    story.append(Paragraph("1. Independent Quality Score", styles["H2"]))

    dims = [
        ("Groundedness", critic.groundedness),
        ("Completeness", critic.completeness),
        ("Consistency", critic.consistency),
        ("Actionability", critic.actionability),
    ]
    rows = [["Dimension", "Score", "Threshold", "Verdict"]]
    for name, dim in dims:
        rows.append(
            [
                name,
                f"{dim.score:.2f}",
                f"≥ {dim.threshold:.2f}",
                "PASS" if dim.passed else "FAIL",
            ]
        )
    rows.append(
        [
            Paragraph("<b>Overall</b>", styles["BodyText"]),
            Paragraph(f"<b>{critic.overall_score:.2f}</b>", styles["BodyText"]),
            "≥ 4.00",
            critic.badge.value.upper(),
        ]
    )
    tbl = Table(rows, colWidths=[1.8 * inch, 1.0 * inch, 1.0 * inch, 3.3 * inch])
    tbl.setStyle(_DEFAULT_TABLE_STYLE)
    story.append(tbl)

    if critic.consistency_issues:
        story.append(
            Paragraph(
                f"<b>Consistency findings ({len(critic.consistency_issues)}):</b>",
                styles["Small"],
            )
        )
        for issue in critic.consistency_issues[:6]:
            agents = ", ".join(issue.agents_involved or [])
            story.append(
                Paragraph(
                    f"• <i>{issue.severity.value}</i> - {issue.conflict_description} ({agents})",
                    styles["Small"],
                )
            )

    if critic.hallucination_flags:
        story.append(
            Paragraph(
                f"<b>Hallucination flags ({len(critic.hallucination_flags)}):</b>",
                styles["Small"],
            )
        )
        for h in critic.hallucination_flags[:6]:
            story.append(
                Paragraph(
                    f"• <i>{h.status}</i> - {h.agent}: {h.claim[:160]}",
                    styles["Small"],
                )
            )
    story.append(Spacer(1, 6))


def _add_alignment_directives(story, styles, state: PipelineState) -> None:
    memo = state.alignment_memo
    if not memo:
        return
    story.append(Paragraph("2. EM Copilot AI Plan Alignment Notes", styles["H2"]))
    if memo.overall_strategy:
        story.append(Paragraph(f"<b>Overall Strategy:</b> {memo.overall_strategy}", styles["BodyText"]))
        story.append(Spacer(1, 4))

    if memo.directives:
        rows = [["Agent", "Directive", "Reasoning", "Evidence"]]
        for d in memo.directives:
            agent_display = d.agent_name.replace("_", " ").title()
            rows.append(
                [
                    Paragraph(f"<b>{agent_display}</b>", styles["Small"]),
                    Paragraph(d.directive or "", styles["Small"]),
                    Paragraph(d.reasoning or "", styles["Small"]),
                    Paragraph(d.evidence or "", styles["Small"]),
                ]
            )
        tbl = Table(rows, colWidths=[1.3 * inch, 2.1 * inch, 2.1 * inch, 1.5 * inch])
        tbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(tbl)
    else:
        story.append(Paragraph("All Pass 1 drafts aligned — no arbitration needed.", styles["BodyText"]))
    story.append(Spacer(1, 6))


def _add_plan(story, styles, state: PipelineState) -> None:
    plan = state.plan_output
    if not plan:
        return
    story.append(Paragraph("3. Engineering Plan", styles["H2"]))
    team = ", ".join(f"{r} × {n}" for r, n in (plan.team_composition or {}).items())
    story.append(
        Paragraph(
            f"<b>Total duration:</b> {plan.total_duration_weeks} weeks  ·  "
            f"<b>Team:</b> {team or 'n/a'}  ·  "
            f"<b>Confidence:</b> {plan.confidence_score:.2f}",
            styles["BodyText"],
        )
    )

    for phase in plan.phases:
        story.append(
            Paragraph(
                f"<b>Phase:</b> {phase.name} ({phase.duration_weeks} weeks)",
                styles["H3"],
            )
        )
        if phase.objectives:
            for o in phase.objectives:
                story.append(Paragraph(f"• {o}", styles["Small"]))
        if phase.milestones:
            ms_rows = [["Week", "Milestone", "Owner", "Deliverable"]]
            for m in phase.milestones:
                ms_rows.append(
                    [
                        str(m.week),
                        m.name,
                        m.owner_role,
                        Paragraph(m.deliverable, styles["Small"]),
                    ]
                )
            ms_tbl = Table(ms_rows, colWidths=[0.6 * inch, 1.7 * inch, 1.2 * inch, 3.6 * inch])
            ms_tbl.setStyle(_DEFAULT_TABLE_STYLE)
            story.append(KeepTogether(ms_tbl))
            story.append(Spacer(1, 4))

    if plan.risks:
        story.append(Paragraph(f"<b>Risks ({len(plan.risks)})</b>", styles["H3"]))
        rrows = [["Description", "Likelihood", "Impact", "Mitigation"]]
        for r in plan.risks:
            rrows.append(
                [
                    Paragraph(r.description, styles["Small"]),
                    r.likelihood.value,
                    r.impact.value,
                    Paragraph(r.mitigation, styles["Small"]),
                ]
            )
        rtbl = Table(rrows, colWidths=[2.4 * inch, 0.9 * inch, 0.9 * inch, 2.9 * inch])
        rtbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(rtbl)

    if plan.reflection_notes:
        story.append(Paragraph("<b>Reflection notes:</b>", styles["Small"]))
        story.append(Paragraph(plan.reflection_notes, styles["Small"]))
    story.append(Spacer(1, 6))


def _add_schedule(story, styles, state: PipelineState) -> None:
    sched = state.schedule_output
    if not sched:
        return
    story.append(Paragraph("4. Schedule", styles["H2"]))
    story.append(
        Paragraph(
            f"<b>Total effort:</b> {sched.total_effort_days:.1f} days  ·  "
            f"<b>Buffer:</b> {sched.buffer_weeks} weeks  ·  "
            f"<b>Confidence:</b> {sched.confidence_score:.2f}",
            styles["BodyText"],
        )
    )
    if sched.critical_path:
        story.append(
            Paragraph(
                "<b>Critical path:</b> " + " → ".join(sched.critical_path),
                styles["Small"],
            )
        )

    if sched.sprints:
        rows = [["Sprint", "Weeks", "Deliverables", "Team", "Effort (d)"]]
        for row in sched.sprints:
            rows.append(
                [
                    str(row.sprint),
                    row.week_range,
                    Paragraph(" • ".join(row.deliverables), styles["Small"]),
                    ", ".join(row.team_members),
                    f"{row.effort_days:.1f}",
                ]
            )
        tbl = Table(rows, colWidths=[0.6 * inch, 0.8 * inch, 3.0 * inch, 1.7 * inch, 0.8 * inch])
        tbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(tbl)
    story.append(Spacer(1, 6))


def _add_architecture(story, styles, state: PipelineState) -> None:
    arch = state.arch_output
    if not arch:
        return
    story.append(Paragraph("5. Architecture", styles["H2"]))
    story.append(
        Paragraph(
            f"<b>Pattern:</b> {arch.pattern}  ·  <b>Deployment:</b> {arch.deployment_model}",
            styles["BodyText"],
        )
    )
    if arch.pattern_justification:
        story.append(Paragraph(f"<b>Justification:</b> {arch.pattern_justification}", styles["BodyText"]))

    if arch.components:
        story.append(Paragraph("<b>Components</b>", styles["H3"]))
        rows = [["Name", "Technology", "Responsibility", "Interfaces"]]
        for c in arch.components:
            rows.append(
                [
                    c.name,
                    c.technology,
                    Paragraph(c.responsibility, styles["Small"]),
                    Paragraph(", ".join(c.interfaces), styles["Small"]),
                ]
            )
        tbl = Table(rows, colWidths=[1.5 * inch, 1.3 * inch, 2.9 * inch, 1.4 * inch])
        tbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(tbl)
        story.append(Spacer(1, 4))

    if arch.nfr_mappings:
        story.append(Paragraph("<b>NFR mappings</b>", styles["H3"]))
        for n in arch.nfr_mappings:
            story.append(
                Paragraph(
                    f"• <i>{n.nfr}</i> → {n.architecture_decision}",
                    styles["Small"],
                )
            )

    if arch.data_flow:
        story.append(
            Paragraph(
                "<b>Data flow:</b> " + " → ".join(arch.data_flow),
                styles["Small"],
            )
        )

    if arch.diagram_mermaid:
        story.append(
            Paragraph(
                "<b>Architecture diagram (Mermaid source - copy into Confluence/GitHub for live render):</b>",
                styles["Small"],
            )
        )
        # Escape reportlab paragraph special chars for the Mono style
        safe = (
            arch.diagram_mermaid.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        )
        story.append(Paragraph(safe, styles["Mono"]))
    story.append(Spacer(1, 6))


def _add_poc(story, styles, state: PipelineState) -> None:
    poc = state.poc_output
    if not poc:
        return
    story.append(Paragraph("6. Proof of Concept", styles["H2"]))
    story.append(Paragraph(f"<b>Hypothesis:</b> {poc.poc_hypothesis}", styles["BodyText"]))
    story.append(
        Paragraph(
            f"<b>Duration:</b> {poc.duration_weeks} weeks  ·  "
            f"<b>Team size:</b> {poc.team_size}  ·  "
            f"<b>Confidence:</b> {poc.confidence_score:.2f}",
            styles["BodyText"],
        )
    )
    if poc.scope_in:
        story.append(Paragraph("<b>In scope:</b> " + "; ".join(poc.scope_in), styles["Small"]))
    if poc.scope_out:
        story.append(Paragraph("<b>Out of scope:</b> " + "; ".join(poc.scope_out), styles["Small"]))

    if poc.success_criteria:
        story.append(Paragraph("<b>Success criteria</b>", styles["H3"]))
        rows = [["Metric", "Target", "Measurement"]]
        for c in poc.success_criteria:
            rows.append(
                [
                    Paragraph(c.metric, styles["Small"]),
                    Paragraph(c.target_value, styles["Small"]),
                    Paragraph(c.measurement_method, styles["Small"]),
                ]
            )
        tbl = Table(rows, colWidths=[2.0 * inch, 1.6 * inch, 3.5 * inch])
        tbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(tbl)
    if poc.risk_if_poc_fails:
        story.append(Paragraph(f"<b>Risk if PoC fails:</b> {poc.risk_if_poc_fails}", styles["Small"]))
    story.append(Spacer(1, 6))


def _add_tech_stack(story, styles, state: PipelineState) -> None:
    stack = state.stack_output
    if not stack:
        return
    story.append(Paragraph("7. Tech Stack Recommendation", styles["H2"]))
    story.append(
        Paragraph(
            f"<b>Recommended:</b> {stack.recommended_option}",
            styles["BodyText"],
        )
    )
    if stack.recommendation_rationale:
        story.append(Paragraph(f"<b>Rationale:</b> {stack.recommendation_rationale}", styles["BodyText"]))

    if stack.options:
        rows = [["Option", "Scalability", "Familiarity", "Risk", "$/mo", "Pros", "Cons"]]
        for opt in stack.options:
            mark = "★ " if opt.name == stack.recommended_option else ""
            rows.append(
                [
                    Paragraph(f"<b>{mark}{opt.name}</b>", styles["Small"]),
                    f"{opt.scalability_rating}/5",
                    f"{opt.team_familiarity_rating}/5",
                    opt.integration_risk.value,
                    f"${opt.estimated_monthly_cost_usd:,.0f}",
                    Paragraph(" • ".join(opt.pros), styles["Small"]),
                    Paragraph(" • ".join(opt.cons), styles["Small"]),
                ]
            )
        tbl = Table(
            rows, colWidths=[1.7 * inch, 0.7 * inch, 0.7 * inch, 0.6 * inch, 0.7 * inch, 1.7 * inch, 1.7 * inch]
        )
        tbl.setStyle(_DEFAULT_TABLE_STYLE)
        story.append(tbl)
    story.append(Spacer(1, 6))


# Phase 7: export-handler registry
from src.integrations.export_registry import register_export


def _pdf_export_handler(state):
    """Wrap build_artifacts_pdf for the export registry. Returns availability flag."""
    return {"available": True, "mode": "pdf"}


register_export("pdf", _pdf_export_handler, "approve")

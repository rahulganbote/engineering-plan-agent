"""
src/core/brd_utils.py
══════════════════════
Shared utilities for normalizing BRD text and extracting metadata from
parsed BRD sections.

Used by:
    - src/security/validator.py    → normalize_pdf_text() after pypdf extraction
    - src/agents/pipeline.py       → populate PipelineState.brd_project_title
    - src/agents/brd_context.py    → regex fallback when LLM extraction fails
    - src/integrations/jira.py     → Jira issue summary
    - src/integrations/pdf_export.py → PDF header
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models import BRDSection

# ── PDF text reflow ──────────────────────────────────────────────────────────
# pypdf's extract_text() frequently shatters a PDF into one word per line when
# the source document uses justified text or custom kerning. Observed shape:
#
#     'Goal  '                       ← heading arrives INTACT (trailing 2 spaces)
#     'Build  an  E-commerce  ...'    ← paragraph opener INTACT (internal 2 spaces)
#     'Sheets,'                      ← remainder shatters, one bare word per line
#     ' '
#     'evaluates'
#     ' '
#     'their'
#
# Left unrepaired this destroys every downstream consumer: the Orchestrator's
# heading regexes match stray single words ('Problem', 'The', 'At') instead of
# real headings, section routing collapses, and agents receive one-word-per-line
# noise that wastes tokens and obscures meaning.
#
# Repair strategy: drop whitespace-only lines, keep INTACT lines on their own
# line, and join each run of consecutive shattered fragments into one reflowed
# line. The distinguishing signal is that pypdf preserves the original text
# run's spacing on intact lines - a non-space character followed by 2+ spaces,
# either between words ('Data  Architecture') or trailing ('Goal  '). Shattered
# fragments arrive bare ('teams', 'monitor'). Keying on that signal keeps
# standalone headings on their own line so heading detection works again.
_INTACT_LINE = re.compile(r"\S[ \t]{2,}")

# Fraction of single-token non-blank lines above which we consider the text
# "shattered" and worth reflowing. Well-formed text sits far below this.
_SHATTER_THRESHOLD = 0.40
_MIN_LINES_TO_ASSESS = 12


def normalize_pdf_text(text: str) -> str:
    """
    Repair one-word-per-line text shattering from PDF extraction.

    No-ops when the text does not look shattered, so .txt/.md/.docx input and
    well-behaved PDFs pass through byte-identical.
    """
    if not text:
        return text

    raw_lines = text.split("\n")
    non_blank = [ln.strip() for ln in raw_lines if ln.strip()]
    if len(non_blank) < _MIN_LINES_TO_ASSESS:
        return text

    single_token = sum(1 for ln in non_blank if " " not in ln)
    if single_token / len(non_blank) < _SHATTER_THRESHOLD:
        return text  # layout is fine - leave the text untouched

    out: list[str] = []
    run: list[str] = []  # buffer of consecutive single-token lines

    def flush() -> None:
        if run:
            out.append(" ".join(run))
            run.clear()

    for ln in raw_lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if _INTACT_LINE.search(ln):
            # Line survived extraction intact (heading or paragraph opener).
            flush()
            # Collapse the double/triple spacing pypdf inserts between words.
            out.append(re.sub(r"[ \t]{2,}", " ", stripped))
        else:
            run.append(stripped)
    flush()

    return "\n".join(out)


# Section names that are too generic to serve as a project title
_GENERIC_HEADINGS = {
    "project overview",
    "overview",
    "background",
    "introduction",
    "executive summary",
    "full brd",
    "business requirements document",
    "business requirements",
    "requirements document",
    "brd",
}


# Leading markdown hashes, bullets, or numbering that should never appear in a
# user-facing project title. Section names and raw content lines may carry them.
_LEADING_MARKUP = re.compile(r"^\s*(?:#{1,6}\s*|[-*•]\s*|\d+[.)]\s*)+")


def _strip_markup(text: str) -> str:
    return _LEADING_MARKUP.sub("", text or "").strip()


def extract_project_name(brd_sections: list[BRDSection]) -> str:
    """
    Best-effort extraction of the BRD project name. Tries, in order:
      1. The first BRD section heading, if it's not a generic placeholder
         like "Project Overview" / "Background" / "Introduction".
      2. An explicit "Project:" / "Project Name:" line in any of the first
         three sections - common in template-driven BRDs.
      3. The leading proper-noun phrase of the first section's content:
         e.g. "FoodHub is a food-aggregator platform…" → "FoodHub".
         Catches the very common "<Name> is/provides/enables…" opening.
      4. The first short headline-style line of the first section's content.
      5. Final fallback: "BRD run".
    """
    if not brd_sections:
        return "BRD run"

    first = brd_sections[0]
    name = _strip_markup(first.section_name)

    # 2. Explicit "Project:" / "Project Name:" markers win over a heading, since
    #    a template BRD's first heading is usually the document type while the
    #    marker names the actual project. Checked in section names and content
    #    of the first five sections.
    project_marker = re.compile(
        r"^\s*(?:project(?:\s+name)?|product|system)\s*[:|]\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    for sec in brd_sections[:5]:
        candidates = [_strip_markup(sec.section_name)]
        candidates += [_strip_markup(ln) for ln in (sec.content or "").splitlines()[:10]]
        for cand_line in candidates:
            m = project_marker.match(cand_line)
            if not m:
                continue
            candidate = m.group(1).strip()
            # Strip trailing meta like "| Version: 1.0"
            candidate = re.split(r"\s*[|·]\s*", candidate, 1)[0].strip()
            if candidate:
                return candidate[:80]

    # 1. Non-generic first heading
    if name and name.lower() not in _GENERIC_HEADINGS:
        return name[:80]

    # 3. Leading proper-noun phrase: "FoodHub is a …" → "FoodHub"
    #    Matches 1–4 capitalized words followed by a copula/predicate verb
    leading_pn = re.match(
        r"^\s*([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3})\s+"
        r"(?:is|are|will|shall|provides?|enables?|offers?|delivers?|connects?)\b",
        (first.content or "").strip(),
    )
    if leading_pn:
        return leading_pn.group(1).strip()

    # 4. First short headline-style line of content
    for line in (first.content or "").splitlines():
        line = _strip_markup(line)
        if not line:
            continue
        if 4 <= len(line) <= 80 and not line.endswith("."):
            return line
        return line[:80].rstrip(".,;:") + ("…" if len(line) > 80 else "")

    return name or "BRD run"


def extract_objectives(brd_sections: list[BRDSection]) -> list[str]:
    """
    Extract the BRD's stated objectives/goals. Looks for an "Objectives"
    or "Goals" section and returns its numbered/bulleted items.
    Returns an empty list if none found.
    """
    obj_names = {
        "objective",
        "objectives",
        "goal",
        "goals",
        "business objectives",
        "business goals",
        "project goals",
        "project objectives",
        "purpose",
    }
    for sec in brd_sections:
        if (sec.section_name or "").strip().lower() in obj_names:
            items = []
            for line in (sec.content or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                # Strip leading numbering/bullets: "1. ...", "- ...", "* ..."
                cleaned = re.sub(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)", "", line).strip()
                if cleaned:
                    items.append(cleaned)
            return items
    return []

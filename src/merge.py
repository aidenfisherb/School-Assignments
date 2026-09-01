"""
Merges Canvas-sourced assignments with syllabus-extracted ones.

Matching is a heuristic, not exact: a syllabus title is prose describing
the same assignment Canvas names precisely, so titles are compared with
plain string similarity (stdlib difflib) rather than requiring an exact
match. Comparisons never cross courses.
"""

from __future__ import annotations

import difflib
import re

from .digest import DigestItem

# Starting point, not tuned against real data yet — expect to revisit once
# real syllabus extraction accuracy is visible on the dashboard.
TITLE_SIMILARITY_THRESHOLD = 0.6


def _normalize_title(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def merge_items(
    canvas_items: list[DigestItem],
    syllabus_items: list[DigestItem],
    handled: list[tuple[str, str]] | None = None,
) -> list[DigestItem]:
    """
    Combines Canvas items with syllabus items for the same courses.

    - Same course + similar title + same due date -> shown once (the
      Canvas copy is kept, since it has html_url/points/live submission
      status that a syllabus item never does).
    - Same course + similar title + different due date -> both kept,
      both flagged `conflict=True`, so a disagreement is surfaced instead
      of one source silently winning.
    - No matching Canvas item -> the syllabus item is kept as-is; this is
      the case where a syllabus has a due date Canvas never got.
    - A syllabus item matching something in `handled` (already submitted
      or graded on Canvas) is dropped entirely rather than resurrected.
    """
    handled = handled or []
    if not syllabus_items:
        return list(canvas_items)

    result = list(canvas_items)
    claimed: set[int] = set()

    for s in syllabus_items:
        if any(
            s.course_name == hc and _similarity(s.title, ht) >= TITLE_SIMILARITY_THRESHOLD
            for hc, ht in handled
        ):
            continue

        best_idx, best_score = None, 0.0
        for idx, c in enumerate(canvas_items):
            if id(c) in claimed or c.course_name != s.course_name:
                continue
            score = _similarity(c.title, s.title)
            if score > best_score:
                best_idx, best_score = idx, score

        if best_idx is not None and best_score >= TITLE_SIMILARITY_THRESHOLD:
            c = canvas_items[best_idx]
            claimed.add(id(c))
            if c.due_at.date() == s.due_at.date():
                continue  # true duplicate
            c.conflict = True
            s.conflict = True
            result.append(s)
        else:
            result.append(s)

    return result

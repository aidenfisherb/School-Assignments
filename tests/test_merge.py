"""Tests for the Canvas/syllabus reconciliation logic in src/merge.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.digest import DigestItem
from src.merge import merge_items

TZ = ZoneInfo("America/Chicago")


def _item(title, due_at, course_name="COSC240 - Intro to Cybersecurity", source="Canvas", **kw):
    return DigestItem(
        course_name=course_name,
        title=title,
        due_at=datetime.fromisoformat(due_at).replace(tzinfo=TZ),
        html_url=kw.pop("html_url", ""),
        points_possible=kw.pop("points_possible", None),
        kind=kw.pop("kind", "assignment"),
        source=source,
    )


def test_same_course_similar_title_same_date_is_deduplicated():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    syllabus = [_item("Homework #3", "2026-09-10T23:59:00", source="Syllabus")]
    merged = merge_items(canvas, syllabus)
    assert len(merged) == 1
    assert merged[0].source == "Canvas"
    assert not merged[0].conflict


def test_same_course_similar_title_different_date_is_flagged_conflicting():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    syllabus = [_item("Homework #3", "2026-09-08T23:59:00", source="Syllabus")]
    merged = merge_items(canvas, syllabus)
    assert len(merged) == 2
    assert all(i.conflict for i in merged)
    sources = {i.source for i in merged}
    assert sources == {"Canvas", "Syllabus"}


def test_syllabus_only_item_with_no_canvas_match_is_kept():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    syllabus = [_item("Reading Reflection 2", "2026-09-12T23:59:00", source="Syllabus")]
    merged = merge_items(canvas, syllabus)
    assert len(merged) == 2
    reflection = next(i for i in merged if i.title == "Reading Reflection 2")
    assert reflection.source == "Syllabus"
    assert not reflection.conflict


def test_same_title_different_course_never_matched():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00", course_name="COSC240")]
    syllabus = [_item("Homework 3", "2026-09-10T23:59:00", course_name="MATH301", source="Syllabus")]
    merged = merge_items(canvas, syllabus)
    assert len(merged) == 2
    assert not any(i.conflict for i in merged)


def test_dissimilar_titles_are_not_matched_or_flagged():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    syllabus = [_item("Group Presentation", "2026-09-15T23:59:00", source="Syllabus")]
    merged = merge_items(canvas, syllabus)
    assert len(merged) == 2
    assert not any(i.conflict for i in merged)


def test_syllabus_item_matching_handled_assignment_is_dropped():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    syllabus = [_item("HW 3", "2026-09-10T23:59:00", source="Syllabus")]
    handled = [("COSC240 - Intro to Cybersecurity", "HW 3")]
    merged = merge_items(canvas, syllabus, handled)
    assert len(merged) == 1
    assert merged[0].source == "Canvas"


def test_no_syllabus_items_returns_canvas_items_unchanged():
    canvas = [_item("Homework 3", "2026-09-10T23:59:00")]
    merged = merge_items(canvas, [])
    assert merged == canvas

"""
Tests for src/syllabus_extractor.py. Gemini is never called: a fake
extract_fn stands in for it, so these cover the matching, caching, and
conversion logic around the model rather than the model itself.
"""

import json
from datetime import date
from pathlib import Path

from src.syllabus_extractor import (
    ExtractedItem,
    discover_syllabus_files,
    match_course_key,
    process_syllabi,
    remove_orphaned_extractions,
    sidecar_path,
)

TODAY = date(2026, 9, 1)
COURSES = [{"id": 1, "course_code": "COSC240.01", "name": "Introduction to Cybersecurity"}]


def _syllabus(root: Path, folder="COSC240", name="syllabus.pdf", content=b"%PDF-fake") -> Path:
    path = root / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class FakeExtractor:
    def __init__(self, items=None, error=None):
        self.items = items if items is not None else [
            ExtractedItem(title="Homework 1", due_date="2026-09-10", due_time=None, kind="assignment"),
            ExtractedItem(title="Midterm", due_date="2026-10-14", due_time="09:30", kind="quiz"),
        ]
        self.error = error
        self.calls = 0

    def __call__(self, path, course_name, term, today):
        self.calls += 1
        if self.error:
            raise self.error
        return self.items, "test-model"


def _run(root, extract_fn):
    return process_syllabi(discover_syllabus_files(root), COURSES, extract_fn=extract_fn, today=TODAY)


def test_match_course_key_by_course_code():
    assert match_course_key("cosc240", COURSES) == 1
    assert match_course_key("COSC240", COURSES) == 1


def test_match_course_key_by_name_fallback():
    courses = [{"id": 2, "course_code": "SOA200.W06", "name": "Arts in Society"}]
    assert match_course_key("artsinsociety", courses) == 2


def test_match_course_key_no_match_returns_none():
    assert match_course_key("MATH101", COURSES) is None


def test_match_course_key_empty_folder_name_returns_none():
    assert match_course_key("___", COURSES) is None


def test_discover_ignores_sidecars_and_other_files(tmp_path):
    pdf = _syllabus(tmp_path)
    sidecar_path(pdf).write_text("{}")
    (tmp_path / "COSC240" / "notes.txt").write_text("hi")
    assert discover_syllabus_files(tmp_path) == {"COSC240": [pdf]}


def test_new_file_is_extracted_and_saved(tmp_path):
    pdf = _syllabus(tmp_path)
    fake = FakeExtractor()
    items, statuses = _run(tmp_path, fake)

    assert fake.calls == 1
    assert statuses[0].state == "extracted"
    assert statuses[0].item_count == 2
    saved = json.loads(sidecar_path(pdf).read_text())
    assert saved["model"] == "test-model"
    assert [i["title"] for i in saved["items"]] == ["Homework 1", "Midterm"]
    assert all(i.source == "Syllabus" and i.course_name == "Introduction to Cybersecurity" for i in items)


def test_saved_extraction_is_reused_without_calling_the_model(tmp_path):
    _syllabus(tmp_path)
    _run(tmp_path, FakeExtractor())
    fake = FakeExtractor()
    items, statuses = _run(tmp_path, fake)

    assert fake.calls == 0
    assert statuses[0].state == "cached"
    assert len(items) == 2


def test_saved_extraction_is_used_even_without_an_api_key(tmp_path):
    _syllabus(tmp_path)
    _run(tmp_path, FakeExtractor())
    items, statuses = _run(tmp_path, None)
    assert statuses[0].state == "cached"
    assert len(items) == 2


def test_hand_edits_to_the_saved_json_are_kept(tmp_path):
    pdf = _syllabus(tmp_path)
    _run(tmp_path, FakeExtractor())
    sidecar = sidecar_path(pdf)
    data = json.loads(sidecar.read_text())
    data["items"][0]["due_date"] = "2026-09-12"
    sidecar.write_text(json.dumps(data))

    items, _ = _run(tmp_path, FakeExtractor())
    assert items[0].due_at.date() == date(2026, 9, 12)


def test_replaced_file_is_re_extracted(tmp_path):
    _syllabus(tmp_path)
    _run(tmp_path, FakeExtractor())
    _syllabus(tmp_path, content=b"%PDF-revised")
    fake = FakeExtractor()
    _, statuses = _run(tmp_path, fake)
    assert fake.calls == 1
    assert statuses[0].state == "extracted"


def test_without_api_key_new_file_is_pending(tmp_path):
    pdf = _syllabus(tmp_path)
    items, statuses = _run(tmp_path, None)
    assert items == []
    assert statuses[0].state == "pending"
    assert not sidecar_path(pdf).exists()


def test_extraction_failure_is_reported_and_nothing_is_saved(tmp_path):
    pdf = _syllabus(tmp_path)
    items, statuses = _run(tmp_path, FakeExtractor(error=RuntimeError("429 rate limited")))
    assert items == []
    assert statuses[0].state == "failed"
    assert "rate limited" in statuses[0].detail
    assert not sidecar_path(pdf).exists()


def test_broken_hand_edit_is_reported_not_overwritten(tmp_path):
    pdf = _syllabus(tmp_path)
    sidecar_path(pdf).write_text("{ not json")
    fake = FakeExtractor()
    _, statuses = _run(tmp_path, fake)
    assert fake.calls == 0
    assert statuses[0].state == "failed"
    assert sidecar_path(pdf).read_text() == "{ not json"


def test_unmatched_folder_is_reported(tmp_path):
    _syllabus(tmp_path, folder="MATH101")
    fake = FakeExtractor()
    items, statuses = _run(tmp_path, fake)
    assert fake.calls == 0
    assert items == []
    assert statuses[0].state == "unmatched"


def test_items_without_a_time_are_due_end_of_day_and_flagged(tmp_path):
    _syllabus(tmp_path)
    items, _ = _run(tmp_path, FakeExtractor())
    homework = next(i for i in items if i.title == "Homework 1")
    midterm = next(i for i in items if i.title == "Midterm")
    assert not homework.has_time
    assert (homework.due_at.hour, homework.due_at.minute) == (23, 59)
    assert midterm.has_time
    assert (midterm.due_at.hour, midterm.due_at.minute) == (9, 30)
    assert midterm.kind == "quiz"


def test_item_with_unreadable_date_is_skipped(tmp_path):
    _syllabus(tmp_path)
    fake = FakeExtractor(items=[
        ExtractedItem(title="Essay", due_date="Sept 10", due_time=None, kind="assignment"),
        ExtractedItem(title="Lab 2", due_date="2026-09-11", due_time=None, kind="assignment"),
    ])
    items, statuses = _run(tmp_path, fake)
    assert [i.title for i in items] == ["Lab 2"]
    assert statuses[0].item_count == 1


def test_orphaned_extraction_is_removed(tmp_path):
    pdf = _syllabus(tmp_path)
    _run(tmp_path, FakeExtractor())
    pdf.unlink()
    removed = remove_orphaned_extractions(tmp_path)
    assert removed == [sidecar_path(pdf)]
    assert not sidecar_path(pdf).exists()

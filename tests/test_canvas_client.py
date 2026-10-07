"""Tests for the pure helpers in src/canvas_client.py (no network)."""

from src.canvas_client import completed_assignment_ids


def test_marked_complete_assignment_is_included():
    overrides = [{"plannable_type": "assignment", "plannable_id": 5, "assignment_id": 5, "marked_complete": True}]
    assert completed_assignment_ids(overrides) == {5}


def test_quiz_override_uses_underlying_assignment_id():
    overrides = [{"plannable_type": "quiz", "plannable_id": 900, "assignment_id": 12, "marked_complete": True}]
    assert completed_assignment_ids(overrides) == {12}


def test_assignment_override_without_assignment_id_falls_back_to_plannable_id():
    overrides = [{"plannable_type": "assignment", "plannable_id": 5, "marked_complete": True}]
    assert completed_assignment_ids(overrides) == {5}


def test_unchecked_dismissed_or_deleted_overrides_are_ignored():
    overrides = [
        {"plannable_type": "assignment", "assignment_id": 1, "marked_complete": False},
        {"plannable_type": "assignment", "assignment_id": 2, "marked_complete": False, "dismissed": True},
        {"plannable_type": "assignment", "assignment_id": 3, "marked_complete": True, "workflow_state": "deleted"},
        {"plannable_type": "assignment", "assignment_id": 4, "marked_complete": True, "deleted_at": "2026-09-01T00:00:00Z"},
        {"plannable_type": "planner_note", "plannable_id": 6, "marked_complete": True},
    ]
    assert completed_assignment_ids(overrides) == set()

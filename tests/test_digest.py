"""
Tests for the filtering/bucketing logic in src/digest.py, using mock
Canvas JSON — no live API access needed. Run with:

    pip install -r requirements.txt -r requirements-dev.txt
    pytest
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.digest import build_digest, format_notification_text

TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 8, 25, 7, 0, tzinfo=TZ)  # a Tuesday, 7 AM


def _assignment(
    name,
    due_at,
    course_name="Test Course",
    course_id=1,
    submission_state=None,
    submission_types=None,
    points=100,
):
    return {
        "name": name,
        "due_at": due_at,
        "_course_name": course_name,
        "_course_id": course_id,
        "html_url": f"https://canvas.example.com/courses/{course_id}/assignments/1",
        "points_possible": points,
        "submission_types": submission_types or ["online_upload"],
        "submission": {"workflow_state": submission_state} if submission_state else None,
    }


def test_due_today_bucket():
    raw = [_assignment("Essay 2", "2026-08-25T23:59:00Z")]
    digest = build_digest(raw, now=NOW)
    assert len(digest.due_today) == 1
    assert digest.due_today[0].title == "Essay 2"
    assert not digest.overdue
    assert not digest.coming_up


def test_coming_up_within_lookahead():
    raw = [_assignment("Problem Set 4", "2026-08-29T23:59:00Z")]  # 4 days out
    digest = build_digest(raw, lookahead_days=7, now=NOW)
    assert len(digest.coming_up) == 1
    assert not digest.due_today


def test_outside_lookahead_is_excluded():
    raw = [_assignment("Final Project", "2026-10-01T23:59:00Z")]
    digest = build_digest(raw, lookahead_days=7, now=NOW)
    assert digest.is_empty


def test_overdue_bucket_within_lookback():
    raw = [_assignment("Quiz 3", "2026-08-24T23:59:00Z")]  # 1 day ago
    digest = build_digest(raw, overdue_lookback_days=3, now=NOW)
    assert len(digest.overdue) == 1


def test_old_overdue_beyond_lookback_is_dropped():
    raw = [_assignment("Ancient Homework", "2026-08-01T23:59:00Z")]
    digest = build_digest(raw, overdue_lookback_days=3, now=NOW)
    assert digest.is_empty


def test_submitted_assignment_is_excluded():
    raw = [_assignment("Lab Report", "2026-08-25T23:59:00Z", submission_state="submitted")]
    digest = build_digest(raw, now=NOW)
    assert digest.is_empty


def test_graded_assignment_is_excluded():
    raw = [_assignment("Quiz 1", "2026-08-25T23:59:00Z", submission_state="graded")]
    digest = build_digest(raw, now=NOW)
    assert digest.is_empty


def test_no_due_date_is_excluded():
    raw = [_assignment("Reading (no deadline)", None)]
    digest = build_digest(raw, now=NOW)
    assert digest.is_empty


def test_quiz_kind_is_detected():
    raw = [_assignment("Midterm", "2026-08-25T23:59:00Z", submission_types=["online_quiz"])]
    digest = build_digest(raw, now=NOW)
    assert digest.due_today[0].kind == "quiz"


def test_notification_text_is_a_brief_summary_with_link():
    raw = [
        _assignment("Late HW", "2026-08-24T23:59:00Z"),
        _assignment("Today's Quiz", "2026-08-25T23:59:00Z", submission_types=["online_quiz"]),
    ]
    digest = build_digest(raw, now=NOW)
    title, body = format_notification_text(digest, dashboard_url="https://example.github.io/repo/")
    assert "overdue" in title.lower()
    assert "1 overdue" in body
    assert "1 due today" in body
    # itemized bullets are gone — this is a summary, not a list
    assert "Late HW" not in body
    assert "Today's Quiz" not in body
    assert body.strip().endswith("https://example.github.io/repo/")


def test_notification_text_flags_conflicts():
    raw = [_assignment("Essay 2", "2026-08-25T23:59:00Z")]
    digest = build_digest(raw, now=NOW)
    digest.due_today[0].conflict = True
    _, body = format_notification_text(digest)
    assert "1 conflicting due date" in body


def test_empty_digest_notification_is_friendly():
    digest = build_digest([], now=NOW)
    title, body = format_notification_text(digest, dashboard_url="https://example.github.io/repo/")
    assert "Nothing" in body
    assert body.strip().endswith("https://example.github.io/repo/")

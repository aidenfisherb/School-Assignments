"""
Tests for src/syllabus_parser.py's pure text/matching logic. No real PDF
or docx files are used — `extract_text`'s two format-specific branches are
thin I/O wrappers and are the one intentionally untested edge, consistent
with keeping all the real logic pure and testable with plain strings.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.syllabus_parser import match_course_key, parse_syllabus_text

TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 9, 1, 7, 0, tzinfo=TZ)


def test_month_name_date_is_parsed():
    items = parse_syllabus_text("Homework 3 is due September 10.", default_year=2026, now=NOW)
    assert len(items) == 1
    assert "Homework 3" in items[0].title
    assert items[0].due_at.month == 9
    assert items[0].due_at.day == 10


def test_numeric_date_is_parsed():
    items = parse_syllabus_text("Quiz 2 - 9/17", default_year=2026, now=NOW)
    assert len(items) == 1
    assert items[0].due_at.month == 9
    assert items[0].due_at.day == 17


def test_undated_year_rolls_over_when_far_in_the_past():
    # "January 15" with default_year=2026 parses to Jan 2026, which is
    # >200 days before NOW (Sept 2026) -- assumed to mean Jan 2027 instead
    # (e.g. a Fall-semester syllabus listing a January final exam date).
    items = parse_syllabus_text("Final exam on January 15.", default_year=2026, now=NOW)
    assert len(items) == 1
    assert items[0].due_at.year == 2027
    assert items[0].due_at.month == 1


def test_explicit_year_is_not_rolled_over():
    items = parse_syllabus_text("Final exam on January 15, 2026.", default_year=2026, now=NOW)
    assert len(items) == 1
    assert items[0].due_at.year == 2026


def test_line_with_no_date_is_dropped():
    items = parse_syllabus_text("This course covers introductory topics in cybersecurity.", default_year=2026, now=NOW)
    assert items == []


def test_leading_noise_is_stripped_from_title():
    items = parse_syllabus_text("Due: Reading Reflection 2 - September 5", default_year=2026, now=NOW)
    assert len(items) == 1
    assert items[0].title.lower().startswith("reading reflection")


def test_multiple_dated_lines_all_parsed():
    text = "Homework 1 due Sept 3.\nHomework 2 due Sept 10.\nHomework 3 due Sept 17."
    items = parse_syllabus_text(text, default_year=2026, now=NOW)
    assert len(items) == 3


def test_match_course_key_by_course_code():
    courses = [{"id": 1, "course_code": "COSC240.01", "name": "Introduction to Cybersecurity"}]
    assert match_course_key("cosc240", courses) == 1
    assert match_course_key("COSC240", courses) == 1


def test_match_course_key_by_name_fallback():
    courses = [{"id": 2, "course_code": "SOA200.W06", "name": "Arts in Society"}]
    assert match_course_key("artsinsociety", courses) == 2


def test_match_course_key_no_match_returns_none():
    courses = [{"id": 1, "course_code": "COSC240.01", "name": "Introduction to Cybersecurity"}]
    assert match_course_key("MATH101", courses) is None


def test_match_course_key_empty_folder_name_returns_none():
    courses = [{"id": 1, "course_code": "COSC240.01", "name": "Introduction to Cybersecurity"}]
    assert match_course_key("___", courses) is None

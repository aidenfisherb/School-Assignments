"""
Extracts candidate assignment/due-date pairs from uploaded syllabus files.

Syllabi live in syllabi/<COURSE_KEY>/*.{pdf,docx}, one folder per course.
COURSE_KEY is matched against the live Canvas course list (case-insensitive,
substring either direction) so it survives semester rollover automatically —
nothing here hardcodes a course id or term.

Extraction is a best-effort heuristic, not a guarantee: syllabi are prose,
and every professor formats dates differently. Each syllabus-derived item
is later reconciled against Canvas in merge.py, and a disagreement between
the two gets flagged rather than silently resolved.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from dateutil import parser as dateutil_parser
from docx import Document
from pypdf import PdfReader

from .digest import LOCAL_TZ, DigestItem

logger = logging.getLogger(__name__)

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_RE = re.compile(
    rf"""
    (?P<month_name>{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?)
    |
    (?P<numeric>\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?)
    """,
    re.IGNORECASE | re.VERBOSE,
)
_HAS_YEAR_RE = re.compile(r"\d{4}")
_LEADING_NOISE_RE = re.compile(r"^[\s\-–—•*]*(?:\d+[.)]|due:?|deadline:?)?\s*", re.IGNORECASE)
# Connector words directly before a date ("is due September 2", "due on",
# "no later than") that should go with the date, not stay in the title.
_TRAILING_CONNECTOR_RE = re.compile(
    r"\s*(?:is\s+)?(?:due|on|by|no later than|before|deadline)\s*$", re.IGNORECASE
)

_QUIZ_WORDS = ("quiz", "exam", "test", "midterm", "final")
_DISCUSSION_WORDS = ("discussion",)


@dataclass
class SyllabusItem:
    title: str
    due_at: datetime  # timezone-aware, LOCAL_TZ


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def match_course_key(folder_name: str, courses: list[dict]) -> int | None:
    """Matches a syllabi/<folder_name> against the live Canvas course list."""
    key = _normalize(folder_name)
    if not key:
        return None
    for course in courses:
        code = _normalize(course.get("course_code") or "")
        if code and (key in code or code in key):
            return course.get("id")
    for course in courses:
        name = _normalize(course.get("name") or "")
        if name and (key in name or name in key):
            return course.get("id")
    return None


def discover_syllabus_files(root: Path) -> dict[str, list[Path]]:
    """Maps each immediate subfolder of `root` to its .pdf/.docx files."""
    if not root.is_dir():
        return {}
    manifest: dict[str, list[Path]] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        files = sorted(
            p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".docx")
        )
        if files:
            manifest[folder.name] = files
    return manifest


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise ValueError(f"Unsupported syllabus file type: {path}")


def _split_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        if len(raw_line) > 150:
            lines.extend(part.strip() for part in raw_line.split(". ") if part.strip())
        else:
            lines.append(raw_line)
    return lines


def _guess_kind(title: str) -> str:
    lowered = title.lower()
    if any(w in lowered for w in _QUIZ_WORDS):
        return "quiz"
    if any(w in lowered for w in _DISCUSSION_WORDS):
        return "discussion"
    return "assignment"


def parse_syllabus_text(text: str, default_year: int, now: datetime | None = None) -> list[SyllabusItem]:
    """Pure text -> [SyllabusItem]. No file I/O, unit-testable with plain strings."""
    now = now or datetime.now(tz=LOCAL_TZ)
    items: list[SyllabusItem] = []

    for line in _split_lines(text):
        match = _DATE_RE.search(line)
        if not match:
            continue
        date_str = match.group(0)

        try:
            parsed = dateutil_parser.parse(date_str, default=datetime(default_year, 1, 1))
        except (ValueError, OverflowError):
            continue

        parsed = parsed.replace(tzinfo=LOCAL_TZ)
        if not _HAS_YEAR_RE.search(date_str) and (now - parsed) > timedelta(days=200):
            parsed = parsed.replace(year=parsed.year + 1)

        before = _TRAILING_CONNECTOR_RE.sub("", line[: match.start()])
        after = line[match.end():].lstrip(" .,-–—:;")
        title = f"{before} {after}".strip() if before and after else (before or after).strip()
        title = _LEADING_NOISE_RE.sub("", title).strip(" -–—:•").strip()
        title = re.sub(r"\s{2,}", " ", title)
        if not title:
            continue

        items.append(SyllabusItem(title=title, due_at=parsed))

    return items


def parse_all(manifest: dict[str, list[Path]], courses: list[dict]) -> list[DigestItem]:
    """Impure orchestrator: matches folders to courses, extracts, parses."""
    now = datetime.now(tz=LOCAL_TZ)
    results: list[DigestItem] = []

    for folder_name, paths in manifest.items():
        course_id = match_course_key(folder_name, courses)
        if course_id is None:
            logger.warning("No Canvas course matches syllabus folder %r - skipping.", folder_name)
            continue
        course = next(c for c in courses if c.get("id") == course_id)
        course_name = course.get("name") or course.get("course_code") or f"Course {course_id}"

        for path in paths:
            try:
                text = extract_text(path)
                parsed_items = parse_syllabus_text(text, default_year=now.year, now=now)
            except Exception:
                logger.warning("Failed to parse syllabus file %s - skipping.", path, exc_info=True)
                continue

            for item in parsed_items:
                results.append(
                    DigestItem(
                        course_name=course_name,
                        title=item.title,
                        due_at=item.due_at,
                        html_url="",
                        points_possible=None,
                        kind=_guess_kind(item.title),
                        source="Syllabus",
                    )
                )

    return results

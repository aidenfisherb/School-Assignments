"""
Turns raw Canvas assignment JSON into the small, student-relevant digest
this project actually cares about: what's overdue, what's due today, and
what's coming up soon — nothing already turned in, nothing ungraded
busywork Canvas doesn't even attach a due date to, and no announcements
(those were never fetched in the first place).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Chicago")

# Submission states that mean "the student already handled this" —
# once Canvas has a submission in one of these states, it drops out of
# the digest even if the due date is still in range.
_DONE_STATES = {"submitted", "graded"}


@dataclass
class DigestItem:
    course_name: str
    title: str
    due_at: datetime  # timezone-aware, America/Chicago
    html_url: str
    points_possible: float | None
    kind: str  # "assignment" | "quiz" | "discussion"
    source: str = "Canvas"  # "Canvas" | "Syllabus"
    conflict: bool = False  # True when Canvas and a syllabus disagree on this assignment
    has_time: bool = True  # False for syllabus items that list a date but no time


def _parse_due_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # Canvas emits e.g. "2026-08-25T23:59:00Z"; fromisoformat wants an
    # explicit offset rather than a bare "Z".
    iso = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return dt.astimezone(LOCAL_TZ)


def _fmt_time(dt: datetime) -> str:
    """12-hour clock without a leading zero, e.g. '9:05 AM'.

    strftime's '%-I' does this on Linux/macOS but raises ValueError on
    Windows (not a glibc extension there), so the hour is computed by hand.
    """
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.strftime('%M %p')}"


def _fmt_date_short(dt: datetime) -> str:
    """Weekday + numeric month/day without leading zeros, e.g. 'Tue 8/5'."""
    return f"{dt.strftime('%a')} {dt.month}/{dt.day}"


def _infer_kind(assignment: dict) -> str:
    submission_types = assignment.get("submission_types") or []
    if "online_quiz" in submission_types or assignment.get("is_quiz_assignment"):
        return "quiz"
    if "discussion_topic" in submission_types:
        return "discussion"
    return "assignment"


def _is_already_handled(assignment: dict) -> bool:
    submission = assignment.get("submission") or {}
    return submission.get("workflow_state") in _DONE_STATES


def _to_digest_item(assignment: dict) -> DigestItem | None:
    due_at = _parse_due_at(assignment.get("due_at"))
    if due_at is None:
        return None
    return DigestItem(
        course_name=assignment.get("_course_name", "Unknown course"),
        title=assignment.get("name", "Untitled assignment"),
        due_at=due_at,
        html_url=assignment.get("html_url", ""),
        points_possible=assignment.get("points_possible"),
        kind=_infer_kind(assignment),
        source="Canvas",
    )


@dataclass
class Digest:
    generated_at: datetime
    overdue: list[DigestItem]
    due_today: list[DigestItem]
    coming_up: list[DigestItem]  # after today, within lookahead_days

    @property
    def is_empty(self) -> bool:
        return not (self.overdue or self.due_today or self.coming_up)


def bucket_items(
    items: list[DigestItem],
    lookahead_days: int = 7,
    overdue_lookback_days: int = 3,
    now: datetime | None = None,
) -> Digest:
    now = (now or datetime.now(tz=LOCAL_TZ)).astimezone(LOCAL_TZ)
    today: date = now.date()
    lookahead_end = today + timedelta(days=lookahead_days)
    overdue_start = today - timedelta(days=overdue_lookback_days)

    overdue: list[DigestItem] = []
    due_today: list[DigestItem] = []
    coming_up: list[DigestItem] = []

    for item in items:
        due_date = item.due_at.date()

        if due_date < today:
            if due_date >= overdue_start:
                overdue.append(item)
            continue
        if due_date == today:
            due_today.append(item)
        elif due_date <= lookahead_end:
            coming_up.append(item)

    overdue.sort(key=lambda i: i.due_at)
    due_today.sort(key=lambda i: i.due_at)
    coming_up.sort(key=lambda i: i.due_at)

    return Digest(generated_at=now, overdue=overdue, due_today=due_today, coming_up=coming_up)


def build_digest(
    raw_assignments: list[dict],
    lookahead_days: int = 7,
    overdue_lookback_days: int = 3,
    now: datetime | None = None,
    syllabus_items: list[DigestItem] | None = None,
) -> Digest:
    canvas_items: list[DigestItem] = []
    handled: list[tuple[str, str]] = []

    for raw in raw_assignments:
        if _is_already_handled(raw):
            # Track (course, title) for already-submitted/graded work so a
            # syllabus-derived duplicate of it can be suppressed below too —
            # otherwise something you've already turned in on Canvas could
            # resurface as a bogus "still outstanding" syllabus-only item.
            handled.append((raw.get("_course_name", "Unknown course"), raw.get("name", "")))
            continue
        item = _to_digest_item(raw)
        if item is None:
            continue
        canvas_items.append(item)

    if syllabus_items:
        from . import merge

        canvas_items = merge.merge_items(canvas_items, syllabus_items, handled)

    return bucket_items(canvas_items, lookahead_days, overdue_lookback_days, now)


def format_notification_text(digest: Digest, dashboard_url: str = "") -> tuple[str, str]:
    """Returns (title, body) sized for a phone push notification.

    Kept brief on purpose: a full itemized list belongs on the dashboard,
    not a phone push. The body is just a one-line summary, an optional
    conflict callout, and a link.
    """
    if digest.is_empty:
        body = "Nothing due today or overdue. Coming up: nothing in the next few days either."
        if dashboard_url:
            body = f"{body}\n{dashboard_url}"
        return "Canvas Digest", body

    parts: list[str] = []
    if digest.overdue:
        parts.append(f"{len(digest.overdue)} overdue")
    if digest.due_today:
        parts.append(f"{len(digest.due_today)} due today")
    if digest.coming_up:
        parts.append(f"{len(digest.coming_up)} coming up")

    lines = [", ".join(parts)]

    conflicts = sum(
        1 for bucket in (digest.overdue, digest.due_today, digest.coming_up) for i in bucket if i.conflict
    )
    if conflicts:
        lines.append(f"{conflicts} conflicting due date{'s' if conflicts != 1 else ''} - check dashboard")
    if dashboard_url:
        lines.append(dashboard_url)

    # ntfy sends this as an HTTP header value, which http.client encodes as
    # latin-1 — non-ASCII characters (em dashes, emoji) raise UnicodeEncodeError
    # and crash the push, so this string has to stay plain ASCII.
    title = "Canvas Digest"
    if digest.overdue:
        title = f"{len(digest.overdue)} overdue - Canvas Digest"
    elif digest.due_today:
        title = f"{len(digest.due_today)} due today - Canvas Digest"

    return title, "\n".join(lines)

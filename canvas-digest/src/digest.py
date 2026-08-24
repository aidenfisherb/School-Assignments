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


def build_digest(
    raw_assignments: list[dict],
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

    for raw in raw_assignments:
        if _is_already_handled(raw):
            continue
        item = _to_digest_item(raw)
        if item is None:
            continue

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


def format_notification_text(digest: Digest) -> tuple[str, str]:
    """Returns (title, body) sized for a phone push notification."""
    if digest.is_empty:
        return ("Canvas Digest", "Nothing due today or overdue. Coming up: nothing in the next few days either.")

    parts: list[str] = []
    if digest.overdue:
        parts.append(f"{len(digest.overdue)} OVERDUE:")
        parts.extend(f"  • {i.course_name}: {i.title}" for i in digest.overdue)
    if digest.due_today:
        parts.append(f"Due today ({len(digest.due_today)}):")
        parts.extend(
            f"  • {i.course_name}: {i.title} ({i.due_at.strftime('%-I:%M %p')})"
            for i in digest.due_today
        )
    if digest.coming_up:
        parts.append(f"Coming up ({len(digest.coming_up)}):")
        parts.extend(
            f"  • {i.course_name}: {i.title} ({i.due_at.strftime('%a %-m/%-d')})"
            for i in digest.coming_up
        )

    title = "Canvas Digest"
    if digest.overdue:
        title = f"⚠️ {len(digest.overdue)} overdue — Canvas Digest"
    elif digest.due_today:
        title = f"{len(digest.due_today)} due today — Canvas Digest"

    return title, "\n".join(parts)

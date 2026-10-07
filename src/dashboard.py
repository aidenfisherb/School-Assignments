"""
Renders the Digest into self-contained HTML pages for GitHub Pages. No
build step, no external JS — just clean static HTML+CSS that looks right
in light and dark mode. A shared navbar links the two pages together.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from .digest import Digest, DigestItem, _fmt_date_short, _fmt_time
from .syllabus_extractor import EXTRACTED_SUFFIX, FileStatus

_KIND_LABEL = {"quiz": "Quiz/Test", "discussion": "Discussion", "assignment": "Assignment"}

_BASE_CSS = """
  :root {
    --bg: #f7f7f8; --surface: #ffffff; --border: #e3e3e6;
    --text: #1c1c1f; --text-muted: #6b6b73;
    --accent: #4f46e5; --overdue: #dc2626; --overdue-bg: #fef2f2;
    --today: #d97706; --today-bg: #fffbeb;
    --quiz: #7c3aed; --discussion: #0891b2; --assignment: #4f46e5;
    --src-canvas: #0891b2; --src-syllabus: #7c3aed; --conflict: #b45309;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #131316; --surface: #1c1c20; --border: #2c2c31;
      --text: #f2f2f3; --text-muted: #9a9aa2;
      --accent: #818cf8; --overdue: #f87171; --overdue-bg: #2a1414;
      --today: #fbbf24; --today-bg: #2a2110;
      --quiz: #a78bfa; --discussion: #22d3ee; --assignment: #818cf8;
      --src-canvas: #22d3ee; --src-syllabus: #a78bfa; --conflict: #fbbf24;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2.5rem 1.25rem 4rem; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  }
  .wrap { max-width: 640px; margin: 0 auto; }
  header { margin-bottom: 1.25rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.35rem; }
  .updated { color: var(--text-muted); font-size: 0.875rem; }
  .navbar {
    display: flex; gap: 1rem; margin-bottom: 1.5rem; padding-bottom: 1rem;
    border-bottom: 1px solid var(--border); font-size: 0.875rem;
  }
  .navlink { color: var(--text-muted); text-decoration: none; font-weight: 600; }
  .navlink.active { color: var(--accent); }
  .section {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.25rem 1.25rem 0.5rem; margin-bottom: 1rem;
  }
  .section-overdue { border-color: var(--overdue); }
  .section-today { border-color: var(--today); }
  h2 {
    font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--text-muted); margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;
  }
  h3 { font-size: 0.95rem; margin: 0 0 0.5rem; }
  .count {
    background: var(--border); color: var(--text); border-radius: 999px;
    font-size: 0.75rem; padding: 0.05rem 0.5rem; text-transform: none; letter-spacing: normal;
  }
  .empty { color: var(--text-muted); font-size: 0.9rem; margin: 0 0 0.75rem; }
  .hint { color: var(--text-muted); font-size: 0.8rem; margin: 0.3rem 0 0.75rem; }
  .hint-problem { color: var(--conflict); }
  .item-list { list-style: none; margin: 0; padding: 0; }
  .item { padding: 0.75rem 0; border-top: 1px solid var(--border); }
  .item:first-child { border-top: none; }
  .item-main { display: flex; flex-direction: column; gap: 0.1rem; }
  .item-title { font-weight: 600; color: var(--text); text-decoration: none; }
  .item-course { color: var(--text-muted); font-size: 0.825rem; }
  .item-meta { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.35rem; font-size: 0.8rem; flex-wrap: wrap; }
  .item-due { color: var(--text-muted); }
  .item-points { color: var(--text-muted); }
  .tag {
    font-size: 0.7rem; font-weight: 600; padding: 0.1rem 0.45rem; border-radius: 6px; color: #fff;
  }
  .tag-quiz { background: var(--quiz); }
  .tag-discussion { background: var(--discussion); }
  .tag-assignment { background: var(--assignment); }
  .tag-src-canvas { background: var(--src-canvas); }
  .tag-src-syllabus { background: var(--src-syllabus); }
  .tag-conflict { background: var(--conflict); }
  .course-block { padding: 0.9rem 0; border-top: 1px solid var(--border); }
  .course-block:first-child { border-top: none; }
  .file-row { display: flex; align-items: center; gap: 0.6rem; font-size: 0.875rem; margin: 0.3rem 0; }
  .file-row a { color: var(--accent); text-decoration: none; }
  .file-row .sep { color: var(--text-muted); }
  footer { text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; }
  footer a { color: inherit; }
"""


def _fmt_full(dt: datetime) -> str:
    """e.g. 'Tuesday, August 5 — 7:00 AM CDT', without relying on '%-d'."""
    return f"{dt.strftime('%A, %B')} {dt.day} — {_fmt_time(dt)} {dt.strftime('%Z')}"


def _navbar(active: str) -> str:
    def link(href: str, label: str, key: str) -> str:
        cls = "navlink active" if key == active else "navlink"
        return f'<a class="{cls}" href="{href}">{escape(label)}</a>'

    return f"""
    <nav class="navbar">
      {link("index.html", "Dashboard", "dashboard")}
      {link("syllabuses.html", "Syllabi", "syllabuses")}
    </nav>"""


def _page_shell(page_title: str, active_nav: str, body_html: str, repo_url: str) -> str:
    footer_link = (
        f'<a href="{escape(repo_url)}">source</a>' if repo_url else "built with Canvas API + GitHub Actions"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(page_title)}</title>
<style>{_BASE_CSS}</style>
</head>
<body>
  <div class="wrap">
    {_navbar(active_nav)}
    {body_html}
    <footer>Generated automatically every weekday morning &middot; {footer_link}</footer>
  </div>
</body>
</html>
"""


def _item_row(item: DigestItem, *, show_date: bool) -> str:
    if not item.has_time:
        when = _fmt_date_short(item.due_at) if show_date else "no time listed"
    elif show_date:
        when = f"{_fmt_date_short(item.due_at)}, {_fmt_time(item.due_at)}"
    else:
        when = _fmt_time(item.due_at)
    points = f"{item.points_possible:g} pts" if item.points_possible not in (None, 0) else ""
    src_class = "tag-src-canvas" if item.source == "Canvas" else "tag-src-syllabus"
    conflict_chip = '<span class="tag tag-conflict">Conflicting</span>' if item.conflict else ""
    return f"""
    <li class="item">
      <div class="item-main">
        <span class="item-title">{escape(item.title)}</span>
        <span class="item-course">{escape(item.course_name)}</span>
      </div>
      <div class="item-meta">
        <span class="tag tag-{item.kind}">{_KIND_LABEL.get(item.kind, "Assignment")}</span>
        <span class="tag {src_class}">{escape(item.source)}</span>
        {conflict_chip}
        <span class="item-due">{escape(when)}</span>
        {f'<span class="item-points">{points}</span>' if points else ""}
      </div>
    </li>"""


def _section(
    title: str, items: list[DigestItem], *, empty_text: str, show_date: bool, tone: str = "", hint: str = ""
) -> str:
    if not items:
        return f"""
    <section class="section">
      <h2>{escape(title)}</h2>
      <p class="empty">{escape(empty_text)}</p>
    </section>"""
    rows = "\n".join(_item_row(i, show_date=show_date) for i in items)
    return f"""
    <section class="section{' section-' + tone if tone else ''}">
      <h2>{escape(title)} <span class="count">{len(items)}</span></h2>
      <ul class="item-list">{rows}
      </ul>{f'<p class="hint">{escape(hint)}</p>' if hint else ""}
    </section>"""


def render_dashboard(digest: Digest, repo_url: str = "") -> str:
    generated = _fmt_full(digest.generated_at)

    overdue_html = _section(
        "Overdue",
        digest.overdue,
        empty_text="Nothing overdue.",
        show_date=True,
        tone="overdue",
        hint="Nothing to turn in (e.g. done in class)? Mark it done in Canvas's To Do list "
        "and it drops off here on the next run.",
    )
    today_html = _section(
        "Due Today", digest.due_today, empty_text="Nothing due today.", show_date=False, tone="today"
    )
    upcoming_html = _section(
        "Coming Up", digest.coming_up, empty_text="Nothing on the horizon yet.", show_date=True
    )

    body = f"""
    <header>
      <h1>Canvas Digest</h1>
      <div class="updated">Last updated {escape(generated)}</div>
    </header>
    {overdue_html}
    {today_html}
    {upcoming_html}"""

    return _page_shell("Canvas Digest", "dashboard", body, repo_url)


def _status_text(status: FileStatus) -> tuple[str, bool]:
    """(text, is_problem) describing one syllabus file's extraction state."""
    if status.state in ("cached", "extracted"):
        n = status.item_count
        return f"{n} dated item{'s' if n != 1 else ''} found", False
    if status.state == "pending":
        return "not extracted yet - GEMINI_API_KEY is not set", True
    if status.state == "unmatched":
        return "folder name doesn't match any course", True
    return f"extraction failed: {status.detail}", True


def render_syllabuses_page(
    courses: list[dict],
    tracked_by_course: dict[int, tuple[str, list[FileStatus]]],
    unmatched: list[FileStatus] | None = None,
    *,
    repo_url: str = "",
    branch: str = "dev",
) -> str:
    """
    Lists which courses have a tracked syllabus, how extraction went for
    each file, and which courses have none. All add/view/edit/delete
    actions link out to GitHub's own file UI — this page only reads what
    `main.py` already built, with no write capability of its own.
    """

    def file_url(action: str, folder: str, fname: str) -> str:
        return f"{repo_url}/{action}/{branch}/syllabi/{folder}/{fname}" if repo_url else "#"

    blocks: list[str] = []
    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name") or course.get("course_code") or f"Course {course_id}"
        tracked = tracked_by_course.get(course_id)

        if tracked:
            folder, statuses = tracked
            rows = []
            for status in statuses:
                fname = status.filename
                text, is_problem = _status_text(status)
                review_link = ""
                if status.state in ("cached", "extracted"):
                    json_name = fname + EXTRACTED_SUFFIX
                    review_link = (
                        f'<span class="sep">&middot;</span>'
                        f'<a href="{escape(file_url("edit", folder, json_name))}">review dates</a>'
                    )
                rows.append(
                    f'<div class="file-row">'
                    f'<a href="{escape(file_url("blob", folder, fname))}">{escape(fname)}</a>'
                    f"{review_link}"
                    f'<span class="sep">&middot;</span>'
                    f'<a href="{escape(file_url("delete", folder, fname))}">remove</a>'
                    f"</div>"
                    f'<p class="hint{" hint-problem" if is_problem else ""}">{escape(text)}</p>'
                )
            upload_url = f"{repo_url}/upload/{branch}/syllabi/{folder}" if repo_url else "#"
            rows.append(f'<div class="file-row"><a href="{escape(upload_url)}">+ add another file</a></div>')
            body = "\n".join(rows)
        else:
            suggested_key = "".join(ch for ch in (course.get("course_code") or "") if ch.isalnum())[:24]
            suggested_key = suggested_key or "".join(ch for ch in course_name if ch.isalnum())[:24]
            upload_url = f"{repo_url}/upload/{branch}/syllabi/{suggested_key}" if repo_url else "#"
            body = (
                f'<p class="empty">No syllabus uploaded yet.</p>'
                f'<div class="file-row"><a href="{escape(upload_url)}">+ upload syllabus</a></div>'
                f'<p class="hint">Or upload manually with path '
                f'<code>syllabi/{escape(suggested_key)}/yourfile.pdf</code></p>'
            )

        blocks.append(
            f"""
    <div class="course-block">
      <h3>{escape(course_name)}</h3>
      {body}
    </div>"""
        )

    courses_html = "\n".join(blocks) if blocks else '<p class="empty">No active courses found.</p>'

    unmatched_html = ""
    if unmatched:
        rows = "\n".join(
            f'<div class="file-row"><a href="{escape(file_url("blob", s.folder, s.filename))}">'
            f"syllabi/{escape(s.folder)}/{escape(s.filename)}</a></div>"
            for s in unmatched
        )
        unmatched_html = f"""
    <section class="section">
      <h2>Not matched to a course</h2>
      <p class="hint hint-problem">These folder names don't match any favorited course's code or name, so they're ignored.</p>
      {rows}
    </section>"""

    body = f"""
    <header>
      <h1>Syllabi</h1>
      <div class="updated">Dated items are pulled from each file once and merged into the dashboard. Use "review dates" to correct anything misread.</div>
    </header>
    <section class="section">
      {courses_html}
    </section>{unmatched_html}"""

    return _page_shell("Syllabi — Canvas Digest", "syllabuses", body, repo_url)

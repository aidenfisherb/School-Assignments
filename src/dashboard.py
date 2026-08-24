"""
Renders the Digest into a single self-contained HTML page for GitHub
Pages. No build step, no external JS — just clean static HTML+CSS that
looks right in light and dark mode.
"""

from __future__ import annotations

from html import escape

from datetime import datetime

from .digest import Digest, DigestItem, _fmt_date_short, _fmt_time

_KIND_LABEL = {"quiz": "Quiz/Test", "discussion": "Discussion", "assignment": "Assignment"}


def _fmt_full(dt: datetime) -> str:
    """e.g. 'Tuesday, August 5 — 7:00 AM CDT', without relying on '%-d'."""
    return f"{dt.strftime('%A, %B')} {dt.day} — {_fmt_time(dt)} {dt.strftime('%Z')}"


def _item_row(item: DigestItem, *, show_date: bool) -> str:
    when = f"{_fmt_date_short(item.due_at)}, {_fmt_time(item.due_at)}" if show_date else _fmt_time(item.due_at)
    points = f"{item.points_possible:g} pts" if item.points_possible not in (None, 0) else ""
    link_open, link_close = (f'<a href="{escape(item.html_url)}">', "</a>") if item.html_url else ("", "")
    return f"""
    <li class="item">
      <div class="item-main">
        {link_open}<span class="item-title">{escape(item.title)}</span>{link_close}
        <span class="item-course">{escape(item.course_name)}</span>
      </div>
      <div class="item-meta">
        <span class="tag tag-{item.kind}">{_KIND_LABEL.get(item.kind, "Assignment")}</span>
        <span class="item-due">{escape(when)}</span>
        {f'<span class="item-points">{points}</span>' if points else ""}
      </div>
    </li>"""


def _section(title: str, items: list[DigestItem], *, empty_text: str, show_date: bool, tone: str = "") -> str:
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
      </ul>
    </section>"""


def render_dashboard(digest: Digest, repo_url: str = "") -> str:
    generated = _fmt_full(digest.generated_at)
    footer_link = (
        f'<a href="{escape(repo_url)}">source</a>' if repo_url else "built with Canvas API + GitHub Actions"
    )

    overdue_html = _section(
        "Overdue", digest.overdue, empty_text="Nothing overdue.", show_date=True, tone="overdue"
    )
    today_html = _section(
        "Due Today", digest.due_today, empty_text="Nothing due today.", show_date=False, tone="today"
    )
    upcoming_html = _section(
        "Coming Up", digest.coming_up, empty_text="Nothing on the horizon yet.", show_date=True
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canvas Digest</title>
<style>
  :root {{
    --bg: #f7f7f8; --surface: #ffffff; --border: #e3e3e6;
    --text: #1c1c1f; --text-muted: #6b6b73;
    --accent: #4f46e5; --overdue: #dc2626; --overdue-bg: #fef2f2;
    --today: #d97706; --today-bg: #fffbeb;
    --quiz: #7c3aed; --discussion: #0891b2; --assignment: #4f46e5;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #131316; --surface: #1c1c20; --border: #2c2c31;
      --text: #f2f2f3; --text-muted: #9a9aa2;
      --accent: #818cf8; --overdue: #f87171; --overdue-bg: #2a1414;
      --today: #fbbf24; --today-bg: #2a2110;
      --quiz: #a78bfa; --discussion: #22d3ee; --assignment: #818cf8;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2.5rem 1.25rem 4rem; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  }}
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  header {{ margin-bottom: 2rem; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 0.35rem; }}
  .updated {{ color: var(--text-muted); font-size: 0.875rem; }}
  .section {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.25rem 1.25rem 0.5rem; margin-bottom: 1rem;
  }}
  .section-overdue {{ border-color: var(--overdue); }}
  .section-today {{ border-color: var(--today); }}
  h2 {{
    font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--text-muted); margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;
  }}
  .count {{
    background: var(--border); color: var(--text); border-radius: 999px;
    font-size: 0.75rem; padding: 0.05rem 0.5rem; text-transform: none; letter-spacing: normal;
  }}
  .empty {{ color: var(--text-muted); font-size: 0.9rem; margin: 0 0 0.75rem; }}
  .item-list {{ list-style: none; margin: 0; padding: 0; }}
  .item {{ padding: 0.75rem 0; border-top: 1px solid var(--border); }}
  .item:first-child {{ border-top: none; }}
  .item-main {{ display: flex; flex-direction: column; gap: 0.1rem; }}
  .item-title {{ font-weight: 600; color: var(--text); text-decoration: none; }}
  a .item-title {{ color: var(--accent); }}
  .item-course {{ color: var(--text-muted); font-size: 0.825rem; }}
  .item-meta {{ display: flex; align-items: center; gap: 0.5rem; margin-top: 0.35rem; font-size: 0.8rem; }}
  .item-due {{ color: var(--text-muted); }}
  .item-points {{ color: var(--text-muted); }}
  .tag {{
    font-size: 0.7rem; font-weight: 600; padding: 0.1rem 0.45rem; border-radius: 6px; color: #fff;
  }}
  .tag-quiz {{ background: var(--quiz); }}
  .tag-discussion {{ background: var(--discussion); }}
  .tag-assignment {{ background: var(--assignment); }}
  footer {{ text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; }}
  footer a {{ color: inherit; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Canvas Digest</h1>
      <div class="updated">Last updated {escape(generated)}</div>
    </header>
    {overdue_html}
    {today_html}
    {upcoming_html}
    <footer>Generated automatically every weekday morning &middot; {footer_link}</footer>
  </div>
</body>
</html>
"""

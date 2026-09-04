"""
Entry point run by the GitHub Actions workflow every weekday morning.

Reads config from environment variables (set as GitHub Actions secrets /
repo variables — see SETUP.md), fetches Canvas assignments, builds the
digest, writes the dashboard HTML for GitHub Pages, and pushes a phone
notification via ntfy.sh.

Run locally for testing with:
    CANVAS_DOMAIN=... CANVAS_TOKEN=... NTFY_TOPIC=... python -m src.main
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import syllabus_parser
from .canvas_client import CanvasClient, CanvasError
from .digest import build_digest, format_notification_text
from .dashboard import render_dashboard, render_syllabuses_page
from .notify import send_ntfy


def _env(name: str, default: str | None = None) -> str | None:
    """Read an env var, falling back to `default` when unset OR blank.

    GitHub Actions substitutes an unset repo variable (`vars.X`) as an
    empty string rather than omitting it, so "set but blank" has to be
    treated the same as "unset" here or optional config like
    LOOKAHEAD_DAYS crashes int() on a fresh repo.
    """
    val = os.environ.get(name)
    if val is None:
        return default
    val = val.strip()
    return val if val else default


def _parse_exclude_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk:
            ids.add(int(chunk))
    return ids


def main() -> int:
    domain = _env("CANVAS_DOMAIN")
    token = _env("CANVAS_TOKEN")
    ntfy_topic = _env("NTFY_TOPIC")
    repo_url = _env("REPO_URL", "")
    repo_branch = _env("REPO_BRANCH", "dev")
    pages_url = _env("PAGES_URL", "")
    lookahead_days = int(_env("LOOKAHEAD_DAYS", "7"))
    exclude_ids = _parse_exclude_ids(_env("EXCLUDE_COURSE_IDS", ""))
    output_dir = Path(_env("OUTPUT_DIR", "docs"))
    syllabus_dir = Path(_env("SYLLABUS_DIR", "syllabi"))
    skip_notify = _env("SKIP_NOTIFY", "").lower() in ("1", "true", "yes")

    if not domain or not token:
        print("CANVAS_DOMAIN and CANVAS_TOKEN must be set.", file=sys.stderr)
        return 1

    client = CanvasClient(domain=domain, token=token)
    try:
        courses = client.get_favorite_courses()
        raw_assignments = client.get_all_assignments(exclude_course_ids=exclude_ids)
    except CanvasError as e:
        print(f"Canvas API error: {e}", file=sys.stderr)
        return 1

    manifest = syllabus_parser.discover_syllabus_files(syllabus_dir)
    syllabus_items = syllabus_parser.parse_all(manifest, courses)
    print(f"Found {len(syllabus_items)} syllabus-derived item(s) across {len(manifest)} tracked syllabus folder(s).")

    tracked_by_course: dict[int, tuple[str, list[str]]] = {}
    for folder_name, paths in manifest.items():
        course_id = syllabus_parser.match_course_key(folder_name, courses)
        if course_id is not None:
            tracked_by_course[course_id] = (folder_name, [p.name for p in paths])

    digest = build_digest(raw_assignments, lookahead_days=lookahead_days, syllabus_items=syllabus_items)

    # Dashboard — always written, even on a quiet day.
    output_dir.mkdir(parents=True, exist_ok=True)
    html = render_dashboard(digest, repo_url=repo_url)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote dashboard to {output_dir / 'index.html'}")

    syllabuses_html = render_syllabuses_page(courses, tracked_by_course, repo_url=repo_url, branch=repo_branch)
    (output_dir / "syllabuses.html").write_text(syllabuses_html, encoding="utf-8")
    print(f"Wrote syllabuses page to {output_dir / 'syllabuses.html'}")

    title, body = format_notification_text(digest, dashboard_url=pages_url)
    print(f"--- {title} ---\n{body}")

    if not skip_notify:
        if not ntfy_topic:
            print("NTFY_TOPIC not set — skipping push notification.", file=sys.stderr)
        else:
            try:
                send_ntfy(ntfy_topic, title, body)
                print("Push notification sent.")
            except Exception as e:
                # The dashboard above is already written correctly by this
                # point; a failed push (ntfy.sh outage, network blip, a
                # future encoding surprise) is a best-effort side channel
                # and must not take the whole run — and the Pages deploy
                # that depends on it succeeding — down with it.
                print(f"Push notification failed (dashboard was still updated): {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

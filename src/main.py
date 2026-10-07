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

import requests

from . import syllabus_extractor
from .canvas_client import CanvasClient, CanvasError, completed_assignment_ids
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
    gemini_api_key = _env("GEMINI_API_KEY")
    gemini_model = _env("GEMINI_MODEL", syllabus_extractor.DEFAULT_MODEL)

    if not domain or not token:
        print("CANVAS_DOMAIN and CANVAS_TOKEN must be set.", file=sys.stderr)
        return 1

    client = CanvasClient(domain=domain, token=token)
    try:
        courses = [c for c in client.get_favorite_courses() if c.get("id") not in exclude_ids]
        raw_assignments = client.get_all_assignments(courses)
    except CanvasError as e:
        print(f"Canvas API error: {e}", file=sys.stderr)
        return 1

    try:
        completed_ids = completed_assignment_ids(client.get_planner_overrides())
        print(f"{len(completed_ids)} assignment(s) marked done in Canvas's planner.")
    except (CanvasError, requests.RequestException) as e:
        # Losing "mark as done" for one run just shows a few extra items;
        # not worth failing the whole digest over.
        print(f"Couldn't read planner overrides, showing everything: {e}", file=sys.stderr)
        completed_ids = set()

    for removed in syllabus_extractor.remove_orphaned_extractions(syllabus_dir):
        print(f"Removed {removed} (its syllabus file was deleted).")

    extract_fn = None
    if gemini_api_key:
        extract_fn = syllabus_extractor.make_gemini_extractor(gemini_api_key, gemini_model)
    manifest = syllabus_extractor.discover_syllabus_files(syllabus_dir)
    syllabus_items, syllabus_statuses = syllabus_extractor.process_syllabi(
        manifest, courses, extract_fn=extract_fn
    )
    for s in syllabus_statuses:
        detail = f" ({s.detail})" if s.detail else ""
        print(f"Syllabus {s.folder}/{s.filename}: {s.state}, {s.item_count} item(s){detail}")

    tracked_by_course: dict[int, tuple[str, list[syllabus_extractor.FileStatus]]] = {}
    unmatched: list[syllabus_extractor.FileStatus] = []
    for folder_name in manifest:
        folder_statuses = [s for s in syllabus_statuses if s.folder == folder_name]
        course_id = syllabus_extractor.match_course_key(folder_name, courses)
        if course_id is None:
            unmatched.extend(folder_statuses)
        else:
            tracked_by_course[course_id] = (folder_name, folder_statuses)

    digest = build_digest(
        raw_assignments,
        lookahead_days=lookahead_days,
        syllabus_items=syllabus_items,
        completed_ids=completed_ids,
    )

    # Dashboard — always written, even on a quiet day.
    output_dir.mkdir(parents=True, exist_ok=True)
    html = render_dashboard(digest, repo_url=repo_url)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote dashboard to {output_dir / 'index.html'}")

    syllabuses_html = render_syllabuses_page(
        courses, tracked_by_course, unmatched, repo_url=repo_url, branch=repo_branch
    )
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

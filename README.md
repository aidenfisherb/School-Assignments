# Canvas Digest

A weekday-morning assignment tracker that pulls live due dates from
Canvas LMS, filters out everything that isn't actually actionable, and
delivers what's left two ways: a push notification and a small static
dashboard.

**Live example:** `https://<your-username>.github.io/<repo-name>/` (once deployed — see SETUP.md)

## What it does

Every weekday morning (scheduled for 6:17 AM Central, though GitHub
often starts scheduled runs late), a GitHub Actions workflow:

1. Calls the Canvas REST API to list your currently active courses.
2. Pulls every assignment (which in Canvas also covers graded quizzes,
   tests, and graded discussions) for each course, along with your
   submission status for each one.
3. Drops anything you've already submitted or that's already graded,
   anything with no due date, and anything outside the lookahead
   window — announcements are never even fetched, since they live on a
   separate Canvas endpoint this project doesn't touch.
4. Buckets what's left into **Overdue**, **Due Today**, and **Coming
   Up** (next 7 days by default).
5. Merges in anything extracted from uploaded syllabus files (see
   below), tagging each item **Canvas** or **Syllabus** so you know
   where it came from, collapsing exact duplicates, and flagging a
   **Conflicting** tag when the two sources disagree on a due date
   instead of silently picking one.
6. Renders a static dashboard (`docs/index.html`) and a syllabus
   management page (`docs/syllabuses.html`), linked by a navbar, and
   deploys both to GitHub Pages.
7. Sends a short push notification via [ntfy.sh](https://ntfy.sh) — a
   one-line summary and a link to the dashboard, not a full list.

No server to run, no database, no student-facing announcements or
noise — just what a student actually needs to see before class.

### Syllabus files

Canvas is sometimes incomplete (a professor forgets to set a due date)
or just wrong. Upload a syllabus PDF/docx per course to
`syllabi/<COURSE_KEY>/yourfile.pdf` (via GitHub's own web UI — no git
needed) and the workflow pulls the graded, dated items out of it.
`COURSE_KEY` just needs to match part of the course's Canvas code or
name (e.g. `syllabi/COSC240/...` for a course coded `COSC240.01`) —
matching happens fresh against your favorited courses each run, so it
survives semester rollover with no changes needed.

Extraction uses Google's Gemini API on its **free tier** (optional —
without a `GEMINI_API_KEY` the syllabus feature simply stays off).
PDFs are sent to the model as documents rather than scraped text, so
schedule tables keep their structure. Each file is read **once**: the
result is committed next to it as `<file>.extracted.json`, and every
later run reuses that file instead of calling the API again. That JSON
is also how you fix a misread date — edit it on GitHub and the
correction sticks until the syllabus itself is replaced.

A model reading a syllabus can still get something wrong, which is
what the Conflicting tag is for: it surfaces a disagreement between
Canvas and a syllabus instead of hiding it. The **Syllabi** page
(reachable from the dashboard's navbar) shows each course's files, how
many dated items were found, any extraction problems, and links to
review the extracted dates, remove a file, or add one — all through
GitHub's own file UI, so there's no custom upload form or backend to
maintain.

## Why it's built this way

- **No always-on infrastructure.** GitHub Actions' free tier runs the
  job on a schedule; there's nothing to host or keep alive.
- **Secrets never touch the codebase.** The Canvas token and ntfy topic
  are GitHub Actions secrets, injected as environment variables at run
  time only.
- **Scales to any number of classes with zero config changes.** Courses
  are auto-discovered from your active Canvas enrollments each run —
  add or drop a class in Canvas and the digest picks it up automatically
  next semester. An optional exclude list handles the rare case you
  want to hide a course (e.g. an audit) without unenrolling.
- **Tested without needing live credentials.** The filtering/bucketing
  logic in `src/digest.py` is pure and covered by `tests/test_digest.py`
  against mock Canvas JSON, so the core logic is verifiable in CI
  without ever calling the real API.

## Project layout

```
src/
  canvas_client.py    Canvas REST API wrapper (courses, assignments, pagination)
  digest.py           Filtering + bucketing (overdue / due today / coming up)
  syllabus_extractor.py  Extracts dated items from syllabus files via Gemini, cached as JSON
  merge.py            Reconciles Canvas items with syllabus items (dedup / conflict tagging)
  dashboard.py        Renders the digest into static HTML pages (dashboard + syllabi)
  notify.py           Sends the push notification via ntfy.sh
  main.py             Orchestrates the above; entry point for the workflow
tests/
  test_digest.py            Unit tests for filtering/bucketing/notification text
  test_merge.py             Unit tests for the dedup/conflict logic
  test_syllabus_extractor.py  Unit tests for course matching, caching, and conversion (model faked)
syllabi/
  <COURSE_KEY>/       One folder per course; drop a .pdf or .docx syllabus in here
                      (the workflow adds <file>.extracted.json beside it)
.github/workflows/
  daily-digest.yml   Cron schedule + GitHub Pages deploy; also rebuilds on syllabus changes
```

## Tech

Python 3.12, `requests`, `google-genai`, `python-docx`, GitHub Actions
(schedule + Pages deploy), ntfy.sh for push delivery, and Gemini's free
tier for syllabus extraction. No frameworks, nothing paid.

## Setup

See [SETUP.md](./SETUP.md) for the full walkthrough (Canvas token,
ntfy topic, GitHub secrets, enabling Pages).

## License

MIT — do whatever you want with it.

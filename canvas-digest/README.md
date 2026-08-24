# Canvas Digest

A weekday-morning assignment tracker that pulls live due dates from
Canvas LMS, filters out everything that isn't actually actionable, and
delivers what's left two ways: a push notification and a small static
dashboard.

**Live example:** `https://<your-username>.github.io/canvas-digest/` (once deployed — see SETUP.md)

## What it does

Every weekday at 6:30 AM Central, a GitHub Actions workflow:

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
5. Renders a static dashboard (`docs/index.html`) and deploys it to
   GitHub Pages.
6. Sends a push notification via [ntfy.sh](https://ntfy.sh) summarizing
   the same thing.

No server to run, no database, no student-facing announcements or
noise — just what a student actually needs to see before class.

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
  canvas_client.py   Canvas REST API wrapper (courses, assignments, pagination)
  digest.py          Filtering + bucketing (overdue / due today / coming up)
  dashboard.py       Renders the digest into a static HTML page
  notify.py          Sends the push notification via ntfy.sh
  main.py            Orchestrates the above; entry point for the workflow
tests/
  test_digest.py     Unit tests against mock assignment data
.github/workflows/
  daily-digest.yml   Cron schedule + GitHub Pages deploy
```

## Tech

Python 3.12, `requests`, GitHub Actions (schedule + Pages deploy),
ntfy.sh for push delivery. No frameworks, no external services beyond
Canvas and ntfy.

## Setup

See [SETUP.md](./SETUP.md) for the full walkthrough (Canvas token,
ntfy topic, GitHub secrets, enabling Pages).

## License

MIT — do whatever you want with it.

# Setup

Five steps: create the repo, get a Canvas token, pick an ntfy topic,
add secrets, enable Pages. About 10 minutes total.

## 1. Create the GitHub repo

- Create a new **public** repository on GitHub (public is required for
  free GitHub Pages hosting; nothing sensitive is ever in the repo —
  see "What's public" below).
- Push this project's files into it:

  ```
  cd canvas-digest
  git init
  git add .
  git commit -m "Initial commit"
  git branch -M main
  git remote add origin https://github.com/<you>/canvas-digest.git
  git push -u origin main
  ```

## 2. Get a Canvas access token

1. Log into Canvas → click your profile picture → **Account** → **Settings**.
2. Scroll to **Approved Integrations** → click **+ New Access Token**.
3. Purpose: something like `Daily digest bot` (so you can revoke this
   token specifically later without breaking anything else).
4. Leave "Expires" blank unless you want to rotate it periodically.
5. Copy the generated token immediately — Canvas only shows it once.

You also need your Canvas domain — the part of the URL before
`/courses`, e.g. `samford.instructure.com`.

## 3. Pick an ntfy topic and install the app

1. Install **ntfy** from the [App Store](https://apps.apple.com/app/ntfy/id1625396347)
   or [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   (it's also just a website, ntfy.sh, if you'd rather not install anything).
2. Pick a topic name that's long and hard to guess — anyone who knows
   the exact name can read what's published to it, since there's no
   account/auth involved. Something like `aiden-canvas-8f2k1x` is fine.
3. In the app, tap **+** and subscribe to that exact topic name.
4. That's it — no account, no signup.

## 4. Add GitHub Actions secrets

In your repo: **Settings → Secrets and variables → Actions**.

**Secrets** (Settings → Secrets and variables → Actions → *Secrets* tab → New repository secret):

| Name | Value |
|---|---|
| `CANVAS_DOMAIN` | e.g. `samford.instructure.com` |
| `CANVAS_TOKEN` | the token from step 2 |
| `NTFY_TOPIC` | the topic name from step 3 |

**Variables** (same page, *Variables* tab — optional, both have defaults):

| Name | Value | Default if unset |
|---|---|---|
| `LOOKAHEAD_DAYS` | how many days ahead to show in "Coming Up" | `7` |
| `EXCLUDE_COURSE_IDS` | comma-separated Canvas course IDs to hide (find a course's ID in its Canvas URL, e.g. `.../courses/12345`) | none |

## 5. Enable GitHub Pages

**Settings → Pages → Build and deployment → Source: "GitHub Actions"**
(not "Deploy from a branch"). The workflow already handles the deploy
step; this just tells GitHub to let it.

## Test it

Go to the **Actions** tab → **Daily Canvas Digest** → **Run workflow**
→ Run workflow. This fires it immediately instead of waiting for the
schedule. Check:

- Your phone for the ntfy push.
- The Pages URL shown at **Settings → Pages** (or the deploy job's
  summary) for the dashboard.

If it fails, click into the failed run — the most common causes are a
typo'd `CANVAS_DOMAIN` (no `https://`, just the bare domain) or a
`CANVAS_TOKEN` that got truncated when copy-pasted.

## Adjusting the schedule

The cron in `.github/workflows/daily-digest.yml` is `30 11 * * 1-5`
(11:30 UTC = 6:30 AM Central during Daylight Time). GitHub Actions cron
doesn't account for Daylight Saving Time, so the workflow will drift to
5:30 AM local once Standard Time starts in the fall. Comments in that
file explain the one-line fix — flip `30 11` to `30 12` when Standard
Time starts, and back when Daylight Time resumes.

## What's public

The repo and the deployed dashboard are public: course names and
assignment titles are visible to anyone with the link. Your Canvas
token, domain, and ntfy topic are **not** — they exist only as
encrypted GitHub Actions secrets, injected as environment variables at
run time, never written to any file in the repo or the deployed site.

## Adding or removing a class later

Nothing to do — courses are auto-discovered from your active Canvas
enrollments every run. To hide a specific course without unenrolling
(e.g. an audit), add its Canvas course ID to the `EXCLUDE_COURSE_IDS`
repo variable (comma-separated for more than one).

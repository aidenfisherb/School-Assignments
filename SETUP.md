# Setup

Five steps: create the repo, get a Canvas token, pick an ntfy topic,
add secrets, enable Pages. About 10 minutes total.

## 1. Push to a public GitHub repo

- The repo hosting this project needs to be **public** (required for
  free GitHub Pages hosting; nothing sensitive is ever in the repo —
  see "What's public" below), and this project's files need to live at
  the **repo root** — GitHub Actions only discovers workflows under
  `.github/workflows/` at the top level, not inside a subdirectory.
- If you're starting fresh:

  ```
  git init
  git add .
  git commit -m "Initial commit"
  git branch -M dev
  git remote add origin https://github.com/<you>/<repo-name>.git
  git push -u origin dev
  ```
  (`dev` here just matches this repo's actual default branch — use
  whatever your repo's default branch is, `main` is just as fine for a
  fresh one.)

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
| `GEMINI_API_KEY` | *optional* — enables syllabus extraction; see "Adding a syllabus" below |

**Variables** (same page, *Variables* tab — optional, both have defaults):

| Name | Value | Default if unset |
|---|---|---|
| `LOOKAHEAD_DAYS` | how many days ahead to show in "Coming Up" | `7` |
| `EXCLUDE_COURSE_IDS` | comma-separated Canvas course IDs to hide (find a course's ID in its Canvas URL, e.g. `.../courses/12345`) | none |
| `GEMINI_MODEL` | Gemini model used for syllabus extraction | `gemini-3.8-flash` |

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

## Adding a syllabus

**One-time: get a free Gemini API key.** Go to
[aistudio.google.com](https://aistudio.google.com), sign in with a
Google account, and click **Get API key → Create API key**. No billing
or card is needed — leave the project on the free tier. Add the key as
the `GEMINI_API_KEY` repo secret (step 4). Each syllabus file costs one
API call, ever, so the free tier's daily limits are far more than this
uses. Note that Google may use free-tier inputs to improve its models;
the syllabi are already public in this repo, so nothing new is exposed.

Without the key the rest of the project works normally; uploaded
syllabi just show as "not extracted yet" on the Syllabi page.

1. On GitHub, use **Add file → Upload files** to upload a `.pdf` or
   `.docx` syllabus to a path like `syllabi/COSC240/syllabus.pdf` —
   `COSC240` should match part of that course's Canvas course code or
   name (case doesn't matter). You can also start from the **Syllabi**
   page on your dashboard (linked from the navbar), which lists a
   suggested path per course and links straight to GitHub's upload
   screen.
2. Commit directly to your default branch. That push triggers an
   immediate rebuild (in addition to the daily schedule), so the
   dashboard picks it up within a minute or two rather than waiting
   for the next morning. The run sends the file to Gemini once and
   commits the result as `<file>.extracted.json` next to it.
3. **Check the result.** On the Syllabi page, click **review dates**
   next to the file. That opens the extracted JSON in GitHub's editor:
   fix any wrong `due_date` (`YYYY-MM-DD`) or `due_time` (`HH:MM`, or
   `null`), delete items that aren't real deliverables, and commit.
   Your edits are kept until the syllabus file itself is replaced.
4. To remove a syllabus, use the **remove** link next to the file on
   the Syllabi page (or delete it on GitHub). The next run deletes its
   `.extracted.json` too.

Anything that still disagrees with Canvas shows up with a
**Conflicting** tag on the dashboard instead of silently overriding
Canvas, so it's always visible when the two disagree.

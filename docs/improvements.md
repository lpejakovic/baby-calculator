# Improvements

_Review started 2026-10-17. Items are removed from this file as they are done; when it is empty, the review is complete._

## Plan

1. **Cleanup:** API time zone, plural helpers, imports, favicon, rate limit on `GET /`.
2. **Features:** milestones, share link, PWA, pregnancy mode, several children.
3. **Quality:** tests and CI.

## 1. Code cleanup and speed

- **`/calculate` API** (kept): the page no longer uses it. It still uses the server's clock (CEST), so callers in other time zones get shifted results and a very recent birth east of CEST can be rejected as "in the future". Accept an optional UTC offset or a time-zone name.
- **Plural helpers:** replace the six near-identical Python functions with one `plural(n, forms)` function, like the one in `static/js/app.js`.
- **Imports:** change `from utils_dt import *` to explicit imports.
- **Favicon:** 92 KB. Use a small `.ico` (under 5 KB) plus an SVG icon and an `apple-touch-icon.png`.
- **Rate limit on `GET /`:** `1 per second; 8 per minute` is strict for a static page; two quick reloads already give a 429. Only `/calculate` needs a strict limit.
- **Storage:** limit counters are in memory. Fine with 1 worker; switch to Redis if workers are added.
- **Tests:**
  - `pytest` tests for the Python plural rules, month ends, leap years (29 Feb) and invalid input.
  - JavaScript tests for `calculateAge`, `plural`, `parseBirth` and `joinParts` (the script exports them via `module.exports`). During the rewrite they were checked against `relativedelta` with 20,000 random dates in QuickJS; turn that into a repeatable test.
- **CI:** GitHub Actions workflow that runs the tests on each push.

## 2. New features

1. **Milestones:** "100. dan za 12 dana", the "1000 dana" date, next month birthday, countdown to the first birthday.
2. **Pregnancy mode:** enter the due date or last period and get "34. tjedan + 2 dana", plus a countdown to the due date.
3. **Several children:** save names and dates in `localStorage` and switch between them.
4. **Share link:** `?d=2026-09-01T08:30` opens with the date filled in, plus a "Kopiraj" button for the text result.
5. **Install as an app (PWA):** manifest and service worker, so it installs on the home screen and works offline.
6. **Language:** HR/EN switch; the page title is still English.
7. **Link preview image:** `og:image` for nicer previews in Viber/WhatsApp (the other Open Graph tags are in place).

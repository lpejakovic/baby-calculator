# Project digest: baby-calculator

_Generated 2026-10-17 at v1.3 (commit `4415c13`); updated for v2.0._

## Summary

baby-calculator is a single-page app that takes a baby's date and time of birth and shows the age
as weeks/days, years/months/days, a live days/hours/minutes/seconds counter and upcoming milestones, with Croatian
labels that use the correct grammatical number, and in English at `/en/`. A pregnancy mode shows weeks + days, trimester, due date and
pregnancy milestones. Since v2.0 the calculation runs in the browser;
Flask serves the page and an optional JSON API. It has no database, has 329 automated tests and linting in CI, and runs
in production under Gunicorn + nginx via systemd.

## Tech stack

| Layer      | Technology                                                    |
|------------|---------------------------------------------------------------|
| Backend    | Python 3.12, Flask 3.1.3, Werkzeug 3.1.9, Jinja2 3.1.6                                       |
| Date math  | Browser: own `calculateAge()`; API: python-dateutil 2.9 (`relativedelta`) |
| Rate limit | Flask-Limiter 4.1.1 (in-memory storage)                        |
| Frontend   | Jinja2 template, plain JavaScript (`static/js/app.js`), plain CSS with light/dark themes |
| Serving    | Gunicorn 26 as `www-data`, 1 worker, socket `/run/baby-calculator/bc-calculator.sock`; nginx serves `/static/`, adds security headers (`deploy/`) |

Dependencies are pinned in `requirements.txt`.

## Files

| File                     | Purpose |
|--------------------------|---------|
| `app.py`                 | Flask app, `APP_VERSION`, Limiter setup, routes `/`, `/en/`, `/sw.js`, `/health`, `/robots.txt`, `/sitemap.xml` and `/calculate`, 404 handler |
| `i18n.py`                | Page texts (`PAGE_TEXT`) in Croatian and English |
| `utils_dt.py`            | API only: `plural()`, Croatian and English word forms, `join_units()`, `format_datetime()`, `calculate_date_difference()` |
| `wsgi.py`                | Gunicorn entry point (`wsgi:app`) |
| `requirements.txt`       | Pinned dependencies |
| `deploy/`                | systemd unit, nginx site config, `deploy.sh` (deploys `origin/main` after CI passed, with rollback) |
| `tests/`, `pytest.ini`   | Python, JavaScript (QuickJS) and browser (Playwright) tests |
| `requirements-dev.txt`   | Test dependencies |
| `.github/workflows/tests.yml` | CI: lint job (ruff, ESLint), unit job, browser job with axe-core accessibility audit |
| `pyproject.toml`, `eslint.config.js`, `package.json` | Linter settings and the pinned ESLint version |
| `.github/workflows/uptime.yml` | Checks `/health`, `/` and `/en/` on the live site every 15 minutes |
| `.github/dependabot.yml` | Weekly update PRs for pip, npm and GitHub Actions |
| `templates/index.html`   | Form, result cards, meta and Open Graph tags (absolute `og:image` via `_external=True`) |
| `templates/404.html`     | Not-found page in the language of the URL (`/en/…` is English), `noindex` |
| `templates/sitemap.xml`  | Both pages with `hreflang` alternates |
| `templates/sw.js`        | Service worker template: precache list and cache name come from the current versioned asset URLs |
| `static/manifest.json`   | Web app manifest (standalone, icons 192/512/maskable); `manifest-en.json` for `/en/` |
| `static/js/app.js`       | Date parsing, `calculateAge()`, `correctedAge()`, `upcomingMilestones()`, children, pregnancy functions, share links, Croatian plurals, live counter, `localStorage` |
| `static/styles/main.css` | CSS variables, light/dark themes, responsive card layout (max width 640px) |
| `static/favicon.ico`     | Favicon, 16 and 32 px (3.9 KB) |
| `static/apple-touch-icon.png` | Home-screen icon, 180 px |
| `static/images/icon-1024.webp` | Full-size icon artwork (source for other icons) |
| `static/images/og-image.png` | Link preview images, 1200×630 (55 KB each; `-en` for English) |
| `scripts/make_og_image.py` | Regenerates the preview image with Pillow |

## Page flow

1. `GET /` renders `index.html` with `APP_VERSION`. `app.js` loads with `defer`.
2. On load, the script reads the children from `localStorage` (`children`: `[{id, name, date, time}]`, `activeChild`).
   `normalizeChildren()` drops invalid entries and renumbers duplicate ids; a v2.x single `birth` entry or a v1.x
   `datetime` cookie becomes the first child and the old key is removed. A valid `?d=YYYY-MM-DD[THH:MM][&n=name]`
   link is added with `addSharedChild()` (or selects a child with the same birth) and removed from the address bar.
   The selected child is filled in and calculated straight away. Chips switch children; "+ Dodaj dijete" clears the
   form and the next calculation creates a child; "Ukloni dijete" asks for confirmation and selects a neighbour.
3. On submit or when an input changes, the script validates the date (required, real calendar date, not in the future),
   saves it and renders three cards. A 1-second timer re-renders them, so the total ticks live.
4. Calendar values (years, months, days, weeks) use wall-clock time stored as UTC milliseconds, so they use the visitor's
   time zone and aren't shifted by DST. The "Ukupno" total uses the real elapsed time (`wallToReal()` turns the birth
   into a real moment in the visitor's zone), so it is one hour longer across a summer-to-winter time change.
   `calculateAge()` uses the same month clipping as `relativedelta` (31 Jan + 1 month = 28/29 Feb).
5. `upcomingMilestones()` lists month birthdays (1–23 months), birthdays (`N. rođendan`) and day counts (100 … 10,000 days)
   by date only, keeps those from today on and shows the nearest three with "danas" / "sutra" / "za N dana".
   The list is rebuilt only when the date changes, not every second.
6. "Podijeli" calls `navigator.share()` with the link and a summary, or copies the link where sharing isn't available;
   "Kopiraj tekst" copies the summary. Both use the Clipboard API with a `textarea` fallback, and report in a `role="status"` line.
7. A visually hidden `aria-live` region announces the result once; the ticking counter is not announced.
8. **Pregnancy mode** ("Trudnoća"): the date is a due date or the first day of the last period (LMP); `lmpFrom()` converts
   with the 280-day rule. `pregnancyStatus()` gives completed weeks + days, the current week, trimester (1: to 13+6,
   2: to 27+6, 3: from 28+0), due date, days to due and progress. `pregnancyError()` accepts LMP from today back to
   42 weeks. `pregnancyMilestones()` lists 14, 20, 28, 37 and 40 weeks. Mode and pregnancy data are stored under the
   `mode` and `pregnancy` keys; `?t=YYYY-MM-DD` shares a due date. Pregnancy values change once a day, so they are
   re-rendered on a 1-minute timer only when the date changes.
9. **Corrected age**: a child can have an optional due date (`due`, stored with the child and shared as `&due=`).
   `correctedAge()` gives the gestational age at birth (280 days minus the days born early), whether the due date
   has passed, and then `calculateAge(due, now)`. The card shows "Počinje na termin" before the due date and "Nije
   potrebna" for babies born on or after it, and notes from age 2 that correction is usually used until then.
   `correctedAgeError()` allows a due date at most 20 weeks after the birth.
10. **Backup and restore** ("Sigurnosna kopija"): `makeBackup()` writes `{app, version: 1, exportedAt, children,
   activeChild, pregnancy, mode}`; "Preuzmi datoteku" downloads it as JSON (Blob link), "Učitaj datoteku" reads a file
   (max 100 KB) and "Kopiraj poveznicu za prijenos" copies `/#backup=<encoded JSON>`. The data after `#` is never sent
   to the server. `parseBackup()` validates and cleans like stored data; `mergeChildren()` adds children with
   `addSharedChild()` (no duplicates, missing names and due dates filled in, new ids); different pregnancy data is
   replaced only after `confirm()`. A transfer link is handled on load and on `hashchange`, then removed from the URL.
11. **Calendar export**: "Dodaj u kalendar" in each milestone card downloads an `.ics` file (RFC 5545) built by
   `buildIcs()`: all-day, non-blocking events with a reminder at 9:00, CRLF line endings, escaped text and lines
   folded at 75 bytes. Baby files cover `babyMilestones()` for the next two years; pregnancy files cover the
   remaining pregnancy milestones. Event ids are derived from the birth (or LMP) date and the milestone key, so
   re-importing updates existing events.
12. **Languages**: `/` (Croatian) and `/en/` (English) render the same template with `PAGE_TEXT[lang]`, and add
   canonical and `hreflang` links (`x-default` is Croatian) plus a link to the other language. The script reads
   `<html lang>` and takes every text from `TEXT[lang]` in `app.js` (plural rules, "i"/"and", ordinals, date format,
   errors, share text); the pure functions take an optional `lang` that defaults to Croatian. Saved data is shared
   between the pages, share links keep the current page, and each language has its own manifest, start URL and
   preview image. The language switch sets a `lang` cookie; `/` redirects to `/en/` when it is `en` (the `#…` part of
   the URL survives the redirect), and the cached page does the same offline.
13. The script registers `/sw.js`. Flask renders it with the page and versioned static URLs, so any static change gives a new
   service worker and cache name; old caches are deleted on activation. The page is network-first with a cached fallback,
   static files are cache-first, and `/calculate` is never cached. Where Chrome fires `beforeinstallprompt`, an
   "Instaliraj aplikaciju" button appears.

## API flow (`POST /calculate`)

The page doesn't call it. It reads form fields or a JSON object (`datetime`, optional `tz` defaulting to
`Europe/Zagreb`, optional `lang` `hr`/`en`), validates them (400 with a message in the requested language), takes the
current time in `tz`, and returns the original text fields (`current`, `day_diff`, `week_diff`, `year_diff`) plus
`age.calendar`, `age.weeks` (wall-clock), `age.elapsed` (real elapsed time, DST-aware), `birth`, `now`, `tz` and `lang`.

## Croatian plural rules

`plural(n, forms)` in `app.js` and `plural(number, forms)` in `utils_dt.py` follow the standard Croatian rule:

- ends in 1, but not 11 → singular (`1 sat`, `21 minutu`)
- ends in 2–4, but not 12–14 → paucal (`3 sata`, `22 minute`)
- otherwise → genitive plural (`5 sati`, `12 minuta`)

"dan" has only two distinct forms (`dan` / `dana`).
The API uses accusative forms (`godinu`, `minutu`, `sekundu`) because its text was written for "Vaše dijete ima …";
the page uses nominative forms (`godina`, `minuta`, `sekunda`) for the card values.

## Rate limiting

- `/calculate`: `1 per second; 8 per minute; 32 per hour`, keyed by client IP
- `/`: not limited (`@limiter.exempt`); static files are served by nginx and never reach Flask
- Defaults for anything else: `200 per day; 50 per hour`
- Storage is explicitly in-memory (`memory://`), so counters reset when the service restarts. Fine with one Gunicorn worker;
  switch to Redis if workers are added.
- **Real client IP** (fixed): nginx proxies over a Unix socket with `include proxy_params`, and the app wraps
  `wsgi_app` in `ProxyFix(x_for=1, x_proto=1, x_host=1)`. `get_remote_address` sees the client IP from the last
  `X-Forwarded-For` entry, so each visitor has their own limit and forged header prefixes are ignored.

## Version history

| Date       | Version / change |
|------------|------------------|
| 2024-05-18 | Initial commit |
| 2024-05-26 | Fixed month label, fixed calculation for unborn children; throttling added; **v1.1** |
| 2024-05-28 | `datetime-local` input |
| 2024-05-30 | **v1.2**: favicon, `main.css`, throttle changed |
| 2024-06-08 | Limits set to 8/min and 32/h; plural labels corrected; **v1.3**; button timeout after request |
| 2026-10-17 | Docs, `requirements.txt`, JSON errors, `ProxyFix`, package upgrades, future dates rejected, accessibility fixes |
| 2026-10-17 | **v2.0**: calculation in the browser, live counter, result cards, dark mode, no jQuery, `localStorage` |
| 2026-10-17 | Server hardening (`deploy/`), cleanup, new icons, 93 tests and CI |
| 2026-10-17 | **v2.1**: upcoming milestones |
| 2026-10-17 | **v2.2**: share link, "Podijeli" and "Kopiraj tekst" |
| 2026-10-17 | **v2.3**: link preview image |
| 2026-10-17 | **v2.4**: installable app (PWA), works offline |
| 2026-10-17 | **v2.5**: pregnancy mode |
| 2026-10-17 | **v2.6**: several children |
| 2026-10-17 | **v2.7**: English version and language switch; the improvement review is complete |
| 2026-10-17 | **v2.7.1**: real elapsed time in "Ukupno", 404 page, `robots.txt`, `sitemap.xml`, date limits follow today |
| 2026-10-17 | Passwordless restart (sudoers rule), `/health`, uptime workflow, Dependabot |
| 2026-10-17 | **v2.8**: corrected age for premature babies |
| 2026-10-17 | **v2.9**: backup and restore; browser tests run under the production CSP |
| 2026-10-17 | **v2.10**: calendar export of milestones (`.ics`) |
| 2026-10-17 | Linting (ruff, ESLint) and axe-core accessibility audit in CI; removed dead code found by ESLint |
| 2026-10-17 | Separate development clone, pull requests, `deploy/deploy.sh`; heavy tests only in CI; branch protection |
| 2026-10-17 | **v2.11**: API with plain numbers, JSON input, `lang=en`, real elapsed time |
| 2026-10-17 | **v2.12**: privacy note, share links after `#` (never sent to the server), remembered language |

## Observations and issues

Checked against the running code with Flask's test client:

1. **Bad input** (fixed): an invalid or missing `datetime` returns 400 with `{"error": "..."}`, and rate-limited
   `/calculate` requests return 429 with a JSON message. The page shows the message in red under the form.
2. **Future dates** (fixed): rejected with 400 `Datum rođenja ne može biti u budućnosti.`, and the input has a `max` of the current time.
3. **Time zone** (fixed): the page calculates in the visitor's time zone; the API accepts `tz` and uses real elapsed time.
4. **Dead code in `utils_dt.py`** (fixed): removed.
5. **Wildcard import** (fixed): `app.py` imports names from `utils_dt` explicitly.
6. **Repetitive helpers** (fixed): one `plural(number, forms)` function with word-form tuples. API output was checked
   to be identical to the old helpers on 3,006 inputs.
7. **Repo hygiene** (fixed): `wsgi.py` and `requirements.txt` are committed, and `.gitignore` covers `__pycache__/`, `bc-env/` and `*.sock`.
   The working tree still has file-mode-only changes (644 → 755) on some tracked files.
8. **Template details** (fixed): the version comes from `APP_VERSION`, and results are inserted with `textContent`.
9. **Production config.** `app.run(debug=True)` only runs when `app.py` is started directly, not under Gunicorn.
   The systemd unit in `deploy/` runs Gunicorn as `www-data` with sandboxing (was `root`).
10. **Tests** (fixed): 329 tests (22 of them an axe-core accessibility audit) under `pytest`: Python helpers, the API with a frozen clock, `app.js` in QuickJS compared with
    `relativedelta`, and Playwright browser tests for behaviour and responsive layout. GitHub Actions runs them on every push.

## Suggested next steps

A second improvement review is in progress; see [improvements.md](improvements.md).

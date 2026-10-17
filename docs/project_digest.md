# Project digest: baby-calculator

_Generated 2026-10-17 at v1.3 (commit `4415c13`); updated for v2.0._

## Summary

baby-calculator is a single-page app that takes a baby's date and time of birth and shows the age
as weeks/days, years/months/days, a live days/hours/minutes/seconds counter and upcoming milestones, with Croatian
labels that use the correct grammatical number. A pregnancy mode shows weeks + days, trimester, due date and
pregnancy milestones. Since v2.0 the calculation runs in the browser;
Flask serves the page and an optional JSON API. It has no database, has 188 automated tests with CI, and runs
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
| `app.py`                 | Flask app, `APP_VERSION`, Limiter setup, routes `/`, `/sw.js` and `/calculate` |
| `utils_dt.py`            | API only: `plural()` and Croatian word forms, `format_datetime()`, `calculate_date_difference()` |
| `wsgi.py`                | Gunicorn entry point (`wsgi:app`) |
| `requirements.txt`       | Pinned dependencies |
| `deploy/`                | systemd unit and nginx site config |
| `tests/`, `pytest.ini`   | Python, JavaScript (QuickJS) and browser (Playwright) tests |
| `requirements-dev.txt`   | Test dependencies |
| `.github/workflows/tests.yml` | CI: unit job and browser job |
| `templates/index.html`   | Form, result cards, meta and Open Graph tags (absolute `og:image` via `_external=True`) |
| `templates/sw.js`        | Service worker template: precache list and cache name come from the current versioned asset URLs |
| `static/manifest.json`   | Web app manifest (standalone, icons 192/512/maskable) |
| `static/js/app.js`       | Date parsing, `calculateAge()`, `upcomingMilestones()`, children, pregnancy functions, share links, Croatian plurals, live counter, `localStorage` |
| `static/styles/main.css` | CSS variables, light/dark themes, responsive card layout (max width 640px) |
| `static/favicon.ico`     | Favicon, 16 and 32 px (3.9 KB) |
| `static/apple-touch-icon.png` | Home-screen icon, 180 px |
| `static/images/icon-1024.webp` | Full-size icon artwork (source for other icons) |
| `static/images/og-image.png` | Link preview image, 1200×630 (55 KB) |
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
4. All date math uses wall-clock time stored as UTC milliseconds, so it uses the visitor's time zone and isn't shifted by DST.
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
9. The script registers `/sw.js`. Flask renders it with the page and versioned static URLs, so any static change gives a new
   service worker and cache name; old caches are deleted on activation. The page is network-first with a cached fallback,
   static files are cache-first, and `/calculate` is never cached. Where Chrome fires `beforeinstallprompt`, an
   "Instaliraj aplikaciju" button appears.

## API flow (`POST /calculate`)

The page no longer calls it. The server parses `datetime=YYYY-MM-DDTHH:MM` with `strptime`, takes the current time in the optional
`tz` time zone (IANA name, via `zoneinfo`) or else the server's local time, rejects invalid dates, future dates and unknown zones with 400,
and returns `day_diff`, `week_diff` and `year_diff` strings plus `current`.

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

## Observations and issues

Checked against the running code with Flask's test client:

1. **Bad input** (fixed): an invalid or missing `datetime` returns 400 with `{"error": "..."}`, and rate-limited
   `/calculate` requests return 429 with a JSON message. The page shows the message in red under the form.
2. **Future dates** (fixed): rejected with 400 `Datum rođenja ne može biti u budućnosti.`, and the input has a `max` of the current time.
3. **Time zone** (fixed): the page calculates in the visitor's time zone; the API accepts an optional `tz`.
4. **Dead code in `utils_dt.py`** (fixed): removed.
5. **Wildcard import** (fixed): `app.py` imports names from `utils_dt` explicitly.
6. **Repetitive helpers** (fixed): one `plural(number, forms)` function with word-form tuples. API output was checked
   to be identical to the old helpers on 3,006 inputs.
7. **Repo hygiene** (fixed): `wsgi.py` and `requirements.txt` are committed, and `.gitignore` covers `__pycache__/`, `bc-env/` and `*.sock`.
   The working tree still has file-mode-only changes (644 → 755) on some tracked files.
8. **Template details** (fixed): the version comes from `APP_VERSION`, and results are inserted with `textContent`.
9. **Production config.** `app.run(debug=True)` only runs when `app.py` is started directly, not under Gunicorn.
   The systemd unit in `deploy/` runs Gunicorn as `www-data` with sandboxing (was `root`).
10. **Tests** (fixed): 188 tests under `pytest`: Python helpers, the API with a frozen clock, `app.js` in QuickJS compared with
    `relativedelta`, and Playwright browser tests for behaviour and responsive layout. GitHub Actions runs them on every push.

## Suggested next steps

New features; see below.

The full list of open improvements is in [improvements.md](improvements.md).

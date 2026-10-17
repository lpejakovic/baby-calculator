# Project digest: baby-calculator

_Generated 2026-10-17 at v1.3 (commit `4415c13`); updated for v2.0._

## Summary

baby-calculator is a single-page app that takes a baby's date and time of birth and shows the age
as weeks/days, years/months/days and a live days/hours/minutes/seconds counter, with Croatian
labels that use the correct grammatical number. Since v2.0 the calculation runs in the browser;
Flask serves the page and an optional JSON API. It has no database and no automated tests, and runs
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
| `app.py`                 | Flask app, `APP_VERSION`, Limiter setup, routes `/` and `/calculate` |
| `utils_dt.py`            | API only: `generate_*_string()` Croatian plural helpers, `format_datetime()`, `calculate_date_difference()` |
| `wsgi.py`                | Gunicorn entry point (`wsgi:app`) |
| `requirements.txt`       | Pinned dependencies |
| `deploy/`                | systemd unit and nginx site config |
| `templates/index.html`   | Form, result cards, meta/Open Graph tags |
| `static/js/app.js`       | Date parsing, `calculateAge()`, Croatian plurals, live counter, `localStorage` |
| `static/styles/main.css` | CSS variables, light/dark themes, responsive card layout (max width 640px) |
| `static/favicon.ico`     | Favicon |

## Page flow

1. `GET /` renders `index.html` with `APP_VERSION`. `app.js` loads with `defer`.
2. On load, the script reads the saved birth date from `localStorage` (or moves a v1.x `datetime` cookie there)
   and, if one exists, fills the inputs and calculates straight away.
3. On submit or when an input changes, the script validates the date (required, real calendar date, not in the future),
   saves it and renders three cards. A 1-second timer re-renders them, so the total ticks live.
4. All date math uses wall-clock time stored as UTC milliseconds, so it uses the visitor's time zone and isn't shifted by DST.
   `calculateAge()` uses the same month clipping as `relativedelta` (31 Jan + 1 month = 28/29 Feb).
5. A visually hidden `aria-live` region announces the result once; the ticking counter is not announced.

## API flow (`POST /calculate`)

The page no longer calls it. The server parses `datetime=YYYY-MM-DDTHH:MM` with `strptime`, rejects invalid or future dates with 400,
subtracts it from `datetime.now()` and returns `day_diff`, `week_diff` and `year_diff` strings plus `current`.

## Croatian plural rules

`plural(n, forms)` in `app.js` and each `generate_*_string(n)` in `utils_dt.py` follow the standard Croatian rule:

- ends in 1, but not 11 → singular (`1 sat`, `21 minutu`)
- ends in 2–4, but not 12–14 → paucal (`3 sata`, `22 minute`)
- otherwise → genitive plural (`5 sati`, `12 minuta`)

`generate_days_string` has only two forms (`dan` / `dana`), which is correct for "dan".
The API uses accusative forms (`godinu`, `minutu`, `sekundu`) because its text was written for "Vaše dijete ima …";
the page uses nominative forms (`godina`, `minuta`, `sekunda`) for the card values.

## Rate limiting

- Defaults: `200 per day; 50 per hour`
- Both routes: `1 per second; 8 per minute; 32 per hour`, keyed by remote address
- Storage is in-memory, so counters reset when the service restarts. Flask-Limiter logs a warning about this at startup.
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

## Observations and issues

Checked against the running code with Flask's test client:

1. **Bad input** (fixed): an invalid or missing `datetime` returns 400 with `{"error": "..."}`, and rate-limited
   `/calculate` requests return 429 with a JSON message. The page shows the message in red under the form.
2. **Future dates** (fixed): rejected with 400 `Datum rođenja ne može biti u budućnosti.`, and the input has a `max` of the current time.
3. **Time zone** (fixed for the page): the page calculates in the visitor's time zone. The API still uses the server's local time.
4. **Dead code in `utils_dt.py`** (fixed): removed.
5. **`from utils_dt import *`** in `app.py`. Explicit imports would be clearer.
6. **Repetitive helpers.** The six three-form plural functions are identical apart from their words and could be one
   `plural(n, one, few, many)` function.
7. **Repo hygiene** (fixed): `wsgi.py` and `requirements.txt` are committed, and `.gitignore` covers `__pycache__/`, `bc-env/` and `*.sock`.
   The working tree still has file-mode-only changes (644 → 755) on some tracked files.
8. **Template details** (fixed): the version comes from `APP_VERSION`, and results are inserted with `textContent`.
9. **Production config.** `app.run(debug=True)` only runs when `app.py` is started directly, not under Gunicorn.
   The systemd unit in `deploy/` runs Gunicorn as `www-data` with sandboxing (was `root`).
10. **No automated tests.** The JS date math was checked against `relativedelta` with 20,000 random dates and the page in headless
    Chromium at five screen sizes, but none of this is in the repo yet.

## Suggested next steps

1. Automated tests (Python and JavaScript) and CI.

The full list of open improvements is in [improvements.md](improvements.md).

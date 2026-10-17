# Project digest: baby-calculator

_Generated 2026-10-17, version v1.3 (commit `4415c13`)._

## Summary

baby-calculator is a single-page Flask app that takes a baby's date and time of birth and returns
the elapsed time as days/hours/minutes/seconds, years/months/days and weeks/days, with Croatian
labels that use the correct grammatical number. It is about 200 lines of code, has no database and
no tests, and runs in production under Gunicorn + nginx via systemd.

## Tech stack

| Layer      | Technology                                                    |
|------------|---------------------------------------------------------------|
| Backend    | Python 3.12, Flask 3.0.3                                       |
| Date math  | python-dateutil 2.9 (`relativedelta`)                          |
| Rate limit | Flask-Limiter 3.7.0 (in-memory storage)                        |
| Frontend   | Jinja2 template, jQuery 3.6.0 (from code.jquery.com), plain CSS |
| Serving    | Gunicorn 22, 1 worker, Unix socket `bc-calculator.sock`, nginx |

Dependencies are pinned in `requirements.txt`.

## Files

| File                     | Purpose |
|--------------------------|---------|
| `app.py`                 | Flask app, Limiter setup, routes `/` and `/calculate` |
| `utils_dt.py`            | `generate_*_string()` Croatian plural helpers, `format_datetime()`, `calculate_date_difference()` |
| `wsgi.py`                | Gunicorn entry point (`wsgi:app`) |
| `requirements.txt`       | Pinned dependencies |
| `templates/index.html`   | Form, cookie helpers, AJAX call and result rendering |
| `static/styles/main.css` | Centered card layout, max width 400px |
| `static/favicon.ico`     | Favicon |

## Request flow

1. `GET /` renders `index.html`. On load, the page fills the input from the `datetime` cookie if one exists.
2. On submit, JS stores the value in the cookie (30 days), disables the button and sends
   `POST /calculate` with `datetime=YYYY-MM-DDTHH:MM`.
3. The server parses the value with `strptime`, subtracts it from `datetime.now()` and builds three strings:
   - `day_diff`: total days from `timedelta.days`, plus hours/minutes/seconds from `timedelta.seconds`
   - `week_diff`: `days // 7` weeks and `days % 7` days
   - `year_diff`: years, months and days from `relativedelta(now, birth)`
4. The JSON response is put into `#result`. The button is enabled again 1 s after the request finishes.

## Croatian plural rules

Each `generate_*_string(n)` follows the standard Croatian rule:

- ends in 1, but not 11 → singular (`1 sat`, `21 minutu`)
- ends in 2–4, but not 12–14 → paucal (`3 sata`, `22 minute`)
- otherwise → genitive plural (`5 sati`, `12 minuta`)

`generate_days_string` has only two forms (`dan` / `dana`), which is correct for "dan".
Accusative forms (`godinu`, `minutu`, `sekundu`) are used because the text reads "Vaše dijete ima …".

## Rate limiting

- Defaults: `200 per day; 50 per hour`
- Both routes: `1 per second; 8 per minute; 32 per hour`, keyed by remote address
- Storage is in-memory, so counters reset when the service restarts. Flask-Limiter logs a warning about this at startup.
- **Likely shared bucket.** nginx proxies over a Unix socket with `include proxy_params` (sends `X-Forwarded-For` / `X-Real-IP`),
  but the app does not use `ProxyFix`. So `get_remote_address` sees the socket peer, not the client, and all visitors
  probably share one limit (e.g. 8 requests per minute across the whole site).

## Version history

| Date       | Version / change |
|------------|------------------|
| 2024-05-18 | Initial commit |
| 2024-05-26 | Fixed month label, fixed calculation for unborn children; throttling added; **v1.1** |
| 2024-05-28 | `datetime-local` input |
| 2024-05-30 | **v1.2**: favicon, `main.css`, throttle changed |
| 2024-06-08 | Limits set to 8/min and 32/h; plural labels corrected; **v1.3**; button timeout after request |

## Observations and issues

Checked against the running code with Flask's test client:

1. **Bad input** (fixed): an invalid or missing `datetime` returns 400 with `{"error": "..."}`, and rate-limited
   `/calculate` requests return 429 with a JSON message. The page shows the message in red under the form.
2. **Future dates give confusing output.** For a date about 2.5 months ahead the response is
   `-76 dana, 14 sati, …`, `-11 tjedana i 1 dan` and `0 godina, -2 mjeseca i -14 dana`. A commit message says
   unborn children are handled, but the current code does not handle them.
3. **Time zone.** `datetime.now()` uses the server's local time, while the browser sends local time without a zone.
   Visitors in another time zone (or around DST changes) get results that are off by hours.
4. **Dead code in `utils_dt.py`.** After `return` in `format_datetime()` there is an unreachable block (an old manual
   date-difference implementation that uses `start_date`/`end_date`, which are undefined there). It is safe but should be removed.
5. **`from utils_dt import *`** in `app.py`. Explicit imports would be clearer.
6. **Repetitive helpers.** The six three-form plural functions are identical apart from their words and could be one
   `plural(n, one, few, many)` function.
7. **Repo hygiene** (fixed): `wsgi.py` and `requirements.txt` are committed, and `.gitignore` covers `__pycache__/`, `bc-env/` and `*.sock`.
   The working tree still has file-mode-only changes (644 → 755) on some tracked files.
8. **Template details.** `lang="en"` on a Croatian page. The version string `v1.3` is hard-coded in HTML.
   Results are inserted with `.html()`; this is safe today because the server returns only numbers and fixed words.
9. **Production config.** `app.run(debug=True)` only runs when `app.py` is started directly, not under Gunicorn.
   The systemd unit runs Gunicorn as `User=root`; a non-root user (e.g. `www-data`) would be safer.
10. **No tests.** The plural helpers and the date math are easy to unit-test.

## Suggested next steps

1. Decide how to handle future dates (e.g. "do poroda je preostalo …") or reject them.
2. Remove the dead code and replace the plural helpers with one generic function.
3. Add pytest tests for the plural rules and for edge cases (month ends, leap years).
4. Configure `ProxyFix`/real client IP for rate limiting, and consider running the service as a non-root user.

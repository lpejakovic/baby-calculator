# baby-calculator

A small web app that calculates a baby's age from its date and time of birth.
The age is shown in three forms, with Croatian labels that use the correct grammatical number:

- weeks and days (`6 tjedana i 3 dana`)
- years, months and days (`1 mjesec i 14 dana`)
- total days, hours, minutes and seconds, updated live every second (`45 dana, 3 sata, 12 minuta i 5 sekundi`)

It also lists the next three milestones (month birthdays, birthdays, 100/500/1000… days) with a countdown.

The UI is in Croatian. Current version: **v2.1**.

## Features

- The age is calculated in the browser, in the visitor's own time zone, with no server request
- Separate date and time inputs; the time is optional (defaults to 00:00)
- Future dates are rejected
- Upcoming milestones: month birthdays (1–23 months), birthdays and day counts (100, 200, 300, 500, 1,000 … 10,000 days),
  with the date and "danas" / "sutra" / "za N dana"
- The last entered birth date is kept in `localStorage` and the result is shown straight away on the next visit
  (a v1.x cookie is moved over automatically)
- Responsive layout (phone to desktop), dark mode, WCAG AA contrast, keyboard focus styles, screen-reader announcements
- No external scripts or libraries
- Optional JSON API (`POST /calculate`), rate limited via Flask-Limiter (`1/second; 8/minute; 32/hour` per IP); the page itself is not limited

## Project structure

```
app.py                       Flask app, routes, rate limits, APP_VERSION
utils_dt.py                  Croatian plural helpers and date math for the API
wsgi.py                      WSGI entry point for Gunicorn
requirements.txt             Pinned Python dependencies
requirements-dev.txt         Test dependencies (pytest, QuickJS, Playwright)
pytest.ini                   pytest settings
tests/                       Python, JavaScript and browser tests
templates/index.html         Page and form
static/js/app.js             Age calculation, live counter, milestones, localStorage
static/styles/main.css       Styles (light and dark)
static/favicon.ico           Favicon (16 and 32 px)
static/apple-touch-icon.png  Home-screen icon (180 px)
static/images/icon-1024.webp Full-size icon artwork
docs/project_digest.md       Project digest / technical overview
docs/improvements.md         Open improvements and review
deploy/                      systemd unit and nginx site config
.github/workflows/tests.yml  CI
```

## Requirements

- Python 3.12
- Flask 3.1, Flask-Limiter 4.1, python-dateutil 2.9, Gunicorn 26 (for production); exact versions in `requirements.txt`

## Running locally

```bash
python3 -m venv bc-env
source bc-env/bin/activate
pip install -r requirements.txt
python app.py            # development server at http://127.0.0.1:5000 (debug=True)
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install --only-shell chromium   # once, for the browser tests
pytest                                               # all tests
pytest -m "not ui"                                   # without the browser tests
```

- `tests/test_utils_dt.py`: Croatian plural rules and date math for the API
- `tests/test_api.py`: `/` and `/calculate` with a frozen clock: valid and invalid input, future dates, time zones, rate limits
- `tests/test_js.py`: `static/js/app.js` in QuickJS: `calculateAge()` checked against `relativedelta` on 2,000 random dates
  plus month ends, leap years and DST; milestones against a `relativedelta` reference on 500 random dates;
  plurals, date parsing and text joining
- `tests/test_ui.py`: headless Chromium: live counter, milestones, saved date, cookie migration, future dates, visitor time zone,
  and layout at 320–1280 px in light and dark mode (no sideways scrolling, 16 px edges, 44 px touch targets)

GitHub Actions (`.github/workflows/tests.yml`) runs the unit tests and the browser tests on every push to `main` and on pull requests.

## API

The page doesn't use the API any more; it is kept for compatibility.

`POST /calculate`, form-encoded:

| Field | Required | Description |
|---|---|---|
| `datetime` | yes | Birth date and time, `YYYY-MM-DDTHH:MM` |
| `tz` | no | IANA time zone of the caller, e.g. `Europe/Zagreb`; without it the server's local time is used |

```bash
curl -X POST -d "datetime=2024-05-01T08:30" -d "tz=Europe/Zagreb" http://127.0.0.1:5000/calculate
```

Errors return HTTP 400 (invalid date, date in the future, unknown time zone) or 429 (rate limit) with `{"error": "..."}`.

Response:

```json
{
  "current":   "08.06.2024 14:10:00",
  "day_diff":  "38 dana, 5 sati, 40 minuta i 0 sekundi",
  "week_diff": "5 tjedana i 3 dana",
  "year_diff": "0 godina, 1 mjesec i 7 dana"
}
```

## Deployment

In production the app runs under Gunicorn as `www-data` (systemd), behind nginx. Both config files are in `deploy/`:

| File | Installed as |
|---|---|
| `deploy/baby-calculator.service` | `/etc/systemd/system/baby-calculator.service` |
| `deploy/nginx-bc.luka-pejakovic.from.hr.conf` | `/etc/nginx/sites-available/bc.luka-pejakovic.from.hr` |

- Gunicorn listens on `/run/baby-calculator/bc-calculator.sock` (created by systemd), with sandboxing options in the unit.
- nginx serves `/static/` and `/favicon.ico` from disk with long caching; Flask adds `?v=<mtime>` to static URLs so changed files are picked up.
- nginx adds HSTS, a strict Content-Security-Policy, `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy`.
  The CSP allows only same-origin scripts and styles, so keep JS and CSS in `static/` (no inline `<script>` or `style=""`).

To apply changes to the config files:

```bash
sudo cp deploy/baby-calculator.service /etc/systemd/system/
sudo cp deploy/nginx-bc.luka-pejakovic.from.hr.conf /etc/nginx/sites-available/bc.luka-pejakovic.from.hr
sudo systemctl daemon-reload && sudo systemctl restart baby-calculator
sudo nginx -t && sudo systemctl reload nginx
```

After code changes, only `sudo systemctl restart baby-calculator` is needed.

## Notes

- The API rejects birth dates in the future (HTTP 400).
- The API calculates in the `tz` time zone if given, otherwise in the server's local time; the page uses the visitor's time zone.
- Rate-limit counters are kept in memory, so they reset when the service restarts and are not shared between workers.

See [docs/project_digest.md](docs/project_digest.md) for a more detailed technical overview.

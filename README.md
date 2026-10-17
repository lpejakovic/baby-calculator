# baby-calculator

A small web app that calculates a baby's age from its date and time of birth.
The age is shown in three forms, with Croatian labels that use the correct grammatical number:

- weeks and days (`6 tjedana i 3 dana`)
- years, months and days (`1 mjesec i 14 dana`)
- total days, hours, minutes and seconds, updated live every second (`45 dana, 3 sata, 12 minuta i 5 sekundi`)

The UI is in Croatian. Current version: **v2.0**.

## Features

- The age is calculated in the browser, in the visitor's own time zone, with no server request
- Separate date and time inputs; the time is optional (defaults to 00:00)
- Future dates are rejected
- The last entered birth date is kept in `localStorage` and the result is shown straight away on the next visit
  (a v1.x cookie is moved over automatically)
- Responsive layout (phone to desktop), dark mode, WCAG AA contrast, keyboard focus styles, screen-reader announcements
- No external scripts or libraries
- Optional JSON API (`POST /calculate`), rate limited via Flask-Limiter (`1/second; 8/minute; 32/hour` per IP)

## Project structure

```
app.py                 Flask app, routes, rate limits, APP_VERSION
utils_dt.py            Croatian plural helpers and date math for the API
wsgi.py                WSGI entry point for Gunicorn
requirements.txt       Pinned Python dependencies
templates/index.html   Page and form
static/js/app.js       Age calculation, live counter, localStorage
static/styles/main.css Styles (light and dark)
static/favicon.ico     Favicon
docs/project_digest.md Project digest / technical overview
docs/improvements.md   Open improvements and review
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

## API

The page doesn't use the API any more; it is kept for compatibility.

`POST /calculate`, form-encoded, field `datetime` in `YYYY-MM-DDTHH:MM` format.

```bash
curl -X POST -d "datetime=2024-05-01T08:30" http://127.0.0.1:5000/calculate
```

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

In production the app runs under Gunicorn behind nginx, as a systemd service:

```
ExecStart=<project>/bc-env/bin/gunicorn --workers 1 --bind unix:bc-calculator.sock -m 007 wsgi:app
```

nginx proxies requests to the `bc-calculator.sock` Unix socket.

## Notes

- The API rejects birth dates in the future (HTTP 400).
- The API calculates with the server's local time (`datetime.now()`); the page uses the visitor's time zone.
- Rate-limit counters are kept in memory, so they reset when the service restarts and are not shared between workers.

See [docs/project_digest.md](docs/project_digest.md) for a more detailed technical overview.

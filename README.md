# baby-calculator

A small Flask web service that calculates a baby's age from its date and time of birth.
The age is shown in three forms, with Croatian labels that use the correct grammatical number:

- days, hours, minutes and seconds (`45 dana, 3 sata, 12 minuta i 5 sekundi`)
- years, months and days (`0 godina, 1 mjesec i 14 dana`)
- weeks and days (`6 tjedana i 3 dana`)

The UI is in Croatian. Current version: **v1.3**.

## Features

- Single-page form with a `datetime-local` input
- The last entered date of birth is kept in a cookie for 30 days
- Results are fetched over AJAX (`POST /calculate`) without reloading the page
- Rate limiting via Flask-Limiter (`1/second; 8/minute; 32/hour` per IP on each route)
- The submit button is disabled while a request runs and for 1 second after it finishes

## Project structure

```
app.py                 Flask app, routes and rate limits
utils_dt.py            Croatian plural helpers and date-difference calculation
wsgi.py                WSGI entry point for Gunicorn
templates/index.html   Page, form and jQuery AJAX logic
static/styles/main.css Styles
static/favicon.ico     Favicon
docs/project_digest.md Project digest / technical overview
```

## Requirements

- Python 3.12
- Flask 3.0, Flask-Limiter 3.7, python-dateutil 2.9, Gunicorn 22 (for production)

## Running locally

```bash
python3 -m venv bc-env
source bc-env/bin/activate
pip install flask flask-limiter python-dateutil gunicorn
python app.py            # development server at http://127.0.0.1:5000 (debug=True)
```

## API

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

- Times are calculated with the server's local time (`datetime.now()`), not the browser's time zone.
- Rate-limit counters are kept in memory, so they reset when the service restarts and are not shared between workers.

See [docs/project_digest.md](docs/project_digest.md) for a more detailed technical overview.

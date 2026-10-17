# baby-calculator

A small web app that shows a baby's age live: in weeks and days, in years, months and days, and as the total time
since birth, with the next milestones. It also follows a pregnancy. Croatian at `/`, English at `/en/`.

Live: <https://bc.luka-pejakovic.from.hr>

## Features

- Age in weeks and days, in years, months and days, and as real elapsed time ticking every second (summer/winter time
  changes included); correct Croatian and English plurals
- Upcoming milestones (month birthdays, birthdays, 100 … 10,000 days) with a countdown, and export to a calendar (`.ics`)
- Several children with optional names, and corrected age for babies born early
- Pregnancy mode from the due date, the last period, an IVF transfer or an ultrasound: weeks + days, trimester, due
  date with progress, and pregnancy milestones
- Share links and copyable summaries; backup to a file or a transfer link, with merging on restore
- Private by design: everything is calculated and stored in the browser; shared and transfer links keep their data
  after `#`, which browsers never send to the server
- Installable app (PWA) that works offline; light and dark mode; responsive from 320 px; accessibility checked with
  axe-core (WCAG 2.2 AA rules) in CI
- JSON API (`POST /calculate`) for other programs

How it works inside: [docs/architecture.md](docs/architecture.md). Changes per version: [CHANGELOG.md](CHANGELOG.md).

## Running locally

Python 3.12.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5000 (debug mode)
```

## Tests and linting

```bash
pip install -r requirements-dev.txt
pytest -m "not ui"                                   # fast: Python and the JavaScript logic (QuickJS), ~2 s
python -m playwright install --only-shell chromium   # once, for the browser tests
pytest -m ui                                         # browser behaviour, layout and the axe-core accessibility audit
ruff check                                           # Python
npm ci && npm run lint                               # JavaScript (ESLint)
```

GitHub Actions runs all of these on every pull request and push to `main`; `main` only accepts pull requests that
pass. The browser tests send the production Content-Security-Policy from `deploy/`, so anything it would block fails.

## API

`POST /calculate`, form-encoded or JSON:

| Field | Required | Description |
|---|---|---|
| `datetime` | yes | Birth date and time, `YYYY-MM-DDTHH:MM`, in the `tz` time zone |
| `tz` | no | IANA time zone, e.g. `Asia/Tokyo`; default `Europe/Zagreb` |
| `lang` | no | `hr` (default) or `en`, for the texts and error messages |

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"datetime": "2026-09-01T08:30", "tz": "Europe/Zagreb", "lang": "en"}' https://bc.luka-pejakovic.from.hr/calculate
```

```json
{
  "current":   "17 Oct 2026 15:30:45",
  "day_diff":  "46 days, 7 hours, 0 minutes and 45 seconds",
  "week_diff": "6 weeks and 4 days",
  "year_diff": "0 years, 1 month and 16 days",
  "age": {
    "calendar": {"years": 0, "months": 1, "days": 16},
    "weeks":    {"weeks": 6, "days": 4},
    "elapsed":  {"days": 46, "hours": 7, "minutes": 0, "seconds": 45, "total_seconds": 3999645}
  },
  "birth": "2026-09-01T08:30:00+02:00",
  "now":   "2026-10-17T15:30:45+02:00",
  "tz":    "Europe/Zagreb",
  "lang":  "en"
}
```

`age.calendar` and `age.weeks` follow the calendar; `age.elapsed` and `day_diff` are real elapsed time. Errors are
HTTP 400 or 429 (rate limit) with `{"error": "..."}` in the requested language.

## Development and deployment

Changes go through a branch and a pull request; CI must pass before merging. The live site is updated only with
`deploy/deploy.sh`, which deploys `origin/main` once CI has passed for that exact commit, restarts the service, checks
`/health` for the new version and rolls back if it doesn't appear (`--check` shows what it would do).

Production runs Gunicorn under systemd behind nginx; templates for both are in `deploy/`. nginx serves `/static/` with
long caching (Flask adds `?v=<mtime>` to static URLs) and sends the security headers, including a strict CSP: keep all
JavaScript and CSS in `static/`. A scheduled workflow checks `/health`, `/` and `/en/` every 15 minutes, and
Dependabot opens weekly update PRs.

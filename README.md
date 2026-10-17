# baby-calculator

A small web app that calculates a baby's age from its date and time of birth.
The age is shown in three forms, with Croatian labels that use the correct grammatical number:

- weeks and days (`6 tjedana i 3 dana`)
- years, months and days (`1 mjesec i 14 dana`)
- total days, hours, minutes and seconds of real elapsed time (summer/winter time changes included), updated live every second (`45 dana, 3 sata, 12 minuta i 5 sekundi`)

It also lists the next three milestones (month birthdays, birthdays, 100/500/1000… days) with a countdown.

A **pregnancy mode** ("Trudnoća") works from the due date or the first day of the last period (280-day rule) and shows
the pregnancy as weeks + days (`32+6 · 33. tjedan · 3. tromjesečje`), the due date with a countdown and progress bar,
and upcoming pregnancy milestones (14, 20, 28, 37 and 40 weeks).

The UI is in Croatian (`/`) and English (`/en/`). Current version: **v2.11**.

## Features

- The age is calculated in the browser, in the visitor's own time zone, with no server request
- Separate date and time inputs; the time is optional (defaults to 00:00)
- Future dates are rejected; the date limits follow "today" even when the page or app stays open overnight
- Upcoming milestones: month birthdays (1–23 months), birthdays and day counts (100, 200, 300, 500, 1,000 … 10,000 days),
  with the date and "danas" / "sutra" / "za N dana"
- Croatian and English: separate pages (`/` and `/en/`) with `hreflang` links, a language switch, English
  plurals, ordinals ("1st birthday") and dates ("4 Mar 2025"); saved data is shared between the languages
- Installable app (PWA) that works offline: manifest, service worker, and an "Instaliraj aplikaciju" button
  where the browser supports it
- Branded 404 page in both languages, `robots.txt`, and `sitemap.xml` with `hreflang`
- Link preview (Open Graph): title, description and a 1200×630 image for Viber, WhatsApp, Facebook and others
- Share link: `?d=2026-09-01` or `?d=2026-09-01T08:30` (optionally `&n=Ana` and `&due=YYYY-MM-DD`) adds that child next to the visitor's own
  children (or selects it if it's already there), `?t=2026-12-10` opens
  pregnancy mode with that due date. "Podijeli" opens the phone's
  share sheet (or copies the link), and "Kopiraj tekst" copies a one-line summary
- Corrected age for premature babies: an optional due date per child ("Prijevremeno rođeno dijete?") adds a
  "Korigirana dob" card with the age counted from the due date and the gestational age at birth
- "Dodaj u kalendar": downloads the milestones as an `.ics` file (baby: the next two years; pregnancy: up to the
  due date) with all-day events, a 9:00 reminder and stable ids, so importing again updates instead of duplicating
- Backup and restore ("Sigurnosna kopija"): download a JSON file, restore it, or copy a transfer link whose data
  stays after `#` (never sent to the server). Restoring merges: no duplicates, missing names and due dates are filled
  in, and different pregnancy data is replaced only after asking
- Several children: optional names, a chip per child to switch between them, "+ Dodaj dijete" and "Ukloni dijete"
- The children are kept in `localStorage` and the result is shown straight away on the next visit
  (a v2.x single saved date and a v1.x cookie are moved over automatically)
- Responsive layout (phone to desktop), dark mode, WCAG AA contrast, keyboard focus styles, screen-reader announcements
- No external scripts or libraries
- JSON API (`POST /calculate`) with plain numbers, time zones and Croatian or English texts, rate limited via
  Flask-Limiter (`1/second; 8/minute; 32/hour` per IP); the page itself is not limited

## Project structure

```
app.py                       Flask app, routes (/, /en/, /sw.js, /health, /robots.txt, /sitemap.xml, /calculate), 404 page,
                             rate limits, APP_VERSION
i18n.py                      Page texts in Croatian and English
utils_dt.py                  Croatian and English word forms and date math for the API
wsgi.py                      WSGI entry point for Gunicorn
requirements.txt             Pinned Python dependencies
requirements-dev.txt         Test and lint dependencies (pytest, QuickJS, Playwright, icalendar, axe-core, ruff)
pytest.ini                   pytest settings
tests/                       Python, JavaScript and browser tests
templates/index.html         Page and form
templates/404.html           Not-found page
templates/sitemap.xml        Sitemap with hreflang alternates
templates/sw.js              Service worker (rendered with the current asset URLs)
static/manifest.json         Web app manifest (Croatian; manifest-en.json for English)
static/js/app.js             Age and pregnancy calculation, live counter, milestones, sharing, localStorage
static/styles/main.css       Styles (light and dark)
static/favicon.ico           Favicon (16 and 32 px)
static/apple-touch-icon.png  Home-screen icon (180 px)
static/images/icon-1024.webp Full-size icon artwork
static/images/icon-*.png     App icons (192, 512, maskable 512)
static/images/og-image*.png  Link preview images (1200×630, Croatian and English), made by scripts/make_og_image.py
scripts/make_og_image.py     Regenerates the preview images (needs Pillow and DejaVu fonts)
docs/project_digest.md       Project digest / technical overview
docs/improvements.md         Improvement list (the 2026-10-17 review is complete)
deploy/                      systemd unit, nginx site config and deploy.sh
.github/workflows/tests.yml  CI: lint, unit tests, browser tests and accessibility audit
pyproject.toml               ruff settings
package.json                 ESLint (JavaScript tooling only; package-lock.json pins it)
eslint.config.js             ESLint settings
.github/workflows/uptime.yml Uptime check every 15 minutes
.github/dependabot.yml       Weekly dependency update PRs
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
python3 -m venv .venv && source .venv/bin/activate   # .venv/ is git-ignored
pip install -r requirements-dev.txt
python -m playwright install --only-shell chromium   # once, for the browser tests
pytest                                               # all tests
pytest -m "not ui"                                   # without the browser tests
```

- `tests/test_a11y.py`: axe-core accessibility audit (WCAG 2.2 A/AA and best practices) in both languages, light and
  dark mode, empty, baby (with corrected age), pregnancy, backup and error states, and the 404 page
- `tests/test_utils_dt.py`: Croatian plural rules and date math for the API
- `tests/test_api.py`: both pages, language links, 404 page, `robots.txt` and `sitemap.xml`, link preview, manifests and icons, service worker, and `/calculate` with a frozen clock: valid and invalid input, future dates, time zones, rate limits
- `tests/test_js.py`: `static/js/app.js` in QuickJS: `calculateAge()` checked against `relativedelta` on 2,000 random dates
  plus month ends, leap years and DST; milestones against a `relativedelta` reference on 500 random dates;
  corrected age (against `relativedelta`, limits, texts); calendar files (escaping, byte-based line folding,
  validated with the `icalendar` parser); backups (format, validation, merging, links); English plurals, ordinals, dates and texts (same keys in both languages); share links; saved children (migration, cleaning, adding shared, removing); pregnancy weeks, trimesters, due date, limits and milestones; plurals, date parsing and text joining
- `tests/test_ui.py`: headless Chromium: live counter, milestones, several children, pregnancy mode, English page
  and language switch, corrected age, calendar export, backup and restore, 404 page, real time across clock changes, date limits after midnight, share link and copy buttons, offline use,
  install button, saved date, cookie migration, future dates, visitor time zone,
  and layout at 320–1280 px in light and dark mode (no sideways scrolling, 16 px edges, 44 px touch targets)

The browser tests send the production Content-Security-Policy (read from `deploy/`), so anything it would block fails
a test.

## Linting

```bash
ruff check                # Python (settings in pyproject.toml)
npm ci && npm run lint    # JavaScript: ESLint recommended rules (eslint.config.js)
```

Without Node on the machine, `pip install nodejs-wheel-binaries` provides it inside the virtualenv.

GitHub Actions (`.github/workflows/tests.yml`) runs the linters, the unit tests and the browser tests on every push to `main` and on pull requests.

## API

The page calculates in the browser and doesn't use the API; it is kept for other programs.

`POST /calculate`, form-encoded or JSON (`Content-Type: application/json`):

| Field | Required | Description |
|---|---|---|
| `datetime` | yes | Birth date and time, `YYYY-MM-DDTHH:MM`, in the `tz` time zone |
| `tz` | no | IANA time zone, e.g. `Asia/Tokyo`; default `Europe/Zagreb` |
| `lang` | no | `hr` (default) or `en`, for the texts and error messages |

```bash
curl -X POST -d "datetime=2026-09-01T08:30" http://127.0.0.1:5000/calculate
curl -X POST -H "Content-Type: application/json" \
     -d '{"datetime": "2026-09-01T08:30", "tz": "Asia/Tokyo", "lang": "en"}' http://127.0.0.1:5000/calculate
```

Response (`lang=hr`, on 17 Oct 2026 at 15:30:45 in Zagreb):

```json
{
  "current":   "17.10.2026 15:30:45",
  "day_diff":  "46 dana, 7 sati, 0 minuta i 45 sekundi",
  "week_diff": "6 tjedana i 4 dana",
  "year_diff": "0 godina, 1 mjesec i 16 dana",
  "age": {
    "calendar": {"years": 0, "months": 1, "days": 16},
    "weeks":    {"weeks": 6, "days": 4},
    "elapsed":  {"days": 46, "hours": 7, "minutes": 0, "seconds": 45, "total_seconds": 3999645}
  },
  "birth": "2026-09-01T08:30:00+02:00",
  "now":   "2026-10-17T15:30:45+02:00",
  "tz":    "Europe/Zagreb",
  "lang":  "hr"
}
```

- The first four fields are the original API and keep their format; with `lang=en` they are English
  ("46 days, 7 hours, 0 minutes and 45 seconds", "17 Oct 2026 15:30:45").
- `age.calendar` and `age.weeks` use wall-clock time, like a calendar. `age.elapsed` and `day_diff` are real elapsed
  time, so they include the extra or missing hour of a summer/winter time change.
- Errors: HTTP 400 (invalid date, date in the future, unknown time zone, unsupported language) or 429 (rate limit,
  `1/second; 8/minute; 32/hour` per IP), as `{"error": "..."}` in the requested language.

## Development workflow

The live site runs from `/var/www/bc.luka-pejakovic.from.hr/baby-calculator`. **Nobody edits that folder**; it only
changes through `deploy/deploy.sh`. The server is shared with other sites, so heavy work (browser tests, the
accessibility audit) runs only in GitHub Actions.

1. Work in a separate clone (on the server: `~/baby-calculator`), on a branch.
2. Check locally with the light checks only: `ruff check` and `pytest -m "not ui"` (about 2 seconds).
3. Push the branch and open a pull request; CI runs lint, unit, browser and accessibility tests.
4. Merge when CI passes, then wait for CI on the merge commit on `main`.
5. Deploy: `deploy/deploy.sh` (or `deploy/deploy.sh --check` to see what it would do).

`deploy/deploy.sh` refuses to run when the live folder has local edits, when its commit isn't part of `origin/main`, or
when CI hasn't passed for exactly that commit. It fast-forwards, reinstalls `requirements.txt` if it changed, restarts
the service and waits for `/health` to report the new version; if that fails, it rolls back to the previous commit.

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

Code changes are deployed with `deploy/deploy.sh` (see above), which restarts the service. A sudoers rule in
`/etc/sudoers.d/baby-calculator` allows exactly that command without a password for the `ubuntu` user:

```
ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart baby-calculator
```

## Monitoring and updates

- `GET /health` returns `{"status": "ok", "version": "…"}` (never rate limited, not cached).
- `.github/workflows/uptime.yml` checks `/health`, `/` and `/en/` on the live site every 15 minutes (with retries).
  A failed run means the site is down; GitHub emails the failure to whoever last changed the schedule.
  GitHub pauses scheduled workflows after 60 days without repository activity; re-enable it under Actions if that happens.
- `.github/dependabot.yml` opens weekly update PRs for pip packages, npm (ESLint) and GitHub Actions (minor and patch updates
  grouped into one PR). The tests run on each PR; merge, then deploy with `deploy/deploy.sh`.

## Notes

- The API rejects birth dates in the future (HTTP 400).
- The API calculates in the `tz` time zone (default `Europe/Zagreb`); the page uses the visitor's time zone.
- Rate-limit counters are kept in memory, so they reset when the service restarts and are not shared between workers.

See [docs/project_digest.md](docs/project_digest.md) for a more detailed technical overview.

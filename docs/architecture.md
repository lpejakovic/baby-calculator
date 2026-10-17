# Architecture

## Overview

Flask serves two pages (`/` Croatian, `/en/` English) from one template, a service worker, `robots.txt`, `sitemap.xml`,
`/health` and the JSON API. Everything a visitor enters is calculated and stored in the browser; there is no database.

| Part | Files |
|---|---|
| Server | `app.py` (routes, rate limits, `APP_VERSION`), `i18n.py` (page texts, API errors), `utils_dt.py` (API date math and word forms), `wsgi.py` |
| Page | `templates/index.html`, `templates/404.html`, `static/styles/main.css` |
| Script | `static/js/texts.js`, `dates.js`, `calendar.js`, `data.js`, `card.js` (pure: no DOM or storage) and `app.js` (page code) |
| Offline | `templates/sw.js` (rendered with the current asset URLs), `static/manifest.json`, `manifest-en.json` |
| Deployment | `deploy/` (systemd unit, nginx template, `deploy.sh`, tested in `tests/test_deploy.py`) |
| Tests | `tests/` (pytest; QuickJS for the pure scripts; Playwright and axe-core in the browser) |

## Script

The six scripts are plain files sharing one namespace, `BC`, loaded in order with `defer`: `texts.js`, `dates.js`,
`calendar.js`, `data.js`, `card.js`, `app.js`. There is no build step. The pure files are what the QuickJS tests load; a test also
checks that `app.js` finds everything it takes from `BC`.

- **Time.** Calendar values (years, months, days, weeks) use wall-clock time stored as UTC milliseconds, so they follow
  the visitor's time zone and aren't shifted by summer/winter time. The live total ("Ukupno") uses real elapsed time
  (`wallToReal()`), so it gains or loses the hour of a clock change. `calculateAge()` clips months like `relativedelta`
  (31 Jan + 1 month = 28/29 Feb).
- **Milestones.** `babyMilestones()`: month birthdays (1–23 months), birthdays and day counts (100 … 10,000 days), by
  date only. `pregnancyMilestones()`: 14, 20, 28, 37 and 40 weeks. Lists are rebuilt when the date changes.
- **Corrected age.** With a due date for a child (at most 20 weeks after the birth), `correctedAge()` gives the
  gestational age at birth (280 days minus the days born early) and, after the due date, the age counted from it.
- **Pregnancy.** A pregnancy is stored as `{basis, date, …}` and turned into the first day of the last period (LMP):
  `due` − 280 days; `lmp` as is; `ivf` transfer − 14 − embryo age (3, 5 or 6 days); `ultrasound` scan − measured age.
  `convertPregnancy()` keeps the same pregnancy when the basis is switched. Accepted: 0 to 42 weeks.
- **Calendar.** `buildIcs()` writes RFC 5545: all-day, non-blocking events with a 9:00 reminder, CRLF, escaped text,
  lines folded at 75 bytes. Event ids come from the birth (or LMP) date and the milestone key, so re-importing updates.
- **Share picture.** `card.js`: `layoutCard()` wraps and fits the text (title, age, details, footer) into a 1080×1080
  square, shrinking everything until it fits above the footer, with the text measure passed in (canvas in the page,
  a stand-in in the tests); `drawCard()` paints it. The page shares the PNG as a file, or downloads it where sharing
  files isn't supported.
- **Texts.** `TEXT.hr` / `TEXT.en` in `texts.js` (same keys, checked by a test); pure functions take an optional `lang`
  that defaults to Croatian. The page texts are in `i18n.py`.

## Data in the browser

| Key | Content |
|---|---|
| `children` | `[{id, name, date, time, due}]`; `activeChild` is the selected id |
| `pregnancy` | `{basis: "due" \| "lmp" \| "ivf" \| "ultrasound", date, embryoDays?, gaWeeks?, gaDays?}` |
| `mode` | `"baby"` or `"pregnancy"` |
| `lang` cookie | `hr` or `en`, set by the language switch; `/` redirects to `/en/` for `en` |

After the visitor saves something, the page asks the browser to keep this data (`navigator.storage.persist()`), at
most once per visit and never on page load, since Firefox shows a prompt for it.

Links keep their data after `#`, which is never sent to the server:

- share a child: `#d=YYYY-MM-DD[THH:MM][&n=name][&due=YYYY-MM-DD]` (added next to existing children, never replacing them)
- share a pregnancy: `#t=YYYY-MM-DD` (due date)
- transfer everything: `#backup=<encoded JSON>`; the backup file has the same JSON:
  `{app: "baby-calculator", version: 1, exportedAt, children, activeChild, pregnancy, mode}`

Links are handled on load and on `hashchange`, then removed from the address bar. Restoring merges children by birth
date and time (no duplicates; missing names and due dates are filled in) and asks before replacing a different
pregnancy. Older `?d=` / `?t=` links still work.

## Offline and install

`/sw.js` is rendered with the two pages and every versioned static URL, so any change to a static file gives a new
cache name; old caches are deleted on activation. Pages are network-first with a cached fallback, static files
cache-first, and the API is never cached. Each language has its own manifest and start URL.

## API

`POST /calculate` reads form fields or JSON (`datetime`, optional `tz` defaulting to `Europe/Zagreb`, optional `lang`).
It returns the original text fields (`current`, `day_diff`, `week_diff`, `year_diff`) and plain numbers: `age.calendar`
and `age.weeks` on the wall clock, `age.elapsed` as real elapsed time. Errors are 400 with a message in the requested
language.

Croatian plurals: ends in 1 but not 11 → `1 sat`; ends in 2–4 but not 12–14 → `3 sata`; otherwise → `5 sati`. The API
uses accusative forms (`godinu`, `minutu`) because its text reads "Vaše dijete ima …"; the page uses nominative forms.

## Rate limiting

`/calculate` allows 1 request per second, 8 per minute and 32 per hour per client IP; pages, `/sw.js` and `/health` are
not limited, and nginx serves static files directly. Counters are kept in memory (one Gunicorn worker). nginx passes the
client IP and the app trusts exactly one proxy (`ProxyFix`), so forged `X-Forwarded-For` prefixes are ignored.

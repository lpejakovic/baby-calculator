# Improvements

_Review started 2026-10-17. Items are removed from this file as they are done; when it is empty, the review is complete._

## Plan

1. **Server setup:** nginx static files and security headers, non-root user (needs `sudo`).
2. **Features:** milestones, share link, PWA, pregnancy mode, several children.
3. **Quality:** tests and CI.

## 1. Server and security

| # | Problem | Suggested fix |
|---|---|---|
| 1 | **The service runs as `User=root`.** | Use `User=www-data` or a dedicated user. That also fixes the root-owned socket. |
| 2 | **No security headers** (HSTS, CSP, `X-Content-Type-Options`, `Referrer-Policy`). | Add `add_header` lines in nginx. The page no longer has inline scripts or third-party resources, so a strict `default-src 'self'` CSP works. |

## 2. Code cleanup and speed

- **`/calculate` API:** the page no longer uses it; it still uses the server's clock (CEST) and can reject a very recent birth from a visitor east of CEST as "in the future". Decide whether to keep it as a public API or remove it (along with `utils_dt.py` and `python-dateutil`).
- **Plural helpers:** if the API stays, replace the six near-identical Python functions with one `plural(n, forms)` function, like the one in `static/js/app.js`.
- **Imports:** change `from utils_dt import *` to explicit imports.
- **Static files:** Flask serves CSS, JS and the favicon with `cache-control: no-cache`. Serve `/static` from nginx with long caching and gzip/brotli (and add a version query string to bust the cache).
- **Favicon:** 92 KB. Use a small `.ico` (under 5 KB) plus an SVG icon and an `apple-touch-icon.png`.
- **Rate limit on `GET /`:** 8 page loads per minute is strict for a static page. Only `/calculate` needs a strict limit.
- **Storage:** limit counters are in memory. Fine with 1 worker; switch to Redis if workers are added.
- **Tests:**
  - `pytest` tests for the Python plural rules, month ends, leap years (29 Feb) and invalid input.
  - JavaScript tests for `calculateAge`, `plural`, `parseBirth` and `joinParts` (the script exports them via `module.exports`). During the rewrite they were checked against `relativedelta` with 20,000 random dates in QuickJS; turn that into a repeatable test.
- **CI:** GitHub Actions workflow that runs the tests on each push.

## 3. New features

1. **Milestones:** "100. dan za 12 dana", the "1000 dana" date, next month birthday, countdown to the first birthday.
2. **Pregnancy mode:** enter the due date or last period and get "34. tjedan + 2 dana", plus a countdown to the due date.
3. **Several children:** save names and dates in `localStorage` and switch between them.
4. **Share link:** `?d=2026-09-01T08:30` opens with the date filled in, plus a "Kopiraj" button for the text result.
5. **Install as an app (PWA):** manifest and service worker, so it installs on the home screen and works offline.
6. **Language:** HR/EN switch; the page title is still English.
7. **Link preview image:** `og:image` for nicer previews in Viber/WhatsApp (the other Open Graph tags are in place).

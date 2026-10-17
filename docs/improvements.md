# Improvements

_Review started 2026-10-17. Items are removed from this file as they are done; when it is empty, the review is complete._

## Plan

1. **Rewrite the page:** browser-side calculation with a live counter, no jQuery, result cards, `localStorage`, dark mode.
2. **Server setup:** nginx static files and security headers, non-root user (needs `sudo`).
3. **Features:** milestones, share link, PWA, pregnancy mode, several children.
4. **Quality:** tests and CI.

## 1. Fix first

| # | Problem | Suggested fix |
|---|---|---|
| 1 | **The age uses the server's clock** (CEST). Visitors in another time zone are off by hours, and every result is a snapshot from the moment of the request. Visitors east of CEST may also have a very recent birth rejected as "in the future". | Do the calculation in the browser (section 3). |
| 2 | **jQuery loads from a CDN without SRI**, only for one AJAX call and one DOM write. | Remove jQuery and use `fetch`. |
| 3 | **The service runs as `User=root`.** | Use `User=www-data` or a dedicated user. That also fixes the root-owned socket. |
| 4 | **No security headers** (HSTS, CSP, `X-Content-Type-Options`, `Referrer-Policy`). | Add `add_header` lines in nginx. |

## 2. Code cleanup and speed

- **Plural helpers:** replace the six near-identical functions with one `plural(n, ("godinu","godine","godina"))` function.
- **Imports:** change `from utils_dt import *` to explicit imports.
- **Version number:** `v1.3` is hard-coded in the HTML. Keep it in one constant and pass it to the template.
- **Static files:** Flask serves CSS and the favicon with `cache-control: no-cache`. Serve `/static` from nginx with long caching and gzip/brotli.
- **Favicon:** 92 KB. Use a small `.ico` (under 5 KB) plus an SVG icon and an `apple-touch-icon.png`.
- **Rate limit on `GET /`:** 8 page loads per minute is strict for a static page. Only `/calculate` needs a strict limit.
- **Storage:** limit counters are in memory. Fine with 1 worker; switch to Redis if workers are added.
- **Tests:** `pytest` tests for the plural rules (1, 2, 5, 11, 12, 21, 22, 111), month ends, leap years (29 Feb) and invalid input.
- **CI:** GitHub Actions workflow that runs the tests on each push.

## 3. Do the calculation in the browser

- **Correct time zone** for every visitor, automatically.
- **A live counter** that ticks every second instead of a frozen snapshot.
- **Instant results:** no server request, no rate-limit errors, works on a bad connection.
- The Flask app becomes a static page plus an optional API; `/calculate` can stay for compatibility.

## 4. New features

1. **Live counter** (comes with section 3).
2. **Milestones:** "100. dan za 12 dana", the "1000 dana" date, next month birthday, countdown to the first birthday.
3. **Pregnancy mode:** enter the due date or last period and get "34. tjedan + 2 dana", plus a countdown to the due date.
4. **Several children:** save names and dates in `localStorage` and switch between them.
5. **Share link:** `?d=2026-09-01T08:30` opens with the date filled in, plus a "Kopiraj" button for the text result.
6. **Install as an app (PWA):** manifest and service worker, so it installs on the home screen and works offline.
7. **Language:** HR/EN switch; the page title is still English.
8. **Dark mode** via `prefers-color-scheme`.

## 5. UX/UI and responsiveness

**Layout:**
- Two-column result layout above about 640px (with the result cards).

**Results:**
- Replace the double `<hr />` lines with 2–3 cards, each with a large number and a small label.
- Lead with weeks + days, which is how doctors count.
- Show "Trenutni datum i vrijeme" as small secondary text, or drop it.
- Loading state on the button ("Računam…"); not needed once the counter is live.

**Form:**
- Hint text "Vrijeme nije obavezno"; allow a date only, defaulting to 00:00.
- `Izračunaj razliku` → `Izračunaj dob`.
- Calculate automatically on load if a date is saved.
- `localStorage` instead of a cookie.

**Look and feel:**
- Softer, baby-friendly palette using CSS variables (makes dark mode easy).
- System font stack instead of Arial; slightly larger numbers.
- `<meta name="description">`, Open Graph tags and `theme-color`.

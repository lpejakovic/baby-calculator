# Improvements

_Review started 2026-10-17. Items are removed from this file as they are done; when it is empty, the review is complete._

Each new feature should come with tests in `tests/` (see the README).

## New features

1. **Milestones:** "100. dan za 12 dana", the "1000 dana" date, next month birthday, countdown to the first birthday.
2. **Pregnancy mode:** enter the due date or last period and get "34. tjedan + 2 dana", plus a countdown to the due date.
3. **Several children:** save names and dates in `localStorage` and switch between them.
4. **Share link:** `?d=2026-09-01T08:30` opens with the date filled in, plus a "Kopiraj" button for the text result.
5. **Install as an app (PWA):** manifest and service worker, so it installs on the home screen and works offline. Icons can be made from `static/images/icon-1024.webp`.
6. **Language:** HR/EN switch; the page title is still English.
7. **Link preview image:** `og:image` for nicer previews in Viber/WhatsApp (the other Open Graph tags are in place); `static/images/icon-1024.webp` could be used.

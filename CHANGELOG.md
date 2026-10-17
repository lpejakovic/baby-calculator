# Changelog

## 2.22 – 2026-10-17
- A one-line intro on the first visit (hidden once something is saved).
- Desktop (1024 px and wider): the form and the result side by side.
- Installed app on phones with a notch or home bar: the page keeps clear of them (safe-area insets).

## 2.21 – 2026-10-17
- The birth date is shown under the child's name, at the top of the result.
- Growth: the chart comes first, measurements are a table (value with its percentile under it), and the form to
  add a measurement is folded away once there are measurements.

## 2.20 – 2026-10-17
- Result first: with saved data the page opens on the result, and the form is folded away behind "Uredi podatke";
  after "Izračunaj" the result is scrolled to and focused. "Ukloni dijete" shows only while editing.
- Phones: no card around the page, a compact language switch (HR · EN · DE · IT), shorter mode labels,
  two-column pregnancy choices, "(nije obavezno)" in the labels, one "Podijeli" button with a short list,
  and the version number in the footer.

## 2.19 – 2026-10-17
- Removed the migration of data saved by versions before 2.6 (the 1.x cookie and the single saved date).
- The site's access log keeps only shortened client IPs and no query strings.

## 2.18 – 2026-10-17
- Growth chart: weight, length and head circumference with WHO percentiles from birth to 24 months, by corrected
  age for babies born early; measurements are stored with the child and included in backups.

## 2.17 – 2026-10-17
- German (`/de/`) and Italian (`/it/`), also in the API (`lang=de`, `lang=it`).
- The language switch lists all languages; action buttons wrap instead of squeezing long labels.

## 2.16 – 2026-10-17
- "Podijeli sliku": a 1080×1080 picture of the age or pregnancy, drawn in the browser, for messaging apps.

## 2.15 – 2026-10-17
- After something is saved, the app asks the browser to keep its data when space runs low.
- MIT license.

## 2.14 – 2026-10-17
- The page script is split into `texts.js`, `dates.js`, `calendar.js`, `data.js` and `app.js`.

## 2.13 – 2026-10-17
- Pregnancy dating from an IVF embryo transfer or an ultrasound.

## 2.12 – 2026-10-17
- Privacy note; share links keep their data after `#`, so it never reaches the server.
- The chosen language is remembered.

## 2.11 – 2026-10-17
- API: plain numbers, JSON input, `lang=en`, real elapsed time.

## 2.10 – 2026-10-17
- Milestones can be added to a calendar (`.ics`).

## 2.9 – 2026-10-17
- Backup and restore (file or transfer link).

## 2.8 – 2026-10-17
- Corrected age for babies born early.

## 2.7.1 – 2026-10-17
- The live total counts real elapsed time across summer/winter time changes.
- 404 page, `robots.txt`, `sitemap.xml`; date limits follow "today" when the page stays open.

## 2.7 – 2026-10-17
- English version (`/en/`) and a language switch.

## 2.6 – 2026-10-17
- Several children.

## 2.5 – 2026-10-17
- Pregnancy mode.

## 2.4 – 2026-10-17
- Installable app that works offline.

## 2.3 – 2026-10-17
- Link preview image.

## 2.2 – 2026-10-17
- Share link, "Podijeli" and "Kopiraj tekst".

## 2.1 – 2026-10-17
- Upcoming milestones.

## 2.0 – 2026-10-17
- Calculation in the browser with a live counter, result cards, dark mode and an accessible, responsive layout.

## 1.3 – 2024-06-08
- Corrected Croatian plurals; stricter rate limits.

## 1.2 – 2024-05-30
- Favicon and stylesheet.

## 1.1 – 2024-05-26
- Rate limiting.

## 1.0 – 2024-05-18
- First version.

# Improvements

_First review: started and completed on 2026-10-17 (see the version history in [project_digest.md](project_digest.md))._
_Second review: started on 2026-10-17. Items are removed from this file as they are done; when it is empty, the review is complete._

Each new feature should come with tests in `tests/` (see the README).

Baseline for this review: axe-core found 0 accessibility issues (WCAG 2.2 AA and best practices) in both languages,
light and dark mode, baby and pregnancy results; the page weighs about 16 KB gzipped; all packages are current.

## Plan

1. **Next:** split `app.js`.

## 1. Small site fixes

1. **Split `app.js`** (828 lines) into modules: date math, texts and page code.

## 2. New features

1. **Privacy note:** "Podaci ostaju samo na vašem uređaju", visible without opening anything (the backup section
   already says so when opened).
2. **Remember the language:** open the chosen language next time, or suggest English once to English-language browsers.
3. **More pregnancy dating options:** IVF transfer date, or a date from an ultrasound.

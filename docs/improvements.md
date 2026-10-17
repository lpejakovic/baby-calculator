# Improvements

Ideas for future work, most useful first. Each new feature should come with tests in `tests/` (see the README).
Earlier reviews are reflected in [CHANGELOG.md](../CHANGELOG.md).

## Features

1. **Measurements for the paediatrician:** a print view of the chart and table, and/or a CSV export.
2. **Manifest screenshots and shortcuts** (e.g. straight to pregnancy) for a richer install dialog on Android.

## Code and operations

3. **Split `app.js` again** (~990 lines): growth, share picture and backup into their own files.
4. **Uptime check for `/de/`, `/it/` and one static file**, which would catch a broken nginx static alias.
5. **Static cache-busting by content hash** instead of the file's mtime.

The pregnancy week-by-week idea was dropped on purpose: the app calculates from the user's own dates and doesn't
host medical content that would need sourcing, review and maintenance in four languages.

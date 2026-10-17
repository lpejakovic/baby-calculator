# Improvements

Ideas for future work, most useful first. Each new feature should come with tests in `tests/` (see the README).
Earlier reviews are reflected in [CHANGELOG.md](../CHANGELOG.md).

## Project

1. **Remove the old data migrations** (the v1.x `datetime` cookie and the single `birth` key) after 2026-11-17.

## Data safety

2. **Shorter IP addresses in the server logs** (nginx: drop the last part of each address), matching the privacy note.

## Features

3. **Pregnancy week by week:** a short note per week (development, size). Needs carefully sourced content.
4. **Growth chart:** weight, length and head size against the WHO growth standards, stored in the browser.
5. **More languages:** the texts are already in one place per language; German or Slovenian would follow the English
   pattern.

## Code

6. **API in its own module** (`api.py`), keeping `app.py` to the pages, as the server code grows.

# Improvements

Ideas for future work, most useful first. Each new feature should come with tests in `tests/` (see the README).
Earlier reviews are reflected in [CHANGELOG.md](../CHANGELOG.md).

## Project

1. **License.** The repository is public but has no license, so nobody may legally reuse the code. Add one
   (e.g. MIT) or state that it isn't open for reuse.
2. **Test `deploy/deploy.sh` in CI** with a throwaway repository and stand-ins for `systemctl`, `curl` and `gh`,
   including the rollback path.
3. **Remove the old data migrations** (the v1.x `datetime` cookie and the single `birth` key) after 2026-11-17.

## Data safety

4. **Ask the browser to keep the data** (`navigator.storage.persist()`), so saved children aren't cleared when the
   device runs low on space. Installed apps usually get this automatically.
5. **Shorter IP addresses in the server logs** (nginx: drop the last part of each address), matching the privacy note.

## Features

6. **Share card:** a picture with the name and age ("Ana: 6 mjeseci") for messaging apps, drawn in the browser.
7. **Pregnancy week by week:** a short note per week (development, size). Needs carefully sourced content.
8. **Growth chart:** weight, length and head size against the WHO growth standards, stored in the browser.
9. **More languages:** the texts are already in one place per language; German or Slovenian would follow the English
   pattern.

## Code

10. **API in its own module** (`api.py`), keeping `app.py` to the pages, as the server code grows.

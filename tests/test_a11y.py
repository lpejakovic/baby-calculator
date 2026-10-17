"""Accessibility audit with axe-core (WCAG 2.2 A/AA and best practices) in every page state."""
import pytest

pytest.importorskip("playwright.sync_api")
axe_module = pytest.importorskip("axe_playwright_python.sync_playwright")

pytestmark = pytest.mark.ui

RULES = {"runOnly": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]}


def baby(page):
    page.fill("#child-name", "Ana")
    page.fill("#birth-date", "2026-08-01")
    page.click("#premature summary")
    page.fill("#due-date", "2026-10-01")
    page.click("#birth-form button[type=submit]")


def pregnancy(page):
    page.click(".mode-switch label:nth-of-type(2)")
    page.fill("#pregnancy-date", "2026-12-06")
    page.click("#pregnancy-form button")


def backup(page):
    baby(page)
    page.click("#backup summary")


def error(page):
    page.evaluate("document.getElementById('birth-date').removeAttribute('max')")
    page.fill("#birth-date", "2099-01-01")
    page.click("#birth-form button[type=submit]")


STATES = {"empty": None, "baby": baby, "pregnancy": pregnancy, "backup": backup, "error": error}


def audit(page):
    violations = axe_module.Axe().run(page, options=RULES).response["violations"]
    return [f"{v['id']} ({v['impact']}): {v['help']} – {[n['target'] for n in v['nodes'][:3]]}" for v in violations]


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("path", ["", "en/"])
@pytest.mark.parametrize("state", STATES)
def test_page_is_accessible(browser, base_url, path, scheme, state):
    context = browser.new_context(color_scheme=scheme, viewport={"width": 390, "height": 900},
                                  timezone_id="Europe/Zagreb")
    page = context.new_page()
    page.clock.set_fixed_time("2026-10-17T12:00:00+02:00")
    page.goto(base_url + path)
    if STATES[state]:
        STATES[state](page)
    page.mouse.move(0, 0)
    assert audit(page) == []
    context.close()


@pytest.mark.parametrize("path", ["nope", "en/nope"])
def test_not_found_page_is_accessible(browser, base_url, path):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + path)
    assert audit(page) == []
    context.close()

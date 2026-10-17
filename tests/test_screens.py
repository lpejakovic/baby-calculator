"""Temporary: full-page screenshots of the main states for a UX review (CI artifacts). Not for merging."""
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

NOW = "2026-10-17T12:00:00+02:00"


def shot(page, name):
    folder = os.environ.get("ARTIFACTS_DIR")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / name), full_page=True)


def open_at(browser, base_url, width, scheme="light", path=""):
    context = browser.new_context(viewport={"width": width, "height": 844}, color_scheme=scheme,
                                  timezone_id="Europe/Zagreb", device_scale_factor=1, has_touch=width < 600,
                                  is_mobile=width < 600)
    page = context.new_page()
    page.clock.set_fixed_time(NOW)
    page.goto(base_url + path)
    return context, page


def baby(page, name="Ana", date="2025-03-04", time="17:45"):
    page.fill("#child-name", name)
    page.fill("#birth-date", date)
    page.fill("#birth-time", time)
    page.click("#birth-form button[type=submit]")


@pytest.mark.parametrize("width, scheme", [(390, "light"), (360, "dark")])
def test_screens(browser, base_url, width, scheme):
    tag = f"{width}-{scheme}"
    context, page = open_at(browser, base_url, width, scheme)
    shot(page, f"{tag}-01-empty.png")
    baby(page)
    shot(page, f"{tag}-02-baby.png")
    page.click("#add-child")
    page.fill("#child-name", "Marko")
    page.fill("#birth-date", "2026-08-01")
    page.click("#premature summary")
    page.fill("#due-date", "2026-10-01")
    page.click("#birth-form button[type=submit]")
    page.click("#growth summary")
    page.click("#growth .sex label.radio >> nth=1")
    for date, weight, length in [("2026-08-01", "1,9", "42"), ("2026-09-01", "2,6", "46"), ("2026-10-15", "3,6", "51")]:
        page.fill("#measure-date", date)
        page.fill("#measure-weight", weight)
        page.fill("#measure-length", length)
        page.click("#measure-form button[type=submit]")
    page.click("#backup summary")
    page.mouse.click(1, 1)
    shot(page, f"{tag}-03-second-child-growth-backup.png")
    page.click(".mode-switch label:nth-of-type(2)")
    page.fill("#pregnancy-date", "2026-12-06")
    page.click("#pregnancy-form button[type=submit]")
    shot(page, f"{tag}-04-pregnancy.png")
    page.click("#pregnancy-form label.radio:has-text('Ultrazvuku')")
    shot(page, f"{tag}-05-pregnancy-ultrasound.png")
    context.close()


def test_screens_german_and_desktop(browser, base_url):
    context, page = open_at(browser, base_url, 360, path="de/")
    baby(page)
    shot(page, "360-de-baby.png")
    context.close()
    context, page = open_at(browser, base_url, 1280)
    baby(page)
    shot(page, "1280-baby.png")
    context.close()

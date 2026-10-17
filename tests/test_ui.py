"""Browser tests: page behaviour and responsive layout in headless Chromium."""
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from conftest import BROWSER

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

BIRTH_DATE, BIRTH_TIME = "2025-03-04", "17:45"


@pytest.fixture
def open_page(browser, base_url):
    contexts, errors = [], []

    def _open(**context_options):
        context = browser.new_context(**context_options)
        contexts.append(context)
        context.add_init_script("""window.__csp = []; document.addEventListener('securitypolicyviolation', (e) =>
            window.__csp.push([e.violatedDirective, e.sourceFile, e.lineNumber, e.sample, e.blockedURI]));""")
        page = context.new_page()
        page.on("console", lambda m: m.type == "error" and print("CSPDIAG", page.evaluate("JSON.stringify(window.__csp)")))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(base_url)
        return page

    yield _open
    for context in contexts:
        context.close()
    assert errors == []


def edit(page):
    """Opens the form when it is folded away behind "Uredi podatke" (while a result is shown)."""
    if page.is_visible("#edit-entry"):
        page.click("#edit-entry")


def share(page, button):
    """Clicks one of the buttons under "Podijeli"."""
    if page.is_hidden("#share-menu"):
        page.click("#share-toggle")
    page.click(button)


def calculate(page, date=BIRTH_DATE, time=BIRTH_TIME, name=None):
    edit(page)
    if name is not None:
        page.fill("#child-name", name)
    page.fill("#birth-date", date)
    page.fill("#birth-time", time)
    page.click("#birth-form button[type=submit]")


def poll(page, expression, timeout=5):
    """Waits until expression is truthy and returns it. Unlike page.wait_for_function, this works under
    the production CSP, which (rightly) blocks the eval that wait_for_function uses."""
    for _ in range(int(timeout * 10)):
        value = page.evaluate(expression)
        if value:
            return value
        page.wait_for_timeout(100)
    raise AssertionError(f"Timed out waiting for {expression}")


@pytest.mark.webkit
def test_result_and_live_counter(open_page):
    page = open_page()
    assert page.is_hidden("#result")
    calculate(page)
    assert page.is_visible("#result")
    assert page.text_content("#born-at") == "Rođenje: 04.03.2025. u 17:45"
    # The birth date is at the top of the result, before the cards
    assert page.evaluate("document.getElementById('born-at').getBoundingClientRect().bottom <= document.querySelector('#result .cards').getBoundingClientRect().top")
    assert page.text_content("#announce").startswith("Dob: ")
    first = page.text_content("#age-total")
    sync_api.expect(page.locator("#age-total")).not_to_have_text(first, timeout=3000)


@pytest.mark.webkit
def test_milestones(open_page):
    page = open_page()
    calculate(page)
    items = page.locator("#milestones li")
    assert items.count() == 3
    for i in range(3):
        assert items.nth(i).locator(".milestone-label").text_content()
        when = items.nth(i).locator(".milestone-when").text_content()
        assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}\. · (danas|sutra|za \d+ dana?)", when), when
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", items.nth(i).locator("time").get_attribute("datetime"))


def test_opens_shared_link(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + "?d=2026-09-01T08:30")
    assert page.input_value("#birth-date") == "2026-09-01"
    assert page.input_value("#birth-time") == "08:30"
    assert page.is_visible("#result")
    assert page.url == base_url  # parameter removed after loading
    assert page.evaluate("JSON.parse(localStorage.getItem('children'))") == [
        {"id": 1, "name": "", "date": "2026-09-01", "time": "08:30", "due": ""}]
    context.close()


def test_invalid_shared_link_is_ignored(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + "?d=2026-02-30")
    assert page.input_value("#birth-date") == ""
    assert page.is_hidden("#result")
    context.close()


@pytest.mark.webkit
def test_share_uses_share_sheet(open_page, base_url):
    page = open_page()
    page.evaluate("navigator.share = async (data) => { window.sharedData = data; }")
    calculate(page)
    share(page, "#share-link")
    data = poll(page, "window.sharedData || null")
    assert data["url"] == base_url + "#d=2025-03-04T17:45"
    assert data["text"].startswith("Dob: ")
    assert data["text"].endswith("Rođenje: 04.03.2025. u 17:45.")


def test_share_falls_back_to_copying_link(open_page, base_url):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    calculate(page, time="")
    share(page, "#share-link")
    sync_api.expect(page.locator("#share-status")).not_to_have_text("")
    assert page.text_content("#share-status") == "Poveznica je kopirana."
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "#d=2025-03-04"


def test_copy_text(open_page):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    calculate(page, time="")
    share(page, "#copy-text")
    sync_api.expect(page.locator("#share-status")).not_to_have_text("")
    assert page.text_content("#share-status") == "Tekst je kopiran."
    text = page.evaluate("navigator.clipboard.readText()")
    assert re.fullmatch(r"Dob: .+ \(.+\)\. Rođenje: 04\.03\.2025\.", text), text


@pytest.mark.webkit
def test_works_offline(open_page):
    page = open_page()
    # Fails after 10 s (instead of hanging) if the service worker never takes control
    poll(page, "navigator.serviceWorker.controller !== null || null", timeout=10)
    page.context.set_offline(True)
    page.reload()
    calculate(page)
    assert page.is_visible("#result")
    assert page.text_content("#age-weeks")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") != "rgba(0, 0, 0, 0)"  # CSS from cache


def test_install_button(open_page):
    page = open_page()
    assert page.is_hidden("#install-app")
    # Simulate Chrome offering installation
    page.evaluate("""() => {
        const event = new Event('beforeinstallprompt', { cancelable: true });
        event.prompt = () => { window.installPrompted = true; };
        event.userChoice = Promise.resolve({ outcome: 'accepted' });
        window.dispatchEvent(event);
    }""")
    assert page.is_visible("#install-app")
    page.click("#install-app")
    assert page.evaluate("window.installPrompted") is True
    assert page.is_hidden("#install-app")


def due_in(days):
    return (date.today() + timedelta(days=days)).isoformat()


def calculate_pregnancy(page, due_date):
    page.click(".mode-switch >> text=Trudnoća")
    edit(page)
    page.fill("#pregnancy-date", due_date)
    page.click("#pregnancy-form button")


@pytest.mark.webkit
def test_pregnancy_mode(open_page):
    page = open_page()
    assert page.is_hidden("#pregnancy-form")
    calculate_pregnancy(page, due_in(50))  # 280 - 50 = 230 days = 32+6
    assert page.is_hidden("#birth-form") and page.is_hidden("#result")
    assert page.text_content("#pregnancy-duration") == "32 tjedna i 6 dana"
    assert page.text_content("#pregnancy-detail") == "32+6 · 33.\u00a0tjedan · 3.\u00a0tromjesečje"
    assert page.text_content("#pregnancy-countdown") == "za 50 dana"
    assert page.get_attribute("#pregnancy-due", "datetime") == due_in(50)
    assert page.evaluate("document.getElementById('pregnancy-progress').value") == 230
    assert page.text_content("#pregnancy-progress-text") == "82 % trudnoće"
    labels = page.locator("#pregnancy-milestones .milestone-label").all_text_contents()
    assert labels == ["Donošena trudnoća", "Termin poroda"]
    assert page.text_content("#announce").startswith("Trudnoća: 32 tjedna i 6 dana")


def test_pregnancy_basis_switch_keeps_pregnancy(open_page):
    page = open_page()
    calculate_pregnancy(page, due_in(50))
    edit(page)
    page.click("text=Zadnjoj menstruaciji")
    assert page.text_content("#pregnancy-date-label") == "Prvi dan zadnje menstruacije"
    assert page.input_value("#pregnancy-date") == due_in(50 - 280)
    assert page.text_content("#pregnancy-duration") == "32 tjedna i 6 dana"


def test_pregnancy_is_remembered_with_mode(open_page):
    page = open_page()
    calculate(page)
    calculate_pregnancy(page, due_in(100))
    page.reload()
    assert page.is_visible("#pregnancy-result")
    assert page.is_checked("input[value=pregnancy]")
    page.click(".mode-switch >> text=Beba")
    assert page.is_visible("#result")  # the baby's date is still there
    assert page.input_value("#birth-date") == BIRTH_DATE


def test_pregnancy_errors(open_page):
    page = open_page()
    page.click(".mode-switch >> text=Trudnoća")
    page.evaluate("document.getElementById('pregnancy-date').removeAttribute('min')")
    page.fill("#pregnancy-date", due_in(-20))
    page.click("#pregnancy-form button")
    assert page.text_content("#error") == "Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba”."
    assert page.is_hidden("#pregnancy-result") and page.is_hidden("#share")


def test_shared_pregnancy_link_and_copy(browser, base_url):
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(base_url + "?t=" + due_in(50))
    assert page.url == base_url
    assert page.is_checked("input[value=pregnancy]")
    assert page.text_content("#pregnancy-duration") == "32 tjedna i 6 dana"
    share(page, "#copy-text")
    sync_api.expect(page.locator("#share-status")).not_to_have_text("")
    due = date.today() + timedelta(days=50)
    assert page.evaluate("navigator.clipboard.readText()") == \
        f"Trudnoća: 32 tjedna i 6 dana (33. tjedan). Termin: {due:%d.%m.%Y}."
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    share(page, "#share-link")
    sync_api.expect(page.locator("#share-status")).to_have_text("Poveznica je kopirana.")
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "#t=" + due_in(50)
    context.close()


@pytest.mark.parametrize("width", [320, 360, 768, 1280])
def test_pregnancy_layout(open_page, width):
    page = open_page(viewport={"width": width, "height": 900})
    calculate_pregnancy(page, due_in(50))
    layout = page.evaluate("""() => ({
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        targets: [...document.querySelectorAll('button, input:not([type=radio]), .mode-switch label, .basis label')]
            .filter(el => el.checkVisibility())
            .map(el => Math.round(el.getBoundingClientRect().height)),
    })""")
    assert not layout["overflow"]
    assert min(layout["targets"]) >= 44, layout["targets"]


def chips(page):
    return page.locator("#child-list .chip").all_text_contents()


def active_chip(page):
    return page.locator("#child-list .chip:has(input:checked)").text_content()


@pytest.mark.webkit
def test_several_children(open_page):
    page = open_page()
    assert page.is_hidden("#children")
    calculate(page, "2025-03-04", "17:45", name="Ana")
    assert chips(page) == ["Ana"] and page.text_content("#result-title") == "Ana"
    page.click("#add-child")
    assert page.input_value("#child-name") == "" and page.input_value("#birth-date") == ""
    assert page.is_hidden("#result") and page.is_hidden("#remove-child")
    calculate(page, "2026-09-01", "08:30", name="Marko")
    assert chips(page) == ["Ana", "Marko"] and active_chip(page) == "Marko"
    marko_weeks = page.text_content("#age-weeks")

    page.click("#child-list >> text=Ana")
    assert page.input_value("#child-name") == "Ana" and page.input_value("#birth-date") == "2025-03-04"
    assert page.text_content("#result-title") == "Ana"
    assert page.text_content("#age-weeks") != marko_weeks

    page.reload()  # the selected child is remembered
    assert chips(page) == ["Ana", "Marko"] and active_chip(page) == "Ana"
    assert page.is_visible("#result")


def test_rename_and_unnamed_child(open_page):
    page = open_page()
    calculate(page)
    assert chips(page) == ["Dijete 1"]
    # No name: the heading is only for screen readers
    assert "visually-hidden" in page.get_attribute("#result-title", "class")
    edit(page)
    page.fill("#child-name", "Iva")
    assert chips(page) == ["Iva"] and page.text_content("#result-title") == "Iva"
    assert "visually-hidden" not in page.get_attribute("#result-title", "class")


def test_remove_child(open_page):
    page = open_page()
    calculate(page, "2025-03-04", name="Ana")
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    edit(page)
    page.click("#remove-child")
    assert chips(page) == ["Ana"] and page.input_value("#child-name") == "Ana"
    assert page.text_content("#undo-text") == "Uklonjeno: „Marko”."
    edit(page)
    page.click("#remove-child")
    assert page.is_hidden("#children") and page.is_hidden("#result")
    assert page.input_value("#birth-date") == ""
    assert page.evaluate("localStorage.getItem('children')") == "[]"


@pytest.mark.webkit
def test_remove_child_can_be_undone(open_page):
    page = open_page(viewport={"width": 390, "height": 844})
    calculate(page, "2025-03-04", name="Ana")
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    edit(page)
    page.click("#remove-child")  # no browser dialog: removed straight away, with "Poništi"
    assert chips(page) == ["Ana"]
    assert page.is_visible("#undo") and page.text_content("#undo-button") == "Poništi"
    assert page.evaluate("document.activeElement.id") == "undo-button"
    assert page.text_content("#announce") == "Uklonjeno: „Marko”."
    keep_artifact(page.screenshot(), "undo-hr-phone.png")
    page.click("#undo-button")
    assert chips(page) == ["Ana", "Marko"] and active_chip(page) == "Marko"
    assert page.is_hidden("#undo") and page.is_visible("#result")
    page.reload()  # the restored list is saved
    assert chips(page) == ["Ana", "Marko"]


def test_undo_goes_away(open_page):
    page = open_page()
    page.clock.install()
    page.reload()
    calculate(page, "2025-03-04", name="Ana")
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    edit(page)
    page.click("#remove-child")
    page.clock.run_for(11_000)
    assert page.is_visible("#undo")  # kept while the focus is on "Poništi"
    page.click("h1")
    page.clock.run_for(3_000)
    assert page.is_hidden("#undo")
    edit(page)
    page.click("#remove-child")  # Ana, the last one
    assert page.is_visible("#undo")
    calculate(page, "2026-01-01", name="Iva")  # saving something else ends the chance to undo
    assert page.is_hidden("#undo") and chips(page) == ["Iva"]


def test_shared_link_adds_child(open_page, base_url):
    page = open_page()
    calculate(page, "2025-03-04", name="Ana")
    page.goto(base_url + "#d=2026-09-01T08:30&n=Marko")  # same page: handled on hashchange
    assert chips(page) == ["Ana", "Marko"] and active_chip(page) == "Marko"
    page.goto(base_url + "#d=2026-09-01T08:30&n=Marko")  # opening it again doesn't duplicate
    assert chips(page) == ["Ana", "Marko"]


def test_named_child_copy_and_share(open_page, base_url):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    calculate(page, "2025-03-04", "", name="Ana Marija")
    share(page, "#copy-text")
    sync_api.expect(page.locator("#share-status")).not_to_have_text("")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert re.fullmatch(r"Ana Marija: .+ \(.+\)\. Rođenje: 04\.03\.2025\.", copied), copied
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    share(page, "#share-link")
    sync_api.expect(page.locator("#share-status")).to_have_text("Poveznica je kopirana.")
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "#d=2025-03-04&n=Ana%20Marija"


@pytest.mark.parametrize("width", [320, 360, 1280])
def test_children_layout(open_page, width):
    page = open_page(viewport={"width": width, "height": 900})
    for name in ["Ana", "Marko Antonio Petrović", "Iva", "Dijete s vrlo dugim imenom za test"]:
        calculate(page, "2025-03-04", name=name)
        page.click("#add-child")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    heights = page.evaluate("[...document.querySelectorAll('.chip')].map(c => Math.round(c.getBoundingClientRect().height))")
    assert not overflow
    assert len(heights) == 5 and min(heights) >= 44


CROATIAN = re.compile(r"[čćžšđČĆŽŠĐ]|\\b(dana?|tjedn|mjesec|godin|sati?|minut|sekund|rođ|danas|sutra)", re.I)


@pytest.mark.parametrize("path, title, home", [("nope", "Stranica nije pronađena", "/"), ("en/nope", "Page not found", "/en/")])
def test_not_found_page(browser, base_url, path, title, home):
    # Not open_page: the browser logs the 404 itself as a console error, which is expected here
    context = browser.new_context()
    page = context.new_page()
    response = page.goto(base_url + path)
    assert response.status == 404
    assert page.text_content("h1") == title
    page.click("a.button")
    assert page.url == base_url + home.lstrip("/")
    context.close()


@pytest.mark.webkit
def test_english_page(open_page, base_url):
    page = open_page()
    page.goto(base_url + "en/")
    calculate(page, "2025-03-04", "17:45", name="Ana")
    assert re.fullmatch(r"\d+ weeks? and \d+ days?|\d+ weeks?", page.text_content("#age-weeks"))
    assert page.text_content("#born-at") == "Born: 4 Mar 2025 at 17:45"
    for item in page.locator("#milestones li").all():
        when = item.locator(".milestone-when").text_content()
        assert re.fullmatch(r"\d{1,2} [A-Z][a-z]{2} \d{4} · (today|tomorrow|in \d+ days)", when), when
    text = page.text_content("main").replace("Pejaković", "")  # the author's name in the footer
    assert not CROATIAN.search(text), CROATIAN.search(text)


def test_english_pregnancy(open_page, base_url):
    page = open_page()
    page.goto(base_url + "en/")
    page.click(".mode-switch >> text=Pregnancy")
    page.fill("#pregnancy-date", due_in(50))
    page.click("#pregnancy-form button")
    assert page.text_content("#pregnancy-duration") == "32 weeks and 6 days"
    assert page.text_content("#pregnancy-detail") == "32+6 · week\u00a033 · third\u00a0trimester"
    assert page.text_content("#pregnancy-countdown") == "in 50 days"
    assert page.text_content("#pregnancy-progress-text") == "82% of pregnancy"
    assert page.locator("#pregnancy-milestones .milestone-label").all_text_contents() == ["Full term", "Due date"]
    edit(page)
    page.click("text=Last period")
    assert page.text_content("#pregnancy-date-label") == "First day of last period"


def test_english_errors_and_confirm(open_page, base_url):
    page = open_page()
    page.goto(base_url + "en/")
    future = (date.today() + timedelta(days=2)).isoformat()
    page.evaluate("document.getElementById('birth-date').removeAttribute('max')")
    calculate(page, future, "10:00")
    assert page.text_content("#error") == "The date of birth can’t be in the future. For a pregnancy, choose “Pregnancy”."
    calculate(page, "2025-03-04", name="Ana")
    edit(page)
    page.click("#remove-child")
    assert page.text_content("#undo-text") == "Removed: “Ana”."
    assert page.text_content("#undo-button") == "Undo"


def test_english_copy_and_share(open_page, base_url):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.goto(base_url + "en/")
    calculate(page, "2025-03-04", "", name="Ana")
    share(page, "#copy-text")
    sync_api.expect(page.locator("#share-status")).to_have_text("Text copied.")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert re.fullmatch(r"Ana: .+ \(.+\)\. Born: 4 Mar 2025\.", copied), copied
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    share(page, "#share-link")
    sync_api.expect(page.locator("#share-status")).to_have_text("Link copied.")
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "en/#d=2025-03-04&n=Ana"


def test_language_switch_keeps_data(open_page, base_url):
    page = open_page()
    calculate(page, "2025-03-04", name="Ana")
    croatian_weeks = page.text_content("#age-weeks")
    page.click(".lang-switch a")
    assert page.url == base_url + "en/"
    assert page.evaluate("document.documentElement.lang") == "en"
    assert page.input_value("#child-name") == "Ana" and page.is_visible("#result")
    assert page.text_content("#age-weeks").split()[0] == croatian_weeks.split()[0]  # same number of weeks
    page.click(".lang-switch a")
    assert page.url == base_url and page.text_content("#age-weeks") == croatian_weeks


def test_english_works_offline(open_page, base_url):
    page = open_page()
    poll(page, "navigator.serviceWorker.controller !== null || null", timeout=10)
    page.context.set_offline(True)
    page.goto(base_url + "en/")
    calculate(page, "2025-03-04")
    assert page.is_visible("#result") and "week" in page.text_content("#age-weeks")


@pytest.mark.parametrize("width", [320, 360, 1280])
def test_english_layout(open_page, base_url, width):
    page = open_page(viewport={"width": width, "height": 900})
    page.goto(base_url + "en/")
    calculate(page, "2025-03-04", name="Ana")
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    # Links inside running text are exempt from the WCAG 2.2 target size, like the WHO source link
    small = page.evaluate("""[...document.querySelectorAll('button, a, input:not([type=radio]), .chip, .mode-switch label')]
        .filter(el => el.checkVisibility() && !el.closest('p') && el.getBoundingClientRect().height < 44)
        .map(el => `${el.tagName.toLowerCase()}#${el.id}: ${el.textContent.trim().slice(0, 30)}`)""")
    assert not overflow
    assert small == []


@pytest.mark.parametrize("now, expected", [
    ("2026-12-01T12:00:00+01:00", "153 dana, 01 sat, 00 minuta i 00 sekundi"),  # winter time: one more real hour
    ("2026-08-01T12:00:00+02:00", "31 dan, 00 sati, 00 minuta i 00 sekundi"),   # same summer time: no difference
    ("2027-07-01T12:00:00+02:00", "365 dana, 00 sati, 00 minuta i 00 sekundi"),  # back in summer time a year later
])
def test_total_uses_real_time_across_clock_changes(open_page, now, expected):
    page = open_page(timezone_id="Europe/Zagreb")
    page.clock.set_fixed_time(now)
    calculate(page, "2026-07-01", "12:00")
    assert page.text_content("#age-total") == expected


@pytest.mark.webkit
def test_date_limits_move_with_today(browser, base_url):
    context = browser.new_context(timezone_id="Europe/Zagreb")
    page = context.new_page()
    page.clock.install(time="2026-10-17T22:00:00+02:00")
    page.goto(base_url)
    assert page.get_attribute("#birth-date", "max") == "2026-10-17"
    page.clock.fast_forward("05:00:00")  # past midnight, page still open
    page.focus("#birth-date")
    assert page.get_attribute("#birth-date", "max") == "2026-10-18"
    page.click(".mode-switch >> text=Trudnoća")
    page.focus("#pregnancy-date")
    assert page.get_attribute("#pregnancy-date", "min") == "2026-10-04"  # due date: up to 14 days ago
    context.close()


def premature_page(open_page, now, path=""):
    page = open_page(timezone_id="Europe/Zagreb", permissions=["clipboard-read", "clipboard-write"])
    page.clock.set_fixed_time(now)
    if path:
        page.goto(page.url + path)
    return page


def enter_premature(page, birth="2026-08-01", due="2026-10-01", name="Ana"):
    edit(page)
    page.fill("#child-name", name)
    page.fill("#birth-date", birth)
    page.click("#premature summary")
    page.fill("#due-date", due)
    page.click("#birth-form button[type=submit]")


def test_corrected_age(open_page):
    page = premature_page(open_page, "2026-12-15T12:00:00+01:00")
    assert page.is_hidden("#due-date")  # collapsed until opened
    enter_premature(page)
    assert page.text_content("#corrected-value") == "2 mjeseca i 14 dana"
    assert page.text_content("#corrected-detail") == "10 tjedana i 5 dana · Gestacijska dob pri rođenju:\u00a031+2"
    assert page.text_content("#age-calendar") == "4 mjeseca i 14 dana"  # the actual age is unchanged
    share(page, "#copy-text")
    sync_api.expect(page.locator("#share-status")).not_to_have_text("")
    assert page.evaluate("navigator.clipboard.readText()") == \
        "Ana: 4 mjeseca i 14 dana (19 tjedana i 3 dana). Korigirana dob: 2 mjeseca i 14 dana. Rođenje: 01.08.2026."


def test_corrected_age_before_due_date(open_page):
    page = premature_page(open_page, "2026-09-15T12:00:00+02:00")
    enter_premature(page)
    assert page.text_content("#corrected-value") == "Počinje na termin"
    assert page.text_content("#corrected-detail") == \
        "za 16 dana (termin 01.10.2026.) · Gestacijska dob pri rođenju:\u00a031+2"


def test_corrected_age_not_needed_and_hidden(open_page):
    page = premature_page(open_page, "2026-12-15T12:00:00+01:00")
    enter_premature(page, due="2026-07-30")
    assert page.text_content("#corrected-value") == "Nije potrebna"
    assert page.text_content("#corrected-detail") == "Gestacijska dob pri rođenju:\u00a040+2"
    edit(page)
    page.fill("#due-date", "")
    page.click("#birth-form button[type=submit]")
    assert page.is_hidden("#corrected-card")


def test_corrected_age_errors_and_note(open_page):
    page = premature_page(open_page, "2026-12-15T12:00:00+01:00")
    enter_premature(page, due="2026-12-20")  # more than 20 weeks after the birth
    assert page.text_content("#error") == "Termin poroda može biti najviše 20 tjedana nakon rođenja."
    page.fill("#birth-date", "2024-01-01")
    page.fill("#due-date", "2024-03-01")
    page.click("#birth-form button[type=submit]")
    assert page.text_content("#corrected-detail").endswith("Korekcija se obično koristi do 2. godine.")


def test_corrected_age_is_saved_per_child(open_page):
    page = premature_page(open_page, "2026-12-15T12:00:00+01:00")
    enter_premature(page)
    page.click("#add-child")
    assert page.input_value("#due-date") == "" and not page.evaluate("document.getElementById('premature').open")
    calculate(page, "2025-03-04", name="Marko")
    assert page.is_hidden("#corrected-card")
    page.click("#child-list >> text=Ana")
    assert page.input_value("#due-date") == "2026-10-01" and page.evaluate("document.getElementById('premature').open")
    assert page.is_visible("#corrected-card")


def test_corrected_age_share_link_and_english(open_page, base_url):
    page = premature_page(open_page, "2026-12-15T12:00:00+01:00", "en/?d=2026-08-01&n=Ana&due=2026-10-01")
    assert page.text_content("#corrected-value") == "2 months and 14 days"
    assert page.text_content("#corrected-detail") == "10 weeks and 5 days · Born at 31+2\u00a0weeks"
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    share(page, "#share-link")
    sync_api.expect(page.locator("#share-status")).to_have_text("Link copied.")
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "en/#d=2026-08-01&n=Ana&due=2026-10-01"


@pytest.mark.parametrize("width", [320, 1280])
def test_corrected_age_layout(open_page, width):
    page = open_page(viewport={"width": width, "height": 900})
    enter_premature(page, birth="2026-08-01", due="2026-10-01")
    edit(page)
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    summary = page.evaluate("document.querySelector('#premature summary').getBoundingClientRect().height")
    assert not overflow and summary >= 44


def open_backup(page):
    if not page.evaluate("document.getElementById('backup').open"):
        page.click("#backup summary")


def download_backup(page, tmp_path):
    open_backup(page)
    with page.expect_download() as info:
        page.click("#backup-download")
    download = info.value
    path = tmp_path / download.suggested_filename
    download.save_as(path)
    return download.suggested_filename, path


@pytest.mark.webkit
def test_backup_download(open_page, tmp_path):
    page = open_page()
    enter_premature(page, birth="2026-08-01", due="2026-10-01", name="Ana")
    page.click(".mode-switch >> text=Trudnoća")
    page.fill("#pregnancy-date", due_in(100))
    page.click("#pregnancy-form button")
    name, path = download_backup(page, tmp_path)
    assert re.fullmatch(r"baby-calculator-\d{4}-\d{2}-\d{2}\.json", name)
    data = json.loads(path.read_text())
    assert (data["app"], data["version"], data["mode"]) == ("baby-calculator", 1, "pregnancy")
    assert data["children"] == [{"id": 1, "name": "Ana", "date": "2026-08-01", "time": "", "due": "2026-10-01"}]
    assert data["pregnancy"] == {"basis": "due", "date": due_in(100)}


def test_backup_restore_file_on_new_device(open_page, browser, base_url, tmp_path):
    page = open_page()
    calculate(page, "2025-03-04", name="Ana")
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    _, path = download_backup(page, tmp_path)

    other = browser.new_context()  # a different browser with no saved data
    new_page = other.new_page()
    new_page.goto(base_url)
    open_backup(new_page)
    new_page.set_input_files("#backup-file", str(path))
    sync_api.expect(new_page.locator("#backup-status")).to_have_text("Podaci su učitani.")
    assert chips(new_page) == ["Ana", "Marko"] and new_page.is_visible("#result")
    new_page.set_input_files("#backup-file", str(path))  # restoring again adds nothing
    sync_api.expect(new_page.locator("#backup-status")).to_have_text("Nema novih podataka – sve je već bilo spremljeno.")
    assert chips(new_page) == ["Ana", "Marko"]
    other.close()


def test_backup_restore_rejects_bad_files(open_page, tmp_path):
    page = open_page()
    open_backup(page)
    bad = tmp_path / "bad.json"
    bad.write_text('{"app": "something-else"}')
    page.set_input_files("#backup-file", str(bad))
    sync_api.expect(page.locator("#backup-status")).to_have_text("Ovo nije ispravna sigurnosna kopija.")
    big = tmp_path / "big.json"
    big.write_text(" " * (100 * 1024 + 1))
    page.set_input_files("#backup-file", str(big))
    sync_api.expect(page.locator("#backup-status")).to_have_text("Datoteka je prevelika za sigurnosnu kopiju.")
    assert page.is_hidden("#children")


def test_backup_transfer_link(open_page, browser):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    calculate(page, "2025-03-04", name="Ana")
    open_backup(page)
    page.click("#backup-link")
    sync_api.expect(page.locator("#backup-status")).to_have_text("Poveznica za prijenos je kopirana.")
    link = page.evaluate("navigator.clipboard.readText()")
    assert "#backup=" in link and "?" not in link  # the data stays after "#", never sent to the server

    other = browser.new_context()
    new_page = other.new_page()
    new_page.goto(link)
    assert "#" not in new_page.url  # removed from the address bar after restoring
    assert chips(new_page) == ["Ana"] and new_page.is_visible("#result")
    assert new_page.evaluate("document.getElementById('backup').open")
    assert new_page.text_content("#backup-status") == "Podaci su učitani."
    other.close()


@pytest.mark.parametrize("accept, expected", [(False, 50), (True, 100)])
def test_backup_pregnancy_conflict_asks(open_page, base_url, accept, expected):
    page = open_page()
    page.click(".mode-switch >> text=Trudnoća")
    page.fill("#pregnancy-date", due_in(50))
    page.click("#pregnancy-form button")
    backup = {"app": "baby-calculator", "version": 1, "children": [], "pregnancy": {"basis": "due", "date": due_in(100)}}
    messages = []
    page.on("dialog", lambda d: (messages.append(d.message), d.accept() if accept else d.dismiss()))
    # Same page, only the "#" part changes: no reload, so the page has to notice the hash change
    page.goto(base_url + "#backup=" + json.dumps(backup).replace(" ", ""))
    sync_api.expect(page.locator("#backup-status")).not_to_have_text("")
    assert messages == ["Sigurnosna kopija ima druge podatke o trudnoći. Zamijeniti postojeće?"]
    assert page.input_value("#pregnancy-date") == due_in(expected)
    assert "#" not in page.url


def test_backup_english_and_layout(open_page, base_url, tmp_path):
    page = open_page(viewport={"width": 320, "height": 900})
    page.goto(base_url + "en/")
    open_backup(page)
    bad = tmp_path / "bad.json"
    bad.write_text("nope")
    page.set_input_files("#backup-file", str(bad))
    sync_api.expect(page.locator("#backup-status")).to_have_text("This isn’t a valid backup.")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    heights = page.evaluate("[...document.querySelectorAll('#backup summary, #backup button')].map(b => b.getBoundingClientRect().height)")
    assert not overflow and min(heights) >= 44, heights


def download_calendar(page, button, tmp_path):
    with page.expect_download() as info:
        page.click(button)
    path = tmp_path / info.value.suggested_filename
    info.value.save_as(path)
    from icalendar import Calendar
    return info.value.suggested_filename, Calendar.from_ical(path.read_bytes()).walk("VEVENT")


def test_calendar_export_baby(open_page, tmp_path):
    page = open_page(timezone_id="Europe/Zagreb")
    page.clock.set_fixed_time("2026-10-17T12:00:00+02:00")
    calculate(page, "2026-09-01", "08:30", name="Ana")
    name, events = download_calendar(page, "#calendar-baby", tmp_path)
    assert name == "baby-calculator-2026-09-01.ics"
    summaries = [str(e["SUMMARY"]) for e in events]
    assert summaries[:3] == ["Ana: 2 mjeseca", "Ana: 3 mjeseca", "Ana: 100 dana"]
    assert "Ana: 2. rođendan" in summaries and "Ana: 3. rođendan" not in summaries  # next two years only
    assert events[0].decoded("DTSTART") == date(2026, 11, 1)


def test_calendar_export_pregnancy_english(open_page, base_url, tmp_path):
    page = open_page(timezone_id="Europe/Zagreb")
    page.clock.set_fixed_time("2026-10-17T12:00:00+02:00")
    page.goto(base_url + "en/")
    page.click(".mode-switch >> text=Pregnancy")
    page.fill("#pregnancy-date", "2026-12-06")
    page.click("#pregnancy-form button")
    name, events = download_calendar(page, "#calendar-pregnancy", tmp_path)
    assert name == "baby-calculator-pregnancy-2026-12-06.ics"
    assert [str(e["SUMMARY"]) for e in events] == ["Pregnancy: Full term", "Pregnancy: Due date"]
    assert events[1].decoded("DTSTART") == date(2026, 12, 6)


def test_privacy_note(open_page, base_url):
    page = open_page()
    assert page.text_content(".privacy-note") == "Datumi i imena ostaju samo na vašem uređaju – ne šalju se na server."
    page.goto(base_url + "en/")
    assert page.is_visible(".privacy-note")
    assert page.text_content(".privacy-note") == "Dates and names stay on your device – they are never sent to the server."


def test_language_choice_is_remembered(open_page, base_url):
    page = open_page()
    page.click(".lang-switch a")  # English
    assert page.url == base_url + "en/"
    page.goto(base_url)  # opening "/" again goes straight to English
    assert page.url == base_url + "en/" and page.evaluate("document.documentElement.lang") == "en"
    page.click(".lang-switch a")  # back to Croatian
    page.goto(base_url)
    assert page.url == base_url and page.evaluate("document.documentElement.lang") == "hr"


def test_share_link_keeps_hash_through_language_redirect(open_page, base_url):
    page = open_page()
    page.click(".lang-switch a")  # English chosen
    page.goto(base_url + "#d=2025-03-04&n=Ana")  # a Croatian share link
    page.wait_for_url(base_url + "en/")
    assert chips(page) == ["Ana"] and page.text_content("#age-weeks").endswith("days")


def days_ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def choose_basis(page, label):
    page.click(".mode-switch >> text=Trudnoća")
    edit(page)
    page.click(f"#pregnancy-form label.radio:has-text('{label}')")


def test_pregnancy_from_ivf_transfer(open_page):
    page = open_page()
    choose_basis(page, "Transferu zametka (IVF)")
    assert page.is_visible("#embryo-days") and page.is_hidden("#ga-weeks")
    assert page.text_content("#pregnancy-date-label") == "Datum transfera zametka"
    page.fill("#pregnancy-date", days_ago(30))
    page.click("#pregnancy-form button[type=submit]")
    assert page.text_content("#pregnancy-duration") == "7 tjedana"  # 30 + 14 + 5 = 49 days
    edit(page)
    page.select_option("#embryo-days", "3")
    assert page.text_content("#pregnancy-duration") == "6 tjedana i 5 dana"  # 30 + 14 + 3 = 47 days
    page.reload()
    assert page.is_checked("input[value=ivf]") and page.input_value("#embryo-days") == "3"
    assert page.text_content("#pregnancy-duration") == "6 tjedana i 5 dana"


def test_pregnancy_from_ultrasound(open_page):
    page = open_page()
    choose_basis(page, "Ultrazvuku")
    assert page.is_visible("#ga-weeks") and page.is_hidden("#embryo-days")
    page.fill("#pregnancy-date", days_ago(10))
    page.fill("#ga-weeks", "8")
    page.fill("#ga-days", "3")
    page.click("#pregnancy-form button[type=submit]")
    assert page.text_content("#pregnancy-duration") == "9 tjedana i 6 dana"  # 59 + 10 = 69 days
    edit(page)
    page.fill("#ga-days", "7")
    page.click("#pregnancy-form button[type=submit]")
    assert page.text_content("#error") == "Unesite tjedne (0–42) i dane (0–6) s ultrazvuka."


def test_switching_basis_keeps_pregnancy(open_page):
    page = open_page()
    calculate_pregnancy(page, due_in(50))
    expected = page.text_content("#pregnancy-duration")
    edit(page)
    for label in ["Transferu zametka (IVF)", "Ultrazvuku", "Zadnjoj menstruaciji", "Terminu poroda"]:
        page.click(f"#pregnancy-form label.radio:has-text('{label}')")
        assert page.text_content("#pregnancy-duration") == expected, label
    page.click("#pregnancy-form label.radio:has-text('Ultrazvuku')")
    assert page.input_value("#pregnancy-date") == date.today().isoformat()
    assert (page.input_value("#ga-weeks"), page.input_value("#ga-days")) == ("32", "6")


def test_future_transfer_is_rejected_and_english(open_page, base_url):
    page = open_page()
    page.goto(base_url + "en/")
    page.click(".mode-switch >> text=Pregnancy")
    page.click("#pregnancy-form label.radio:has-text('Embryo transfer (IVF)')")
    assert page.text_content("#pregnancy-date-label") == "Embryo transfer date"
    page.evaluate("document.getElementById('pregnancy-date').removeAttribute('max')")
    page.fill("#pregnancy-date", due_in(3))
    page.click("#pregnancy-form button[type=submit]")
    assert page.text_content("#error") == "The date can’t be in the future."


@pytest.mark.parametrize("width", [320, 1280])
def test_pregnancy_dating_layout(open_page, width):
    page = open_page(viewport={"width": width, "height": 900})
    choose_basis(page, "Ultrazvuku")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    heights = page.evaluate("""[...document.querySelectorAll('#pregnancy-form label.radio, #pregnancy-form input:not([type=radio]), #pregnancy-form select, #pregnancy-form button')]
        .filter(el => el.checkVisibility()).map(el => Math.round(el.getBoundingClientRect().height))""")
    assert not overflow and min(heights) >= 44, heights


PERSIST_STUB = """
    window.persistCalls = 0;
    if (navigator.storage) {
        navigator.storage.persisted = async () => window.alreadyPersisted === true;
        navigator.storage.persist = async () => { window.persistCalls += 1; return true; };
    }
"""


def test_asks_to_keep_data_once_after_saving(browser, base_url):
    context = browser.new_context()
    context.add_init_script(PERSIST_STUB)
    page = context.new_page()
    page.goto(base_url)
    assert page.evaluate("window.persistCalls") == 0  # nothing on page load
    calculate(page, "2025-03-04", name="Ana")
    assert poll(page, "window.persistCalls") == 1
    page.click("#add-child")
    calculate(page, "2026-09-01", name="Marko")
    page.wait_for_timeout(200)
    assert page.evaluate("window.persistCalls") == 1  # once per visit
    page.reload()  # saved data is shown again on load: no request without the visitor doing something
    page.wait_for_timeout(200)
    assert page.evaluate("window.persistCalls") == 0
    context.close()


def test_does_not_ask_when_already_kept(browser, base_url):
    context = browser.new_context()
    context.add_init_script(PERSIST_STUB + "window.alreadyPersisted = true;")
    page = context.new_page()
    page.goto(base_url)
    calculate_pregnancy(page, due_in(50))
    page.wait_for_timeout(200)
    assert page.evaluate("window.persistCalls") == 0
    context.close()


def keep_artifact(data, name):
    """In CI (ARTIFACTS_DIR set), saves a generated file so it can be looked at after the run."""
    folder = os.environ.get("ARTIFACTS_DIR")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        prefix = "" if BROWSER == "chromium" else f"{BROWSER}-"
        (Path(folder) / f"{prefix}{name}").write_bytes(bytes(data))


SHARE_FILES_STUB = """
    navigator.canShare = (data) => Boolean(data && data.files);
    navigator.share = async (data) => {
        const file = data.files[0];
        const bitmap = await createImageBitmap(file);
        window.sharedPicture = { name: file.name, type: file.type, size: file.size, width: bitmap.width, height: bitmap.height };
        const bytes = new Uint8Array(await file.arrayBuffer());
        window.sharedPictureData = Array.from(bytes);
    };
"""


def test_share_picture(open_page):
    page = open_page()
    page.add_init_script(SHARE_FILES_STUB)
    page.reload()
    calculate(page, "2025-03-04", name="Ana")
    share(page, "#share-picture")
    picture = poll(page, "window.sharedPicture || null")
    assert picture["name"] == "baby-calculator-2025-03-04.png" and picture["type"] == "image/png"
    assert (picture["width"], picture["height"]) == (1080, 1080)
    assert picture["size"] > 20_000  # text and icon were drawn, not an empty canvas
    keep_artifact(page.evaluate("window.sharedPictureData"), "share-card-hr.png")


def test_share_picture_downloads_without_file_sharing(open_page, base_url, tmp_path):
    page = open_page()
    page.goto(base_url + "en/")
    page.evaluate("delete Navigator.prototype.canShare; delete navigator.canShare")
    page.click(".mode-switch >> text=Pregnancy")
    page.fill("#pregnancy-date", due_in(50))
    page.click("#pregnancy-form button[type=submit]")
    with page.expect_download() as info:
        share(page, "#share-picture")
    path = tmp_path / info.value.suggested_filename
    info.value.save_as(path)
    assert path.name == f"baby-calculator-pregnancy-{due_in(50)}.png"
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[16:24] == (1080).to_bytes(4, "big") * 2
    sync_api.expect(page.locator("#share-status")).to_have_text("Picture saved.")
    keep_artifact(list(data), "share-card-pregnancy-en.png")


@pytest.mark.parametrize("lang, weeks, born", [
    ("de", r"\d+ Wochen und \d+ Tage?", "Geburt: 4. März 2025 um 17:45"),
    ("it", r"\d+ settimane e \d+ giorni?", "Nascita: 4 marzo 2025 alle 17:45"),
])
def test_german_and_italian_pages(open_page, base_url, lang, weeks, born):
    page = open_page()
    page.goto(base_url + f"{lang}/")
    calculate(page, "2025-03-04", "17:45", name="Ana")
    assert re.fullmatch(weeks, page.text_content("#age-weeks").replace("\u00a0", " "))
    assert page.text_content("#born-at") == born
    text = page.text_content("main")
    # Words that only Croatian or English would use ("Minuten" / "minuti" share a start with "minuta")
    leftover = re.search(r"\b(dana|tjedna|tjedana|mjesec\w*|godin\w*|rođ\w*|sutra|danas|weeks|days|months|Born|Due date)\b", text)
    assert not leftover, leftover


def test_german_pregnancy_and_language_choice(open_page, base_url):
    page = open_page()
    page.click(".lang-switch a[hreflang=de]")
    assert page.url == base_url + "de/"
    page.goto(base_url)  # remembered: "/" opens German
    assert page.url == base_url + "de/"
    page.click(".mode-switch >> text=Schwangerschaft")
    page.fill("#pregnancy-date", due_in(50))
    page.click("#pregnancy-form button[type=submit]")
    assert page.text_content("#pregnancy-duration") == "32 Wochen und 6 Tage"
    assert page.text_content("#pregnancy-countdown") == "in 50 Tagen"


@pytest.mark.parametrize("width", [320, 360, 1280])
@pytest.mark.parametrize("lang", ["", "en/", "de/", "it/"])
def test_no_button_label_is_cut_off(open_page, base_url, lang, width):
    page = open_page(viewport={"width": width, "height": 900})
    page.goto(base_url + lang)
    calculate(page, "2025-03-04", name="Ana")
    page.click("#backup summary")
    page.click("#growth > summary")
    page.click("#growth .sex label.radio >> nth=0")
    add_measurement(page, date.today().isoformat(), weight="10,25", length="80,5", head="45,5")  # the table at its widest
    page.click("#share-toggle")
    # Elements reaching past the right edge (named, so a failure says what to fix)
    # (The measurements table may scroll sideways on its own at 320 px; checked separately below)
    sticking_out = page.evaluate("""[...document.querySelectorAll('main *')]
        .filter(el => el.checkVisibility() && !el.parentElement.closest('.measurements')
            && el.getBoundingClientRect().right > document.documentElement.clientWidth)
        .map(el => `${el.tagName.toLowerCase()}#${el.id}.${el.className}: ${el.textContent.trim().slice(0, 40)}`)""")
    cut = page.evaluate("""[...document.querySelectorAll('button, a, .chip, .mode-switch label, .basis label')]
        .filter(el => el.checkVisibility() && el.scrollWidth > el.clientWidth + 1)
        .map(el => el.textContent.trim())""")
    assert sticking_out == [] and cut == []
    table = page.locator("#measurements-box")
    assert width < 360 or table.evaluate("el => el.scrollWidth <= el.clientWidth"), "measurements table scrolls"


def growth_page(open_page, path="", **context):
    page = open_page(timezone_id="Europe/Zagreb", **context)
    page.clock.set_fixed_time("2026-07-10T12:00:00+02:00")
    if path:
        page.goto(page.url + path)
    return page


def add_measurement(page, date, weight="", length="", head=""):
    if not page.evaluate("document.getElementById('measure-add').open"):
        page.click("#measure-add summary")
    page.fill("#measure-date", date)
    page.fill("#measure-weight", weight)
    page.fill("#measure-length", length)
    page.fill("#measure-head", head)
    page.click("#measure-form button[type=submit]")


def measurement_rows(page):
    """The table rows as "date: value unit (percentile) · ...", newest first."""
    return page.evaluate("""[...document.querySelectorAll('#measurements tr')].map(row => {
        const units = ['kg', 'cm', 'cm'];
        const values = [...row.cells].slice(1, 4).map((cell, i) => cell.firstChild ? [
            `${cell.firstChild.textContent} ${units[i]}`,
            cell.querySelector('.percentile') ? ` (${cell.querySelector('.percentile').textContent})` : '',
        ].join('') : null).filter(Boolean);
        return `${row.cells[0].textContent}: ${values.join(' · ')}`;
    })""")


@pytest.mark.webkit
def test_growth_chart(open_page):
    page = growth_page(open_page)
    calculate(page, "2026-01-10", name="Ana")
    page.click("#growth > summary")
    assert page.text_content("#growth-chart") == "Odaberite spol djeteta za WHO krivulje i percentile."
    page.click("#growth label.radio:has-text('Djevojčica')")
    add_measurement(page, "2026-01-10", weight="3,2", length="49,1", head="33,9")   # close to the WHO medians at birth
    add_measurement(page, "2026-04-10", weight="6,2")
    rows = measurement_rows(page)
    assert rows[0] == "10.04.2026.: 6,2 kg (P69)"
    assert rows[1] == "10.01.2026.: 3,2 kg (P47) · 49,1 cm (P49) · 33,9 cm (P51)"
    svg = page.locator("#growth-chart svg")
    assert svg.get_attribute("aria-label") == "Krivulja rasta: Težina, percentili WHO-a i mjerenja djeteta"
    assert svg.locator("path.curve").count() == 5 and svg.locator("circle.point").count() == 2
    page.click("#growth label.radio:has-text('Duljina')")
    assert page.locator("#growth-chart circle.point").count() == 1  # only one length was measured
    keep_artifact(page.locator("#growth").screenshot(), "growth-hr-light.png")
    page.reload()  # saved with the child; the section opens again because there are measurements
    assert page.evaluate("document.getElementById('growth').open") and len(measurement_rows(page)) == 2
    # Chart first, then the table; the form to add more is folded away
    assert not page.evaluate("document.getElementById('measure-add').open")
    order = page.evaluate("""['growth-chart', 'measurements-box', 'measure-add']
        .map(id => document.getElementById(id).getBoundingClientRect().top)""")
    assert order == sorted(order)
    headers = page.locator("#measurements-box thead th").all_text_contents()
    assert headers == ["Datum", "Težina kg", "Duljina cm", "Glava cm", "Ukloni"]


def test_growth_validation_and_editing(open_page):
    page = growth_page(open_page)
    calculate(page, "2026-01-10", name="Ana")
    page.click("#growth > summary")
    page.click("#growth label.radio:has-text('Dječak')")
    add_measurement(page, "2026-04-10", weight="4200")
    assert page.text_content("#measure-error") == "Težina: unesite vrijednost od 0,3 do 30 kg."
    add_measurement(page, "2026-04-10")
    assert page.text_content("#measure-error") == "Unesite barem jednu vrijednost."
    page.evaluate("document.getElementById('measure-date').removeAttribute('max')")
    add_measurement(page, "2026-08-01", weight="7")
    assert page.text_content("#measure-error") == "Datum mjerenja mora biti između rođenja i današnjeg dana."
    add_measurement(page, "2026-04-10", weight="6.4")
    add_measurement(page, "2026-04-10", head="40.5")  # same date: added to it
    assert page.is_hidden("#measure-error")
    assert measurement_rows(page) == ["10.04.2026.: 6,4 kg (P53) · 40,5 cm (P52)"]
    page.click("#measurements button")
    assert measurement_rows(page) == [] and page.is_hidden("#measurements-box")
    assert page.text_content("#undo-text") == "Uklonjeno: mjerenje od 10.04.2026."
    page.click("#undo-button")
    assert measurement_rows(page) == ["10.04.2026.: 6,4 kg (P53) · 40,5 cm (P52)"]


def test_growth_uses_corrected_age(open_page):
    page = growth_page(open_page)
    page.fill("#child-name", "Ana")
    page.fill("#birth-date", "2026-01-10")
    page.click("#premature summary")
    page.fill("#due-date", "2026-03-01")
    page.click("#birth-form button[type=submit]")
    page.click("#growth > summary")
    page.click("#growth label.radio:has-text('Djevojčica')")
    add_measurement(page, "2026-02-10", weight="1,9")
    add_measurement(page, "2026-03-01", weight="3,2")
    assert measurement_rows(page) == ["01.03.2026.: 3,2 kg (P47)", "10.02.2026.: 1,9 kg (prije termina)"]
    assert page.is_visible("#growth-corrected")


def test_growth_in_english(open_page):
    page = growth_page(open_page, "en/", color_scheme="dark", viewport={"width": 390, "height": 900})
    calculate(page, "2026-01-10", name="Ana")
    page.click("#growth > summary")
    page.click("#growth label.radio:has-text('Girl')")
    add_measurement(page, "2026-04-10", weight="6.2")
    assert measurement_rows(page) == ["10 Apr 2026: 6.2 kg (P69)"]
    add_measurement(page, "2026-06-10", weight="7.1")
    keep_artifact(page.locator("#growth").screenshot(), "growth-en-dark-phone.png")
    # Drawn at the real width: the SVG isn't scaled down, so its text keeps its size on a phone
    svg_width, box_width = page.evaluate("""[document.querySelector('#growth-chart svg').getAttribute('width'),
        document.querySelector('#growth-chart').clientWidth]""")
    assert abs(int(svg_width) - box_width) <= 1


def test_restores_saved_date(open_page):
    page = open_page()
    calculate(page)
    page.reload()
    assert page.input_value("#birth-date") == BIRTH_DATE
    assert page.input_value("#birth-time") == BIRTH_TIME
    assert page.is_visible("#result")


def test_future_date_is_rejected(open_page):
    page = open_page()
    future = datetime.now() + timedelta(days=2)
    page.evaluate("document.getElementById('birth-date').removeAttribute('max')")
    calculate(page, future.strftime("%Y-%m-%d"), "10:00")
    assert page.text_content("#error") == "Datum rođenja ne može biti u budućnosti. Za trudnoću odaberite „Trudnoća”."
    assert page.is_hidden("#result")


def test_uses_visitor_time_zone(open_page):
    # A birth one hour ago in Tokyo is in the future for a server in most other zones
    tokyo_now = datetime.now(ZoneInfo("Asia/Tokyo"))
    birth = tokyo_now - timedelta(hours=1)
    page = open_page(timezone_id="Asia/Tokyo")
    calculate(page, birth.strftime("%Y-%m-%d"), birth.strftime("%H:%M"))
    assert page.text_content("#age-total").startswith("00 dana, 01 sat, ")


@pytest.mark.parametrize("width, height, columns", [
    (320, 568, 1),
    (360, 740, 1),
    (740, 360, 2),
    (768, 1024, 2),
    (1280, 800, 2),
])
@pytest.mark.webkit
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_responsive_layout(open_page, width, height, columns, scheme):
    page = open_page(viewport={"width": width, "height": height}, color_scheme=scheme)
    calculate(page)
    page.click("#share-toggle")
    layout = page.evaluate("""() => {
        const box = document.querySelector('.container').getBoundingClientRect();
        return {
            overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            top: box.top + scrollY, left: box.left, right: innerWidth - box.right,  // top in page coordinates
            button: document.querySelector('#edit-entry').getBoundingClientRect().height,
            // The share buttons stay on one line (the backup transfer button may wrap; see test_no_button_label_is_cut_off)
            actions: [...document.querySelectorAll('#share button')].map(b => b.getBoundingClientRect().height),
            // Visible text/date inputs, and the labels that act as radio buttons
            inputs: [...document.querySelectorAll('input:not([type=radio]), .mode-switch label, .basis label')]
                .filter(el => el.checkVisibility())
                .map(el => el.getBoundingClientRect().height),
            columns: getComputedStyle(document.querySelector('.cards')).gridTemplateColumns.split(' ').length,
        };
    }""")
    assert not layout["overflow"]
    assert layout["top"] >= 0
    assert layout["left"] >= 16 and layout["right"] >= 16
    assert layout["button"] >= 44
    # Share buttons: touch-sized and labels on one line
    assert all(44 <= height < 60 for height in layout["actions"]), layout["actions"]
    assert min(layout["inputs"]) >= 44
    assert layout["columns"] == columns


def form_is_open(page):
    return page.is_visible("#birth-date") or page.is_visible("#pregnancy-date")


@pytest.mark.webkit
def test_result_first(open_page):
    page = open_page(viewport={"width": 390, "height": 844})
    assert form_is_open(page) and page.is_hidden("#edit-entry")  # nothing saved yet: the form
    calculate(page, name="Ana")
    # The form is folded away and the result gets the focus, in view
    assert not form_is_open(page) and page.is_visible("#edit-entry")
    assert page.evaluate("document.activeElement.id") == "result"
    assert poll(page, "document.getElementById('result').getBoundingClientRect().top < innerHeight / 2 || null")
    page.reload()  # saved: opens on the result, without moving the focus
    assert page.is_visible("#result") and not form_is_open(page)
    assert page.evaluate("document.activeElement === document.body")
    keep_artifact(page.screenshot(full_page=True), "result-first-hr-phone.png")
    page.click("#edit-entry")
    assert form_is_open(page) and page.is_hidden("#edit-entry")
    assert page.evaluate("document.activeElement.id") == "child-name"
    assert page.is_visible("#remove-child")  # only while editing
    page.fill("#birth-date", "2025-01-01")  # still updated live while editing
    page.dispatch_event("#birth-date", "change")
    assert form_is_open(page) and page.input_value("#birth-date") == "2025-01-01"
    page.click("#add-child")
    assert form_is_open(page) and page.is_hidden("#result")


@pytest.mark.webkit
def test_result_first_pregnancy(open_page):
    page = open_page()
    calculate_pregnancy(page, due_in(50))
    assert not form_is_open(page) and page.evaluate("document.activeElement.id") == "pregnancy-result"
    page.click("#edit-entry")
    assert page.evaluate("document.activeElement.value") == "due"  # the chosen basis
    page.click(".mode-switch >> text=Beba")
    assert form_is_open(page)  # no baby saved: the form


@pytest.mark.webkit
def test_share_menu(open_page):
    page = open_page()
    calculate(page)
    assert page.is_hidden("#share-menu") and page.get_attribute("#share-toggle", "aria-expanded") == "false"
    page.click("#share-toggle")
    assert page.is_visible("#copy-text") and page.get_attribute("#share-toggle", "aria-expanded") == "true"
    page.focus("#copy-text")
    page.keyboard.press("Escape")
    assert page.is_hidden("#share-menu") and page.evaluate("document.activeElement.id") == "share-toggle"


@pytest.mark.webkit
def test_compact_header_and_footer(open_page):
    page = open_page(viewport={"width": 360, "height": 740})
    assert page.locator(".lang-switch [aria-hidden=true]").all_text_contents() == ["HR", "EN", "DE", "IT"]
    assert page.get_attribute(".lang-switch a[hreflang=en]", "lang") == "en"
    assert page.locator(".lang-switch a[hreflang=en] .visually-hidden").text_content() == "English"
    # Title and language switch on one line
    tops = page.evaluate("[...document.querySelectorAll('h1, .lang-switch')].map(e => Math.round(e.getBoundingClientRect().top + e.getBoundingClientRect().height / 2))")
    assert abs(tops[0] - tops[1]) <= 4, tops
    footer = " ".join(page.text_content(".site-footer .version-text").split())
    assert re.fullmatch(r"© 2024–\d{4} Luka Pejaković · v\d+\.\d+(\.\d+)? · Izvorni kod", footer), footer
    assert page.text_content("h1") == "Baby Calculator"


def test_intro_only_on_first_visit(open_page):
    page = open_page()
    assert page.text_content("#intro").startswith("Izračunajte dob bebe")
    calculate(page)
    assert page.is_hidden("#intro")
    page.reload()  # something is saved: straight to the result
    assert page.is_hidden("#intro")


@pytest.mark.webkit
@pytest.mark.parametrize("width, side_by_side", [(1280, True), (1024, True), (768, False), (390, False)])
def test_desktop_form_and_result_side_by_side(open_page, width, side_by_side):
    page = open_page(viewport={"width": width, "height": 900})
    calculate(page, name="Ana")
    edit(page)
    box = page.evaluate("""() => {
        const form = document.querySelector('#birth-form').getBoundingClientRect();
        const result = document.querySelector('#result').getBoundingClientRect();
        return { formRight: form.right, resultLeft: result.left, formTop: form.top, resultTop: result.top,
                 overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth };
    }""")
    assert not box["overflow"]
    if side_by_side:
        assert box["resultLeft"] > box["formRight"] and box["resultTop"] < box["formTop"] + 200, box
    else:
        assert box["resultTop"] > box["formTop"], box
    if width == 1280:
        page.click("#growth > summary")
        keep_artifact(page.screenshot(full_page=True), "desktop-1280.png")


def saved_page(browser, base_url, storage, **context):
    """A page opened with data already in localStorage, e.g. saved on an earlier visit."""
    ctx = browser.new_context(**context)
    ctx.add_init_script(f"if (!sessionStorage.getItem('seeded')) {{ sessionStorage.setItem('seeded', '1'); "
                        f"Object.entries({json.dumps(storage)}).forEach(([k, v]) => localStorage.setItem(k, JSON.stringify(v))); }}")
    page = ctx.new_page()
    page.goto(base_url)
    return ctx, page


ANA = [{"id": 1, "name": "Ana", "date": "2025-03-04", "time": "", "due": ""}]


@pytest.mark.webkit
def test_backup_reminder(browser, base_url, tmp_path):
    ctx, page = saved_page(browser, base_url, {"children": ANA, "firstSaved": "2026-01-01"})
    assert page.is_visible("#backup-reminder")
    assert page.text_content("#backup-last") == "Zadnja sigurnosna kopija: još nijedna"
    keep_artifact(page.screenshot(full_page=True), "backup-reminder-hr.png")
    with page.expect_download() as info:
        page.click("#reminder-backup")
    assert info.value.suggested_filename.startswith("baby-calculator-")
    assert page.is_hidden("#backup-reminder")
    today = date.today()
    assert page.text_content("#backup-last") == f"Zadnja sigurnosna kopija: {today:%d.%m.%Y}."
    page.reload()
    assert page.is_hidden("#backup-reminder")
    ctx.close()


def test_backup_reminder_later_and_first_day(browser, base_url):
    ctx, page = saved_page(browser, base_url, {"children": ANA, "firstSaved": "2026-01-01"})
    page.click("#reminder-later")
    assert page.is_hidden("#backup-reminder")
    page.reload()
    assert page.is_hidden("#backup-reminder")  # snoozed for a week
    ctx.close()
    ctx, page = saved_page(browser, base_url, {"children": ANA})  # saved before this version: counts from today
    assert page.is_hidden("#backup-reminder")
    assert page.evaluate("JSON.parse(localStorage.getItem('firstSaved'))") == date.today().isoformat()
    ctx.close()


IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


@pytest.mark.webkit
def test_iphone_install_hint(open_page):
    page = open_page(user_agent=IPHONE_UA, viewport={"width": 390, "height": 844})
    assert page.is_hidden("#ios-install")  # nothing saved yet
    calculate(page, name="Ana")
    assert page.is_visible("#ios-install")
    assert "Dodaj na početni zaslon" in page.text_content("#ios-install")
    page.click("#ios-install-close")
    assert page.is_hidden("#ios-install")
    page.reload()
    assert page.is_hidden("#ios-install")


def test_no_install_hint_elsewhere(open_page):
    page = open_page()
    calculate(page)
    assert page.is_hidden("#ios-install")

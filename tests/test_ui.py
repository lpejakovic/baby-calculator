"""Browser tests: page behaviour and responsive layout in headless Chromium."""
import re
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from werkzeug.serving import make_server

import app as app_module

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

BIRTH_DATE, BIRTH_TIME = "2025-03-04", "17:45"


@pytest.fixture(scope="module")
def base_url():
    app_module.limiter.enabled = False
    server = make_server("127.0.0.1", 0, app_module.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    app_module.limiter.enabled = True


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def open_page(browser, base_url):
    contexts, errors = [], []

    def _open(**context_options):
        context = browser.new_context(**context_options)
        contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(base_url)
        return page

    yield _open
    for context in contexts:
        context.close()
    assert errors == []


def calculate(page, date=BIRTH_DATE, time=BIRTH_TIME):
    page.fill("#birth-date", date)
    page.fill("#birth-time", time)
    page.click("button")


def test_result_and_live_counter(open_page):
    page = open_page()
    assert page.is_hidden("#result")
    calculate(page)
    assert page.is_visible("#result")
    assert page.text_content("#born-at") == "Rođenje: 04.03.2025. u 17:45"
    assert page.text_content("#announce").startswith("Dob: ")
    first = page.text_content("#age-total")
    page.wait_for_function(f"document.getElementById('age-total').textContent !== {first!r}", timeout=3000)


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
    assert page.evaluate("localStorage.getItem('birth')") == '{"date":"2026-09-01","time":"08:30"}'
    context.close()


def test_invalid_shared_link_is_ignored(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + "?d=2026-02-30")
    assert page.input_value("#birth-date") == ""
    assert page.is_hidden("#result")
    context.close()


def test_share_uses_share_sheet(open_page, base_url):
    page = open_page()
    page.evaluate("navigator.share = async (data) => { window.sharedData = data; }")
    calculate(page)
    page.click("#share-link")
    data = page.wait_for_function("window.sharedData").json_value()
    assert data["url"] == base_url + "?d=2025-03-04T17:45"
    assert data["text"].startswith("Dob: ")
    assert data["text"].endswith("Rođenje: 04.03.2025. u 17:45.")


def test_share_falls_back_to_copying_link(open_page, base_url):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.evaluate("delete Navigator.prototype.share; delete navigator.share")
    calculate(page, time="")
    page.click("#share-link")
    page.wait_for_function("document.getElementById('share-status').textContent !== ''")
    assert page.text_content("#share-status") == "Poveznica je kopirana."
    assert page.evaluate("navigator.clipboard.readText()") == base_url + "?d=2025-03-04"


def test_copy_text(open_page):
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    calculate(page, time="")
    page.click("#copy-text")
    page.wait_for_function("document.getElementById('share-status').textContent !== ''")
    assert page.text_content("#share-status") == "Tekst je kopiran."
    text = page.evaluate("navigator.clipboard.readText()")
    assert re.fullmatch(r"Dob: .+ \(.+\)\. Rođenje: 04\.03\.2025\.", text), text


def test_works_offline(open_page):
    page = open_page()
    # Fails after 10 s (instead of hanging) if the service worker never takes control
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10_000)
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


def test_restores_saved_date(open_page):
    page = open_page()
    calculate(page)
    page.reload()
    assert page.input_value("#birth-date") == BIRTH_DATE
    assert page.input_value("#birth-time") == BIRTH_TIME
    assert page.is_visible("#result")


def test_migrates_legacy_cookie(open_page, base_url):
    page = open_page()
    page.context.add_cookies([{"name": "datetime", "value": "2026-08-15T22:10", "url": base_url}])
    page.reload()
    assert page.input_value("#birth-date") == "2026-08-15"
    assert page.input_value("#birth-time") == "22:10"
    assert page.context.cookies() == []
    assert page.evaluate("localStorage.getItem('birth')") == '{"date":"2026-08-15","time":"22:10"}'


def test_future_date_is_rejected(open_page):
    page = open_page()
    future = datetime.now() + timedelta(days=2)
    page.evaluate("document.getElementById('birth-date').removeAttribute('max')")
    calculate(page, future.strftime("%Y-%m-%d"), "10:00")
    assert page.text_content("#error") == "Datum rođenja ne može biti u budućnosti."
    assert page.is_hidden("#result")


def test_uses_visitor_time_zone(open_page):
    # A birth one hour ago in Tokyo is in the future for a server in most other zones
    tokyo_now = datetime.now(ZoneInfo("Asia/Tokyo"))
    birth = tokyo_now - timedelta(hours=1)
    page = open_page(timezone_id="Asia/Tokyo")
    calculate(page, birth.strftime("%Y-%m-%d"), birth.strftime("%H:%M"))
    assert page.text_content("#age-total").startswith("1 sat")


@pytest.mark.parametrize("width, height, columns", [
    (320, 568, 1),
    (360, 740, 1),
    (740, 360, 2),
    (768, 1024, 2),
    (1280, 800, 2),
])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_responsive_layout(open_page, width, height, columns, scheme):
    page = open_page(viewport={"width": width, "height": height}, color_scheme=scheme)
    calculate(page)
    layout = page.evaluate("""() => {
        const box = document.querySelector('.container').getBoundingClientRect();
        return {
            overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            top: box.top, left: box.left, right: innerWidth - box.right,
            button: document.querySelector('button').getBoundingClientRect().height,
            actions: [...document.querySelectorAll('.actions button')].map(b => b.getBoundingClientRect().height),
            inputs: [...document.querySelectorAll('input')].map(i => i.getBoundingClientRect().height),
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

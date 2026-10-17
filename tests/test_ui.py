"""Browser tests: page behaviour and responsive layout in headless Chromium."""
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
            inputs: [...document.querySelectorAll('input')].map(i => i.getBoundingClientRect().height),
            columns: getComputedStyle(document.querySelector('.cards')).gridTemplateColumns.split(' ').length,
        };
    }""")
    assert not layout["overflow"]
    assert layout["top"] >= 0
    assert layout["left"] >= 16 and layout["right"] >= 16
    assert layout["button"] >= 44
    assert min(layout["inputs"]) >= 44
    assert layout["columns"] == columns

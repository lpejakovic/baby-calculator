import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from werkzeug.serving import make_server

import api as api_module
import app as app_module

# "Now" for the API tests: 17 Oct 2026 15:30:45 in Zagreb (UTC+2 on that date)
FROZEN_NOW_UTC = datetime(2026, 10, 17, 13, 30, 45, tzinfo=UTC)


@pytest.fixture
def freeze_at(monkeypatch):
    """freeze_at(aware_datetime): the app's clock stands still at that instant."""
    def _freeze(instant):
        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
        monkeypatch.setattr(api_module, "datetime", Frozen)
    return _freeze


@pytest.fixture
def frozen_time(freeze_at):
    freeze_at(FROZEN_NOW_UTC)


@pytest.fixture
def limiter():
    app_module.limiter.reset()
    app_module.limiter.enabled = True
    yield app_module.limiter
    app_module.limiter.reset()


@pytest.fixture
def client(limiter):
    """Test client with rate limiting off; use the `limiter` fixture alone to test limits."""
    limiter.enabled = False
    yield app_module.app.test_client()
    limiter.enabled = True


# --- Browser tests (test_ui.py, test_a11y.py) ---

NGINX_CONF = Path(__file__).resolve().parent.parent / "deploy" / "nginx-bc.luka-pejakovic.from.hr.conf"
# The production Content-Security-Policy, so the browser tests fail if it would block anything
CSP = re.search(r'add_header Content-Security-Policy "([^"]+)"', NGINX_CONF.read_text()).group(1)


def with_csp(wsgi_app):
    def wrapped(environ, start_response):
        def start(status, headers, exc_info=None):
            return start_response(status, headers + [("Content-Security-Policy", CSP)], exc_info)
        return wsgi_app(environ, start)
    return wrapped


@pytest.fixture(scope="module")
def base_url():
    app_module.limiter.enabled = False
    server = make_server("127.0.0.1", 0, with_csp(app_module.app), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    app_module.limiter.enabled = True


# Chromium by default; BROWSER=webkit (Safari's engine) runs the smoke tests marked "webkit" (CI: Browser (WebKit))
BROWSER = os.environ.get("BROWSER", "chromium")


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        browser = getattr(p, BROWSER).launch()
        yield browser
        browser.close()

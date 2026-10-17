import re
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from werkzeug.serving import make_server

import app as app_module

# Wall-clock "now" used by the API tests (server local time)
FROZEN_NOW = datetime(2026, 10, 17, 15, 30, 45)
# The same instant in UTC, for requests with a tz field (Europe/Zagreb is UTC+2 on this date)
FROZEN_NOW_UTC = datetime(2026, 10, 17, 13, 30, 45, tzinfo=UTC)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW if tz is None else FROZEN_NOW_UTC.astimezone(tz)


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr(app_module, "datetime", FrozenDatetime)


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


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()

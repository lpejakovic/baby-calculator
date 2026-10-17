from datetime import datetime, timezone

import pytest

import app as app_module

# Wall-clock "now" used by the API tests (server local time)
FROZEN_NOW = datetime(2026, 10, 17, 15, 30, 45)
# The same instant in UTC, for requests with a tz field (Europe/Zagreb is UTC+2 on this date)
FROZEN_NOW_UTC = datetime(2026, 10, 17, 13, 30, 45, tzinfo=timezone.utc)


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

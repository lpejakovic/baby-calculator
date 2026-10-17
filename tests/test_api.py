import re

import pytest

import app as app_module


def post(client, **data):
    response = client.post("/calculate", data=data)
    return response.status_code, response.get_json()


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f"v{app_module.APP_VERSION}" in html
    # Every static URL carries a cache-busting version
    static_urls = re.findall(r'"(/static/[^"]+)"', html)
    assert static_urls
    assert all(re.search(r"\?v=\d+$", url) for url in static_urls)


def test_calculate(client, frozen_time):
    status, body = post(client, datetime="2026-09-01T08:30")
    assert status == 200
    assert body == {
        "current": "17.10.2026 15:30:45",
        "day_diff": "46 dana, 7 sati, 0 minuta i 45 sekundi",
        "week_diff": "6 tjedana i 4 dana",
        "year_diff": "0 godina, 1 mjesec i 16 dana",
    }


def test_calculate_exactly_now(client, frozen_time):
    status, body = post(client, datetime="2026-10-17T15:30")
    assert status == 200
    assert body["day_diff"] == "0 dana, 0 sati, 0 minuta i 45 sekundi"


@pytest.mark.parametrize("data", [
    {"datetime": "bad"},
    {"datetime": "2026-02-30T10:00"},
    {"datetime": "2026-09-01"},
    {"datetime": ""},
    {},
])
def test_invalid_input(client, frozen_time, data):
    assert post(client, **data) == (400, {"error": "Neispravan datum i vrijeme rođenja."})


def test_future_date(client, frozen_time):
    assert post(client, datetime="2026-10-17T15:31") == (400, {"error": "Datum rođenja ne može biti u budućnosti."})


def test_time_zone(client, frozen_time):
    # 20:00 is in the future in Zagreb (15:30) but 2.5 hours ago in Tokyo (22:30)
    status, body = post(client, datetime="2026-10-17T20:00", tz="Asia/Tokyo")
    assert status == 200
    assert body["current"] == "17.10.2026 22:30:45"
    assert body["day_diff"] == "0 dana, 2 sata, 30 minuta i 45 sekundi"

    status, _ = post(client, datetime="2026-10-17T20:00", tz="Europe/Zagreb")
    assert status == 400


@pytest.mark.parametrize("tz", ["Nope/Zone", "../../etc/passwd", "UTC+2"])
def test_unknown_time_zone(client, frozen_time, tz):
    assert post(client, datetime="2026-09-01T08:30", tz=tz) == (400, {"error": "Nepoznata vremenska zona."})


def test_rate_limit(limiter, frozen_time):
    client = app_module.app.test_client()
    assert client.post("/calculate", data={"datetime": "2026-09-01T08:30"}).status_code == 200
    response = client.post("/calculate", data={"datetime": "2026-09-01T08:30"})
    assert response.status_code == 429
    assert response.get_json() == {"error": "Previše zahtjeva. Pokušajte ponovno kasnije."}


def test_rate_limit_per_client_ip(limiter, frozen_time):
    client = app_module.app.test_client()

    def status(ip):
        return client.post("/calculate", data={"datetime": "2026-09-01T08:30"},
                           headers={"X-Forwarded-For": ip}).status_code

    assert [status("1.1.1.1"), status("1.1.1.1")] == [200, 429]
    assert status("2.2.2.2") == 200
    # Only the last X-Forwarded-For entry (added by nginx) is trusted
    assert status("9.9.9.9, 1.1.1.1") == 429


def test_index_not_rate_limited(limiter):
    client = app_module.app.test_client()
    assert {client.get("/").status_code for _ in range(20)} == {200}

import json
import re
import struct

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


def test_link_preview(client):
    # Headers as nginx sends them (proxy_params)
    html = client.get("/", headers={"Host": "bc.luka-pejakovic.from.hr", "X-Forwarded-Proto": "https",
                                    "X-Forwarded-For": "1.2.3.4"}).get_data(as_text=True)
    meta = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', html))
    assert meta["og:url"] == "https://bc.luka-pejakovic.from.hr/"
    assert re.fullmatch(r"https://bc\.luka-pejakovic\.from\.hr/static/images/og-image\.png\?v=\d+", meta["og:image"])
    assert (meta["og:image:width"], meta["og:image:height"], meta["og:image:type"]) == ("1200", "630", "image/png")
    assert meta["og:image:alt"]
    assert meta["twitter:card"] == "summary_large_image"

    image = client.get(meta["og:image"].removeprefix("https://bc.luka-pejakovic.from.hr"))
    assert image.status_code == 200
    data = image.get_data()
    assert png_size(data) == (1200, 630)
    assert len(data) < 300 * 1024  # WhatsApp skips large preview images


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


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_manifest(client):
    html = client.get("/").get_data(as_text=True)
    href = re.search(r'<link rel="manifest" href="([^"]+)"', html).group(1)
    response = client.get(href)
    assert response.status_code == 200
    manifest = json.loads(response.get_data())
    assert manifest["name"] and manifest["short_name"]
    assert (manifest["start_url"], manifest["scope"], manifest["display"]) == ("/", "/", "standalone")
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert purposes == {"any", "maskable"}
    sizes = {icon["sizes"] for icon in manifest["icons"] if icon["purpose"] == "any"}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        image = client.get("/static/" + icon["src"])
        assert image.status_code == 200, icon["src"]
        width, height = (int(n) for n in icon["sizes"].split("x"))
        assert png_size(image.get_data()) == (width, height)


def test_service_worker(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/javascript")
    assert response.headers["Cache-Control"] == "no-cache"
    precache = json.loads(re.search(r"const PRECACHE = (\[.*?\]);", response.get_data(as_text=True)).group(1))

    # Everything the page loads from this site is precached, with the same versioned URL
    html = client.get("/").get_data(as_text=True)
    page_assets = set(re.findall(r'(?:href|src)="(/static/[^"]+)"', html))
    assert "/" in precache
    assert page_assets <= set(precache)
    for url in precache:
        assert client.get(url).status_code == 200, url


def test_service_worker_changes_with_assets(client, monkeypatch):
    before = client.get("/sw.js").get_data(as_text=True)
    monkeypatch.setattr(app_module, "APP_VERSION", "0.0-test")
    after = client.get("/sw.js").get_data(as_text=True)
    cache_name = re.compile(r"const CACHE = '(bc-[0-9a-f]+)'")
    assert cache_name.search(before).group(1) != cache_name.search(after).group(1)

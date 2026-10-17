import json
import re
import struct
from datetime import datetime
from html import unescape

import pytest

import app as app_module
from i18n import PAGE_TEXT


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
    # The original four fields are unchanged, so existing callers keep working
    assert {k: body[k] for k in ("current", "day_diff", "week_diff", "year_diff")} == {
        "current": "17.10.2026 15:30:45",
        "day_diff": "46 dana, 7 sati, 0 minuta i 45 sekundi",
        "week_diff": "6 tjedana i 4 dana",
        "year_diff": "0 godina, 1 mjesec i 16 dana",
    }
    assert body["age"] == {
        "calendar": {"years": 0, "months": 1, "days": 16},
        "weeks": {"weeks": 6, "days": 4},
        "elapsed": {"days": 46, "hours": 7, "minutes": 0, "seconds": 45, "total_seconds": 46 * 86400 + 7 * 3600 + 45},
    }
    assert (body["birth"], body["now"]) == ("2026-09-01T08:30:00+02:00", "2026-10-17T15:30:45+02:00")
    assert (body["tz"], body["lang"]) == ("Europe/Zagreb", "hr")


def test_calculate_english(client, frozen_time):
    status, body = post(client, datetime="2026-09-01T08:30", lang="en")
    assert status == 200
    assert {k: body[k] for k in ("current", "day_diff", "week_diff", "year_diff", "lang")} == {
        "current": "17 Oct 2026 15:30:45",
        "day_diff": "46 days, 7 hours, 0 minutes and 45 seconds",
        "week_diff": "6 weeks and 4 days",
        "year_diff": "0 years, 1 month and 16 days",
        "lang": "en",
    }


def test_calculate_json_body(client, frozen_time):
    response = client.post("/calculate", json={"datetime": "2026-09-01T08:30", "lang": "en", "tz": "Asia/Tokyo"})
    assert response.status_code == 200
    body = response.get_json()
    assert (body["tz"], body["birth"], body["now"]) == ("Asia/Tokyo", "2026-09-01T08:30:00+09:00", "2026-10-17T22:30:45+09:00")
    assert body["age"]["calendar"] == {"years": 0, "months": 1, "days": 16}


@pytest.mark.parametrize("payload", ["not json", "[1, 2]", '{"datetime": 5}'])
def test_calculate_bad_json(client, frozen_time, payload):
    response = client.post("/calculate", data=payload, content_type="application/json")
    assert (response.status_code, response.get_json()) == (400, {"error": "Neispravan datum i vrijeme rođenja."})


@pytest.mark.parametrize("data, error", [
    ({"datetime": "bad", "lang": "en"}, "Invalid date and time of birth."),
    ({"datetime": "2026-10-18T10:00", "lang": "en"}, "The date of birth can't be in the future."),
    ({"datetime": "2026-09-01T08:30", "lang": "en", "tz": "Nope/Zone"}, "Unknown time zone."),
    ({"datetime": "2026-09-01T08:30", "lang": "fr"}, "Nepodržani jezik / Unsupported language (hr, en, de, it)."),
])
def test_calculate_errors_by_language(client, frozen_time, data, error):
    assert post(client, **data) == (400, {"error": error})


@pytest.mark.parametrize("now, elapsed_hours, day_diff", [
    ("2026-12-01T12:00:00+01:00", 1, "153 dana, 1 sat, 0 minuta i 0 sekundi"),  # winter time: one more real hour
    ("2026-08-01T12:00:00+02:00", 0, "31 dan, 0 sati, 0 minuta i 0 sekundi"),
])
def test_calculate_real_elapsed_time(client, freeze_at, now, elapsed_hours, day_diff):
    freeze_at(datetime.fromisoformat(now))
    status, body = post(client, datetime="2026-07-01T12:00")
    assert status == 200
    assert body["day_diff"] == day_diff
    assert body["age"]["elapsed"]["hours"] == elapsed_hours
    # Calendar values stay on the wall clock
    assert body["age"]["calendar"]["days"] == 0


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


# --- English page

NGINX = {"Host": "bc.luka-pejakovic.from.hr", "X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}


def page_meta(html):
    return {name: unescape(value) for name, value in re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', html)}


def test_page_texts_match():
    assert PAGE_TEXT["hr"].keys() == PAGE_TEXT["en"].keys()
    assert all(PAGE_TEXT["en"].values())


def test_english_page(client):
    html = client.get("/en/", headers=NGINX).get_data(as_text=True)
    assert '<html lang="en">' in html
    assert "Baby is born" in html and "Beba je rođena" not in html
    meta = page_meta(html)
    assert meta["og:url"] == "https://bc.luka-pejakovic.from.hr/en/"
    assert meta["og:locale"] == "en_US"
    assert meta["description"] == PAGE_TEXT["en"]["description"] == meta["og:description"]
    assert re.fullmatch(r"https://bc\.luka-pejakovic\.from\.hr/static/images/og-image-en\.png\?v=\d+", meta["og:image"])
    image = client.get(meta["og:image"].removeprefix("https://bc.luka-pejakovic.from.hr")).get_data()
    assert png_size(image) == (1200, 630)
    assert re.search(r'<link rel="manifest" href="/static/manifest-en\.json\?v=\d+">', html)


SITE = "https://bc.luka-pejakovic.from.hr"
PAGES = {"hr": f"{SITE}/", "en": f"{SITE}/en/", "de": f"{SITE}/de/", "it": f"{SITE}/it/"}
NAMES = {"hr": "Hrvatski", "en": "English", "de": "Deutsch", "it": "Italiano"}


@pytest.mark.parametrize("lang", PAGES)
def test_alternate_links_and_switch(client, lang):
    html = client.get(PAGES[lang].removeprefix(SITE), headers=NGINX).get_data(as_text=True)
    assert f'<link rel="canonical" href="{PAGES[lang]}">' in html
    for code, url in PAGES.items():
        assert f'<link rel="alternate" hreflang="{code}" href="{url}">' in html
    assert f'<link rel="alternate" hreflang="x-default" href="{PAGES["hr"]}">' in html
    # The switch links to the three other languages, in their own words; the current one is marked, not a link
    nav = re.search(r'<nav class="lang-switch"[^>]*>(.*?)</nav>', html, re.S).group(1)
    links = re.findall(r'<a href="([^"]+)" hreflang="([^"]+)" lang="([^"]+)">([^<]+)</a>', nav)
    assert links == [(PAGES[c], c, c, NAMES[c]) for c in PAGES if c != lang]
    assert f'<span class="lang-current" lang="{lang}" aria-current="page">{NAMES[lang]}</span>' in nav


@pytest.mark.parametrize("lang, mode_baby, description", [
    ("de", "Baby ist geboren", "Das Alter Ihres Babys in Wochen, Monaten und Tagen – live auf die Sekunde."),
    ("it", "Il bambino è nato", "Calcola l’età del tuo bambino in settimane, mesi e giorni, in tempo reale al secondo."),
])
def test_german_and_italian_pages(client, lang, mode_baby, description):
    html = client.get(f"/{lang}/", headers=NGINX).get_data(as_text=True)
    assert f'<html lang="{lang}">' in html and mode_baby in html
    meta = page_meta(html)
    assert meta["description"] == description and meta["og:url"] == PAGES[lang]
    assert re.fullmatch(rf"{SITE}/static/images/og-image-{lang}\.png\?v=\d+", meta["og:image"])
    assert png_size(client.get(meta["og:image"].removeprefix(SITE)).get_data()) == (1200, 630)
    assert f"manifest-{lang}.json" in html


@pytest.mark.parametrize("lang", ["en", "de", "it"])
def test_language_without_slash_redirects(client, lang):
    response = client.get(f"/{lang}")
    assert response.status_code == 308 and response.headers["Location"].endswith(f"/{lang}/")


def test_unknown_language_is_not_found(client):
    assert client.get("/fr/").status_code == 404


@pytest.mark.parametrize("lang", ["en", "de", "it"])
def test_language_manifest(client, lang):
    manifest = json.loads(client.get(f"/static/manifest-{lang}.json").get_data())
    assert (manifest["id"], manifest["start_url"], manifest["lang"]) == (f"/{lang}/", f"/{lang}/", lang)
    croatian = json.loads(client.get("/static/manifest.json").get_data())
    assert manifest["icons"] == croatian["icons"]
    assert manifest["id"] != croatian["id"]  # installs as a separate app


def test_service_worker_covers_all_languages(client):
    sw = client.get("/sw.js").get_data(as_text=True)
    precache = json.loads(re.search(r"const PRECACHE = (\[.*?\]);", sw).group(1))
    pages = json.loads(re.search(r"const PAGES = (\[.*?\]);", sw).group(1))
    assert pages == ["/", "/en/", "/de/", "/it/"]
    for path in pages:
        html = client.get(path).get_data(as_text=True)
        assert set(re.findall(r'(?:href|src)="(/static/[^"]+)"', html)) <= set(precache), path
    assert set(pages) <= set(precache)


def test_robots_txt(client):
    response = client.get("/robots.txt", headers=NGINX)
    assert response.status_code == 200 and response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == (
        "User-agent: *\nDisallow: /calculate\nDisallow: /health\n\n"
        "Sitemap: https://bc.luka-pejakovic.from.hr/sitemap.xml\n")


def test_sitemap(client):
    import xml.etree.ElementTree as ET
    response = client.get("/sitemap.xml", headers=NGINX)
    assert response.status_code == 200 and response.mimetype == "application/xml"
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
    urls = ET.fromstring(response.get_data()).findall("s:url", ns)
    assert [u.find("s:loc", ns).text for u in urls] == list(PAGES.values())
    for url in urls:
        alternates = {link.get("hreflang"): link.get("href") for link in url.findall("x:link", ns)}
        assert alternates == {**PAGES, "x-default": PAGES["hr"]}


@pytest.mark.parametrize("path, lang, title, home", [
    ("/nope", "hr", "Stranica nije pronađena", "/"),
    ("/en/nope", "en", "Page not found", "/en/"),
    ("/de/nope", "de", "Seite nicht gefunden", "/de/"),
    ("/it/nope", "it", "Pagina non trovata", "/it/"),
    ("/static/missing.css", "hr", "Stranica nije pronađena", "/"),
])
def test_not_found(client, path, lang, title, home):
    response = client.get(path)
    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert f'<html lang="{lang}">' in html and f"<h1>{title}</h1>" in html
    assert f'<a class="button" href="{home}">' in html
    assert '<meta name="robots" content="noindex">' in html


def test_health(limiter):
    client = app_module.app.test_client()
    for _ in range(60):  # never rate limited, so monitoring can't trip it
        response = client.get("/health")
        assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": app_module.APP_VERSION}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("lang", ["en", "de", "it"])
def test_language_cookie_redirects(client, lang):
    client.set_cookie("lang", lang)
    response = client.get("/")
    assert response.status_code == 302 and response.headers["Location"] == f"/{lang}/"
    assert "Cookie" in response.headers["Vary"]
    response = client.get("/?d=2026-09-01")  # older share links keep their query
    assert response.headers["Location"] == f"/{lang}/?d=2026-09-01"


@pytest.mark.parametrize("cookie", ["hr", "xx", None])
def test_croatian_page_without_english_cookie(client, cookie):
    if cookie:
        client.set_cookie("lang", cookie)
    response = client.get("/")
    assert response.status_code == 200 and '<html lang="hr">' in response.get_data(as_text=True)
    assert "Cookie" in response.headers["Vary"]


@pytest.mark.parametrize("lang, expected", [
    ("de", {"current": "17.10.2026 15:30:45", "day_diff": "46 Tage, 7 Stunden, 0 Minuten und 45 Sekunden",
            "week_diff": "6 Wochen und 4 Tage", "year_diff": "0 Jahre, 1 Monat und 16 Tage"}),
    ("it", {"current": "17/10/2026 15:30:45", "day_diff": "46 giorni, 7 ore, 0 minuti e 45 secondi",
            "week_diff": "6 settimane e 4 giorni", "year_diff": "0 anni, 1 mese e 16 giorni"}),
])
def test_calculate_german_and_italian(client, frozen_time, lang, expected):
    status, body = post(client, datetime="2026-09-01T08:30", lang=lang)
    assert status == 200
    assert {k: body[k] for k in expected} == expected
    assert post(client, datetime="bad", lang=lang)[1]["error"] == {
        "de": "Ungültiges Geburtsdatum oder ungültige Geburtszeit.", "it": "Data e ora di nascita non valide."}[lang]

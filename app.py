import hashlib
import json
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from i18n import API_ERRORS, LANGUAGES, PAGE_TEXT, UNSUPPORTED_LANG
from utils_dt import calculate_date_difference, format_datetime, join_units

APP_VERSION = "2.15"

# Cached by the service worker for offline use (besides the page itself)
SCRIPTS = ["texts", "dates", "calendar", "data", "app"]  # load order, see templates/index.html
PRECACHED_STATIC = ["styles/main.css", *(f"js/{name}.js" for name in SCRIPTS), "favicon.ico",
                    "apple-touch-icon.png", "manifest.json", "manifest-en.json"]

app = Flask(__name__)
# nginx is the only proxy in front of the app; trust its X-Forwarded-* headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    # One Gunicorn worker, so in-process storage is enough; use Redis if workers are added
    storage_uri="memory://",
)
throttle_string = "1 per second; 8 per minute; 32 per hour"

@app.url_defaults
def static_cache_buster(endpoint, values):
    # nginx caches /static for a year; the file's mtime in the URL makes browsers fetch changed files
    if endpoint == 'static' and 'filename' in values:
        path = os.path.join(app.static_folder, values['filename'])
        if os.path.isfile(path):
            values['v'] = int(os.stat(path).st_mtime)

PAGE_ENDPOINTS = {"hr": "index", "en": "index_en"}


def render_page(lang):
    page_urls = {code: url_for(PAGE_ENDPOINTS[code], _external=True) for code in LANGUAGES}
    other_lang = "en" if lang == "hr" else "hr"
    return render_template('index.html', version=APP_VERSION, lang=lang, t=PAGE_TEXT[lang],
                           page_urls=page_urls, other_lang=other_lang)

@app.route('/')
@limiter.exempt
def index():
    # Visitors who chose English (the "lang" cookie, set by the language switch) go straight to /en/;
    # the browser keeps any "#..." part of the URL across the redirect
    if request.cookies.get('lang') == 'en':
        query = request.query_string.decode()
        response = redirect(url_for('index_en') + (f'?{query}' if query else ''))
    else:
        response = make_response(render_page("hr"))
    response.vary.add('Cookie')
    return response

@app.route('/en/')
@limiter.exempt
def index_en():
    return render_page("en")

@app.route('/health')
@limiter.exempt
def health():
    # For uptime monitoring (.github/workflows/uptime.yml)
    response = jsonify({"status": "ok", "version": APP_VERSION})
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/robots.txt')
@limiter.exempt
def robots():
    body = f"User-agent: *\nDisallow: /calculate\nDisallow: /health\n\nSitemap: {url_for('sitemap', _external=True)}\n"
    return Response(body, mimetype='text/plain')

@app.route('/sitemap.xml')
@limiter.exempt
def sitemap():
    page_urls = {code: url_for(PAGE_ENDPOINTS[code], _external=True) for code in LANGUAGES}
    return Response(render_template('sitemap.xml', page_urls=page_urls), mimetype='application/xml')

@app.errorhandler(404)
def not_found(e):
    lang = "en" if request.path.startswith("/en/") else "hr"
    return render_template('404.html', lang=lang, t=PAGE_TEXT[lang], home=url_for(PAGE_ENDPOINTS[lang])), 404

@app.route('/sw.js')
@limiter.exempt
def service_worker():
    # Served from the root so it can control the whole site, not just /static/
    pages = [url_for(endpoint) for endpoint in PAGE_ENDPOINTS.values()]
    assets = pages + [url_for('static', filename=name) for name in PRECACHED_STATIC]
    version = hashlib.sha256(json.dumps([APP_VERSION, assets]).encode()).hexdigest()[:12]
    response = make_response(render_template('sw.js', version=version, assets=assets, pages=pages))
    response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
    response.headers['Cache-Control'] = 'no-cache'
    return response

DEFAULT_TZ = "Europe/Zagreb"


def api_input():
    """Form fields or a JSON object, as a plain dict of strings."""
    if request.is_json:
        data = request.get_json(silent=True)
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}
    return request.form


@app.route('/calculate', methods=['POST'])
@limiter.limit(throttle_string)
def calculate():
    data = api_input()
    lang = data.get('lang') or 'hr'
    if lang not in LANGUAGES:
        return jsonify({"error": UNSUPPORTED_LANG}), 400
    errors = API_ERRORS[lang]

    try:
        birth_wall = datetime.strptime(data.get('datetime', ''), '%Y-%m-%dT%H:%M')
    except ValueError:
        return jsonify({"error": errors["invalid_datetime"]}), 400

    # IANA time zone of the caller (e.g. "Asia/Tokyo"); the birth time is read in this zone too
    tz_name = data.get('tz') or DEFAULT_TZ
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return jsonify({"error": errors["unknown_tz"]}), 400
    now = datetime.now(zone)
    birth = birth_wall.replace(tzinfo=zone)
    now_wall = now.replace(tzinfo=None)
    if birth_wall > now_wall:
        return jsonify({"error": errors["future"]}), 400

    # Calendar values (years, months, days, weeks) use wall-clock time; the elapsed time is real time, which
    # differs by an hour when a summer/winter time change lies in between
    calendar_days = (now_wall - birth_wall).days
    weeks, week_days = divmod(calendar_days, 7)
    years, months, days = calculate_date_difference(birth_wall, now_wall)
    elapsed = now.astimezone(UTC) - birth.astimezone(UTC)
    hours, rest = divmod(elapsed.seconds, 3600)
    minutes, seconds = divmod(rest, 60)

    return jsonify({
        "current": format_datetime(now_wall, lang=lang),
        "day_diff": join_units(
            [(elapsed.days, "day"), (hours, "hour"), (minutes, "minute"), (seconds, "second")], lang),
        "week_diff": join_units([(weeks, "week"), (week_days, "day")], lang),
        "year_diff": join_units([(years, "year"), (months, "month"), (days, "day")], lang),
        "age": {
            "calendar": {"years": years, "months": months, "days": days},
            "weeks": {"weeks": weeks, "days": week_days},
            "elapsed": {"days": elapsed.days, "hours": hours, "minutes": minutes, "seconds": seconds,
                        "total_seconds": int(elapsed.total_seconds())},
        },
        "birth": birth.isoformat(),
        "now": now.replace(microsecond=0).isoformat(),
        "tz": tz_name,
        "lang": lang,
    })

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path != '/calculate':
        return e
    data = api_input()
    lang = data.get('lang') if data.get('lang') in LANGUAGES else 'hr'
    return jsonify({"error": API_ERRORS[lang]["rate_limited"]}), 429


if __name__ == '__main__':
    app.run(debug=True)

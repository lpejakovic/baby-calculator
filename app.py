from flask import Flask, Response, render_template, request, jsonify, make_response, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
import hashlib
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from i18n import LANGUAGES, PAGE_TEXT
from utils_dt import (YEARS, MONTHS, WEEKS, DAYS, HOURS, MINUTES, SECONDS,
                      plural, format_datetime, calculate_date_difference)

APP_VERSION = "2.9"

# Cached by the service worker for offline use (besides the page itself)
PRECACHED_STATIC = ["styles/main.css", "js/app.js", "favicon.ico", "apple-touch-icon.png",
                    "manifest.json", "manifest-en.json"]

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
    return render_page("hr")

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

@app.route('/calculate', methods=['POST'])
@limiter.limit(throttle_string)
def calculate():
    try:
        input_datetime = datetime.strptime(request.form.get('datetime', ''), '%Y-%m-%dT%H:%M')
    except ValueError:
        return jsonify({"error": "Neispravan datum i vrijeme rođenja."}), 400

    # Optional IANA time zone (e.g. "Europe/Zagreb"); without it the server's local time is used
    tz_name = request.form.get('tz')
    try:
        current_datetime = datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None) if tz_name else datetime.now()
    except (ZoneInfoNotFoundError, ValueError):
        return jsonify({"error": "Nepoznata vremenska zona."}), 400
    if input_datetime > current_datetime:
        return jsonify({"error": "Datum rođenja ne može biti u budućnosti."}), 400

    difference = current_datetime - input_datetime
    days = difference.days
    hours = difference.seconds // 3600
    minutes = (difference.seconds % 3600) // 60
    seconds = difference.seconds % 60
    weeks, week_days = divmod(days, 7)
    years_diff, months_diff, days_diff = calculate_date_difference(input_datetime, current_datetime)

    result = {
        "current": format_datetime(current_datetime),
        "day_diff": f"{days} {plural(days, DAYS)}, {hours} {plural(hours, HOURS)}, "
                    f"{minutes} {plural(minutes, MINUTES)} i {seconds} {plural(seconds, SECONDS)}",
        "week_diff": f"{weeks} {plural(weeks, WEEKS)} i {week_days} {plural(week_days, DAYS)}",
        "year_diff": f"{years_diff} {plural(years_diff, YEARS)}, {months_diff} {plural(months_diff, MONTHS)} "
                     f"i {days_diff} {plural(days_diff, DAYS)}",
    }
    return jsonify(result)

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path != '/calculate':
        return e
    return jsonify({"error": "Previše zahtjeva. Pokušajte ponovno kasnije."}), 429


if __name__ == '__main__':
    app.run(debug=True)

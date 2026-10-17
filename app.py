import hashlib
import json
import os
from datetime import date

from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from api import api
from extensions import limiter
from i18n import LANGUAGE_NAMES, LANGUAGES, PAGE_TEXT

APP_VERSION = "2.24"
SOURCE_URL = "https://github.com/lpejakovic/baby-calculator"

# Cached by the service worker for offline use (besides the page itself)
SCRIPTS = ["texts", "dates", "who-growth", "growth", "calendar", "data", "card", "app"]  # load order
PRECACHED_STATIC = ["styles/main.css", *(f"js/{name}.js" for name in SCRIPTS), "favicon.ico",
                    "apple-touch-icon.png", "images/icon-512.png", "manifest.json",
                    *(f"manifest-{code}.json" for code in LANGUAGES if code != "hr")]

app = Flask(__name__)
# nginx is the only proxy in front of the app; trust its X-Forwarded-* headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

limiter.init_app(app)
app.register_blueprint(api)  # POST /calculate

@app.url_defaults
def static_cache_buster(endpoint, values):
    # nginx caches /static for a year; the file's mtime in the URL makes browsers fetch changed files
    if endpoint == 'static' and 'filename' in values:
        path = os.path.join(app.static_folder, values['filename'])
        if os.path.isfile(path):
            values['v'] = int(os.stat(path).st_mtime)

OTHER_LANGUAGES = [code for code in LANGUAGES if code != "hr"]  # served at /en/, /de/, /it/


def page_url(lang, **kwargs):
    """Croatian is the default page "/"; the other languages are "/<lang>/"."""
    return url_for('index', **kwargs) if lang == "hr" else url_for('index_lang', lang=lang, **kwargs)


def page_urls():
    return {code: page_url(code, _external=True) for code in LANGUAGES}


def render_page(lang):
    return render_template('index.html', version=APP_VERSION, lang=lang, t=PAGE_TEXT[lang], scripts=SCRIPTS,
                           page_urls=page_urls(), language_names=LANGUAGE_NAMES, year=date.today().year,
                           source_url=SOURCE_URL)

@app.route('/')
@limiter.exempt
def index():
    # Visitors who chose another language (the "lang" cookie, set by the language switch) go straight to its
    # page; the browser keeps any "#..." part of the URL across the redirect
    chosen = request.cookies.get('lang')
    if chosen in OTHER_LANGUAGES:
        query = request.query_string.decode()
        response = redirect(page_url(chosen) + (f'?{query}' if query else ''))
    else:
        response = make_response(render_page("hr"))
    response.vary.add('Cookie')
    return response

@app.route(f"/<any({', '.join(OTHER_LANGUAGES)}):lang>/")
@limiter.exempt
def index_lang(lang):
    return render_page(lang)

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
    return Response(render_template('sitemap.xml', page_urls=page_urls()), mimetype='application/xml')

@app.errorhandler(404)
def not_found(e):
    first = request.path.strip('/').split('/')[0]
    lang = first if first in OTHER_LANGUAGES else "hr"
    return render_template('404.html', lang=lang, t=PAGE_TEXT[lang], home=page_url(lang)), 404

@app.route('/sw.js')
@limiter.exempt
def service_worker():
    # Served from the root so it can control the whole site, not just /static/
    pages = [page_url(code) for code in LANGUAGES]
    assets = pages + [url_for('static', filename=name) for name in PRECACHED_STATIC]
    version = hashlib.sha256(json.dumps([APP_VERSION, assets]).encode()).hexdigest()[:12]
    response = make_response(render_template('sw.js', version=version, assets=assets, pages=pages))
    response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
    response.headers['Cache-Control'] = 'no-cache'
    return response


if __name__ == '__main__':
    app.run(debug=True)

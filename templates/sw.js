// Service worker, rendered by Flask (app.py: service_worker). The asset URLs carry ?v=<mtime>,
// so this file changes whenever a static file changes, and browsers install the new version.
const CACHE = 'bc-{{ version }}';
const PRECACHE = {{ assets|tojson }};
const PAGES = {{ pages|tojson }};

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE)
            .then((cache) => cache.addAll(PRECACHE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys
                .filter((key) => key.startsWith('bc-') && key !== CACHE)
                .map((key) => caches.delete(key))))
            .then(() => self.clients.claim())
    );
});

function cacheCopy(key, response) {
    if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(key, copy));
    }
    return response;
}

self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin) return;

    if (request.mode === 'navigate' && PAGES.includes(url.pathname)) {
        // Network first so updates show up straight away; the cached page works offline
        event.respondWith(
            fetch(request)
                .then((response) => cacheCopy(url.pathname, response))
                .catch(() => caches.match(url.pathname))
        );
    } else if (url.pathname.startsWith('/static/')) {
        // Versioned URLs never change content, so the cache can answer first
        event.respondWith(
            caches.match(request).then((cached) => cached || fetch(request).then((response) => cacheCopy(request, response)))
        );
    }
});

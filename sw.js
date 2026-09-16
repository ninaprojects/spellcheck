// Minimal service worker. Two jobs right now:
// 1. Its mere existence is what makes browsers treat this site as
//    "installable" (Add to Home Screen / Install App).
// 2. Basic offline fallback, if there's no connection, you still get
//    the last version you loaded instead of a blank error page.
// This is also the foundation a future push-notification feature would
// build on (a 'push' event listener would get added here later).

const CACHE_NAME = 'practical-magic-v1';
const PRECACHE_URLS = ['./', './index.html'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch(() => { /* fine if precaching fails, not critical */ })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Network-first: always try to get the live version. Only fall back
  // to whatever's cached if the network request fails (offline).
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

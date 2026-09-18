// Minimal service worker. A few jobs:
// 1. Its mere existence is what makes browsers treat this site as
//    "installable" (Add to Home Screen / Install App).
// 2. Basic offline fallback, if there's no connection, you still get
//    the last version you loaded instead of a blank error page.
// 3. Receiving push notifications sent via Firebase Cloud Messaging,
//    and showing them even when this site isn't open.

// STEP 2: same Firebase config as index.html, needed here too because
// this file runs in its own separate worker context that can't see
// anything from the page itself.
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyBMsNA93P1g8ND5OLMPFh6uSBSEDlOz8mk",
  authDomain: "cast-and-check.firebaseapp.com",
  projectId: "cast-and-check",
  storageBucket: "cast-and-check.firebasestorage.app",
  messagingSenderId: "936031353099",
  appId: "1:936031353099:web:312bb33e8939843497ca0e"
});

// This is kept initialized because the page still needs it to generate
// a device token (getToken). But we no longer rely on Firebase's own
// automatic "notification message" display, that's the part iOS Safari
// doesn't handle reliably. Instead, we listen to the raw push event
// ourselves below and show the notification manually, every time,
// regardless of platform quirks.
const messaging = firebase.messaging();

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    console.error('push payload parse failed', e);
  }
  // Our data-only messages land in payload.data. Fall back to
  // payload.notification or the raw payload just in case the wire
  // format ever differs.
  const data = payload.data || payload.notification || payload || {};
  const title = data.title || 'Spell Check';
  const body = data.body || '';
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: 'icon-192.png'
    })
  );
});

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

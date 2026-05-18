const CACHE = 'raidfun-v3'
const ASSETS = ['/app.js', '/style.css', '/manifest.json']

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)))
  self.skipWaiting()
})

self.addEventListener('activate', e => {
  // Clear old caches on activate
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  )
  self.clients.claim()
})

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)
  // Only cache same-origin static assets.
  // Skip: cross-origin requests (API/backend), index.html, and config.js (must stay fresh)
  if (url.origin !== self.location.origin) return
  if (
    url.pathname === '/' ||
    url.pathname.endsWith('/index.html') ||
    url.pathname.endsWith('/config.js')
  ) return
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)))
})

// Service worker of the logistics map.
//  - App shell (index.html, JS/CSS with hash in the name, icons, map image): cache first, refresh in the background
//  - /api/*: network first; offline the last stored state (the page shows its age)
//  - Writing requests (POST) never from the cache
const SHELL = 'shell-v4', API = 'api-v2';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(['/', '/manifest.webmanifest', '/icon-192.png', '/icon.svg'])));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => ![SHELL, API].includes(k)).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    // Don't hoard large, rarely changing data and history
    if (/\/api\/(frames|series|train-flow)/.test(u.pathname)) return;
    e.respondWith(fetch(e.request).then(r => {
      if (r.ok) { const c = r.clone(); caches.open(API).then(x => x.put(u.pathname, c)); }
      return r;
    }).catch(async () => {
      // From the cache, but flagged — the page then shows "offline · last state"
      const r = await caches.open(API).then(x => x.match(u.pathname));
      if (!r) return new Response('{"error":"offline"}', { status: 503, headers: { 'Content-Type': 'application/json' } });
      const h = new Headers(r.headers); h.set('X-From-Cache', '1'); h.delete('ETag');
      return new Response(await r.blob(), { status: 200, headers: h });
    }));
    return;
  }
  // Navigation (index.html): network first — otherwise an installed app shows an old page after every deploy
  // that references assets that no longer exist. Offline: stored page.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then(r => { if (r.ok) caches.open(SHELL).then(c => c.put('/', r.clone())); return r; })
      .catch(() => caches.open(SHELL).then(c => c.match('/'))));
    return;
  }
  // JS/CSS/images: files with a hash in the name never change → cache first
  e.respondWith(caches.open(SHELL).then(async c => {
    const hit = await c.match(e.request);
    if (hit) return hit;
    const r = await fetch(e.request);
    if (r.ok && (r.headers.get('Content-Type') || '').indexOf('text/html') < 0) c.put(e.request, r.clone());
    return r;
  }));
});
